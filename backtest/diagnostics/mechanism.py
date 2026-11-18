"""Where in time is P&L made/lost: D-1 session, overnight gap (D-1 15:29 -> D0 09:15..09:16 mark), D0 session (to settlement). Uses the net equity path of the HOLD baseline (gross of nothing: net path)."""
import json, datetime, pickle
from common import *
d = cycles('HOLD', 'HOLD_SETTLE'); rows = []
for r in d.itertuples():
    t_d1 = scen.epoch(str(r.d1)[:10], '15:29') + 60; t_d0 = scen.epoch(str(r.d0)[:10], '09:16'); path = r.path
    v_d1 = [v for t, v in path if t <= t_d1][-1]; v_d0 = [v for t, v in path if t <= t_d0][-1] if any(t <= t_d0 for t, _ in path) else v_d1; fin = r.net
    # D0 intraday settle-minus-15:29 mark
    t_end = scen.epoch(str(r.d0)[:10], '15:29') + 60; v_end = [v for t, v in path if t <= t_end][-1]
    rows.append(dict(und=r.und, expiry=str(r.expiry)[:10], split=r.split, subset=r.subset, net=fin, d1_session=v_d1, overnight_gap=v_d0 - v_d1, d0_morning_to_1529=v_end - v_d0, settlement_step=fin - v_end))
M_ = pd.DataFrame(rows); M_.to_csv(f'{RES}/pnl_time_decomposition.csv', index=False)
g = []
for p in ('IS', 'OOS', 'OOS_exposed', 'OOS_clean'):
    x = M_[M_.split.eq('IS') if p == 'IS' else (M_.split.eq('OOS') if p == 'OOS' else (M_.subset.eq('OOS_EXPOSED') if p == 'OOS_exposed' else M_.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER'])))]
    for lab, y in (('ALL', x), ('WORST10pct', x[x.net <= x.net.quantile(.1)]), ('BEST10pct', x[x.net >= x.net.quantile(.9)])):
        g.append(dict(part=p, group=lab, cycles=len(y), net=y.net.sum(), d1_session=y.d1_session.sum(), overnight_gap=y.overnight_gap.sum(), d0_to_1529=y.d0_morning_to_1529.sum(), settlement_step=y.settlement_step.sum()))
G = pd.DataFrame(g); G.to_csv(f'{RES}/pnl_time_decomposition_summary.csv', index=False); pd.set_option('display.width', 250); print(G.round(0).to_string(index=False))
# when does the frozen config's cut first fire (minute of D0)?
fz = cycles('cut_t20000_f10000_re_cd1800band', 'HOLD_SETTLE'); ts = []
for r in fz.itertuples():
    for t in r.trades:
        if t[6] == 'ENGINE' and t[2] > 0: ts.append(dict(split=r.split, und=r.und, minute_of_d0=(t[0] + 19800) % 86400 // 60 - (9 * 60 + 15), day=datetime.datetime.fromtimestamp(t[0] + 19800, datetime.UTC).strftime('%Y-%m-%d'), d0=str(r.d0)[:10], d1=str(r.d1)[:10], leg=t[1]))
Tm = pd.DataFrame(ts); Tm['on_d0'] = Tm.day == Tm.d0; print(Tm.groupby('split').agg(n=('on_d0', 'size'), on_d0=('on_d0', 'mean'), first_minutes_le_5=('minute_of_d0', lambda v: (v <= 5).mean()), median_min=('minute_of_d0', 'median')))
Tm.to_csv(f'{RES}/cut_timing.csv', index=False)
# straddle identity: gross_straddle (SCE+SPE) vs premium - |close-K| ; wings add small
L = pd.read_csv(f'{RES}/leg_attribution_cycles.csv'); lot = d.set_index(['und', d.expiry.astype(str).str[:10]]).lot
L['qty'] = L.SCE_qty; L['prem'] = (L.SCE_entry_ref + L.SPE_entry_ref); L['model'] = L.qty * (L.prem - L.move_pts.abs()); L['straddle_gross'] = L.SCE_gross + L.SPE_gross
print('corr(straddle gross, qty*(premium-|move|))', L[['straddle_gross', 'model']].corr().iloc[0, 1].round(4), ' max abs err', (L.straddle_gross - L.model).abs().max().round(1))
# did cuts ever happen BEFORE the gap, i.e. on D-1? 
print('cut orders on D-1:', int((~Tm.on_d0).sum()), 'of', len(Tm))
