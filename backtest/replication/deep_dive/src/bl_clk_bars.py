"""Clock-bar study: bar-level confusion of the machine (previous 2 completed 30-min bars; one entry per side per bar; current-minute close) vs the real reactive entries, with clock-phase placebos and the rolling-70 comparison. Bar = 30-minute clock block with at least one minute in the 10:30-15:15 window.
Outputs bl_clk_bars.csv, bl_clk_barcount.csv, bl_summary_clk7.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
sys.argv = ['x']; exec(open('bl_clk_refine.py').read().split("rows = []\nfor nm, fn")[0])
R = {}
def barsets(fn, phi=0):
    tot = dict(both=0, act_only=0, mach_only=0, neither=0); per = []
    for d in CYC:
        fi = fn(d); mb = {int((33300 + 60 * f - phi * 60) // Lb) for f, _ in fi}; ab = {int((33300 + 60 * a - phi * 60) // Lb) for a in d['A']}; bars = set(range(int((33300 + 60 * J0 - phi * 60) // Lb), int((33300 + 60 * J1 - phi * 60) // Lb) + 1))
        for b in bars: m = b in mb; a = b in ab; tot['both'] += m and a; tot['act_only'] += (not m) and a; tot['mach_only'] += m and (not a); tot['neither'] += (not m) and (not a)
    return tot
def stats(t): n = sum(t.values()); a, b, c, d_ = t['both'], t['mach_only'], t['act_only'], t['neither']; return dict(bars=n, **t, precision_bar=a / (a + b), recall_bar=a / (a + c), odds_ratio=(a * d_) / max(b * c, 1), phi=(a * d_ - b * c) / np.sqrt((a + b) * (c + d_) * (a + c) * (b + d_)), base_rate_actual=(a + c) / n, base_rate_machine=(a + b) / n)
rows = []
for nm, fn, phi in (('previous 2 completed 30-min bars, clock phase 0 (hh:00 / hh:30)', lambda d: run2(d, var='intra', per_side=True), 0), ('same, completed minute closes only', lambda d: run2(d, var='bar', per_side=True), 0), ('same but clock shifted by +5 min (placebo)', lambda d: run2(d, var='intra', per_side=True, phi=5), 5), ('clock shifted by +15 min (placebo)', lambda d: run2(d, var='intra', per_side=True, phi=15), 15), ('clock shifted by -1 min (placebo)', lambda d: run2(d, var='intra', per_side=True, phi=-1), -1), ('previous 1 bar', lambda d: run2(d, K=1, var='intra', per_side=True), 0), ('previous 3 bars', lambda d: run2(d, K=3, var='intra', per_side=True), 0), ('rolling 70-min range, one entry per side per 30-min block', lambda d: runc(d, 'intra', 70, 30, 30, 1, 0), 0)):
    rows.append(dict(machine=nm, **stats(barsets(fn, phi))))
BR = pd.DataFrame(rows); BR.round(4).to_csv(f'{OUT}/bl_clk_bars.csv', index=False); print(BR.round(3).to_string(index=False)); R['rows'] = BR.round(4).to_dict('records')
# entries per bar: actual fires vs machine fires per bar
cnt = []
for d in CYC:
    fi = run2(d, var='intra', per_side=True); mc = {}; ac = {}
    for f, s in fi: b = int((33300 + 60 * f) // Lb); mc[b] = mc.get(b, 0) + 1
    for a in d['A']: b = int((33300 + 60 * a) // Lb); ac[b] = ac.get(b, 0) + 1
    for b in set(mc) | set(ac): cnt.append(dict(machine_fires=mc.get(b, 0), actual_pair_minutes=ac.get(b, 0)))
C = pd.DataFrame(cnt); T = pd.crosstab(C.machine_fires, C.actual_pair_minutes); T.to_csv(f'{OUT}/bl_clk_barcount.csv'); print(T); R['crosstab'] = {str(k): {str(c): int(v) for c, v in r.items()} for k, r in T.iterrows()}
R['actual_bar_count_dist'] = {int(k): int(v) for k, v in C[C.actual_pair_minutes > 0].actual_pair_minutes.value_counts().sort_index().items()}; R['machine_bar_count_dist'] = {int(k): int(v) for k, v in C[C.machine_fires > 0].machine_fires.value_counts().sort_index().items()}; rec('clk7', R)
