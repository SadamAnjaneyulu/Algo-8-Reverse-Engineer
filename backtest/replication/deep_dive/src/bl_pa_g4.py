"""Phase A G4 (plan: reports/PHASE_A_G1_G6_PLAN.md): body-module (`num`) long closes on D-1 in all cycles: are they closes of OPENING-WING contracts (num open_long in the first minute of the session), are they within 10 s of a buy-back or within 60 s of a short sale,
and do the two sell-to-close exceptions (NIFTY 3 Aug 15:29:05-07, SENSEX 9 Sep 15:23 and 15:29) belong to that class? Output outputs/phaseA/g4.json, g4_orders.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT; PA = f'{OUT}/phaseA'; T_OPEN = 9 * 3600 + 17 * 60
def run():
    O = DG.real_orders(); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; rows = []
    for r in Tc.itertuples():
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_first', 'row'])
        if not len(g): continue
        num = g[g.module == 'num']; ow = set(zip(num[(num.role == 'open_long') & (num.t_first <= T_OPEN)].cp, num[(num.role == 'open_long') & (num.t_first <= T_OPEN)].strike)); cov = g[g.role == 'cover_short'].t_first.values; sh = g[g.role == 'open_short'].t_first.values
        for q in num[num.role == 'close_long'].itertuples():
            ent = num[(num.role == 'open_long') & (num.cp == q.cp) & (num.strike == q.strike) & (num.t_first < q.t_first)]; entry = float((ent.lots * ent.px_avg).sum() / ent.lots.sum()) if len(ent) else np.nan
            rows.append(dict(cyc=f'{r.und}|{r.d1}', t=float(q.t_first), hms=f'{int(q.t_first) // 3600:02d}:{int(q.t_first) % 3600 // 60:02d}:{int(q.t_first) % 60:02d}', cp=q.cp, strike=float(q.strike), lots=int(q.lots), px=float(q.px_avg), entry=entry, ratio=float(q.px_avg / entry) if entry == entry and entry > 0 else np.nan,
                             opening_wing=bool((q.cp, q.strike) in ow), cover_10s=bool((np.abs(cov - q.t_first) <= 10).any()) if len(cov) else False, short_60s=bool((np.abs(sh - q.t_first) <= 60).any()) if len(sh) else False, minute_from_open=int(q.t_first // 60 - 555)))
    D = pd.DataFrame(rows); D['cls'] = D.opening_wing & (D.cover_10s | D.short_60s); D.to_csv(f'{PA}/g4_orders.csv', index=False); res = {}
    res['orders'] = int(len(D)); res['cycles'] = int(D.cyc.nunique()); res['opening_wing_share'] = float(D.opening_wing.mean()); res['cover_10s_share'] = float(D.cover_10s.mean()); res['class_share'] = float(D.cls.mean()); res['median_exit_over_entry'] = float(D.ratio.median())
    late = D[D.minute_from_open >= 330]; res['last_30_min_orders'] = int(len(late)); res['last_30_min_in_class'] = int(late.cls.sum()); res['last_30_min_cycles'] = int(late.cyc.nunique())
    ex = D[((D.cyc == 'NIFTY|2026-08-03') & D.hms.str.startswith('15:29')) | ((D.cyc == 'SENSEX|2026-09-09') & (D.hms.str.startswith('15:23') | D.hms.str.startswith('15:29')) & (D.cp == 'PE') & (D.strike == 71100))]
    res['exceptions'] = ex[['cyc', 'hms', 'cp', 'strike', 'lots', 'px', 'entry', 'ratio', 'opening_wing', 'cover_10s', 'short_60s', 'cls']].round(2).to_dict('records'); res['exceptions_in_class'] = int(ex.cls.sum()); res['exceptions_n'] = int(len(ex)); res['success'] = bool(len(ex) > 0 and ex.cls.all())
    hist = D.minute_from_open.map(lambda m: f'{(555 + m) // 60:02d}h').value_counts().sort_index().to_dict(); res['by_hour'] = hist
    json.dump(res, open(f'{PA}/g4.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3)))
if __name__ == '__main__': run()
