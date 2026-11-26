"""Why D0 has 83 scheduled pairs where D-1 has 33 (cycle 4: NIFTY, expiry 2026-07-28): boundary decomposition + a raster across the NIFTY (timetable V1) cycles.
Boundaries are 5-minute marks (minute multiple of 5; 09:15 is one). A pair 'belongs' to a boundary when it falls in [boundary - 3 s, boundary + 130 s].
A boundary is 'used' on a day type when >= 80% of the active NIFTY V1 cycles have a pair that follows it (D0: pairs that recur in other cycles).
Decomposition of the cycle's 83 pairs: (A) same second as a D-1 pair of this cycle; (B) at a boundary D-1 also uses, but another second; (C) at a boundary D-1 does not use (extra 5-minute / skipped 15-minute boundaries); (D) not recurring in other cycles (opening burst); (E) other.
Outputs bl_d0q_why_boundaries.csv, bl_d0q_why_cycle.csv, bl_summary_d0q4.json, figures/bl_d0q_why.png"""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); L = pd.read_csv(f'{OUT}/bl_d0q_loo.csv'); DT = pd.read_csv(f'{OUT}/bl_d0q_detail4.csv'); P1 = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); P1 = P1[P1.sched]
CYi = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}; P1['cid'] = [CYi.get((u, e)) for u, e in zip(P1.und, P1.expiry)]; hm = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}'
nif = [i for i in range(len(CY)) if CY.iloc[i].und == 'NIFTY' and CY.iloc[i].version == 'V1']; act = [i for i in nif if i in set(L.cid)]; Lr = L[L.recurs_in_other_cycles]
bs = np.arange(33300 + 300, 55800, 300); rows = []
for b in bs:
    d1 = np.mean([((P1[P1.cid == i].te >= b - 3) & (P1[P1.cid == i].te <= b + 130)).any() for i in nif]); d0 = np.mean([((Lr[Lr.cid == i].t >= b - 3) & (Lr[Lr.cid == i].t <= b + 130)).any() for i in act])
    n0 = np.mean([((Lr[Lr.cid == i].t >= b - 3) & (Lr[Lr.cid == i].t <= b + 130)).sum() for i in act]); n1 = np.mean([((P1[P1.cid == i].te >= b - 3) & (P1[P1.cid == i].te <= b + 130)).sum() for i in nif])
    rows.append(dict(boundary=hm(b), seconds=b, is_15min=((b - 33300) % 900 == 0), D1_cycles_with_pair=d1, D0_cycles_with_pair=d0, D1_pairs_per_cycle=n1, D0_pairs_per_cycle=n0))
BD = pd.DataFrame(rows); BD.to_csv(f'{OUT}/bl_d0q_why_boundaries.csv', index=False)
used1 = set(BD[BD.D1_cycles_with_pair >= .8].seconds); used0 = set(BD[BD.D0_cycles_with_pair >= .8].seconds); extra_b = sorted(used0 - used1); both_b = sorted(used0 & used1); d1only = sorted(used1 - used0)
# decomposition for the cycle
def boundary_of(t):
    for b in bs:
        if b - 3 <= t <= b + 130: return b
    return None
cat = []
for x in DT.itertuples():
    b = boundary_of(x.seconds)
    if not x.recurs_in_other_cycles: c = 'D: not recurring (opening burst)'
    elif x.on_D1_clock: c = 'A: same second as a D-1 pair'
    elif b in used1: c = 'B: at a boundary D-1 also uses, other second (more pairs per boundary)'
    elif b in used0: c = 'C: at a boundary D-1 does not use'
    else: c = 'E: other'
    cat.append((c, b))
DT['category'] = [c for c, _ in cat]; DT['boundary'] = [hm(b) if b else '' for _, b in cat]; DT.to_csv(f'{OUT}/bl_d0q_why_cycle.csv', index=False)
dec = DT.category.value_counts().sort_index(); print(dec.to_string()); cc = DT[DT.category.str.startswith('C')]; print('extra boundaries used on D0 not D-1:', [hm(b) for b in extra_b]); print('D-1 boundaries unused on D0:', [hm(b) for b in d1only])
R = dict(nifty_v1_cycles=len(nif), nifty_v1_cycles_with_D0=len(act), extra_boundaries_D0_only=[hm(b) for b in extra_b], D1_boundaries_not_used_on_D0=[hm(b) for b in d1only], boundaries_used_by_both=len(both_b), D1_boundaries_used=len(used1), D0_boundaries_used=len(used0),
         pairs_per_boundary_both_D1=float(BD[BD.seconds.isin(both_b)].D1_pairs_per_cycle.mean()), pairs_per_boundary_both_D0=float(BD[BD.seconds.isin(both_b)].D0_pairs_per_cycle.mean()), pairs_per_extra_boundary_D0=float(BD[BD.seconds.isin(extra_b)].D0_pairs_per_cycle.mean()),
         decomposition={k: int(v) for k, v in dec.items()}, exceptions=DT[~DT.strike_is_that_ATM][['time', 'strike', 'spot_prev_min_close', 'ATM_of_prev_close']].to_dict('records'))
pd.to_pickle(dict(BD=BD), f'{OUT}/bl_d0q_why_tmp.pkl'); rec('d0q4', R); print({k: v for k, v in R.items() if k != 'exceptions'}); print(R['exceptions'])
# ---------------- figure: raster of D-1 and D0 pairs across the NIFTY V1 cycles
fig, ax = plt.subplots(2, 1, figsize=(17, 8.5), sharex=True)
for k, (nm, getter) in enumerate((('D-1 (the day before expiry): scheduled pairs', lambda i: P1[P1.cid == i].te.values), ('D0 (expiry day): scheduled pairs (blue = recurs at the same second in other cycles; grey = does not)', lambda i: L[L.cid == i]))):
    a = ax[k]
    for r_, i in enumerate(nif if k == 0 else act):
        if k == 0:
            t = getter(i); a.vlines(t / 3600, r_ - .35, r_ + .35, color='#ed8936', lw=1.6)
        else:
            d = getter(i)
            a.vlines(d[d.recurs_in_other_cycles].t / 3600, r_ - .35, r_ + .35, color='#2b6cb0', lw=1.6); a.vlines(d[~d.recurs_in_other_cycles].t / 3600, r_ - .35, r_ + .35, color='#a0aec0', lw=1.6)
    for b in bs:
        is15 = (b - 33300) % 900 == 0; a.axvline(b / 3600, color='#cbd5e0' if is15 else ('#fbd38d' if (k == 1 and b in extra_b) else '#f1f5f9'), lw=.9 if is15 else (1.4 if (k == 1 and b in extra_b) else .6), zorder=0)
    ids = nif if k == 0 else act; a.set_yticks(range(len(ids))); a.set_yticklabels([CY.iloc[i].expiry[5:] for i in ids], fontsize=8); a.set_title(nm, fontsize=10); a.set_xlim(9.2, 15.0)
ax[1].set_xlabel('time of day (hours). Grey lines = 15-minute boundaries; yellow lines = the 5-minute boundaries D0 uses and D-1 does not')
plt.tight_layout(); plt.savefig(os.path.join(os.path.dirname(OUT), 'reports', 'figures', 'bl_d0q_why.png'), dpi=120, bbox_inches='tight')
