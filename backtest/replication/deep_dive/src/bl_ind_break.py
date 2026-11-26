"""Indicator search step 3 (post-hoc after Donchian position led): breakout reading. (1) robustness of the channel-position activation AUC (halves, underlyings, versions; completed-bar version without the live proxy); (2) shares of events vs controls beyond / near the trailing N-minute high-low band; (3) minute-level hazard by breakout state and by minutes since the breakout began; (4) breakout episodes: pairs per episode, delay to the first pair, share of pairs outside any episode.
Outputs bl_ind_robust.csv, bl_ind_bands.csv, bl_ind_episode.csv, bl_summary_ind2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(611); R = {}; D = pd.read_pickle(f'{OUT}/bl_ind_table.pkl.gz'); y = D.y.values; cid = D.cid.values; ucy = np.unique(cid); ev = y == 1; first = (D.expiry < '2026-08-25').values
def auc(x, y_): m = ~np.isnan(x); x, y_ = x[m], y_[m]; n1 = y_.sum(); n0 = len(y_) - n1; r = stats.rankdata(x); return (r[y_ == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
pos = D['Donchian position|60'].values; ap = np.abs(pos); rows = []
for nm, m in (('all', np.ones(len(D), bool)), ('first half', first), ('second half', ~first), ('NIFTY', (D.und == 'NIFTY').values), ('SENSEX', (D.und == 'SENSEX').values), ('V1', (D.v2 == 0).values), ('V2', (D.v2 == 1).values)): rows.append((nm, int(ev[m].sum()), auc(ap[m], y[m]), float(((D.atm.values + np.sign(pos) * D.step.values) == D.strike.values)[m & ev].mean())))
RB = pd.DataFrame(rows, columns=['subset', 'events', 'activation_AUC_|position-0.5|_N60', 'direction_hit']); RB.round(4).to_csv(f'{OUT}/bl_ind_robust.csv', index=False); print(RB.round(3).to_string(index=False)); R['robust'] = RB.round(4).to_dict('list')
# bands: share of events vs controls beyond / near the 60-minute channel (live proxy)
bands = []
for lab, cond in (('beyond the 60-min high or low (|pos| > 0.5)', ap > 0.5), ('within 5% of the band (|pos| >= 0.45)', ap >= 0.45), ('within 10% (|pos| >= 0.40)', ap >= 0.40), ('inner half of the range (|pos| < 0.25)', ap < 0.25)): bands.append((lab, float(cond[ev].mean()), float(cond[~ev].mean()), float(cond[ev].mean() / cond[~ev].mean()), 0.0277 * cond[ev].mean() / cond[~ev].mean() * 1000))
BD = pd.DataFrame(bands, columns=['state (live spot vs trailing 60-min closes)', 'share_of_events', 'share_of_control_seconds', 'ratio', 'rate_per1000_min']); BD.round(4).to_csv(f'{OUT}/bl_ind_bands.csv', index=False); print(BD.round(3).to_string(index=False)); R['bands'] = BD.round(4).to_dict('list')
# N scan for the beyond-band flag
scan = []
for N in (5, 10, 15, 20, 30, 45, 60, 90, 120):
    p = np.abs(D[f'Donchian position|{N}'].values) > 0.5; scan.append((N, float(p[ev].mean()), float(p[~ev].mean()), float(p[ev].mean() / max(p[~ev].mean(), 1e-9)), auc(np.abs(D[f'Donchian position|{N}'].values), y)))
SN = pd.DataFrame(scan, columns=['N_min', 'share_events_beyond_band', 'share_controls_beyond_band', 'ratio', 'AUC_abs_position']); print(SN.round(3).to_string(index=False)); R['scan_beyond'] = SN.round(4).to_dict('list')
# ---- minute-level, completed bars only: breakout state and episodes
P = pd.read_csv(f'{OUT}/bl_mech_panel.csv.gz'); P = P[(P.j >= 75) & (P.j < 360)].reset_index(drop=True); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); ch = Chain(); NB = (20, 30, 45, 60, 90); cols = {f'brk{N}': np.zeros(len(P)) for N in NB}; cols.update({f'pos{N}': np.full(len(P), np.nan) for N in NB}); cols['since_brk60'] = np.full(len(P), np.nan)
epi = []
for (u, e), idx in P.groupby(['und', 'expiry']).groups.items():
    c = ch.cyc(u, e); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; js = P.loc[idx, 'j'].values
    for N in NB:
        b = []; ps = []
        for j in js:
            w = sp[max(j - 1 - N, 0): j - 1]; i = j - 1; b.append(float(sp[i] > w.max() or sp[i] < w.min())); ps.append((sp[i] - w.min()) / max(w.max() - w.min(), 1e-6) - 0.5)
        cols[f'brk{N}'][idx] = b; cols[f'pos{N}'][idx] = ps
    # minutes since the current completed-bar breakout state began (N = 60), 0 if not in breakout
    b60 = cols['brk60'][idx]; since = np.zeros(len(idx)); run = 0
    for k in range(len(idx)): run = run + 1 if b60[k] else 0; since[k] = run
    cols['since_brk60'][idx] = since
for k, v in cols.items(): P[k] = v
rows = []
for N in NB: m = P[f'brk{N}'] == 1; rows.append((N, float(m.mean()), float(P.yR[m].mean() * 1000), float(P.yR[~m].mean() * 1000), float(P.yR[m].mean() / P.yR[~m].mean()), float(P.yR[P.yR == 1].index.isin(P.index[m]).mean())))
BS = pd.DataFrame(rows, columns=['N_min', 'share_of_minutes_in_breakout_state', 'hazard_in_state_per1000', 'hazard_outside_per1000', 'ratio', 'share_of_events_in_state']); print('\ncompleted-bar breakout state (close beyond the previous N closes), D-1 10:30-15:15'); print(BS.round(3).to_string(index=False)); R['state'] = BS.round(4).to_dict('list')
P['sb'] = pd.cut(P.since_brk60, [-1, 0, 1, 2, 3, 5, 10, 20, 100]); H = P.groupby('sb', observed=True).yR.agg(['size', 'sum']); H['per1000'] = (H['sum'] / H['size'] * 1000).round(1); print('\nhazard by minutes since the 60-min breakout state began (0 = not in state)'); print(H.to_string()); R['since'] = H.reset_index().assign(sb=lambda d: d.sb.astype(str)).to_dict('list')
# episodes (completed-bar, N=60): runs of consecutive breakout minutes within a cycle
ep = []
for (u, e), g in P.groupby(['und', 'expiry']):
    g = g.sort_values('j'); b = g.brk60.values; jj = g.j.values; yy = g.yR.values; i = 0
    while i < len(b):
        if b[i]:
            k = i
            while k + 1 < len(b) and b[k + 1] and jj[k + 1] == jj[k] + 1: k += 1
            ep.append((u, e, jj[i], k - i + 1, int(yy[i:k + 1].sum()), (np.argmax(yy[i:k + 1]) if yy[i:k + 1].any() else np.nan))); i = k + 1
        else: i += 1
EP = pd.DataFrame(ep, columns=['und', 'expiry', 'j_start', 'length_min', 'pair_minutes', 'delay_to_first_pair_min']); EP.to_csv(f'{OUT}/bl_ind_episode.csv', index=False); R['episodes'] = len(EP); R['episodes_with_pair'] = float((EP.pair_minutes > 0).mean()); R['pair_minutes_per_episode_mean'] = float(EP.pair_minutes.mean()); R['first_pair_delay_q'] = EP.delay_to_first_pair_min.dropna().quantile([.25, .5, .75]).tolist(); R['episode_len_q'] = EP.length_min.quantile([.25, .5, .75]).tolist(); R['pair_minutes_in_episodes'] = float(EP.pair_minutes.sum() / max(P.yR.sum(), 1)); R['pair_minutes_total'] = int(P.yR.sum())
print(f"\nbreakout episodes (N=60, completed bars): {len(EP)}; with >=1 pair minute {R['episodes_with_pair']:.2f}; median length {R['episode_len_q'][1]} min; median delay to first pair {R['first_pair_delay_q'][1]} min; share of all pair-minutes inside episodes {R['pair_minutes_in_episodes']:.2f}")
rec('ind2', R)
