"""Experiment ledger for the frozen late-sale rule (reports/EXPERIMENT_LEDGER.md). Reconstructed from git history, scripts and saved result tables; unrecoverable items are marked.
Output outputs/audit/experiment_ledger.csv, script_inventory.csv and the markdown report (written by this script so the table and the csv cannot diverge)."""
import sys, os, re, glob, subprocess, ast, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); AU = f'{OUT}/audit'; REP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reports')
def nrows(p):
    try: return len(pd.read_csv(f'{OUT}/{p}'))
    except Exception: return None
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))).stdout
# ---------------- script inventory (every script in src, with the date it first entered git and its docstring's first line)
added = {}; cur = None
for l in sh("git log --diff-filter=A --name-only --format='@%ad' --date=short -- .").splitlines():
    if l.startswith('@'): cur = l[1:]
    elif l.strip().endswith('.py'): added[os.path.basename(l.strip())] = cur
rows = []
for f in sorted(glob.glob('*.py')):
    try: doc = (ast.get_docstring(ast.parse(open(f).read())) or '').split('\n')[0][:160]
    except Exception: doc = ''
    rows.append(dict(script=f, first_in_git=added.get(f), doc=doc))
pd.DataFrame(rows).to_csv(f'{AU}/script_inventory.csv', index=False)
inv = pd.DataFrame(rows); late_scripts = inv[inv.script.str.match(r'bl_(late|trig|x_|cas_|clr|unmatched|fwd|bt3x|bt3s|bt3u|d0x)')]
# ---------------- curated ledger
n_auc = sum(nrows(f'trig/{f}') or 0 for f in ('auc_after.csv', 'auc_after_with_outlier.csv', 'auc_before.csv', 'auc_before_with_outlier.csv')); n_lag = sum(nrows(f'trig/{f}') or 0 for f in ('auc_after_lag1.csv', 'auc_before_lag1.csv'))
L = [
 ('E00', 'D-1 engine', 'The D-1 rules (timetable, breakout, ladder gate 60 / step 0.2, strike window 4, stops, wings, lump) reproduce the real log', 'algo8_d1.Config defaults', '32 observed real cycles (Jun-Oct 2026; contains all 18 post-auction development cycles)', 'same 32', 'fit to the real log (decision match)', 'order-level match', 'UNRECOVERABLE (fitting iterations before 2026-11-23 are not preserved as experiments; Config docstring says "fitted on the 32 observed cycles")', 'YES: the ladder skeleton of the frozen rule (step 0.2, strike window, reference logic) comes from here; only gate (60 -> 5) and underlying (index -> future) were changed later'),
 ('E01', 'late rule', 'Late D-1 strike and side follow simple rules', f'13 rules (7 strike, 5 side, 1 base rate), 2 eras, exact/within-1-step; {nrows("late/rule_scores.csv")} saved numbers', '21 post-auction + 11 pre-auction cycles', 'same (teacher-forced, leave-one-cycle-out for constants)', 'highest exact match; no formal selection', 'exact match rate', 'S_LAST 0.54, S_PREM 0.51, D_TREND 0.68 vs 0.56', 'INDIRECT: strike rule not frozen; trend-side idea fed the ladder hypothesis'),
 ('E02', 'late rule', 'Shortening the ladder gate G explains late timing', f'G in {{5,10,15,30,60}} on the published index; {nrows("late/trigger_scores.csv")} saved score rows', '32 cycles', 'same, leave-one-cycle-out choice of G', 'F1 by LOCO', 'event F1', 'no gain (0.46 vs 0.47)', 'INDIRECT: first look at G=5 (later retested on other underlyings)'),
 ('E03', 'late rule', 'Real late sales are worth money inside the simulator', '4 cut-offs (none, 15:15, 15:00, 14:15) x 30 cycles', '30 cycles', 'same', 'none (descriptive)', 'P&L difference', 'mean +15k to +65k, median ~0-9k', 'NO'),
 ('E04', 'closing session', 'Cache to 15:39 and Fix A (breakout window to session end) improve fidelity', '3 variants (base, X, XA)', '19 post-auction cycles', 'same', 'decision match then P&L', 'precision/recall, P&L with flips', 'Fix A rejected', 'NO'),
 ('E05', 'closing session', 'Which underlying does the real system trade after 15:15', '6 variants (X, XF, XS, XU, XSA, XUA)', '19 post-auction cycles', 'same', 'decision match (precision/recall, bootstrap)', 'late-sale F1 vs real', 'frozen index falsified; XS/XU similar', 'YES: introduced FUT and OPT as the candidate underlyings'),
 ('E06', 'D0 clearance', 'Real D0 clearance minute is later before 3 Aug', 'clear_j in {359, 364}, LOCO constant, free-run era regime; 30 cycles x 2 + 11', '30 cycles', 'same', 'share of real covers by the minute; P&L last', 'decision share, MAE', '15:19 before 3 Aug; adopted opt-in', 'NO (clearance is not part of the late rule)'),
 ('E07', 'late rule', 'Late D-1 sale timing is explained by features of the underlying', f'43 scores x 4 runs = {n_auc} AUC tests + {n_lag} lag-1 tests + 4 nested combination models (pre-registered in the plan file before the tests ran)', '18 post + 11 pre cycles', 'same (nested leave-one-cycle-out)', 'BH-FDR 10%; combination vs clock baseline', 'stratified AUC; delta AUC vs clock', 'FUT +0.067 [0.002, 0.131]; FEED, OPT no gain', 'YES: identified FUT and the feature families'),
 ('E08', 'late rule', 'Directional features beat the clock; FUT beats FEED', '27 paired comparisons, 12 side-split numbers, 6 directional nested models (3 underlyings x 2 windows); post-hoc, counted', '18 post cycles', 'same', 'BH-FDR; delta AUC vs clock with clock forced in', 'stratified AUC', 'FUT +0.088 [0.015, 0.158]; 1 of 27 comparisons significant', 'YES: chose FUT_ext5, FUT_mv1 as the frozen features'),
 ('E09', 'late rule', 'Ladder gate G on each underlying matches real late sales', '20 combinations (4 era-underlying groups x 5 gates) x 18 cycles', '18 post + 11 pre', 'same, LOCO choice of G', 'F1 by LOCO', 'event F1', 'G=5 chosen in 17/18 folds on FUT; dF1 +0.03 [-0.06, +0.16]', 'YES: the frozen gate is 5'),
 ('E10', 'freeze', 'Freeze the candidate score', '3 features (FUT_ext5, FUT_mv1, clock), L2 logistic fitted on ALL 18 development cycles; OOF evaluation uses the pre-chosen features without re-selecting them', '18 post cycles', 'same cycles (leave-one-cycle-out, not chronological)', 'features chosen from E07-E09', 'delta AUC vs clock', 'OOF +0.098 (feature choice leaks)', 'YES: it IS the frozen score'),
 ('E11', 'power', 'How many forward cycles are needed', '2 analyses (F1 test, AUC test), resampling the 18 development cycles', '18 cycles', 'same cycles for effect and variance', 'none', 'power', '30 cycles: 94% / 42%', 'NO'),
 ('E12', 'late rule', 'Anatomy of unmatched late sales', 'descriptive, 148 orders', '17 cycles', 'same', 'none', 'order recall', '66% order-level, 54% of misses in pairs', 'NO'),
 ('E13', 'battery', 'Tuning the simulator has out-of-sample value', '61 variants run, 41 enter the PBO matrix; DSR counts N = 83 configurations', '275 cycles, 158 weeks', 'CSCV 16 blocks', 'PBO < 0.5', 'PBO, DSR', 'PBO 0.60; DSR 1.00', 'NO (different object: whole-simulator tuning)'),
 ('E14', 'earlier history', 'Alpha thesis, premium mechanisms, design thesis, margin, unresolved three, entry/exit/sizing diagnostics, ML exit controllers, 22-branch knowledge graph', '435 scripts / 128 reports / 55 plan files in deep_dive; 314 commits (2026-10-24 to 2026-11-24)', 'real log and 3-year cache', 'various', 'various', 'various', 'UNRECOVERABLE at hypothesis level: the number of hypotheses tested is not recorded as a count anywhere; script_inventory.csv lists every script', 'INDIRECT: shaped what was considered'),
]
D = pd.DataFrame(L, columns=['id', 'line', 'hypothesis', 'features_and_parameters', 'development_sample', 'evaluation_sample', 'selection_criteria', 'primary_metric', 'result', 'influenced_final_rule']); D.to_csv(f'{AU}/experiment_ledger.csv', index=False)
md = ['# Experiment ledger', '', '*Reconstructed 2026-11-24 from git history, scripts and saved result tables (`src/bl_audit_ledger.py`; csv: `outputs/audit/experiment_ledger.csv`, `script_inventory.csv`). Nothing was deleted from the history. "UNRECOVERABLE" marks information that was not preserved.*', '',
      f'**Repository facts:** {sh("git log --oneline | wc -l").strip()} commits on this lineage (first {sh("git log --reverse --format=%ad --date=short | head -1").strip()}, last {sh("git log -1 --format=%ad --date=short").strip()}); {len(inv)} scripts in `deep_dive/src`, of which {len(late_scripts)} belong to the late-rule / closing-session / forward-test lineage; {len(glob.glob(REP + "/*.md"))} reports, {len(glob.glob(REP + "/*PLAN*.md"))} of them plans.', '',
      '| ID | Line | Hypothesis | Features / parameters | Development sample | Evaluation sample | Selection | Primary metric | Result | Influenced the frozen rule? |', '|---|---|---|---|---|---|---|---|---|---|']
for r in L: md.append('| ' + ' | '.join(str(x).replace('|', '/') for x in r) + ' |')
tests = n_auc + n_lag + 27 + 12 + 6 + 20
md += ['', '## Counts that matter for selection bias',
       f'* **Distinct late-rule variants evaluated on the development labels** (E01 13 rules, E02 5 gates, E04 3, E05 6, E06 3, E07 43 scores, E08 27 comparisons + 6 models, E09 20 gate x underlying combinations): **{13 + 5 + 3 + 6 + 3 + 43 + 27 + 6 + 20} distinct variants**, before counting the replicates across eras and with/without the outlier.',
       f'* **Saved test results in the trigger line alone** (E07-E09): {tests} numbers ({n_auc} AUC + {n_lag} lag-1 + 27 + 12 + 6 + 20).',
       '* **Every one of them used the same 18 post-auction development cycles** (and 11 pre-auction cycles for the era comparison). There was **no untouched evaluation set**: nested leave-one-cycle-out protects feature weights from the held-out cycle but not the choice of *what to try*.',
       '* **The final three-feature score was selected after seeing these results** (E07-E09 chose FUT, then ext5 and mv1, then gate 5). The OOF figure in E10 therefore leaks the feature choice.',
       '* **The frozen rule\'s skeleton (E00) was fitted on the 32 observed cycles that contain the development cycles.**',
       '* **Unrecoverable:** E00 fitting iterations; E14 hypothesis count (hundreds of scripts, no count recorded); interactive profiling queries run while exploring (not saved as scripts). The true number of looks at the development data is therefore **larger than the counts above**.', '',
       '## What the ledger says about independence', 'Nothing in the ledger is independent confirmation of the frozen rule. The 18 development cycles are development data in the strict sense, as the pre-registration says. The only independent evidence will be the confirmatory forward sample.']
open(f'{REP}/EXPERIMENT_LEDGER.md', 'w').write('\n'.join(md) + '\n'); print(len(inv), len(late_scripts), 'variants', 13 + 5 + 3 + 6 + 3 + 43 + 27 + 6 + 20, 'tests', tests)
