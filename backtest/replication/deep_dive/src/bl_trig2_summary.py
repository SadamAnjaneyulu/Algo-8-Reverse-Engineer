"""Late-sale trigger investigation: assemble the multiple-testing family (BH 10%), the per-event/per-cycle table and the verdict table. Reads outputs/trig2/*.json|csv. Output outputs/trig2/bh_family.csv, per_cycle_events.csv/.md"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, bl_risk_tests as RT
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); T2 = f'{OUT}/trig2'
def build():
    a = json.load(open(f'{T2}/tests_part1.json')); c = json.load(open(f'{T2}/tests_part3.json')); H = pd.read_csv(f'{T2}/state_hazard.csv'); inc = json.load(open(f'{T2}/incremental.json')); fam = []
    add = lambda tid, expl, desc, stat, p, note='': fam.append(dict(id=tid, explanation=expl, test=desc, statistic=stat, p=p, note=note))
    add('S1', 'S timer', 'cross-cycle same-second coincidence (shift null)', f"{a['S1']['coincident_pairs']} pairs vs {a['S1']['null_mean']:.1f}", a['S1']['p'])
    add('S2', 'S timer', 'share of events in seconds :00-:05 (binomial vs 10%)', f"{a['S2']['share_0_5s']:.3f}", a['S2']['p'])
    add('S3', 'S timer', 'events within 15:29-15:31 (shift null)', f"{a['S3']['n']} vs {a['S3']['null_n_mean']:.1f}", a['S3']['p'])
    for P_ in ('300', '900', '1800'): add(f'S4_{P_}', 'S timer', f'phase locking to the 09:16 grid, period {P_} s (shift null)', f"R={a['S4'][P_]['R']:.2f} vs {a['S4'][P_]['null_R_mean']:.2f}", a['S4'][P_]['p'], 'period 1800 s is longer than the window (1500 s): weak design' if P_ == '1800' else '')
    add('P1', 'P pair', 'pair share vs independent-leg shift null', f"{a['P1']['share']:.3f} vs {a['P1']['null_share_mean']:.3f}", a['P1']['p'], 'only 6 pair events')
    add('P3a', 'P pair', 'FIFO pair-completion vs own/mirror expectation', f"{a['P3a_all']['observed']:.3f} vs {a['P3a_all']['expected']:.3f}", a['P3a_all']['p'], 'low-power by construction when the side is stable within a cycle')
    p4 = a['P4']; add('P4', 'P pair / replacement', 'late sale within 10 min after a same-side cover (shift null of covers)', f"{p4['share']:.3f} vs {p4['null_mean']:.3f}", min(1.0, 2 * (1 - p4['p'] + 1 / 2001)), 'two-sided p derived from the stored upper-tail p (approximate); direction is BELOW chance')
    add('R2', 'R premium', 'premium target: Spearman late vs pre-15:15 premium', f"slope {a['R2']['slope']:.2f}", a['R2']['spearman_p'])
    add('R3', 'R lump', 'late events within 120 s before the lump (shift null)', f"{a['R3']['share_within_120s_before_lump']:.3f} vs {a['R3']['null_mean']:.3f}", min(1.0, 2 * a['R3']['p']), 'two-sided derived from the upper-tail p (approximate)')
    for r in H.itertuples(): add(f'O_{r.feature}', 'O portfolio state', f'hazard AUC of {r.feature} (curveball null)', f'AUC {r.auc:.3f} vs {r.null_mean:.3f}', float(r.p), f'same direction in {r.cycles_same_direction} cycles')
    add('S5', 'S timer (minute level)', 'minute concentration (sum of squares, shift null)', f"{c['S5']['sumsq']} vs {c['S5']['null_mean']:.0f}", c['S5']['p'], 'post-hoc addition')
    add('S1b', 'S timer (second level)', 'same-minute different-cycle seconds coincidence', f"{c['S1b']['coincident_within_3s']} vs {c['S1b']['null_mean']:.1f}", c['S1b']['p'], 'post-hoc addition')
    add('S6', 'S timer / index', 'events in 15:15, 15:20, 15:29 (shift null)', f"{c['S6']['share']:.3f} vs {c['S6']['null_share_mean']:.3f}", c['S6']['p'], 'post-hoc: minutes chosen after seeing the histogram')
    for k in ('d', 'd_feed', 'd_fut', 'd_l', 'd_feed_l', 'd_fut_l'): add(f'X1_{k}', 'index/futures moves', f'stratified AUC of {k} for a sale in the minute', f"{c['X1_' + k]['auc']:.3f} vs {c['X1_' + k]['null_mean']:.3f}", c['X1_' + k]['p_two_sided'], 'strictly BEFORE the minute' if k.endswith('_l') else 'CONTEMPORANEOUS (through the sale minute): not causal; post-hoc addition')
    for k in ('feed', 'fut', 'feed_lag1', 'fut_lag1'): add(f'X2_{k}', 'index/futures direction', f'CE after up or PE after down ({k})', f"{c['X2_' + k]['share_CE_after_up_or_PE_after_down']:.3f}", c['X2_' + k]['p'], ('strictly BEFORE the minute; ' if 'lag1' in k else 'CONTEMPORANEOUS: not causal; ') + 'minutes treated as independent: p optimistic')
    Ev = pd.read_csv(f'{T2}/events.csv'); Pr = Ev[Ev.type == 'pair']; kk = int(Pr.t0.between(55680, 55860).sum()); from scipy.stats import binomtest
    add('S7', 'S timer / P pair', 'all pair events fall inside 15:28:00-15:31:00 (binomial vs 180/1500, x22 window positions)', f"{kk} of {len(Pr)} vs 12% expected", min(1.0, 22 * float(binomtest(kk, len(Pr), 180 / 1500, alternative='greater').pvalue)), 'POST-HOC: window chosen after seeing the six pair times; Bonferroni for window position only')
    F = pd.DataFrame(fam); F['p_bh_10'] = RT.bh(F.p.values); F['bh_significant_10'] = F.p_bh_10 <= 0.10; F.to_csv(f'{T2}/bh_family.csv', index=False)
    E = pd.read_csv(f'{T2}/events.csv'); hm = lambda s: f'{int(s) // 3600:02d}:{int(s) % 3600 // 60:02d}:{int(s) % 60:02d}'; E['time'] = E.t0.map(hm); E['legs'] = np.where(E.type == 'pair', 'CE+PE', np.where(E.ce_lots > 0, f'CE x{0}', f'PE'))
    E['lots'] = np.where(E.type == 'pair', 'CE ' + E.ce_lots.astype(str) + ' + PE ' + E.pe_lots.astype(str), np.where(E.ce_lots > 0, 'CE ' + E.ce_lots.astype(str), 'PE ' + E.pe_lots.astype(str)))
    tab = E.sort_values(['cyc', 't0'])[['cyc', 'time', 'n', 'lots', 'type', 'labels']].rename(columns={'cyc': 'cycle', 'n': 'orders'}); tab['cycle'] = tab.cycle.str.replace('NIFTY', 'NIFTY ').str.replace('SENSEX', 'SENSEX ').str.replace('|', ' ')
    tab.to_csv(f'{T2}/per_cycle_events.csv', index=False)
    with open(f'{T2}/per_cycle_events.md', 'w') as f: f.write('| cycle (D-1) | event start | orders | lots | type | labels |\n|---|---|--:|---|---|---|\n' + '\n'.join(f"| {r.cycle} | {r.time} | {r.orders} | {r.lots} | {r.type} | {r.labels} |" for r in tab.itertuples()) + '\n')
    print(F[['id', 'statistic', 'p', 'p_bh_10', 'bh_significant_10']].round(4).to_string(index=False)); print('events by label:', E.labels.value_counts().to_dict()); print('cycles with events', E.cyc.nunique(), 'unexplained', int((E.labels == 'unexplained').sum()), 'of', len(E))
if __name__ == '__main__': build()
