"""M2-E: read-only forensic assembly for the two frozen demonstration cycles.

Nothing here re-implements accounting, closing-batch grouping or wing/body association: the observed layer comes from LineageSet (M2-B), closing batches and
wing/body views are read from the COMMITTED M2-C / M2-D outputs filtered by (underlying, expiry) and are asserted equal to a per-cycle recomputation by the build tool.
Every timestamp is UTC epoch seconds; every human-readable time is IST (UTC+05:30) and is labelled so. Marks are never invented: no market bars => marks are MISSING.
"""
import csv, gzip, hashlib, io, json, os, time
from collections import Counter, defaultdict

IST = 19800
CYCLES = (('NIFTY', '2026-06-30'), ('SENSEX', '2026-07-16'))                       # frozen in e06a711e before any grouping; never substituted
VERSION = 'M2E_1'


def ist_date(ts): return time.strftime('%Y-%m-%d', time.gmtime(ts + IST))
def ist_str(ts): return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts + IST))
def cycle_key(und, expiry): return f'{und}_{expiry}'


class Cycle:
    def __init__(self, repo, und, expiry):
        from .lineage_set import LineageSet
        from .generators import historical as H
        self.repo, self.und, self.expiry = repo, und, expiry
        self.ins, self.fills, self.src = H.generate(repo, cycle=(und, expiry))
        self.ls = LineageSet(self.fills, self.ins, 'HISTORICAL_OBSERVED_REPLAY', 'src')
        rows = H.generate_parents(repo, self.ls.roles); pids = {f.parent_order_id for f in self.fills}
        self.meta = {r['parent_order_id']: r for r in rows if r['parent_order_id'] in pids}
        self.sessions = sorted({ist_date(f.timestamp_s) for f in self.fills})
        self.key = cycle_key(und, expiry)

    def d_label(self, ts):
        s = ist_date(ts)
        if s == self.expiry: return 'D0'
        assert s < self.expiry, f'fill after expiry session: {s}'
        prior = [x for x in self.sessions if x < self.expiry]; return f'D-{len(prior) - prior.index(s)}'

    def right(self, instrument_id): return self.ins[instrument_id].option_type
    def strike(self, instrument_id): return self.ins[instrument_id].strike


# ------------------------------------------------------------------------------------------------------------------------------ small TSV helpers
def tsv(header, rows):
    return '\n'.join(['\t'.join(header)] + ['\t'.join('' if v is None else str(v) for v in r) for r in rows]) + '\n'


def read_tsv_text(text):
    L = text.rstrip('\n').split('\n'); h = L[0].split('\t'); return h, [dict(zip(h, l.split('\t'))) for l in L[1:] if l]


def read_gz_text(path):
    with gzip.open(path, 'rt') as f: return f.read()


def sha(text): return hashlib.sha256(text.encode()).hexdigest()


# ------------------------------------------------------------------------------------------------------------------------------ datasets (observed layer)
def fills_table(c):
    H = ['fill_id', 'source_row_id', 'parent_order_id', 'module_tag', 'instrument_id', 'right', 'strike', 'ts_utc_s', 'ts_ist', 'session_ist', 'd_label', 'side', 'quantity', 'price_paise', 'requested_quantity', 'order_status', 'is_duplicate_fill', 'opening_qty', 'closing_qty']
    oq = defaultdict(int); cq = defaultdict(int)
    for r in c.ls.oa.values(): oq[r[2]] += r[8]
    for r in c.ls.cp.values(): cq[r[2]] += r[8]
    rows = [(f.fill_id, f.source_row_id, f.parent_order_id, f.module_tag, f.instrument_id, c.right(f.instrument_id), c.strike(f.instrument_id), f.timestamp_s, ist_str(f.timestamp_s), ist_date(f.timestamp_s), c.d_label(f.timestamp_s),
             f.side, f.quantity, f.price_paise, f.requested_quantity, f.order_status, int(f.is_duplicate_fill), oq[f.fill_id], cq[f.fill_id]) for f in sorted(c.fills, key=lambda f: (f.timestamp_s, f.source_row_id))]
    return H, rows


def inventory_series(c):
    """V1 data. Position per instrument is taken from the M2-B lifecycle events (signed inventory_after); one row per fill (state AFTER the fill)."""
    ls = c.ls; ev_by_fill = defaultdict(list)
    for e in ls.events: ev_by_fill[e[4]].append(e)
    fills = sorted(c.fills, key=lambda f: (f.timestamp_s, f.source_row_id)); pos = defaultdict(int)
    cum_open = defaultdict(int); cum_close = defaultdict(int); opened_by_fill = defaultdict(list); closed_by_fill = defaultdict(list)
    for r in ls.oa.values(): opened_by_fill[r[2]].append(r)
    for r in ls.cp.values(): closed_by_fill[r[2]].append(r)
    H = ['seq', 'fill_id', 'ts_utc_s', 'ts_ist', 'session_ist', 'd_label', 'instrument_id', 'fill_side', 'fill_quantity', 'short_CE', 'short_PE', 'long_CE', 'long_PE', 'net_CE', 'net_PE', 'net_total', 'gross_total',
         'cum_opened_units', 'cum_closed_units', 'cum_opened_num_short', 'cum_opened_h_long', 'cum_opened_other', 'cum_closed_by_tag_num', 'cum_closed_by_tag_h_', 'cum_closed_by_tag_s_', 'cum_closed_by_tag_v_', 'cum_closed_by_tag_other', 'lifecycle_events']
    rows = []
    for i, f in enumerate(fills, 1):
        evs = ev_by_fill[f.fill_id]; assert evs, f'fill {f.fill_id} has no lifecycle event'
        for e in evs:
            pos[ls.episodes[e[1]]['instrument_id']] = e[8]            # inventory_after is SIGNED in M2-B lifecycle (short < 0)
        for r in opened_by_fill[f.fill_id]:
            cum_open['all'] += r[8]; k = 'num_short' if (r[10] == 'num' and r[7] < 0) else 'h_long' if (r[10] == 'h_' and r[7] > 0) else 'other'; cum_open[k] += r[8]
        for r in closed_by_fill[f.fill_id]:
            cum_close['all'] += r[8]; cum_close[r[10] if r[10] in ('num', 'h_', 's_', 'v_') else 'other'] += r[8]
        s = {('short', 'CE'): 0, ('short', 'PE'): 0, ('long', 'CE'): 0, ('long', 'PE'): 0}
        for iid, p in pos.items():
            if p: s[('long' if p > 0 else 'short', c.right(iid))] += abs(p)
        netCE = s[('long', 'CE')] - s[('short', 'CE')]; netPE = s[('long', 'PE')] - s[('short', 'PE')]
        rows.append((i, f.fill_id, f.timestamp_s, ist_str(f.timestamp_s), ist_date(f.timestamp_s), c.d_label(f.timestamp_s), f.instrument_id, f.side, f.quantity, s[('short', 'CE')], s[('short', 'PE')], s[('long', 'CE')], s[('long', 'PE')], netCE, netPE, netCE + netPE,
                     sum(s.values()), cum_open['all'], cum_close['all'], cum_open['num_short'], cum_open['h_long'], cum_open['other'], cum_close['num'], cum_close['h_'], cum_close['s_'], cum_close['v_'], cum_close['other'], '|'.join(e[3] for e in evs)))
    return H, rows


def session_carry(c):
    """Inventory (units) at the last fill of each IST session, by right and direction: what is carried into the next session."""
    H, rows = inventory_series(c); I = {h: k for k, h in enumerate(H)}; last = {}
    for r in rows: last[r[I['session_ist']]] = r
    return ['session_ist', 'd_label', 'last_fill_id', 'last_fill_ts_ist', 'short_CE', 'short_PE', 'long_CE', 'long_PE', 'gross_total'], [(s, r[I['d_label']], r[I['fill_id']], r[I['ts_ist']], r[I['short_CE']], r[I['short_PE']], r[I['long_CE']], r[I['long_PE']], r[I['gross_total']]) for s, r in sorted(last.items())]


def lifecycle_table(c):
    ls = c.ls; ep = ls.episodes; fl = {f.fill_id: f for f in c.fills}
    H = ['event_id', 'episode_id', 'instrument_id', 'right', 'strike', 'direction', 'seq', 'event_type', 'fill_id', 'source_row_id', 'parent_order_id', 'module_tag', 'ts_utc_s', 'ts_ist', 'session_ist', 'd_label', 'quantity', 'inventory_after', 'started_by_reversal']
    rows = []
    for e in ls.events:
        f = fl[e[4]]; E = ep[e[1]]
        rows.append((e[0], e[1], E['instrument_id'], c.right(E['instrument_id']), c.strike(E['instrument_id']), 'SHORT' if E['direction'] < 0 else 'LONG', e[2], e[3], e[4], f.source_row_id, e[5], f.module_tag, e[6], ist_str(e[6]), ist_date(e[6]), c.d_label(e[6]), e[7], e[8], e[9]))
    return H, rows


def episodes_table(c):
    ls = c.ls; from . import lineage as ln
    H = ['episode_id', 'instrument_id', 'right', 'strike', 'direction', 'started_by_reversal', 'opened', 'closed', 'remaining', 'ended_by', 'terminal_status', 'first_ts_utc_s', 'last_ts_utc_s', 'first_ts_ist', 'last_ts_ist', 'n_open_fills', 'n_close_fills', 'n_parents']
    par = defaultdict(set)
    for r in list(ls.oa.values()) + list(ls.cp.values()): par[r[5]].add(r[3])
    rows = []
    for eid, E in sorted(ls.episodes.items(), key=lambda kv: (kv[1]['first_ts'], kv[0])):
        ts = ln.terminal_status(ls.runs['FIFO'].state, E, ls.instruments, ls.runs['FIFO'].last_day)
        rows.append((eid, E['instrument_id'], c.right(E['instrument_id']), c.strike(E['instrument_id']), 'SHORT' if E['direction'] < 0 else 'LONG', int(E['started_by_reversal']), E['opened'], E['closed'], E['opened'] - E['closed'], E['ended_by'], ts, E['first_ts'], E['last_ts'], ist_str(E['first_ts']), ist_str(E['last_ts']), E['n_open_fills'], E['n_close_fills'], len(par[eid])))
    return H, rows


def opening_items(c, tp03):
    """V3 data: one row per (parent order, instrument) over ALL opening allocations (M2-B OA). Role is a MODULE-TAG label only (never ownership)."""
    ls = c.ls; g = {}
    for r in sorted(ls.oa.values(), key=lambda r: (r[6], r[11])):
        k = (r[3], r[4]); d = g.setdefault(k, dict(parent=r[3], inst=r[4], tag=r[10], side=r[7], qty=0, notional=0, first=r[6], last=r[6], n=0, oas=[], fills=[]))
        d['qty'] += r[8]; d['notional'] += r[8] * r[9]; d['last'] = max(d['last'], r[6]); d['n'] += 1; d['oas'].append(r[1]); d['fills'].append(r[2])
    H = ['item_key', 'parent_order_id', 'instrument_id', 'right', 'strike', 'module_tag', 'side', 'tag_role', 'quantity', 'avg_price_paise', 'n_opening_fills', 'first_ts_utc_s', 'last_ts_utc_s', 'first_ts_ist', 'session_ist', 'd_label', 'order_entry_minute_s', 'order_entry_minute_ist', 'app_key_last6',
         'order_number', 'requested_units', 'tp03_event_class', 'oa_ids']
    rows = []
    for k, d in sorted(g.items(), key=lambda kv: (kv[1]['first'], kv[0])):
        m = c.meta.get(d['parent']) or {}; em = m.get('order_entry_minute_s')
        role = 'BODY_SHORT_BY_TAG' if (d['tag'] == 'num' and d['side'] < 0) else 'WING_LONG_BY_TAG' if (d['tag'] == 'h_' and d['side'] > 0) else f"UNCLASSIFIED({d['tag']},{'SELL' if d['side'] < 0 else 'BUY'})"
        cls = tp03.get(d['parent'], 'NOT_LISTED_BY_TP03_AS_OFF_WINDOW')
        rows.append((f"{d['parent']}|{d['inst']}", d['parent'], d['inst'], c.right(d['inst']), c.strike(d['inst']), d['tag'], d['side'], role, d['qty'], round(d['notional'] / d['qty'], 4), d['n'], d['first'], d['last'], ist_str(d['first']), ist_date(d['first']), c.d_label(d['first']),
                     'NA' if em is None else em, 'NA' if em is None else ist_str(em), m.get('app_key_last6') or 'NA', m.get('order_number') or 'NA', m.get('requested_units', 'NA'), cls, ','.join(d['oas'])))
    return H, rows


def tp03_overlay(repo, c):
    """TP-03 entry-window attribution, kept SEPARATE from every grouping: window rows (as published) and the per-parent off-window classes TP-03 lists. TP-03 publishes no per-parent window id."""
    import pandas as pd
    A = os.path.join(repo, 'tp_reconstruction', 'tp03')
    w = pd.read_parquet(os.path.join(A, 'data', 'p1_window_dataset.parquet')); w = w[w.cycle == f'{c.und}|{c.expiry}']
    o = pd.read_csv(os.path.join(A, 'analysis', 'p1_off_window_events.csv')); o = o[o.cycle == f'{c.und}|{c.expiry}']
    cls = {str(p): e for p, e in zip(o.parent_oid, o.event_class)}
    H = ['cycle', 'kind', 'date', 'window', 'window_start_ts_utc_s', 'window_start_ist', 'control_window', 'view1_class', 'view2_class', 'view3_class', 'n_parents_inside', 'n_parents_ambiguous', 'n_parents_decision_fill_outside', 'n_body_short_fills_in_window', 'Q_v2']
    rows = []
    for r in w.sort_values(['date', 'window']).itertuples():
        hh, mm = (int(x) for x in r.window.split(':')); d = pd.Timestamp(r.date); t = int(d.value // 10**9) + hh * 3600 + mm * 60 - IST        # window label is an IST wall-clock time
        rows.append((r.cycle, r.kind, str(d.date()), r.window, t, ist_str(t), int(r.control_window), r.view1_class, r.view2_class, r.view3_class, int(r.n_parents_inside), int(r.n_parents_ambiguous), int(r.n_parents_decision_fill_outside), int(r.n_body_short_fills_in_window), r.Q_v2))
    return cls, H, rows


# ------------------------------------------------------------------------------------------------------------------------------ canonical M2-C / M2-D slices
def m2c_slice(repo, c):
    out = {}; key = f':{c.und}:{c.expiry}:'
    for kind in ('closing_batches', 'closing_batch_members', 'closing_batch_portions'):
        for m in ('C1', 'C2'):
            name = f'{kind}_{m}.tsv'; text = read_gz_text(os.path.join(repo, 'portfolio_engine', 'reports', 'm2c_data', name + '.gz')); L = text.rstrip('\n').split('\n')
            out[name] = '\n'.join([L[0]] + [l for l in L[1:] if key in l.split('\t')[0]]) + '\n'
    return out


def m2d_slice(repo, c):
    out = {}
    for name in ['wing_body_items'] + [f'wing_body_links_{m}' for m in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3')]:
        text = read_gz_text(os.path.join(repo, 'portfolio_engine', 'reports', 'm2d_data', name + '.tsv.gz')); L = text.rstrip('\n').split('\n'); h = L[0].split('\t'); u, e = h.index('underlying'), h.index('expiry')
        out[name + '.tsv'] = '\n'.join([L[0]] + [l for l in L[1:] if l.split('\t')[u] == c.und and l.split('\t')[e] == c.expiry]) + '\n'
    return out


def recompute_m2c_m2d(c):
    """Per-cycle recomputation with the committed engines; the build tool asserts text equality with the filtered committed slices."""
    from . import closing_batches as cb, wing_body as wb
    parents, unattr, multi = cb.closing_parents(c.ls); views = cb.all_views(parents); files = {}
    for m in ('C1', 'C2'): files.update(cb.files_for_method(views, m, c.ls))
    R = wb.analyse(c.ls, c.meta, 'TAGGED'); wb.check(R, c.ls)
    return files, R, dict(closing_parents=len(parents), unattributable=len(unattr), parents_in_multiple_streams=len(multi))


# ------------------------------------------------------------------------------------------------------------------------------ independent reconciliation (computed from raw fills only)
class ReconciliationError(AssertionError): pass


def need(cond, msg):
    if not cond: raise ReconciliationError(msg)


def reconcile_observed(c):
    """Independent re-derivation: signed position per instrument from side*quantity only (no lineage), compared with the V1 series, lifecycle table and episode table."""
    H, rows = inventory_series(c); I = {h: k for k, h in enumerate(H)}; fills = sorted(c.fills, key=lambda f: (f.timestamp_s, f.source_row_id))
    need(len(rows) == len(fills), 'series rows != fills'); pos = defaultdict(int); n = 0; carry_ok = True
    for r, f in zip(rows, fills):
        need(r[I['fill_id']] == f.fill_id, 'series order differs from fill order'); pos[f.instrument_id] += f.side * f.quantity
        s = Counter()
        for iid, p in pos.items():
            if p: s[('long' if p > 0 else 'short', c.right(iid))] += abs(p)
        for k, col in ((('short', 'CE'), 'short_CE'), (('short', 'PE'), 'short_PE'), (('long', 'CE'), 'long_CE'), (('long', 'PE'), 'long_PE')): need(s[k] == r[I[col]], f'{col} mismatch at {f.fill_id}: independent {s[k]} vs series {r[I[col]]}')
        need(r[I['gross_total']] == sum(s.values()) and r[I['net_total']] == sum(v if k[0] == 'long' else -v for k, v in s.items()), f'gross/net mismatch at {f.fill_id}'); n += 1
    oq = Counter(); cq = Counter()
    for r in c.ls.oa.values(): oq[r[2]] += r[8]
    for r in c.ls.cp.values(): cq[r[2]] += r[8]
    for f in fills: need(oq[f.fill_id] + cq[f.fill_id] == f.quantity, f'opening+closing != fill quantity at {f.fill_id}')
    opened = sum(oq.values()); closed = sum(cq.values()); last = rows[-1]; need(last[I['cum_opened_units']] == opened and last[I['cum_closed_units']] == closed, 'cumulative opened/closed != OA/CP totals')
    # episodes: opened - closed == remaining and equals the final signed position of the instrument's last episode
    final = {iid: p for iid, p in pos.items()}; EH, ER = episodes_table(c); J = {h: k for k, h in enumerate(EH)}; by_inst = defaultdict(list)
    for r in ER: by_inst[r[J['instrument_id']]].append(r)
    for iid, lst in by_inst.items():
        last_ep = max(lst, key=lambda r: (r[J['last_ts_utc_s']], r[J['episode_id']])); sign = -1 if last_ep[J['direction']] == 'SHORT' else 1
        need(sign * last_ep[J['remaining']] == final.get(iid, 0), f'remaining of last episode != independent final position for {iid}')
    LH, LR = lifecycle_table(c); K = {h: k for k, h in enumerate(LH)}
    need(sum(1 for r in LR if r[K['event_type']] == 'CLOSED') + sum(1 for r in LR if r[K['event_type']] == 'REVERSED') == len(ER), 'episode count != closed+reversed events (expired-unclosed would be unterminated)')
    need(all(r[K['ts_ist']][:10] == r[K['session_ist']] for r in LR), 'IST session label inconsistent')
    # IST sanity: no fill outside the NSE/BSE cash-derivative session in IST (would reveal UTC read as IST or vice versa)
    for f in fills:
        t = (f.timestamp_s + IST) % 86400; need(9 * 3600 + 14 * 60 <= t <= 15 * 3600 + 31 * 60, f'fill {f.fill_id} outside 09:14-15:31 IST: timezone suspect')
    return dict(fills=n, opened_units=opened, closed_units=closed, episodes=len(ER), final_open_instruments=sum(1 for p in final.values() if p), independent_checks='PASS')


# ------------------------------------------------------------------------------------------------------------------------------ cycle coverage (source audit)
def marks_audit(c):
    d = os.environ.get('ALGO8_MARKET_DIR'); present = bool(d and os.path.isdir(os.path.join(d, 'indices')))
    contracts = sorted({f.instrument_id for f in c.fills}); sel = None
    p = os.path.join(c.repo, 'portfolio_engine', 'reports', 'demo_cycle_scores.csv')
    if os.path.exists(p):
        with open(p) as fh:
            for r in csv.DictReader(fh):
                if r['cycle'] == f'{c.und}|{c.expiry}': sel = dict(C4_option_marks=r['C4_option_marks'], C5_classification=r['C5_classification'], C6_d1_d0=r['C6_d1_d0'])
    return dict(source_env_var='ALGO8_MARKET_DIR', source_present_in_this_environment=present, contracts_traded=len(contracts),
                historical_mark_status='NOT_COMPUTED: raw 1-minute option bars are absent from this environment; coverage unknown here, NO mark substituted, no unrealized P&L computed' if not present else 'SOURCE_PRESENT_BUT_MARK_COVERAGE_NOT_IMPLEMENTED_IN_M2E',
                recorded_at_cycle_selection_time=sel, recorded_note='selection-time C4 value is a recorded earlier measurement; it is not reproducible here and is not used for any M2-E number',
                prices_used_in_M2E='EXECUTION prices only (fill price_paise); no market mark, no interpolation, unrealized P&L = NA', expired_unclosed_positions=0)


def cycle_coverage(c, slices_c, slices_d, R, recomputed_meta):
    from . import wing_body as wb
    ls = c.ls; I = {}
    oq = Counter(); cq = Counter()
    for r in ls.oa.values(): oq[r[2]] += r[8]
    for r in ls.cp.values(): cq[r[2]] += r[8]
    fills = c.fills; per_session = {}
    EH, ER = episodes_table(c); J = {h: k for k, h in enumerate(EH)}
    for s in c.sessions:
        fs = [f for f in fills if ist_date(f.timestamp_s) == s]
        per_session[s] = dict(d_label=c.d_label(fs[0].timestamp_s), fills=len(fs), parents=len({f.parent_order_id for f in fs}), opening_units=sum(oq[f.fill_id] for f in fs), closing_units=sum(cq[f.fill_id] for f in fs), first_fill_ist=ist_str(min(f.timestamp_s for f in fs)), last_fill_ist=ist_str(max(f.timestamp_s for f in fs)),
                              instruments=len({f.instrument_id for f in fs}), episodes_started=sum(1 for r in ER if ist_date(r[J['first_ts_utc_s']]) == s), episodes_ended=sum(1 for r in ER if ist_date(r[J['last_ts_utc_s']]) == s))
    mt = {k: sum(1 for m in c.meta.values() if m.get(k) not in (None, '')) for k in ('order_entry_minute_s', 'app_key_full', 'order_number', 'algo_id', 'requested_units', 'first_fill_ts')}
    ih, ir = opening_items(c, {}); K = {h: k for k, h in enumerate(ih)}; role_units = Counter()
    for r in ir: role_units[r[K['tag_role']]] += r[K['quantity']]
    ph, pr = read_tsv_text(slices_c['closing_batch_portions_C1.tsv']); cp_roles = Counter()
    for r in pr:
        if r['threshold_s'] == '10': cp_roles[r['role']] += int(r['quantity'])
    wcov = {f'{lv}|{m}': wb.coverage(R, lv, m) for lv in wb.LEVELS for m in ('W1', 'W1_S60') + (('W3',) if lv == 'OPENING' else ())}
    parents = {f.parent_order_id for f in fills}
    return dict(
        cycle=f'{c.und}|{c.expiry}', sessions=c.sessions,
        fills=dict(raw_fill_count=len(fills), duplicate_flagged=sum(f.is_duplicate_fill for f in fills), partially_filled_status=sum(1 for f in fills if f.order_status == 'PartiallyFilled'), unique_parent_orders=len(parents),
                   opening_fills=sum(1 for f in fills if oq[f.fill_id] > 0), closing_fills=sum(1 for f in fills if cq[f.fill_id] > 0), fills_with_both_opening_and_closing_quantity=sum(1 for f in fills if oq[f.fill_id] > 0 and cq[f.fill_id] > 0),
                   opening_units=sum(oq.values()), closing_units=sum(cq.values()), parent_roles=dict(Counter(ls.roles[p] for p in parents)), mixed_parent_ids=sorted(p for p in parents if ls.roles[p] == 'MIXED')),
        episodes=dict(episode_count=len(ER), terminal_status=dict(Counter(r[J['terminal_status']] for r in ER)), started_by_reversal=sum(r[J['started_by_reversal']] for r in ER), expired_unclosed=sum(1 for r in ER if r[J['terminal_status']] not in ('CLOSED', 'REVERSED'))),
        historical_marks=marks_audit(c),
        role_classification=dict(opening_units_by_tag_role=dict(role_units), opening_units_total=sum(role_units.values()),
                                 opening_units_classified_by_tag=role_units['BODY_SHORT_BY_TAG'] + role_units['WING_LONG_BY_TAG'], opening_units_unclassified=sum(v for k, v in role_units.items() if k.startswith('UNCLASSIFIED')),
                                 closing_units_by_M2C_role_10s=dict(cp_roles), m2d_tagged_scope_exclusions_units=wb.scope_exclusions(ls)),
        order_metadata=dict(parents=len(parents), metadata_rows=len(c.meta), field_available=mt, field_missing={k: len(parents) - v for k, v in mt.items()}),
        d1_d0=per_session,
        missing_or_ambiguous=dict(parents_with_mixed_role=sum(1 for p in parents if ls.roles[p] == 'MIXED'), partially_filled_fills=sum(1 for f in fills if f.order_status == 'PartiallyFilled'), unattributable_closing_portions=recomputed_meta['unattributable'],
                                  closing_parents_in_multiple_streams=recomputed_meta['parents_in_multiple_streams'], parents_without_metadata=len(parents - set(c.meta)), wing_items_without_W1_candidate=wcov['OPENING|W1']['wing_items_no_candidate'], wing_items_without_W1_S60_candidate=wcov['OPENING|W1_S60']['wing_items_no_candidate'],
                                  body_items_without_wing_W1=wcov['OPENING|W1']['body_items_without_wing'], body_items_without_wing_W1_S60=wcov['OPENING|W1_S60']['body_items_without_wing']),
        wing_body_coverage_cycle_level=wcov)
