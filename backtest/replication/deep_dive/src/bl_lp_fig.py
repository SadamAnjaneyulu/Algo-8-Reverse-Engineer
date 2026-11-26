"""Figure for the lump study: reports/figures/bl_lp_summary.png"""
import sys, os; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv').reset_index().rename(columns={'index': 'cid'}); D = pd.read_csv(f'{OUT}/bl_lp_dec.csv').merge(CY[['cid', 'd1']], on='cid'); RK = pd.read_csv(f'{OUT}/bl_lp_risk.csv'); Q = pd.read_csv(f'{OUT}/bl_lp_d0.csv')
col = lambda u: np.where(u == 'NIFTY', '#2b6cb0', '#dd6b20'); fig, ax = plt.subplots(2, 2, figsize=(14, 9)); D['d1'] = pd.to_datetime(D.d1)
for main, mk, s in ((1, 'o', 60), (0, 'x', 30)):
    q = D[D.main == main]; ax[0, 0].scatter(q.d1, (q.t - 54000) / 60, c=col(q.und), marker=mk, s=s, label='main decision' if main else 'top-up')
for y in (6, 14, 23, 30): ax[0, 0].axhline(y, color='#cbd5e0', lw=.8)
ax[0, 0].set_ylabel('minutes after 15:00'); ax[0, 0].set_title('(a) Lump time vs D-1 date: three clock regimes (blue NIFTY, orange SENSEX)'); ax[0, 0].legend(fontsize=8); ax[0, 0].tick_params(axis='x', labelsize=8)
M = D[D.main == 1]; ax[0, 1].scatter(M.S_h, M.lots, c=col(M.und)); xx = np.array([0, 100])
for u, c_ in (('NIFTY', '#2b6cb0'), ('SENSEX', '#dd6b20')): r = (M[M.und == u].lots / M[M.und == u].S_h).median(); ax[0, 1].plot(xx, r * xx, color=c_, ls='--', label=f'{u}: lots = {r:.2f} × S_heavy (median)')
ax[0, 1].plot(xx, xx, 'k:', lw=.8); ax[0, 1].set_xlim(0, 100); ax[0, 1].set_ylim(0, 100); ax[0, 1].set_xlabel('heavy-side short lots at the decision'); ax[0, 1].set_ylabel('lump lots (main decision)'); ax[0, 1].legend(fontsize=8); ax[0, 1].set_title('(b) Size: tracks heavy-side shorts, ~24% error')
ax[1, 0].scatter(-RK.worst_pre / 1e5, -RK.worst_post / 1e5, c=col(RK.und)); ax[1, 0].plot([0, 55], [0, 55], 'k:', lw=.8); ax[1, 0].set_xlabel('worst loss in the heavy direction before the lump (₹ lakh)'); ax[1, 0].set_ylabel('after the lump (₹ lakh)'); ax[1, 0].set_title('(c) Lump halves the heavy-direction tail (expiry intrinsic, 0–6% move)')
q = Q.copy(); q['ratio'] = q.sell_px / q.buy_px; q = q.sort_values('ratio'); ax[1, 1].bar(range(len(q)), q.ratio.fillna(0), color=col(q.und)); ax[1, 1].axhline(1, ls='--', color='k', lw=.8); ax[1, 1].set_xticks([]); ax[1, 1].set_ylabel('D0 sale price ÷ purchase price'); ax[1, 1].set_title(f'(d) D0: v_ sells in {int((Q.sold_d0 > 0).sum())} of {len(Q)} cycles, never above cost (0 = not sold by v_)')
plt.tight_layout(); plt.savefig(f'{FIG}/bl_lp_summary.png', dpi=130); print('ok')
