"""Figure and one descriptive diagnosis for reports/LATE_SALE_FOCUSED.md -> outputs/trig3/focused.png, focused_extra.json.
Diagnosis (NOT pre-registered, descriptive): where in the window the straddle effect sits, by splitting the post-auction AUC at 15:29/15:30."""
import os, sys, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
import bl_trig3_focused as T
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); T3 = f'{OUT}/trig3'; r = json.load(open(f'{T3}/focused.json')); CL = pd.read_csv(f'{T3}/close_long.csv'); E = pd.read_csv(f'{OUT}/trig2/events.csv')
SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'; BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK, 'font.size': 8.5, 'axes.titlesize': 9.5, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left', 'axes.spines.top': False, 'axes.spines.right': False, 'grid.color': GRID, 'axes.grid': True, 'axes.axisbelow': True})
Ma = pd.read_csv(f'{T3}/state_after.csv'); ca, nj, X = T.cubes(Ma, ['STR15', 'y'], 360, 384); Y = X['y'].astype(int); R = T.ranks(X['STR15'])
def part(a, b): Rr = T.ranks(X['STR15'][:, :, a:b]); return T.auc(Rr, Y[:, :, a:b], b - a)
ex = dict(auc_360_374=part(0, 15), auc_375_384=part(15, 25), auc_full=T.auc(R, Y, nj), sale_minutes_360_374=int(Y[:, :, :15].sum()), sale_minutes_375_384=int(Y[:, :, 15:].sum())); json.dump(ex, open(f'{T3}/focused_extra.json', 'w'), indent=1)
fig, ax = plt.subplots(1, 3, figsize=(15, 4.7)); a = ax[0]
lab = ['post-auction\n(development)', 'pre-auction\n(held-out)']; sh = [r['F2a']['contrarian_share'], r['F2a_heldout']['contrarian_share']]; ci = [r['F2a']['ci95'], r['F2a_heldout']['ci95']]; n = [r['F2a']['single_side_minutes'], r['F2a_heldout']['single_side_minutes']]
a.bar(range(2), sh, color=[BLUE, AQUA], width=0.55, edgecolor=INK2, lw=0.7)
for i in range(2): a.plot([i, i], ci[i], color=INK, lw=1.6); a.text(i, 0.03, f'{sh[i]:.0%}\n{n[i]} minutes', ha='center', color='white' if True else INK, fontsize=9, fontweight='bold')
a.axhline(0.5, color=INK2, lw=0.9, ls='--'); a.set_ylim(0, 1.05); a.set_xticks(range(2)); a.set_xticklabels(lab); a.set_ylabel('share of single-side minutes where the side sold was the contrarian one'); a.set_title('Side follows the move away from it, in both eras'); a.grid(axis='x', visible=False)
b = ax[1]; rng = np.random.default_rng(3); pl = []; Rfix = R
for _ in range(1000): pl.append(T.auc(Rfix[rng.permutation(len(ca))], Y, nj))
b.hist(pl, bins=30, color=GRID, edgecolor=INK2, lw=0.5); b.axvline(r['F1p']['post_auc'], color=BLUE, lw=2.2); b.axvline(ex['auc_360_374'], color=ORANGE, lw=2.2, ls='--'); b.axvline(r['F1']['auc'], color=AQUA, lw=2.2)
b.text(0.02, 0.97, f"post, 15:15–15:39: {r['F1p']['post_auc']:.3f}\npost, 15:15–15:29 only: {ex['auc_360_374']:.3f}\npost, 15:30–15:39 only: {ex['auc_375_384']:.3f}\npre-auction held-out: {r['F1']['auc']:.3f}\n(power of the held-out test ≈ {r['F1']['power_estimate_7cycles_15min']:.0%})", transform=b.transAxes, va='top', fontsize=8.5)
b.set_xlabel('stratified AUC of the 15-min straddle change (below 0.5 = sale after a decline)'); b.set_ylabel('placebo draws (cycles shuffled)'); b.set_title('Straddle signal: beats the placebo, not confirmed on held-out'); b.grid(axis='x', visible=False)
c = ax[2]; A = CL[CL.era == 'after'].copy(); EE = E; gaps = []
for q in A.itertuples():
    bb = EE[EE.cyc == q.cyc]
    if len(bb): d = np.where(q.t < bb.t0, bb.t0 - q.t, np.where(q.t > bb.t1, q.t - bb.t1, 0)); gaps.append(float(d.min()))
    else: gaps.append(np.nan)
A['gap'] = gaps; c.scatter(A.gap.clip(lower=0.5), A.ratio, s=28 + 14 * A.lots.clip(upper=6), color=BLUE, alpha=0.7, edgecolor='none'); c.axhline(1.0, color=INK, lw=1.2); c.text(1.2e3, 1.02, 'break-even', ha='right', fontsize=8); c.set_xscale('log'); c.set_xlim(0.4, 1500); c.set_ylim(0, 1.25); c.set_xlabel('seconds to the nearest late short-sale burst (log)'); c.set_ylabel('sale price ÷ entry price of the long sold')
c.set_title(f'Sell-to-close orders: all {len(A)} sold below entry, mostly beside a burst'); c.grid(axis='y', visible=True)
fig.tight_layout(); fig.savefig(f'{T3}/focused.png', dpi=150); plt.close(fig); print(ex)
