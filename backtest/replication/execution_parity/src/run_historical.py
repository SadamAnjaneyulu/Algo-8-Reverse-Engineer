"""PHASE 5 - historical MECHANICS robustness. Not an optimisation and not a performance comparison: the original has no execution records for these periods.
Segments cycles by expiry-calendar structure (weekday runs per index) and by regime labels computed ONLY from the independent Yahoo daily index series (realised volatility terciles, trend).
Runs the reconstructed engine (R1 modules, parameters as in rules.py) on every ELIGIBLE cycle in two execution policies (sim_compat and strict volume>0) and records mechanics checks.
Eligibility register: algo8_replica/experiments/results/cycle_eligibility_register.csv (criteria fixed before use; strict and substituted sets kept apart)."""
import os, sys, warnings, hashlib
import numpy as np, pandas as pd
from multiprocessing import Pool
warnings.filterwarnings('ignore')
import ref
sys.path.insert(0, ref.REPL)
import data, runner
from exec_core import NM
ROOT = ref.ROOT; REG = f'{ROOT}/algo8_replica/experiments/results/cycle_eligibility_register.csv'


def regime_table(E):
    Y = {}
    for u, s in (('NIFTY', 'NSEI'), ('SENSEX', 'BSESN')):
        y = pd.read_csv(f'{ROOT}/data_validation/reference/yahoo_daily_{s}.csv'); y['date'] = pd.to_datetime(y.date_ist); y = y.set_index('date').sort_index(); y['r'] = np.log(y.close).diff(); Y[u] = y
    rows = []
    for r in E.itertuples():
        y = Y[r.und]; d1 = pd.Timestamp(r.d1); past = y[y.index < d1]                                   # strictly before D-1: no information from the cycle itself
        rv = past.r.tail(20).std() * np.sqrt(252) if len(past) >= 21 else np.nan; tr = (past.close.iloc[-1] / past.close.iloc[-61] - 1) if len(past) >= 61 else np.nan
        rows.append(dict(und=r.und, expiry=r.expiry, rv20=rv, trend60=tr))
    X = pd.DataFrame(rows); E = E.merge(X, on=['und', 'expiry'])
    E['vol_regime'] = E.groupby('und').rv20.transform(lambda s: pd.qcut(s, 3, labels=['low_vol', 'mid_vol', 'high_vol'], duplicates='drop'))
    E['trend_regime'] = np.where(E.trend60 > 0.03, 'uptrend', np.where(E.trend60 < -0.03, 'downtrend', 'flat')); return E


def expiry_structure(E):
    """weekday of the expected expiry; the structural weekday is the rolling mode of 5 (holiday shifts are single deviations); a new segment starts when it changes"""
    out = []
    for u, g in E.groupby('und'):
        g = g.sort_values('d0').copy(); g['wd'] = pd.to_datetime(g.d0).dt.day_name(); codes = g.wd.astype('category').cat.codes
        mode = codes.rolling(5, center=True, min_periods=1).apply(lambda x: pd.Series(x).mode().iloc[0]); names = dict(enumerate(g.wd.astype('category').cat.categories)); g['wd_main'] = mode.round().astype(int).map(names)
        g['seg_run'] = (g.wd_main != g.wd_main.shift()).cumsum(); g['expiry_structure'] = [f'{u}-{w}-expiry#{k}' for w, k in zip(g.wd_main, g.seg_run)]; out.append(g)
    return pd.concat(out)


LOTHIST = pd.read_csv(f'{ROOT}/backtest/results/cycle_feasibility.csv')[['und', 'expiry', 'lot1', 'lot0']]


def mech(row):
    und, exp, d1, d0 = row['und'], row['expiry'], row['d1'], row['d0']; res = dict(und=und, expiry=exp, ok=False)
    try:
        c = data.load_cycle(und, exp, d1, d0)
        out = {}
        lh = LOTHIST[(LOTHIST.und == und) & (LOTHIST.expiry == exp)]
        for pol, strict in (('compat', False), ('strict', True), ('compat_histlot', False)):
            lp = runner.build(c, und, 'R1', units=(int(lh.lot1.iloc[0]) if pol == 'compat_histlot' and len(lh) else None), slip=False, strict=strict).run(); ev = runner.events(lp); S = lp.state
            if pol == 'compat_histlot':
                res.update(hist_lot=int(lh.lot1.iloc[0]) if len(lh) else np.nan, cycle_stop_histlot=lp.stopped is not None, leg_stops_histlot=int((ev.tag == 'LEG_STOP').sum()))
            elif pol == 'compat':
                fb = vz = 0
                for f in lp.fills:
                    it = f.intent; o = c[(it.day, it.right, 'open')][it.si, it.j]; v = c[(it.day, it.right, 'volume')][it.si, it.j]
                    fb += int(not (o == o)); vz += int(not (v == v and v > 0))
                body_e = ev[(ev.role == 'body') & (ev.tag == 'ENTRY')]; wing_e = ev[(ev.role == 'wing') & (ev.tag == 'ENTRY')]
                step = ref.STEP[und]; ev2 = ev.reset_index(drop=True); dist = []; ratio = []
                for i in range(len(ev2) - 1):
                    a, b2 = ev2.iloc[i], ev2.iloc[i + 1]
                    if a.role == 'body' and a.tag == 'ENTRY' and b2.role == 'wing' and b2.tag == 'ENTRY' and a.j == b2.j and a.right == b2.right: dist.append(abs(b2.strike - a.strike) / step); ratio.append(b2.ref / a.ref if a.ref else np.nan)
                res.update(wing_dist_steps_median=float(np.median(dist)) if dist else np.nan, wing_px_ratio_median=float(np.nanmedian(ratio)) if ratio else np.nan)
                res.update(n_fills=len(ev), n_entries_body=len(body_e), n_entries_wing=len(wing_e), wing_missing=len(body_e) - len(wing_e), fills_on_open_nan=fb, fills_on_zero_volume_bar=vz, leg_stops=int((ev.tag == 'LEG_STOP').sum()), cycle_stop=lp.stopped is not None, flatten_events=int((ev.tag == 'FLATTEN').sum()), open_at_end=len(S.lots), settle_close_nan=bool(not (lp.settle_close == lp.settle_close)),
                           gross_finite=bool(np.isfinite(lp.gross_pnl())), d1_bars=int((~np.isnan(c[(0, 'spot')])).sum()), d0_bars=int((~np.isnan(c[(1, 'spot')])).sum()), strikes_in_chain=len(c['strikes']))
                # accounting invariants
                net = {}
                for f in lp.fills: net[(f.intent.right, f.intent.si)] = net.get((f.intent.right, f.intent.si), 0) + f.intent.side
                inv_net = {}
                for L in S.lots: inv_net[(L['right'], L['si'])] = inv_net.get((L['right'], L['si']), 0) + L['side']
                res['inventory_consistent'] = {k: v for k, v in net.items() if v} == {k: v for k, v in inv_net.items() if v}
                res['events_hash'] = hashlib.sha1(ev[['d', 'j', 'right', 'strike', 'side', 'role', 'tag']].to_csv().encode()).hexdigest()[:12]
                res['body_closed_gt_opened'] = int((ev[(ev.role == 'body') & (ev.side == 1)].shape[0]) > body_e.shape[0])
            else:
                nm = lp.no_market; res.update(strict_no_market_entries=sum(1 for i in nm if i.tag == 'ENTRY'), strict_no_market_exits=sum(1 for i in nm if i.tag != 'ENTRY'), strict_fills=len(ev), strict_open_at_end=len(S.lots))
        res['ok'] = True
    except Exception as e:
        res['error'] = repr(e)[:200]
    return res


if __name__ == '__main__':
    E = pd.read_csv(REG); E = regime_table(E); E = expiry_structure(E); E['eligible'] = E.eligibility.isin(['FULLY_FEASIBLE', 'FEASIBLE_WITH_DECLARED_SUBSTITUTION'])
    E.to_csv(f'{ref.OUT}/historical_regime_register.csv', index=False)
    todo = E[E.eligible][['und', 'expiry', 'd1', 'd0']].to_dict('records')
    with Pool(4) as p: R = p.map(mech, todo, chunksize=4)
    M = pd.DataFrame(R); M = E.merge(M, on=['und', 'expiry'], how='left'); M.to_csv(f'{ref.OUT}/historical_mechanics_by_cycle.csv', index=False)
    print(len(E), 'cycles;', int(E.eligible.sum()), 'eligible; ok:', int(M.ok.sum()), '; errors:', int(M.error.notna().sum()) if 'error' in M else 0)
