"""Figure for the D-1 long-side study: reports/figures/bl_hg_summary.png"""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT, load_orders
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); O = load_orders(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); T1 = pd.read_csv(f'{OUT}/bl_hg_strike.csv'); T2 = pd.read_csv(f'{OUT}/bl_hg_strike2.csv'); S = json.load(open(f'{OUT}/bl_summary_hg345.json')); LC = pd.read_csv(f'{OUT}/bl_hg_lump_cyc.csv')
fig, ax = plt.subplots(2, 2, figsize=(14, 9))
r = CY.iloc[0]; z = O[(O.dayno == 0) & (O.und == r.und) & (O.expiry == r.expiry)].sort_values(['te', 'row']); pos = {}; ts = []; ser = {('CE', 'S'): [], ('CE', 'L'): [], ('PE', 'S'): [], ('PE', 'L'): []}
for q in z.itertuples():
    k = (q.cp, int(q.strike)); pos[k] = pos.get(k, 0) + (1 if q.side.lower() == 'buy' else -1) * q.lots; ts.append((q.te - 33300) / 3600 + 9.25)
    for cp in ('CE', 'PE'): ser[(cp, 'S')].append(-sum(v for (c2, _), v in pos.items() if c2 == cp and v < 0)); ser[(cp, 'L')].append(sum(v for (c2, _), v in pos.items() if c2 == cp and v > 0))
for (cp, kd), v in ser.items(): ax[0, 0].step(ts, v, where='post', color={'CE': '#2b6cb0', 'PE': '#dd6b20'}[cp], ls='-' if kd == 'S' else '--', label=f'{cp} {"short lots S" if kd == "S" else "long lots L"}')
ax[0, 0].set_xlabel('hour (D-1)'); ax[0, 0].set_ylabel('lots'); ax[0, 0].legend(fontsize=8); ax[0, 0].set_title(f'(a) {r.und} {r.expiry}: wings track shorts (L = S); v_ lump adds longs after 15:00')
t = pd.concat([T2.assign(lab=lambda d: 'ref = ' + d.reference)[['lab', 'exact', 'within1', 'null_same_slot_exact']]]).sort_values('exact')
y = np.arange(len(t)); ax[0, 1].barh(y - .2, t.exact, .4, color='#2b6cb0', label='exact strike (out-of-fold)'); ax[0, 1].barh(y + .2, t.null_same_slot_exact, .4, color='#a0aec0', label='null: reference shuffled in slot'); ax[0, 1].scatter(t.within1, y, color='k', marker='|', s=200, label='within one strike')
ax[0, 1].set_yticks(y); ax[0, 1].set_yticklabels(t.lab, fontsize=8); ax[0, 1].set_xlim(0, 1); ax[0, 1].legend(fontsize=8); ax[0, 1].set_title('(b) Wing strike = premium nearest 2.5% × reference')
L4 = S['L4']; keys = ['outermost', 'cheapest', 'newest', 'near_2p5_atm', 'oldest', 'innermost', 'dearest']; ax[1, 0].bar(range(len(keys)), [L4[k] for k in keys], color='#2b6cb0'); ax[1, 0].axhline(L4['chance'], ls='--', color='k', label=f"chance {L4['chance']:.0%}"); ax[1, 0].set_xticks(range(len(keys))); ax[1, 0].set_xticklabels(keys, fontsize=8, rotation=20); ax[1, 0].legend(); ax[1, 0].set_title(f"(c) Which wing is sold on a D-1 release (n = {L4['n']})")
L = LC[LC.has_lump == 1]; ax[1, 1].scatter(L.S_heavy, L.lump_on_heavy, c=np.where(L.und == 'NIFTY', '#2b6cb0', '#dd6b20')); m = max(L.S_heavy.max(), 1); ax[1, 1].plot([0, 100], [0, 100], 'k:', lw=.8); ax[1, 1].set_xlim(0, 110); ax[1, 1].set_xlabel('short lots on the heavier side at the first lump order'); ax[1, 1].set_ylabel('v_ lump lots on that side'); ax[1, 1].set_title('(d) Overnight lump size vs heavier-side shorts (blue NIFTY, orange SENSEX)')
plt.tight_layout(); plt.savefig(f'{FIG}/bl_hg_summary.png', dpi=130); print('ok')
