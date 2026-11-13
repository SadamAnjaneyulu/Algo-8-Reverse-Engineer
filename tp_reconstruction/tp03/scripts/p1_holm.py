"""TP-03 Phase 1: entry-family Holm correction (registered size upper bound 120; unrun / NOT_TESTABLE members count as p = 1) and the E2 evidence labelling with the exploratory ceiling."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as tc
tc.assert_frozen(); A = tc.ANALYSIS; FAM = tc.CFG['inference']['holm_families']['entry']['size_upper_bound']; ALPHA = 0.05
E2 = pd.read_csv(os.path.join(A, 'p1_e2_results.csv')); T = pd.read_csv(os.path.join(A, 'p1_testability.csv'))
rows = []
prim = E2[(E2.view == 'V2') & (E2.snapshot == 'primary') & (E2.scheme == 'block')]
for r in prim.itertuples():
    tb = T[(T.design == r.design) & (T.view == 'V2') & (T.outcome == r.outcome)].iloc[0]
    rows.append(dict(family='E2', test_id=r.test_id, p=r.p if (r.status == 'RUN' and tb.testable) else np.nan, status=r.status if tb.testable else 'NOT_TESTABLE_GATE'))
for f, tag in (('p1_e3_results.csv', 'E3'), ('p1_e5_results.csv', 'E5'), ('p1_e6_results.csv', 'E6'), ('p1_e7_results.csv', 'E7'), ('p1_e8_results.csv', 'E8')):
    d = pd.read_csv(os.path.join(A, f))
    if tag == 'E3': d = d[d.view == 'VIEW2']                       # V3 is a sensitivity, not a family member
    for i, r in d.iterrows(): rows.append(dict(family=tag, test_id=(r.get('test') if tag not in ('E3', 'E7') else (f"{r['test']}|{r['design']}|{r['view']}" if tag == 'E3' else 'E7 ' + str(r['convention']))), p=r.get('p', np.nan), status='RUN' if pd.notna(r.get('p', np.nan)) else 'NOT_TESTABLE'))
rows.append(dict(family='E1', test_id='E1 schedule (descriptive, no p-value by registration)', p=np.nan, status='DESCRIPTIVE'))
H = pd.DataFrame(rows); n_run = int(H.p.notna().sum()); H = H.sort_values('p', na_position='last').reset_index(drop=True)
H['rank'] = np.arange(1, len(H) + 1); H['holm_threshold'] = [ALPHA / (FAM - k + 1) for k in H['rank']]; sig = []; stop = False
for r in H.itertuples():
    ok = (not stop) and pd.notna(r.p) and r.p <= r.holm_threshold
    if not ok: stop = True
    sig.append(bool(ok))
H['holm_significant'] = sig; H['family_size_used'] = FAM; H['tests_with_p'] = n_run; H.to_csv(os.path.join(A, 'p1_holm_entry_family.csv'), index=False)
print(f'{n_run} tests with a p-value of {FAM} registered members; Holm-significant: {int(H.holm_significant.sum())}'); print(H.head(25).to_string())
# ---------------- E2 evidence table (feature x outcome), exploratory ceiling and sensitivities
rows = []
for (feat, outcome), g in E2.groupby(['feature', 'outcome']):
    rec = dict(feature=feat, outcome=outcome)
    for dsg in ('PRE', 'D0'):
        x = g[g.design == dsg]; base = x[(x.view == 'V2') & (x.snapshot == 'primary') & (x.scheme == 'block')]
        if base.empty or base.iloc[0].status != 'RUN': rec[f'{dsg}_p'] = np.nan; rec[f'{dsg}_status'] = 'NOT_TESTABLE'; continue
        b = base.iloc[0]; v3 = x[(x.view == 'V3') & (x.snapshot == 'primary') & (x.scheme == 'block')].iloc[0]; s1 = x[(x.view == 'V2') & (x.snapshot == 'S1')].iloc[0]; wi = x[(x.scheme == 'within')].iloc[0]
        sg = lambda r_: np.sign(r_.observed_S) if r_.status == 'RUN' else 0
        rec.update({f'{dsg}_S': b.observed_S, f'{dsg}_p': b.p, f'{dsg}_p_V3': v3.p, f'{dsg}_p_S1': s1.p, f'{dsg}_p_within': wi.p, f'{dsg}_same_sign_both_und': b.same_sign_both_und, f'{dsg}_cycle_share': b.cycle_share_agreeing, f'{dsg}_auc': b.auc, f'{dsg}_tercile_ratio': b.tercile_ratio,
                    f'{dsg}_sign_stable_V3_S1': bool(sg(v3) == sg(b) == sg(s1)), f'{dsg}_status': 'RUN'})
    rows.append(rec)
EV = pd.DataFrame(rows); hs = dict(zip(H.test_id, H.holm_significant))
for dsg in ('PRE', 'D0'): EV[f'{dsg}_holm'] = [hs.get(f'E2|{dsg}|{o}|{f}|V2|primary|block', False) for f, o in zip(EV.feature, EV.outcome)]
def ceiling(r):
    pre, d0 = bool(r.PRE_holm), bool(r.D0_holm); same = (np.sign(r.PRE_S) == np.sign(r.D0_S)) if pre and d0 else False
    return tc.e2_evidence_ceiling(pre, d0, same)
EV['evidence_ceiling_result'] = EV.apply(ceiling, axis=1); EV.to_csv(os.path.join(A, 'p1_e2_evidence.csv'), index=False)
print(EV.evidence_ceiling_result.value_counts().to_string())
