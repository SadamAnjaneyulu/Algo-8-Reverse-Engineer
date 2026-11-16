// Portfolio-construction skeleton (prototype, SYNTHETIC_TEST_ONLY): plugin contract, registry, basket book, risk validator, simulation. Mirrors python/pc rule for rule.
// Plugins propose; the engine validates and applies accepted actions as explicit synthetic fills through the UNCHANGED M2 ledger (pe::PortfolioState::apply_fill).
#pragma once
#include <algorithm>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>
#include "pe/ledger.hpp"
#include "pe/types.hpp"
namespace pc {
using pe::i64;
constexpr int kApiVersion = 1;
inline const char* kEvidence = "SYNTHETIC_TEST_ONLY";
struct ConfigError : std::runtime_error { using std::runtime_error::runtime_error; };
struct LookAheadError : std::runtime_error { using std::runtime_error::runtime_error; };
struct ScenarioError : std::runtime_error { using std::runtime_error::runtime_error; };
struct EngineInvariantError : std::runtime_error { using std::runtime_error::runtime_error; };
struct RegistryError : std::runtime_error { std::string code; RegistryError(const std::string& c, const std::string& m) : std::runtime_error(c + ": " + m), code(c) {} };

inline std::string fnv1a64(const std::string& t) {
  std::uint64_t h = 14695981039346656037ULL; for (unsigned char b : t) { h ^= b; h *= 1099511628211ULL; }
  char buf[17]; std::snprintf(buf, sizeof buf, "%016llx", (unsigned long long)h); return buf;
}
// integers: optional '-' then ASCII digits only (identical rule in python/pc/scenario.py)
inline i64 parse_int(const std::string& s, const std::string& what, i64 lo = INT64_MIN, i64 hi = INT64_MAX) {
  std::size_t k = (!s.empty() && s[0] == '-') ? 1 : 0;
  if (k == s.size() || s.size() > 20) throw ScenarioError(what + ": not a valid integer: " + s);
  for (std::size_t i = k; i < s.size(); ++i) if (s[i] < '0' || s[i] > '9') throw ScenarioError(what + ": not a valid integer: " + s);
  i64 v; try { v = std::stoll(s); } catch (...) { throw ScenarioError(what + ": integer out of range: " + s); }
  if (v < lo || v > hi) throw ScenarioError(what + ": " + std::to_string(v) + " outside " + std::to_string(lo) + ".." + std::to_string(hi));
  return v;
}
inline bool in_set(char c, const std::string& extra, bool upper, bool lower, bool digit) { return (upper && c >= 'A' && c <= 'Z') || (lower && c >= 'a' && c <= 'z') || (digit && c >= '0' && c <= '9') || extra.find(c) != std::string::npos; }
inline bool all_of_set(const std::string& s, const std::string& extra, bool upper, bool lower, bool digit, std::size_t mn, std::size_t mx) { if (s.size() < mn || s.size() > mx) return false; for (char c : s) if (!in_set(c, extra, upper, lower, digit)) return false; return true; }
inline void need_id(const std::string& s, const std::string& w) { if (!all_of_set(s, "_.:-", true, true, true, 1, 64)) throw ScenarioError(w + ": invalid id '" + s + "'"); }
inline void need_aid(const std::string& s, const std::string& w) { if (!all_of_set(s, "_.:|-", true, true, true, 1, 300)) throw ScenarioError(w + ": invalid id '" + s + "'"); }
inline bool is_name(const std::string& s) { return !s.empty() && s.size() <= 41 && s[0] >= 'a' && s[0] <= 'z' && all_of_set(s, "_", false, true, true, 1, 41); }
inline void need_name(const std::string& s, const std::string& w) { if (!is_name(s)) throw ScenarioError(w + ": invalid name '" + s + "'"); }
inline void need_key(const std::string& s, const std::string& w) { if (!all_of_set(s, "_", false, true, false, 1, 40)) throw ScenarioError(w + ": invalid key '" + s + "'"); }
inline bool is_semver(const std::string& v) { std::size_t a = v.find('.'); if (a == std::string::npos) return false; std::size_t b = v.find('.', a + 1); if (b == std::string::npos || v.find('.', b + 1) != std::string::npos) return false;
  for (auto part : {v.substr(0, a), v.substr(a + 1, b - a - 1), v.substr(b + 1)}) {
    if (part.empty() || !all_of_set(part, "", false, false, true, 1, 40)) return false;
  }
  return true;
}
inline void check_instrument_id(const std::string& id) {
  auto f = [&]() { std::vector<std::string> p; std::string cur; for (char c : id) { if (c == '|') { p.push_back(cur); cur.clear(); } else cur += c; } p.push_back(cur); return p; }(); bool ok = f.size() == 4 && all_of_set(f[0], "", true, false, false, 1, 12);
  if (ok) { const std::string& d = f[1]; ok = d.size() == 10 && d[4] == '-' && d[7] == '-' && all_of_set(d.substr(0, 4), "", false, false, true, 4, 4) && all_of_set(d.substr(5, 2), "", false, false, true, 2, 2) && all_of_set(d.substr(8, 2), "", false, false, true, 2, 2);
    if (ok) { const int mo = std::stoi(d.substr(5, 2)), dy = std::stoi(d.substr(8, 2)); ok = mo >= 1 && mo <= 12 && dy >= 1 && dy <= 31; } }
  ok = ok && (f[2] == "CE" || f[2] == "PE") && all_of_set(f[3], "", false, false, true, 1, 9);
  if (!ok) throw ScenarioError("invalid instrument id '" + id + "'");
}
constexpr i64 kMaxT = 100000000000LL, kMaxPx = 1000000000LL, kMaxQty = 10000000LL, kMaxLot = 1000000LL, kMaxActQty = 1000000000000LL, kNotionalCap = 4000000000000000000LL;
inline std::vector<std::string> split(const std::string& s, char d) { std::vector<std::string> o; std::string cur; for (char c : s) { if (c == d) { o.push_back(cur); cur.clear(); } else cur += c; } o.push_back(cur); return o; }

// ------------------------------------------------------------------ contract
struct ProposedAction { std::string action_id, plugin, version, type, group_id, basket_id, leg_id; i64 qty = 0; std::string parent_cut_id; i64 ts = 0, info_ts = 0; std::string reason; };
struct Decision { i64 ts = 0; std::string plugin, version, basket_id, leg_id, outcome, reason, detail; i64 info_ts = 0; };
struct PluginResult { std::string status = "NO_ACTION"; std::vector<ProposedAction> actions; std::vector<Decision> decisions; };
struct Spec { std::string kind; std::string def; std::vector<std::string> allowed; bool has_min = false, has_max = false; i64 minv = 0, maxv = 0; };
using Config = std::map<std::string, std::string>;

struct LegView { std::string basket_id, leg_id, instrument_id; int side = 0; i64 initial = 0, current = 0, entry_price = 0, cuts_done = 0; };
struct BasketView { std::string basket_id, status; std::vector<LegView> legs; };
struct CutView { std::string cut_id, basket_id, leg_id, instrument_id; i64 qty = 0, ts = 0, price = 0, reentered = 0, reentries = 0; };
struct ScriptedAction { i64 ts = 0; std::string action_id, plugin, version, type, basket_id, leg_id; i64 qty = 0; std::string parent_cut_id; i64 info_ts = 0; std::string group_id; };

class MarkStore {
 public:
  void add(i64 ts, const std::string& iid, i64 px) { m_[iid].push_back({ts, px}); }
  void finish() { for (auto& kv : m_) std::sort(kv.second.begin(), kv.second.end()); }
  std::shared_ptr<const MarkStore> truncated(i64 ts) const {            // a copy that holds ONLY marks with timestamp <= ts (plugins never see the full series)
    auto v = std::make_shared<MarkStore>(); for (auto& kv : m_) for (auto& e : kv.second) if (e.first <= ts) v->m_[kv.first].push_back(e); return v;
  }
  std::optional<std::pair<i64, i64>> at(const std::string& iid, i64 ts) const {
    auto it = m_.find(iid); if (it == m_.end()) return std::nullopt;
    std::optional<std::pair<i64, i64>> r; for (auto& e : it->second) { if (e.first <= ts) r = std::make_pair(e.second, e.first); else break; } return r;
  }
 private: std::map<std::string, std::vector<std::pair<i64, i64>>> m_;
};

struct EvalContext {
  i64 ts = 0; std::shared_ptr<const MarkStore> marks; std::vector<BasketView> baskets; std::vector<CutView> cuts; std::map<std::string, i64> lots; std::vector<ScriptedAction> scripted;
  std::optional<std::pair<i64, i64>> mark(const std::string& iid, i64 at_ts = -1) const {
    const i64 t = at_ts < 0 ? ts : at_ts; if (t > ts) throw LookAheadError("mark requested after the evaluation time"); return marks->at(iid, t);
  }
  i64 lot_size(const std::string& iid) const { return lots.at(iid); }
};

class Plugin {
 public:
  virtual ~Plugin() = default;
  virtual std::string name() const = 0;
  virtual std::string version() const = 0;
  virtual int api_version() const { return kApiVersion; }
  virtual std::vector<std::pair<std::string, Spec>> spec() const { return {}; }
  virtual void evaluate(const EvalContext& ctx, PluginResult& out) const = 0;
  Config config;
  void configure(const Config& in) {                                     // validates; throws ConfigError; fills defaults
    std::vector<std::string> errs; Config out; auto sp = spec();
    for (auto& kv : in) { bool known = false; for (auto& s : sp) known |= s.first == kv.first; if (!known) errs.push_back("unknown key " + kv.first); }
    for (auto& s : sp) {
      auto it = in.find(s.first); std::string v = it == in.end() ? s.second.def : it->second;
      if (s.second.kind == "int") {
        i64 x = 0; try { x = parse_int(v, s.first); } catch (const ScenarioError&) { errs.push_back(s.first + ": not an integer"); continue; }
        if (s.second.has_min && x < s.second.minv) errs.push_back(s.first + ": below minimum");
        if (s.second.has_max && x > s.second.maxv) errs.push_back(s.first + ": above maximum");
        v = std::to_string(x);
      } else if (s.second.kind == "enum") { if (std::find(s.second.allowed.begin(), s.second.allowed.end(), v) == s.second.allowed.end()) errs.push_back(s.first + ": value not allowed"); }
      out[s.first] = v;
    }
    if (!errs.empty()) { std::string m = name() + ": "; for (auto& e : errs) m += e + "; "; throw ConfigError(m); }
    config = out;
  }
  std::string config_hash() const { std::string t = name() + "@" + version() + "|"; bool first = true; for (auto& kv : config) { if (!first) t += ";"; first = false; t += kv.first + "=" + kv.second; } return fnv1a64(t); }
  i64 geti(const std::string& k) const { return std::stoll(config.at(k)); }
  const std::string& gets(const std::string& k) const { return config.at(k); }
};

// ------------------------------------------------------------------ registry
class Registry {
 public:
  void add(std::shared_ptr<Plugin> p, bool enabled = true) {
    const std::string n = p->name(); const std::string v = p->version();
    bool okname = !n.empty() && n[0] >= 'a' && n[0] <= 'z'; for (char c : n) okname &= (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_';
    if (!okname) throw RegistryError("INVALID_NAME", n);
    auto parts = split(v, '.'); bool okv = parts.size() == 3; for (auto& q : parts) { okv &= !q.empty(); for (char c : q) okv &= c >= '0' && c <= '9'; }
    if (!okv) throw RegistryError("INVALID_VERSION", v);
    if (p->api_version() != kApiVersion) throw RegistryError("INCOMPATIBLE_API_VERSION", n);
    if (items_.count(n)) throw RegistryError("DUPLICATE_NAME", n);
    items_[n] = {p, enabled}; order_.push_back(n);
  }
  std::shared_ptr<Plugin> get(const std::string& n) const { auto it = items_.find(n); if (it == items_.end()) throw RegistryError("UNKNOWN_PLUGIN", n); return it->second.first; }
  void enable(const std::string& n) { get(n); items_[n].second = true; }
  void disable(const std::string& n) { get(n); items_[n].second = false; }
  void configure(const std::string& n, const Config& c) { auto p = get(n); auto cp = p->config; try { p->configure(c); } catch (...) { p->config = cp; throw; } }
  void require_version(const std::string& n, const std::string& wanted) { if (split(get(n)->version(), '.')[0] != split(wanted, '.')[0]) throw RegistryError("INCOMPATIBLE_VERSION", n); }
  struct Row { std::string name, version; bool enabled; std::string hash; };
  std::vector<Row> list() const { std::vector<Row> r; for (auto& n : order_) r.push_back({n, items_.at(n).first->version(), items_.at(n).second, items_.at(n).first->config_hash()}); return r; }
  std::vector<std::shared_ptr<Plugin>> enabled() const { std::vector<std::shared_ptr<Plugin>> r; for (auto& n : order_) if (items_.at(n).second) r.push_back(items_.at(n).first); return r; }
 private:
  std::map<std::string, std::pair<std::shared_ptr<Plugin>, bool>> items_; std::vector<std::string> order_;
};

// ------------------------------------------------------------------ basket book (claims only; executed inventory lives in the M2 ledger)
struct Leg { std::string leg_id, basket_id, instrument_id; int side = 0; i64 initial = 0, current = 0, notional = 0, cuts_done = 0, last_price = 0; std::vector<std::string> seed_fills; i64 entry_price() const { return initial ? notional / initial : 0; } };
struct Cut { std::string cut_id, basket_id, leg_id; i64 qty = 0, ts = 0, price = 0; std::string fill_id; i64 reentered = 0, reentries = 0; };
struct Book {
  std::map<std::string, std::map<std::string, Leg>> baskets; std::map<std::string, Cut> cuts; std::set<std::string> seen_ids;
  Leg* leg(const std::string& b, const std::string& l) { auto i = baskets.find(b); if (i == baskets.end()) return nullptr; auto j = i->second.find(l); return j == i->second.end() ? nullptr : &j->second; }
  std::string status(const std::string& b) const {
    bool all0 = true, anydiff = false; for (auto& kv : baskets.at(b)) { all0 &= kv.second.current == 0; anydiff |= kv.second.current != kv.second.initial; }
    return all0 ? "FULLY_CUT" : (anydiff ? "PARTIALLY_CUT" : "ACTIVE");
  }
  void seed(const std::string& b, const std::string& l, const std::string& iid, int side, i64 qty, i64 price, const std::string& fid) {
    auto& m = baskets[b]; auto it = m.find(l); if (it == m.end()) { Leg g; g.leg_id = l; g.basket_id = b; g.instrument_id = iid; g.side = side; it = m.emplace(l, g).first; }
    Leg& g = it->second; if (g.notional + qty * price > kNotionalCap) throw EngineInvariantError("basket leg notional too large");
    g.initial += qty; g.current += qty; g.notional += qty * price; g.seed_fills.push_back(fid); g.last_price = price;
  }
  void cut(const ProposedAction& a, i64 ts, i64 price, const std::string& fid) {
    Leg* g = leg(a.basket_id, a.leg_id); g->current -= a.qty; g->cuts_done += 1; g->last_price = price; Cut c; c.cut_id = a.action_id; c.basket_id = a.basket_id; c.leg_id = a.leg_id; c.qty = a.qty; c.ts = ts; c.price = price; c.fill_id = fid; cuts[a.action_id] = c;
  }
  void reenter(const ProposedAction& a, i64 price = 0) { Leg* g = leg(a.basket_id, a.leg_id); g->current += a.qty; if (price) g->last_price = price; Cut& c = cuts[a.parent_cut_id]; c.reentered += a.qty; c.reentries += 1; }
};

// ------------------------------------------------------------------ prototype risk validation (NOT exchange margin, NOT production controls)
struct Limits { i64 max_gross_units = 1000000000, max_short_units = 1000000000, max_cut_qty_per_action = 1000000000, max_reentry_qty_per_action = 1000000000, reentry_min_cooldown_s = 0; };
inline Limits parse_risk(const std::map<std::string, i64>& cfg) {
  Limits l; for (auto& kv : cfg) { const std::string& k = kv.first; i64 v = kv.second; if (v < 0 || v > 1000000000000LL) throw ScenarioError("risk " + k + " outside 0..10^12");
    if (k == "max_gross_units") l.max_gross_units = v; else if (k == "max_short_units") l.max_short_units = v; else if (k == "max_cut_qty_per_action") l.max_cut_qty_per_action = v;
    else if (k == "max_reentry_qty_per_action") l.max_reentry_qty_per_action = v; else if (k == "reentry_min_cooldown_s") l.reentry_min_cooldown_s = v; else throw ScenarioError("unknown risk key " + k); }
  return l;
}
struct Projection { Book book; std::map<std::string, i64> delta; };
inline std::pair<i64, i64> exposure(const std::map<std::string, i64>& inv, const std::map<std::string, i64>& delta) {
  std::set<std::string> ids; for (auto& kv : inv) ids.insert(kv.first); for (auto& kv : delta) ids.insert(kv.first);
  i64 gross = 0, sh = 0; for (auto& i : ids) { i64 v = 0; auto a = inv.find(i); if (a != inv.end()) v += a->second; auto d = delta.find(i); if (d != delta.end()) v += d->second; gross += v < 0 ? -v : v; sh += v < 0 ? -v : 0; }
  return {gross, sh};
}
using Verdict = std::optional<std::pair<std::string, std::string>>;                         // empty = accepted
inline Verdict check(const ProposedAction& a, i64 now, Projection& proj, const std::map<std::string, i64>& inv, const std::map<std::string, i64>& lots, const Limits& L, const Plugin& producer) {
  Book& b = proj.book; auto R = [](const std::string& r, const std::string& d) { return Verdict(std::make_pair(r, d)); };
  if (b.seen_ids.count(a.action_id)) return R("DUPLICATE_ACTION_ID", a.action_id);
  if (a.type != "CUT" && a.type != "REENTRY") return R("INVALID_ACTION_TYPE", a.type);
  if (a.plugin != producer.name() || a.version != producer.version()) return R("PLUGIN_MISMATCH", a.plugin + "@" + a.version + " returned by " + producer.name() + "@" + producer.version());
  if (a.ts != now) return R("STALE_ACTION_TIMESTAMP", "action_ts=" + std::to_string(a.ts) + " now=" + std::to_string(now));
  if (a.info_ts > a.ts) return R("LOOKAHEAD_VIOLATION", "info_ts=" + std::to_string(a.info_ts) + " ts=" + std::to_string(a.ts));
  if (!b.baskets.count(a.basket_id)) return R("INVALID_BASKET_STATE", "unknown basket");
  Leg* leg = b.leg(a.basket_id, a.leg_id); if (!leg) return R("MISSING_OR_INVALID_LEG", a.leg_id);
  const i64 lot = lots.at(leg->instrument_id);
  if (a.qty <= 0 || a.qty % lot != 0) return R("INVALID_QUANTITY", "qty=" + std::to_string(a.qty) + " lot=" + std::to_string(lot));
  int sign;
  if (a.type == "CUT") {
    if (b.status(a.basket_id) == "FULLY_CUT") return R("INVALID_BASKET_STATE", "basket already fully cut");
    if (a.qty > leg->current) return R("INSUFFICIENT_INVENTORY", "qty=" + std::to_string(a.qty) + " available=" + std::to_string(leg->current));
    if (a.qty > L.max_cut_qty_per_action) return R("QUANTITY_LIMIT_EXCEEDED", "qty=" + std::to_string(a.qty) + " limit=" + std::to_string(L.max_cut_qty_per_action));
    sign = -leg->side;
  } else {
    auto it = b.cuts.find(a.parent_cut_id);
    if (it == b.cuts.end() || it->second.basket_id != a.basket_id || it->second.leg_id != a.leg_id) return R("INVALID_CUT_LINEAGE", "parent_cut='" + a.parent_cut_id + "'");
    const Cut& c = it->second;
    if (a.qty > L.max_reentry_qty_per_action) return R("QUANTITY_LIMIT_EXCEEDED", "qty=" + std::to_string(a.qty) + " limit=" + std::to_string(L.max_reentry_qty_per_action));
    if (a.ts < c.ts + L.reentry_min_cooldown_s) return R("COOLDOWN_NOT_ELAPSED", "ts=" + std::to_string(a.ts) + " earliest=" + std::to_string(c.ts + L.reentry_min_cooldown_s));
    if (c.reentered + a.qty > c.qty || leg->current + a.qty > leg->initial) return R("REENTRY_LIMIT_EXCEEDED", "reentered=" + std::to_string(c.reentered) + " qty=" + std::to_string(a.qty) + " cut_qty=" + std::to_string(c.qty));
    sign = leg->side;
  }
  auto e0 = exposure(inv, proj.delta); auto d = proj.delta; d[leg->instrument_id] += sign * a.qty; auto e1 = exposure(inv, d);
  if (e1.first > L.max_gross_units && e1.first > e0.first) return R("EXPOSURE_LIMIT_EXCEEDED", "gross=" + std::to_string(e1.first) + " limit=" + std::to_string(L.max_gross_units));
  if (e1.second > L.max_short_units && e1.second > e0.second) return R("EXPOSURE_LIMIT_EXCEEDED", "short=" + std::to_string(e1.second) + " limit=" + std::to_string(L.max_short_units));
  return std::nullopt;
}

// ------------------------------------------------------------------ scenario
struct SeedLeg { std::string fill_id, basket_id, leg_id, instrument_id; int side = 0; i64 qty = 0, price = 0, ts = 0; bool operator==(const SeedLeg& o) const { return std::tie(fill_id, basket_id, leg_id, instrument_id, side, qty, price, ts) == std::tie(o.fill_id, o.basket_id, o.leg_id, o.instrument_id, o.side, o.qty, o.price, o.ts); } };
struct Scenario {
  std::string name, description, method = "FIFO"; std::map<std::string, i64> instruments, risk; std::vector<std::tuple<std::string, std::string, bool>> plugins; std::map<std::string, Config> configs;
  std::vector<SeedLeg> seeds, duplicates; std::vector<std::tuple<i64, std::string, i64>> marks; std::vector<i64> ticks; std::vector<ScriptedAction> actions; i64 duplicate_seeds = 0;
  static Scenario parse(const std::string& text) {
    for (unsigned char c : text) if (c > 126 || (c < 32 && c != '\n' && c != '\t')) throw ScenarioError("scenario files must be printable ASCII");
    Scenario s; std::map<std::string, std::string> meta; std::map<std::string, SeedLeg> seen; std::map<std::pair<i64, std::string>, i64> markpx; std::map<std::pair<std::string, std::string>, std::pair<std::string, int>> legdef; i64 n = 0;
    std::set<std::string> seen_plugin; std::set<std::pair<std::string, std::string>> seen_cfg;
    for (auto& line : split(text, '\n')) {
      ++n; if (line.empty() || line[0] == '#') continue;
      auto p = split(line, '\t'); const std::string k = p[0]; const std::string w = "line " + std::to_string(n); auto need = [&](std::size_t c) { if (p.size() < c) throw ScenarioError(w + ": too few fields for " + k); };
      if (k == "META") { need(2); need_key(p[1], w); if (meta.count(p[1])) throw ScenarioError(w + ": META repeated"); meta[p[1]] = p.size() > 2 ? p[2] : ""; }
      else if (k == "INST") { need(3); check_instrument_id(p[1]); if (s.instruments.count(p[1])) throw ScenarioError(w + ": instrument repeated"); s.instruments[p[1]] = parse_int(p[2], w, 1, kMaxLot); }
      else if (k == "RISK") { need(3); if (s.risk.count(p[1])) throw ScenarioError(w + ": RISK repeated"); s.risk[p[1]] = parse_int(p[2], w, 0, 1000000000000LL); }
      else if (k == "PLUGIN") {
        need(4); need_name(p[1], w); if (!is_semver(p[2])) throw ScenarioError(w + ": invalid version"); if (seen_plugin.count(p[1])) throw ScenarioError(w + ": plugin listed twice");
        if (p[3] != "0" && p[3] != "1") throw ScenarioError(w + ": enabled flag must be 0 or 1");
        seen_plugin.insert(p[1]); s.plugins.emplace_back(p[1], p[2], p[3] == "1");
      }
      else if (k == "CONFIG") {
        need(4); need_name(p[1], w); need_key(p[2], w); if (!all_of_set(p[3], "_.*:-", true, true, true, 0, 64)) throw ScenarioError(w + ": invalid value");
        if (!seen_cfg.insert({p[1], p[2]}).second) throw ScenarioError(w + ": CONFIG repeated");
        s.configs[p[1]][p[2]] = p[3];
      }
      else if (k == "LEG") {
        need(9); need_id(p[1], w); need_id(p[2], w); need_id(p[3], w);
        SeedLeg d{p[1], p[2], p[3], p[4], (int)parse_int(p[5], w, -1, 1), parse_int(p[6], w, 1, kMaxQty), parse_int(p[7], w, 5, kMaxPx), parse_int(p[8], w, 0, kMaxT)};
        if (d.fill_id.size() > 2 && d.fill_id[0] == 'P' && d.fill_id[1] == 'C' && all_of_set(d.fill_id.substr(2), "", false, false, true, 1, 64)) throw ScenarioError(w + ": fill ids PC<digits> are reserved for the engine");
        auto it = seen.find(d.fill_id); if (it != seen.end()) { if (!(it->second == d)) throw ScenarioError(w + ": fill_id " + d.fill_id + " repeated with different content"); s.duplicates.push_back(d); continue; }
        seen[d.fill_id] = d; s.seeds.push_back(d);
      }
      else if (k == "MARK") { need(4); i64 ts = parse_int(p[1], w, 0, kMaxT), px = parse_int(p[3], w, 5, kMaxPx); auto key = std::make_pair(ts, p[2]); auto it = markpx.find(key); if (it != markpx.end() && it->second != px) throw ScenarioError(w + ": conflicting marks"); if (it == markpx.end()) { markpx[key] = px; s.marks.emplace_back(ts, p[2], px); } }
      else if (k == "TICK") { need(2); s.ticks.push_back(parse_int(p[1], w, 0, kMaxT)); }
      else if (k == "ACTION") {
        need(11); ScriptedAction a; a.ts = parse_int(p[1], w, 0, kMaxT); need_aid(p[2], w); a.action_id = p[2]; if (!p[3].empty()) need_name(p[3], w); a.plugin = p[3]; if (!p[4].empty() && !is_semver(p[4])) throw ScenarioError(w + ": invalid version"); a.version = p[4];
        if (!all_of_set(p[5], "_", true, false, false, 1, 20)) throw ScenarioError(w + ": invalid action type");
        a.type = p[5]; need_id(p[6], w); a.basket_id = p[6]; need_id(p[7], w); a.leg_id = p[7]; a.qty = parse_int(p[8], w, -kMaxActQty, kMaxActQty);
        if (!p[9].empty()) need_aid(p[9], w);
        a.parent_cut_id = p[9]; a.info_ts = p[10].empty() ? a.ts : parse_int(p[10], w, 0, kMaxT); a.group_id = p.size() > 11 ? p[11] : "";
        if (!a.group_id.empty()) need_id(a.group_id, w);
        s.actions.push_back(a);
      }
      else throw ScenarioError(w + ": unknown line type '" + k + "'");
    }
    if (!meta.count("evidence") || meta["evidence"] != kEvidence) throw ScenarioError("scenario must declare META evidence SYNTHETIC_TEST_ONLY (exactly once)");
    s.name = meta["name"]; s.description = meta["description"]; if (meta.count("method")) s.method = meta["method"]; if (s.method != "FIFO" && s.method != "LIFO" && s.method != "AVG") throw ScenarioError("bad method");
    for (auto& kv : s.configs) if (!seen_plugin.count(kv.first)) throw ScenarioError("CONFIG names plugin '" + kv.first + "' that has no PLUGIN line");
    parse_risk(s.risk);
    for (const auto* list : {&s.seeds, &s.duplicates}) for (auto& d : *list) {
      auto it = s.instruments.find(d.instrument_id); if (it == s.instruments.end()) throw ScenarioError("seed " + d.fill_id + ": undeclared instrument");
      if ((d.side != 1 && d.side != -1) || d.qty % it->second != 0 || d.price % 5 != 0) throw ScenarioError("seed " + d.fill_id + ": invalid side/qty/price");
      auto key = std::make_pair(d.basket_id, d.leg_id); auto ld = legdef.find(key); if (ld == legdef.end()) legdef[key] = {d.instrument_id, d.side}; else if (ld->second != std::make_pair(d.instrument_id, d.side)) throw ScenarioError("leg seeds disagree on instrument or side");
    }
    for (auto& m : s.marks) { if (!s.instruments.count(std::get<1>(m)) || std::get<2>(m) % 5 != 0) throw ScenarioError("mark: undeclared instrument or price not a multiple of the tick"); }
    auto seedless = [](const SeedLeg& a, const SeedLeg& b) { return std::tie(a.ts, a.fill_id) < std::tie(b.ts, b.fill_id); };
    std::sort(s.seeds.begin(), s.seeds.end(), seedless); std::sort(s.duplicates.begin(), s.duplicates.end(), seedless); s.duplicate_seeds = (i64)s.duplicates.size();
    std::sort(s.marks.begin(), s.marks.end()); std::sort(s.ticks.begin(), s.ticks.end()); s.ticks.erase(std::unique(s.ticks.begin(), s.ticks.end()), s.ticks.end());
    std::sort(s.actions.begin(), s.actions.end(), [](const ScriptedAction& a, const ScriptedAction& b) {
      return std::tie(a.ts, a.action_id, a.plugin, a.version, a.type, a.basket_id, a.leg_id, a.qty, a.parent_cut_id, a.info_ts, a.group_id) < std::tie(b.ts, b.action_id, b.plugin, b.version, b.type, b.basket_id, b.leg_id, b.qty, b.parent_cut_id, b.info_ts, b.group_id); });
    for (auto& a : s.actions) if (!std::binary_search(s.ticks.begin(), s.ticks.end(), a.ts)) throw ScenarioError("ACTION " + a.action_id + " is not at a TICK time");
    return s;
  }
};
}  // namespace pc
