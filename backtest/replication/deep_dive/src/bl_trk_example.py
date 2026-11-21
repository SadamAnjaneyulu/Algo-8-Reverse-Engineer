"""Tracker study deliverable 1: time-aligned D-1 example cycles (rule fixed in BODY_REACTIVE_TRACKER_PLAN.md: >= 8 reactive pairs, count closest to the median over all cycles, ties earliest expiry; one NIFTY, one SENSEX).
Outputs reports/figures/bl_trk_example_NIFTY.png, bl_trk_example_SENSEX.png, outputs/bl_trk_example_<UND>.csv"""
import sys, os, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import *
FIG = os.path.join(os.path.dirname(OUT), 'reports', 'figures'); R = {}; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); ch = Chain(); O = load_orders(); O1 = O[O.dayno == 0]; N_BAND, K_REF = 70, 12
cnt = Pr[Pr.reactive].groupby(['und', 'expiry']).size().rename('n').reset_index(); med = cnt.n.median(); R['median_reactive_pairs_per_cycle'] = float(med)
FI = pd.read_csv(f'{OUT}/bl_trk_sim2_fires.csv'); cid_of = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}
hhmmss = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'; hm = lambda m: (33300 + 60 * m) / 3600
def example(und):
    c_ = cnt[(cnt.und == und) & (cnt.n >= 8)].copy(); c_['d'] = (c_.n - med).abs(); c_ = c_.sort_values(['d', 'expiry']); e = c_.expiry.iloc[0]; n = int(c_.n.iloc[0])
    c = ch.cyc(und, e); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; K = np.array(c['strikes'], dtype=float); step = ref.STEP[und]; near = lambda s: K[np.argmin(np.abs(K - s))]
    g = Pr[(Pr.und == und) & (Pr.expiry == e)].sort_values('te'); rp = g[g.reactive]; sc = g[g.sched]; z = O1[(O1.und == und) & (O1.expiry == e)]; bb = z[(z.module == 'num') & (z.role == 'cover_short')].te.values; oth = z[z.module != 'num'].te.values; cid = cid_of[(und, e)]
    mf = FI[FI.cid == cid]; mfm = mf.minute.values; T = np.arange(375); x = hm(T)
    hi = np.array([sp[max(j - N_BAND, 0):j].max() if j > 0 else sp[0] for j in T]); lo = np.array([sp[max(j - N_BAND, 0):j].min() if j > 0 else sp[0] for j in T])
    rows = []; prev_t = None
    for r in rp.itertuples():
        j = int((r.te - 33300) // 60); f = ((r.te - 33300) % 60) / 60; live = sp[max(j - 1, 0)] + f * (sp[min(j, 374)] - sp[max(j - 1, 0)]); w = sp[max(j - N_BAND, 0):j + 0]; pos = (live - w.min()) / max(w.max() - w.min(), 1e-6) - 0.5; atm = near(live)
        rows.append(dict(time=hhmmss(r.te), seconds_from_open=int(r.te - 33300), strike=int(r.strike), live_ATM=int(atm), strike_minus_ATM_steps=int(round((r.strike - atm) / step)), live_spot=round(live, 1), position_in_70min_range=round(pos, 2), minutes_since_previous_reactive_pair=(np.nan if prev_t is None else round((r.te - prev_t) / 60, 1)), machine_fire_within_1min=int(any(abs(m - j) <= 1 for m in mfm)))); prev_t = r.te
    D = pd.DataFrame(rows); D.to_csv(f'{OUT}/bl_trk_example_{und}.csv', index=False)
    fig, ax = plt.subplots(4, 1, figsize=(15, 13), sharex=True, gridspec_kw=dict(height_ratios=[3.2, 1.6, 1.0, 1.2])); a = ax[0]
    a.plot(x, sp, color='#333', lw=1.1, label='spot (1-min closes)'); a.fill_between(x, lo, hi, color='#1f77b4', alpha=.10, label=f'trailing {N_BAND}-min high-low band (completed closes)'); a.plot(x, hi, color='#1f77b4', lw=.6); a.plot(x, lo, color='#1f77b4', lw=.6)
    for r in D.itertuples():
        t = r.seconds_from_open / 3600 + 9.25; up = r.strike_minus_ATM_steps > 0; a.axvline(t, color='#d62728' if up else '#1f77b4', lw=.8, ls='--', alpha=.6); a.plot(t, r.live_spot, '^' if up else 'v', color='#d62728' if up else '#1f77b4', ms=9, zorder=5)
    ymin, ymax = a.get_ylim(); rng_ = ymax - ymin
    for i, r in enumerate(D.itertuples()):
        t = r.seconds_from_open / 3600 + 9.25; a.text(t, ymax - (0.03 + 0.045 * (i % 3)) * rng_, f'{r.time}\n{r.strike}', fontsize=6.5, ha='center', va='top', rotation=0, color='#d62728' if r.strike_minus_ATM_steps > 0 else '#1f77b4')
    a.scatter(sc.te / 3600, [ymin + .015 * rng_] * len(sc), marker='|', color='#7f7f7f', s=60, label='scheduled timetable pairs'); a.scatter(bb / 3600, [ymin + .045 * rng_] * len(bb), marker='|', color='#2ca02c', s=40, label='body buy-backs'); a.axvspan(10.5, 15.25, color='#ffd54f', alpha=.08, label='reactive-pair window 10:30-15:15')
    a.set_ylabel('spot'); a.legend(fontsize=7, loc='lower left', ncol=3); a.set_title(f'{und} D-1 of expiry {e}: every reactive pair (triangle: red = strike above ATM, blue = below) with exact second; {n} pairs')
    a = ax[1]; pos_min = np.array([(sp[j] - sp[max(j - N_BAND, 0):j + 1].min()) / max(np.ptp(sp[max(j - N_BAND, 0):j + 1]), 1e-6) - 0.5 for j in T]); a.plot(x, pos_min, color='#555', lw=.9); a.axhline(.5, color='k', lw=.6, ls=':'); a.axhline(-.5, color='k', lw=.6, ls=':'); a.set_ylabel(f'position in {N_BAND}-min range\n(±0.5 = at the edge)')
    a.scatter(D.seconds_from_open / 3600 + 9.25, D.position_in_70min_range, color='#d62728', zorder=5, s=36, label='actual reactive pair (live position at its second)'); a.scatter(hm(mfm), [0] * len(mfm), marker='x', color='k', s=36, label=f'simulated tracker fire (range edge + refractory; out-of-fold N={int(mf.N.iloc[0]) if len(mf) else "-"}, K={int(mf.K.iloc[0]) if len(mf) else "-"})'); a.legend(fontsize=7, loc='upper left')
    a = ax[2]; ev = [('actual reactive pairs', rp.te.values / 3600, '#d62728'), ('simulated tracker', hm(mfm), 'k'), ('scheduled pairs', sc.te.values / 3600, '#7f7f7f'), ('body buy-backs', bb / 3600, '#2ca02c'), ('hedge/stop/lump orders', oth / 3600, '#9467bd')]
    for i, (nm, tt, col) in enumerate(ev): a.scatter(tt, [len(ev) - i] * len(tt), marker='|', s=130, color=col)
    a.set_yticks(range(1, len(ev) + 1)); a.set_yticklabels([e_[0] for e_ in ev][::-1], fontsize=7); a.set_ylim(.3, len(ev) + .7); a.set_ylabel('event timeline')
    a = ax[3]; tt = np.arange(33300, 54900, 30); lastp = np.array([(t - rp.te.values[rp.te.values <= t].max()) / 60 if (rp.te.values <= t).any() else np.nan for t in tt]); a.plot(tt / 3600, lastp, color='#d62728', lw=1); a.axhspan(4, 14, color='k', alpha=.08, label='refractory range K = 4-14 min (cross-validated)'); a.set_ylabel('min since previous\nreactive pair'); a.set_ylim(0, 70); a.legend(fontsize=7, loc='upper right')
    a.set_xlim(9.25, 15.5); a.set_xticks(np.arange(9.25, 15.6, .5)); a.set_xticklabels([f'{int(h)}:{int(round((h % 1) * 60)):02d}' for h in np.arange(9.25, 15.6, .5)]); a.set_xlabel('time of day (D-1)'); plt.tight_layout(); plt.savefig(f'{FIG}/bl_trk_example_{und}.png', dpi=125); plt.close()
    R[und] = dict(expiry=e, pairs=n, machine_fires=int(len(mf)), matched=int(D.machine_fire_within_1min.sum())); print(und, e, n, 'machine fires', len(mf), 'pairs with a machine fire within 1 min', int(D.machine_fire_within_1min.sum())); print(D.to_string(index=False))
for u in ('NIFTY', 'SENSEX'): example(u)
rec('trk6', R)
