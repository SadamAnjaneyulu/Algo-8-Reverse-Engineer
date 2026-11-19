"""Extract the Algo 8 decision parameters from the 35 live cycles (teacher data) into config/algo8_v1_params.json.
Everything here is DESCRIPTIVE and IN-SAMPLE: ladders are the conditional median of lots per (slot, right) over the cycles in which the original acted; a slot is 'scheduled' when the original acted in >= 50 % of the cycles that have that session.
No parameter is tuned on P&L. Constants without a recovered value (stop multiplier, cycle-stop rupees, wing ratio) are the repository's evidenced central values and are listed with their evidence band."""
import json, hashlib, subprocess, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import ref
F = ref.load_fills(); O = ref.orders(F); O['jc'] = O.j.clip(0, 374); cyc = pd.read_csv(ref.CYCLES)
out = dict(provenance=dict(source='Trades_GKOHNP140.csv (35 live cycles, 2026-06-23..2026-10-22)', ledger_sha256=hashlib.sha256(open(f'{ref.ROOT}/Trades_GKOHNP140.csv', 'rb').read()).hexdigest(), git_head=subprocess.run(['git', '-C', ref.ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
                       status='IN-SAMPLE descriptive extraction; every value is a HYPOTHESIS about the original decision rule, not a recovered rule'))
for d, name in ((0, 'ladder_d1'), (1, 'ladder_d0')):
    has = {(r.und, r.expiry) for r in cyc.itertuples() if (r.has_d1 if d == 0 else r.has_d0)}
    x = O[(O.module == 'num') & (O.side == 'Sell') & (O.dayno == d)]; g = x.groupby(['und', 'expiry', 'jc', 'cp']).lots.sum(); tab = {}
    for j in range(0, 375):
        row = {}
        for cp in ('CE', 'PE'):
            v = np.array([g.get((u, e, j, cp), 0) for (u, e) in has], float); act = v[v > 0]; p = float((v > 0).mean())
            if p >= 0.5 and len(act): row[cp] = dict(p_act=round(p, 3), lots=int(np.floor(np.median(act) + 0.5)), median_when_active=float(np.median(act)))
        if row: tab[str(j)] = row
    out[name] = dict(design='PER-MINUTE schedule: minute index j (0 = 09:15) is scheduled for a right when the original sold at that minute in >= 50 % of the cycles that have the session; lots = conditional median over the cycles that sold',
                     cycles_with_session=len(has), minutes=tab, share_of_original_lots_covered=None,
                     gate=('none (runs while no cycle stop)' if d == 0 else 'D0 entries only while the book holds an open body short and the cycle stop has not fired (ENT-03)'))
    cov = sum(g.get((u, e, int(j), cp), 0) for (u, e) in has for j in tab for cp in tab[j]); tot = int(x[[(u, e) in has for u, e in zip(x.und, x.expiry)]].lots.sum()); out[name]['share_of_original_lots_covered'] = round(cov / tot, 3)
P = pd.read_csv(f'{ref.OUT}/mode1_wing_pairs.csv'); out['wing'] = dict(price_ratio_to_body=round(float(P.ratio.median()), 4), rule='highest OTM same-right strike whose last close <= ratio x body price (cheapest-first search outward), one wing per body lot', evidence='HYPOTHESIS: strike exact 32 % vs original, within one step 55 % (parity S11)')
# flatten minute: last minute with contract-level shorts on D0, by period
rows = []
for r in cyc[cyc.has_d0].itertuples():
    g = F[(F.und == r.und) & (F.expiry == r.expiry)].sort_values(['t', 'row']); cum = {}; last = -1
    for x in g.itertuples():
        cum[(x.cp, x.strike)] = cum.get((x.cp, x.strike), 0) + x.sgn_lots
        if x.dayno == 1 and sum(-v for v in cum.values() if v < 0) > 0: last = x.j
    rows.append((r.expiry, last))
pre = [l for e, l in rows if e < '2026-08-03' and l >= 300]; post = [l for e, l in rows if e >= '2026-08-03' and l >= 300]
out['flatten'] = dict(cutover_date='2026-08-03', minute_post_cutover=int(pd.Series(post).mode().iloc[0]), minute_pre_cutover=int(pd.Series(pre).mode().iloc[0]), pre_cutover_values=sorted(pre), post_cutover_values=sorted(post),
                      note='minute index 0 = 09:15; 359 = 15:14. Pre-cutover value is the mode of the last minute holding shorts in cycles that were still short after 15:00; the cut-over date is the registered 2026-08-03 (two later cycles do not conform; not adopted)')
out['risk'] = dict(per_lot_stop=dict(multiplier=1.60, reference='own_entry', exempt_entry_px=4.0, band=[1.55, 1.70], evidence='HYPOTHESIS (explains <= 17 % of original buy-backs, precision 63-74 %)'),
                   cycle_stop=dict(limit_rs=144000.0, scaling='limit_rs is the value at the 2026 lot size (NIFTY 65 / SENSEX 20) and scales linearly with the session lot size (user decision; fixed-rupee is a sensitivity)', band_rs=[130000.0, 144000.0], mark='previous completed close (causal); open-of-minute as sensitivity', evidence='HYPOTHESIS (reproduced 1/0/0 of 11 causally; 10/9/8 with the decision-minute close)'),
                   after_cycle_stop='no new entries; every open lot liquidated at the stop minute (passive-lot treatment: all lots, an ASSUMPTION; U4)',
                   unknown_not_modelled=['4 % carry SL (Info.txt)', '1 % of capital on expiry day (Info.txt)', 'off-schedule entries', 'Clock-B reductions', 'lump hedge', 'margin gate'])
json.dump(out, open(f'{ref.EP}/config/algo8_v1_params.json', 'w'), indent=1)
for n in ('ladder_d1', 'ladder_d0'): print(n, 'scheduled minutes:', len(out[n]['minutes']), 'share of original lots covered:', out[n]['share_of_original_lots_covered'])
print('wing ratio', out['wing']['price_ratio_to_body'], '| flatten', out['flatten']['minute_pre_cutover'], out['flatten']['minute_post_cutover'])
