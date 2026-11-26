"""Decoding step 2a: describe the repeat entries (real pair-minutes after the first entry of the same 30-min candle) with true OHLC: side vs previous entry, gap, extension beyond the previous entry's price and beyond the candle's running extreme, ATM change, and whether a new channel level was broken.
Outputs bl_dq_repeat_desc.csv, bl_summary_dq2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_dq_ohlc.py').read().split("rows = []\nfor nm, kw")[0])
ch = Chain(); R = {}; rows = []
for d in CYC:
    K_ = np.array(ch.cyc(d['und'], d['expiry'])['strikes'], float); near = lambda s: K_[np.argmin(np.abs(K_ - s))]
    g = Pr[(Pr.und == d['und']) & (Pr.expiry == d['expiry']) & Pr.reactive].sort_values('te'); t = g.te.values; grp = np.r_[0, np.cumsum(np.diff(t) > 5)] if len(t) else []
    fires = []
    for gi in np.unique(grp):
        m = grp == gi; j = int((t[m][0] - 33300) // 60)
        if j < J0 or j > J1: continue
        fires.append(dict(t=t[m][0], j=j, strike=int(g.strike.values[m][0]), lots=int(m.sum())))
    for f in fires:
        H, L = chan(d, f['j'], 2, 'hl'); atm_prev = near(d['c'][max(f['j'] - 1, 0)]); f['side'] = int(np.sign(f['strike'] - near(d['c'][max(f['j'] - 1, 0)])) or np.sign(f['strike'] - atm_prev)); f['bar'] = (33300 + 60 * f['j']) // 1800; f['H'] = H; f['L'] = L
        f['brk_up'] = d['h'][f['j']] > H; f['brk_dn'] = d['l'][f['j']] < L
    bars = {}
    for f in fires: bars.setdefault(f['bar'], []).append(f)
    for b, fs in bars.items():
        for k in range(1, len(fs)):
            p, f = fs[k - 1], fs[k]; j0, j1 = p['j'], f['j']
            run_hi = d['h'][(b * 1800 - 33300) // 60: j1].max() if j1 > (b * 1800 - 33300) // 60 else np.nan; run_lo = d['l'][(b * 1800 - 33300) // 60: j1].min() if j1 > (b * 1800 - 33300) // 60 else np.nan
            prev_ext = (d['h'][j0:j1].max() if f['side'] > 0 else d['l'][j0:j1].min()) if j1 > j0 else np.nan
            rows.append(dict(und=d['und'], gap_min=(f['t'] - p['t']) / 60, same_side=int(f['side'] == p['side']), same_strike=int(f['strike'] == p['strike']), lots=f['lots'],
                             ext_vs_prev_entry_close_steps=(f['side'] * (d['c'][j1] - d['c'][j0]) / d['step']), new_extreme_since_prev=int((d['h'][j1] > prev_ext) if f['side'] > 0 else (d['l'][j1] < prev_ext)) if j1 > j0 else 0,
                             new_bar_extreme=int((d['h'][j1] >= run_hi) if f['side'] > 0 else (d['l'][j1] <= run_lo)) if run_hi == run_hi else 0, still_beyond_channel=int((d['h'][j1] > f['H']) if f['side'] > 0 else (d['l'][j1] < f['L'])), min_in_bar=((33300 + 60 * j1) % 1800) / 60))
D = pd.DataFrame(rows); D.round(3).to_csv(f'{OUT}/bl_dq_repeat_desc.csv', index=False)
print(len(D), 'repeat fires'); print(D.describe().round(2).T[['mean', '25%', '50%', '75%']])
for c in ('same_side', 'same_strike', 'new_extreme_since_prev', 'new_bar_extreme', 'still_beyond_channel'): R[c] = float(D[c].mean())
R['gap_q'] = D.gap_min.quantile([.1, .25, .5, .75, .9]).round(2).tolist(); R['ext_q'] = D.ext_vs_prev_entry_close_steps.quantile([.1, .25, .5, .75, .9]).round(2).tolist(); print(R); rec('dq2', R)
