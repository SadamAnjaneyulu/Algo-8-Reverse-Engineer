"""Deterministic event replay: validate mode, order events, apply each fill once, snapshot, check invariants, write the canonical state dump."""
from .schema import *
from .ledger import PortfolioState
from . import invariants

TIE_KEY = {'src': lambda s: 0, 'sells_first': lambda s: 0 if s < 0 else 1, 'buys_first': lambda s: 0 if s > 0 else 1}


class RunResult:
    def __init__(self): self.lineage = None; self.last_day = 0; self.instruments = None; self.dump = ''; self.state = None; self.roles = []; self.snapshots = []; self.warnings = {}; self.meta = {}; self.checks = []


def order_events(fills, tie_order):
    """deterministic order (timestamp, tie key, source row, fill id); the first three are TP-01's per-contract order, the id only breaks exact ties between synthetic rows"""
    tk = TIE_KEY[tie_order]
    return sorted(fills, key=lambda f: (f.timestamp_s, tk(f.side), f.source_row_id, f.fill_id))


def _fmt(x, avg): return f'{x:.6f}' if avg else str(int(x))


def replay(fills, instruments, mode, method='FIFO', tie_order='src', snapshot_interval=0, strict=False, lineage=False):
    if mode not in MODES: raise EngineError(f'unknown mode {mode}')
    if method not in METHODS or tie_order not in TIE_ORDERS: raise EngineError('bad method / tie order')
    for f in fills:                                                          # the in-memory API is as strict as the TSV loader
        if f.quantity <= 0 or f.price_paise <= 0 or f.price_paise % TICK_PAISE or f.side not in (1, -1): raise EventValidationError(f'fill {f.fill_id}: invalid quantity / price / side')
    for f in fills:                                                          # contamination guard: checked BEFORE anything is applied
        if f.execution_mode != mode: raise ModeContaminationError(f'fill {f.fill_id} has mode {f.execution_mode}, run mode is {mode}')
    warn = {k: 0 for k in WARN_CODES}
    warn['INPUT_NOT_TIME_ORDERED'] = sum(1 for a, b in zip(fills, fills[1:]) if b.timestamp_s < a.timestamp_s)
    ordered = order_events(fills, tie_order); live = [f for f in ordered if not f.is_duplicate_fill]; warn['DUPLICATE_FILL_IGNORED'] = len(ordered) - len(live)
    groups = {}
    for f in live: groups.setdefault((f.instrument_id, f.timestamp_s), set()).add(f.side)
    warn['TIE_GROUP_MIXED_SIDE'] = sum(1 for v in groups.values() if len(v) == 2)
    warn['PARTIAL_FILL_ROWS'] = sum(1 for f in live if f.order_status == 'PartiallyFilled'); warn['MISSING_MARKS'] = 1
    from .lineage import LineageRecorder
    rec = LineageRecorder(method) if lineage else None
    state = PortfolioState(method, instruments, rec); res = RunResult(); signed = {}; parents = {}; snaps = []; roles = []
    def snap(seq, ts):
        a = state.agg; short = a['short_CE'] + a['short_PE']; long = a['long_CE'] + a['long_PE']
        snaps.append(dict(seq=seq, timestamp_s=ts, date=day_iso(ist_day(ts)), open_instruments=a['open_instruments'], short_CE=a['short_CE'], short_PE=a['short_PE'], long_CE=a['long_CE'], long_PE=a['long_PE'],
                          gross_units=short + long, net_units=long - short, realized=state.realized_total(), cash=state.cash, unrealized='NA'))
    n = len(live)
    for k, f in enumerate(live):
        roles.append(state.apply_fill(f)); signed[f.instrument_id] = signed.get(f.instrument_id, 0) + f.side * f.quantity
        p = parents.setdefault(f.parent_order_id, dict(fills=0, units=0, requested=f.requested_quantity, days=set())); p['fills'] += 1; p['units'] += f.quantity; p['days'].add(ist_day(f.timestamp_s))
        if strict: invariants.check_state(state, signed)
        last = k == n - 1; day_end = last or ist_day(live[k + 1].timestamp_s) != ist_day(f.timestamp_s)
        if day_end or (snapshot_interval and state.applied % snapshot_interval == 0): snap(state.applied, f.timestamp_s)
    res.checks = invariants.check_state(state, signed)
    last_day = ist_day(live[-1].timestamp_s) if live else 0; stat = {}; exp_units = 0; open_units = 0
    for iid, st in state.s.items():
        inv = st.inv
        if inv == 0: stat[iid] = 'CLOSED'
        elif iso_day(instruments[iid].expiry) <= last_day: stat[iid] = 'EXPIRED_UNCLOSED'; exp_units += inv
        else: stat[iid] = 'OPEN_AT_END_OF_DATA'; open_units += inv
    warn['EXPIRED_UNCLOSED_INSTRUMENTS'] = sum(1 for v in stat.values() if v == 'EXPIRED_UNCLOSED')
    for p in parents.values():
        warn['UNFILLED_REMAINDER_ORDERS'] += p['units'] < p['requested']; warn['OVERFILLED_ORDERS'] += p['units'] > p['requested']; warn['PARENT_SPANS_DATES'] += len(p['days']) > 1
    avg = state.avg; L = ['#PE_STATE_DUMP v1']
    meta = [('method', method), ('tie_order', tie_order), ('execution_mode', mode), ('events_read', len(fills)), ('events_applied', state.applied), ('duplicates_ignored', warn['DUPLICATE_FILL_IGNORED']),
            ('first_ts', live[0].timestamp_s if live else 0), ('last_ts', live[-1].timestamp_s if live else 0), ('last_date', day_iso(last_day) if live else '')]
    L += [f'META\t{k}\t{v}' for k, v in meta]
    tot = [('opened_units', state.opened), ('closed_units', state.closed), ('remaining_units', state.opened - state.closed), ('reversal_fills', state.reversal_fills), ('reversal_units_reopened', state.reversal_units_reopened),
           ('realized_pnl_paise', _fmt(state.realized_total(), avg)), ('cash_flow_paise', state.cash), ('remaining_book_value_paise', _fmt(state.book_total(), avg)),
           ('remaining_expired_unclosed_units', exp_units), ('remaining_open_at_end_units', open_units)]
    L += [f'TOTAL\t{k}\t{v}' for k, v in tot]
    for iid in sorted(state.s):
        st = state.s[iid]; L.append(f'INSTR\t{iid}\t{state.signed_inventory(iid)}\t{st.opened}\t{st.closed}\t{_fmt(st.realized, avg)}\t{_fmt(state.book_value(iid), avg)}\t{stat[iid]}')
    for eid in sorted(state.episodes):
        e = state.episodes[eid]; L.append(f'EPISODE\t{eid}\t{e["direction"]}\t{e["opened"]}\t{e["closed"]}\t{e["opened"] - e["closed"]}\t{_fmt(e["realized"], avg)}\t{e["ended_by"]}\t{e["n_open_fills"]}\t{e["n_close_fills"]}')
    for s_ in snaps: L.append(f'SNAP\t{s_["seq"]}\t{s_["timestamp_s"]}\t{s_["date"]}\t{s_["open_instruments"]}\t{s_["short_CE"]}\t{s_["short_PE"]}\t{s_["long_CE"]}\t{s_["long_PE"]}\t{s_["gross_units"]}\t{s_["net_units"]}\t{_fmt(s_["realized"], avg)}\t{s_["cash"]}\t{s_["unrealized"]}')
    for pid in sorted(parents):
        p = parents[pid]; status = 'COMPLETE' if p['units'] == p['requested'] else ('UNFILLED_REMAINDER' if p['units'] < p['requested'] else 'OVERFILLED'); L.append(f'PARENT\t{pid}\t{p["fills"]}\t{p["units"]}\t{p["requested"]}\t{status}')
    for k in WARN_CODES: L.append(f'WARN\t{k}\t{warn[k]}')
    res.lineage = rec; res.last_day = last_day; res.instruments = instruments
    res.dump = '\n'.join(L) + '\n'; res.state = state; res.roles = roles; res.snapshots = snaps; res.warnings = warn; res.meta = dict(meta)
    return res


def roles_tsv(roles):
    L = ['fill_id\tinstrument_id\tclose_qty\topen_qty\tinventory_after\tis_reversal\tepisode_closed\tepisode_opened']
    for r in sorted(roles, key=lambda r: r.fill_id): L.append(f'{r.fill_id}\t{r.instrument_id}\t{r.close_qty}\t{r.open_qty}\t{r.inventory_after}\t{int(r.is_reversal)}\t{r.episode_closed or "-"}\t{r.episode_opened or "-"}')
    return '\n'.join(L) + '\n'


def lineage_files(res):
    """name -> text for the M2-B lineage outputs of one convention (observed files are convention-independent by construction and by test)"""
    from . import lineage as ln
    m = res.state.method
    return {'observed_allocations.tsv': ln.observed_tsv(res.lineage), 'lifecycle.tsv': ln.lifecycle_tsv(res.lineage), 'episodes.tsv': ln.episodes_tsv(res.state, res.instruments, res.last_day),
            f'ca_{m}.tsv': ln.ca_tsv(res.lineage, res.state.avg), f'slices_{m}.tsv': ln.slices_tsv(res.state, res.lineage)}
