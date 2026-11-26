"""Gate 4 validation report on the frozen B1 (reports/PHASE1_GATE4_STANDARDS.md). Reads saved runs; recomputes nothing about the engine. Outputs outputs/phase1/gate4/."""
import sys, os, json, subprocess, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, bl_common, bl_p1_eval as E
OUT = bl_common.OUT; B1 = f'{OUT}/scoring/d1_F_v2_onelot'; G = f'{OUT}/phase1/gate4'; os.makedirs(G, exist_ok=True)
rep = json.load(open(f'{B1}/all/report.json')); rec = json.load(open(f'{B1}/run_record.json')); st = pd.read_csv(f'{B1}/all/strictness.csv'); bc = pd.read_csv(f'{B1}/all/by_class.csv'); pc = pd.read_csv(f'{B1}/all/per_cycle.csv'); blk = pd.read_csv(f'{B1}/all/by_block.csv'); sa = pd.read_csv(f'{B1}/all/state_after_matched.csv')
real = pd.read_csv(f'{B1}/real_orders.csv'); sim = pd.read_csv(f'{B1}/sim_orders.csv'); P = pd.read_csv(f'{B1}/all/pairs.csv')
f60 = lambda lvl: float(st[(st.cumulative_tolerance_s == 60) & (st.level == lvl)].F1.iloc[0]); res = {}
res['Q1'] = dict(value=f60('keys'), threshold=0.70); res['Q2'] = dict(value=f60('lots_exact') if False else float(st[(st.cumulative_tolerance_s == 60) & (st.level == 'lots_exact')].F1.iloc[0]), threshold=0.55, note='strict = strike exact and lots exact (level lots_exact)')
res['Q3'] = dict(value=rec['legacy_f1_on_this_replay'], threshold=0.65); res['Q4'] = dict(value=float(pc.F1.min()), threshold=0.60, worst_five=pc.sort_values('F1').head(5)[['cyc', 'F1']].values.tolist(), cycles_below_0_60=int((pc.F1 < 0.60).sum()), median=float(pc.F1.median()))
cls = bc[bc.real >= 100][['cls', 'real', 'recall', 'precision', 'F1']]; res['Q5'] = dict(value=float(cls.F1.min()), threshold=0.50, table=cls.round(4).to_dict('records'), failing=cls[cls.F1 < 0.50].cls.tolist())
plc = rep['time_shift_placebo']['F1_keys_at_60s']; res['Q6'] = dict(value=float(plc), actual=f60('keys'), ratio=float(plc / f60('keys')), threshold=0.5)
sm = sim[(sim.role == 'scheduled_straddle')]; ms = P[P.si.isin(sm.index)]; res['Q7'] = dict(value=float(len(ms) / len(sm)), threshold=0.95, matched=int(len(ms)), simulated=int(len(sm)))
net = {}; max_short = {'CE': 0, 'PE': 0}
for c, g in sim.sort_values(['cyc', 't', 'seq']).groupby('cyc'):
    net = {}
    for cp, k, side, n in zip(g.cp, g.strike, g.side.str.lower(), g.lots):
        net[(cp, k)] = net.get((cp, k), 0) + (n if side == 'buy' else -n)
        for c2 in ('CE', 'PE'): max_short[c2] = max(max_short[c2], sum(-v for (cc, _), v in net.items() if cc == c2 and v < 0))
per_min = sim.assign(m=((sim.t - 33300) // 60).astype(int)).groupby(['cyc', 'm']).size().max()
res['Q8'] = dict(rejected=int(rec['rejected_orders']), max_net_short_lots_per_right=max_short, limit=400, max_orders_per_minute_children=int(per_min), decisions_cap=40, note='the decision cap is enforced by the engine (0 rejected); the child count is informational'); res['Q8']['pass'] = bool(rec['rejected_orders'] == 0 and max(max_short.values()) <= 400)
res['Q9'] = dict(value=float(sa.l1_norm.median()), threshold=0.35, SL_equal_share=float((sa.SL_equal).mean()))
res['by_block'] = blk.round(4).to_dict('records'); res['by_class_all'] = bc.round(4).to_dict('records'); res['per_cycle'] = pc[['cyc', 'real', 'sim', 'matched', 'F1']].round(4).to_dict('records')
# Q10: reproducibility is recorded by the integrity check and the test suites (run separately)
fi = json.load(open(f'{OUT}/scoring/split_comparison/freeze_integrity.json')); res['Q10'] = dict(replay_identical_to_saved=bool(fi['one_lot_v2']['identical_to_saved'] and fi['freeze_v1']['identical_to_saved']))
# Q11: classes with > 5% unmatched
un = bc.assign(unmatched_share=1 - bc.recall)[['cls', 'real', 'unmatched_share']]; res['Q11'] = dict(classes_over_5pct_unmatched=un[un.unmatched_share > 0.05].round(3).to_dict('records'))
# sensitivity rows (diagnostic; not baseline)
sens = {}
for nm, d in (('B1', B1), ('V01_book_condition', f'{OUT}/phase1/2A/V01'), ('C1_rebased_futures_feed', f'{OUT}/phase1/2C/C1')):
    s = pd.read_csv(f'{d}/all/strictness.csv'); sens[nm] = dict(keys_F1_60s=float(s[(s.cumulative_tolerance_s == 60) & (s.level == 'keys')].F1.iloc[0]), strict_F1_60s=float(s[(s.cumulative_tolerance_s == 60) & (s.level == 'lots_exact')].F1.iloc[0]), legacy_lot_F1=json.load(open(f'{d}/run_record.json')).get('legacy_f1', rec['legacy_f1_on_this_replay']) if 'legacy_f1' in json.load(open(f'{d}/run_record.json')) else rec['legacy_f1_on_this_replay'])
res['sensitivity'] = sens; res['tfe_note'] = 'TF-E diagnostics are reported separately (D1_TFE_COMPARISON.md); F1 keys 0.739 (F) versus 0.645 (TF-E first decisions): TF-E is not a score and is not mixed here'
verdict = {k: bool((res[k]['value'] >= res[k]['threshold']) if k in ('Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q7', 'Q9') and k != 'Q9' else (res[k]['value'] <= res[k]['threshold']) if k in ('Q6', 'Q9') else res[k].get('pass', res[k].get('replay_identical_to_saved'))) for k in ('Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8', 'Q9', 'Q10')}
res['verdict'] = verdict; json.dump(res, open(f'{G}/gate4_report.json', 'w'), indent=1, default=float)
print({k: ('PASS' if v else 'fail') for k, v in verdict.items()}); print({k: (round(res[k]['value'], 4) if 'value' in res[k] else None) for k in ('Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q9')}); print(res['Q5']['failing'], res['Q4']['worst_five'], res['Q4']['cycles_below_0_60'], res['Q8'], res['Q11'], res['sensitivity'])
