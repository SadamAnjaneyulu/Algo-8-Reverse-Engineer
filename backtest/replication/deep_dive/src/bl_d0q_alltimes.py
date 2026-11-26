"""Every scheduled clock time on D-1 and on D0, per group (underlying x timetable version), with the average lots executed (CE + PE) per active cycle.
Wave = a learned recurring clock time (>= 50% of the group's active cycles, +-3 s; `waves()` for D0 from D0 pair starts of the group's cycles, `waves_d1` logic for D-1). Waves within 3 s of each other form one clock-time cluster
(stacked straddles in the same second). Per cluster and cycle: lots executed = lots of all scheduled pairs whose first order falls in [cluster min - 3 s, cluster max + 3 s]; averaged over the cycles still active at that time (D0: before the cycle stop; D-1: all).
Slot = the 133 s after each 5-minute mark (09:15, 09:20, ...): average lots per active cycle of scheduled pairs starting in [mark - 3 s, mark + 130 s].
Outputs bl_d0q_alltimes.csv, bl_d0q_slots.csv, bl_d0q_daytotals.csv, bl_summary_d0q5.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_d0s_tt.py').read(); exec(src[:src.index('WALL = waves(D0C)')])
hm = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'; R = {}
P1 = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); P1 = P1[P1.sched].copy(); CYi = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}; P1['cid'] = [CYi.get((u, e)) for u, e in zip(P1.und, P1.expiry)]; P1 = P1.dropna(subset=['cid']); P1['cid'] = P1.cid.astype(int)
P1['lots'] = P1.lots_ce + P1.lots_pe; W1 = pd.read_csv(f'{OUT}/bl_d0q_d1waves.csv'); WALL = waves(D0C)
# D0 scheduled pairs (pairs at a wave of the cycle's own group) with their lots
wl = {g: WALL[(WALL.und == g[0]) & (WALL.version == g[1])].t.values for g in sorted({GRP(i) for i in D0C})}
PS['sched_all'] = [len(wl[GRP(i)]) > 0 and np.min(np.abs(wl[GRP(i)] - t)) <= 3 for i, t in zip(PS.cid, PS.t0)]
pl = S[S.pid >= 0].groupby(['cid', 'pid']).agg(lots=('lots', 'sum')).reset_index(); P0 = PS[PS.sched_all].merge(pl, on=['cid', 'pid'], suffixes=('_min', '')).rename(columns={'t0': 't'})[['cid', 'pid', 't', 'lots']]
def clusters(t):
    t = np.sort(np.asarray(t, float)); out = []; cur = [t[0]]
    for x in t[1:]:
        if x - cur[-1] <= 3: cur.append(x)
        else: out.append(cur); cur = [x]
    out.append(cur); return out
rows = []; slots = []
GR = sorted({GRP(i) for i in D0C}); bs = np.arange(33300, 55800, 300)
for (und, ver) in GR:
    c0 = [i for i in D0C if GRP(i) == (und, ver)]; c1 = [i for i, r in enumerate(CY.itertuples()) if (r.und, r.version) == (und, ver) and (P1.cid == i).any()]
    for day, cids, tt, pairs, tcol in (('D-1', c1, W1[(W1.und == und) & (W1.version == ver)].t.values, P1, 'te'), ('D0', c0, wl[(und, ver)], P0, 't')):
        for cl in clusters(tt):
            lo, hi, med = min(cl) - 3, max(cl) + 3, float(np.median(cl)); act = [i for i in cids if (STOP[i] > med if day == 'D0' else True)]
            per = [float(pairs[(pairs.cid == i) & (pairs[tcol] >= lo) & (pairs[tcol] <= hi)].lots.sum()) for i in act]
            rows.append(dict(und=und, version=ver, day=day, time=hm(med), seconds=med, waves_in_cluster=len(cl), expected_lots=2 * len(cl), cycles_active=len(act), cycles_executed=int(sum(x > 0 for x in per)), avg_lots_per_active_cycle=float(np.mean(per)) if per else np.nan))
        for b in bs:
            act = [i for i in cids if (STOP[i] > b if day == 'D0' else True)]
            if not act: continue
            per = [float(pairs[(pairs.cid == i) & (pairs[tcol] >= b - 3) & (pairs[tcol] <= b + 130)].lots.sum()) for i in act]
            slots.append(dict(und=und, version=ver, day=day, mark=hm(b)[:5], seconds=b, is_15min=bool((b - 33300) % 900 == 0), cycles_active=len(act), avg_lots=float(np.mean(per)), avg_pairs=float(np.mean(per)) / 2))
A = pd.DataFrame(rows); SL = pd.DataFrame(slots); A.to_csv(f'{OUT}/bl_d0q_alltimes.csv', index=False); SL.to_csv(f'{OUT}/bl_d0q_slots.csv', index=False)
dt = A.groupby(['und', 'version', 'day']).agg(clock_times=('time', 'size'), waves=('waves_in_cluster', 'sum'), expected_lots_per_day=('expected_lots', 'sum'), avg_lots_per_active_cycle_per_day=('avg_lots_per_active_cycle', 'sum'), max_lots_in_one_clock_time=('avg_lots_per_active_cycle', 'max')).reset_index()
dt['slots_used(5-min marks with lots)'] = [int((SL[(SL.und == u) & (SL.version == v) & (SL.day == d)].avg_lots > 0.05).sum()) for u, v, d in zip(dt.und, dt.version, dt.day)]
dt['avg_lots_per_used_slot'] = [float(SL[(SL.und == u) & (SL.version == v) & (SL.day == d) & (SL.avg_lots > 0.05)].avg_lots.mean()) for u, v, d in zip(dt.und, dt.version, dt.day)]
dt.to_csv(f'{OUT}/bl_d0q_daytotals.csv', index=False); print(dt.round(2).to_string(index=False))
R['daytotals'] = dt.round(3).to_dict('records'); R['lots_per_clock_time_hist'] = {f'{u} {v} {d}': A[(A.und == u) & (A.version == v) & (A.day == d)].waves_in_cluster.value_counts().sort_index().to_dict() for u, v, d in dt[['und', 'version', 'day']].itertuples(index=False)}
R['lots_per_clock_time_hist'] = {k: {int(a): int(b) for a, b in v.items()} for k, v in R['lots_per_clock_time_hist'].items()}; rec('d0q5', R); print(R['lots_per_clock_time_hist'])
print(A[(A.und == 'NIFTY') & (A.version == 'V1') & (A.day == 'D0')].head(14).round(2).to_string(index=False))
