"""Mismatch profile of the first D-1 order-level run (mode F; diagnostic). Reads outputs/scoring/d1_F; descriptive only: nothing is fitted, nothing is tuned, no P&L.
Outputs outputs/scoring/d1_F/profile/*.csv and profile.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); D = f'{OUT}/scoring/d1_F'; PD = f'{D}/profile'; os.makedirs(PD, exist_ok=True)
def run():
    real = pd.read_csv(f'{D}/real_orders.csv'); sim = pd.read_csv(f'{D}/sim_orders.csv'); P = pd.read_csv(f'{D}/all/pairs.csv'); A = pd.read_csv(f'{D}/cycle_attributes.csv'); out = {}
    real['sec'] = real.t; sim['sec'] = np.floor(sim.t).astype(int); real['matched'] = False; sim['matched'] = False; real.loc[P.ri, 'matched'] = True; sim.loc[P.si, 'matched'] = True; r = real.loc[P.ri].reset_index(drop=True); s = sim.loc[P.si].reset_index(drop=True)
    X = P.assign(cyc=r.cyc.values, real_cls=r.cls.values, sim_cls=s.cls.values, sim_role=s.role.values, cp=r.cp.values, side=r.side.values, real_t=r.t.values, real_lots=r.lots.values, sim_lots=s.lots.values, real_strike=r.strike.values, sim_strike=s.strike.values)
    # 1 class tables (two-sided) and confusion
    bc = pd.read_csv(f'{D}/all/by_class.csv'); cc = pd.read_csv(f'{D}/all/class_confusion.csv'); bc.to_csv(f'{PD}/by_class.csv', index=False); cc.to_csv(f'{PD}/class_confusion.csv', index=False)
    out['cross_class_share_of_matched'] = float((X.real_cls != X.sim_cls).mean()); out['cross_class_pairs_with_exact_strike_and_lots'] = int(((X.real_cls != X.sim_cls) & (X.dstrike == 0) & (X.dlots == 0)).sum())
    # 2 missing / extra by class and by engine role
    miss = real[~real.matched].groupby('cls').lots.agg(orders='size', lots='sum'); extra = sim[~sim.matched].groupby('role').lots.agg(orders='size', lots='sum'); miss.to_csv(f'{PD}/missing_by_real_class.csv'); extra.to_csv(f'{PD}/extra_by_sim_role.csv')
    out['missing_total'] = int((~real.matched).sum()); out['extra_total'] = int((~sim.matched).sum())
    # 3 granularity: lots per order by class, real vs simulated
    g = pd.concat([real.groupby('cls').lots.agg(real_orders='size', real_mean_lots='mean', real_multi_lot_share=lambda x: (x > 1).mean()), sim.groupby('cls').lots.agg(sim_orders='size', sim_mean_lots='mean', sim_multi_lot_share=lambda x: (x > 1).mean())], axis=1); g.to_csv(f'{PD}/granularity_by_class.csv'); out['granularity'] = g.round(3).reset_index().to_dict('records')
    bl = pd.read_csv(f'{D}/all/unmatched_missing_by_cyc.csv') if os.path.exists(f'{D}/all/unmatched_missing_by_cyc.csv') else None
    # 4 timing: signed dt among matched by class and side (systematic lags)
    X['dt_abs'] = X.dt.abs(); tim = X.groupby(['real_cls', 'side']).agg(n=('dt', 'size'), dt_median=('dt', 'median'), dt_mean=('dt', 'mean'), p90_abs=('dt_abs', lambda v: v.quantile(.9)), exact=('tier', lambda v: (v == 0).mean())).reset_index(); tim.to_csv(f'{PD}/timing_by_class_side.csv', index=False)
    # 5 late session (>= 15:00) by class: real orders, missing, simulated, extra
    late_r = real[real.t >= 54000]; late_s = sim[sim.sec >= 54000]
    out['late_session'] = dict(real=int(len(late_r)), sim=int(len(late_s)), real_missing=int((~late_r.matched).sum()), sim_extra=int((~late_s.matched).sum()), missing_by_cls=late_r[~late_r.matched].groupby('cls').size().to_dict(), extra_by_role=late_s[~late_s.matched].groupby('role').size().to_dict(), real_by_cls=late_r.groupby('cls').size().to_dict())
    # 6 state: totals vs contract level, and end-of-day carried book
    st = pd.read_csv(f'{D}/all/state_after_matched.csv'); relS = []; relL = []
    for cp in ('CE', 'PE'):
        relS.append(((st[f'S_real_{cp}'] - st[f'S_sim_{cp}']).abs() / st[f'S_real_{cp}'].clip(lower=1))); relL.append(((st[f'L_real_{cp}'] - st[f'L_sim_{cp}']).abs() / st[f'L_real_{cp}'].clip(lower=1)))
    out['state'] = dict(events=int(len(st)), median_rel_error_short_lots=float(pd.concat(relS).median()), median_rel_error_long_lots=float(pd.concat(relL).median()), signed_short_bias=float(((st.S_sim_CE + st.S_sim_PE) - (st.S_real_CE + st.S_real_PE)).mean()), signed_long_bias=float(((st.L_sim_CE + st.L_sim_PE) - (st.L_real_CE + st.L_real_PE)).mean()),
                        l1_norm_median=float(st.l1_norm.median()), exact_S_L_share=float(st.SL_equal.mean()), by_time_block=st.assign(b=(real.loc[st.ri, 't'].values // 3600).astype(int)).groupby('b').l1_norm.median().round(3).to_dict())
    ck = pd.read_csv(f'{D}/all/checkpoints.csv'); eod = ck[ck.end_of_day]; out['end_of_day_book'] = dict(cycles=int(len(eod)), l1_over_gross_real_median=float((eod.l1 / eod.gross_real.clip(lower=1)).median()), l1_over_gross_real_iqr=[float((eod.l1 / eod.gross_real.clip(lower=1)).quantile(.25)), float((eod.l1 / eod.gross_real.clip(lower=1)).quantile(.75))])
    # 7 cycles: table with attributes and drivers
    pc = pd.read_csv(f'{D}/all/per_cycle.csv').merge(A, on='cyc', how='left'); pc.to_csv(f'{PD}/per_cycle_with_attributes.csv', index=False); drv = []
    for c in pc.sort_values('F1').head(6).cyc.tolist() + pc.sort_values('F1_strike_lots_exact').head(3).cyc.tolist():
        rr = real[(real.cyc == c) & ~real.matched].groupby('cls').size(); ss = sim[(sim.cyc == c) & ~sim.matched].groupby('role').size(); drv.append(dict(cyc=c, F1=float(pc.set_index('cyc').loc[c, 'F1']), strict=float(pc.set_index('cyc').loc[c, 'F1_strike_lots_exact']), top_missing=rr.sort_values(ascending=False).head(3).to_dict(), top_extra=ss.sort_values(ascending=False).head(3).to_dict()))
    out['worst_cycle_drivers'] = drv
    pc['sim_over_real_orders'] = pc.sim / pc.real; out['order_count_ratio'] = dict(median=float(pc.sim_over_real_orders.median()), min=float(pc.sim_over_real_orders.min()), max=float(pc.sim_over_real_orders.max()))
    out['by_und_strict'] = pc.groupby('und').F1_strike_lots_exact.median().round(3).to_dict(); out['by_version_strict'] = pc.groupby('version').F1_strike_lots_exact.median().round(3).to_dict(); out['by_era_F1'] = pc.groupby('era').F1.median().round(3).to_dict()
    # 8 strike error structure among matched, by class
    X['dstep'] = X.dstrike; sk = X.groupby('real_cls').agg(n=('dstep', 'size'), exact=('dstep', lambda v: (v == 0).mean()), within1=('dstep', lambda v: (v.abs() <= 1).mean()), far_over5=('dstep', lambda v: (v.abs() > 5).mean()), median_signed=('dstep', 'median')).reset_index(); sk.to_csv(f'{PD}/strike_by_class.csv', index=False)
    json.dump(out, open(f'{PD}/profile.json', 'w'), indent=1, default=float); print(json.dumps(out, indent=1, default=lambda z: round(float(z), 3))[:9000]); print(bc.round(3).to_string(index=False)); print(cc.to_string(index=False)); print(miss.to_string()); print(extra.to_string()); print(sk.round(3).to_string(index=False)); print(tim.round(2).to_string(index=False))
if __name__ == '__main__': run()
