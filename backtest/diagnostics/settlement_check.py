"""Backtest-error check: engine official_close vs independent Yahoo daily close for every complete cycle. Diagnostic only."""
from common import *
y = {u: pd.read_csv(f'{BT}/../data_validation/reference/yahoo_daily_{s}.csv').set_index('date_ist') for u, s in (('NIFTY', 'NSEI'), ('SENSEX', 'BSESN'))}
d = cycles('HOLD', 'HOLD_SETTLE'); rows = []
for r in d.itertuples():
    yc = y[r.und].close.get(str(r.d0)[:10], np.nan); yo = y[r.und].open.get(str(r.d0)[:10], np.nan)
    rows.append(dict(und=r.und, expiry=str(r.expiry)[:10], subset=r.subset, official_close=r.official_close, src=r.close_src, yahoo_close=yc, diff=r.official_close - yc, K=r.K, lot=r.lot))
S = pd.DataFrame(rows); S['absdiff'] = S['diff'].abs(); S.to_csv(f'{RES}/settlement_vs_yahoo.csv', index=False)
pd.set_option('display.width', 200)
print(S.groupby(['und', 'src']).absdiff.describe().round(2)); print((S.absdiff > 50).groupby(S.und).sum(), S.yahoo_close.isna().sum())
print(S.sort_values('absdiff', ascending=False).head(15).round(2).to_string())
