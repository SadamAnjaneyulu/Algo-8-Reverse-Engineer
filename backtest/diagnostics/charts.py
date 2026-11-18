import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from common import *
d = cycles('HOLD', 'HOLD_SETTLE').sort_values(['d0', 'und']); d['d0'] = pd.to_datetime(d.d0)
# 1 cumulative net by cycle date, IS/OOS, exposed window shaded
fig, ax = plt.subplots(figsize=(11, 4)); c = d.net.cumsum() / 1e3; ax.plot(d.d0, c, lw=1.2); ax.axvline(pd.Timestamp('2025-11-18'), c='k', ls='--', lw=.8); ax.axvspan(pd.Timestamp('2026-06-22'), pd.Timestamp('2026-10-22'), color='orange', alpha=.2, label='exposed window (inspected)')
ax.set_title('Cumulative net P&L (₹k), NIFTY+SENSEX, HOLD baseline (dashed = IS/OOS boundary)'); ax.legend(); plt.tight_layout(); plt.savefig(f'{FIG}/cumulative_net.png', dpi=130); plt.close()
# 2 ranked cycle P&L OOS
o = d[d.split == 'OOS'].sort_values('net', ascending=False); fig, ax = plt.subplots(figsize=(11, 3.6)); ax.bar(range(len(o)), o.net / 1e3, color=['#2a9d8f' if v > 0 else '#c0392b' for v in o.net]); ax.axvline(4.5, c='k', ls=':'); ax.set_title('OOS cycles ranked by net P&L (₹k); dotted = top 5'); plt.tight_layout(); plt.savefig(f'{FIG}/oos_ranked_cycles.png', dpi=130); plt.close()
# 3 time decomposition
g = pd.read_csv(f'{RES}/pnl_time_decomposition_summary.csv'); g = g[g.group == 'ALL'].set_index('part')[['d1_session', 'overnight_gap', 'd0_to_1529', 'settlement_step']] / 1e3
g.plot.bar(figsize=(8, 4)); plt.title('Net P&L by time segment (₹k), HOLD baseline'); plt.axhline(0, c='k', lw=.6); plt.tight_layout(); plt.savefig(f'{FIG}/pnl_time_segments.png', dpi=130); plt.close()
# 4 leg attribution
s = pd.read_csv(f'{RES}/leg_attribution_summary.csv'); s = s[s.scope == 'COMBINED'].pivot(index='part', columns='leg', values='net_pnl').loc[['IS', 'OOS', 'OOS_exposed', 'OOS_clean']] / 1e3
s.plot.bar(figsize=(8, 4)); plt.title('Net P&L by leg (₹k), HOLD baseline'); plt.axhline(0, c='k', lw=.6); plt.tight_layout(); plt.savefig(f'{FIG}/leg_attribution.png', dpi=130); plt.close()
# 5 slippage scan
b = pd.read_csv(f'{RES}/slippage_scan.csv'); fig, ax = plt.subplots(1, 2, figsize=(11, 3.8), sharey=False)
for a, col, t in zip(ax, ('net_original_settle', 'net_yahoo_settle'), ('original settlement proxy', 'official-close (Yahoo) settlement')):
    for p in ('IS', 'OOS', 'OOS_clean', 'OOS_exposed'): x = b[b.part == p]; a.plot(x.slip_multiple, x[col] / 1e3, marker='o', label=p)
    a.axhline(0, c='k', lw=.6); a.set_title(f'Net P&L (₹k) vs slippage multiple\n{t}'); a.set_xlabel('× base slippage (0.5% of price, min ₹0.10)'); a.legend()
plt.tight_layout(); plt.savefig(f'{FIG}/slippage_scan.png', dpi=130); plt.close()
# 6 premium vs realised move
F = pd.read_csv(f'{RES}/regime_features_cycles.csv'); F['grp'] = np.where(F.split == 'IS', 'IS', np.where(F.subset == 'OOS_EXPOSED', 'OOS exposed', 'OOS clean'))
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for a, u in zip(ax, ('NIFTY', 'SENSEX')):
    for gname, col in (('IS', '#888'), ('OOS clean', '#c0392b'), ('OOS exposed', '#e67e22')): x = F[(F.und == u) & (F.grp == gname)]; a.scatter(x.prem_pct_spot, x.abs_move_pct, s=14, alpha=.6, c=col, label=gname)
    a.plot([0, 2.5], [0, 2.5], 'k--', lw=.7); a.set_title(f'{u}: |close−K| vs straddle premium (% of strike)\nabove the line = short straddle loses'); a.set_xlabel('premium %'); a.set_ylabel('|move| %'); a.legend()
plt.tight_layout(); plt.savefig(f'{FIG}/premium_vs_move.png', dpi=130); plt.close()
# headline table
rows = []
for lab, name, var in (('HOLD_SETTLE baseline', 'HOLD', 'HOLD_SETTLE'), ('Frozen cut+re-entry', 'cut_t20000_f10000_re_cd1800band', 'HOLD_SETTLE'), ('FLATTEN_1525 (HOLD)', 'HOLD', 'FLATTEN_1525')):
    t = cycles(name, var)
    for p in ('IS', 'OOS', 'OOS_exposed', 'OOS_clean'):
        s_ = M.summarize(part(t, p)); rows.append(dict(config=lab, part=p, **{k: s_[k] for k in ('cycles', 'weeks', 'net_pnl', 'cum_return_pct', 'ann_return_pct', 'vol_ann_pct', 'sharpe', 'sortino', 'max_dd_rs', 'max_dd_pct', 'win_rate_pct', 'profit_factor', 'best_cycle', 'worst_cycle')}))
pd.DataFrame(rows).to_csv(f'{RES}/headline_metrics.csv', index=False); print(pd.DataFrame(rows).round(2).to_string(index=False))
