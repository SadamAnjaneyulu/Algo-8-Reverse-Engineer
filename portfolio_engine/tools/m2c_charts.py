"""M2-C charts supporting closing-batch reconstruction (real ledger, HISTORICAL_OBSERVED_REPLAY). Each PNG has its plotted data in a CSV beside it.
python3 portfolio_engine/tools/m2c_charts.py -> reports/m2c_figures/"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, numpy as np, pandas as pd
from pe.schema import *
from pe.lineage_set import LineageSet
from pe import closing_batches as cb
from pe.generators import historical as H
OUT = os.path.join(PE, 'reports', 'm2c_figures'); os.makedirs(OUT, exist_ok=True)
ins, fills, src = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); parents, un, multi = cb.closing_parents(ls); V = cb.all_views(parents); S = cb.summarize(V, parents, ls)
STAMP = (f'Source: Trades_GKOHNP140.csv (sha256 {src["raw_trades_sha256"][:8]}…) → TP-01 ledger; mode HISTORICAL_OBSERVED_REPLAY; closing portions are convention-independent (no FIFO/LIFO/AVG used). '
         'Grouping = INFERRED analytical view (execution-time proximity of closing parent orders), not an original basket and not evidence of one decision. Units: parent orders / closing units / seconds.')
def stamp(fig, extra=''): fig.text(0.01, 0.005, (extra + ' ' + STAMP).strip(), fontsize=6, wrap=True, va='bottom')
# ---- 1. threshold sensitivity (both methods; C2 is drawn dashed on top: identical on this data)
rows = []
for r in S: rows.append(dict(method=r['method'], threshold_s=r['threshold_s'], batches=r['batches'], singleton_batches=r['singleton_batches'], parents_per_batch_median=r['size']['median'], parents_per_batch_p99=r['size']['p99'], parents_per_batch_max=r['size']['max'],
                              duration_median_s=r['duration_s']['median'], duration_p99_s=r['duration_s']['p99'], duration_max_s=r['duration_s']['max'], max_duration_over_threshold=r['max_duration_over_threshold'], pairs_gap_eq_threshold=r['pairs_gap_exactly_threshold'], pairs_gap_threshold_plus_1s=r['pairs_gap_threshold_plus_1s']))
D = pd.DataFrame(rows); D.to_csv(os.path.join(OUT, 'm2c_threshold_sensitivity.csv'), index=False)
fig, ax = plt.subplots(1, 4, figsize=(17, 4.2)); sty = {'C1': dict(color='#1b9e77', lw=2.5), 'C2': dict(color='#d95f02', lw=1.2, ls='--')}
for m in ('C1', 'C2'):
    d = D[D.method == m]; ax[0].plot(d.threshold_s, d.batches, marker='o', label=m, **sty[m]); ax[1].plot(d.threshold_s, d.singleton_batches / d.batches, marker='o', **sty[m]); ax[2].plot(d.threshold_s, d.parents_per_batch_p99, marker='o', **sty[m]); ax[3].plot(d.threshold_s, d.duration_max_s, marker='o', **sty[m])
for a, t in zip(ax, ('batches (count)', 'share of singleton batches', 'parents per batch, p99', 'longest batch duration (s)')): a.set_title(t, fontsize=9); a.set_xscale('log'); a.set_xticks([2, 5, 10, 30, 60]); a.set_xticklabels(['2', '5', '10', '30', '60']); a.set_xlabel('gap threshold (s)')
ax[3].plot([2, 60], [2, 60], color='grey', lw=0.8, ls=':'); ax[3].text(2.2, 45, 'dotted: duration = threshold', fontsize=7); ax[0].legend(fontsize=8); fig.suptitle('Closing batches: sensitivity to the gap threshold (C2 coincides with C1 on this data)', fontsize=10); stamp(fig); plt.tight_layout(rect=(0, 0.06, 1, 0.95)); plt.savefig(os.path.join(OUT, 'm2c_threshold_sensitivity.png'), dpi=130); plt.close()
# ---- 2. timestamp-precision sensitivity: pairs exactly at the threshold vs one second beyond
fig, ax = plt.subplots(figsize=(7, 4)); d = D[D.method == 'C1']; x = np.arange(len(d)); ax.bar(x - 0.2, d.pairs_gap_eq_threshold, 0.4, label='adjacent pairs with gap = threshold (linked)'); ax.bar(x + 0.2, d.pairs_gap_threshold_plus_1s, 0.4, label='gap = threshold + 1 s (not linked)')
ax.set_xticks(x); ax.set_xticklabels([f'{g} s' for g in d.threshold_s]); ax.legend(fontsize=7); ax.set_title('Timestamp-precision sensitivity (whole-second data)', fontsize=9); stamp(fig); plt.tight_layout(rect=(0, 0.08, 1, 1)); plt.savefig(os.path.join(OUT, 'm2c_precision_sensitivity.png'), dpi=130); plt.close()
# ---- 3. batch maps for the two frozen demonstration cycles (expiry-day session), primary C1 10 s
v = V[('C1', 10)]; owner = {p.key: b['batch_id'] for b in v['batches'] for p in b['members']}
for und, expiry in (('NIFTY', '2026-06-30'), ('SENSEX', '2026-07-16')):
    pts = []
    for p in parents:
        if p.und == und and p.expiry == expiry and p.session == expiry:
            for r in p.cps: pts.append(dict(batch_id=owner[p.key], parent_order_id=p.parent_id, cp_id=r[1], ts=r[6], time=pd.Timestamp(r[6] + IST_OFFSET_S, unit='s'), contract=f'{ls.instruments[r[4]].option_type}{ls.instruments[r[4]].strike}', option_type=ls.instruments[r[4]].option_type, strike=ls.instruments[r[4]].strike, qty=r[8], closed_direction='SHORT' if ls.episodes[r[5]]['direction'] == -1 else 'LONG'))
    P = pd.DataFrame(pts)
    if P.empty: continue
    P.drop(columns='time').to_csv(os.path.join(OUT, f'm2c_batch_map_{und}_{expiry}_D0.csv'), index=False)
    order = {b: i for i, b in enumerate(sorted(P.batch_id.unique()))}; P['c'] = P.batch_id.map(order) % 10; fig, ax = plt.subplots(figsize=(14, 6))
    P['y'] = P.apply(lambda r: r.strike + (0.35 if r.option_type == 'PE' else 0), axis=1)
    for opt, mk in (('CE', 'o'), ('PE', '^')):
        q = P[P.option_type == opt]; ax.scatter(q.time, q.y, c=q.c, cmap='tab10', vmin=0, vmax=9, marker=mk, s=8 + np.sqrt(q.qty), alpha=0.8, edgecolors='none', label=opt)
    for b in sorted(P.batch_id.unique()):
        q = P[P.batch_id == b]
        if len(q.parent_order_id.unique()) >= 8: ax.axvspan(q.time.min(), q.time.max(), color='grey', alpha=0.12)
    ax.set_xlabel(f'time (IST), {expiry}'); ax.set_ylabel('strike (PE offset +0.35 for legibility)'); ax.legend(title='marker'); n_b = P.batch_id.nunique()
    ax.set_title(f'{und} expiry {expiry}: closing portions by contract, coloured by C1 10 s batch ({n_b} batches, {P.parent_order_id.nunique()} parent orders, {int(P.qty.sum())} units closed; grey bands = batches of ≥ 8 parents; colours cycle)', fontsize=8)
    stamp(fig, f'Demonstration cycle frozen before any grouping (DEMO_CYCLE_SELECTION_NOTE). Period: {expiry} session only.'); plt.tight_layout(rect=(0, 0.06, 1, 1)); plt.savefig(os.path.join(OUT, f'm2c_batch_map_{und}_{expiry}_D0.png'), dpi=120); plt.close()
print(sorted(os.listdir(OUT)))
