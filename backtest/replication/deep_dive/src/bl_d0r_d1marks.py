"""D-1 scheduled selling per 15-minute mark (all 32 cycles): share of cycles that sell in the 3 minutes after the mark, average straddles per cycle, lots per straddle, ATM-of-previous-close share.
D-1 scheduled pairs: bl_react_pairs.csv (sched = True). Outputs bl_d0r_d1marks.csv, bl_summary_d0r4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
P = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); P = P[P.sched].copy(); cyc = P[['und', 'expiry']].drop_duplicates(); idx = pd.MultiIndex.from_frame(cyc); n = len(cyc); rows = []
for b in np.arange(33300, 55800, 900):
    inw = P[(P.te >= b - 3) & (P.te <= b + 180)]; per = inw.groupby(['und', 'expiry']).size().reindex(idx, fill_value=0)
    rows.append(dict(mark=f'{int(b // 3600):02d}:{int(b % 3600 // 60):02d}', pct_cycles_selling=float((per > 0).mean()), avg_straddles_per_cycle=float(per.mean()), min_straddles=int(per.min()), max_straddles=int(per.max()), pairs=len(inw)))
M = pd.DataFrame(rows); M.to_csv(f'{OUT}/bl_d0r_d1marks.csv', index=False)
inany = np.zeros(len(P), bool)
for b in np.arange(33300, 55800, 900): inany |= ((P.te >= b - 3) & (P.te <= b + 180)).values
full = M[(M.pct_cycles_selling >= 0.99)].mark.tolist(); part = M[(M.pct_cycles_selling > 0) & (M.pct_cycles_selling < 0.99)][['mark', 'pct_cycles_selling']].values.tolist()
skipped = M[(M.pct_cycles_selling == 0) & (M.mark >= '09:30') & (M.mark <= '14:30')].mark.tolist()
R = dict(cycles=n, pairs=len(P), pairs_per_cycle=len(P) / n, lots_per_pair=int((P.lots_ce + P.lots_pe).iloc[0]), all_1_plus_1=bool(((P.lots_ce == 1) & (P.lots_pe == 1)).all()), atm_share=float((P.strike == P.atm_prev).mean()), share_in_mark_windows=float(inany.mean()),
         full_marks=full, partial_marks=part, skipped_marks_0930_1430=skipped, straddles_per_mark_range=[float(M[M.pct_cycles_selling >= 0.99].avg_straddles_per_cycle.min()), float(M[M.pct_cycles_selling >= 0.99].avg_straddles_per_cycle.max())])
rec('d0r4', R); print({k: v for k, v in R.items()}); print(M.round(2).to_string(index=False))
