"""Reactive-pair mechanism study, step 3 (plan test C, strike rule): hit rates of pre-registered strike rules on reactive pairs (and timetable pairs for reference); by half and underlying. Outputs bl_mech_strike_rules.csv, bl_summary_mech2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
R = {}; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); Pr = Pr[Pr.j <= 373]; ch = Chain(); Pn = pd.read_csv(f'{OUT}/bl_react_panel.csv.gz'); yrs = sorted(Pr.expiry.unique()); med = yrs[len(yrs) // 2]; rows = []
last_rp = {}
for (u, e), g in Pr.sort_values('te').groupby(['und', 'expiry']): last_rp[(u, e)] = g
for r in Pr.itertuples():
    c = ch.cyc(r.und, r.expiry); K = np.array(c['strikes'], dtype=float); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().values; step = ref.STEP[r.und]; j = int(r.j)
    near = lambda s: K[np.argmin(np.abs(K - s))]; fl = lambda s: K[K <= s].max() if (K <= s).any() else K[0]; ce = lambda s: K[K >= s].min() if (K >= s).any() else K[-1]
    px = {cp: pd.DataFrame(np.array(c[(0, cp, 'close')], dtype=float)).ffill(axis=1).values for cp in ('CE', 'PE')}
    sgn = lambda w: np.sign(sp[j - 1] - sp[max(j - 1 - w, 0)])
    cand = {'nearest(close j-1)': near(sp[j - 1]), 'nearest(close j)': near(sp[j])}
    for w in (3, 5, 15): s_ = sgn(w); cand[f'ATM + 1 step toward {w}-min move'] = near(sp[j - 1]) + s_ * step; cand[f'floor/ceil of spot toward {w}-min move'] = (fl(sp[j - 1]) if s_ < 0 else ce(sp[j - 1])) if s_ != 0 else near(sp[j - 1])
    for L in (3, 5, 10, 15): cand[f'nearest(close j-1-{L})'] = near(sp[max(j - 1 - L, 0)])
    for lam in (1, 2, 3): cand[f'nearest(spot + {lam}x 5-min move)'] = near(sp[j - 1] + lam * (sp[j - 1] - sp[max(j - 6, 0)]))
    d = np.abs(px['CE'][:, j - 1] - px['PE'][:, j - 1]); cand['synthetic ATM min|CE-PE| (j-1)'] = K[int(np.nanargmin(d))]
    prev = last_rp[(r.und, r.expiry)]; prev = prev[(prev.te < r.te - 3) & prev.reactive]
    cand['strike of previous reactive pair'] = prev.strike.iloc[-1] if len(prev) else np.nan; cand['previous reactive strike +-1 step'] = r.strike if (len(prev) and abs(prev.strike.iloc[-1] - r.strike) <= step) else np.nan
    for k, v in cand.items(): rows.append((bool(r.reactive), r.und, bool(r.expiry < med), k, float(v == r.strike) if v == v else np.nan))
D = pd.DataFrame(rows, columns=['reactive', 'und', 'first_half', 'rule', 'hit']); T = D.groupby(['reactive', 'rule']).hit.agg(['mean', 'count']).reset_index().pivot(index='rule', columns='reactive', values='mean').rename(columns={True: 'reactive_hit', False: 'timetable_hit'}); T['n_reactive'] = D[D.reactive].groupby('rule').hit.count()
H = D[D.reactive].groupby(['rule', 'first_half']).hit.mean().unstack().rename(columns={True: 'half1', False: 'half2'}); U = D[D.reactive].groupby(['rule', 'und']).hit.mean().unstack(); T = T.join(H).join(U).sort_values('reactive_hit', ascending=False); T.round(3).to_csv(f'{OUT}/bl_mech_strike_rules.csv'); print(T.round(3).head(14).to_string()); R['best'] = {k: float(v) for k, v in T.reactive_hit.head(6).items()}; R['table'] = T.round(4).reset_index().to_dict('list')
rec('mech2', R)
