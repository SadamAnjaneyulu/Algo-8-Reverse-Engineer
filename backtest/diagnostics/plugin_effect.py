"""Plugin effectiveness at the FROZEN thresholds (cut trigger 20000bp, fraction 10000bp). Diagnostic only; nothing is selected from the OOS numbers."""
import json, math, pickle
from common import *
cyc = X.usable(); P = BASE
def table_cfg(name):
    eng = X.load_engine(name, 'HOLD_SETTLE'); 
    try: eng2 = pickle.load(open(f'{X.ENG}/HOLD_SETTLE_DXOOS/{name}.pkl', 'rb'))
    except FileNotFoundError: eng2 = {}
    merged = {**eng, **eng2}; rows = []
    for r in cyc.itertuples():
        e = merged[(r.und, r.expiry)]; c = X._cyc(r.und, r.expiry); a = A.account(c, e['fills'], 'HOLD_SETTLE', P)
        rows.append(dict(und=r.und, expiry=r.expiry, d1=r.d1, d0=r.d0, split=r.split, subset=r.subset, gross=a['gross'], net=a['net'], slippage=a['slippage'], costs=a['costs'], n_orders=a['n_orders'], n_engine_orders=a['n_engine_orders'], peak_margin=a['peak_margin'], min_path=a['min_path'], max_path=a['max_path'], path=a['path'], leg_pnl=a['leg_pnl'], lots_traded=a['lots_traded']))
    d = pd.DataFrame(rows); d['wk'] = pd.to_datetime(d.d0).dt.strftime('%G-W%V'); return d
CF = {'PLAIN_HOLD': 'HOLD', 'CUT_ONLY': 'cut_t20000_f10000_re_none', 'CUT+REENTRY(no band)': 'cut_t20000_f10000_re_cd1800', 'CUT+REENTRY+BAND (frozen)': 'cut_t20000_f10000_re_cd1800band', 'CUT_ONLY+CAPITAL_STOP': 'cut_t20000_f10000_re_none_STOP', 'CAPITAL_STOP_ONLY': 'STOP_ONLY'}
T = {k: table_cfg(v) for k, v in CF.items()}; rows = []
for k, d in T.items():
    d.drop(columns=['path', 'leg_pnl']).to_csv(f'{RES}/plugin_cycles_{v if (v:=CF[k]) else k}.csv', index=False)
    for p in ('IS', 'OOS', 'OOS_exposed', 'OOS_clean'):
        x = part(d, p); s = M.summarize(x); h = part(T['PLAIN_HOLD'], p)
        rows.append(dict(config=k, part=p, cycles=len(x), net=x.net.sum(), gross=x.gross.sum(), costs=x.costs.sum(), slippage=x.slippage.sum(), orders=x.n_orders.sum(), orders_per_cycle=x.n_orders.mean(), cycles_with_plugin_action=int((x.n_engine_orders > 0).sum()), sharpe=s['sharpe'], max_dd=s['max_dd_rs'], worst_cycle=x.net.min(), delta_vs_hold=x.net.sum() - h.net.sum(),
                         peak_margin_mean=x.peak_margin.mean()))
R = pd.DataFrame(rows); R.to_csv(f'{RES}/plugin_effectiveness.csv', index=False); pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); print(M.summarize(part(T['PLAIN_HOLD'], 'IS')).keys())
print(R.round(3).to_string(index=False))
# per-cycle delta vs HOLD: helped / hurt breakdown on cycles where the plugin acted
H = T['PLAIN_HOLD'].set_index(['und', 'expiry']); out = []
for k, d in T.items():
    if k == 'PLAIN_HOLD': continue
    x = d.set_index(['und', 'expiry']); dl = (x.net - H.net); act = x.n_engine_orders > 0
    for p, m in (('IS', x.split == 'IS'), ('OOS', x.split == 'OOS'), ('OOS_exposed', x.subset == 'OOS_EXPOSED'), ('OOS_clean', x.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER']))):
        a = dl[m & act]; out.append(dict(config=k, part=p, cycles=int(m.sum()), acted=int(len(a)), helped=int((a > 0).sum()), hurt=int((a < 0).sum()), sum_helped=a[a > 0].sum(), sum_hurt=a[a < 0].sum(), net_delta=a.sum(), mean_delta_when_acted=a.mean() if len(a) else np.nan, worst_cycle_hold_in_acted=H.net[m & act].min() if len(a) else np.nan, worst_cycle_cfg_in_acted=x.net[m & act].min() if len(a) else np.nan,
                        extra_orders_per_acted=x.n_orders[m & act].mean() - H.n_orders[m & act].mean() if len(a) else np.nan, extra_cost_total=(x.costs - H.costs)[m & act].sum(), extra_slippage_total=(x.slippage - H.slippage)[m & act].sum()))
O = pd.DataFrame(out); O.to_csv(f'{RES}/plugin_helped_hurt.csv', index=False); print(O.round(0).to_string(index=False))
# reentry increment: cut-only vs cut+reentry per acted cycles
for a, b in (('CUT_ONLY', 'CUT+REENTRY(no band)'), ('CUT+REENTRY(no band)', 'CUT+REENTRY+BAND (frozen)')):
    xa = T[a].set_index(['und', 'expiry']); xb = T[b].set_index(['und', 'expiry']); dl = xb.net - xa.net; diff = dl[dl.abs() > 1e-6]
    for p, m in (('IS', xa.split == 'IS'), ('OOS', xa.split == 'OOS'), ('OOS_clean', xa.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER']))):
        q = dl[m & (dl.abs() > 1e-6)]; print(f'{b} minus {a} | {p}: cycles_changed={len(q)} helped={(q>0).sum()} hurt={(q<0).sum()} sum={q.sum():.0f}')
# how many positions got cut and how did that leg end: (cut leg: realised at cut vs would-have-settled) via leg_pnl difference only for CUT_ONLY
