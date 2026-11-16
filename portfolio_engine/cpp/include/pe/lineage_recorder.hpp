// M2-B lineage RECORDER (data only; included by ledger.hpp). Writers are in lineage.hpp. Observed layer (OA, CP, lifecycle, episodes) is convention-independent; analytical layer (CA, slices) is per convention.
// Formats are byte-identical to python/pe/lineage.py (parity-tested). The recorder only observes the ledger's role decisions; it never changes inventory.
#pragma once
#include <sstream>
#include "pe/types.hpp"
namespace pe {
struct ObsRow { std::string type, id, fill, parent, inst, ep; i64 ts, qty, px, src; int side; std::string module, mode; };
struct EventRow { std::string id, ep; i64 seq; std::string type, fill, parent; i64 ts, qty, inv_after; int sbr; };
struct CaRow { std::string id, conv, cp, source; i64 qty; i64 entry_i = 0; double entry_d = 0; i64 exit_px = 0; i64 pnl_i = 0; double pnl_d = 0; i64 src_remaining = 0; std::string ownership; };

struct LineageRecorder {
  std::string method; bool avg = false; std::vector<ObsRow> observed; std::vector<EventRow> events; std::vector<CaRow> ca; std::map<std::string, i64> seq, can;
  explicit LineageRecorder(const std::string& m) : method(m), avg(m == "AVG") {}
  void opening_allocation(const Fill& f, const std::string& ep, i64 q) { observed.push_back({"OA", "OA:" + f.fill_id, f.fill_id, f.parent_id, f.instrument_id, ep, f.ts, q, f.price, f.source_row, f.side, f.module_tag, f.mode}); }
  void closing_portion(const Fill& f, const std::string& ep, i64 q) { observed.push_back({"CP", "CP:" + f.fill_id, f.fill_id, f.parent_id, f.instrument_id, ep, f.ts, q, f.price, f.source_row, f.side, f.module_tag, f.mode}); }
  void lifecycle(const Fill& f, const std::string& ep, const std::string& type, i64 q, i64 inv_after, bool sbr) { const i64 n = ++seq[ep]; events.push_back({"LE:" + ep + ":" + std::to_string(n), ep, n, type, f.fill_id, f.parent_id, f.ts, q, inv_after, sbr ? 1 : 0}); }
  std::string next_ca_id(const Fill& f) { const i64 n = ++can[f.fill_id]; return "CA:" + method + ":" + f.fill_id + ":" + std::to_string(n); }
  void allocation_lot(const Fill& f, const std::string& oa, i64 q, i64 entry, i64 pnl, i64 lot_remaining) { CaRow r; r.id = next_ca_id(f); r.conv = method; r.cp = "CP:" + f.fill_id; r.source = oa; r.qty = q; r.entry_i = entry; r.exit_px = f.price; r.pnl_i = pnl; r.src_remaining = lot_remaining; r.ownership = "IDENTIFIED_BY_CONVENTION"; ca.push_back(r); }
  void allocation_pool(const Fill& f, const std::string& ep, i64 q, double pool_avg, double pnl, i64 pool_remaining) { CaRow r; r.id = next_ca_id(f); r.conv = method; r.cp = "CP:" + f.fill_id; r.source = "POOL:" + ep; r.qty = q; r.entry_d = pool_avg; r.exit_px = f.price; r.pnl_d = pnl; r.src_remaining = pool_remaining; r.ownership = "NOT_IDENTIFIABLE"; ca.push_back(r); }
};

}  // namespace pe
