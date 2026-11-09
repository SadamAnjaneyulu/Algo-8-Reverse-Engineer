"""Timestamp resolution of the simulated crossings (requirement: 'exact first-crossing timestamp').  Breeze bars are 1-minute and body orders are stamped to the minute, so a
crossing can only be BRACKETED to its minute.  This reports, for matched (event, buy-back) pairs of the quote-confirmed W5 variant, how many minutes after the crossing minute the
buy-back's order minute falls, and the buy-back's own quote relative to the entry price.  Own entry and cheapest open entry, k = 1.55 and 1.65.
python3 analysis/allocation/stop_lag.py -> results/stop_lag.csv"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE)
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine')); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import stop_reference as sr
from common import orders, markets, minute_index
from alloc import build_allocations, lot_ledger, RES

if __name__ == '__main__':
    o = orders(); mk = markets(); A = build_allocations(o); L = lot_ledger('cheap', A); bbs = o[(o.closing_short == True) & (o.side == 'Buy') & (o.label == sr.STOP)]; rows = []
    for key, m in mk.items():
        u, e = key; s = L[(L.und == u) & (L.expiry == e) & (L.sgn < 0) & (L.role == 'short')].copy(); nk = len(m['keys']); n = len(m['grid'])
        s['ki'] = [m['k2i'].get((c, k), -1) for c, k in zip(s.cp, s.strike)]; s = s[s.ki >= 0]
        if s.empty: continue
        arr = dict(mi0=s.entry_mi.values, mi1=s.exit_mi.values, px=s.entry_px.values.astype(float), ki=s.ki.values, carried=s.carried.values.astype(bool), day=m['day'],
                   slot=pd.factorize(s.alloc_slot)[0], chain=pd.factorize(s.alloc_chain)[0], ocode=pd.factorize(s.entry_oid)[0])
        Op, SEG, refs = sr.build_refs(arr, nk, n); b = bbs[(bbs.und == u) & (bbs.expiry == e)]
        bc = np.array([m['k2i'].get((c, k), -1) for c, k in zip(b.cp, b.strike)]); ok = bc >= 0; b = b[ok]; bc = bc[ok]
        bm = np.array([minute_index(m['grid'], t) for t in b.t_dec_lo]); bL = b.L.values.astype(float); bt = (pd.to_datetime(b.t_dec) - pd.Timestamp('2026-01-01')).dt.total_seconds().values
        for rname in (sr.REFS[0], sr.REFS[1]):
            T, uc = refs[rname]; Hu = m['H'][uc]
            for k in (1.55, 1.65):
                cond = Hu >= k * T; prev = np.zeros_like(cond); prev[:, 1:] = cond[:, :-1]; ui, mi = np.nonzero(cond & ~prev)
                ec = uc[ui]; er = T[ui, mi]; me, mb = sr.match(ec, mi, er, bc, bm, bL, bt, 5, k, True)
                # lag of each matched pair: replicate the greedy rule to recover the partner
                used = np.zeros(len(ec), bool); order = np.lexsort((mi, ec)); by = {}
                for i in order: by.setdefault(ec[i], []).append(i)
                for j in np.lexsort((bt, bm)):
                    for i in by.get(bc[j], []):
                        if used[i]: continue
                        if mi[i] > bm[j]: break
                        if bm[j] - mi[i] > 5 or bL[j] < k * er[i]: continue
                        used[i] = True; rows.append((rname, k, bm[j] - mi[i], bL[j] / er[i])); break
    D = pd.DataFrame(rows, columns=['ref', 'k', 'lag_minutes', 'quote_over_threshold'])
    D['ratio'] = D.quote_over_threshold * D.k; S = D.groupby(['ref', 'k']).agg(pairs=('lag_minutes', 'size'), same_minute=('lag_minutes', lambda x: (x == 0).mean()), next_minute=('lag_minutes', lambda x: (x == 1).mean()),
                                                                           two_to_five=('lag_minutes', lambda x: (x >= 2).mean()), median_quote_over_entry=('ratio', 'median')).reset_index()
    S.to_csv(os.path.join(RES, 'stop_lag.csv'), index=False); print(S.round(3).to_string(index=False))
