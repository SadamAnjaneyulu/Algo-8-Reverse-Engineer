"""Decoding final evaluation of the true-OHLC machine (previous two completed clock-aligned 30-min candles' high/low; first intrabar break per side per candle; 10:30-15:15; no margin). Subsets, placebos, first-entry capture, error budget. Targets: reactive pair-minutes 10:30-15:29.
Outputs bl_dq_final.csv, bl_dq_final_subsets.csv, bl_dq_error_budget.csv, bl_summary_dq7.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_dq_tune.py').read().split("GR = [")[0])
R = {}; ids = list(range(len(CYC)))
def chan_v(d, j, K, src, phi=0):
    clock = 33300 + 60 * j - phi * 60; b0 = (clock // 1800) * 1800 + phi * 60; a = max(int(np.ceil((b0 - K * 1800 - 33300) / 60)), 0); e = max(int(np.ceil((b0 - 33300) / 60)), 0)
    if e - a < 2: return np.nan, np.nan
    return (d['h'][a:e].max(), d['l'][a:e].min()) if src == 'hl' else (d['c'][a:e].max(), d['c'][a:e].min())
def machv(d, K=2, src='hl', brk='hl', phi=0, per_side=True, jend=360):
    out = []; done = set()
    for j in range(J0, jend + 1):
        H, L = chan_v(d, j, K, src, phi)
        if H != H: continue
        b = (33300 + 60 * j - phi * 60) // 1800
        up = d['h'][j] > H if brk == 'hl' else d['c'][j] > H; dn = d['l'][j] < L if brk == 'hl' else d['c'][j] < L
        for s, fl in ((1, up), (-1, dn)):
            key = (b, s) if per_side else b
            if fl and key not in done: out.append((j, s)); done.add(key)
    return out
def ev(fn, cids=ids):
    tp = tp0 = nf = na = 0; both = ao = mo = ne = 0
    for i in cids:
        d = CYC[i]; F_ = [f for f, _ in fn(d)]; A = d['Afull']; tp += match(F_, A, 1); tp0 += match(F_, A, 0); nf += len(F_); na += len(A)
        mb = {(33300 + 60 * f) // 1800 for f in F_}; ab = {(33300 + 60 * a) // 1800 for a in A}
        for b in range((33300 + 60 * J0) // 1800, (33300 + 60 * 374) // 1800 + 1): m = b in mb; a = b in ab; both += m and a; ao += a and not m; mo += m and not a; ne += not m and not a
    return dict(F1=2 * tp / (nf + na), precision=tp / nf, recall=tp / na, F1_same_minute=2 * tp0 / (nf + na), fires=nf, targets=na, bar_precision=both / max(both + mo, 1), bar_recall=both / max(both + ao, 1), bar_odds=(both * ne) / max(ao * mo, 1))
rows = []
for nm, fn in (('FINAL: true high/low, previous 2 candles, intrabar break, per side, 10:30-15:15', lambda d: machv(d)),
               ('placebo: clock shifted +5 min', lambda d: machv(d, phi=5)), ('placebo: clock shifted +15 min (09:15-aligned candles)', lambda d: machv(d, phi=15)), ('placebo: clock shifted -1 min', lambda d: machv(d, phi=-1)),
               ('previous 1 candle', lambda d: machv(d, K=1)), ('previous 3 candles', lambda d: machv(d, K=3)), ('channel from closes, break by close (earlier report)', lambda d: machv(d, src='c', brk='c')), ('true channel, break by close only', lambda d: machv(d, brk='c')), ('one entry per candle (not per side)', lambda d: machv(d, per_side=False))):
    rows.append(dict(machine=nm, **ev(fn)))
T = pd.DataFrame(rows); T.round(4).to_csv(f'{OUT}/bl_dq_final.csv', index=False); print(T.round(3).to_string(index=False)); R['machines'] = T.round(4).to_dict('records')
sub = []
for nm, cids in (('all', ids), ('NIFTY', [d['cid'] for d in CYC if d['und'] == 'NIFTY']), ('SENSEX', [d['cid'] for d in CYC if d['und'] == 'SENSEX']), ('V1 (to 2026-09-09)', [d['cid'] for d in CYC if d['expiry'] < '2026-09-16']), ('V2 (from 2026-09-16)', [d['cid'] for d in CYC if d['expiry'] >= '2026-09-16']), ('first half of cycles', ids[:16]), ('second half of cycles', ids[16:])):
    sub.append(dict(subset=nm, cycles=len(cids), **ev(lambda d: machv(d), cids)))
SB = pd.DataFrame(sub); SB.round(4).to_csv(f'{OUT}/bl_dq_final_subsets.csv', index=False); print(SB.round(3).to_string(index=False)); R['subsets'] = SB.round(4).to_dict('records')
# first-entry capture and error budget
fe = fe_hit = fe_exact = 0; bud = dict(targets=0, matched=0, repeat_in_candle=0, after_1515=0, first_entry_timing_off=0, no_machine_break=0); fires_unmatched = dict(no_real_entry_in_candle_side=0, timing_off=0)
for d in CYC:
    fi = machv(d); F_ = [f for f, _ in fi]; A = sorted(d['Afull']); used = set(); mm = {}
    for f in sorted(F_):
        c = [a for a in A if abs(a - f) <= 1 and a not in used]
        if c: a = min(c, key=lambda x: abs(x - f)); used.add(a); mm[f] = a
    g = Pr[(Pr.und == d['und']) & (Pr.expiry == d['expiry']) & Pr.reactive]; jj = ((g.te.values - 33300) // 60).astype(int); K_ = np.array(Chain().cyc(d['und'], d['expiry'])['strikes'], float)
    side_of = {}
    for j_, k_ in zip(jj, g.strike.values):
        if J0 <= j_ <= 374: side_of.setdefault(j_, int(np.sign(k_ - K_[np.argmin(np.abs(K_ - d['c'][max(j_ - 1, 0)]))])))
    firsts = {}
    for a in A: firsts.setdefault(((33300 + 60 * a) // 1800, side_of.get(a, 0)), a)
    mfire = {((33300 + 60 * f) // 1800, s): f for f, s in fi}
    for key, a in firsts.items():
        fe += 1; f = mfire.get(key)
        if f is not None and abs(f - a) <= 1: fe_hit += 1; fe_exact += int(f == a)
    for a in A:
        bud['targets'] += 1
        if a in used: bud['matched'] += 1; continue
        b = (33300 + 60 * a) // 1800; key = (b, side_of.get(a, 0))
        if a > 360: bud['after_1515'] += 1
        elif firsts.get(key) != a: bud['repeat_in_candle'] += 1
        elif key in mfire: bud['first_entry_timing_off'] += 1
        else: bud['no_machine_break'] += 1
    for f, s in fi:
        if f in mm: continue
        if ((33300 + 60 * f) // 1800, s) in firsts: fires_unmatched['timing_off'] += 1
        else: fires_unmatched['no_real_entry_in_candle_side'] += 1
R['first_entry'] = dict(candle_sides_with_real_entry=fe, machine_within_1min=fe_hit, exact_minute=fe_exact, capture=fe_hit / fe, exact_share=fe_exact / fe); R['budget'] = bud; R['fires_unmatched'] = fires_unmatched
print(R['first_entry']); print(bud); print(fires_unmatched)
pd.DataFrame([dict(item=k, count=v) for k, v in list(bud.items()) + [('machine fires: ' + k, v) for k, v in fires_unmatched.items()]]).to_csv(f'{OUT}/bl_dq_error_budget.csv', index=False); rec('dq7', R)
