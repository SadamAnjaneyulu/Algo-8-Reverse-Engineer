// Built-in example plugins (transparent, configurable, NOT Algo 8 rules). Mirrors python/pc/plugins/*.py.
#pragma once
#include "pc/core.hpp"
namespace pc {
inline Spec ispec(i64 def, bool hm = true, i64 mn = 0, bool hx = false, i64 mx = 0) { Spec s; s.kind = "int"; s.def = std::to_string(def); s.has_min = hm; s.minv = mn; s.has_max = hx; s.maxv = mx; return s; }
inline Spec espec(const std::string& def, std::vector<std::string> allowed) { Spec s; s.kind = "enum"; s.def = def; s.allowed = std::move(allowed); return s; }
inline Spec sspec(const std::string& def) { Spec s; s.kind = "str"; s.def = def; return s; }
inline Decision mkdec(i64 ts, const Plugin& p, const std::string& b, const std::string& l, const std::string& outcome, const std::string& reason, const std::string& detail, i64 info) { return Decision{ts, p.name(), p.version(), b, l, outcome, reason, detail, info}; }

class BasketCutPlugin : public Plugin {
 public:
  std::string name() const override { return "basket_cut"; } std::string version() const override { return "1.0.0"; }
  std::vector<std::pair<std::string, Spec>> spec() const override {
    return {{"policy", espec("MARK_ADVERSE_MOVE", {"MARK_ADVERSE_MOVE", "SCHEDULED"})}, {"trigger_bp", ispec(2000, true, 0, true, 1000000)}, {"cut_at_ts", ispec(0, true, 0, true, 100000000000LL)}, {"scope", espec("LEG", {"LEG", "BASKET"})},
            {"leg_side_filter", espec("ANY", {"ANY", "SHORT", "LONG"})}, {"option_type_filter", espec("ANY", {"ANY", "CE", "PE"})}, {"qty_mode", espec("UNITS", {"UNITS", "FRACTION_BP"})}, {"units", ispec(65, true, 0, true, 1000000000)},
            {"fraction_bp", ispec(10000, true, 0, true, 10000)}, {"clamp_to_available", ispec(0, true, 0, true, 1)}, {"max_cuts_per_leg", ispec(1, true, 1, true, 1000000)}, {"basket_filter", sspec("*")}};
  }
  i64 qty(const EvalContext& ctx, const LegView& l) const {
    if (gets("qty_mode") == "UNITS") { i64 q = geti("units"); return geti("clamp_to_available") ? std::min(q, l.current) : q; }
    const i64 lot = ctx.lot_size(l.instrument_id), lots = l.current / lot; return ((lots * geti("fraction_bp") + 5000) / 10000) * lot;
  }
  void evaluate(const EvalContext& ctx, PluginResult& res) const override {
    const i64 ts = ctx.ts; auto dec = [&](const std::string& b, const std::string& l, const std::string& o, const std::string& r, const std::string& d, i64 info) { res.decisions.push_back(mkdec(ts, *this, b, l, o, r, d, info)); };
    for (auto& bk : ctx.baskets) {
      if ((gets("basket_filter") != "*" && gets("basket_filter") != bk.basket_id) || bk.status == "FULLY_CUT") continue;
      std::vector<LegView> cand, elig;
      for (auto& l : bk.legs) {
        const bool side_ok = gets("leg_side_filter") == "ANY" || ((gets("leg_side_filter") == "SHORT") == (l.side < 0)); const bool opt_ok = gets("option_type_filter") == "ANY" || split(l.instrument_id, '|')[2] == gets("option_type_filter");
        if (side_ok && opt_ok) cand.push_back(l);
      }
      for (auto& l : cand) if (l.current > 0 && l.cuts_done < geti("max_cuts_per_leg")) elig.push_back(l);
      if (cand.empty()) { dec(bk.basket_id, "*", "NOT_PROPOSED", "NO_MATCHING_LEG", "filters select no leg", ts); continue; }
      std::map<std::string, std::pair<std::string, i64>> trig; std::vector<i64> used;
      for (auto& l : elig) {
        if (gets("policy") == "SCHEDULED") { if (ts >= geti("cut_at_ts")) trig[l.leg_id] = {"cut_at_ts=" + std::to_string(geti("cut_at_ts")), ts}; continue; }
        auto m = ctx.mark(l.instrument_id);
        if (!m) { dec(bk.basket_id, l.leg_id, "NOT_PROPOSED", "NO_MARK_AVAILABLE", "no mark at or before ts", ts); continue; }
        const i64 px = m->first, mts = m->second; used.push_back(mts); const i64 bp = geti("trigger_bp");
        const bool hit = l.side < 0 ? px * 10000 >= l.entry_price * (10000 + bp) : px * 10000 <= l.entry_price * (10000 - bp);
        if (hit) trig[l.leg_id] = {"mark=" + std::to_string(px) + " entry=" + std::to_string(l.entry_price) + " trigger_bp=" + std::to_string(bp), mts};
      }
      if (trig.empty()) {
        if (elig.empty()) dec(bk.basket_id, "*", "NOT_PROPOSED", "NO_ELIGIBLE_LEG", "no leg is eligible (no inventory or max_cuts_per_leg reached)", ts);
        else dec(bk.basket_id, "*", "NOT_PROPOSED", "NO_TRIGGER", "policy=" + gets("policy"), used.empty() ? ts : *std::max_element(used.begin(), used.end()));
        continue;
      }
      std::vector<LegView> targets; for (auto& l : elig) if (gets("scope") == "BASKET" || trig.count(l.leg_id)) targets.push_back(l);
      const std::string group = gets("scope") == "BASKET" ? name() + "|" + std::to_string(ts) + "|" + bk.basket_id : "";
      i64 maxinfo = 0; for (auto& kv : trig) maxinfo = std::max(maxinfo, kv.second.second);
      for (auto& l : targets) {
        const i64 q = qty(ctx, l); auto t = trig.find(l.leg_id); const std::string why = t == trig.end() ? "basket scope" : t->second.first; const i64 info = t == trig.end() ? maxinfo : t->second.second;
        if (q == 0) { dec(bk.basket_id, l.leg_id, "NOT_PROPOSED", "CUT_QTY_ZERO", why, ts); continue; }
        res.actions.push_back({name() + "|" + std::to_string(ts) + "|" + bk.basket_id + "|" + l.leg_id + "|CUT", name(), version(), "CUT", group, bk.basket_id, l.leg_id, q, "", ts, info, "POLICY_TRIGGERED"});
        dec(bk.basket_id, l.leg_id, "PROPOSED", "POLICY_TRIGGERED", why + " qty=" + std::to_string(q), info);
      }
    }
    res.status = res.actions.empty() ? "NO_ACTION" : "OK";
  }
};

class BasketReentryPlugin : public Plugin {
 public:
  std::string name() const override { return "basket_reentry"; } std::string version() const override { return "1.0.0"; }
  std::vector<std::pair<std::string, Spec>> spec() const override {
    return {{"cooldown_s", ispec(600, true, 0, true, 100000000000LL)}, {"max_wait_s", ispec(0, true, 0, true, 100000000000LL)}, {"max_reentries_per_cut", ispec(1, true, 1, true, 1000000)}, {"max_reentry_fraction_bp", ispec(10000, true, 0, true, 10000)}, {"qty_mode", espec("RESTORE", {"RESTORE", "UNITS"})},
            {"units", ispec(0, true, 0, true, 1000000000)}, {"price_condition", espec("NONE", {"NONE", "WITHIN_BAND"})}, {"band_bp", ispec(1000, true, 0, true, 1000000)}, {"basket_filter", sspec("*")}};
  }
  void evaluate(const EvalContext& ctx, PluginResult& res) const override {
    const i64 ts = ctx.ts; std::map<std::pair<std::string, std::string>, LegView> legs; for (auto& b : ctx.baskets) for (auto& l : b.legs) legs[{b.basket_id, l.leg_id}] = l;
    auto dec = [&](const CutView& c, const std::string& o, const std::string& r, const std::string& d, i64 info) { res.decisions.push_back(mkdec(ts, *this, c.basket_id, c.leg_id, o, r, d, info)); };
    std::vector<CutView> cuts = ctx.cuts; std::sort(cuts.begin(), cuts.end(), [](const CutView& a, const CutView& b) { return a.cut_id < b.cut_id; });
    for (auto& cut : cuts) {
      if (gets("basket_filter") != "*" && gets("basket_filter") != cut.basket_id) continue;
      const LegView& leg = legs.at({cut.basket_id, cut.leg_id}); const i64 lot = ctx.lot_size(cut.instrument_id);
      const i64 allowed = ((cut.qty / lot) * geti("max_reentry_fraction_bp") / 10000) * lot - cut.reentered, room = leg.initial - leg.current, qty = std::min(allowed, room);
      if (cut.reentries >= geti("max_reentries_per_cut") || qty <= 0) { dec(cut, "NOT_PROPOSED", "REENTRY_LIMIT_REACHED", "reentries=" + std::to_string(cut.reentries) + " reentered=" + std::to_string(cut.reentered) + " cut_qty=" + std::to_string(cut.qty), ts); continue; }
      if (ts < cut.ts + geti("cooldown_s")) { dec(cut, "NOT_PROPOSED", "COOLDOWN_ACTIVE", "cut_ts=" + std::to_string(cut.ts) + " cooldown_s=" + std::to_string(geti("cooldown_s")) + " eligible_ts=" + std::to_string(cut.ts + geti("cooldown_s")), ts); continue; }
      if (geti("max_wait_s") && ts > cut.ts + geti("max_wait_s")) { dec(cut, "NOT_PROPOSED", "WINDOW_EXPIRED", "cut_ts=" + std::to_string(cut.ts) + " max_wait_s=" + std::to_string(geti("max_wait_s")), ts); continue; }
      auto m = ctx.mark(cut.instrument_id);
      if (!m) { dec(cut, "NOT_PROPOSED", "NO_MARK_AVAILABLE", "no mark at or before ts", ts); continue; }
      const i64 px = m->first, mts = m->second;
      if (gets("price_condition") == "WITHIN_BAND" && std::llabs(px - cut.price) * 10000 > geti("band_bp") * cut.price) {
        dec(cut, "NOT_PROPOSED", "PRICE_CONDITION_NOT_MET", "mark=" + std::to_string(px) + " cut_price=" + std::to_string(cut.price) + " band_bp=" + std::to_string(geti("band_bp")), mts); continue; }
      const i64 q = gets("qty_mode") == "RESTORE" ? qty : std::min(geti("units"), qty);
      if (q <= 0) { dec(cut, "NOT_PROPOSED", "REENTRY_LIMIT_REACHED", "configured units give zero quantity", ts); continue; }
      res.actions.push_back({name() + "|" + std::to_string(ts) + "|" + cut.basket_id + "|" + cut.leg_id + "|REENTRY|" + cut.cut_id, name(), version(), "REENTRY", "", cut.basket_id, cut.leg_id, q, cut.cut_id, ts, mts, "REENTRY_ELIGIBLE"});
      dec(cut, "PROPOSED", "REENTRY_ELIGIBLE", "mark=" + std::to_string(px) + " cut_price=" + std::to_string(cut.price) + " qty=" + std::to_string(q), mts);
    }
    res.status = res.actions.empty() ? "NO_ACTION" : "OK";
  }
};

class ScriptedActionsPlugin : public Plugin {
 public:
  std::string name() const override { return "scripted_actions"; } std::string version() const override { return "1.0.0"; }
  void evaluate(const EvalContext& ctx, PluginResult& res) const override {
    for (auto& a : ctx.scripted) {
      res.actions.push_back({a.action_id, a.plugin.empty() ? name() : a.plugin, a.version.empty() ? version() : a.version, a.type, a.group_id, a.basket_id, a.leg_id, a.qty, a.parent_cut_id, a.ts, a.info_ts, "SCRIPTED"});
      res.decisions.push_back(mkdec(ctx.ts, *this, a.basket_id, a.leg_id, "PROPOSED", "SCRIPTED", "type=" + a.type + " qty=" + std::to_string(a.qty), ctx.ts));
    }
    res.status = res.actions.empty() ? "NO_ACTION" : "OK";
  }
};

inline std::shared_ptr<Plugin> make_builtin(const std::string& n) {
  if (n == "basket_cut") return std::make_shared<BasketCutPlugin>();
  if (n == "basket_reentry") return std::make_shared<BasketReentryPlugin>();
  if (n == "scripted_actions") return std::make_shared<ScriptedActionsPlugin>();
  return nullptr;
}
}  // namespace pc
