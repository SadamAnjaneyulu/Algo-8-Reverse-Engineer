// Simulation / execution layer (mirrors python/pc/engine.py). Plugins never touch the ledger or the book.
#pragma once
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include "pc/plugins.hpp"
namespace pc {
using Catalog = std::map<std::string, std::function<std::shared_ptr<Plugin>()>>;

inline Registry build_registry(const Scenario& sc, const Catalog& extra = {}) {
  Registry reg;
  for (auto& t : sc.plugins) {
    const std::string& name = std::get<0>(t); std::shared_ptr<Plugin> p; auto it = extra.find(name); if (it != extra.end()) p = it->second(); else p = make_builtin(name);
    if (!p) throw ConfigError("scenario names unknown plugin '" + name + "'");
    Config cfg; auto c = sc.configs.find(name); if (c != sc.configs.end()) cfg = c->second; p->configure(cfg); reg.add(p, std::get<2>(t)); reg.require_version(name, std::get<1>(t));
  }
  return reg;
}

class Simulation {
 public:
  Scenario sc; Registry registry; std::map<std::string, i64> lots; std::map<std::string, pe::Instrument> ins; std::unique_ptr<pe::PortfolioState> ledger; Book book; MarkStore marks; Limits limits;
  std::vector<pe::Fill> fills; std::vector<std::string> dec_rows, act_rows, state_rows, lin_rows; i64 pc_n = 0; std::size_t seed_i = 0; std::map<std::string, i64> counts; bool done = false;

  explicit Simulation(const Scenario& s, const Catalog& extra = {}) : sc(s), registry(build_registry(s, extra)), lots(s.instruments), limits(parse_risk(s.risk)) {
    for (auto& kv : lots) {
      auto f = split(kv.first, '|'); pe::Instrument i; i.id = kv.first; i.underlying = f.at(0); i.segment = "NSEFO"; i.type = "OPTION"; i.option_type = f.at(2); i.strike = std::stoll(f.at(3)); i.expiry = f.at(1); i.lot_size = kv.second; i.tick_paise = pe::kTickPaise;
      i.lot_source = "SYNTHETIC"; i.is_call = i.option_type == "CE"; i.expiry_day = pe::iso_day(i.expiry); ins[kv.first] = i;
    }
    ledger = std::make_unique<pe::PortfolioState>(pe::parse_method(s.method), ins);
    for (auto& m : s.marks) marks.add(std::get<0>(m), std::get<1>(m), std::get<2>(m));
    marks.finish();
  }

  static std::string S(i64 x) { return std::to_string(x); }
  static std::string row(const std::vector<std::string>& v) { std::string o; for (std::size_t i = 0; i < v.size(); ++i) { if (i) o += '\t'; o += v[i]; } return o; }
  std::map<std::string, i64> inv() const { std::map<std::string, i64> m; for (auto& kv : ins) m[kv.first] = ledger->signed_inventory(kv.first); return m; }
  void bump(const std::string& k) { counts[k] += 1; }
  void reconcile() {
    std::map<std::string, i64> claims; for (auto& b : book.baskets) for (auto& l : b.second) claims[l.second.instrument_id] += l.second.side * l.second.current;
    for (auto& kv : ins) if (ledger->signed_inventory(kv.first) != claims[kv.first]) throw EngineInvariantError("ledger inventory != basket claims for " + kv.first);
  }
  void fill(const std::string& fid, const std::string& iid, i64 ts, int side, i64 qty, i64 px, const std::string& parent, const std::string& source) {
    pe::Fill f; f.fill_id = fid; f.source_row = (i64)fills.size() + 1; f.parent_id = parent; f.module_tag = "pc"; f.instrument_id = iid; f.ts = ts; f.side = side; f.qty = qty; f.price = px; f.requested = qty; f.status = "Filled"; f.duplicate = false;
    f.mode = "SYNTHETIC_TEST"; f.evidence = source; ledger->apply_fill(f); fills.push_back(f);
  }
  void state(i64 ts, const std::string& event, const std::string& action, const std::string& bid, const std::string& touched, i64 before, i64 after) {
    auto e = exposure(inv(), {});
    for (auto& kv : book.baskets.at(bid)) {
      const Leg& l = kv.second; const bool t = kv.first == touched;
      state_rows.push_back(row({S((i64)state_rows.size() + 1), S(ts), event, action, bid, kv.first, l.instrument_id, S(l.side), S(l.initial), S(t ? before : l.current), S(t ? after : l.current), book.status(bid), S(ledger->signed_inventory(l.instrument_id)), S(e.first), S(e.second)}));
    }
  }
  EvalContext context(i64 ts) const {
    EvalContext c; c.ts = ts; c.marks = marks.truncated(ts); c.lots = lots;
    for (auto& b : book.baskets) { BasketView bv; bv.basket_id = b.first; bv.status = book.status(b.first); for (auto& l : b.second) bv.legs.push_back({b.first, l.first, l.second.instrument_id, l.second.side, l.second.initial, l.second.current, l.second.entry_price(), l.second.cuts_done}); c.baskets.push_back(bv); }
    for (auto& k : book.cuts) { const Cut& x = k.second; c.cuts.push_back({x.cut_id, x.basket_id, x.leg_id, book.baskets.at(x.basket_id).at(x.leg_id).instrument_id, x.qty, x.ts, x.price, x.reentered, x.reentries}); }
    for (auto& a : sc.actions) if (a.ts == ts) c.scripted.push_back(a);
    return c;
  }
  void apply_seeds(i64 upto) {
    while (seed_i < sc.seeds.size() && sc.seeds[seed_i].ts <= upto) {
      const SeedLeg d = sc.seeds[seed_i++]; Leg* leg = book.leg(d.basket_id, d.leg_id); const i64 before = leg ? leg->current : 0;
      fill(d.fill_id, d.instrument_id, d.ts, d.side, d.qty, d.price, "seed:" + d.basket_id, "pc:SEED"); book.seed(d.basket_id, d.leg_id, d.instrument_id, d.side, d.qty, d.price, d.fill_id); reconcile(); bump("seed_fills");
      state(d.ts, d.fill_id, "SEED", d.basket_id, d.leg_id, before, book.leg(d.basket_id, d.leg_id)->current);
      lin_rows.push_back(row({d.fill_id, "SEED", "", d.basket_id, d.leg_id, d.instrument_id, S(d.qty), "", d.fill_id}));
    }
  }
  static bool printable(const std::string& s) { for (unsigned char c : s) if (c < 32 || c > 126) return false; return true; }
  static bool invalid_output(const Plugin& p, const PluginResult& r, i64 ts) {            // a result must be plain data with printable ASCII text and honest decision stamps (fail closed otherwise)
    if (r.status != "OK" && r.status != "NO_ACTION" && r.status != "ERROR") return true;
    for (auto& d : r.decisions) {
      for (const std::string* x : {&d.plugin, &d.version, &d.basket_id, &d.leg_id, &d.outcome, &d.reason, &d.detail}) if (!printable(*x)) return true;
      if (d.plugin != p.name() || d.version != p.version() || d.ts != ts || d.info_ts > d.ts || (d.outcome != "PROPOSED" && d.outcome != "NOT_PROPOSED")) return true;
    }
    for (auto& a : r.actions) for (const std::string* x : {&a.action_id, &a.plugin, &a.version, &a.type, &a.group_id, &a.basket_id, &a.leg_id, &a.parent_cut_id, &a.reason}) if (!printable(*x)) return true;
    return false;
  }
  void run_plugin(const std::shared_ptr<Plugin>& plugin, i64 ts) {
    PluginResult res;
    try { plugin->evaluate(context(ts), res); }
    catch (const std::exception&) {
      dec_rows.push_back(row({S((i64)dec_rows.size() + 1), S(ts), plugin->name(), plugin->version(), "*", "*", "NOT_PROPOSED", "PLUGIN_ERROR", "plugin raised an exception", plugin->config_hash(), S(ts)})); bump("plugin_errors"); return; }
    if (invalid_output(*plugin, res, ts)) {
      dec_rows.push_back(row({S((i64)dec_rows.size() + 1), S(ts), plugin->name(), plugin->version(), "*", "*", "NOT_PROPOSED", "PLUGIN_ERROR", "invalid plugin output", plugin->config_hash(), S(ts)})); bump("plugin_errors"); return; }
    for (auto& d : res.decisions) { dec_rows.push_back(row({S((i64)dec_rows.size() + 1), S(d.ts), d.plugin, d.version, d.basket_id, d.leg_id, d.outcome, d.reason, d.detail, plugin->config_hash(), S(d.info_ts)})); bump("decision_" + d.outcome); }
    std::vector<std::pair<std::string, std::vector<ProposedAction>>> groups;
    for (auto& a : res.actions) {
      if (!a.group_id.empty()) { bool found = false; for (auto& g : groups) if (g.first == a.group_id) { g.second.push_back(a); found = true; break; } if (!found) groups.push_back({a.group_id, {a}}); }
      else groups.push_back({"", {a}});
    }
    for (auto& g : groups) handle_group(*plugin, g.second, ts);
  }
  void handle_group(const Plugin& plugin, const std::vector<ProposedAction>& acts, i64 ts) {
    Projection proj; proj.book = book; auto cur = inv(); std::vector<std::optional<std::pair<std::string, std::string>>> reasons; std::optional<std::pair<std::string, std::string>> failed_id;
    std::string failed_action; bool failed = false;
    for (auto& a : acts) {
      if (failed) { reasons.push_back(std::make_pair(std::string("GROUP_REJECTED"), "group member " + failed_action + " failed")); continue; }
      auto r = check(a, ts, proj, cur, lots, limits, plugin);
      if (!r) {
        Leg* leg = proj.book.leg(a.basket_id, a.leg_id); const int sign = a.type == "CUT" ? -leg->side : leg->side; proj.delta[leg->instrument_id] += sign * a.qty; proj.book.seen_ids.insert(a.action_id);
        if (a.type == "CUT") proj.book.cut(a, ts, 0, "-"); else proj.book.reenter(a); reasons.push_back(std::nullopt);
      } else { failed = true; failed_action = a.action_id; reasons.push_back(r); }
    }
    for (std::size_t i = 0; i < acts.size(); ++i) {
      const ProposedAction& a = acts[i]; book.seen_ids.insert(a.action_id); bump("proposed");
      if (failed) { auto rr = reasons[i] ? *reasons[i] : std::make_pair(std::string("GROUP_REJECTED"), "group member " + failed_action + " failed"); reject(a, ts, rr.first, rr.second); continue; }
      execute(a, ts);
    }
  }
  void reject(const ProposedAction& a, i64 ts, const std::string& reason, const std::string& detail) {
    act_rows.push_back(row({S((i64)act_rows.size() + 1), S(ts), a.action_id, a.plugin, a.version, a.type, a.group_id, a.basket_id, a.leg_id, S(a.qty), a.parent_cut_id, S(a.info_ts), "REJECTED", reason, detail, "", "", ""}));
    bump("rejected"); bump("reason_" + reason); Leg* leg = book.leg(a.basket_id, a.leg_id); if (leg) state(ts, "-", a.action_id, a.basket_id, a.leg_id, leg->current, leg->current);
  }
  void execute(const ProposedAction& a, i64 ts) {
    Leg* leg = book.leg(a.basket_id, a.leg_id); const i64 before = leg->current; auto m = marks.at(leg->instrument_id, ts); const i64 px = m ? m->first : leg->last_price;            // no mark yet: the leg's latest actual fill price (always a valid tick)
    const int side = a.type == "CUT" ? -leg->side : leg->side; ++pc_n; char b[40]; std::snprintf(b, sizeof b, "PC%06lld", (long long)pc_n); const std::string fid = b;
    fill(fid, leg->instrument_id, ts, side, a.qty, px, a.action_id, "pc:" + a.plugin + "@" + a.version);
    if (a.type == "CUT") book.cut(a, ts, px, fid); else book.reenter(a, px);
    reconcile(); bump("accepted");
    act_rows.push_back(row({S((i64)act_rows.size() + 1), S(ts), a.action_id, a.plugin, a.version, a.type, a.group_id, a.basket_id, a.leg_id, S(a.qty), a.parent_cut_id, S(a.info_ts), "ACCEPTED", "OK", "", fid, S(side), S(px)}));
    state(ts, fid, a.action_id, a.basket_id, a.leg_id, before, leg->current);
    std::string seeds; for (std::size_t i = 0; i < leg->seed_fills.size(); ++i) { if (i) seeds += ","; seeds += leg->seed_fills[i]; }
    lin_rows.push_back(row({fid, a.type, a.action_id, a.basket_id, a.leg_id, leg->instrument_id, S(a.qty), a.parent_cut_id, seeds}));
  }
  Simulation& run() {
    if (done) return *this;
    std::set<i64> times(sc.ticks.begin(), sc.ticks.end());
    for (i64 t : times) { apply_seeds(t); for (auto& p : registry.enabled()) run_plugin(p, t); }
    apply_seeds((i64)1 << 62); done = true; return *this;
  }
  static std::string tsv(const std::string& note, const std::vector<std::string>& cols, const std::vector<std::string>& rows) { std::string o = "# " + note + "\n" + row(cols) + "\n"; for (auto& r : rows) o += r + "\n"; return o; }
  std::map<std::string, std::string> files() {
    run(); const std::string note = std::string(kEvidence) + "; scenario=" + sc.name + "; not Algo 8 data"; std::map<std::string, std::string> out;
    std::string ev = "# " + note + "\n" + row(pe::kEventColumns) + "\n"; for (auto& x : fills) ev += row({pe::kSchemaFill, x.mode, x.fill_id, S(x.source_row), x.parent_id, x.module_tag, x.instrument_id, S(x.ts), S(x.side), S(x.qty), S(x.price), S(x.requested), x.status, "0", x.evidence}) + "\n";
    std::string is = "# " + note + "\n" + row(pe::kInstrumentColumns) + "\n"; for (auto& kv : ins) { const pe::Instrument& i = kv.second; is += row({i.id, i.underlying, i.segment, i.type, i.option_type, S(i.strike), i.expiry, S(i.lot_size), S(i.tick_paise), i.lot_source}) + "\n"; }
    auto e = exposure(inv(), {}); std::string ids; for (auto& kv : ins) { if (!ids.empty()) ids += ";"; ids += kv.first + ":" + S(ledger->signed_inventory(kv.first)); }
    std::string plugs; for (auto& r : registry.list()) { if (!plugs.empty()) plugs += ","; plugs += r.name + "@" + r.version + ":" + (r.enabled ? "1" : "0") + ":" + r.hash; }
    std::vector<std::string> sm; auto kv = [&](const std::string& k, const std::string& v) { sm.push_back(k + "\t" + v); };
    auto C = [&](const std::string& k) { auto it = counts.find(k); return S(it == counts.end() ? 0 : it->second); };
    kv("scenario", sc.name); kv("evidence", kEvidence); kv("method", sc.method); kv("plugins", plugs); kv("seed_fills_applied", C("seed_fills")); kv("duplicate_seed_events_ignored", S(sc.duplicate_seeds)); kv("actions_proposed", C("proposed"));
    kv("actions_accepted", C("accepted")); kv("actions_rejected", C("rejected")); kv("plugin_errors", C("plugin_errors"));
    for (auto& c : counts) if (c.first.rfind("reason_", 0) == 0) kv("rejected_" + c.first.substr(7), S(c.second));
    kv("fills_total", S((i64)fills.size())); kv("final_gross_units", S(e.first)); kv("final_short_units", S(e.second)); kv("final_realized_pnl_paise", ledger->avg ? pe::fmt6(ledger->realized_total_d()) : S(ledger->realized_total_i())); kv("final_inventory_digest", fnv1a64(ids));
    out["decisions.tsv"] = tsv(note, {"seq", "ts", "plugin", "plugin_version", "basket_id", "leg_id", "outcome", "reason", "detail", "config_hash", "info_ts"}, dec_rows);
    out["actions.tsv"] = tsv(note, {"seq", "ts", "action_id", "plugin", "plugin_version", "type", "group_id", "basket_id", "leg_id", "qty", "parent_cut_id", "info_ts", "status", "reason", "detail", "fill_id", "fill_side", "fill_price_paise"}, act_rows);
    out["states.tsv"] = tsv(note, {"seq", "ts", "event_id", "action_id", "basket_id", "leg_id", "instrument_id", "leg_side", "initial_qty", "qty_before", "qty_after", "basket_status", "instrument_inventory", "gross_units", "short_units"}, state_rows);
    out["lineage.tsv"] = tsv(note, {"fill_id", "kind", "action_id", "basket_id", "leg_id", "instrument_id", "qty", "parent_cut_id", "origin_seed_fills"}, lin_rows);
    out["events.tsv"] = ev; out["instruments.tsv"] = is; out["summary.tsv"] = tsv(note, {"key", "value"}, sm); return out;
  }
  void write(const std::string& dir) { std::filesystem::create_directories(dir); for (auto& kv : files()) { std::ofstream f(dir + "/" + kv.first, std::ios::binary); f << kv.second; } }
};
}  // namespace pc
