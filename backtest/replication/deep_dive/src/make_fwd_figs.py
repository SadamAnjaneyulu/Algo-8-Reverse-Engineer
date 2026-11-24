"""Figures for reports/FORWARD_TEST.md (static PNG; palette validated with the dataviz validator: blue/orange/aqua, direct labels + marker shapes as secondary encoding).
fwd_clearance.png, fwd_late_raster.png, fwd_paths.png, fwd_evidence.png, fwd_power.png -> outputs/fwd/"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
import bl_bt3_sim as S, bl_d0x_diag as DG, algo8_d1 as A
OUT = S.OUT; FW = f'{OUT}/fwd'; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16')
SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'; BLUE, ORANGE, AQUA, GREY = '#2a78d6', '#eb6834', '#1baf7a', '#9a9993'
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK, 'font.size': 10, 'axes.titlesize': 11, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left', 'axes.spines.top': False, 'axes.spines.right': False, 'grid.color': GRID, 'grid.linewidth': 0.6, 'axes.grid': True, 'axes.axisbelow': True, 'axes.grid.axis': 'y'})
hm = lambda j: f'{(555 + j) // 60:02d}:{(555 + j) % 60:02d}'
O = DG.real_orders(); O = O.assign(jj=(O.t_last // 60 - 555).astype(int)); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; B = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(B.und, B.expiry))
def fires_fut(r):
    g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.role == 'open_short')]; ev = {cp: sorted(set(g[g.cp == cp].jj.tolist())) for cp in ('CE', 'PE')}
    fut = pd.read_pickle(f'{OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')['spot1']; h, l, c = (fut[k].values.astype(float) for k in ('high', 'low', 'close')); cfg = A.Config(); cfg.ladder_gate_min = 5; cfg.strike_step = 50.0 if r.und == 'NIFTY' else 100.0
    return g, {(j, cp) for j, cps in A.ladder_fires(c, h, l, ev, cfg).items() for cp in cps}
# ---- 1. clearance
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True); xs = np.arange(350, 386)
for a, (era, col, ttl) in zip(ax, (('before', BLUE, 'Before 3 Aug 2026 (9 cycles)'), ('after', ORANGE, 'From 3 Aug 2026 (12 cycles)'))):
    curves = []
    for r in T.itertuples():
        if (r.und, r.expiry) not in keep: continue
        if (r.d0 >= CAS) != (era == 'after'): continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1) & (O.role == 'cover_short') & (O.t_last >= 15 * 3600)]
        if g.lots.sum() < 10: continue
        cv = np.array([g.lots[g.jj <= x].sum() / g.lots.sum() for x in xs]); curves.append(cv); a.plot(xs, cv, color=col, lw=1, alpha=0.45)
    a.plot(xs, np.mean(curves, 0), color=col, lw=2.4); a.axvline(359, color=INK2, ls=':', lw=1.2); a.axvline(364, color=INK2, ls='--', lw=1.2)
    a.set_title(ttl); a.set_xticks([350, 355, 359, 364, 370, 375, 380, 385]); a.set_xticklabels([hm(x) for x in [350, 355, 359, 364, 370, 375, 380, 385]]); a.set_xlabel('minute of day (D0)'); a.text(359.3, 0.04, 'simulator\n15:14', fontsize=8.5, color=INK2); a.text(364.3, 0.20, 'real, before 3 Aug\n15:19', fontsize=8.5, color=INK2)
ax[0].set_ylabel('share of real D0 covers done (after 15:00)'); ax[0].text(350.4, 0.93, 'thin = one cycle, thick = mean', fontsize=8.5, color=INK2); fig.suptitle('D0 clearance clock: real system vs the simulator', x=0.01, ha='left', fontweight='bold', fontsize=12); fig.tight_layout(); fig.savefig(f'{FW}/fwd_clearance.png', dpi=160); plt.close(fig)
# ---- 2. late raster + 3. paths
rows = []; per = []
for r in T.itertuples():
    if (r.und, r.expiry) not in keep or r.d0 < CAS or (r.und, r.d1) == OUTLIER: continue
    g, pred = fires_fut(r); late = g[g.jj >= 360]; pred = {x for x in pred if 359 <= x[0] <= 385}
    if not len(late): continue
    per.append((r, late, pred))
fig, ax = plt.subplots(figsize=(11, 6.6)); labels = []
for i, (r, late, pred) in enumerate(per):
    y0 = len(per) - 1 - i; labels.append((y0, f'{r.und[:3]} {r.d1[5:]}'))
    for (j, cp) in pred: ax.plot([j, j], [y0 + (0.13 if cp == 'CE' else -0.13) - 0.1, y0 + (0.13 if cp == 'CE' else -0.13) + 0.1], color=GREY, lw=1.2, zorder=1)
    for (j, cp), gg in late.groupby(['jj', 'cp']):
        m = any((j + d, cp) in pred for d in (-1, 0, 1)); yy = y0 + (0.13 if cp == 'CE' else -0.13); n = gg.lots.sum()
        ax.scatter(j, yy, s=18 + 12 * min(n, 12), marker='v' if cp == 'CE' else '^', facecolor=INK if m else SURF, edgecolor=INK, lw=1.1, zorder=3)
ax.set_xlim(358.5, 386.5); ax.set_yticks([l[0] for l in labels]); ax.set_yticklabels([l[1] for l in labels], fontsize=8.5); ax.set_xticks([360, 365, 370, 375, 380, 384]); ax.set_xticklabels([hm(x) for x in [360, 365, 370, 375, 380, 384]]); ax.set_ylim(-0.8, len(per) - 0.1); ax.grid(axis='y', alpha=0.4)
ax.axvline(374.5, color=INK2, ls=':', lw=1); ax.text(375.0, len(per) - 0.35, 'index frozen from 15:29', fontsize=8.5, color=INK2, va='bottom')
ax.set_title('Real late D-1 sales (15:15–15:40) vs ladder fires on futures, gate 5'); ax.set_xlabel('minute of day (D-1)'); ax.text(0.995, 0.01, '▼ call sale   ▲ put sale   filled = matched ±1 min   hollow = unmatched   marker size = lots in that minute   grey tick = rule fire', transform=ax.transAxes, ha='right', fontsize=8.5, color=INK2)
fig.tight_layout(); fig.savefig(f'{FW}/fwd_late_raster.png', dpi=160); plt.close(fig)
ex = [('SENSEX', '2026-10-21'), ('NIFTY', '2026-10-05'), ('NIFTY', '2026-08-24')]; fig, axs = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
for a, (u, d1) in zip(axs, ex):
    r = [x for x in per if x[0].und == u and x[0].d1 == d1][0][0]; late = [x for x in per if x[0].und == u and x[0].d1 == d1][0][1]; step = 50.0 if u == 'NIFTY' else 100.0
    cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); U = {'FEED': (cx['spot1'], BLUE, '-'), 'FUT': (pd.read_pickle(f'{OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')['spot1'], ORANGE, '-'), 'OPT': (pd.read_pickle(f'{OUT}/bt3s/{r.und}_{r.expiry}.pkl.gz')['spot1'], AQUA, '--')}
    xs = np.arange(345, 385); lo = 1e9
    for nm, (s, col, ls) in U.items():
        v = (s.close.values[345:385] - s.close.values[359]) / step; a.plot(xs, v, color=col, lw=1.8, ls=ls); a.text(384.3, v[-1], nm, color=col, fontsize=9, va='center'); lo = min(lo, np.nanmin(v))
    a.axvline(360, color=INK2, ls=':', lw=1); a.axvline(374.5, color=INK2, ls=':', lw=1); a.axhline(0, color=GRID, lw=1)
    for q in late.itertuples(): a.scatter(q.t_last / 60 - 555, lo - 0.25 - (0.35 if q.cp == 'PE' else 0), marker='v' if q.cp == 'CE' else '^', s=26, color=INK, zorder=3)
    a.set_title(f'{u} D-1 {d1}'); a.set_ylabel('strike steps vs 15:14 close'); a.text(360.3, a.get_ylim()[1] * 0.92, '15:15 stocks stop', fontsize=8.5, color=INK2); a.text(374.8, a.get_ylim()[1] * 0.92, '15:29 index frozen', fontsize=8.5, color=INK2)
axs[-1].set_xticks([345, 350, 355, 360, 365, 370, 375, 380, 384]); axs[-1].set_xticklabels([hm(x) for x in [345, 350, 355, 360, 365, 370, 375, 380, 384]]); axs[-1].set_xlabel('minute of day'); axs[0].text(0.01, 0.04, '▼ call sale (lower strip)  ▲ put sale', transform=axs[0].transAxes, fontsize=8.5, color=INK2)
fig.suptitle('Three candidate underlyings through the closing auction, with the real late sales', x=0.01, ha='left', fontweight='bold', fontsize=12); fig.tight_layout(); fig.savefig(f'{FW}/fwd_paths.png', dpi=160); plt.close(fig)
# ---- 4. evidence
S_ = json.load(open(f'{OUT}/trig/summary.json')); FU = json.load(open(f'{OUT}/trig/followup.json')); AU = pd.read_csv(f'{OUT}/trig/auc_after.csv').set_index('feature')
fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.6)); a = ax[0]; items = [('FEED', S_['after']['combo'][0], BLUE), ('FUT', S_['after']['combo'][1], ORANGE), ('OPT', S_['after']['combo'][2], AQUA)]
for k, (nm, c, col) in enumerate(items):
    y = 2 - k; a.plot(c['oof_ci'], [y, y], color=col, lw=3); a.scatter(c['oof_auc'], y, color=col, s=60, zorder=3, marker='o'); a.scatter(c['clock_auc'], y, color=INK2, s=45, marker='|', zorder=3); a.text(0.505, y + 0.22, nm, fontsize=9, color=INK)
a.axvline(0.5, color=GRID, lw=1); a.set_yticks([]); a.set_xlim(0.5, 0.9); a.set_ylim(-0.6, 2.7); a.set_xlabel('out-of-fold AUC (within cycle × side)'); a.set_title('After 3 Aug: model vs the clock baseline'); a.text(0.505, -0.45, '● model, 95% cycle bootstrap   | clock baseline (same for all)', fontsize=8.5, color=INK2); a.grid(axis='x', alpha=0.5); a.grid(axis='y', visible=False)
a = ax[1]; feats = [('mv1', '1-min move'), ('ext5', 'fresh 5-min extreme')]; fo = FU['side']
for r_, (f, ttl) in enumerate(feats):
    for k, (nm, col) in enumerate((('FEED', BLUE), ('FUT', ORANGE), ('OPT', AQUA))):
        y = (1 - r_) * 3.4 + (2 - k) * 0.9; row = AU.loc[f'{nm}_{f}']
        a.plot([row.lo, row.hi], [y, y], color=col, lw=3); a.scatter(row.auc, y, color=col, s=55, zorder=3)
        a.scatter(fo[f'{nm}_CE'][f], y + 0.0, color=INK, s=22, marker='v', zorder=4); a.scatter(fo[f'{nm}_PE'][f], y, color=INK, s=22, marker='^', zorder=4); a.text(0.255, y, nm, fontsize=8.5, color=INK, va='center')
    a.text(0.255, (1 - r_) * 3.4 + 2.45, ttl, fontsize=9.5, fontweight='bold')
a.axvline(0.5, color=GRID, lw=1); a.set_yticks([]); a.set_xlim(0.25, 0.85); a.set_ylim(-0.4, 6.4); a.set_xlabel('AUC of the directional score (within cycle × side)\n▼ call side   ▲ put side   bar = pooled 95% CI'); a.set_title('Directional signal by underlying'); a.grid(axis='x', alpha=0.5); a.grid(axis='y', visible=False)
fig.tight_layout(); fig.savefig(f'{FW}/fwd_evidence.png', dpi=160); plt.close(fig)
# ---- 5. power
P1 = pd.read_csv(f'{FW}/power.csv'); P2 = pd.read_csv(f'{FW}/power_auc.csv'); fig, ax = plt.subplots(figsize=(8.6, 4.6))
ax.plot(P2.cycles, P2.power_at_dev, color=ORANGE, lw=2.2, marker='o'); ax.plot(P2.cycles, P2.power_at_half, color=ORANGE, lw=2.2, ls='--', marker='o'); ax.plot(P1.cycles, P1.power_at_dev_effect, color=BLUE, lw=2.2, marker='s'); ax.plot(P1.cycles, P1.power_at_half, color=BLUE, lw=2.2, ls='--', marker='s')
ax.axhline(0.8, color=INK2, lw=1, ls=':'); ax.text(9, 0.81, '80% power', fontsize=8.5, color=INK2, ha='left'); ax.set_xlim(8, 125); ax.set_ylim(0, 1.03); ax.set_xticks([10, 20, 30, 40, 60, 80, 120]); ax.set_xticklabels(['10\n5 wk', '20\n10 wk', '30\n15 wk', '40\n20 wk', '60\n30 wk', '80\n40 wk', '120\n60 wk']); ax.set_xlabel('forward cycles (two indices per week)'); ax.set_ylabel('power, 5% two-sided')
ax.text(33, 0.86, 'AUC test, true effect = observed (+0.098)', color=ORANGE, fontsize=9); ax.text(41, 0.45, 'AUC test, true effect = half', color=ORANGE, fontsize=9); ax.text(62, 0.74, 'F1 test, effect = observed (+0.15)', color=BLUE, fontsize=9); ax.text(61, 0.28, 'F1 test, effect = half', color=BLUE, fontsize=9)
ax.set_title('How many forward cycles settle the question?'); fig.tight_layout(); fig.savefig(f'{FW}/fwd_power.png', dpi=160); plt.close(fig); print('ok')
