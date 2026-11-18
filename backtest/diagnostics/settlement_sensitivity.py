"""Corrected-settlement run (SETTLE_YAHOO): re-values only the expiry settlement leg of each cycle using the independent Yahoo official daily close.
Entry/exit fills, slippage and costs are unchanged except the exercise-STT term, which depends on settlement value. Original results are NOT modified."""
import json, math
from common import *
y = {u: pd.read_csv(f'{BT}/../data_validation/reference/yahoo_daily_{s}.csv').set_index('date_ist').close for u, s in (('NIFTY', 'NSEI'), ('SENSEX', 'BSESN'))}
intr = lambda cp, K, S: max(S - K, 0.0) if cp == 'CE' else max(K - S, 0.0)


def corrected(d):
    out = []
    for r in d.itertuples():
        c = Cy.load(r.und, str(r.expiry)[:10]); S0 = r.official_close; S1 = float(y[r.und][str(r.d0)[:10]]); dv = dstt = 0.0
        for lid, q, v in r.settle:
            k, cp = c['legs'][lid]['strike'], c['legs'][lid]['cp']; v1 = intr(cp, k, S1); dv += q * (v1 - v)
            rate = A.stt_exercise(str(r.d0)[:10]); dstt += rate * ((v1 * q if (q > 0 and v1 > 0) else 0) - (v * q if (q > 0 and v > 0) else 0))
        out.append((r.gross + dv, r.net + dv - dstt, S1 - S0))
    d = d.copy(); d['gross_y'], d['net_y'], d['close_diff'] = zip(*out); return d


res = {}; rows = []
for lab, name, var in (('HOLD', 'HOLD', 'HOLD_SETTLE'), ('FROZEN_CUT_REENTRY', 'cut_t20000_f10000_re_cd1800band', 'HOLD_SETTLE')):
    d = corrected(cycles(name, var)); d.drop(columns=['path', 'trades', 'leg_pnl', 'settle']).to_csv(f'{RES}/settle_yahoo_cycles_{lab}.csv', index=False)
    for p in ('IS', 'OOS', 'OOS_exposed', 'OOS_clean'):
        x = part(d, p); xs = x.copy(); w0 = xs.groupby('wk').net.sum() / CAP; w1 = xs.groupby('wk').net_y.sum() / CAP
        sh = lambda w: w.mean() / w.std(ddof=1) * math.sqrt(52)
        rows.append(dict(config=lab, part=p, cycles=len(x), net_original=x.net.sum(), net_settle_yahoo=x.net_y.sum(), delta=x.net_y.sum() - x.net.sum(), sharpe_original=sh(w0), sharpe_settle_yahoo=sh(w1),
                         mean_close_diff_pts=x.close_diff.mean(), mean_abs_close_diff_pts=x.close_diff.abs().mean(), top5_share_orig=x.net.nlargest(5).sum() / x.net.sum(), top5_share_yahoo=x.net_y.nlargest(5).sum() / x.net_y.sum()))
T = pd.DataFrame(rows); T.to_csv(f'{RES}/settlement_sensitivity.csv', index=False); pd.set_option('display.width', 250); print(T.round(3).to_string(index=False))
