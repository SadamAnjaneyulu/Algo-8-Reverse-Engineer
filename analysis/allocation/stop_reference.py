"""Phase 2 - the exact per-lot stop reference and constant.  PRE-REGISTERED BEFORE RUNNING (see ALLOCATION_FINDINGS.md section 8).

Question: does ONE reference-price formula and ONE stop constant k explain the actual stop-like buy-backs?
Simulated rule (per unit u of a reference R): the unit is 'crossed' in minute m when the Breeze minute HIGH >= k x ref_R(u, m), where the reference is built
only from lots that are OPEN at the start of m (entered in an earlier minute, not yet closed under the ownership convention): lots already closed at the trigger
are excluded.  An EVENT is a rising edge of that condition.  First crossing = the first edge of the unit on a given day; later edges are repeated crossings.
Units:  own entry (one per lot) | cheapest open entry (per contract) | slot-allocation average, chain-allocation average (per allocation x contract) |
        lot-weighted contract average | order-average (mean of the entry ORDERS' prices; each order once).
Matching: ONE actual buy-back order <-> at most ONE event, and each event is used at most once (greedy in time order).  A buy-back b matches event e when
        same contract, minute(e) <= minute(b) <= minute(e) + W, and (quote-confirmed) the algo's OWN recovered decision quote L_b >= k x ref_e.
        L_b = limit / 1.15 for buys: the algo's LTP when it placed the order (this is the 'recovered per-order quote').
        Crossing timestamps are bounded to the minute (Breeze bars carry no intraminute time; body orders are stamped to the minute); they are NOT exact.
Responder pools:  S = buy-backs labelled '1 individual lot stop-loss' (the label uses cheapest-entry >= 1.45x, so it is circular for that reference);
                  U = every closing short buy-back that is not scheduled / clock (label-free sensitivity).
Metrics per (convention, R, k, pool, segment, split):  precision = matched events / events;  recall = matched buy-backs / pool buy-backs;
        false triggers = events - matched;  missed exits = buy-backs - matched;  stop-consistent coverage = share of pool buy-backs whose OWN quote satisfies
        L_b >= k x (lowest reference among the contract's units) -- independent of event matching.  First and repeated crossings are reported separately.
Segments (state of the contract's open lots at the minute): D-1 fresh | D0 fresh (no carried lot open) | D0 carried (all open lots carried) | D0 mixed.
k grid 1.40 ... 2.00 step 0.05 (brackets the observed 1.55-1.70).  k is chosen on DEV ONLY; VAL and TEST are never used for selection.
Conventions: cheap / fifo / lifo (which lot a buy-back closes is unobservable).
python3 analysis/allocation/stop_reference.py -> results/stop_ref_counts.csv.gz (per cycle), results/stop_ref_exit_ratio_quantiles.csv"""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE)
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine')); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from scipy import sparse
from common import orders, markets, minute_index, split_of, C
from alloc import build_allocations, lot_ledger, RES

NONSTOP = ('5 cycle stop & liquidation', '7 expiry-day salvage', '6 clock-based exit (final flatten)', '10 manual / platform risk engine',
           '8 clock-B rebalance', '6 clock-based exit (clock B, no replacement)', '8b grid rebalance (A/:00 clock)')
STOP = '1 individual lot stop-loss'
REFS = ['own entry (per lot)', 'cheapest open entry', 'slot-allocation average', 'chain-allocation average', 'lot-weighted contract average', 'order-average contract']
KS = [round(x, 2) for x in np.arange(1.40, 2.0001, 0.05)]
VARIANTS = [('W2 quote-confirmed', 2, True), ('W5 quote-confirmed', 5, True), ('W2 association only', 2, False)]
SEGN = {0: 'D-1 fresh', 1: 'D0 fresh', 2: 'D0 carried', 3: 'D0 mixed', 9: 'other'}

def build_refs(arr, nk, n):
    """arr: dict of lot arrays.  Returns (Op, SEG, {ref: (T[unit, minute], unit_contract)})."""
    M = np.arange(n); Op = (arr['mi0'][:, None] < M[None, :]) & (arr['mi1'][:, None] >= M[None, :]); nl = len(arr['px']); px = arr['px']
    Opf = Op.astype(np.float32); Z = sparse.csr_matrix((np.ones(nl), (arr['ki'], np.arange(nl))), shape=(nk, nl))
    opn = Z @ Opf; carr = Z @ (Op & arr['carried'][:, None]).astype(np.float32)
    day = arr['day']; SEG = np.full((nk, n), 9, np.int8)
    d1 = (day[None, :] == 0) & (opn > 0); SEG[d1] = 0
    d0 = (day[None, :] == 1) & (opn > 0)
    SEG[d0 & (carr == 0)] = 1; SEG[d0 & (carr == opn)] = 2; SEG[d0 & (carr > 0) & (carr < opn)] = 3
    out = {}
    out[REFS[0]] = (np.where(Op, px[:, None], np.nan).astype(np.float32), arr['ki'])
    cheap = np.full((nk, n), np.nan, np.float32)
    for kk in np.unique(arr['ki']):
        idx = np.where(arr['ki'] == kk)[0]; v = np.where(Op[idx], px[idx, None], np.inf).min(0); cheap[kk] = np.where(np.isfinite(v), v, np.nan)
    out[REFS[1]] = (cheap, np.arange(nk))
    for name, code in ((REFS[2], arr['slot']), (REFS[3], arr['chain'])):
        pair = code.astype(np.int64) * nk + arr['ki']; uq, inv = np.unique(pair, return_inverse=True); nu = len(uq)
        Zu = sparse.csr_matrix((np.ones(nl), (inv, np.arange(nl))), shape=(nu, nl)); cnt = Zu @ Opf; s = Zu @ (Opf * px[:, None].astype(np.float32))
        T = np.where(cnt > 0, s / np.maximum(cnt, 1), np.nan).astype(np.float32); uc = np.zeros(nu, int); uc[inv] = arr['ki']; out[name] = (T, uc)
    with np.errstate(invalid='ignore', divide='ignore'):
        out[REFS[4]] = (np.where(opn > 0, (Z @ (Opf * px[:, None].astype(np.float32))) / opn, np.nan).astype(np.float32), np.arange(nk))
        # order-average: each entry ORDER counts once while any of its lots is open
        oc = arr['ocode']; order = np.argsort(oc, kind='stable'); starts = np.r_[0, np.where(np.diff(oc[order]) != 0)[0] + 1]
        OpO = np.maximum.reduceat(Op[order].astype(np.float32), starts, axis=0); first = order[starts]; no = len(starts)
        Zo = sparse.csr_matrix((np.ones(no), (arr['ki'][first], np.arange(no))), shape=(nk, no)); cntO = Zo @ OpO
        out[REFS[5]] = (np.where(cntO > 0, (Zo @ (OpO * px[first, None].astype(np.float32))) / cntO, np.nan).astype(np.float32), np.arange(nk))
    return Op, SEG, out

def match(ev_c, ev_m, ev_ref, bb_c, bb_m, bb_L, bb_t, W, k, qc):
    """greedy one-to-one matching; returns (event matched mask, buy-back matched mask)."""
    me = np.zeros(len(ev_c), bool); mb = np.zeros(len(bb_c), bool)
    if len(ev_c) == 0 or len(bb_c) == 0: return me, mb
    order = np.lexsort((ev_m, ev_c)); by = {}
    for i in order: by.setdefault(ev_c[i], []).append(i)
    for j in np.lexsort((bb_t, bb_m)):
        lst = by.get(bb_c[j])
        if not lst: continue
        for i in lst:
            if me[i]: continue
            if ev_m[i] > bb_m[j]: break
            if bb_m[j] - ev_m[i] > W: continue
            if qc and bb_L[j] < k * ev_ref[i]: continue
            me[i] = True; mb[j] = True; break
    return me, mb

def run(conv, o, mk, A):
    L = lot_ledger(conv, A); rows, qrows = [], []
    bbs = o[(o.closing_short == True) & (o.side == 'Buy')].copy()
    for key, m in mk.items():
        u, e = key; s = L[(L.und == u) & (L.expiry == e) & (L.sgn < 0) & (L.role == 'short')].copy(); nk = len(m['keys']); n = len(m['grid'])
        s['ki'] = [m['k2i'].get((c, k), -1) for c, k in zip(s.cp, s.strike)]; s = s[s.ki >= 0]
        if s.empty: continue
        arr = dict(mi0=s.entry_mi.values, mi1=s.exit_mi.values, px=s.entry_px.values.astype(float), ki=s.ki.values, carried=s.carried.values.astype(bool), day=m['day'],
                   slot=pd.factorize(s.alloc_slot)[0], chain=pd.factorize(s.alloc_chain)[0], ocode=pd.factorize(s.entry_oid)[0])
        Op, SEG, refs = build_refs(arr, nk, n); H = m['H']; day = m['day']; sp = split_of(e)
        b = bbs[(bbs.und == u) & (bbs.expiry == e)]
        bc = np.array([m['k2i'].get((c, k), -1) for c, k in zip(b.cp, b.strike)]); ok = bc >= 0; b = b[ok]; bc = bc[ok]
        bm = np.array([minute_index(m['grid'], t) for t in b.t_dec_lo]); bL = b.L.values.astype(float); bt = (pd.to_datetime(b.t_dec) - pd.Timestamp('2026-01-01')).dt.total_seconds().values
        bseg = SEG[bc, bm].astype(int); pools = {'S': (b.label == STOP).values, 'U': (~b.label.isin(NONSTOP)).values}
        for rname, (T, uc) in refs.items():
            Hu = H[uc]; ubc = {}
            for ui, c_ in enumerate(uc): ubc.setdefault(c_, []).append(ui)
            # exit-level: lowest reference among the contract's units at the decision minute, and the ratio L_b / that reference
            refmin = np.full(len(b), np.nan)
            for j in range(len(b)):
                us = ubc.get(bc[j]);
                if us is not None:
                    v = T[us, bm[j]]; refmin[j] = np.nanmin(v) if np.isfinite(v).any() else np.nan
            for pn, pm in pools.items():
                for j in np.where(pm)[0]: qrows.append((conv, rname, pn, sp, key[0], str(e)[:10], SEG[bc[j], bm[j]], bL[j] / refmin[j] if refmin[j] > 0 else np.nan))
            for k in KS:
                cond = Hu >= k * T; prev = np.zeros_like(cond); prev[:, 1:] = cond[:, :-1]; ui, mi = np.nonzero(cond & ~prev)
                if len(ui):
                    d = day[mi]; first = np.r_[True, (ui[1:] != ui[:-1]) | (d[1:] != d[:-1])]
                    ec = uc[ui]; er = T[ui, mi]; eseg = SEG[ec, mi].astype(int)
                else: first = np.zeros(0, bool); ec = er = mi = np.zeros(0); eseg = np.zeros(0, int)
                covered = np.isfinite(refmin) & (bL >= k * refmin)
                for pn, pm in pools.items():
                    for vn, W, qc in VARIANTS:
                        me, mb = match(ec, mi, er, bc[pm], bm[pm], bL[pm], bt[pm], W, k, qc)
                        bs = bseg[pm]
                        for sg in np.unique(np.r_[eseg, bs]) if (len(eseg) or len(bs)) else []:
                            em = eseg == sg; bmk = bs == sg
                            rows.append((conv, rname, k, pn, vn, key[0], str(e)[:10], sp, SEGN[int(sg)], int((em & first).sum()), int((em & ~first).sum()), int((em & first & me).sum()),
                                         int((em & ~first & me).sum()), int(bmk.sum()), int((bmk & mb).sum()), int((bmk & covered[pm]).sum())))
    return rows, qrows

if __name__ == '__main__':
    o = orders(); mk = markets(); A = build_allocations(o); allrows, allq = [], []
    for conv in (sys.argv[1:] or ['cheap', 'fifo', 'lifo']):
        t0 = time.time(); r, q = run(conv, o, mk, A); allrows += r; allq += q; print(conv, 'done', round(time.time() - t0), 's', len(r), flush=True)
        cols = ['conv', 'ref', 'k', 'pool', 'variant', 'und', 'expiry', 'split', 'segment', 'ev_first', 'ev_repeat', 'tp_first', 'tp_repeat', 'buybacks', 'matched_buybacks', 'covered_buybacks']
        D = pd.DataFrame(allrows, columns=cols); D.to_csv(os.path.join(RES, 'stop_ref_counts.csv.gz'), index=False, compression='gzip')
        Q = pd.DataFrame(allq, columns=['conv', 'ref', 'pool', 'split', 'und', 'expiry', 'seg', 'ratio']); Q['segment'] = Q.seg.map(SEGN)
        Q.to_pickle(os.path.join(C, 'stop_ref_exit_ratios.pkl'))
        qq = Q.dropna(subset=['ratio']).groupby(['conv', 'ref', 'pool', 'segment', 'split']).ratio.describe(percentiles=[.05, .25, .5, .75, .95]).reset_index()
        qq.to_csv(os.path.join(RES, 'stop_ref_exit_ratio_quantiles.csv'), index=False)
