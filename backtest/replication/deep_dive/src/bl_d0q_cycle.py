"""One cycle, D-1 vs D0 scheduled selling side by side (usage: python bl_d0q_cycle.py [cid]; default 4 = NIFTY expiry 2026-07-28, D-1 = 2026-07-27).
Question (stated before computing the match): is the D0 scheduled selling of this cycle the same as its D-1 scheduled selling?
Measures (descriptive, this cycle only): share of D-1 scheduled pairs that recur on D0 within +-3 s of the same clock time; share of D0 pairs that are also on D-1; strike = ATM of the previous minute's close on each day.
D-1 scheduled pairs: bl_react_pairs.csv (sched = True, day = D-1). D0 scheduled pairs: bl_d0q_pairs.csv (pairs within +-3 s of a wave of the cycle's group).
Outputs bl_d0q_cycle<cid>.csv, figures/bl_d0q_cycle<cid>.png, bl_summary_d0q2_<cid>.json"""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
import bl_ohlc
cid = int(sys.argv[1]) if len(sys.argv) > 1 else 4
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); r = CY.iloc[cid]; P1 = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); PK = pd.read_csv(f'{OUT}/bl_d0q_pairs.csv'); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); OH1 = bl_ohlc.load()
a = P1[(P1.und == r.und) & (P1.expiry == r.expiry) & (P1.day == 'D-1') & P1.sched].sort_values('te').reset_index(drop=True); b = PK[PK.cid == cid].sort_values('tod').reset_index(drop=True)
s1 = OH1[(r.und, r.expiry)]; s0 = SPT[(r.und, r.expiry)]; step = ref.STEP[r.und]
hm = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'
ta = a.te.values; tb = b.tod.values
a['recurs_on_D0'] = [bool(np.min(np.abs(tb - t)) <= 3) for t in ta]; b['also_on_D1'] = [bool(np.min(np.abs(ta - t)) <= 3) for t in tb]
def atm_check(df, t_col, spot, K):
    out = []
    for t, k in zip(df[t_col], df.strike):
        j = int((t - 33300) // 60); c0 = spot.close.values[j - 1] if j > 0 else spot.close.values[0]; out.append(float(K[np.argmin(np.abs(K - c0))]) == k)
    return np.array(out)
Ka = np.arange(s1.close.min() - 600, s1.close.max() + 600, step); Kb = np.arange(s0.close.min() - 600, s0.close.max() + 600, step)
Ka = np.round(Ka / step) * step; Kb = np.round(Kb / step) * step; Ka = np.unique(Ka); Kb = np.unique(Kb)
a['strike_is_prev_close_ATM'] = atm_check(a, 'te', s1, Ka); b['strike_is_prev_close_ATM'] = atm_check(b, 'tod', s0, Kb)
R = dict(cid=cid, und=r.und, expiry=r.expiry, d1=r.d1, version=r.version, D1_pairs=len(a), D0_pairs=len(b), D1_pairs_recurring_on_D0=int(a.recurs_on_D0.sum()), D0_pairs_also_on_D1=int(b.also_on_D1.sum()), D0_extra_pairs=int((~b.also_on_D1).sum()),
         D1_strike_atm_share=float(a.strike_is_prev_close_ATM.mean()), D0_strike_atm_share=float(b.strike_is_prev_close_ATM.mean()), D1_first_last=[hm(ta.min()), hm(ta.max())], D0_first_last=[hm(tb.min()), hm(tb.max())])
ex = b[~b.also_on_D1]; R['D0_extra_clock_times'] = [hm(t) for t in ex.tod]; R['D1_not_on_D0'] = [hm(t) for t in a[~a.recurs_on_D0].te]
R['D0_extra_block_minute'] = ex.assign(m=((ex.tod - 33300) // 60 % 15).astype(int)).m.value_counts().sort_index().to_dict(); R['D0_extra_block_minute'] = {int(k): int(v) for k, v in R['D0_extra_block_minute'].items()}
rows = [dict(day='D-1', time=hm(t), seconds=t, strike=k, also_on_other_day=bool(x), strike_is_prev_close_ATM=bool(y)) for t, k, x, y in zip(a.te, a.strike, a.recurs_on_D0, a.strike_is_prev_close_ATM)] + \
       [dict(day='D0', time=hm(t), seconds=t, strike=k, also_on_other_day=bool(x), strike_is_prev_close_ATM=bool(y)) for t, k, x, y in zip(b.tod, b.strike, b.also_on_D1, b.strike_is_prev_close_ATM)]
pd.DataFrame(rows).to_csv(f'{OUT}/bl_d0q_cycle{cid}.csv', index=False); rec(f'd0q2_{cid}', R); print(R)
# ---------------- figure
fig = plt.figure(figsize=(18, 11)); gs = fig.add_gridspec(3, 2, height_ratios=[1.25, 1.25, 1], hspace=.38, wspace=.12)
def day_panel(ax, df, tc, spot, flag, title, col_both='#2b6cb0', col_new='#ed8936'):
    t = (np.arange(375) * 60 + 33300) / 3600; ax.plot(t, spot.close.values, color='#a0aec0', lw=1.2, label='spot (1-min close)')
    for flg, col, lab in ((True, col_both, 'same clock time also on the other day (±3 s)'), (False, col_new, 'only on this day')):
        m = df[flag] == flg
        if m.any(): ax.scatter(df.loc[m, tc] / 3600, df.loc[m, 'strike'], s=34, color=col, edgecolor='white', lw=.5, zorder=3, label=f'{lab}: {int(m.sum())} pairs (CE + PE at that strike)')
    ax.set_xlim(9.2, 15.55); ax.set_title(title, fontsize=11); ax.set_ylabel('strike sold / spot'); ax.legend(fontsize=8, loc='best')
    for x in np.arange(9.25, 15.6, .25): ax.axvline(x, color='#edf2f7', lw=.6, zorder=0)
day_panel(fig.add_subplot(gs[0, :]), a.rename(columns={'te': 't'}), 't', s1, 'recurs_on_D0', f"D-1 ({r.d1}): scheduled selling — {len(a)} pairs, {hm(ta.min())} → {hm(ta.max())}   [{r.und} cycle expiring {r.expiry}]")
day_panel(fig.add_subplot(gs[1, :]), b.rename(columns={'tod': 't'}), 't', s0, 'also_on_D1', f"D0 ({r.expiry}, expiry day): scheduled selling — {len(b)} pairs, {hm(tb.min())} → {hm(tb.max())}")
ax = fig.add_subplot(gs[2, 0]); lo, hi = 33300 + 15 * 60, 33300 + 75 * 60
for k, (df, tc, y, nm) in enumerate(((a, 'te', 1, 'D-1'), (b, 'tod', 0, 'D0'))):
    z = df[(df[tc] >= lo) & (df[tc] <= hi)]
    for t in z[tc]: ax.plot([t, t], [y - .3, y + .3], color='#2b6cb0' if (df.loc[df[tc] == t, 'recurs_on_D0' if nm == 'D-1' else 'also_on_D1'].iloc[0]) else '#ed8936', lw=2)
ax.set_yticks([0, 1]); ax.set_yticklabels(['D0', 'D-1']); ax.set_xlim(lo - 30, hi); ax.set_xticks(np.arange(lo, hi + 1, 300)); ax.set_xticklabels([hm(t)[:5] for t in np.arange(lo, hi + 1, 300)]); ax.set_title('Zoom 09:15–10:30: each tick is one pair (blue = same second on both days)', fontsize=10)
ax = fig.add_subplot(gs[2, 1]); tbl = [['', 'D-1', 'D0'], ['scheduled pairs (1 CE + 1 PE each)', len(a), len(b)], ['first → last', f'{hm(ta.min())} → {hm(ta.max())}', f'{hm(tb.min())} → {hm(tb.max())}'], ['strike = ATM of previous minute close', f"{R['D1_strike_atm_share']:.0%}", f"{R['D0_strike_atm_share']:.0%}"],
                                                                      ['pairs also on the other day (±3 s)', f"{R['D1_pairs_recurring_on_D0']} of {len(a)}", f"{R['D0_pairs_also_on_D1']} of {len(b)}"], ['pairs only on this day', len(a) - R['D1_pairs_recurring_on_D0'], R['D0_extra_pairs']]]
ax.axis('off'); t_ = ax.table(cellText=tbl, loc='center', cellLoc='center'); t_.auto_set_font_size(False); t_.set_fontsize(10); t_.scale(1, 1.8); ax.set_title('Same cycle, D-1 vs D0', fontsize=10)
plt.savefig(os.path.join(os.path.dirname(OUT), 'reports', 'figures', f'bl_d0q_cycle{cid}.png'), dpi=120, bbox_inches='tight')
