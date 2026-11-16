"""Stage 1 descriptive data audit for the skeleton / take-profit project (read-only; no thresholds are fitted).
Reads the clean column-163 caches built by PR #3 (analysis/_cache) and writes counts to algo8_skeleton/results/.
python3 algo8_skeleton/stage1_audit.py"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE); C = os.path.join(REPO, 'analysis', '_cache')
RES = os.path.join(HERE, 'results'); os.makedirs(RES, exist_ok=True)
sys.path.insert(0, os.path.join(REPO, 'analysis'))
from exit_engine.common import split_of

o = pd.read_pickle(os.path.join(C, 'exit_orders.pkl'))
lines = []
P = lambda *a: lines.append(' '.join(str(x) for x in a))
P('orders', len(o), 'fills', int(o.n_fills.sum()), 'cycles', o.groupby(['und', 'expiry']).ngroups)
P('orders by module', o.tp.value_counts().to_dict())
cyc = o.groupby(['und', 'expiry']).agg(sessions=('date', 'nunique'), first=('date', 'min'), orders=('oid', 'size')).reset_index()
cyc['split'] = cyc.expiry.map(split_of)
cyc['has_D-1'] = cyc['first'] < cyc.expiry
cyc.to_csv(os.path.join(RES, 'stage1_cycles.csv'), index=False)
P('cycles by split', cyc.split.value_counts().to_dict(), '| cycles with a D-1 session', int(cyc['has_D-1'].sum()), 'of', len(cyc))

rows = []
for conv in ('cheap', 'fifo', 'lifo'):
    x = pd.read_pickle(os.path.join(C, f'exit_lots_{conv}.pkl'))
    P(conv, 'unit lots', len(x), 'short', int((x.sgn < 0).sum()), 'long', int((x.sgn > 0).sum()),
      'short open at end of export', int(((x.sgn < 0) & x.exit_oid.isna()).sum()), 'long open', int(((x.sgn > 0) & x.exit_oid.isna()).sum()))
    s = x[(x.sgn < 0) & x.exit_oid.notna()].copy()
    s['exit_day'] = np.where(s.exit_t.dt.normalize() == s.expiry, 'D0', 'D-1')
    s['segment'] = np.where(s.exit_day == 'D-1', 'D-1 entry, D-1 exit', np.where(s.carried, 'D-1 entry carried, D0 exit', 'D0 entry, D0 exit'))
    s['below_own_entry'] = s.exit_px < s.entry_px
    g = s.groupby(['segment', 'split']).agg(lots=('below_own_entry', 'size'), share_exit_below_own_entry=('below_own_entry', 'mean')).reset_index()
    g['convention'] = conv; rows.append(g)
    if conv == 'cheap':
        P('short lots opened by non-body modules (entry_tp):', s.entry_tp.value_counts().to_dict())
        lab = s.groupby('exit_label').agg(lots=('below_own_entry', 'size'), share_below_own_entry=('below_own_entry', 'mean')).sort_values('lots', ascending=False)
        lab.round(3).to_csv(os.path.join(RES, 'stage1_short_exits_by_existing_label_cheap.csv'))
seg = pd.concat(rows); seg.round(3).to_csv(os.path.join(RES, 'stage1_short_exit_segments.csv'), index=False)
P('\nshare of closed short lots bought back below their assigned entry (descriptive; NOT a take-profit test):')
P(seg.groupby(['convention', 'segment']).apply(lambda g: pd.Series({'lots': g.lots.sum(), 'share': np.average(g.share_exit_below_own_entry, weights=g.lots)}), include_groups=False).round(3).to_string())
open(os.path.join(RES, 'stage1_audit.txt'), 'w').write('\n'.join(lines) + '\n'); print('\n'.join(lines))
