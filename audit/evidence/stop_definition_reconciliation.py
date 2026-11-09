"""Read-only reconciliation of two stop measurements (no model fitting, no change to any research code).
PR #2 (FINDINGS.md section 0, '74 % within 2 min'): per LOT, trigger = first minute high >= 1.55 x that lot's OWN entry fill (analysis/leg_stop.py,
   analysis/p1_exempt.py); 'stopped' = the next actual body buy-back of the CONTRACT at/after (trigger - 2 min) is within 2 / 15 minutes.  No one-to-one matching.
PR #3 (EXIT_ENGINE_FINDINGS.md section 5): per CONTRACT exposure, first minute high >= k x CHEAPEST open entry; answered = any buy-back of that contract in [m, m+W].
This script recomputes PR #2's definition with PR #2's own functions on the clean data, then splits it to show what drives the gap.
Run:  python3 audit/evidence/stop_definition_reconciliation.py <path to analysis/> -> audit/evidence/stop_definition_reconciliation.csv"""
import sys, os
AN = sys.argv[1] if len(sys.argv) > 1 else 'analysis'
sys.path.insert(0, os.path.abspath(AN)); sys.path.insert(0, os.path.join(os.path.abspath(AN), 'exit_engine'))
import numpy as np, pandas as pd
from leg_stop import lots_and_exits, simulate          # PR #2 functions, unchanged
from load import load_tagged
C = os.path.join(os.path.abspath(AN), '_cache')
d = load_tagged(); o = pd.read_pickle(os.path.join(C, 'opt_candles.pkl')).set_index(['und', 'expiry', 'cp', 'strike']).sort_index()
lots, exits = lots_and_exits(d, lambda r: r.dte >= 1)
pl = simulate(lots, o, 1.55, 'h').dropna(subset=['pred']).copy()
ex = {k: sorted(g.t.tolist()) for k, g in exits.groupby('ks')}
dl = []
for r in pl.itertuples():
    nxt = [a for a in ex.get(r.ks, []) if a >= r.pred - pd.Timedelta(minutes=2)]
    dl.append((nxt[0] - r.pred).total_seconds() / 60 if nxt else np.inf)
pl['dl'] = dl
pl = pl.sort_values(['ks', 'pred']); pl['rank_in_contract'] = pl.groupby('ks').cumcount()
first = pl[pl.rank_in_contract == 0]; later = pl[pl.rank_in_contract > 0]
uniq = pl.drop_duplicates(['ks', 'pred'])
rows = []
def add(name, df, note):
    rows.append(dict(measure=name, n_events=len(df), within_2min=float((df.dl <= 2).mean()), within_15min=float((df.dl <= 15).mean()),
                     exit_before_trigger_share=float((df.dl < 0).mean()), note=note))
add('PR #2 as published (every lot, own entry, window opens 2 min before the trigger)', pl, 'reproduces the ~74 % / ~82 % family of numbers on the clean order data')
add('  same, only the FIRST crossing of each contract', first, 'one event per contract-day; the first crossing is the lowest-entry lot, i.e. the cheapest-entry reference')
add('  same, only LATER lots of a contract already crossed', later, 'follow-on lots whose own-entry level is crossed after the first one')
add('  same, one event per contract-minute (shared triggers removed)', uniq, 'removes lots that cross in the same minute')
st = pl[pl.dl >= 0]
add('  same, but exits before the trigger minute not credited', st, 'strict window [trigger, ...]')
fs = first[first.dl >= 0]
rows.append(dict(measure='  same, FIRST crossing only, exits before the trigger minute not credited', n_events=len(first), within_2min=float(((first.dl >= 0) & (first.dl <= 2)).mean()),
                 within_15min=float(((first.dl >= 0) & (first.dl <= 15)).mean()), exit_before_trigger_share=0.0, note='closest to the PR #3 definition (one event per exposure, cheapest-entry reference, window [m, m+W])'))
fp = pd.read_pickle(os.path.join(C, 'fp_events.pkl')); fp = fp[(fp.ref == 'cheap') & (fp.basis == 'high') & (fp.k == 1.55) & (fp.segment == 'D-1 fresh')]
t = fp.min_to_next_exit.where(fp.min_to_next_exit >= 0, np.inf)
rows.append(dict(measure='PR #3 first passage (cheapest open entry x 1.55, minute high, D-1 fresh, any buy-back of the contract), all 35 cycles', n_events=len(fp),
                 within_2min=float((t <= 2).mean()), within_15min=float((t <= 15).mean()), exit_before_trigger_share=0.0, note='from analysis/_cache/fp_events.pkl (clean build); minutes, not seconds'))
pd.DataFrame(rows).to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stop_definition_reconciliation.csv'), index=False)
pd.set_option('display.width', 220); pd.set_option('display.max_colwidth', 80)
print(pd.DataFrame(rows).round(3).to_string(index=False))
print('lots with a crossing:', len(pl), '| contract-days:', pl.ks.nunique(), '| mean lots per contract-day crossing:', round(len(pl) / pl.ks.nunique(), 2))
