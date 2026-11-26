"""Clock-gate study: refinements of the two-completed-30-min-bars, one-entry-per-bar machine (post-hoc): phase, per-side limit, information variant, first-break timing, start/end window, strike side agreement.
Outputs bl_clk_refine.csv, bl_clk_timing.csv, bl_summary_clk4.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_clk_chan.py').read().split("\nCF = [('roll'")[0]; sys.argv = ['x']; exec(src)
R = {}
def run2(d, K=2, var='bar', phi=0, per_side=False, jstart=J0, jend=J1, kind='bars_prev'):
    out = []; cnt = {}; sp = d['sp']
    for j in range(jstart, jend + 1):
        c = sp[j - 1] if var == 'bar' else sp[j]; hi, lo = chan(d, j, kind, K, var)
        if hi != hi: continue
        s = 1 if c > hi else (-1 if c < lo else 0)
        if s == 0: continue
        b = int((33300 + 60 * j - phi * 60) // Lb); key = (b, s) if per_side else b
        if cnt.get(key, 0) >= 1: continue
        out.append((j, s)); cnt[key] = 1
    return out
def sc(fn, tol=1):
    tp = nf = na = tp0 = 0
    for d in CYC: fi = fn(d); F_ = [f for f, _ in fi]; tp += match(F_, d['A'], tol); tp0 += match(F_, d['A'], 0); nf += len(F_); na += len(d['A'])
    return dict(F1=2 * tp / (nf + na), precision=tp / nf, recall=tp / na, F1_same_minute=2 * tp0 / (nf + na), fires=nf)
rows = []
for nm, fn in (('base: prev 2 bars, one entry per bar, completed bars, phase 0', lambda d: run2(d)),
               ('current-minute close (look-ahead proxy)', lambda d: run2(d, var='intra')),
               ('one entry per SIDE per bar', lambda d: run2(d, per_side=True)),
               ('phase +1 min', lambda d: run2(d, phi=1)), ('phase -1 min', lambda d: run2(d, phi=-1)), ('phase +5 min', lambda d: run2(d, phi=5)), ('phase +15 min', lambda d: run2(d, phi=15)),
               ('start 10:00 (minute 45)', lambda d: run2(d, jstart=45)), ('start 11:00 (minute 105)', lambda d: run2(d, jstart=105)), ('end 15:30 (minute 375 capped)', lambda d: run2(d, jend=374)),
               ('K = 3 bars', lambda d: run2(d, K=3)), ('K = 2 bars + current partial', lambda d: run2(d, kind='bars_cur')), ('K = 1 bar', lambda d: run2(d, K=1))):
    rows.append(dict(variant=nm, **sc(fn)))
RF = pd.DataFrame(rows); RF.round(4).to_csv(f'{OUT}/bl_clk_refine.csv', index=False); print(RF.round(3).to_string(index=False)); R['rows'] = RF.round(4).to_dict('records')
# timing: actual pair minute minus machine fire minute for matched fires (intra variant), and the minute of the block of the fires
diff = []; pos = []
for d in CYC:
    fi = run2(d, var='intra'); A = sorted(d['A'])
    for f, s in fi:
        c = [a for a in A if abs(a - f) <= 3]
        if c: a = min(c, key=lambda x: abs(x - f)); diff.append(a - f)
        pos.append(((33300 + 60 * f) % 1800) / 60)
D = pd.Series(diff).value_counts().sort_index(); print('actual minus machine fire minute (within 3 min):', D.to_dict()); R['timing_diff'] = {int(k): int(v) for k, v in D.items()}
PMB = pd.Series(np.floor(pos)).value_counts().sort_index(); print('machine fire minute within block:', PMB.head(12).to_dict()); R['machine_minute_in_block'] = {int(k): int(v) for k, v in PMB.items()}
pd.DataFrame({'actual_minus_machine_minute': D.index, 'count': D.values}).to_csv(f'{OUT}/bl_clk_timing.csv', index=False)
# side agreement of matched fires
for d in CYC:
    pa = P[(P.und == d['und']) & (P.expiry == CY.expiry.iloc[d['cid']]) & (P.y == 1)]; d['side_a'] = dict(zip(pa.j.values.astype(int), pa.pair_dir.values))
ok = n = 0
for d in CYC:
    for f, s in run2(d):
        for a in (f - 1, f, f + 1):
            if a in d['A']: n += 1; ok += int(np.sign(d['side_a'][a]) == s); break
R['side_agreement'] = ok / n; R['side_n'] = n; print('side agreement', ok / n, n); rec('clk4', R)
