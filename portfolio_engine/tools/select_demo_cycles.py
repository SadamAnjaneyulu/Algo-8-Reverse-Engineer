"""Demonstration-cycle selection per docs/DEMO_CYCLE_SELECTION.md (criteria frozen before this script was run). Uses source availability and reconstruction quality only.
ALGO8_MARKET_DIR=... python3 portfolio_engine/tools/select_demo_cycles.py"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE)
sys.path.insert(0, os.path.join(REPO, 'tp_reconstruction', 'scripts')); import market_data as md
TP = os.path.join(REPO, 'tp_reconstruction')
L = pd.read_parquet(os.path.join(TP, 'data', 'fill_event_ledger.parquet')); R = pd.read_parquet(os.path.join(TP, 'data', 'fill_roles.parquet')); R = R[R.method == 'FIFO'][['src_row', 'close_qty', 'open_qty']]
raw = pd.read_csv(os.path.join(REPO, 'Trades_GKOHNP140.csv'), header=None, dtype=str, keep_default_na=False, usecols=[163, 166]); L['app_key_full'] = raw[166].values
L = L.merge(R, on='src_row'); L['cycle'] = L.und + '|' + L.expiry.dt.strftime('%Y-%m-%d')
E = pd.read_parquet(os.path.join(TP, 'data', 'position_episodes.parquet')); E = E[E.method == 'FIFO']; E['cycle'] = E.und + '|' + E.expiry.dt.strftime('%Y-%m-%d')
M = pd.read_parquet(os.path.join(TP, 'tp02', 'data', 'exit_event_mechanisms.parquet'), columns=['close_row', 'candidate_mechanism']).set_index('close_row')
W = pd.read_parquet(os.path.join(TP, 'tp03', 'data', 'p1_window_dataset.parquet'), columns=['cycle', 'kind', 'window'])
O = md.option_bars(); have = set(zip(O.contract_id.values, O.ts.values.astype('datetime64[m]').astype('int64')))
def md_table(df):
    h = '| ' + ' | '.join(df.columns) + ' |'; sep = '|' + '---|' * len(df.columns); body = ['| ' + ' | '.join(f'{v:.4f}' if isinstance(v, float) else str(v) for v in r) + ' |' for r in df.itertuples(index=False)]
    return '\n'.join([h, sep] + body)


rows = []
for cy, g in L.groupby('cycle'):
    sessions = g.date.nunique(); exp = g.expiry.iloc[0]; d1 = (g.date < exp).any(); d0 = (g.date == exp).any()
    c1 = 1 - (g.dq_flag_any | g.tie_group_mixed_side).mean()
    pr = g.drop_duplicates('parent_oid'); c2 = ((pr.order_entry_minute.notna()) & (pr.order_no != '') & (pr.app_key_full != '')).mean()
    e = E[E.cycle == cy]; opened = e.opened_units.sum(); unsettled = e[e.remaining_status == 'EXPIRED_UNCLOSED'].remaining_units.sum(); c3 = 1 - unsettled / opened
    mins = g.t_fill.values.astype('datetime64[m]').astype('int64'); c4 = np.mean([(c, m) in have for c, m in zip(g.contract_id.values, mins)])
    cl = g[g.close_qty > 0]; c5a = cl.src_row.map(lambda r: r in M.index and pd.notna(M.candidate_mechanism.get(r))).mean(); c5b = len(W[W.cycle == cy]) / 44; c5 = (c5a + c5b) / 2
    c6 = 1.0 if (d1 and d0) else 0.0
    rows.append(dict(cycle=cy, und=g.und.iloc[0], expiry=exp.strftime('%Y-%m-%d'), eligible=bool(d1 and d0), fills=len(g), C1_fill_coverage=c1, C2_parent_metadata=c2, C3_reconciliation=c3, C4_option_marks=c4, C5_classification=c5, C6_d1_d0=c6))
T = pd.DataFrame(rows); T['score'] = T[[c for c in T.columns if c.startswith('C')]].mean(axis=1)
out = os.path.join(PE, 'reports'); T.sort_values(['und', 'expiry']).to_csv(os.path.join(out, 'demo_cycle_scores.csv'), index=False, float_format='%.6f')
note = ['# Demonstration-cycle selection note (frozen)', '', 'Criteria: `docs/DEMO_CYCLE_SELECTION.md`, committed before this script was run. Inputs: source availability and reconstruction quality only. Eligibility: fills on D-1 and D0. Score = mean of C1–C6; tie-break earlier expiry. No grouping output, P&L or chart was examined.', '']
for und in ('NIFTY', 'SENSEX'):
    t = T[(T.und == und) & T.eligible].sort_values(['score', 'expiry'], ascending=[False, True]); sel = t.iloc[0]
    note += [f'## {und}: SELECTED `{sel.cycle}` (score {sel.score:.4f}, {int(sel.fills)} fills)', '', 'Runner-ups: ' + '; '.join(f'`{r.cycle}` ({r.score:.4f})' for r in t.iloc[1:4].itertuples()), '', md_table(t.head(4)[['cycle', 'fills', 'C1_fill_coverage', 'C2_parent_metadata', 'C3_reconciliation', 'C4_option_marks', 'C5_classification', 'C6_d1_d0', 'score']]), '']
    print(und, sel.cycle, round(sel.score, 4))
ineligible = T[~T.eligible].cycle.tolist(); note += [f'Ineligible (missing D-1 or D0 fills): {", ".join(ineligible) if ineligible else "none"}', '', 'Full table: `demo_cycle_scores.csv`. **Frozen: not to be rerun after grouping results exist.**']
open(os.path.join(out, 'DEMO_CYCLE_SELECTION_NOTE.md'), 'w').write('\n'.join(note) + '\n')
