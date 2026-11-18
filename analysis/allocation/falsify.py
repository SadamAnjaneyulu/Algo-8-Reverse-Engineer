"""Falsification tests for allocation-level hypotheses (no model fitting; thresholds, where used, are chosen on DEV and applied to VAL / TEST).
Question: is the book managed as ONE aggregated position, or as independent allocations (each with its own entry, size, hedge and exit)?
Allocation ids are not in the data, so every allocation definition in alloc.py (slot / chain / lot) is a hypothesis, and the owner of a closed lot is a
convention (cheap / fifo / lifo).  Results are reported per definition and per convention; nothing is combined.

T1  closure granularity : a stop buy-back closes n lots.  If a stop were sized to a whole allocation, n would equal the remaining size of some allocation
                          holding the contract.  Report P(n < smallest remaining allocation) per definition (n < every candidate => NOT an allocation-sized stop).
T2  contract choice     : at each stop buy-back, rank the open short contracts of the cycle by (previous-minute close) / reference.  Hit@1 / hit@3 / mean rank of the
                          contract actually bought, per reference, against the random baseline 1 / (number of candidates).
T3  reference sharpness : D-1 / D0 contract-minute panel; score = previous close / reference; label = a stop buy-back of that contract in that minute.
                          AP of the raw ratio (no fitting) and F1 at the DEV-best threshold applied to VAL / TEST.
T4  wing coupling       : released wings ('L-hedge release') vs the shorts closed within 60 s: share whose entry allocation equals a closed short's allocation,
                          against 1,000 within-cycle permutations of the wing allocation labels.
python3 analysis/allocation/falsify.py -> results/allocation_T1..T4_*.csv + allocation_falsification_report.txt"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE)
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine')); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from sklearn.metrics import average_precision_score
from common import orders, markets, minute_index, split_of
from alloc import build_allocations, lot_ledger, RES

STOP = '1 individual lot stop-loss'
REFS = ['lot_min (cheapest open lot)', 'contract_wavg (aggregate)', 'slot_min (min of slot-allocation avg entry)', 'chain_min (min of chain-allocation avg entry)',
        'lot_newest', 'lot_max (negative control)']

def _codes(x):
    return pd.factorize(x)[0]

def cycle_arrays(L, mk, key):
    """short lots of one cycle as arrays (entry/exit in ns, minute indexes, contract index, allocation codes)."""
    u, e = key; s = L[(L.und == u) & (L.expiry == e) & (L.sgn < 0) & (L.role == 'short')].copy(); m = mk[key]
    s['ki'] = [m['k2i'].get((c, k), -1) for c, k in zip(s.cp, s.strike)]; s = s[s.ki >= 0]
    return dict(t0=s.entry_t.values.astype('datetime64[ns]').astype('int64'), t1=s.exit_t.fillna(pd.Timestamp.max).values.astype('datetime64[ns]').astype('int64'),
                mi0=s.entry_mi.values, mi1=s.exit_mi.values, ki=s.ki.values, px=s.entry_px.values.astype(float), slot=_codes(s.alloc_slot), chain=_codes(s.alloc_chain),
                alloc_slot=s.alloc_slot.values, alloc_chain=s.alloc_chain.values, exit_oid=s.exit_oid.values, entry_oid=s.entry_oid.values, exit_label=s.exit_label.values,
                nk=len(m['keys']))

def refs_at(arr, mask, prev_close):
    """reference prices per contract index for the open lot subset `mask`; returns dict ref -> array(nk) (nan where no open lot)."""
    nk = arr['nk']; out = {r: np.full(nk, np.nan) for r in REFS}
    ki = arr['ki'][mask]
    if ki.size == 0: return out
    px = arr['px'][mask]
    mn = np.full(nk, np.inf); np.minimum.at(mn, ki, px); mx = np.full(nk, -np.inf); np.maximum.at(mx, ki, px)
    sm = np.bincount(ki, px, nk); n = np.bincount(ki, minlength=nk)
    t0 = arr['t0'][mask]; newest = np.full(nk, np.nan)
    order = np.argsort(t0, kind='stable'); newest[ki[order]] = px[order]
    has = n > 0
    out['lot_min (cheapest open lot)'][has] = mn[has]; out['lot_max (negative control)'][has] = mx[has]; out['contract_wavg (aggregate)'][has] = sm[has] / n[has]
    out['lot_newest'][has] = newest[has]
    for name, code in (('slot_min (min of slot-allocation avg entry)', arr['slot'][mask]), ('chain_min (min of chain-allocation avg entry)', arr['chain'][mask])):
        pair = ki.astype(np.int64) * (code.max() + 2) + code; uq, inv = np.unique(pair, return_inverse=True)
        a_sum = np.bincount(inv, px); a_n = np.bincount(inv); a_avg = a_sum / a_n; a_k = uq // (code.max() + 2)
        r = np.full(nk, np.inf); np.minimum.at(r, a_k, a_avg); out[name][has] = r[has]
    return out

def t1_t2(o, L, mk, conv):
    st = o[(o.label == STOP) & (o.closing_short)].copy(); rows1, rows2 = [], []
    for key, g in st.groupby([st.und, st.expiry]):
        key = (key[0], key[1])
        if key not in mk: continue
        m = mk[key]; arr = cycle_arrays(L, mk, key)
        for r in g.itertuples():
            tn = pd.Timestamp(r.t_dec).to_datetime64().astype('datetime64[ns]').astype('int64'); mi = minute_index(m['grid'], r.t_dec_lo)
            if mi < 1: continue
            open_ = (arr['t0'] < tn) & (arr['t1'] >= tn)
            ki_b = m['k2i'].get((r.cp, r.strike), -1)
            if ki_b < 0 or not ((arr['ki'] == ki_b) & open_).any(): continue
            inb = open_ & (arr['ki'] == ki_b); n_closed = int(r.lots)
            # T1: remaining allocation sizes in the bought contract just before the order
            for d in ('slot', 'chain'):
                sizes = pd.Series(arr['alloc_' + d][inb]).value_counts().values
                rows1.append(dict(conv=conv, defn=d, day='D-1' if r.dte >= 1 else 'D0', split=r.split, n_closed=n_closed, n_open_contract=int(inb.sum()), n_alloc=len(sizes),
                                  min_size=int(sizes.min()), max_size=int(sizes.max()), n_lt_min=n_closed < sizes.min(), n_eq_some=bool((sizes == n_closed).any()),
                                  n_ge_all=n_closed >= sizes.max()))
            pc = m['Cf'][:, mi - 1].astype(float); R = refs_at(arr, open_, pc)
            cand = np.where(np.isfinite(R['lot_min (cheapest open lot)']) & np.isfinite(pc) & (pc > 0))[0]
            if len(cand) < 2 or ki_b not in cand: continue
            for ref in REFS:
                rt = pc[cand] / R[ref][cand]; rb = pc[ki_b] / R[ref][ki_b]
                rank = 1 + int((rt > rb).sum()); ties = int((rt == rb).sum()) - 1
                rows2.append(dict(conv=conv, oid=r.oid, cyc=f'{key[0]}|{key[1]}', ref=ref, day='D-1' if r.dte >= 1 else 'D0', split=r.split, n_cand=len(cand), rank=rank + ties / 2, hit1=(rank == 1) and ties == 0,
                                  hit3=rank + ties <= 3, rand1=1 / len(cand), ratio_bought=rb))
    return pd.DataFrame(rows1), pd.DataFrame(rows2)

def t3_panel(o, L, mk, conv):
    st = o[(o.label == STOP) & (o.closing_short)]
    stm = {(r.und, r.expiry, r.cp, r.strike, minute_index(mk[(r.und, r.expiry)]['grid'], r.t_dec_lo)) for r in st.itertuples() if (r.und, r.expiry) in mk}
    rows = []
    for key, m in mk.items():
        arr = cycle_arrays(L, mk, key); n = len(m['grid']); inv = {v: k for k, v in m['k2i'].items()}
        for mi in range(1, n):
            op = (arr['mi0'] < mi) & (arr['mi1'] >= mi)           # lots entered before this minute and not yet closed at its start
            if not op.any(): continue
            pc = m['Cf'][:, mi - 1].astype(float); R = refs_at(arr, op, pc)
            cand = np.where(np.isfinite(R[REFS[0]]) & np.isfinite(pc) & (pc > 0))[0]
            for kk in cand:
                cp, strike = inv[kk]
                rec = dict(split=split_of(key[1]), day=int(m['day'][mi]), y=(key[0], key[1], cp, strike, mi) in stm, cyc=f'{key[0]}|{key[1]}')
                for ref in REFS: rec[ref] = pc[kk] / R[ref][kk]
                rows.append(rec)
    return pd.DataFrame(rows)

def t3_metrics(P, conv):
    out = []
    for day in (0, 1):
        D = P[P.day == day]
        for ref in REFS:
            dv = D[D.split == 'DEV']; ths = np.arange(1.05, 3.01, 0.05); best = (0, 1.5)
            for th in ths:
                p = dv[ref] >= th; tp = (p & dv.y).sum(); f = 2 * tp / max(p.sum() + dv.y.sum(), 1)
                if f > best[0]: best = (f, th)
            for sp in ('DEV', 'VAL', 'TEST'):
                X = D[D.split == sp]
                if X.y.sum() == 0: continue
                p = X[ref] >= best[1]; tp = int((p & X.y).sum())
                out.append(dict(conv=conv, day='D-1' if day == 0 else 'D0', ref=ref, split=sp, n_rows=len(X), n_events=int(X.y.sum()), AP=average_precision_score(X.y, X[ref].fillna(0)),
                                dev_threshold=round(best[1], 2), precision=tp / max(int(p.sum()), 1), recall=tp / int(X.y.sum())))
    return pd.DataFrame(out)

def t4(L, defn, conv, nperm=1000, seed=0):
    col = 'alloc_' + defn; rng = np.random.default_rng(seed)
    w = L[(L.sgn > 0) & (L.role == 'wing') & L.exit_label.fillna('').str.startswith('L-hedge release') & (L[col] != 'unlinked')].copy()
    s = L[(L.sgn < 0) & (L.role == 'short') & L.exit_t.notna()]
    hits, rows = [], []
    for (u, e), g in w.groupby(['und', 'expiry']):
        ss = s[(s.und == u) & (s.expiry == e)]
        for r in g.itertuples():
            c = ss[(ss.cp == r.cp) & ((ss.exit_t - r.exit_t).abs() <= pd.Timedelta(seconds=60))]
            if len(c): rows.append((u, e, r.cp, pd.Timestamp(r.exit_t).normalize(), r[w.columns.get_loc(col) + 1], set(c[col])))
    if not rows: return dict(conv=conv, defn=defn, n=0)
    obs = np.mean([a in cs for _, _, _, _, a, cs in rows])
    df = pd.DataFrame(rows, columns=['u', 'e', 'cp', 'd', 'a', 'cs']); nulls = []
    for _ in range(nperm):
        h = []
        for _, g in df.groupby(['u', 'e', 'cp', 'd']):   # permute within (cycle, right, release date): preserves the right and the day
            a = rng.permutation(g.a.values); h += [x in cs for x, cs in zip(a, g.cs)]
        nulls.append(np.mean(h))
    nulls = np.array(nulls)
    return dict(conv=conv, defn=defn, n=len(df), observed=obs, null_mean=nulls.mean(), null_p95=np.percentile(nulls, 95), p_value=float((nulls >= obs).mean()))

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); pd.set_option('display.max_rows', 200)
    o = orders(); mk = markets(); A = build_allocations(o); r1s, r2s, r3s, r4s = [], [], [], []
    for conv in ('cheap', 'fifo', 'lifo'):
        L = lot_ledger(conv, A); a, b = t1_t2(o, L, mk, conv); r1s.append(a); r2s.append(b)
        r4s += [t4(L, d, conv) for d in ('slot', 'chain')]
        print('done', conv, len(a), len(b), flush=True)
        if conv == 'cheap':
            P = t3_panel(o, L, mk, conv); r3s.append(t3_metrics(P, conv)); P.to_pickle(os.path.join(RES, '..', '..', '_cache', 'alloc_t3_panel.pkl'))
    T1 = pd.concat(r1s); T2 = pd.concat(r2s); T3 = pd.concat(r3s); T4 = pd.DataFrame(r4s)
    g1 = T1.groupby(['conv', 'defn', 'day']).agg(stop_orders=('n_closed', 'size'), mean_n_closed=('n_closed', 'mean'), mean_alloc_in_contract=('n_alloc', 'mean'),
                                                 mean_min_alloc_size=('min_size', 'mean'), p_closed_lt_every_alloc=('n_lt_min', 'mean'), p_closed_eq_some_alloc=('n_eq_some', 'mean'),
                                                 p_closed_ge_largest=('n_ge_all', 'mean')).reset_index()
    g2 = T2.groupby(['conv', 'day', 'ref']).agg(n=('hit1', 'size'), hit1=('hit1', 'mean'), hit3=('hit3', 'mean'), mean_rank=('rank', 'mean'), random_hit1=('rand1', 'mean')).reset_index()
    piv = T2.pivot_table(index=['conv', 'day', 'cyc', 'oid'], columns='ref', values='hit1', aggfunc='first').reset_index(); rng = np.random.default_rng(0); bs = []
    for (conv, day), g in piv.groupby(['conv', 'day']):
        cycs = g.cyc.unique(); idx = {c: g[g.cyc == c] for c in cycs}
        for ref in REFS[1:]:
            d = (g[REFS[0]].astype(float) - g[ref].astype(float)); boot = []
            for _ in range(1000):
                pick = rng.integers(0, len(cycs), len(cycs)); x = pd.concat([idx[cycs[j]] for j in pick]); boot.append((x[REFS[0]].astype(float) - x[ref].astype(float)).mean())
            bs.append(dict(conv=conv, day=day, ref=ref, n=len(g), hit1_lot_min_minus_ref=d.mean(), ci90_lo=np.percentile(boot, 5), ci90_hi=np.percentile(boot, 95)))
    BS = pd.DataFrame(bs); BS.to_csv(os.path.join(RES, 'allocation_T2_paired_bootstrap.csv'), index=False)
    g2s = T2.groupby(['conv', 'day', 'split', 'ref']).agg(n=('hit1', 'size'), hit1=('hit1', 'mean'), random_hit1=('rand1', 'mean')).reset_index()
    g1.to_csv(os.path.join(RES, 'allocation_T1_closure_granularity.csv'), index=False); g2.to_csv(os.path.join(RES, 'allocation_T2_contract_choice.csv'), index=False)
    g2s.to_csv(os.path.join(RES, 'allocation_T2_contract_choice_by_split.csv'), index=False)
    T3.to_csv(os.path.join(RES, 'allocation_T3_reference_sharpness.csv'), index=False); T4.to_csv(os.path.join(RES, 'allocation_T4_wing_coupling.csv'), index=False)
    rep = ['T1 closure granularity', g1.round(3).to_string(index=False), '', 'T2 contract choice', g2.round(3).to_string(index=False), '', 'T2 paired difference in hit@1: lot_min minus reference (90% cycle-bootstrap CI)', BS.round(3).to_string(index=False), '', 'T3 reference sharpness',
           T3.round(3).to_string(index=False), '', 'T4 wing coupling', T4.round(3).to_string(index=False)]
    open(os.path.join(RES, 'allocation_falsification_report.txt'), 'w').write('\n'.join(rep) + '\n'); print('\n'.join(rep))
