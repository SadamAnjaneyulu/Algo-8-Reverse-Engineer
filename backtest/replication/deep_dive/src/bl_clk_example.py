"""Clock-bar study example plots (same cycles as the earlier examples): reports/figures/bl_clk_example_NIFTY.png, bl_clk_example_SENSEX.png, outputs/bl_clk_example_<UND>.csv
Rows: spot with 30-min clock grid, the channel of the previous two completed 30-min bars, machine first breaks and every real reactive pair | bar strip (30-min blocks: match / machine only / actual only / neither) | event timeline incl. scheduled pairs and the hedge-wing buys that follow."""
import sys, os, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from bl_common import *
sys.argv = ['x']; exec(open('bl_clk_refine.py').read().split("rows = []\nfor nm, fn")[0])
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); O = load_orders(); EX = {'NIFTY': '2026-09-08', 'SENSEX': '2026-10-22'}; Rr = {}
hhmm = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'
def plot(und):
    e = EX[und]; d = [x for x in CYC if x['und'] == und and CY.expiry.iloc[x['cid']] == e][0]; sp = d['sp']; step = ref.STEP[und]; T = np.arange(375); x = (33300 + 60 * T) / 3600
    g = Pr[(Pr.und == und) & (Pr.expiry == e)].sort_values('te'); rp = g[g.reactive]; sc = g[g.sched]; z = O[(O.und == und) & (O.expiry == e) & (O.dayno == 0)]; wing = z[(z.module == 'h_') & (z.role == 'open_long')].te.values; bb = z[(z.module == 'num') & (z.role == 'cover_short')].te.values
    fi = run2(d, var='intra', per_side=True); mb = {int((33300 + 60 * f) // 1800): (f, s) for f, s in fi}; ab = {}
    for t in rp.te.values: ab.setdefault(int(t // 1800), []).append(t)
    fig, ax = plt.subplots(3, 1, figsize=(15, 11.5), sharex=True, gridspec_kw=dict(height_ratios=[3.2, 0.9, 1.5])); a = ax[0]; a.plot(x, sp, color='#333', lw=1)
    b_first = int(33300 // 1800); b_last = int(55800 // 1800)
    for b in range(b_first, b_last + 1):
        t0 = b * 1800; a.axvline(t0 / 3600, color='#bbb', lw=.6, ls=':')
        i0 = max(int(np.ceil((t0 - 2 * 1800 - 33300) / 60)), 0); i1 = max(int(np.ceil((t0 - 33300) / 60)), 0); w = sp[i0:i1]
        if len(w) >= 2 and t0 >= 37800 - 1800: a.hlines([w.max(), w.min()], t0 / 3600, (t0 + 1800) / 3600, color='#1f77b4', lw=1.4); a.fill_between([t0 / 3600, (t0 + 1800) / 3600], w.min(), w.max(), color='#1f77b4', alpha=.07)
    for b, (f, s) in mb.items(): a.plot((33300 + 60 * f) / 3600, sp[f], 'x', color='k', ms=9, mew=2, zorder=6)
    for r in rp.itertuples():
        j = int((r.te - 33300) // 60); f_ = ((r.te - 33300) % 60) / 60; live = sp[max(j - 1, 0)] + f_ * (sp[min(j, 374)] - sp[max(j - 1, 0)]); up = r.strike > np.array(ch.cyc(und, e)['strikes'], float)[np.argmin(np.abs(np.array(ch.cyc(und, e)['strikes'], float) - live))]
        a.plot(r.te / 3600, live, '^' if up else 'v', color='#d62728' if up else '#1f77b4', ms=9, zorder=5)
    a.axvspan(10.5, 15.25, color='#ffd54f', alpha=.06); a.set_ylabel('spot'); a.plot([], [], 'x', color='k', mew=2, label='machine: first break of the previous 2 completed 30-min bars (one per side per bar)'); a.plot([], [], '^', color='#d62728', label='real reactive pair, strike above ATM'); a.plot([], [], 'v', color='#1f77b4', label='real reactive pair, strike below ATM'); a.plot([], [], color='#1f77b4', lw=1.4, label='high/low of the previous 2 completed 30-min bars (minute closes)'); a.legend(fontsize=7, loc='lower left', ncol=2)
    a.set_title(f'{und} D-1 {e}: reactive pairs vs the 30-minute clock (grid at hh:00 / hh:30)')
    a = ax[1]; res = {}
    for b in range(int(37800 // 1800), int(55800 // 1800)):
        m = b in mb; ac = b in ab; col = '#2ca02c' if (m and ac) else ('#ff7f0e' if m else ('#d62728' if ac else '#dddddd')); a.add_patch(Rectangle((b * 1800 / 3600, 0), 0.5, 1, color=col, alpha=.85, ec='w')); a.text((b * 1800 + 900) / 3600, .5, f'{len(ab.get(b, []))}', ha='center', va='center', fontsize=9, color='k'); res[b] = (m, ac)
    a.set_ylim(0, 1); a.set_yticks([]); a.set_ylabel('30-min bars\n(number of real\npair-minutes)'); a.plot([], [], 's', color='#2ca02c', label='machine break and real entry'); a.plot([], [], 's', color='#ff7f0e', label='machine break, no real entry'); a.plot([], [], 's', color='#d62728', label='real entry, no machine break'); a.plot([], [], 's', color='#dddddd', label='neither'); a.legend(fontsize=7, loc='upper right', ncol=4)
    a = ax[2]; ev = [('real reactive pairs', rp.te.values / 3600, '#d62728'), ('machine breaks', (33300 + 60 * np.array([f for f, _ in fi])) / 3600, 'k'), ('scheduled pairs', sc.te.values / 3600, '#7f7f7f'), ('hedge-wing buys (h_)', wing / 3600, '#9467bd'), ('body buy-backs', bb / 3600, '#2ca02c')]
    for i, (nm, tt, col) in enumerate(ev): a.scatter(tt, [len(ev) - i] * len(tt), marker='|', s=120, color=col)
    a.set_yticks(range(1, len(ev) + 1)); a.set_yticklabels([n for n, _, _ in ev][::-1], fontsize=8); a.set_ylim(.3, len(ev) + .7); a.set_xlim(9.25, 15.5); a.set_xticks(np.arange(9.5, 15.6, .5)); a.set_xticklabels([f'{int(h)}:{int(round((h % 1) * 60)):02d}' for h in np.arange(9.5, 15.6, .5)], fontsize=8); a.set_xlabel('clock time (D-1)')
    plt.tight_layout(); plt.savefig(f'{FIG}/bl_clk_example_{und}.png', dpi=125); plt.close()
    rows = [dict(bar_start=hhmm(b * 1800)[:5], machine_break=int(m), machine_break_time=(hhmm(33300 + 60 * mb[b][0]) if b in mb else ''), real_pair_times=' '.join(hhmm(t) for t in ab.get(b, [])), real_pair_minutes=len(ab.get(b, []))) for b, (m, ac) in res.items()]
    pd.DataFrame(rows).to_csv(f'{OUT}/bl_clk_example_{und}.csv', index=False); Rr[und] = dict(expiry=e, bars=len(res), both=sum(1 for m, a_ in res.values() if m and a_), machine_only=sum(1 for m, a_ in res.values() if m and not a_), actual_only=sum(1 for m, a_ in res.values() if a_ and not m)); print(und, Rr[und])
for u in EX: plot(u)
rec('clk8', Rr)
