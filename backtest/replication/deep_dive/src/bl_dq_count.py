"""Decoding step 6 (post-hoc): is the number of entries in a candle-side (1, 2, 3+) decided at the first entry? Spearman of the count with the state at the machine's first break (market, option volume, premium, portfolio). Outputs bl_dq_count.csv, bl_summary_dq8.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
exec(open('bl_dq_tune.py').read().split("GR = [")[0])
F = pd.read_csv(f'{OUT}/bl_dq_gate_first_rows.csv'); R = {}; rows = []
# rebuild first-break minutes in the same order as bl_dq_gates (machine() per cycle) and count real entries in that candle-side after it
k = 0; cnt = []
for d in CYC:
    A = sorted(d['Afull'])
    for f, s in machine(d):
        b = (33300 + 60 * f) // 1800; n = sum(1 for a in A if (33300 + 60 * a) // 1800 == b and a >= f - 1); cnt.append(n)
F['entries_in_candle_from_break'] = cnt[:len(F)]; G = F[F.y == 1]
for v in [c for c in F.columns if c not in ('cid', 'y', 'entries_in_candle_from_break')]:
    x = G[v].values.astype(float); m = ~np.isnan(x); r, p = spearmanr(x[m], G.entries_in_candle_from_break.values[m]); rows.append(dict(variable=v, spearman=r, p=p))
C = pd.DataFrame(rows).sort_values('p'); C.round(4).to_csv(f'{OUT}/bl_dq_count.csv', index=False); print(G.entries_in_candle_from_break.value_counts().sort_index().to_dict()); print(C.round(3).head(10).to_string(index=False))
R['count_dist'] = {int(a): int(b) for a, b in G.entries_in_candle_from_break.value_counts().sort_index().items()}; R['top'] = C.head(6).round(4).to_dict('records'); R['n_tests'] = len(C); rec('dq8', R)
