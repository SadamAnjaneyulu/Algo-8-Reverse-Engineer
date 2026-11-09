"""Phase 2 selection and evaluation (reads results/stop_ref_counts.csv.gz; no simulation here).
Pre-registered protocol (written before the results were examined):
  * k is selected on DEV only, per (convention, reference, pool, variant): (i) per segment, maximising DEV F1 of (precision, recall);
    (ii) one GLOBAL k per (convention, reference), maximising DEV F1 on the counts pooled over all segments.  A segment is assessed only if it has >= 30
    events and >= 30 pool buy-backs in that split; otherwise it is reported as 'insufficient'.
  * The chosen k is applied unchanged to VAL and TEST.  90 % cycle-bootstrap intervals (2,000 resamples of the split's cycles) for precision, recall, coverage.
  * VERDICT RULE: a single (reference, global k) 'explains' the stop-like exits only if precision >= 0.80 AND recall >= 0.80 on VAL and on TEST in every
    assessable segment, under every ownership convention.  Otherwise the per-lot stop classification stays UNKNOWN.
  * ORACLE ceiling (informational, NOT a selection): best F1 over k on each split, to show whether ANY constant on this grid could reach the bar.
python3 analysis/allocation/stop_select.py"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from alloc import RES

SEGS = ['D-1 fresh', 'D0 fresh', 'D0 carried']
MIN_N = 30
REP = 2000

def prf(d):
    ev = d.ev_first + d.ev_repeat; tp = d.tp_first + d.tp_repeat
    P = np.where(ev > 0, tp / np.maximum(ev, 1), np.nan); R = np.where(d.buybacks > 0, d.matched_buybacks / np.maximum(d.buybacks, 1), np.nan)
    return ev, tp, P, R

def agg(D, keys):
    return D.groupby(keys)[['ev_first', 'ev_repeat', 'tp_first', 'tp_repeat', 'buybacks', 'matched_buybacks', 'covered_buybacks']].sum().reset_index()

def f1(P, R):
    return np.where((P + R) > 0, 2 * P * R / np.maximum(P + R, 1e-12), 0.0)

def metrics(a):
    ev, tp, P, R = prf(a); a = a.copy(); a['events'] = ev; a['tp'] = tp; a['precision'] = P; a['recall'] = R; a['f1'] = f1(np.nan_to_num(P), np.nan_to_num(R))
    a['false_triggers'] = ev - tp; a['missed_exits'] = a.buybacks - a.matched_buybacks; a['coverage'] = np.where(a.buybacks > 0, a.covered_buybacks / np.maximum(a.buybacks, 1), np.nan)
    a['precision_first'] = np.where(a.ev_first > 0, a.tp_first / np.maximum(a.ev_first, 1), np.nan); a['precision_repeat'] = np.where(a.ev_repeat > 0, a.tp_repeat / np.maximum(a.ev_repeat, 1), np.nan)
    return a

def boot(Dc, reps=REP, seed=0):
    """Dc: per-cycle rows of one config/split.  Returns 90 % intervals for precision, recall, coverage."""
    c = Dc.groupby(['und', 'expiry'])[['ev_first', 'ev_repeat', 'tp_first', 'tp_repeat', 'buybacks', 'matched_buybacks', 'covered_buybacks']].sum()
    if len(c) < 2: return dict(p_lo=np.nan, p_hi=np.nan, r_lo=np.nan, r_hi=np.nan, c_lo=np.nan, c_hi=np.nan)
    V = c.values.astype(float); rng = np.random.default_rng(seed); idx = rng.integers(0, len(V), (reps, len(V))); S = V[idx].sum(1)
    ev = S[:, 0] + S[:, 1]; tp = S[:, 2] + S[:, 3]; P = tp / np.maximum(ev, 1); R = S[:, 5] / np.maximum(S[:, 4], 1); Cv = S[:, 6] / np.maximum(S[:, 4], 1)
    q = lambda x: np.nanpercentile(x, [5, 95]); return dict(p_lo=q(P)[0], p_hi=q(P)[1], r_lo=q(R)[0], r_hi=q(R)[1], c_lo=q(Cv)[0], c_hi=q(Cv)[1])

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 400)
    D = pd.read_csv(os.path.join(RES, 'stop_ref_counts.csv.gz')); D = D[D.segment != 'other']
    key0 = ['conv', 'ref', 'pool', 'variant']
    # ---- selection on DEV only ------------------------------------------------------------------------------------------------------------------------
    dev = D[D.split == 'DEV']
    seg = metrics(agg(dev, key0 + ['segment', 'k'])); seg = seg[seg.segment.isin(SEGS) & (seg.events >= MIN_N) & (seg.buybacks >= MIN_N)]
    sel_seg = seg.loc[seg.groupby(key0 + ['segment']).f1.idxmax()][key0 + ['segment', 'k', 'f1']].rename(columns={'k': 'k_dev', 'f1': 'dev_f1'})
    glob = metrics(agg(dev, key0 + ['k'])); sel_glob = glob.loc[glob.groupby(key0).f1.idxmax()][key0 + ['k', 'f1']].rename(columns={'k': 'k_dev', 'f1': 'dev_f1'})
    sel_seg.to_csv(os.path.join(RES, 'stop_ref_selected_k_per_segment.csv'), index=False); sel_glob.to_csv(os.path.join(RES, 'stop_ref_selected_k_global.csv'), index=False)
    # ---- evaluation on DEV / VAL / TEST at the selected k ---------------------------------------------------------------------------------------------
    rows = []
    for kind, sel in (('global k', sel_glob), ('per-segment k', sel_seg)):
        for r in sel.itertuples():
            d = D[(D.conv == r.conv) & (D.ref == r.ref) & (D.pool == r.pool) & (D.variant == r.variant) & (D.k == r.k_dev)]
            segs = [r.segment] if kind == 'per-segment k' else SEGS + ['D0 mixed', 'ALL']
            for sg in segs:
                dd = d if sg == 'ALL' else d[d.segment == sg]
                for sp in ('DEV', 'VAL', 'TEST'):
                    x = dd[dd.split == sp]
                    if x.empty: continue
                    a = metrics(agg(x.assign(g=1), ['g'])).iloc[0].to_dict(); a.update(boot(x) if sp != 'DEV' else {})
                    a.update(selection=kind, conv=r.conv, ref=r.ref, pool=r.pool, variant=r.variant, k=r.k_dev, segment=sg, split=sp, dev_f1=r.dev_f1,
                             assessable=bool(a['events'] >= MIN_N and a['buybacks'] >= MIN_N)); rows.append(a)
    E = pd.DataFrame(rows); E.drop(columns=['g'], errors='ignore').to_csv(os.path.join(RES, 'stop_ref_eval.csv'), index=False)
    # ---- oracle ceiling (informational) ---------------------------------------------------------------------------------------------------------------
    orc = metrics(agg(D, key0 + ['segment', 'split', 'k'])); orc = orc[orc.segment.isin(SEGS) & (orc.events >= MIN_N) & (orc.buybacks >= MIN_N)]
    orc = orc.loc[orc.groupby(key0 + ['segment', 'split']).f1.idxmax()][key0 + ['segment', 'split', 'k', 'events', 'buybacks', 'precision', 'recall', 'f1', 'coverage']]
    orc.to_csv(os.path.join(RES, 'stop_ref_oracle_ceiling.csv'), index=False)
    # ---- verdict --------------------------------------------------------------------------------------------------------------------------------------
    g = E[(E.selection == 'global k') & (E.pool == 'S') & (E.variant == 'W2 quote-confirmed') & E.segment.isin(SEGS) & E.split.isin(['VAL', 'TEST'])].copy()
    g['meets'] = (g.precision >= 0.8) & (g.recall >= 0.8)
    v = g.groupby(['conv', 'ref']).agg(k=('k', 'first'), assessable_cells=('assessable', 'sum'), cells_meeting_80_80=('meets', lambda s: int((s & g.loc[s.index, 'assessable']).sum())),
                                       min_precision=('precision', 'min'), min_recall=('recall', 'min'), mean_precision=('precision', 'mean'), mean_recall=('recall', 'mean')).reset_index()
    v['verdict'] = np.where((v.assessable_cells > 0) & (v.cells_meeting_80_80 == v.assessable_cells), 'EXPLAINS', 'UNKNOWN retained')
    v.to_csv(os.path.join(RES, 'stop_ref_verdict.csv'), index=False)
    print('GLOBAL k selected on DEV (pool S, W2 quote-confirmed):'); print(sel_glob[(sel_glob.pool == 'S') & (sel_glob.variant == 'W2 quote-confirmed')].round(3).to_string(index=False))
    print('\nVAL / TEST at the global k (pool S, W2 quote-confirmed):')
    cols = ['conv', 'ref', 'k', 'segment', 'split', 'events', 'buybacks', 'precision', 'p_lo', 'p_hi', 'recall', 'r_lo', 'r_hi', 'coverage', 'false_triggers', 'missed_exits', 'precision_first', 'precision_repeat']
    show = E[(E.selection == 'global k') & (E.pool == 'S') & (E.variant == 'W2 quote-confirmed') & E.split.isin(['VAL', 'TEST']) & E.segment.isin(SEGS + ['ALL']) & (E.conv == 'cheap')]
    print(show[cols].round(3).to_string(index=False))
    print('\nVERDICT (80/80 on VAL and TEST in every assessable segment):'); print(v.round(3).to_string(index=False))
    print('\nORACLE ceiling: best F1 over k, per reference (pool S, W2 quote-confirmed, cheap):')
    oc = orc[(orc.pool == 'S') & (orc.variant == 'W2 quote-confirmed') & (orc.conv == 'cheap')]; print(oc.groupby(['ref', 'split']).f1.max().unstack().round(3).to_string())
    print('\nmax over references/segments/splits/conventions of min(precision, recall):', round(float(np.minimum(orc.precision, orc.recall).max()), 3))
