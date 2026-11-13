// M2-B lineage file writers (see lineage_recorder.hpp). Formats are byte-identical to python/pe/lineage.py (parity-tested).
#pragma once
#include "pe/ledger.hpp"
namespace pe {
inline std::string observed_tsv(const LineageRecorder& r) {
  std::ostringstream o; o << "row_type\tid\tfill_id\tparent_order_id\tinstrument_id\tepisode_id\ttimestamp_s\tside\tquantity\tprice_paise\tmodule_tag\tsource_row_id\texecution_mode\n";
  for (auto& x : r.observed) o << x.type << "\t" << x.id << "\t" << x.fill << "\t" << x.parent << "\t" << x.inst << "\t" << x.ep << "\t" << x.ts << "\t" << x.side << "\t" << x.qty << "\t" << x.px << "\t" << x.module << "\t" << x.src << "\t" << x.mode << "\n";
  return o.str();
}
inline std::string lifecycle_tsv(const LineageRecorder& r) {
  std::ostringstream o; o << "event_id\tepisode_id\tseq\tevent_type\tfill_id\tparent_order_id\ttimestamp_s\tquantity\tinventory_after\tstarted_by_reversal\n";
  for (auto& x : r.events) o << x.id << "\t" << x.ep << "\t" << x.seq << "\t" << x.type << "\t" << x.fill << "\t" << x.parent << "\t" << x.ts << "\t" << x.qty << "\t" << x.inv_after << "\t" << x.sbr << "\n";
  return o.str();
}
inline std::string terminal_status(const Episode& e, const std::map<std::string, Instrument>& ins, i64 last_day) {
  if (e.opened - e.closed == 0) return e.ended_by == "flat" ? "CLOSED" : "REVERSED";
  return ins.at(e.instrument_id).expiry_day <= last_day ? "EXPIRED_UNCLOSED" : "OPEN_AT_END_OF_DATA";
}
inline std::string episodes_tsv(const PortfolioState& st, const std::map<std::string, Instrument>& ins, i64 last_day) {
  std::ostringstream o; o << "episode_id\tinstrument_id\tdirection\tstarted_by_reversal\topened\tclosed\tremaining\tended_by\tterminal_status\tfirst_ts\tlast_ts\tn_open_fills\tn_close_fills\n";
  for (auto& kv : st.episodes) { const Episode& e = kv.second; o << kv.first << "\t" << e.instrument_id << "\t" << e.dir << "\t" << (e.started_by_reversal ? 1 : 0) << "\t" << e.opened << "\t" << e.closed << "\t" << e.opened - e.closed << "\t" << e.ended_by << "\t" << terminal_status(e, ins, last_day) << "\t" << e.first_ts << "\t" << e.last_ts << "\t" << e.n_open << "\t" << e.n_close << "\n"; }
  return o.str();
}
inline std::string ca_tsv(const LineageRecorder& r) {
  std::ostringstream o; o << "ca_id\tconvention\tcp_id\tsource_id\tallocated_qty\tentry_price\texit_price_paise\trealized_pnl\tsource_remaining_qty\townership\n";
  for (auto& x : r.ca) o << x.id << "\t" << x.conv << "\t" << x.cp << "\t" << x.source << "\t" << x.qty << "\t" << (r.avg ? fmt6(x.entry_d) : std::to_string(x.entry_i)) << "\t" << x.exit_px << "\t" << (r.avg ? fmt6(x.pnl_d) : std::to_string(x.pnl_i)) << "\t" << x.src_remaining << "\t" << x.ownership << "\n";
  return o.str();
}
inline std::string slices_tsv(const PortfolioState& st, const LineageRecorder& r) {
  std::ostringstream o; o << "slice_id\tconvention\tkind\tsource_id\tepisode_id\tremaining_qty\tprice_paise\tcontributing_oa_ids\n";
  if (st.avg) {
    std::map<std::string, std::vector<std::string>> oas; for (auto& x : r.observed) if (x.type == "OA") oas[x.ep].push_back(x.id);
    for (auto& kv : st.s) { const InstState& x = kv.second; if (x.inv > 0) { std::string list; for (auto& id : oas[x.eid]) { if (!list.empty()) list += ","; list += id; }
      o << "SL:AVG:" << x.eid << "\tAVG\tPOOL\tPOOL:" << x.eid << "\t" << x.eid << "\t" << x.pool_q << "\t" << fmt6(x.pool_px) << "\t" << list << "\n"; } }
  } else {
    struct R { std::string oa, ep; i64 q, px; }; std::vector<R> rows;
    for (auto& kv : st.s) for (auto& l : kv.second.lots) rows.push_back({l.oa, kv.second.eid, l.q, l.px});
    std::sort(rows.begin(), rows.end(), [](const R& a, const R& b) { return a.oa < b.oa; });
    for (auto& x : rows) o << "SL:" << st.method_name << ":" << x.oa << "\t" << st.method_name << "\tLOT\t" << x.oa << "\t" << x.ep << "\t" << x.q << "\t" << x.px << "\t-\n";
  }
  return o.str();
}
}  // namespace pe
