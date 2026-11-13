"""TP-03 Phase 1: E1 (schedule), E3 descriptive ladder (gross vs net), testability table, ENT-04 off-window description, view reconciliation.  Descriptive only: no p-values here."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as tc, entry_common as ec
tc.assert_frozen(); A = tc.ANALYSIS
W = pd.read_parquet(os.path.join(tc.DATA, 'p1_window_dataset.parquet')); O = pd.read_csv(os.path.join(A, 'p1_off_window_events.csv'), parse_dates=['order_entry_minute', 'first_fill', 'date'])
BASE = ec.BASE


def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return (c - h, c + h)


def counts(g, v):
    c = g[f'view{v}_class'].value_counts(); a = int(c.get('ACTION', 0)); q = int(c.get('NO_ACTION_ACTIVE', 0)); u = int(c.get('NO_ACTION_UNCERTAIN', 0)); amb = int(c.get('AMBIGUOUS_ACTION', 0)); oth = int(c.get('ACTION_OTHER_CLASS', 0)); na = int(c.get('NOT_APPLICABLE', 0))
    den = a + q + u; lo, hi = wilson(a, den)
    return dict(session_windows=len(g), ACTION=a, NO_ACTION_ACTIVE=q, NO_ACTION_UNCERTAIN=u, AMBIGUOUS_ACTION=amb, ACTION_OTHER_CLASS=oth, NOT_APPLICABLE=na, rate_denominator=den, action_rate=a / den if den else np.nan, wilson_lo=lo, wilson_hi=hi, unconditional_rate=a / len(g) if len(g) else np.nan)


# ---------------- E1 per window x view
rows = []
for (k, w), g in W.groupby(['kind', 'window']):
    for v in (1, 2, 3): rows.append(dict(kind=k, window=w, control_window=bool(g.control_window.iloc[0]), view=f'V{v}', **counts(g, v)))
E1w = pd.DataFrame(rows); E1w.to_csv(os.path.join(A, 'p1_e1_window_rates.csv'), index=False)
rows = []
P = W[W.kind == 'PRE']
for name, g in (('PRE registered 17 windows', P[~P.control_window]), ('PRE control 4 windows', P[P.control_window]), ('PRE all 21 candidate windows', P), ('PRE all 21 NIFTY', P[P.und == 'NIFTY']), ('PRE all 21 SENSEX', P[P.und == 'SENSEX']),
                ('PRE registered 17 NIFTY', P[(~P.control_window) & (P.und == 'NIFTY')]), ('PRE registered 17 SENSEX', P[(~P.control_window) & (P.und == 'SENSEX')]), ('D0 all 23 windows', W[W.kind == 'D0']), ('D0 NIFTY', W[(W.kind == 'D0') & (W.und == 'NIFTY')]), ('D0 SENSEX', W[(W.kind == 'D0') & (W.und == 'SENSEX')])):
    for v in (1, 2, 3): rows.append(dict(group=name, view=f'V{v}', **counts(g, v)))
E1a = pd.DataFrame(rows); E1a.to_csv(os.path.join(A, 'p1_e1_aggregates.csv'), index=False)
NA = W[(W.view2_class.isin(['NO_ACTION_ACTIVE', 'NO_ACTION_UNCERTAIN'])) | (W.view3_class == 'AMBIGUOUS_ACTION') | (W.view2_class == 'ACTION_OTHER_CLASS')][['cycle', 'und', 'kind', 'window', 'control_window', 'view1_class', 'view2_class', 'view3_class', 'n_parents_ambiguous', 'n_other_class_openings', 'minutes_to_expiry', 'adds_so_far', 'short_units_at_snapshot', 'cycle_mtm', 'spot_ret_15m_bp']]
NA.sort_values(['kind', 'cycle', 'window']).to_csv(os.path.join(A, 'p1_e1_non_action_windows.csv'), index=False)
# ---------------- testability (clarification 1)
rows = []
for k in ('PRE', 'D0'):
    for v in (2, 3):
        g = W[W.kind == k]; cl = g[f'view{v}_class']
        for outcome in ('action', 'quantity'):
            if outcome == 'action':
                m = cl.isin(['ACTION', 'NO_ACTION_ACTIVE']); n = int(m.sum()); mino = g[cl == 'NO_ACTION_ACTIVE'].groupby('und').size().reindex(['NIFTY', 'SENSEX']).fillna(0).astype(int); cyc = g[m].groupby('und').cycle.nunique().reindex(['NIFTY', 'SENSEX']).fillna(0).astype(int)
                t = tc.testability('E2_action', n, list(cyc.values), int(mino.sum()), list(mino.values)); extra = dict(minority_pooled=int(mino.sum()), minority_NIFTY=int(mino['NIFTY']), minority_SENSEX=int(mino['SENSEX']))
            else:
                m = cl == 'ACTION'; n = int(m.sum()); cyc = g[m].groupby('und').cycle.nunique().reindex(['NIFTY', 'SENSEX']).fillna(0).astype(int); t = tc.testability('E2_quantity', n, list(cyc.values)); extra = {}
            rows.append(dict(design=k, view=f'V{v}', outcome=outcome, N=n, cycles_NIFTY=int(cyc['NIFTY']), cycles_SENSEX=int(cyc['SENSEX']), testable=t['testable'], reasons='; '.join(t['reasons']), rule=t['rule'], **extra))
T = pd.DataFrame(rows); T.to_csv(os.path.join(A, 'p1_testability.csv'), index=False)
# ---------------- E3 descriptive: ladder by window, gross opening vs net short change, per right
D = ec.Data(); RF = D.RF; body_sell = RF[(RF.sgn < 0) & (RF.open_qty > 0)]; cover_buy = RF[(RF.sgn > 0) & (RF.close_qty > 0)]
def window_flows(r):
    t = pd.Timestamp(r.date) + pd.Timedelta(hours=int(r.window[:2]), minutes=int(r.window[3:])); w0, w1 = t - ec.B0, t + ec.B1
    s = body_sell[(body_sell.und == r.und) & (body_sell.expiry == r.expiry) & (body_sell.t_fill >= w0) & (body_sell.t_fill < w1)]; c = cover_buy[(cover_buy.und == r.und) & (cover_buy.expiry == r.expiry) & (cover_buy.t_fill >= w0) & (cover_buy.t_fill < w1)]
    return pd.Series(dict(gross_short_open_units=s.open_qty.sum() / BASE[r.und], short_cover_units=c.close_qty.sum() / BASE[r.und]))
WF = pd.concat([W[['cycle', 'und', 'expiry', 'kind', 'date', 'window', 'view2_class', 'Q_v2', 'Q_v3', 'view3_class']].reset_index(drop=True), W.apply(window_flows, axis=1)], axis=1) if False else None
fl = W.apply(window_flows, axis=1); WF = pd.concat([W[['cycle', 'und', 'kind', 'window', 'view2_class', 'view3_class', 'Q_v2', 'Q_v3', 'Q_CE_v2', 'Q_PE_v2']].reset_index(drop=True), fl.reset_index(drop=True)], axis=1); WF['net_short_change_units'] = WF.gross_short_open_units - WF.short_cover_units
WF.to_csv(os.path.join(A, 'p1_e3_window_flows.csv'), index=False)
rows = []
for k in ('PRE', 'D0'):
    for v in (2, 3):
        a = WF[(WF.kind == k) & (WF[f'view{v}_class'] == 'ACTION')]
        for w, g in a.groupby('window'):
            q = g[f'Q_v{v}']; vc = q.value_counts(); mode = vc.index[0]; reg = (k == 'PRE')
            rows.append(dict(kind=k, view=f'V{v}', window=w, n=len(g), modal_Q=mode, mode_share=vc.iloc[0] / len(g), median_Q=q.median(), mean_Q=q.mean(), distinct_Q=q.nunique(), modal_Q_CE=g.Q_CE_v2.mode().iloc[0] if v == 2 else np.nan, modal_Q_PE=g.Q_PE_v2.mode().iloc[0] if v == 2 else np.nan,
                             mean_gross_open=g.gross_short_open_units.mean(), mean_cover=g.short_cover_units.mean(), mean_net=g.net_short_change_units.mean()))
L = pd.DataFrame(rows); L.to_csv(os.path.join(A, 'p1_e3_ladder_by_window.csv'), index=False)
# ---------------- ENT-04 off-window and initial-entry events (descriptive)
O['hour'] = O.order_entry_minute.dt.hour; O['minute_of_hour'] = O.order_entry_minute.dt.minute
S = O.groupby(['kind', 'event_class']).agg(parents=('parent_oid', 'nunique'), units=('units', 'sum'), median_minutes_to_nearest_window=('minutes_to_nearest_window', 'median'), share_within_5min_of_window=('minutes_to_nearest_window', lambda s: (s <= 5).mean()), share_within_10min_after_close=('minutes_since_last_close', lambda s: (s <= 10).mean())).reset_index()
S.to_csv(os.path.join(A, 'p1_ent04_off_window_summary.csv'), index=False)
H = O[O.event_class == 'OFF_WINDOW_ACTION'].groupby(['kind', 'hour']).size().rename('parents').reset_index(); H.to_csv(os.path.join(A, 'p1_ent04_off_window_by_hour.csv'), index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print(E1a.to_string()); print(T.to_string()); print(S.to_string()); print(L[L.view == 'V2'].query("kind=='PRE'")[['window', 'n', 'modal_Q', 'mode_share', 'mean_Q', 'mean_gross_open', 'mean_cover', 'mean_net']].to_string())
