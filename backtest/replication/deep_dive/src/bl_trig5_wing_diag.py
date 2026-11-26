"""POST-HOC diagnostic for reports/LATE_SALE_SEQUENCE.md (not pre-registered): for each close-long cluster of bl_trig5_sequence.py, long WING lots (overnight lump `v_` excluded) vs short lots on that right,
before and after the cluster, plus a baseline at random late-window times. Output outputs/trig5/wing_diag_excluding_lump.csv, wing_diag_summary.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT; T5 = f'{OUT}/trig5'; W0, W1 = 54900, 56400
tol = lambda s: max(1.0, 0.1 * s)
def lots(g, t, incl=False):
    x = g[(g.t_first <= t) if incl else (g.t_first < t)]; q = x.sg * x.lots; n2 = q.groupby(x.strike).sum(); S_ = float(-n2[n2 < 0].sum()); xl = x[x.module != 'v_']; Lw = float((xl.sg * xl.lots).groupby(xl.strike).sum().clip(lower=0).sum()); xv = x[x.module == 'v_']; Lv = float((xv.sg * xv.lots).groupby(xv.strike).sum().clip(lower=0).sum()); return S_, Lw, Lv
def run():
    O = DG.real_orders(); C = pd.read_csv(f'{T5}/clusters.csv'); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); rows = []; rng = np.random.default_rng(7); base = []; G = {}
    for r in C.itertuples():
        u, d1 = r.cyc.split('|'); ex = Tc[(Tc.und == u) & (Tc.d1 == d1)].expiry.iloc[0]; g = O[(O.und == u) & (O.expiry == ex) & (O.dayno == 0) & (O.cp == r.cp)].sort_values(['t_first', 'row']); G[(r.cyc, r.cp)] = g
        S0, Lw0, Lv0 = lots(g, r.t0); S1, Lw1, _ = lots(g, r.t1, True); rows.append(dict(cyc=r.cyc, cp=r.cp, post=r.post, S_before=S0, Lwing_before=Lw0, Llump_before=Lv0, S_after=S1, Lwing_after=Lw1, closed=r.lots_closed, wing_excess_before=Lw0 > S0 + tol(S0), balanced_after=abs(Lw1 - S1) <= tol(S1)))
    for (cyc, cp), g in G.items():
        for t in rng.uniform(W0, W1, 400): s, l, _ = lots(g, t); base.append(l - s)
    D = pd.DataFrame(rows); D.to_csv(f'{T5}/wing_diag_excluding_lump.csv', index=False); b = np.array(base); before = (D.Lwing_before - D.S_before).values; after = (D.Lwing_after - D.S_after).values
    out = dict(clusters_all=len(D), clusters_post=int(D.post.sum()), wing_minus_short_before=before.tolist(), wing_minus_short_after=after.tolist(), after_exact_equal=int((after == 0).sum()), before_positive=int((before > 0).sum()), random_times_wing_minus_short_ge_1=float((b >= 1).mean()), random_times_exact_equal=float((b == 0).mean()), random_times_n=int(len(b)))
    json.dump(out, open(f'{T5}/wing_diag_summary.json', 'w'), indent=1); print(json.dumps(out))
if __name__ == '__main__': run()
