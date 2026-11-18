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

# ---- population reconciliation (added after review): why 194 PR #2 first crossings vs 438 PR #3 events -------------------------------------------
allfp = pd.read_pickle(os.path.join(C, 'fp_events.pkl'))
allfp['ks'] = allfp.und + '|' + allfp.expiry.dt.date.astype(str) + '|' + allfp.cp + '|' + allfp.strike.astype(int).astype(str)
base = allfp[(allfp.ref == 'cheap') & (allfp.basis == 'high') & (allfp.k == 1.55)]
fp1 = base[base.segment == 'D-1 fresh']; f3 = fp1.sort_values('mi').groupby('ks').head(1).copy()
f2 = pl.groupby('ks').head(1).copy()                                  # PR #2 first crossing per contract (pl is sorted by ks, pred)
common = set(f2.ks) & set(f3.ks)
sells = {k: sorted(g.t0.tolist()) for k, g in lots.groupby('ks')}; buys = {k: sorted(g.t.tolist()) for k, g in exits.groupby('ks')}
openn = lambda ks, t: sum(1 for x in sells.get(ks, []) if x <= t) - sum(1 for x in buys.get(ks, []) if x <= t)
pl['open_lots_at_trigger'] = [openn(r.ks, r.pred) for r in pl.itertuples()]; f2['open_lots_at_trigger'] = [openn(r.ks, r.pred) for r in f2.itertuples()]
strict = lambda x: x.where(x >= 0, np.inf)
def prow(name, x, n, note):
    rows.append(dict(measure=name, n_events=n, within_2min=float((x <= 2).mean()), within_15min=float((x <= 15).mean()), exit_before_trigger_share=0.0, note=note))
prow('POPULATION: PR #3 D-1 fresh events at k=1.55 (438 events)', strict(fp1.min_to_next_exit), len(fp1), f'{len(fp1)} events come from {fp1.ks.nunique()} contracts ({len(fp1) / fp1.ks.nunique():.2f} per contract): PR #3 emits repeated crossing events per contract')
prow('POPULATION: PR #3 first event per contract (151 contracts)', strict(f3.min_to_next_exit), len(f3), 'one event per contract; directly comparable with PR #2 first crossing per contract')
a = f2[f2.ks.isin(common)].copy(); a['x'] = strict(a.dl)
prow('POPULATION: PR #2 first crossing per contract, strict, restricted to the same 151 contracts', a.x, len(a), f'same contract set as above; same trigger minute in {int(((a.set_index("ks").pred.dt.hour * 60 + a.set_index("ks").pred.dt.minute - 555) == f3.set_index("ks").mi.reindex(a.ks).values).sum())} of {len(a)}')
o2 = f2[~f2.ks.isin(common)].copy(); o2['x'] = strict(o2.dl)
prow('POPULATION: PR #2 first-crossing contracts absent from PR #3 D-1 fresh (43 contracts)', o2.x, len(o2), f'{int((o2.open_lots_at_trigger <= 0).sum())} of {len(o2)} had NO open lot in the contract at the trigger minute (PR #2 does not check that the lot is still open)')
rows.append(dict(measure='POPULATION: PR #2 lot events with no open lot in the contract at the trigger minute', n_events=int((pl.open_lots_at_trigger <= 0).sum()), within_2min=np.nan, within_15min=np.nan, exit_before_trigger_share=np.nan,
                 note=f'of {len(pl)} lot events; first-crossing contracts with no open lot: {int((f2.open_lots_at_trigger <= 0).sum())} of {len(f2)}'))
pd.DataFrame(rows).to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stop_definition_reconciliation.csv'), index=False)
print(pd.DataFrame(rows).tail(6).round(3).to_string(index=False))
