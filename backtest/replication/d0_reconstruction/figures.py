import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from d0common import *
E = load_events(False); D0 = E[E.day == 'D0']
cols = {'SCHEDULED_SALE': '#2a9d8f', 'OFF_SCHEDULE_SALE': '#e9c46a', 'REPLACEMENT_SALE': '#e76f51', 'BUYBACK': '#264653', 'FINAL_LIQUIDATION': '#6d597a', 'HEDGE_ADD': '#bbb', 'HEDGE_REPLACEMENT': '#999', 'HEDGE_REDUCE': '#ddd', 'STOP_MODULE_ORDER': '#d00000'}
fig, axs = plt.subplots(2, 1, figsize=(12, 8))
for ax, (u, e) in zip(axs, (('SENSEX', '2026-07-02'), ('SENSEX', '2026-10-01'))):
    g = D0[(D0.und == u) & (D0.expiry == e)]; g = g[g.module == 'num']
    for cl, x in g.groupby('event_class'): ax.scatter(x.sec / 3600, x.off_steps, s=np.clip(x.lots * 6, 6, 120), c=cols.get(cl, 'k'), alpha=.6, label=cl, lw=0)
    ax.set_title(f'{u} {e} ({split_of(e)}) — D0 body orders: strike offset from previous-minute ATM (steps) vs time; size = lots'); ax.set_xlabel('IST hour'); ax.set_ylabel('strike offset (steps)'); ax.set_ylim(-12, 12); ax.axhline(0, c='k', lw=.5)
axs[0].legend(ncol=4, fontsize=7); plt.tight_layout(); plt.savefig(f'{FIG}/d0_event_timeline.png', dpi=120); plt.close()
# position-state timelines actual vs sim V1
fig, axs = plt.subplots(2, 2, figsize=(12, 7))
for r, (u, e, sp, f) in enumerate((('SENSEX', '2026-07-02', 'DISCOVERY', 'replay_orders_DISCOVERY_V1.csv'), ('SENSEX', '2026-10-01', 'HOLDOUT', 'replay_orders_HOLDOUT_V1.csv'))):
    O = pd.read_csv(f'{RES}/{f}'); O = O[(O.und == u) & (O.expiry == e) & (O.role == 'body')]; ev = E[(E.und == u) & (E.expiry == e) & (E.module == 'num')]
    for c, cp in enumerate(('CE', 'PE')):
        s0 = ev[(ev.day == 'D-1') & (ev.cp == cp)].assign(x=lambda z: np.where(z.side == 'Sell', z.lots, -z.lots)).x.sum(); a = ev[(ev.day == 'D0') & (ev.cp == cp)].assign(m=lambda z: z.sec / 60 - 555, x=lambda z: np.where(z.side == 'Sell', z.lots, -z.lots)).sort_values('m'); s = O[O.cp == cp].assign(m=lambda z: z.j, x=lambda z: np.where(z.side == -1, z.lots, -z.lots)).sort_values('m')
        axs[r, c].step(a.m / 60 + 9.25, s0 + a.x.cumsum(), where='post', label='actual'); axs[r, c].step(s.m / 60 + 9.25, s0 + s.x.cumsum(), where='post', label='sim V1'); axs[r, c].set_title(f'{u} {e} {sp} — net short body lots {cp}'); axs[r, c].legend(); axs[r, c].set_xlabel('IST hour')
plt.tight_layout(); plt.savefig(f'{FIG}/d0_position_state_timelines.png', dpi=120); plt.close()
# agreement bars
a = pd.read_csv(f'{RES}/compare_events_discovery_V1.csv').assign(split='discovery'); b = pd.read_csv(f'{RES}/compare_events_holdout_V1.csv').assign(split='HOLDOUT'); M = pd.concat([a, b]); cats = list(a.category)
fig, ax = plt.subplots(figsize=(12, 4.5)); w = .2; x = np.arange(len(cats))
for i, (sp, col, lab) in enumerate((('discovery', 'precision_L2', 'disc. precision'), ('discovery', 'recall_L2', 'disc. recall'), ('HOLDOUT', 'precision_L2', 'holdout precision'), ('HOLDOUT', 'recall_L2', 'holdout recall'))): ax.bar(x + (i - 1.5) * w, M[M.split == sp].set_index('category').loc[cats, col].fillna(0), w, label=lab)
ax.axhline(.5, c='r', ls='--', lw=.8); ax.set_xticks(x); ax.set_xticklabels([c[:26] for c in cats], rotation=35, ha='right', fontsize=7); ax.set_title('Variant V1: L2 precision/recall (any strike, 2-min bucket); dashed = pre-registered 0.5 criterion'); ax.legend(fontsize=7); plt.tight_layout(); plt.savefig(f'{FIG}/d0_agreement_by_category.png', dpi=120)
