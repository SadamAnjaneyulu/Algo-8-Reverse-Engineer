// Deterministic replay + canonical state dump (docs/SCHEMAS.md). Same ordering, warnings, snapshots and formatting as python/pe/replay.py.
#pragma once
#include <cstdio>
#include <sstream>
#include "pe/lineage.hpp"
namespace pe {
struct Snap { i64 seq, ts; std::string date; i64 open_instruments, sCE, sPE, lCE, lPE, gross, net; i64 realized_i; double realized_d; i64 cash; };
struct ReplayResult { std::map<std::string, std::string> lineage_files; std::string dump; std::string roles; std::vector<std::string> checks; std::map<std::string, i64> warnings; };

inline int tie_key(const std::string& tie, int side) { if (tie == "src") return 0; if (tie == "sells_first") return side < 0 ? 0 : 1; if (tie == "buys_first") return side > 0 ? 0 : 1; throw EngineError("bad tie order " + tie); }

inline ReplayResult replay(const std::vector<Fill>& fills, const std::map<std::string, Instrument>& ins, const std::string& mode, const std::string& method_s, const std::string& tie, i64 snapshot_interval, bool strict, bool want_lineage = false) {
  bool okm = false;
  for (auto& m : kModes) okm = okm || (m == mode);
  if (!okm) throw EngineError("unknown mode " + mode);
  const Method method = parse_method(method_s); tie_key(tie, 1);
  for (auto& f : fills) if (f.mode != mode) throw ModeContaminationError("fill " + f.fill_id + " has mode " + f.mode + ", run mode is " + mode);
  std::map<std::string, i64> warn; for (auto& k : kWarnCodes) warn[k] = 0;
  for (std::size_t i = 1; i < fills.size(); ++i) if (fills[i].ts < fills[i - 1].ts) warn["INPUT_NOT_TIME_ORDERED"]++;
  std::vector<const Fill*> ord; for (auto& f : fills) ord.push_back(&f);
  std::stable_sort(ord.begin(), ord.end(), [&](const Fill* a, const Fill* b) {
    if (a->ts != b->ts) return a->ts < b->ts;
    const int ta = tie_key(tie, a->side), tb = tie_key(tie, b->side);
    if (ta != tb) return ta < tb;
    if (a->source_row != b->source_row) return a->source_row < b->source_row;
    return a->fill_id < b->fill_id; });
  std::vector<const Fill*> live; for (auto* f : ord) if (!f->duplicate) live.push_back(f);
  warn["DUPLICATE_FILL_IGNORED"] = (i64)(ord.size() - live.size());
  { std::map<std::pair<std::string, i64>, std::set<int>> g; for (auto* f : live) g[{f->instrument_id, f->ts}].insert(f->side); for (auto& kv : g) if (kv.second.size() == 2) warn["TIE_GROUP_MIXED_SIDE"]++; }
  for (auto* f : live) if (f->status == "PartiallyFilled") warn["PARTIAL_FILL_ROWS"]++;
  warn["MISSING_MARKS"] = 1;
  LineageRecorder rec(method_s); PortfolioState state(method, ins, want_lineage ? &rec : nullptr); std::map<std::string, i64> signed_sum; struct P { i64 fills = 0, units = 0, requested = 0; std::set<i64> days; }; std::map<std::string, P> parents; std::vector<Snap> snaps; std::vector<Role> roles;
  auto snap = [&](i64 seq, i64 ts) {
    const Agg& a = state.agg; const i64 sh = a.short_CE + a.short_PE, lg = a.long_CE + a.long_PE;
    snaps.push_back({seq, ts, day_iso(ist_day(ts)), a.open_instruments, a.short_CE, a.short_PE, a.long_CE, a.long_PE, sh + lg, lg - sh, state.realized_total_i(), state.realized_total_d(), state.cash}); };
  const std::size_t n = live.size();
  for (std::size_t k = 0; k < n; ++k) {
    const Fill& f = *live[k]; roles.push_back(state.apply_fill(f)); signed_sum[f.instrument_id] += f.side * f.qty;
    auto it = parents.find(f.parent_id); if (it == parents.end()) { it = parents.emplace(f.parent_id, P{}).first; it->second.requested = f.requested; }
    it->second.fills++; it->second.units += f.qty; it->second.days.insert(ist_day(f.ts));
    if (strict) check_state(state, &signed_sum);
    const bool last = k == n - 1; const bool day_end = last || ist_day(live[k + 1]->ts) != ist_day(f.ts);
    if (day_end || (snapshot_interval && state.applied % snapshot_interval == 0)) snap(state.applied, f.ts);
  }
  ReplayResult res; res.checks = check_state(state, &signed_sum); res.warnings = warn;
  const i64 last_day = n ? ist_day(live.back()->ts) : 0; std::map<std::string, std::string> stat; i64 exp_units = 0, open_units = 0, exp_instr = 0;
  for (auto& kv : state.s) {
    const i64 inv = kv.second.inv;
    if (inv == 0) stat[kv.first] = "CLOSED"; else if (ins.at(kv.first).expiry_day <= last_day) { stat[kv.first] = "EXPIRED_UNCLOSED"; exp_units += inv; exp_instr++; } else { stat[kv.first] = "OPEN_AT_END_OF_DATA"; open_units += inv; } }
  warn["EXPIRED_UNCLOSED_INSTRUMENTS"] = exp_instr;
  for (auto& kv : parents) { warn["UNFILLED_REMAINDER_ORDERS"] += kv.second.units < kv.second.requested; warn["OVERFILLED_ORDERS"] += kv.second.units > kv.second.requested; warn["PARENT_SPANS_DATES"] += kv.second.days.size() > 1; }
  const bool avg = state.avg; std::ostringstream o; auto F = [&](i64 i, double d) { return avg ? fmt6(d) : std::to_string(i); };
  o << "#PE_STATE_DUMP v1\n"; o << "META\tmethod\t" << method_s << "\nMETA\ttie_order\t" << tie << "\nMETA\texecution_mode\t" << mode << "\nMETA\tevents_read\t" << fills.size() << "\nMETA\tevents_applied\t" << state.applied
    << "\nMETA\tduplicates_ignored\t" << warn["DUPLICATE_FILL_IGNORED"] << "\nMETA\tfirst_ts\t" << (n ? live.front()->ts : 0) << "\nMETA\tlast_ts\t" << (n ? live.back()->ts : 0) << "\nMETA\tlast_date\t" << (n ? day_iso(last_day) : "") << "\n";
  o << "TOTAL\topened_units\t" << state.opened << "\nTOTAL\tclosed_units\t" << state.closed << "\nTOTAL\tremaining_units\t" << state.opened - state.closed << "\nTOTAL\treversal_fills\t" << state.reversal_fills << "\nTOTAL\treversal_units_reopened\t" << state.reversal_units_reopened
    << "\nTOTAL\trealized_pnl_paise\t" << F(state.realized_total_i(), state.realized_total_d()) << "\nTOTAL\tcash_flow_paise\t" << state.cash << "\nTOTAL\tremaining_book_value_paise\t" << F(state.book_total_i(), state.book_total_d())
    << "\nTOTAL\tremaining_expired_unclosed_units\t" << exp_units << "\nTOTAL\tremaining_open_at_end_units\t" << open_units << "\n";
  for (auto& kv : state.s) { const InstState& x = kv.second; o << "INSTR\t" << kv.first << "\t" << state.signed_inventory(kv.first) << "\t" << x.opened << "\t" << x.closed << "\t" << F(x.realized_i, x.realized_d) << "\t" << F(state.book_value_i(x), state.book_value_d(x)) << "\t" << stat[kv.first] << "\n"; }
  for (auto& kv : state.episodes) { const Episode& e = kv.second; o << "EPISODE\t" << kv.first << "\t" << e.dir << "\t" << e.opened << "\t" << e.closed << "\t" << e.opened - e.closed << "\t" << F(e.realized_i, e.realized_d) << "\t" << e.ended_by << "\t" << e.n_open << "\t" << e.n_close << "\n"; }
  for (auto& s_ : snaps) o << "SNAP\t" << s_.seq << "\t" << s_.ts << "\t" << s_.date << "\t" << s_.open_instruments << "\t" << s_.sCE << "\t" << s_.sPE << "\t" << s_.lCE << "\t" << s_.lPE << "\t" << s_.gross << "\t" << s_.net << "\t" << F(s_.realized_i, s_.realized_d) << "\t" << s_.cash << "\tNA\n";
  for (auto& kv : parents) { const P& p = kv.second; o << "PARENT\t" << kv.first << "\t" << p.fills << "\t" << p.units << "\t" << p.requested << "\t" << (p.units == p.requested ? "COMPLETE" : (p.units < p.requested ? "UNFILLED_REMAINDER" : "OVERFILLED")) << "\n"; }
  for (auto& k : kWarnCodes) o << "WARN\t" << k << "\t" << warn[k] << "\n";
  res.dump = o.str(); res.warnings = warn;
  std::sort(roles.begin(), roles.end(), [](const Role& a, const Role& b) { return a.fill_id < b.fill_id; }); std::ostringstream r; r << "fill_id\tinstrument_id\tclose_qty\topen_qty\tinventory_after\tis_reversal\tepisode_closed\tepisode_opened\n";
  for (auto& x : roles) r << x.fill_id << "\t" << x.instrument_id << "\t" << x.close_qty << "\t" << x.open_qty << "\t" << x.inventory_after << "\t" << (int)x.reversal << "\t" << (x.ep_closed.empty() ? "-" : x.ep_closed) << "\t" << (x.ep_opened.empty() ? "-" : x.ep_opened) << "\n";
  res.roles = r.str();
  if (want_lineage) { res.lineage_files["observed_allocations.tsv"] = observed_tsv(rec); res.lineage_files["lifecycle.tsv"] = lifecycle_tsv(rec); res.lineage_files["episodes.tsv"] = episodes_tsv(state, ins, last_day);
    res.lineage_files["ca_" + method_s + ".tsv"] = ca_tsv(rec); res.lineage_files["slices_" + method_s + ".tsv"] = slices_tsv(state, rec); }
  return res;
}
}  // namespace pe
