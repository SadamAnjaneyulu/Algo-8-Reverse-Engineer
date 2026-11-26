"""Pace study example plots (same cycles as the tracker study): reports/figures/bl_pc_example_NIFTY.png, bl_pc_example_SENSEX.png
Rows: spot + 70-min band + actual pairs | cumulative reactive pairs vs the 1-per-30-min pace line (from 10:30) with the pace tracker's fires | range position with 'armed' (behind pace) shading | book net delta (all modules) with pairs and other-module orders."""
import sys, os, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import *
src = open('bl_bk_build.py').read().split('def feats')[0]; exec(src)
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); PC = pd.read_csv(f'{OUT}/bl_pc_fires.csv'); cid_of = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}; unit = {(r.und, r.expiry): r.unit for r in CY.itertuples()}; D_MIN = 30; T0 = 4500
EX = {'NIFTY': '2026-09-08', 'SENSEX': '2026-10-22'}; R = {}
def plot(und):
    e = EX[und]; k = (und, e); cb = CycleBook(und, e, unit[k]); sp = cb.sp; step = cb.step; T = np.arange(375); x = (33300 + 60 * T) / 3600; cid = cid_of[k]
    g = Pr[(Pr.und == und) & (Pr.expiry == e)].sort_values('te'); rp = g[g.reactive]; sc = g[g.sched]; z = O[(O.und == und) & (O.expiry == e) & (O.dayno == 0)]; oth = z[z.module != 'num'].te.values; bb = z[(z.module == 'num') & (z.role == 'cover_short')].te.values
    N = 70; hi = np.array([sp[max(j - N, 0):j].max() if j > 0 else sp[0] for j in T]); lo = np.array([sp[max(j - N, 0):j].min() if j > 0 else sp[0] for j in T]); pos = np.array([(sp[j] - sp[max(j - N, 0):j + 1].min()) / max(np.ptp(sp[max(j - N, 0):j + 1]), 1e-6) - 0.5 for j in T])
    mf = PC[(PC.family == 'M10') & (PC['info'] == 'bar') & (PC.cid == cid)]; mfm = mf.minute.values; tt = np.arange(33300, 54900, 30); ra = rp.te.values
    cum = np.array([np.sum(ra < t) for t in tt]); tgt = np.maximum(0, (tt - 33300 - T0) / (D_MIN * 60)); deficit = tgt - cum
    fig, ax = plt.subplots(4, 1, figsize=(15, 13.5), sharex=True, gridspec_kw=dict(height_ratios=[2.6, 1.8, 1.4, 1.6])); a = ax[0]
    a.plot(x, sp, color='#333', lw=1); a.fill_between(x, lo, hi, color='#1f77b4', alpha=.10); a.plot(x, hi, color='#1f77b4', lw=.6); a.plot(x, lo, color='#1f77b4', lw=.6)
    for r in rp.itertuples():
        j = int((r.te - 33300) // 60); f = ((r.te - 33300) % 60) / 60; live = sp[max(j - 1, 0)] + f * (sp[min(j, 374)] - sp[max(j - 1, 0)]); up = r.strike > cb.K[np.argmin(np.abs(cb.K - live))]; a.plot(r.te / 3600, live, '^' if up else 'v', color='#d62728' if up else '#1f77b4', ms=9, zorder=5); a.axvline(r.te / 3600, color='#d62728' if up else '#1f77b4', lw=.6, ls='--', alpha=.5)
    a.axvspan(10.5, 15.25, color='#ffd54f', alpha=.08); a.set_ylabel('spot'); a.set_title(f'{und} D-1 {e}: reactive pairs (triangles) against a pace of one reactive entry per 30 minutes from 10:30')
    a = ax[1]; a.step(tt / 3600, cum, where='post', color='#d62728', lw=1.6, label='cumulative reactive pairs (actual)'); a.plot(tt / 3600, tgt, color='k', ls='--', lw=1.2, label='pace line: one per 30 min from 10:30'); a.fill_between(tt / 3600, cum, tgt, where=tgt - cum >= 1, color='#2ca02c', alpha=.2, step='post', label='behind pace by >= 1 pair ("armed")')
    a.scatter(33300 / 3600 + 60 * mfm / 3600, [0.3] * len(mfm), marker='x', color='k', s=40, label=f'pace-tracker fires (out-of-fold; range edge AND behind pace)'); a.set_ylabel('pairs'); a.legend(fontsize=7, loc='upper left')
    a = ax[2]; a.plot(x, pos, color='#555', lw=.9); a.axhline(.5, color='k', ls=':', lw=.6); a.axhline(-.5, color='k', ls=':', lw=.6); armed = np.interp(x * 3600, tt, (deficit >= 1).astype(float)) > .5; a.fill_between(x, -.75, .75, where=armed, color='#2ca02c', alpha=.12); a.scatter(ra / 3600, [0] * len(ra), color='#d62728', s=30, zorder=5, label='actual reactive pairs'); a.set_ylim(-.75, .75); a.set_ylabel('position in 70-min range\n(green = armed)'); a.legend(fontsize=7, loc='upper left')
    tm = np.arange(33300 + 60, 54900, 60); dl = []
    for t in tm: j = int((t - 33300) // 60); pm = min(max(j - 1, 0), 374); f = cb.state(t, sp[max(j - 1, 0)], pm); dl.append(f.get('delta', np.nan))
    a = ax[3]; a.plot(tm / 3600, dl, color='#9467bd', lw=1.1, label='book net delta (lots-equivalent, all modules)'); a.axhline(0, color='k', lw=.6)
    for t in ra: a.axvline(t / 3600, color='#d62728', lw=.6, alpha=.6)
    a.scatter(oth / 3600, [np.nanmin(dl)] * len(oth), marker='|', color='#7f7f7f', s=40, label='hedge/stop/lump orders'); a.set_ylabel('net delta (lots)'); a.legend(fontsize=7, loc='upper right'); a.set_xlim(9.25, 15.5); a.set_xticks(np.arange(9.25, 15.6, .5)); a.set_xticklabels([f'{int(h)}:{int(round((h % 1) * 60)):02d}' for h in np.arange(9.25, 15.6, .5)]); a.set_xlabel('time of day (D-1); red lines = reactive pairs')
    plt.tight_layout(); plt.savefig(f'{FIG}/bl_pc_example_{und}.png', dpi=125); plt.close(); R[und] = dict(expiry=e, pairs=int(len(ra)), fires=int(len(mf)), delta_range=[float(np.nanmin(dl)), float(np.nanmax(dl))]); print(und, R[und])
for u in EX: plot(u)
rec('pc3', R)
