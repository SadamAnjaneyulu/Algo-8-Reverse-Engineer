// PortfolioState: the only place where executed inventory changes (apply_fill). Mirrors python/pe/ledger.py rule for rule.
// FIFO/LIFO use exact int64 (paise x units); AVG uses IEEE double with the identical operation order as Python (build with -ffp-contract=off).
#pragma once
#include <algorithm>
#include <deque>
#include <map>
#include <set>
#include "pe/lineage_recorder.hpp"
#include "pe/types.hpp"
namespace pe {
enum class Method { FIFO, LIFO, AVG };
inline Method parse_method(const std::string& s) { if (s == "FIFO") return Method::FIFO; if (s == "LIFO") return Method::LIFO; if (s == "AVG") return Method::AVG; throw EngineError("bad method " + s); }

struct Lot { i64 q, px; std::string oa; };
struct InstState {
  int dir = 0; i64 inv = 0; std::deque<Lot> lots; i64 pool_q = 0; double pool_px = 0.0; i64 opened = 0, closed = 0; i64 realized_i = 0; double realized_d = 0.0; i64 ep_n = 0; std::string eid;
};
struct Episode { std::string id, instrument_id; bool started_by_reversal = false; i64 first_ts = 0, last_ts = 0; int dir = 0; i64 opened = 0, closed = 0; i64 realized_i = 0; double realized_d = 0.0; std::string ended_by = "open"; i64 n_open = 0, n_close = 0; };
struct Role { std::string fill_id, instrument_id; i64 close_qty = 0, open_qty = 0, inventory_after = 0; bool reversal = false; std::string ep_closed, ep_opened; };
struct Agg { i64 short_CE = 0, short_PE = 0, long_CE = 0, long_PE = 0, open_instruments = 0; };

class PortfolioState {
 public:
  Method method; bool avg; const std::map<std::string, Instrument>& ins;
  std::map<std::string, InstState> s; std::map<std::string, Episode> episodes; i64 opened = 0, closed = 0, reversal_fills = 0, reversal_units_reopened = 0, cash = 0, applied = 0; Agg agg; std::set<std::string> applied_ids;
  std::string method_name; LineageRecorder* lin = nullptr;
  PortfolioState(Method m, const std::map<std::string, Instrument>& i, LineageRecorder* l = nullptr) : method(m), avg(m == Method::AVG), ins(i), method_name(m == Method::FIFO ? "FIFO" : (m == Method::LIFO ? "LIFO" : "AVG")), lin(l) {}

  void agg_change(const std::string& iid, i64 old_s, i64 new_s) {
    const bool call = ins.at(iid).is_call; i64& sh = call ? agg.short_CE : agg.short_PE; i64& lg = call ? agg.long_CE : agg.long_PE;
    if (old_s < 0) sh -= -old_s; else if (old_s > 0) lg -= old_s;
    if (new_s < 0) sh += -new_s; else if (new_s > 0) lg += new_s;
    agg.open_instruments += (new_s != 0) - (old_s != 0);
  }
  Role apply_fill(const Fill& f) {
    if (!applied_ids.insert(f.fill_id).second) throw InvariantViolation("fill " + f.fill_id + " applied twice");
    InstState& st = s[f.instrument_id]; const i64 q = f.qty; const int sg = f.side; const i64 px = f.price; const i64 old_signed = st.dir ? st.inv * st.dir : 0;
    i64 close_q = 0, open_q = 0; std::string eid_close, eid_open; bool reversal = false;
    if (st.dir != 0 && sg == -st.dir) {
      close_q = std::min(q, st.inv); eid_close = st.eid; Episode& ep = episodes[eid_close]; const int d = st.dir;
      if (lin) lin->closing_portion(f, eid_close, close_q);
      if (avg) { const double pnl = (double)d * ((double)px - st.pool_px) * (double)close_q; const double pool_before = st.pool_px; st.pool_q -= close_q; st.realized_d += pnl; ep.realized_d += pnl; if (lin) lin->allocation_pool(f, eid_close, close_q, pool_before, pnl, st.pool_q); }
      else {
        i64 need = close_q, pnl = 0;
        while (need > 0) {
          Lot& lot = (method == Method::FIFO) ? st.lots.front() : st.lots.back(); const i64 take = std::min(need, lot.q); const i64 p_ = (i64)d * (px - lot.px) * take; pnl += p_; lot.q -= take; need -= take;
          if (lin) lin->allocation_lot(f, lot.oa, take, lot.px, p_, lot.q);
          if (lot.q == 0) { if (method == Method::FIFO) st.lots.pop_front(); else st.lots.pop_back(); }
        }
        st.realized_i += pnl; ep.realized_i += pnl;
      }
      st.inv -= close_q; st.closed += close_q; closed += close_q; ep.closed += close_q; ep.n_close += 1;
      ep.last_ts = f.ts;
      if (st.inv == 0) { ep.ended_by = (q == close_q) ? "flat" : "reversal"; st.dir = 0; st.lots.clear(); st.pool_q = 0; st.pool_px = 0.0; }
      if (lin) lin->lifecycle(f, eid_close, st.inv > 0 ? "PARTIALLY_REDUCED" : (q == close_q ? "CLOSED" : "REVERSED"), close_q, st.inv == 0 ? 0 : st.inv * d, false);
      open_q = q - close_q; if (open_q > 0) reversal = true;
    } else open_q = q;
    if (open_q > 0) {
      const bool created = st.dir == 0;
      if (created) { st.dir = sg; st.ep_n += 1; st.eid = f.instrument_id + "#" + std::to_string(st.ep_n); Episode e; e.id = st.eid; e.instrument_id = f.instrument_id; e.dir = sg; e.started_by_reversal = reversal; e.first_ts = f.ts; e.last_ts = f.ts; episodes[st.eid] = e; }
      eid_open = st.eid; Episode& ep = episodes[eid_open]; ep.last_ts = f.ts;
      if (avg) { st.pool_px = (st.pool_px * (double)st.pool_q + (double)(px * open_q)) / (double)(st.pool_q + open_q); st.pool_q += open_q; } else st.lots.push_back({open_q, px, "OA:" + f.fill_id});
      if (lin) { lin->opening_allocation(f, eid_open, open_q); lin->lifecycle(f, eid_open, created ? "CREATED" : "ADDED", open_q, (st.inv + open_q) * st.dir, reversal && created); }
      st.inv += open_q; st.opened += open_q; opened += open_q; ep.opened += open_q; ep.n_open += 1;
    }
    if (reversal) { reversal_fills += 1; reversal_units_reopened += open_q; }
    const i64 new_signed = st.dir ? st.inv * st.dir : 0; agg_change(f.instrument_id, old_signed, new_signed); cash += -(i64)sg * q * px; applied += 1;
    if (close_q > q || close_q + open_q != q || (st.dir && st.inv <= 0)) throw InvariantViolation("role arithmetic broken on " + f.fill_id);
    return Role{f.fill_id, f.instrument_id, close_q, open_q, new_signed, reversal, eid_close, eid_open};
  }
  i64 signed_inventory(const std::string& iid) const { auto it = s.find(iid); return (it == s.end() || !it->second.dir) ? 0 : it->second.inv * it->second.dir; }
  // returns {int value, double value}; only the one matching the method is meaningful
  double book_value_d(const InstState& st) const { if (!st.dir) return 0.0; const double v = (double)st.pool_q * st.pool_px; return st.dir < 0 ? v : -v; }
  i64 book_value_i(const InstState& st) const { if (!st.dir) return 0; i64 v = 0; for (auto& l : st.lots) v += l.q * l.px; return st.dir < 0 ? v : -v; }
  i64 realized_total_i() const { i64 t = 0; for (auto& kv : s) t += kv.second.realized_i; return t; }
  double realized_total_d() const { double t = 0.0; for (auto& kv : s) t += kv.second.realized_d; return t; }
  i64 book_total_i() const { i64 t = 0; for (auto& kv : s) t += book_value_i(kv.second); return t; }
  double book_total_d() const { double t = 0.0; for (auto& kv : s) t += book_value_d(kv.second); return t; }
};

// accounting invariants (same list as python/pe/invariants.py); throws InvariantViolation
inline std::vector<std::string> check_state(const PortfolioState& st, const std::map<std::string, i64>* expected_signed = nullptr) {
  std::vector<std::string> done; i64 gross = 0; auto ok = [&](const char* name, bool c, const std::string& d = "") { done.push_back(name); if (!c) throw InvariantViolation(std::string(name) + ": " + d); };
  for (auto& kv : st.s) {
    const InstState& x = kv.second; ok("inventory_non_negative_in_direction", x.inv >= 0 && (x.inv == 0 || x.dir == 1 || x.dir == -1), kv.first);
    i64 lots = 0; if (st.avg) lots = x.pool_q; else for (auto& l : x.lots) lots += l.q;
    ok("lots_reconcile_to_inventory", lots == x.inv, kv.first); ok("per_instrument_opened_minus_closed", x.opened - x.closed == x.inv, kv.first); gross += x.inv;
  }
  ok("portfolio_opened_minus_closed_equals_gross_inventory", st.opened - st.closed == gross);
  ok("aggregates_reconcile_to_instruments", st.agg.short_CE + st.agg.short_PE + st.agg.long_CE + st.agg.long_PE == gross);
  if (expected_signed) for (auto& kv : *expected_signed) ok("signed_inventory_equals_sum_of_fills", st.signed_inventory(kv.first) == kv.second, kv.first);
  const double tol = 1e-6 * (double)std::max<i64>(1, st.applied);
  if (!st.avg) { ok("cash_identity_cash_equals_realized_plus_book_value", st.cash - (st.realized_total_i() + st.book_total_i()) == 0); i64 er = 0; for (auto& kv : st.episodes) er += kv.second.realized_i; ok("episode_realized_sums_to_portfolio_realized", er == st.realized_total_i()); }
  else { const double diff = (double)st.cash - (st.realized_total_d() + st.book_total_d()); ok("cash_identity_cash_equals_realized_plus_book_value", std::abs(diff) <= tol); double er = 0; for (auto& kv : st.episodes) er += kv.second.realized_d; ok("episode_realized_sums_to_portfolio_realized", std::abs(er - st.realized_total_d()) <= tol); }
  i64 eu = 0; for (auto& kv : st.episodes) eu += kv.second.opened - kv.second.closed; ok("episode_units_reconcile", eu == gross);
  return done;
}
}  // namespace pe
