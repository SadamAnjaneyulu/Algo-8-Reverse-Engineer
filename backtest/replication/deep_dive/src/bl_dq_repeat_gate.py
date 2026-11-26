"""Decoding step 5 (post-hoc): does a portfolio-stress gate on repeat entries add to the true-OHLC machine? Base = first break per side per 30-min candle (end 15:15). Repeat candidates = minutes after the first entry that make a new candle extreme beyond the channel; a repeat fires when a single feature passes a threshold (chosen on the other cycle half). Scored on full-session targets.
Outputs bl_dq_repeat_gate.csv, bl_summary_dq6.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_dq_tune.py').read().split("GR = [")[0])
RP = pd.read_csv(f'{OUT}/bl_dq_gate_repeat_rows.csv'); R = {}; ids = list(range(len(CYC)))
BASE = {d['cid']: [f for f, _ in mach(d, 0, 360)] for d in CYC}
def score(extra, cids):
    tp = nf = na = tp0 = 0
    for i in cids: F_ = sorted(set(BASE[i]) | set(extra.get(i, []))); A = CYC[i]['Afull']; tp += match(F_, A, 1); tp0 += match(F_, A, 0); nf += len(F_); na += len(A)
    return 2 * tp / (nf + na), tp / nf, tp / na, 2 * tp0 / (nf + na)
def extra_for(v, th, sgn, gap=1):
    x = RP[(sgn * RP[v] >= sgn * th) & (RP.min_since_last >= gap)]; e = {}
    for r in x.itertuples(): e.setdefault(r.cid, []).append(int(r.j))
    return e
feats = ['delta_vs_side', 'itm_short', 'pnl_chg15', 'minute_range', 'short_lots', 'vol_rel', 'ext_beyond_channel', 'min_since_last']
rows = [dict(rule='base only', F1=score({}, ids)[0], precision=score({}, ids)[1], recall=score({}, ids)[2])]
for v in feats:
    sgn = -1 if v == 'pnl_chg15' else 1; qs = np.nanquantile(RP[v], [.5, .6, .7, .8, .85, .9, .95, .98]); cfgs = [(th, g) for th in qs for g in (1, 3, 5)]
    tp = nf = na = 0; ch_ = []
    for h in (0, 1):
        tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; b = max(cfgs, key=lambda c: score(extra_for(v, c[0], sgn, c[1]), tr)[0]); ch_.append((round(float(b[0]), 3), b[1]))
        e = extra_for(v, b[0], sgn, b[1])
        for i in te: F_ = sorted(set(BASE[i]) | set(e.get(i, []))); A = CYC[i]['Afull']; tp += match(F_, A, 1); nf += len(F_); na += len(A)
    rows.append(dict(rule=f'repeat when {v} {"<=" if sgn < 0 else ">="} threshold (out-of-fold)', chosen=str(ch_), F1=2 * tp / (nf + na), precision=tp / nf, recall=tp / na))
S = pd.DataFrame(rows); S.round(4).to_csv(f'{OUT}/bl_dq_repeat_gate.csv', index=False); print(S.round(3).to_string(index=False)); R['rows'] = S.round(4).to_dict('records'); rec('dq6', R)
