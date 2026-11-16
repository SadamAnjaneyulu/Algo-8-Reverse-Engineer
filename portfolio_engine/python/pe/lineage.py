"""M2-B position lineage. Two layers (docs/POSITION_BASKET_ONTOLOGY.md):
  OBSERVED, convention-independent: OpeningAllocation (OA), ClosingPortion (CP), lifecycle events, episodes   -> files observed_allocations.tsv, lifecycle.tsv, episodes.tsv
  ANALYTICAL, convention-dependent: ClosingAllocation (CA) and PositionSlice                                  -> files ca_<CONV>.tsv, slices_<CONV>.tsv
The recorder only OBSERVES the ledger's role decisions; it never changes inventory. Output files are byte-identical in the C++ core (parity-tested)."""
from .schema import *

TERMINAL = ('CLOSED', 'REVERSED', 'EXPIRED_UNCLOSED', 'OPEN_AT_END_OF_DATA', 'INCOMPLETE_SOURCE_HISTORY')   # the last one is reserved: never produced without external evidence


class LineageRecorder:
    def __init__(self, method):
        self.method = method; self.observed = []; self.events = []; self.ca = []; self._seq = {}; self._ca_n = {}

    # ---------------- observed layer
    def opening_allocation(self, f, episode_id, qty):
        self.observed.append(('OA', f'OA:{f.fill_id}', f.fill_id, f.parent_order_id, f.instrument_id, episode_id, f.timestamp_s, f.side, qty, f.price_paise, f.module_tag, f.source_row_id, f.execution_mode))

    def closing_portion(self, f, episode_id, qty):
        self.observed.append(('CP', f'CP:{f.fill_id}', f.fill_id, f.parent_order_id, f.instrument_id, episode_id, f.timestamp_s, f.side, qty, f.price_paise, f.module_tag, f.source_row_id, f.execution_mode))

    def lifecycle(self, f, episode_id, event_type, qty, inventory_after_signed, started_by_reversal):
        n = self._seq.get(episode_id, 0) + 1; self._seq[episode_id] = n
        self.events.append((f'LE:{episode_id}:{n}', episode_id, n, event_type, f.fill_id, f.parent_order_id, f.timestamp_s, qty, inventory_after_signed, int(started_by_reversal)))

    # ---------------- analytical layer (convention dependent)
    def _ca_id(self, f):
        n = self._ca_n.get(f.fill_id, 0) + 1; self._ca_n[f.fill_id] = n; return f'CA:{self.method}:{f.fill_id}:{n}'

    def allocation_lot(self, f, episode_id, oa_id, qty, entry_px, pnl, lot_remaining):
        self.ca.append((self._ca_id(f), self.method, f'CP:{f.fill_id}', oa_id, qty, entry_px, f.price_paise, pnl, lot_remaining, 'IDENTIFIED_BY_CONVENTION'))

    def allocation_pool(self, f, episode_id, qty, pool_avg, pnl, pool_remaining):
        self.ca.append((self._ca_id(f), self.method, f'CP:{f.fill_id}', f'POOL:{episode_id}', qty, pool_avg, f.price_paise, pnl, pool_remaining, 'NOT_IDENTIFIABLE'))


# ======================================================================= file writers (identical format in C++)
def _num(x, avg): return f'{x:.6f}' if avg else str(int(x))


def observed_tsv(rec):
    L = ['row_type\tid\tfill_id\tparent_order_id\tinstrument_id\tepisode_id\ttimestamp_s\tside\tquantity\tprice_paise\tmodule_tag\tsource_row_id\texecution_mode']
    L += ['\t'.join(str(v) for v in r) for r in rec.observed]; return '\n'.join(L) + '\n'


def lifecycle_tsv(rec):
    L = ['event_id\tepisode_id\tseq\tevent_type\tfill_id\tparent_order_id\ttimestamp_s\tquantity\tinventory_after\tstarted_by_reversal']
    L += ['\t'.join(str(v) for v in r) for r in rec.events]; return '\n'.join(L) + '\n'


def terminal_status(state, ep, instruments, last_day):
    """terminal status of an episode at the end of the replay (EXPIRED_UNCLOSED only by the contract's expiry date; no settlement value exists)"""
    if ep['opened'] - ep['closed'] == 0: return 'CLOSED' if ep['ended_by'] == 'flat' else 'REVERSED'
    return 'EXPIRED_UNCLOSED' if iso_day(instruments[ep['instrument_id']].expiry) <= last_day else 'OPEN_AT_END_OF_DATA'


def episodes_tsv(state, instruments, last_day):
    L = ['episode_id\tinstrument_id\tdirection\tstarted_by_reversal\topened\tclosed\tremaining\tended_by\tterminal_status\tfirst_ts\tlast_ts\tn_open_fills\tn_close_fills']
    for eid in sorted(state.episodes):
        e = state.episodes[eid]
        L.append('\t'.join(str(v) for v in (eid, e['instrument_id'], e['direction'], int(e['started_by_reversal']), e['opened'], e['closed'], e['opened'] - e['closed'], e['ended_by'], terminal_status(state, e, instruments, last_day), e['first_ts'], e['last_ts'], e['n_open_fills'], e['n_close_fills'])))
    return '\n'.join(L) + '\n'


def ca_tsv(rec, avg):
    L = ['ca_id\tconvention\tcp_id\tsource_id\tallocated_qty\tentry_price\texit_price_paise\trealized_pnl\tsource_remaining_qty\townership']
    for r in rec.ca: L.append('\t'.join([r[0], r[1], r[2], r[3], str(r[4]), _num(r[5], avg) if avg else str(int(r[5])), str(r[6]), _num(r[7], avg), str(r[8]), r[9]]))
    return '\n'.join(L) + '\n'


def slices_tsv(state, rec):
    """remaining analytical slices at the end of the replay. FIFO/LIFO: one LOT per OA with remaining > 0. AVG: one POOL per open episode (contributing OAs listed as provenance, NOT ownership)"""
    avg = state.avg; L = ['slice_id\tconvention\tkind\tsource_id\tepisode_id\tremaining_qty\tprice_paise\tcontributing_oa_ids']
    if avg:
        oas = {}
        for r in rec.observed:
            if r[0] == 'OA': oas.setdefault(r[5], []).append(r[1])
        for iid in sorted(state.s):
            st = state.s[iid]
            if st.inv > 0: L.append('\t'.join([f'SL:AVG:{st.eid}', 'AVG', 'POOL', f'POOL:{st.eid}', st.eid, str(st.pool_q), f'{st.pool_px:.6f}', ','.join(oas.get(st.eid, []))]))
    else:
        rows = []
        for iid in sorted(state.s):
            st = state.s[iid]
            for lot in st.lots: rows.append((lot[2], st.eid, lot[0], lot[1]))
        for oa, eid, q, px in sorted(rows): L.append('\t'.join([f'SL:{state.method}:{oa}', state.method, 'LOT', oa, eid, str(q), str(px), '-']))
    return '\n'.join(L) + '\n'
