"""Phase 3 - replacement and re-entry continuity: the position-management state machine.  PRE-REGISTERED (rules fixed here before results were read).

EVENTS (clean order table, column-163 key; fill times at 1-second resolution; body orders are stamped to the minute, so 'time' below is the FIRST FILL):
  reduction  R : every closing short buy-back (11,007 orders, any module / label, incl. Clock-B rebalances, stops, reductions, liquidation).
  sale       S : every short-opening sell (label 'open', side Sell; 13,410 orders; module tag kept).
  hedge      H : every wing order (long opening buy, or wing close labelled 'L-...').
  Inventory before / after every order (contract and right level) from a running pass over all orders in replay order (common.orders() ordering).

LINKER (event-based; association only, NOT ownership):
  * A sale can be linked only to EARLIER reductions (replay order AND first fill not after the sale's first fill) of the same underlying, expiry, right (CE / PE) and date.
  * Quantity: each reduction has capacity = lots bought back; a sale's lots are assigned greedily and may be SPLIT across reductions (one link row per split);
    no reduction gives more lots than it bought back, and no sale lot is used twice.
  * Scheduled sales (first fill inside a schedule window [09:16 + 15k - 2 s, + 180 s)) are 'independent scheduled entry' and do NOT consume capacity (primary);
    variant 'sched_consumes' lets them consume it.
  * Candidate order (primary): the most RECENT reduction first, same contract breaking ties.  Variants: 'same-contract-first' (same contract, then most recent; this
    was the first version of the rule and is kept as a sensitivity: it tied Clock-B re-sales to older same-strike reductions), 'earliest' (oldest first),
    'sched_consumes', 'horizon 15 min' (candidates > 15 min dropped).
  * Ambiguity flag: at the sale time, eligible reductions with capacity on >= 2 different contracts within 15 min  ->  ownership 'ambiguous'.
CLASSES of a link (exclusive, in this order):
  dt > 15 min                                   -> unresolved association (too far apart for a structural claim)
  same contract, contract inventory 0 before sale -> same-contract re-entry after full closure
  same contract, all of the reduction re-sold in that contract -> same-contract replacement
  same contract, part of it                     -> partial position replenishment
  different strike, sale strike = ATM (nearest strike to the index at the last completed minute) and the original strike was not ATM -> ATM re-centering
  different strike otherwise                    -> same-right, different-strike replacement
  Sales not linked: independent scheduled entry | independent off-grid entry (no eligible antecedent) | independent off-grid entry (antecedent capacity exhausted).
  Wing orders within 0-60 s after a reduction of the same right -> hedge adjustment (wings never consume short capacity).
ASSOCIATION TEST: observed (reduction -> later off-grid same-right sale) pairs per window vs a null that shifts every reduction by a random +-20..120 min inside the same
  session (200 draws).  Windows 0-30 s, 30-60 s, 1-5 min, 5-15 min, > 15 min.  Clock-B's ~28 s median is a reference, not a matching rule.
OWNERSHIP (separate from association): for each linked lot pair (closed lot -> new lot; closed lots by convention cheap / fifo / lifo):
  A slot  : the new lot keeps its own slot allocation (off-grid sale = new 'extra' allocation) -> continuation iff the slots are equal
  B chain : continuation iff the timer-phase chains are equal
  C event : the new lot INHERITS the closed lot's allocation (non-ambiguous, <= 15 min replacement links only; ambiguous links -> an explicit 'AMB|' thread)
  'identified' only if all three conventions give the closed lot the same slot allocation; otherwise 'convention-dependent'.
LIFECYCLE: per thread (allocation under A / B / C x convention): OPEN, ADD, REDUCE, CLOSE (inventory -> 0 and later re-opened), REPLACE (C-linked replacement),
  RE-ENTER (re-opened after CLOSE; or C-linked re-entry after full closure), CARRY (open at the first D0 minute), FINAL CLOSE (last close).  Only observed orders create events.
python3 analysis/allocation/replacement.py -> results/replacement_event_links.csv, replacement_transition_matrix.csv, position_lifecycle_ledger.csv (model C, cheapest-first)
  and .csv.gz (all 9 model x convention ledgers),
  unresolved_position_links.csv, state_transition_metrics.csv, replacement_association_null.csv, replacement_variant_stability.csv"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE)
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine')); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from common import orders, markets, minute_index, split_of
from alloc import build_allocations, lot_ledger, slot_of, RES

BUCKETS = [(0, 30, '0-30 s'), (30, 60, '30-60 s'), (60, 300, '1-5 min'), (300, 900, '5-15 min'), (900, 10 ** 9, '> 15 min')]
STEP = {'NIFTY': 50, 'SENSEX': 100}
REPLACE_CLASSES = ('same-contract replacement', 'partial position replenishment', 'ATM re-centering', 'same-right, different-strike replacement')
REENTRY_CLASS = 'same-contract re-entry after full closure'
AMB_WIN = 900

def bucket(dt):
    for a, b, n in BUCKETS:
        if a <= dt < b: return n
    return 'negative'

def prepare(o=None, mk=None):
    o = orders() if o is None else o; mk = markets() if mk is None else mk
    o = o.copy(); o['seq'] = np.arange(len(o)); o['t'] = pd.to_datetime(o.t_fill)
    # running inventory (short lots) per contract and per right, in replay order
    ic_b, ic_a, ir_b, ir_a = (np.zeros(len(o), int) for _ in range(4))
    for _, g in o.groupby(['und', 'expiry']):
        pos = {}; sh_r = {'CE': 0, 'PE': 0}
        for i, r in zip(g.index, g.itertuples()):
            k = (r.cp, r.strike); p0 = pos.get(k, 0); p1 = p0 + (int(r.lots) if r.side == 'Buy' else -int(r.lots)); pos[k] = p1
            s0, s1 = max(-p0, 0), max(-p1, 0); ic_b[i], ic_a[i] = s0, s1; ir_b[i] = sh_r[r.cp]; sh_r[r.cp] += s1 - s0; ir_a[i] = sh_r[r.cp]
    o['inv_contract_before'], o['inv_contract_after'], o['inv_right_before'], o['inv_right_after'] = ic_b, ic_a, ir_b, ir_a
    # ATM distance (in strikes) at the last completed minute before the order
    atm = np.full(len(o), np.nan)
    for (u, e), g in o.groupby(['und', 'expiry']):
        if (u, e) not in mk: continue
        m = mk[(u, e)]; mi = np.array([max(minute_index(m['grid'], t) - 1, 0) for t in g.t]); S = m['S'][mi]
        atm[g.index] = (g.strike.values - S) / STEP[u]
    o['atm_steps'] = atm; o['is_atm'] = np.abs(o.atm_steps) <= 0.5
    o['slot_k'] = [slot_of(t)[0] for t in o.t]; o['on_grid'] = o.slot_k >= 0
    return o, mk

def link(o, priority='recent', sched_consumes=False, horizon=None):
    R = o[(o.closing_short == True) & (o.side == 'Buy')]; S = o[(o.label == 'open') & (o.side == 'Sell')]
    links, unl = [], []
    for (u, e, cp, d), sg in S.groupby(['und', 'expiry', 'cp', 'date']):
        rg = R[(R.und == u) & (R.expiry == e) & (R.cp == cp) & (R.date == d)].sort_values('seq')
        cap = dict(zip(rg.oid, rg.lots.astype(int))); rinfo = {r.oid: r for r in rg.itertuples()}
        for s in sg.sort_values('seq').itertuples():
            left = int(s.lots)
            if s.on_grid and not sched_consumes:
                unl.append(dict(sale_oid=s.oid, lots=left, cls='independent scheduled entry')); continue
            cands = [r for r in rinfo.values() if r.seq < s.seq and cap[r.oid] > 0]
            dts = {r.oid: (s.t - r.t).total_seconds() for r in cands}
            cands = [r for r in cands if dts[r.oid] >= 0]          # a sale whose first fill precedes the reduction's first fill is not 'subsequent'
            if horizon is not None: cands = [r for r in cands if dts[r.oid] <= horizon]
            if not cands:
                unl.append(dict(sale_oid=s.oid, lots=left, cls='independent scheduled entry' if s.on_grid else 'independent off-grid entry (no eligible antecedent)')); continue
            near = {(r.cp, r.strike) for r in cands if dts[r.oid] <= AMB_WIN}; amb = len(near) >= 2; n60 = len({(r.cp, r.strike) for r in cands if dts[r.oid] <= 60})
            key = {'recent': lambda r: (dts[r.oid], r.strike != s.strike), 'same-contract-first': lambda r: (r.strike != s.strike, dts[r.oid]),
                   'earliest': lambda r: (-dts[r.oid], r.strike != s.strike)}[priority]
            split = 0
            for r in sorted(cands, key=key):
                if left == 0: break
                q = min(left, cap[r.oid]); cap[r.oid] -= q; left -= q; split += 1
                links.append(dict(und=u, expiry=e, cp=cp, date=d, red_oid=r.oid, red_label=r.label, red_module=r.tp, red_clock=r.clock, red_t=r.t, red_strike=r.strike, red_lots=int(r.lots),
                                  red_px=r.vwap, red_quote=r.L, red_atm_steps=r.atm_steps, red_is_atm=r.is_atm, red_inv_contract_before=r.inv_contract_before, red_inv_contract_after=r.inv_contract_after,
                                  red_inv_right_before=r.inv_right_before, red_inv_right_after=r.inv_right_after,
                                  sale_oid=s.oid, sale_module=s.tp, sale_t=s.t, sale_strike=s.strike, sale_lots=int(s.lots), sale_px=s.vwap, sale_quote=s.L, sale_atm_steps=s.atm_steps, sale_is_atm=s.is_atm,
                                  sale_on_grid=bool(s.on_grid), sale_inv_contract_before=s.inv_contract_before, sale_inv_contract_after=s.inv_contract_after, sale_inv_right_before=s.inv_right_before,
                                  sale_inv_right_after=s.inv_right_after, linked_lots=q, split_index=split, dt_s=dts[r.oid], ownership_ambiguous=amb, competing_contracts_15min=len(near), competing_contracts_60s=n60, red_seq=r.seq, sale_seq=s.seq, split=split_of(e)))
            if left > 0: unl.append(dict(sale_oid=s.oid, lots=left, cls='independent scheduled entry' if s.on_grid else 'independent off-grid entry (antecedent capacity exhausted)'))
    Lk = pd.DataFrame(links); U = pd.DataFrame(unl)
    if len(Lk):
        same = Lk.red_strike == Lk.sale_strike
        tot_same = Lk[same].groupby('red_oid').linked_lots.sum(); full = Lk.red_oid.map(tot_same).fillna(0).values >= Lk.red_lots.values
        cls = np.select([Lk.dt_s > 900, same & (Lk.sale_inv_contract_before == 0), same & full, same, Lk.sale_is_atm & ~Lk.red_is_atm],
                        ['unresolved association', REENTRY_CLASS, 'same-contract replacement', 'partial position replenishment', 'ATM re-centering'], 'same-right, different-strike replacement')
        Lk['cls'] = np.where(Lk.sale_on_grid, 'independent scheduled entry', cls)   # only possible in the sched_consumes variant
        Lk['window'] = Lk.dt_s.map(bucket); Lk['strike_change_steps'] = (Lk.sale_strike - Lk.red_strike) / Lk.und.map(STEP)
    return Lk, U

def hedge_links(o):
    R = o[(o.closing_short == True) & (o.side == 'Buy')]
    W = o[((o.label == 'open') & (o.side == 'Buy')) | o.label.str.startswith('L-')]
    out = []
    for (u, e, cp, d), wg in W.groupby(['und', 'expiry', 'cp', 'date']):
        rg = R[(R.und == u) & (R.expiry == e) & (R.cp == cp) & (R.date == d)]
        if rg.empty: continue
        rs, rt = rg.seq.values, rg.t.values
        for w in wg.itertuples():
            ok = (rs < w.seq) & ((w.t - pd.to_datetime(rt)).total_seconds() <= 60)
            if not ok.any(): continue
            j = np.where(ok)[0][np.argmax(rs[ok])]; dt = (w.t - pd.Timestamp(rt[j])).total_seconds()
            out.append(dict(und=u, expiry=e, cp=cp, red_oid=rg.oid.values[j], red_label=rg.label.values[j], wing_oid=w.oid, wing_side=w.side, wing_label=w.label, wing_strike=w.strike,
                            wing_lots=int(w.lots), dt_s=dt, window=bucket(dt), cls='hedge adjustment'))
    return pd.DataFrame(out)

def association_null(o, reps=200, seed=0):
    """observed vs time-shifted-null counts of (reduction, later off-grid same-right sale) pairs per window and reduction label."""
    rng = np.random.default_rng(seed); R = o[(o.closing_short == True) & (o.side == 'Buy')]; S = o[(o.label == 'open') & (o.side == 'Sell') & ~o.on_grid]
    sec = lambda t: (t - t.dt.normalize()).dt.total_seconds().values
    lo, hi = 9 * 3600 + 20 * 60, 15 * 3600 + 25 * 60; edges = [b[0] for b in BUCKETS] + [7 * 3600]
    grp = R.label.where(~R.label.isin(['5 cycle stop & liquidation', '6 clock-based exit (final flatten)', '7 expiry-day salvage', '10 manual / platform risk engine', '11 unexplained']), 'scheduled / liquidation / other')
    obs = np.zeros((grp.nunique(), len(BUCKETS))); null = np.zeros((reps, grp.nunique(), len(BUCKETS))); gi = {g: i for i, g in enumerate(sorted(grp.unique()))}
    Sg = {k: np.sort(sec(g.t)) for k, g in S.groupby(['und', 'expiry', 'cp', 'date'])}
    for k, g in R.assign(grp=grp).groupby(['und', 'expiry', 'cp', 'date']):
        st = Sg.get(k)
        if st is None: continue
        rt = sec(g.t); gidx = np.array([gi[x] for x in g.grp])
        def counts(tt):
            c = np.zeros((len(gi), len(BUCKETS)))
            for b in range(len(BUCKETS)):
                n = np.searchsorted(st, tt + edges[b + 1], 'left') - np.searchsorted(st, tt + edges[b], 'right' if b == 0 else 'left')
                np.add.at(c[:, b], gidx, n)
            return c
        obs += counts(rt)
        for rep in range(reps):
            sh = rng.uniform(1200, 7200, len(rt)) * rng.choice([-1, 1], len(rt)); tt = rt + sh
            bad = (tt < lo) | (tt > hi); tt[bad] = rt[bad] - sh[bad]; tt = np.clip(tt, lo, hi); null[rep] += counts(tt)
    rows = []
    for g, i in gi.items():
        for b, (_, _, bn) in enumerate(BUCKETS):
            nm = null[:, i, b]; rows.append(dict(reduction_group=g, window=bn, observed_pairs=int(obs[i, b]), null_mean=nm.mean(), null_p95=np.percentile(nm, 95),
                                                  excess_ratio=obs[i, b] / max(nm.mean(), 1e-9), p_value=float((nm >= obs[i, b]).mean())))
    return pd.DataFrame(rows)

def ownership(Lk, ledgers, A):
    """pair each linked lot (closed lot of the reduction -> new lot of the sale) under each convention; returns pair table."""
    rows = []
    slot = dict(zip(A.oid, A.alloc_slot)); chain = dict(zip(A.oid, A.alloc_chain))
    for conv, L in ledgers.items():
        sh = L[(L.sgn < 0)]
        closed = {k: g.sort_values('entry_t') for k, g in sh[sh.exit_oid.isin(set(Lk.red_oid))].groupby('exit_oid')}
        newl = {k: g.sort_values('entry_t') for k, g in sh[sh.entry_oid.isin(set(Lk.sale_oid))].groupby('entry_oid')}
        pr, ps = {}, {}
        for l in Lk.sort_values(['sale_seq', 'split_index']).itertuples():
            c = closed.get(l.red_oid); n = newl.get(l.sale_oid)
            if c is None or n is None: continue
            i0, j0 = pr.get(l.red_oid, 0), ps.get(l.sale_oid, 0); q = min(l.linked_lots, len(c) - i0, len(n) - j0)
            for t in range(q):
                cl, nl = c.iloc[i0 + t], n.iloc[j0 + t]
                rows.append(dict(conv=conv, link_id=l.Index, red_oid=l.red_oid, sale_oid=l.sale_oid, cls=l.cls, ownership_ambiguous=l.ownership_ambiguous, dt_s=l.dt_s,
                                 closed_lot_entry_oid=cl.entry_oid, closed_slot=cl.alloc_slot, closed_chain=cl.alloc_chain, new_slot=slot.get(l.sale_oid), new_chain=chain.get(l.sale_oid),
                                 new_lot_key=(nl.entry_oid, int(nl.name)), closed_lot_key=(cl.entry_oid, int(cl.name))))
            pr[l.red_oid] = i0 + q; ps[l.sale_oid] = j0 + q
    P = pd.DataFrame(rows)
    if len(P):
        P['A_continuation'] = P.closed_slot == P.new_slot; P['B_continuation'] = P.closed_chain == P.new_chain
        agree = P.groupby(['link_id']).closed_slot.nunique()
        P['owner_convention_status'] = np.where(P.link_id.map(agree) == 1, 'identified (same slot under all conventions)', 'convention-dependent')
    return P

def threads(L, model, P, Lk, conv):
    """thread id per short lot under model A / B / C."""
    s = L[(L.sgn < 0)].copy(); s['lot_key'] = list(zip(s.entry_oid, s.index.astype(int)))
    if model == 'A': s['thread'] = s.alloc_slot
    elif model == 'B': s['thread'] = s.alloc_chain
    else:
        th = dict(zip(s.lot_key, s.alloc_slot)); how = {}
        pc = P[P.conv == conv].copy() if len(P) else P
        pc = pc.merge(Lk[['sale_seq']], left_on='link_id', right_index=True).sort_values('sale_seq')
        for r in pc.itertuples():
            if r.cls in REPLACE_CLASSES + (REENTRY_CLASS,):
                th[r.new_lot_key] = ('AMB|' + str(r.sale_oid)) if r.ownership_ambiguous else th.get(r.closed_lot_key, r.closed_slot)
                how[r.new_lot_key] = 'RE-ENTER' if r.cls == REENTRY_CLASS else 'REPLACE'
        s['thread'] = s.lot_key.map(th); s['entry_via'] = s.lot_key.map(how)
    if 'entry_via' not in s: s['entry_via'] = None
    s['thread'] = s.thread.fillna('nonentry'); return s

def lifecycle(s, o, model, conv):
    seq = dict(zip(o.oid, o.seq)); lab = dict(zip(o.oid, o.label)); big = 10 ** 9
    e1 = pd.DataFrame(dict(thread=s.thread, oid=s.entry_oid, seq=s.entry_oid.map(seq), t=s.entry_t, d=1, via=s.entry_via, cp=s.cp, strike=s.strike, und=s.und, expiry=s.expiry))
    ex = s.exit_oid.fillna('EXPIRY'); e2 = pd.DataFrame(dict(thread=s.thread, oid=ex, seq=s.exit_oid.map(seq).fillna(big), t=s.exit_t, d=-1, via=None, cp=s.cp, strike=s.strike, und=s.und, expiry=s.expiry))
    E = pd.concat([e1, e2]); E['via'] = E.via.fillna('')
    G = E.groupby(['thread', 'oid', 'd', 'via'], dropna=False).agg(seq=('seq', 'first'), t=('t', 'first'), qty=('d', 'size'), cp=('cp', 'first'), strike=('strike', 'first'), und=('und', 'first'),
                                                                     expiry=('expiry', 'first')).reset_index().sort_values(['thread', 'seq', 'd'], ascending=[True, True, False])
    G['delta'] = G.d * G.qty; G['inv_after'] = G.groupby('thread').delta.cumsum(); G['inv_before'] = G.inv_after - G.delta
    G['n_after'] = G.groupby('thread').cumcount(ascending=False)
    # last close = FINAL CLOSE; a close followed by a re-opening = CLOSE
    reopen_after = G.groupby('thread').d.transform(lambda x: x[::-1].eq(1).cumsum()[::-1].shift(-1, fill_value=0) > 0)
    first = G.groupby('thread').cumcount() == 0
    et = np.select([(G.d == 1) & (G.via == 'REPLACE'), (G.d == 1) & (G.via == 'RE-ENTER'), (G.d == 1) & first, (G.d == 1) & (G.inv_before == 0), G.d == 1,
                    (G.d == -1) & (G.inv_after > 0), (G.d == -1) & reopen_after], ['REPLACE', 'RE-ENTER', 'OPEN', 'RE-ENTER', 'ADD', 'REDUCE', 'CLOSE'], 'FINAL CLOSE')
    G['event'] = et; G['exit_label'] = G.oid.map(lab).where(G.d == -1)
    # CARRY: thread open at the first D0 minute
    d0 = pd.to_datetime(G.expiry) + pd.Timedelta('09:15:00'); pre = G[(pd.to_datetime(G.t) < d0) & (G.d == 1) | ((G.d == -1) & (pd.to_datetime(G.t) < d0))]
    last_pre = pre.groupby('thread').tail(1); car = last_pre[last_pre.inv_after > 0]
    C = car.assign(event='CARRY', oid='D0-OPEN', d=0, delta=0, qty=car.inv_after, inv_before=car.inv_after, seq=car.seq + 0.5, t=pd.to_datetime(car.expiry) + pd.Timedelta('09:15:00'), exit_label=None)
    G = pd.concat([G, C]).sort_values(['thread', 'seq', 'd'], ascending=[True, True, False]).reset_index(drop=True)
    G['model'] = model; G['conv'] = conv; G['event_seq'] = G.groupby('thread').cumcount()
    return G[['model', 'conv', 'thread', 'event_seq', 'event', 'oid', 't', 'und', 'expiry', 'cp', 'strike', 'qty', 'inv_before', 'inv_after', 'exit_label']]

def inventory_check(o, L):
    """reconstructed contract inventory from the lot ledger vs the running order pass, after every order."""
    s = L[L.sgn < 0]; seq = dict(zip(o.oid, o.seq)); big = 10 ** 9
    ev = pd.concat([pd.DataFrame(dict(c=list(zip(s.und, s.expiry, s.cp, s.strike)), seq=s.entry_oid.map(seq), d=1)),
                    pd.DataFrame(dict(c=list(zip(s.und, s.expiry, s.cp, s.strike)), seq=s.exit_oid.map(seq).fillna(big), d=-1))])
    ev = ev.groupby(['c', 'seq']).d.sum().reset_index().sort_values(['c', 'seq']); ev['inv'] = ev.groupby('c').d.cumsum()
    oo = o[['seq', 'und', 'expiry', 'cp', 'strike', 'inv_contract_after']].copy(); oo['c'] = list(zip(oo.und, oo.expiry, oo.cp, oo.strike))
    m = oo.merge(ev[['c', 'seq', 'inv']], on=['c', 'seq'], how='left'); m['inv'] = m.groupby('c').inv.ffill().fillna(0)
    return int((m.inv != m.inv_contract_after).sum()), len(m)

def metrics(G, P, model, conv, inv_mismatch):
    tr = G.assign(nxt=G.groupby('thread').event.shift(-1)).dropna(subset=['nxt'])
    ev = G.event.value_counts(); th = G.groupby('thread')
    rep = G[G.event == 'REPLACE']
    d = dict(model=model, conv=conv, threads=G.thread.nunique(), events=len(G), mean_events_per_thread=len(G) / max(G.thread.nunique(), 1),
             negative_inventory_events=int((G.inv_after < 0).sum()), inventory_mismatches_vs_orders=inv_mismatch,
             threads_with_CARRY=int(th.event.apply(lambda x: (x == 'CARRY').any()).sum()), threads_with_REPLACE=int(th.event.apply(lambda x: (x == 'REPLACE').any()).sum()),
             threads_with_RE_ENTER=int(th.event.apply(lambda x: (x == 'RE-ENTER').any()).sum()), threads_closed_and_reopened=int(th.event.apply(lambda x: (x == 'CLOSE').any()).sum()),
             ambiguous_threads=int(G.thread.astype(str).str.startswith('AMB|').groupby(G.thread).first().sum()),
             share_threads_with_at_most_2_events=float((th.size() <= 2).mean()))
    for e in ['OPEN', 'ADD', 'REDUCE', 'CLOSE', 'REPLACE', 'RE-ENTER', 'CARRY', 'FINAL CLOSE']: d['n_' + e] = int(ev.get(e, 0))
    if model == 'C' and len(rep):
        # restoration: after REPLACE, is the thread back at its inventory before the preceding reduction(s)?
        g = G.copy(); g['prev_peak'] = g.groupby('thread').inv_after.cummax()
        r = g[g.event == 'REPLACE']; d['replace_restores_thread_peak'] = float((r.inv_after >= r.prev_peak).mean())
    pc = P[P.conv == conv] if len(P) else P
    if len(pc):
        sub = pc[pc.cls.isin(REPLACE_CLASSES + (REENTRY_CLASS,))]
        d['replacement_lot_pairs'] = len(sub); d['A_continuation_share'] = float(sub.A_continuation.mean()); d['B_continuation_share'] = float(sub.B_continuation.mean())
        d['ownership_identified_share'] = float((sub.owner_convention_status.str.startswith('identified') & ~sub.ownership_ambiguous).mean())
    return d, tr.groupby(['event', 'nxt']).size().rename('n').reset_index().assign(model=model, conv=conv)

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 300)
    o, mk = prepare(); A = build_allocations(o)
    Lk, U = link(o); Lk = Lk.reset_index(drop=True)
    # ---- integrity: no double counting, capacity respected -------------------------------------------------------------------------------------------
    assert (Lk.groupby('red_oid').linked_lots.sum() <= Lk.groupby('red_oid').red_lots.first()).all(), 'reduction capacity exceeded'
    sl = pd.concat([Lk.groupby('sale_oid').linked_lots.sum(), U.groupby('sale_oid').lots.sum()], axis=1).fillna(0).sum(axis=1)
    S = o[(o.label == 'open') & (o.side == 'Sell')].set_index('oid').lots
    assert (sl.reindex(S.index).fillna(0).values == S.values).all(), 'sale lots not conserved'
    H = hedge_links(o); N = association_null(o)
    sup = N[(N.p_value < 0.05) & (N.excess_ratio > 1)]; sup = set(zip(sup.reduction_group, sup.window))
    Lk['reduction_group'] = Lk.red_label.where(Lk.red_label.isin(N.reduction_group.unique()), 'scheduled / liquidation / other')
    Lk['association_supported'] = [(g, w) in sup for g, w in zip(Lk.reduction_group, Lk.window)]
    ledgers = {c: lot_ledger(c, A) for c in ('cheap', 'fifo', 'lifo')}
    P = ownership(Lk, ledgers, A)
    # ---- variants for stability ----------------------------------------------------------------------------------------------------------------------
    var = []
    for vn, kw in (('primary (recent, sched excluded, same day)', {}), ('same-contract-first', dict(priority='same-contract-first')), ('earliest-first', dict(priority='earliest')),
                   ('scheduled sales consume capacity', dict(sched_consumes=True)),
                   ('horizon 15 min', dict(horizon=900))):
        lk, uu = (Lk, U) if not kw else link(o, **kw)
        t = pd.concat([lk.groupby('cls').linked_lots.sum(), uu.groupby('cls').lots.sum()]).groupby(level=0).sum()
        t60 = lk[lk.dt_s <= 60].groupby('cls').linked_lots.sum()
        var += [dict(variant=vn, cls=c, lots=int(v), share_of_sale_lots=v / S.sum(), lots_linked_within_60s=int(t60.get(c, 0))) for c, v in t.items()]
    V = pd.DataFrame(var)
    # ---- lifecycles ----------------------------------------------------------------------------------------------------------------------------------
    met, trs, leds = [], [], []
    for conv, L in ledgers.items():
        mis = inventory_check(o, L)
        for model in ('A', 'B', 'C'):
            s = threads(L, model, P, Lk, conv); G = lifecycle(s, o, model, conv); m, t = metrics(G, P, model, conv, mis[0]); m['orders_checked'] = mis[1]; met.append(m); trs.append(t); leds.append(G)
    M = pd.DataFrame(met); T = pd.concat(trs); LED = pd.concat(leds)
    # ---- per reduction label: how much of what was bought back is re-sold, how fast, and how ------------------------------------------------------------
    R = o[(o.closing_short == True) & (o.side == 'Buy')]; tot = R.groupby('label').lots.sum()
    BR = pd.DataFrame({'reduction_lots': tot})
    for nm, msk in (('resold_0_30s', Lk.dt_s < 30), ('resold_0_60s', Lk.dt_s < 60), ('resold_0_15min', Lk.dt_s < 900)):
        BR[nm] = Lk[msk].groupby('red_label').linked_lots.sum().reindex(BR.index).fillna(0) / BR.reduction_lots
    for c in REPLACE_CLASSES + (REENTRY_CLASS,):
        BR['le60s_' + c] = Lk[(Lk.dt_s < 60) & (Lk.cls == c)].groupby('red_label').linked_lots.sum().reindex(BR.index).fillna(0) / BR.reduction_lots
    BR['median_dt_le15min_s'] = Lk[Lk.dt_s < 900].groupby('red_label').dt_s.median()
    BR.reset_index().rename(columns={'label': 'reduction_label'}).to_csv(os.path.join(RES, 'replacement_by_reduction_label.csv'), index=False)
    amb60 = float((Lk[Lk.cls.isin(REPLACE_CLASSES + (REENTRY_CLASS,))].competing_contracts_60s >= 2).mean())
    # ---- outputs -------------------------------------------------------------------------------------------------------------------------------------
    keep = [c for c in Lk.columns if c not in ('red_seq', 'sale_seq')]
    Lk[keep].to_csv(os.path.join(RES, 'replacement_event_links.csv'), index_label='link_id')
    cw = Lk.pivot_table(index='cls', columns='window', values='linked_lots', aggfunc='sum', fill_value=0).reindex(columns=[b[2] for b in BUCKETS], fill_value=0)
    cwr = Lk[Lk.red_label.str.startswith('8 clock-B')].pivot_table(index='cls', columns='window', values='linked_lots', aggfunc='sum', fill_value=0).reindex(columns=[b[2] for b in BUCKETS], fill_value=0)
    out = [cw.reset_index().assign(table='class x window (lots, all reductions)'),
           Lk[Lk.association_supported].pivot_table(index='cls', columns='window', values='linked_lots', aggfunc='sum', fill_value=0).reset_index().assign(table='class x window (lots, association-supported links only)'), cwr.reset_index().assign(table='class x window (lots, Clock-B rebalance reductions)'),
           Lk.pivot_table(index='red_label', columns='cls', values='linked_lots', aggfunc='sum', fill_value=0).reset_index().assign(table='reduction label x class (lots)'),
           (H.pivot_table(index='red_label', columns='window', values='wing_lots', aggfunc='sum', fill_value=0).reset_index().assign(table='hedge adjustments: reduction label x window (wing lots)') if len(H) else pd.DataFrame()),
           T.rename(columns={'event': 'from_state', 'nxt': 'to_state'}).assign(table='state transition (from -> to) per model / convention')]
    pd.concat(out, ignore_index=True).to_csv(os.path.join(RES, 'replacement_transition_matrix.csv'), index=False)
    LED.to_csv(os.path.join(RES, 'position_lifecycle_ledger.csv.gz'), index=False, compression='gzip')
    LED[(LED.model == 'C') & (LED.conv == 'cheap')].to_csv(os.path.join(RES, 'position_lifecycle_ledger.csv'), index=False)   # primary: model C, cheapest-first
    Pk = P.drop(columns=['new_lot_key', 'closed_lot_key'])
    unres = Lk[(Lk.cls == 'unresolved association') | Lk.ownership_ambiguous][keep].assign(reason=lambda x: np.where(x.cls == 'unresolved association', 'association > 15 min', 'competing antecedents on >= 2 contracts within 15 min'))
    cd = Pk[Pk.owner_convention_status == 'convention-dependent'].drop_duplicates('link_id')[['link_id']].assign(reason2='owner allocation differs across cheap / fifo / lifo')
    unres = unres.reset_index().rename(columns={'index': 'link_id'}).merge(cd, on='link_id', how='outer')
    unres.to_csv(os.path.join(RES, 'unresolved_position_links.csv'), index=False)
    M.to_csv(os.path.join(RES, 'state_transition_metrics.csv'), index=False); N.to_csv(os.path.join(RES, 'replacement_association_null.csv'), index=False)
    V.to_csv(os.path.join(RES, 'replacement_variant_stability.csv'), index=False); H.to_csv(os.path.join(RES, 'replacement_hedge_links.csv'), index=False)
    Pk.to_csv(os.path.join(RES, 'replacement_ownership_pairs.csv.gz'), index=False, compression='gzip')
    # ---- report --------------------------------------------------------------------------------------------------------------------------------------
    cws = Lk[Lk.association_supported].pivot_table(index='cls', columns='window', values='linked_lots', aggfunc='sum', fill_value=0)
    rep = ['LINK CLASSES x WINDOW (lots)', cw.to_string(), '', 'LINK CLASSES x WINDOW, only links whose (reduction group, window) shows excess over the null (lots)', cws.to_string(), '', 'CLOCK-B REBALANCE reductions: class x window (lots)', cwr.to_string(),
           '', 'median dt (s) by class', Lk.groupby('cls').dt_s.median().round(1).to_string(), '', 'Clock-B rebalance links: dt quantiles (s)',
           Lk[Lk.red_label.str.startswith('8 clock-B')].dt_s.describe(percentiles=[.1, .25, .5, .75, .9]).round(1).to_string(),
           '', 'unlinked sale lots by class', U.groupby('cls').lots.sum().to_string(), '', 'ASSOCIATION vs time-shifted null', N.round(3).to_string(index=False),
           '', 'VARIANT STABILITY (share of sale lots)', V.pivot_table(index='cls', columns='variant', values='share_of_sale_lots').round(3).to_string(),
           '', 'HEDGE ADJUSTMENTS (wing orders within 60 s after a same-right reduction)', (H.groupby(['window', 'wing_side']).wing_lots.sum().to_string() if len(H) else 'none'),
           '', 'OWNERSHIP (replacement / re-entry lot pairs)', (P[P.cls.isin(REPLACE_CLASSES + (REENTRY_CLASS,))].groupby('conv')[['A_continuation', 'B_continuation', 'ownership_ambiguous']].mean().round(3).to_string()),
           (P[P.cls.isin(REPLACE_CLASSES + (REENTRY_CLASS,))].drop_duplicates('link_id').owner_convention_status.value_counts(normalize=True).round(3).to_string()),
           '', 'share of replacement / re-entry links with competing antecedents on >= 2 contracts within 60 s (sensitivity of the 15-min ambiguity rule):', str(round(amb60, 3)),
           '', 'PER REDUCTION LABEL', BR.round(3).to_string(), '', 'STATE METRICS', M.round(3).T.to_string()]
    open(os.path.join(RES, 'replacement_report.txt'), 'w').write('\n'.join(rep) + '\n'); print('\n'.join(rep))
