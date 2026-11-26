"""Builds reports/D1_FORWARD.md from bl_fwd.csv and bl_fwd_classes.csv."""
import sys, os; sys.path.insert(0, '.')
import pandas as pd
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); F = pd.read_csv(f'{OUT}/bl_fwd.csv'); C = pd.read_csv(f'{OUT}/bl_fwd_classes.csv'); O = pd.read_csv(f'{OUT}/bl_fr2_overall.csv').iloc[0]
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
a, b = F.iloc[0], F.iloc[1]
t = pd.DataFrame([[r.split, r.train_cycles, r.test_cycles, f'{r.F1_forward:.3f}', f'{r.precision_forward:.0%}', f'{r.recall_forward:.0%}', f'{r.F1_within1_forward:.3f}', f'{r.F1_out_of_fold_same_cycles:.3f}', f'{r.AUC_any_forward:.3f}', f'{r.AUC_any_out_of_fold_same_cycles:.3f}'] for r in F.itertuples()],
                 columns=['split', 'cycles learned from', 'unseen cycles', 'lot F1 (timing)', 'precision', 'recall', 'F1 + strike within one', 'F1 out-of-fold, same cycles', 'AUC any activity', 'AUC out-of-fold, same cycles'])
cl = C.pivot(index='cls', columns='split', values='F1').round(3).reset_index()
txt = f"""# Algo 8 — complete D-1 reconstruction on unseen cycles (forward test)

*The rules are applied to cycles whose data were **not** used to fit anything. In-sample caveat: the rule **structure** was designed after looking at all 32 cycles, so even these forward numbers are somewhat optimistic for genuinely new data.*

## 0. Result
| Measure | On unseen cycles | Earlier figure (all cycles, out-of-fold) |
|---|---|---|
| **Lot-level accuracy (F1, ±1 min)** | **{a.F1_forward:.2f}** same version · **{b.F1_forward:.2f}** after a version change | {O.F1:.2f} |
| Precision / recall | {a.precision_forward:.0%} / {a.recall_forward:.0%} | 78% / 62% |
| **AUC (any D-1 activity, minute × right)** | **{a.AUC_any_forward:.2f}** same version · **{b.AUC_any_forward:.2f}** after a version change | 0.96–0.98 |

**Expected range on new cycles:** lot-level F1 about **0.60–0.65** and AUC about **0.90–0.92**, if the system keeps its configuration. If it changes version again (as it did on 2026-09-16), these hold up surprisingly well (0.62 / 0.91), because most of the scheduled timetable and every decoded trigger carried over. The real risks are new timetables, new lump time windows and new modules.

## 1. Setup
* **A, same version:** within V1 the first 14 cycles are learned from and the last 7 tested; within V2, the first 7 and the last 4. Everything is learned from the training cycles only: the scheduled timetable (minutes with a scheduled sale in ≥ 50% of training cycles), the lump time (the regime of the latest training cycle; config changes are not given), reactive size and extras, the buy-back stop θ, lump ratio, opening-wing offset, and the AUC model with its timetable share.
* **B, version change:** learned from all 21 V1 cycles and tested on all 11 V2 cycles, applying the **V1 timetable** to V2.
* Test cycles include the stop-out cycle and the deep-OTM batch cycle, which makes them harder (more not-modelled lots).

## 2. Scores
{table(t)}

## 3. By class (unseen cycles, lot F1)
{table(cl)}

## 4. What the numbers mean
* About **63%** of D-1 lot decisions are reproduced in the right minute (±1) and on the right side on unseen cycles. About **59%** also have the strike within one step.
* AUC about **0.92** means the reconstruction ranks the minutes where the real system acts far above the rest, on days it has not seen.
* The drop from the in-sample figures (F1 0.69 → 0.63, AUC 0.97 → 0.92) is the honest cost of new data.
* A truly independent check needs new live cycles (after 2026-10-22) scored with the rules frozen now.

## Evidence labels
* **Observed:** executed forward tests.
* **Not testable here:** genuinely new cycles, i.e. future data.
* For split A, the lump time came from the latest training cycle overall, a V2 cycle. Some V1 test cycles had an earlier lump regime, so their lump scores are conservative.
"""
open(f'{RP}/D1_FORWARD.md', 'w').write(txt); print('ok')
