"""Decoding step 1: rebuild the 30-minute-candle machine with TRUE one-minute highs/lows (channel = previous K completed clock-aligned 30-min candles; break detected intrabar from the minute's high/low), then decompose the remaining error.
Outputs bl_dq_ohlc.csv, bl_dq_errors.csv, bl_summary_dq1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
OH = bl_ohlc.load(); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz'); J0, J1 = 75, 360; R = {}
CYC = []
for i, r in enumerate(CY.itertuples()):
    o = OH[(r.und, r.expiry)]; pa = P[(P.und == r.und) & (P.expiry == r.expiry)]; A = pa[pa.y == 1]
    CYC.append(dict(cid=i, und=r.und, expiry=r.expiry, o=o.open.values, h=o.high.values, l=o.low.values, c=o.close.values, step=ref.STEP[r.und], A=A.j.values.astype(int), side_a=dict(zip(A.j.values.astype(int), np.sign(A.pair_dir.values)))))
def chan(d, j, K, src):
    clock = 33300 + 60 * j; b0 = (clock // 1800) * 1800; a = max(int(np.ceil((b0 - K * 1800 - 33300) / 60)), 0); e = max(int(np.ceil((b0 - 33300) / 60)), 0)
    if e - a < 2: return np.nan, np.nan
    if src == 'hl': return d['h'][a:e].max(), d['l'][a:e].min()
    return d['c'][a:e].max(), d['c'][a:e].min()
def machine(d, K=2, src='hl', brk='hl', per_side=True, j0=J0, j1=J1):
    out = []; done = set()
    for j in range(j0, j1 + 1):
        H, L = chan(d, j, K, src)
        if H != H: continue
        up = (d['h'][j] > H) if brk == 'hl' else (d['c'][j] > H); dn = (d['l'][j] < L) if brk == 'hl' else (d['c'][j] < L)
        b = (33300 + 60 * j) // 1800
        for s, flag in ((1, up), (-1, dn)):
            if not flag: continue
            key = (b, s) if per_side else b
            if key in done: continue
            out.append((j, s)); done.add(key)
    return out
def match(F, A, tol):
    used = set(); tp = 0
    for f in sorted(F):
        best = None
        for a in A:
            if a in used or abs(a - f) > tol: continue
            if best is None or abs(a - f) < abs(best - f): best = a
        if best is not None: used.add(best); tp += 1
    return tp
def score(fn):
    tp1 = tp0 = nf = na = 0; both = ao = mo = ne = 0
    for d in CYC:
        fi = fn(d); F_ = [f for f, _ in fi]; tp1 += match(F_, d['A'], 1); tp0 += match(F_, d['A'], 0); nf += len(F_); na += len(d['A'])
        mb = {(33300 + 60 * f) // 1800 for f in F_}; ab = {(33300 + 60 * a) // 1800 for a in d['A']}
        for b in range((33300 + 60 * J0) // 1800, (33300 + 60 * J1) // 1800 + 1): m = b in mb; a = b in ab; both += m and a; ao += a and not m; mo += m and not a; ne += not m and not a
    return dict(F1=2 * tp1 / (nf + na), precision=tp1 / nf, recall=tp1 / na, F1_same_minute=2 * tp0 / (nf + na), fires=nf, bar_precision=both / (both + mo), bar_recall=both / (both + ao), bar_odds=(both * ne) / max(ao * mo, 1))
rows = []
for nm, kw in (('closes channel, close break (previous report)', dict(src='c', brk='c')), ('true high/low channel, close break', dict(src='hl', brk='c')), ('closes channel, intrabar high/low break', dict(src='c', brk='hl')), ('TRUE high/low channel + intrabar high/low break', dict(src='hl', brk='hl')),
               ('true HL, K=1', dict(K=1)), ('true HL, K=3', dict(K=3)), ('true HL, one entry per bar (not per side)', dict(per_side=False))):
    rows.append(dict(machine=nm, **score(lambda d: machine(d, **kw))))
S = pd.DataFrame(rows); S.round(4).to_csv(f'{OUT}/bl_dq_ohlc.csv', index=False); print(S.round(3).to_string(index=False)); R['machines'] = S.round(4).to_dict('records')
# error decomposition for the true-HL machine
E = dict(real_total=0, real_matched=0, real_repeat_in_machine_bar=0, real_first_in_bar_timing_off=0, real_in_no_machine_bar=0, mach_total=0, mach_matched=0, mach_in_bar_without_real=0, mach_timing_off=0); tdiff = []
for d in CYC:
    fi = machine(d); F_ = [f for f, _ in fi]; A = sorted(d['A']); used = set(); mm = {}
    for f in sorted(F_):
        c = [a for a in A if abs(a - f) <= 1 and a not in used]
        if c: a = min(c, key=lambda x: abs(x - f)); used.add(a); mm[f] = a
    mbar = {}
    for f, s in fi: mbar.setdefault((33300 + 60 * f) // 1800, []).append(f)
    abar = {}
    for a in A: abar.setdefault((33300 + 60 * a) // 1800, []).append(a)
    E['real_total'] += len(A); E['real_matched'] += len(used); E['mach_total'] += len(F_); E['mach_matched'] += len(mm)
    for a in A:
        if a in used: continue
        b = (33300 + 60 * a) // 1800
        if b not in mbar: E['real_in_no_machine_bar'] += 1
        elif a == min(abar[b]) and not any(x in used for x in abar[b]): E['real_first_in_bar_timing_off'] += 1; tdiff.append(a - min(mbar[b]))
        else: E['real_repeat_in_machine_bar'] += 1
    for f in F_:
        if f in mm: continue
        b = (33300 + 60 * f) // 1800
        if b not in abar: E['mach_in_bar_without_real'] += 1
        else: E['mach_timing_off'] += 1
R['errors'] = E; R['timing_off_diffs'] = sorted(tdiff); print(json.dumps(E, indent=1)); print('first-real-entry minus machine-break (timing-off cases):', sorted(tdiff))
pd.DataFrame([E]).T.to_csv(f'{OUT}/bl_dq_errors.csv'); rec('dq1', R)
