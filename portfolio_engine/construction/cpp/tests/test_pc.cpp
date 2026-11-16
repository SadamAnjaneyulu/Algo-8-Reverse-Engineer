// C++ tests of the portfolio-construction prototype. Expected values are hand-calculated; the same behaviour is compared with Python in tests/test_parity.py.
#include <iostream>
#include "pc/engine.hpp"
using namespace pc;
static int failures = 0, checks = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #c "\n"; } } while (0)
#define THROWS(stmt, T) do { ++checks; bool ok_ = false; try { stmt; } catch (const T&) { ok_ = true; } catch (...) {} if (!ok_) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": expected " #T "\n"; } } while (0)

static const i64 T0 = 1767584760;
static const char* SCE = "NIFTY|2026-01-08|CE|24000"; static const char* SPE = "NIFTY|2026-01-08|PE|24000"; static const char* WCE = "NIFTY|2026-01-08|CE|24800"; static const char* WPE = "NIFTY|2026-01-08|PE|23200";
static std::string L(const std::vector<std::string>& v) { std::string o; for (std::size_t i = 0; i < v.size(); ++i) { if (i) o += '\t'; o += v[i]; } return o + "\n"; }
static std::string T(i64 x) { return std::to_string(x); }
// base scenario: basket B1 = short CE/PE 195, long CE/PE wing 195 (lot 65); `body` adds PLUGIN/CONFIG/RISK/MARK/TICK/ACTION lines
static std::string scn(const std::string& body, const std::string& evidence = "SYNTHETIC_TEST_ONLY") {
  std::string s = "#PC_SCENARIO v1\n" + L({"META", "name", "t"}) + L({"META", "evidence", evidence});
  for (auto* i : {SCE, SPE, WCE, WPE}) s += L({"INST", i, "65"});
  s += L({"LEG", "f1", "B1", "SCE", SCE, "-1", "195", "10000", T(T0)}) + L({"LEG", "f2", "B1", "SPE", SPE, "-1", "195", "9000", T(T0)}) + L({"LEG", "f3", "B1", "WCE", WCE, "1", "195", "200", T(T0)}) + L({"LEG", "f4", "B1", "WPE", WPE, "1", "195", "250", T(T0)});
  return s + body;
}
static std::string plugins(bool cut = true, bool re = true, bool scr = true) { return L({"PLUGIN", "basket_cut", "1.0.0", cut ? "1" : "0"}) + L({"PLUGIN", "basket_reentry", "1.0.0", re ? "1" : "0"}) + L({"PLUGIN", "scripted_actions", "1.0.0", scr ? "1" : "0"}); }
static std::string cfg(const std::string& p, const std::string& k, const std::string& v) { return L({"CONFIG", p, k, v}); }
static std::string mark(i64 off, const char* i, i64 px) { return L({"MARK", T(T0 + off), i, T(px)}); }
static std::string tick(i64 off) { return L({"TICK", T(T0 + off)}); }
static std::string action(i64 off, const std::string& id, const std::string& type, const std::string& leg, i64 qty, const std::string& parent = "", i64 info_off = 0, const std::string& plugin = "") {
  return L({"ACTION", T(T0 + off), id, plugin, plugin.empty() ? "" : "1.0.0", type, "B1", leg, T(qty), parent, T(T0 + off + info_off), ""});
}
static std::map<std::string, std::string> run(const std::string& text, const Catalog& extra = {}) { Simulation s(Scenario::parse(text), extra); return s.files(); }
static std::vector<std::vector<std::string>> rows(const std::string& tsv) { std::vector<std::vector<std::string>> r; for (auto& l : split(tsv, '\n')) { if (l.empty() || l[0] == '#') continue; r.push_back(split(l, '\t')); } r.erase(r.begin()); return r; }
static std::string kv(const std::string& summary, const std::string& key) { for (auto& r : rows(summary)) if (r[0] == key) return r[1]; return "<missing>"; }
static const std::string CUTID = "basket_cut|" + T(T0 + 600) + "|B1|SCE|CUT";

static std::string example_body(const std::string& extra_re_cfg = "", const std::string& risk = "") {      // extra_re_cfg re-states settings: they override the example's own (a setting appears once per file)
  std::map<std::pair<std::string, std::string>, std::string> base = {{{"basket_cut", "policy"}, "MARK_ADVERSE_MOVE"}, {{"basket_cut", "trigger_bp"}, "2000"}, {{"basket_cut", "scope"}, "LEG"}, {{"basket_cut", "leg_side_filter"}, "SHORT"},
    {{"basket_cut", "option_type_filter"}, "CE"}, {{"basket_cut", "units"}, "65"}, {{"basket_reentry", "cooldown_s"}, "600"}, {{"basket_reentry", "price_condition"}, "WITHIN_BAND"}, {{"basket_reentry", "band_bp"}, "1500"}};
  for (auto& l : split(extra_re_cfg, '\n')) { if (l.empty()) continue; auto f = split(l, '\t'); base[{f[1], f[2]}] = f[3]; }
  std::string cfgs; for (auto& kv : base) cfgs += cfg(kv.first.first, kv.first.second, kv.second);
  return plugins() + cfgs + risk + mark(0, SCE, 10000) + mark(300, SCE, 11000) + mark(600, SCE, 12500) + mark(900, SCE, 12000) + mark(1200, SCE, 11000) + mark(1500, SCE, 10800)
         + mark(0, SPE, 9000) + mark(0, WCE, 200) + mark(0, WPE, 250) + tick(0) + tick(300) + tick(600) + tick(900) + tick(1200) + tick(1500);
}

struct Flatten : Plugin {            // a plugin that lives OUTSIDE the core headers: proposes cutting one named leg completely at a given time
  std::string name() const override { return "flatten_leg"; } std::string version() const override { return "1.0.0"; }
  std::vector<std::pair<std::string, Spec>> spec() const override { return {{"at_ts", ispec(0)}}; }
  void evaluate(const EvalContext& ctx, PluginResult& r) const override {
    if (ctx.ts < geti("at_ts")) return;
    for (auto& b : ctx.baskets) for (auto& l : b.legs) if (l.leg_id == "WPE" && l.current > 0) { r.actions.push_back({name() + "|" + T(ctx.ts), name(), version(), "CUT", "", b.basket_id, l.leg_id, l.current, "", ctx.ts, ctx.ts, "FLATTEN"}); r.status = "OK"; }
  }
};
struct Boom : Plugin { std::string name() const override { return "boom"; } std::string version() const override { return "1.0.0"; } void evaluate(const EvalContext&, PluginResult&) const override { throw std::runtime_error("bug"); } };
struct Greedy : Plugin {             // tries to look at the future
  std::string name() const override { return "greedy"; } std::string version() const override { return "1.0.0"; }
  void evaluate(const EvalContext& ctx, PluginResult&) const override { ctx.mark("x", ctx.ts + 1); }
};
struct V2 : Plugin { std::string name() const override { return "other"; } std::string version() const override { return "1.0.0"; } int api_version() const override { return 2; } void evaluate(const EvalContext&, PluginResult&) const override {} };

static void test_registry() {
  Registry r; r.add(std::make_shared<BasketCutPlugin>()); r.add(std::make_shared<BasketReentryPlugin>(), false);
  THROWS(r.add(std::make_shared<BasketCutPlugin>()), RegistryError);                  // duplicate name
  THROWS(r.add(std::make_shared<V2>()), RegistryError);                               // incompatible API version
  CHECK(r.list().size() == 2 && r.list()[0].name == "basket_cut" && r.list()[1].enabled == false);
  CHECK(r.enabled().size() == 1); r.enable("basket_reentry"); CHECK(r.enabled().size() == 2); r.disable("basket_cut"); CHECK(r.enabled().size() == 1 && r.enabled()[0]->name() == "basket_reentry");
  THROWS(r.get("nope"), RegistryError);
  const std::string h0 = r.get("basket_cut")->config_hash(); r.configure("basket_cut", {{"trigger_bp", "500"}}); CHECK(r.get("basket_cut")->config_hash() != h0 && r.get("basket_cut")->geti("trigger_bp") == 500);
  THROWS(r.configure("basket_cut", {{"trigger_bp", "-1"}}), ConfigError); CHECK(r.get("basket_cut")->geti("trigger_bp") == 500);   // a bad configuration leaves the old one in place
  THROWS(r.configure("basket_cut", {{"unknown_key", "1"}}), ConfigError); THROWS(r.configure("basket_cut", {{"policy", "MAGIC"}}), ConfigError);
  THROWS(r.require_version("basket_cut", "2.0.0"), RegistryError); r.require_version("basket_cut", "1.9.9");
  CHECK(fnv1a64("") == "cbf29ce484222325"); CHECK(fnv1a64("a") == "af63dc4c8601ec8c");                                           // published FNV-1a 64 test vectors
}
static void test_example_by_hand() {
  auto f = run(scn(example_body()));                                                          // short CE 195 @10000: +25% mark at t+600 triggers a 65-unit cut; cooldown ends at t+1200
  auto a = rows(f["actions.tsv"]); CHECK(a.size() == 2);
  CHECK(a[0][12] == "ACCEPTED" && a[0][9] == "65" && a[0][16] == "1" && a[0][17] == "12500" && a[0][1] == T(T0 + 600));      // buy 65 at the mark 12500
  CHECK(a[1][5] == "REENTRY" && a[1][12] == "ACCEPTED" && a[1][10] == CUTID && a[1][16] == "-1" && a[1][17] == "11000" && a[1][1] == T(T0 + 1200));
  auto s = rows(f["states.tsv"]); bool saw_cut = false, saw_re = false;
  for (auto& r : s) { if (r[2] == "PC000001" && r[5] == "SCE") { saw_cut = true; CHECK(r[9] == "195" && r[10] == "130" && r[11] == "PARTIALLY_CUT" && r[12] == "-130" && r[13] == "715" && r[14] == "325"); }
                      if (r[2] == "PC000002" && r[5] == "SCE") { saw_re = true; CHECK(r[9] == "130" && r[10] == "195" && r[11] == "ACTIVE" && r[12] == "-195" && r[13] == "780" && r[14] == "390"); } }
  CHECK(saw_cut && saw_re);
  CHECK(kv(f["summary.tsv"], "final_realized_pnl_paise") == "-162500");                       // closing 65 short units bought at 12500 against entry 10000: (10000-12500)*65
  auto d = rows(f["decisions.tsv"]); int cooldown = 0; for (auto& r : d) cooldown += r[2] == "basket_reentry" && r[7] == "COOLDOWN_ACTIVE"; CHECK(cooldown == 2);   // t+600 and t+900
  auto lin = rows(f["lineage.tsv"]); CHECK(lin.back()[1] == "REENTRY" && lin.back()[7] == CUTID && lin.back()[8] == "f1");   // re-entry -> its cut -> the original seed fill
}
static void test_cut_variants() {
  auto fr = [&](const std::string& extra) { return plugins() + cfg("basket_cut", "policy", "SCHEDULED") + cfg("basket_cut", "cut_at_ts", T(T0 + 300)) + extra + tick(0) + tick(300); };
  { auto f = run(scn(fr(cfg("basket_cut", "scope", "BASKET") + cfg("basket_cut", "qty_mode", "FRACTION_BP") + cfg("basket_cut", "fraction_bp", "3333")))); auto a = rows(f["actions.tsv"]);       // 3 lots * 3333/10000 = 0.9999 -> rounds to 1 lot = 65
    CHECK(a.size() == 4); for (auto& r : a) CHECK(r[12] == "ACCEPTED" && r[9] == "65" && r[6] == "basket_cut|" + T(T0 + 300) + "|B1"); CHECK(kv(f["summary.tsv"], "final_gross_units") == "520"); }
  { auto f = run(scn(fr(cfg("basket_cut", "scope", "BASKET") + cfg("basket_cut", "qty_mode", "FRACTION_BP") + cfg("basket_cut", "fraction_bp", "10000")))); CHECK(kv(f["summary.tsv"], "final_gross_units") == "0"); auto s = rows(f["states.tsv"]); CHECK(s.back()[11] == "FULLY_CUT"); }
  { auto f = run(scn(fr(cfg("basket_cut", "leg_side_filter", "SHORT") + cfg("basket_cut", "option_type_filter", "PE") + cfg("basket_cut", "units", "130")))); auto a = rows(f["actions.tsv"]); CHECK(a.size() == 1 && a[0][8] == "SPE" && a[0][9] == "130" && a[0][16] == "1"); CHECK(kv(f["summary.tsv"], "final_short_units") == "260"); }  // individual, side-aware leg cut
  { auto f = run(scn(fr(cfg("basket_cut", "scope", "BASKET") + cfg("basket_cut", "leg_side_filter", "LONG") + cfg("basket_cut", "units", "65")))); auto a = rows(f["actions.tsv"]); CHECK(a.size() == 2 && a[0][8] == "WCE" && a[1][8] == "WPE" && a[0][16] == "-1"); CHECK(kv(f["summary.tsv"], "final_short_units") == "390"); }      // cutting the long wings sells them
  { auto f = run(scn(fr(cfg("basket_cut", "scope", "BASKET") + cfg("basket_cut", "units", "260") + cfg("basket_cut", "clamp_to_available", "1")))); auto a = rows(f["actions.tsv"]); CHECK(a.size() == 4 && a[0][9] == "195" && a[0][12] == "ACCEPTED"); }  // clamp
  { auto f = run(scn(fr(cfg("basket_cut", "scope", "BASKET") + cfg("basket_cut", "units", "260")))); auto a = rows(f["actions.tsv"]);                                          // no clamp: whole group rejected, nothing executed
    CHECK(a.size() == 4 && a[0][13] == "INSUFFICIENT_INVENTORY" && a[1][13] == "GROUP_REJECTED" && a[3][13] == "GROUP_REJECTED"); CHECK(kv(f["summary.tsv"], "final_gross_units") == "780" && kv(f["summary.tsv"], "fills_total") == "4"); }
}
static void test_risk() {
  auto one = [&](const std::string& extra_actions, const std::string& risk = "", const std::string& re = "") { return run(scn(plugins(false, false, true) + risk + re + mark(0, SCE, 10000) + tick(0) + extra_actions)); };
  auto reason = [&](std::map<std::string, std::string>& f, std::size_t i) { auto a = rows(f["actions.tsv"]); return a.at(i)[13]; };
  { auto f = one(action(0, "a1", "CUT", "SCE", 260)); CHECK(reason(f, 0) == "INSUFFICIENT_INVENTORY"); }
  { auto f = one(action(0, "a1", "CUT", "SCE", 30)); CHECK(reason(f, 0) == "INVALID_QUANTITY"); }
  { auto f = one(action(0, "a1", "CUT", "NOPE", 65)); CHECK(reason(f, 0) == "MISSING_OR_INVALID_LEG"); }
  { auto f = one(action(0, "a1", "SWAP", "SCE", 65)); CHECK(reason(f, 0) == "INVALID_ACTION_TYPE"); }
  { auto f = one(action(0, "a1", "CUT", "SCE", 65) + action(0, "a1", "CUT", "SCE", 65)); auto a = rows(f["actions.tsv"]); CHECK(a[0][12] == "ACCEPTED" && a[1][13] == "DUPLICATE_ACTION_ID"); }
  { auto f = one(action(0, "a1", "CUT", "SCE", 130), L({"RISK", "max_cut_qty_per_action", "65"})); CHECK(reason(f, 0) == "QUANTITY_LIMIT_EXCEEDED"); }
  { auto f = one(action(0, "a1", "REENTRY", "SCE", 65, "nonexistent")); CHECK(reason(f, 0) == "INVALID_CUT_LINEAGE"); }
  { auto f = one(action(0, "a1", "CUT", "SCE", 65, "", 1)); CHECK(reason(f, 0) == "LOOKAHEAD_VIOLATION"); }                                        // decided with data stamped after the action time
  { auto f = one(action(0, "a1", "CUT", "SCE", 65, "", 0, "basket_cut")); CHECK(reason(f, 0) == "PLUGIN_MISMATCH"); }                                 // scripted plugin pretends to be basket_cut
  { auto f = one(action(0, "c1", "CUT", "SCE", 65) + action(0, "r1", "REENTRY", "SCE", 130, "c1")); CHECK(reason(f, 1) == "REENTRY_LIMIT_EXCEEDED"); }  // more than was cut
  { auto f = one(action(0, "c1", "CUT", "SCE", 65) + action(0, "r1", "REENTRY", "SCE", 65, "c1"), L({"RISK", "reentry_min_cooldown_s", "100"})); CHECK(reason(f, 1) == "COOLDOWN_NOT_ELAPSED"); }   // same timestamp as the cut
  { auto f = one(action(0, "c1", "CUT", "SCE", 65) + action(0, "r1", "REENTRY", "SCE", 65, "c1"), L({"RISK", "max_short_units", "325"})); CHECK(reason(f, 1) == "EXPOSURE_LIMIT_EXCEEDED"); }     // 325 -> 390 > 325
  { auto f = one(action(0, "c1", "CUT", "SCE", 65), L({"RISK", "max_short_units", "100"})); CHECK(reason(f, 0) == "OK"); }                         // de-risking is allowed even when already above a limit
  { auto f = one(action(0, "c1", "CUT", "SCE", 195) + action(0, "c2", "CUT", "SPE", 195) + action(0, "c3", "CUT", "WCE", 195) + action(0, "c4", "CUT", "WPE", 195) + action(0, "c5", "CUT", "WPE", 65)); CHECK(reason(f, 4) == "INVALID_BASKET_STATE"); }   // basket already fully cut
  // many small re-entries cannot add up past the unsplit limit
  { std::string acts = action(0, "c1", "CUT", "SCE", 130); for (int k = 0; k < 2; ++k) acts += action(0, "r" + std::to_string(k), "REENTRY", "SCE", 65, "c1");
    acts += action(0, "r9", "REENTRY", "SCE", 65, "c1"); auto f = one(acts, L({"RISK", "max_short_units", "390"})); auto a = rows(f["actions.tsv"]); CHECK(a[1][12] == "ACCEPTED" && a[2][12] == "ACCEPTED" && a[3][13] == "REENTRY_LIMIT_EXCEEDED"); }
}
static void test_boundaries_and_groups() {
  auto trig = [&](i64 px) { auto f = run(scn(plugins(true, false, false) + cfg("basket_cut", "trigger_bp", "2000") + cfg("basket_cut", "leg_side_filter", "SHORT") + cfg("basket_cut", "option_type_filter", "CE") + mark(0, SCE, 10000) + mark(300, SCE, px) + tick(0) + tick(300))); return rows(f["actions.tsv"]).size(); };
  CHECK(trig(11995) == 0 && trig(12000) == 1 && trig(12005) == 1);                                             // inclusive at +20 %
  auto re = [&](i64 px) { std::string t = scn(example_body()); std::string from = "MARK\t" + T(T0 + 1200) + "\t" + SCE + "\t11000\n", to = "MARK\t" + T(T0 + 1200) + "\t" + SCE + "\t" + T(px) + "\n"; t.replace(t.find(from), from.size(), to);
    std::size_t n = 0; for (auto& r : rows(run(t)["actions.tsv"])) n += r[5] == "REENTRY" && r[1] == T(T0 + 1200); return n; };
  CHECK(re(10620) == 0 && re(10625) == 1 && re(14375) == 1 && re(14380) == 0);                                 // band = 1500 bp of 12500 = 1875 paise, inclusive
  auto ga = [&](const std::string& id, const std::string& leg, i64 q) { return L({"ACTION", T(T0), id, "", "", "CUT", "B1", leg, T(q), "", T(T0), "grp"}); };
  const std::string pre = plugins(false, false, true) + mark(0, SCE, 10000) + tick(0);
  { auto f = run(scn(pre + ga("g1", "SCE", 130) + ga("g2", "SCE", 130))); auto a = rows(f["actions.tsv"]); CHECK(a[0][13] == "GROUP_REJECTED" && a[1][13] == "INSUFFICIENT_INVENTORY" && kv(f["summary.tsv"], "fills_total") == "4"); }
  { auto f = run(scn(pre + ga("g1", "SCE", 65) + ga("g2", "SPE", 65))); auto a = rows(f["actions.tsv"]); CHECK(a[0][12] == "ACCEPTED" && a[1][12] == "ACCEPTED" && kv(f["summary.tsv"], "fills_total") == "6"); }
  { auto f = run(scn(pre + action(0, "c1", "CUT", "SCE", 65) + action(0, "c2", "CUT", "SCE", 65) + action(0, "r1", "REENTRY", "SCE", 130, "c1"))); CHECK(rows(f["actions.tsv"]).back()[13] == "REENTRY_LIMIT_EXCEEDED"); }
}
static void test_lineage_and_reconciliation() {
  const std::string pre = plugins(false, false, true) + mark(0, SCE, 10000) + tick(0);
  { auto f = run(scn(pre + action(0, "c", "CUT", "SPE", 65) + action(0, "r", "REENTRY", "SCE", 65, "c"))); CHECK(rows(f["actions.tsv"]).back()[13] == "INVALID_CUT_LINEAGE"); }          // cut of another leg
  { auto f = run(scn(pre + action(0, "c", "CUT", "SCE", 260) + action(0, "r", "REENTRY", "SCE", 65, "c"))); CHECK(rows(f["actions.tsv"]).back()[13] == "INVALID_CUT_LINEAGE"); }      // the cited cut was rejected
  { auto f = run(scn(pre + action(0, "r", "REENTRY", "SCE", 65, ""))); CHECK(rows(f["actions.tsv"]).back()[13] == "INVALID_CUT_LINEAGE"); }
  { auto f = run(scn(pre + action(0, "c", "CUT", "SCE", 65) + L({"ACTION", T(T0), "r", "", "", "REENTRY", "B2", "SCE", "65", "c", T(T0), ""}))); CHECK(rows(f["actions.tsv"]).back()[13] == "INVALID_BASKET_STATE"); }
  { auto f = run(scn(plugins() + tick(0))); auto l = rows(f["lineage.tsv"]); CHECK(l.size() == 4 && l[0][1] == "SEED"); }
  Simulation sim(Scenario::parse(scn(plugins() + tick(0)))); sim.run(); sim.reconcile();
  pe::Fill rogue; rogue.fill_id = "rogue"; rogue.source_row = 99; rogue.parent_id = "rogue"; rogue.module_tag = "x"; rogue.instrument_id = SCE; rogue.ts = T0 + 5; rogue.side = 1; rogue.qty = 65; rogue.price = 10000; rogue.requested = 65; rogue.status = "Filled"; rogue.mode = "SYNTHETIC_TEST";
  sim.ledger->apply_fill(rogue); THROWS(sim.reconcile(), EngineInvariantError);                              // a fill that bypasses the engine is detected
}
struct BadDetail : Plugin {
  std::string name() const override { return "bad"; } std::string version() const override { return "1.0.0"; } int mode = 0;
  void evaluate(const EvalContext& ctx, PluginResult& r) const override {
    Decision d{ctx.ts, name(), version(), "B1", "SCE", "NOT_PROPOSED", "X", "ok", ctx.ts};
    if (mode == 1) d.detail = "a\n\tb";
    if (mode == 2) d.info_ts = ctx.ts + 1;
    if (mode == 3) d.plugin = "basket_cut";
    if (mode == 4) d.ts = ctx.ts - 1;
    if (mode == 5) d.detail = "caf\xc3\xa9";
    r.decisions.push_back(d);
    if (mode == 6) r.status = "MAYBE";
  }
};
template <int M> struct BadM : BadDetail { BadM() { mode = M; } };
static void test_plugin_isolation_and_output_validation() {
  const std::string pre = scn(L({"PLUGIN", "bad", "1.0.0", "1"}) + mark(0, SCE, 10000) + tick(0));
  auto one = [&](Catalog cat) { auto f = run(pre, cat); return std::make_pair(rows(f["decisions.tsv"]), kv(f["summary.tsv"], "plugin_errors")); };
  { Catalog c; c["bad"] = [] { return std::make_shared<BadM<0>>(); }; auto r = one(c); CHECK(r.second == "0" && r.first.size() == 1 && r.first[0][7] == "X"); }               // a well-formed result is kept
  { Catalog c; c["bad"] = [] { return std::make_shared<BadM<1>>(); }; auto r = one(c); CHECK(r.second == "1" && r.first[0][7] == "PLUGIN_ERROR" && r.first[0][8] == "invalid plugin output"); }
  { Catalog c; c["bad"] = [] { return std::make_shared<BadM<2>>(); }; CHECK(one(c).second == "1"); }
  { Catalog c; c["bad"] = [] { return std::make_shared<BadM<3>>(); }; CHECK(one(c).second == "1"); }
  { Catalog c; c["bad"] = [] { return std::make_shared<BadM<4>>(); }; CHECK(one(c).second == "1"); }
  { Catalog c; c["bad"] = [] { return std::make_shared<BadM<5>>(); }; CHECK(one(c).second == "1"); }
  { Catalog c; c["bad"] = [] { return std::make_shared<BadM<6>>(); }; CHECK(one(c).second == "1"); }
  MarkStore m; m.add(100, "x", 5); m.add(101, "x", 7); m.finish(); auto v = m.truncated(100); CHECK(!v->at("x", 101).has_value() || v->at("x", 101)->first == 5); CHECK(v->at("x", 1000000)->first == 5);       // the context copy cannot reveal later marks
}
static void test_boundaries_filters_and_info_ts() {
  std::string longleg = scn(""); { std::string from = L({"LEG", "f3", "B1", "WCE", WCE, "1", "195", "200", T(T0)}), to = L({"LEG", "f3", "B1", "WCE", WCE, "1", "195", "10000", T(T0)}); longleg.replace(longleg.find(from), from.size(), to); }
  auto n = [&](i64 px) { auto f = run(longleg + plugins(true, false, false) + cfg("basket_cut", "trigger_bp", "2000") + cfg("basket_cut", "leg_side_filter", "LONG") + cfg("basket_cut", "option_type_filter", "CE") + mark(0, WCE, 10000) + mark(300, WCE, px) + tick(0) + tick(300)); return rows(f["actions.tsv"]).size(); };
  CHECK(n(8005) == 0 && n(8000) == 1 && n(7995) == 1);                                                       // long entry 10000: inclusive at mark <= 8000
  auto re = [&](i64 wait) { std::size_t k = 0; for (auto& r : rows(run(scn(example_body(cfg("basket_reentry", "cooldown_s", "300") + cfg("basket_reentry", "price_condition", "NONE") + cfg("basket_reentry", "max_wait_s", T(wait)))))["actions.tsv"])) k += r[5] == "REENTRY"; return k; };
  CHECK(re(299) == 0 && re(300) == 1 && re(600) == 1);                                                       // exactly cut + max_wait is inside the window
  const std::string two = scn("") + L({"LEG", "g1", "B2", "SCE", SCE, "-1", "130", "10000", T(T0)});
  auto filt = [&](const std::string& f) { auto r = rows(run(two + plugins() + cfg("basket_cut", "policy", "SCHEDULED") + cfg("basket_cut", "basket_filter", f) + cfg("basket_cut", "leg_side_filter", "SHORT") + cfg("basket_cut", "option_type_filter", "CE") + cfg("basket_cut", "units", "65") + cfg("basket_reentry", "basket_filter", f) + cfg("basket_reentry", "cooldown_s", "0") + mark(0, SCE, 10000) + tick(0) + tick(300))["actions.tsv"]);
    std::string s; for (auto& x : r) s += x[7] + ":" + x[5] + " "; return s; };
  CHECK(filt("B2") == "B2:CUT B2:REENTRY " && filt("B1") == "B1:CUT B1:REENTRY " && filt("*") == "B1:CUT B2:CUT B1:REENTRY B2:REENTRY ");
  { auto f = run(scn(plugins(true, false, false) + cfg("basket_cut", "scope", "BASKET") + cfg("basket_cut", "units", "65") + mark(0, SPE, 9000) + mark(0, WCE, 200) + mark(0, WPE, 250) + mark(100, SCE, 12500) + mark(200, SPE, 11250) + mark(0, SCE, 10000) + tick(0) + tick(300)));
    std::map<std::string, std::string> info; for (auto& r : rows(f["actions.tsv"])) info[r[8]] = r[11]; CHECK(info["SCE"] == T(T0 + 100) && info["SPE"] == T(T0 + 200) && info["WCE"] == T(T0 + 200) && info["WPE"] == T(T0 + 200)); }
  { auto f = run(scn(plugins(true, false, false) + cfg("basket_cut", "trigger_bp", "2000") + mark(0, SCE, 10000) + mark(0, SPE, 9000) + tick(300))); for (auto& r : rows(f["decisions.tsv"])) if (r[7] == "NO_TRIGGER") CHECK(r[10] == T(T0)); }
}
static void test_lookahead_and_errors() {
  EvalContext c; c.ts = 100; MarkStore m; m.add(100, "x", 5); m.add(101, "x", 7); m.finish(); c.marks = m.truncated(100);
  CHECK(c.mark("x")->first == 5); THROWS(c.mark("x", 101), LookAheadError); CHECK(!c.mark("y").has_value());
  const std::string base = example_body(); const std::string alt = base + mark(1260, SCE, 5) + mark(1800, SCE, 99995) + tick(1800);      // future marks differ
  auto f1 = run(scn(base)); auto f2 = run(scn(alt)); auto d1 = rows(f1["decisions.tsv"]), d2 = rows(f2["decisions.tsv"]);
  for (std::size_t i = 0; i < d1.size(); ++i) { if (std::stoll(d1[i][1]) > T0 + 1200) break; CHECK(d1[i] == d2[i]); }                                  // decisions up to t+1200 do not see later marks
  Catalog cat; cat["greedy"] = [] { return std::make_shared<Greedy>(); }; cat["boom"] = [] { return std::make_shared<Boom>(); };
  auto f = run(scn(L({"PLUGIN", "greedy", "1.0.0", "1"}) + L({"PLUGIN", "boom", "1.0.0", "1"}) + tick(0) + tick(1)), cat);
  CHECK(kv(f["summary.tsv"], "plugin_errors") == "4"); auto d = rows(f["decisions.tsv"]); CHECK(d.size() == 4 && d[0][7] == "PLUGIN_ERROR");                  // both plugins fail closed at both ticks; the run continues
}
static void test_new_plugin_without_core_change() {
  Catalog cat; cat["flatten_leg"] = [] { return std::make_shared<Flatten>(); };
  auto f = run(scn(L({"PLUGIN", "flatten_leg", "1.0.0", "1"}) + cfg("flatten_leg", "at_ts", T(T0 + 100)) + mark(0, WPE, 250) + tick(0) + tick(200)), cat);
  auto a = rows(f["actions.tsv"]); CHECK(a.size() == 1 && a[0][3] == "flatten_leg" && a[0][12] == "ACCEPTED" && a[0][9] == "195" && a[0][16] == "-1");
  THROWS(run(scn(L({"PLUGIN", "flatten_leg", "1.0.0", "1"}) + tick(0))), ConfigError);                                                         // unknown without the drop-in
  THROWS(run(scn(L({"PLUGIN", "basket_cut", "2.0.0", "1"}) + tick(0))), RegistryError);                                                         // incompatible required version
}
static void test_scenario_rules() {
  THROWS(run(scn(plugins() + tick(0), "REAL_DATA")), ScenarioError);                                                                            // every scenario must be marked synthetic
  THROWS(Scenario::parse(scn(L({"LEG", "f1", "B1", "SCE", SCE, "-1", "195", "10005", T(T0)}))), ScenarioError);                                 // same fill id, different content
  { std::string dup = L({"LEG", "f1", "B1", "SCE", SCE, "-1", "195", "10000", T(T0)}); auto sc = Scenario::parse(scn(dup + plugins() + tick(0))); CHECK(sc.duplicate_seeds == 1 && sc.seeds.size() == 4); }  // identical repeat: ignored and counted
  THROWS(Scenario::parse(scn(mark(0, SCE, 10000) + mark(0, SCE, 10005))), ScenarioError);                                                       // conflicting duplicate marks
  THROWS(Scenario::parse(scn(L({"LEG", "f9", "B1", "SCE", SCE, "-1", "70", "10000", T(T0)}))), ScenarioError);                                  // not a lot multiple
}
int main() {
  test_registry(); test_example_by_hand(); test_cut_variants(); test_risk(); test_boundaries_and_groups(); test_lineage_and_reconciliation(); test_plugin_isolation_and_output_validation(); test_boundaries_filters_and_info_ts(); test_lookahead_and_errors(); test_new_plugin_without_core_change(); test_scenario_rules();
  std::cout << (failures ? "FAILED " : "") << (checks - failures) << "/" << checks << " plugin checks passed\n"; return failures ? 1 : 0;
}
