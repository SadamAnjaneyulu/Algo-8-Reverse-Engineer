"""Phase 7 charts. Solid markers = ACTUAL observations (ledger fills); hatched/hollow or labelled 'inferred' = reconstructed associations (allocation, replacement links)."""
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from ledger import *
L = pd.read_csv(f'{OUT}/lots.csv.gz'); C = pd.read_csv(f'{OUT}/cycles.csv'); CA = pd.read_csv(f'{OUT}/carried_lots_analysed.csv.gz'); RP = pd.read_csv(f'{OUT}/replacement_pairs.csv.gz') if os.path.exists(f'{OUT}/replacement_pairs.csv.gz') else None
Ck = C[C.carry_in_known]; d0 = Ck.set_index(['und', 'expiry']).d0.to_dict(); d1 = Ck.set_index(['und', 'expiry']).d1.to_dict()
B = L[(L.role == 'body') & (L.side == 'SHORT') & (~L.entry_unrecorded) & L.set_index(['index', 'expiry']).index.isin(Ck.set_index(['und', 'expiry']).index)].copy()
B['t_in'] = [(0 if dd == d1[(u, e)] else 86400) + s for u, e, dd, s in zip(B['index'], B.expiry, B.entry_day, B.entry_sec)]
B['t_out'] = [np.inf if reason == 'SETTLEMENT' else (0 if dd == d1[(u, e)] else 86400) + s for u, e, reason, dd, s in zip(B['index'], B.expiry, B.close_reason, B.close_day, B.close_sec)]
B['hold_h'] = np.where(np.isfinite(B.t_out), (B.t_out - B.t_in) / 3600, np.nan)
# 1. lifecycle timelines for individual lots (one holdout-label cycle, 120 lots sample)
u, e = 'SENSEX', '2026-10-01'; x = B[(B['index'] == u) & (B.expiry == e)].sort_values('t_in'); x = x.iloc[::max(len(x) // 120, 1)].head(120)
fig, ax = plt.subplots(figsize=(12, 7))
for i, r in enumerate(x.itertuples()):
    end = r.t_out if np.isfinite(r.t_out) else 86400 + 15.5 * 3600; ax.plot([r.t_in / 3600, end / 3600], [i, i], color={'BODY_BUYBACK': '#264653', 'STOP_MODULE': '#d00000', 'SETTLEMENT': '#2a9d8f'}.get(r.close_reason, '#999'), lw=1.6, ls='-' if r.alloc_agree_all else '--'); ax.plot(r.t_in / 3600, i, 'k.', ms=3)
ax.axvline(24, c='k', lw=.6); ax.set_title(f'{u} {e}: individual body short lots (every 4th). x = hours since D-1 midnight (24 = D0 midnight). Dashed = closing fill depends on the allocation convention (INFERRED); solid = same fill under all 4 conventions'); ax.set_xlabel('hour'); ax.set_ylabel('lot'); plt.tight_layout(); plt.savefig(f'{FIG}/01_lot_lifecycle_timelines.png', dpi=110); plt.close()
# 2. carried lots entering D0
cc = CA.groupby('cycle_id').size(); fig, ax = plt.subplots(1, 2, figsize=(12, 4)); cc.plot.bar(ax=ax[0], color='#264653'); ax[0].set_title('Carried body short lots per cycle (opened D-1, open at D0 open under any convention)'); ax[0].tick_params(axis='x', labelsize=6); CA.d0_open_ratio.clip(0, 3).hist(bins=40, ax=ax[1], color='#e76f51'); ax[1].set_title('Option price at D0 open / entry price (lots)'); plt.tight_layout(); plt.savefig(f'{FIG}/02_carried_lots.png', dpi=110); plt.close()
# 3. buyback timing distribution under the 4 conventions
fig, ax = plt.subplots(figsize=(11, 4)); rowsec = None
F = load_fills(); rs = F.set_index('row').sec.to_dict(); rd = F.set_index('row').day.to_dict(); rm = F.set_index('row').module.to_dict()
for cv in ('FIFO', 'LIFO', 'LOW_ENTRY_FIRST', 'HIGH_ENTRY_FIRST'):
    rows = [r for r in CA[f'close_row_{cv}'] if r >= 0 and rm.get(r) == 'num']; mins = [rs[r] // 60 - 555 for r in rows]; ax.hist(mins, bins=np.arange(0, 380, 5), histtype='step', label=f'{cv} ({len(mins)} buy-backs)', lw=1.4)
ax.set_title('Minute of D0 at which carried lots are closed by BODY buy-backs, by allocation convention (INFERRED allocation; buy-back times are ACTUAL)'); ax.set_xlabel('minutes since 09:15'); ax.legend(); plt.tight_layout(); plt.savefig(f'{FIG}/03_buyback_timing_by_convention.png', dpi=110); plt.close()
# 4. holding-duration distribution
fig, ax = plt.subplots(figsize=(11, 4)); 
for rsn, col in (('BODY_BUYBACK', '#264653'), ('STOP_MODULE', '#d00000')): B[B.close_reason == rsn].hold_h.clip(0, 30).hist(bins=60, alpha=.6, label=rsn, ax=ax, color=col)
ax.set_title('Holding duration of body short lots (hours; FIFO; settled lots excluded)'); ax.legend(); plt.tight_layout(); plt.savefig(f'{FIG}/04_holding_duration.png', dpi=110); plt.close()
# 5. entry vs buyback premium
cl = B[B.close_reason == 'BODY_BUYBACK']; fig, ax = plt.subplots(figsize=(6, 6)); ax.scatter(cl.entry_price, cl.close_price, s=3, alpha=.25); m = max(cl.entry_price.quantile(.99), cl.close_price.quantile(.99)); ax.plot([0, m], [0, m], 'r--', lw=.8); ax.set_xlim(0, m); ax.set_ylim(0, m); ax.set_title('Entry vs buy-back price per lot (FIFO; below line = profit)'); plt.tight_layout(); plt.savefig(f'{FIG}/05_entry_vs_buyback_premium.png', dpi=110); plt.close()
# 6. MFE / MAE
fig, ax = plt.subplots(1, 2, figsize=(11, 4)); CA.mfe_pts.clip(-50, 600).hist(bins=60, ax=ax[0]); ax[0].set_title('Max favourable excursion on D0 (pts, carried lots)'); CA.mae_pts.clip(-200, 600).hist(bins=60, ax=ax[1], color='#e76f51'); ax[1].set_title('Max adverse excursion on D0 (pts; <0 = never above entry)'); plt.tight_layout(); plt.savefig(f'{FIG}/06_mfe_mae.png', dpi=110); plt.close()
# 7. lot-level realised P&L distribution with convention spread
fig, ax = plt.subplots(figsize=(11, 4)); 
for cv in ('FIFO', 'LIFO', 'LOW_ENTRY_FIRST', 'HIGH_ENTRY_FIRST'): B[f'pnl_{cv}'].clip(-60000, 60000).hist(bins=100, histtype='step', label=cv, ax=ax)
ax.set_title('Lot-level realised P&L (Rs, body shorts) under four allocation conventions: same cycle totals, different lot distributions'); ax.legend(); plt.tight_layout(); plt.savefig(f'{FIG}/07_lot_pnl_distribution.png', dpi=110); plt.close()
# 8. CE vs PE
fig, ax = plt.subplots(1, 2, figsize=(11, 4)); 
for cp, col in (('CE', '#2a9d8f'), ('PE', '#e76f51')): B[B.cp == cp].hold_h.clip(0, 30).hist(bins=50, alpha=.5, label=cp, ax=ax[0], color=col); B[B.cp == cp].pnl_FIFO.clip(-30000, 30000).hist(bins=60, alpha=.5, label=cp, ax=ax[1], color=col)
ax[0].set_title('Holding hours CE vs PE'); ax[1].set_title('Lot P&L CE vs PE (FIFO)'); ax[0].legend(); plt.tight_layout(); plt.savefig(f'{FIG}/08_ce_vs_pe.png', dpi=110); plt.close()
# 9. strike distance vs holding
B['off'] = B.apply(lambda r: np.nan, axis=1); fig, ax = plt.subplots(figsize=(8, 5)); CA2 = CA.dropna(subset=['hold_minutes_from_d0_open']); ax.scatter(CA2.off_steps_at_d0_open.abs(), CA2.hold_minutes_from_d0_open, s=4, alpha=.3); ax.set_xlabel('|strike offset from spot at D0 open| (steps)'); ax.set_ylabel('minutes from D0 open to close (FIFO)'); ax.set_title('Strike distance vs time to close (carried lots closed on D0; FIFO)'); plt.tight_layout(); plt.savefig(f'{FIG}/09_strike_distance_vs_hold.png', dpi=110); plt.close()
# 10. intraday outstanding short exposure (actual, from the lot engine; convention-free count) averaged over cycles + 2 example cycles
grid = np.arange(0, 376, 5); fig, ax = plt.subplots(1, 2, figsize=(12, 4)); cur = []
for (uu, ee), g in B.groupby(['index', 'expiry']):
    t = 86400 + (555 + grid) * 60; n = [((g.t_in <= tt) & (g.t_out > tt)).sum() for tt in t]; cur.append(n); 
    if (uu, ee) in (('NIFTY', '2026-07-07'), ('SENSEX', '2026-10-01')): ax[1].plot(grid, n, label=f'{uu} {ee}')
ax[0].plot(grid, np.mean(cur, axis=0)); ax[0].set_title('Mean outstanding body short lots through D0 (ACTUAL; 30 cycles)'); ax[1].set_title('Two cycles'); ax[1].legend(); [a.set_xlabel('minutes since 09:15') for a in ax]; plt.tight_layout(); plt.savefig(f'{FIG}/10_outstanding_exposure.png', dpi=110); plt.close()
# 11/12. actual vs reconstructed (sim v2) open-lot count and buyback events
SO = pd.read_csv(f'{OUT}/remediation_orders_V1_none.csv'); fig, ax = plt.subplots(2, 2, figsize=(12, 7))
for k, (uu, ee) in enumerate((('NIFTY', '2026-07-07'), ('SENSEX', '2026-10-01'))):
    g = B[(B['index'] == uu) & (B.expiry == ee)]; t = 86400 + (555 + grid) * 60; act = [((g.t_in <= tt) & (g.t_out > tt)).sum() for tt in t]; so = SO[(SO.und == uu) & (SO.expiry == ee) & (SO.role == 'body')]; start = int(((g.t_in < 86400) & (g.t_out >= 86400)).sum()); sim = [start + (so[(so.j <= j) & (so.side == -1)].lots.sum() - so[(so.j <= j) & (so.side == 1)].lots.sum()) for j in grid]
    ax[0, k].plot(grid, act, label='actual (lot engine)'); ax[0, k].plot(grid, sim, label='reconstructed by rules (RULE SIMULATOR v2 V1, inferred)'); ax[0, k].set_title(f'{uu} {ee}: open body short lots'); ax[0, k].legend(fontsize=7)
    tb = g[g.close_reason == 'BODY_BUYBACK']; ab = np.histogram((tb.t_out - 86400) / 60 - 555, bins=np.arange(0, 380, 15))[0]; sb = np.histogram(so[so.side == 1].j.repeat(so[so.side == 1].lots.astype(int)), bins=np.arange(0, 380, 15))[0]
    ax[1, k].bar(np.arange(0, 375, 15) - 2, ab, width=4, label='actual buy-backs'); ax[1, k].bar(np.arange(0, 375, 15) + 2, sb, width=4, label='rule-simulated buy-backs (inferred)'); ax[1, k].legend(fontsize=7); ax[1, k].set_title('buy-back lots per 15 min')
plt.tight_layout(); plt.savefig(f'{FIG}/11_12_actual_vs_reconstructed.png', dpi=110); plt.close()
# 13. chronological cycle visual with replacement candidates (inferred)
if RP is not None:
    u, e = 'NIFTY', '2026-07-07'; g = B[(B['index'] == u) & (B.expiry == e)]; fig, ax = plt.subplots(figsize=(13, 6)); d = g[g.t_in >= 86400]; ax.scatter((d.t_in - 86400) / 60 - 555, d.strike, c='#2a9d8f', s=6, marker='v', label='D0 entries (actual)'); b = g[(g.close_reason == 'BODY_BUYBACK') & (g.t_out >= 86400)]; ax.scatter((b.t_out - 86400) / 60 - 555, b.strike, c='#264653', s=6, marker='^', label='buy-backs (actual; lot allocation inferred)')
    pr = RP[(RP.und == u) & (RP.expiry == e) & RP.has_candidate & RP.classification.isin(['STRONGLY_SUPPORTED', 'POSSIBLE', 'POSSIBLE_CROSS_RIGHT'])]; opn = L[(L['index'] == u) & (L.expiry == e)].set_index('entry_tag').strike; cls = L[(L['index'] == u) & (L.expiry == e) & (L.role == 'body')].drop_duplicates('close_tag').set_index('close_tag').strike
    for r in pr.itertuples():
        if r.s_tag in opn.index and r.b_tag in cls.index: ax.plot([(r.b_sec / 60) - 555, (r.b_sec + r.delay) / 60 - 555], [cls[r.b_tag], opn[r.s_tag]], c='#e76f51' if r.classification == 'STRONGLY_SUPPORTED' else '#f4a261', lw=.6, alpha=.7)
    S = L[(L['index'] == u) & (L.expiry == e) & (L.close_reason == 'SETTLEMENT') & (L.role == 'body')]; ax.scatter([375] * len(S), S.strike, marker='s', facecolors='none', edgecolors='k', s=12, label='held to settlement (actual)')
    ax.set_title(f'{u} {e} D0: entries, buy-backs, INFERRED replacement links (orange = strongly supported / light = possible), settlement'); ax.set_xlabel('minutes since 09:15'); ax.set_ylabel('strike'); ax.legend(fontsize=7); plt.tight_layout(); plt.savefig(f'{FIG}/13_cycle_chronology_with_links.png', dpi=110); plt.close()
print(sorted(os.listdir(FIG)))
