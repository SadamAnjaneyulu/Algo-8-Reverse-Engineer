"""Indicator search step 1 (plan BODY_REACTIVE_INDICATOR_PLAN.md): compute the pre-registered indicator values for the 363 events and 10,890 control seconds. Output outputs/bl_ind_table.pkl.gz, bl_ind_meta.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
T = pd.read_pickle(f'{OUT}/bl_act_table.pkl.gz')[['cid', 'und', 'expiry', 'y', 't', 'j', 'strike', 'atm', 'step', 'live', 'v2', 'sec_since_1030']].reset_index(drop=True); ch = Chain()
NS = [3, 5, 8, 10, 15, 20, 30, 45, 60, 90, 120]; RN = [10, 15, 20, 30, 45, 60]; CROSS = [(3, 15), (5, 20), (5, 30), (10, 30), (10, 60), (15, 60)]; MACD = [(5, 15), (8, 21), (12, 26)]; DN = [15, 30, 60]
names = []; cols = {}
def put(nm, arr): cols[nm] = arr; names.append(nm)
for (u, e), idx in T.groupby(['und', 'expiry']).groups.items():
    c = ch.cyc(u, e); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; step = ref.STEP[u]; sub = T.loc[idx]; I = (sub.j.values - 1).astype(int); live = sub.live.values; n = len(sub); out = {}
    ema = {s: pd.Series(sp).ewm(alpha=2 / (s + 1), adjust=False).mean().values for s in NS + [12, 21, 26]}
    win = lambda N, i: sp[max(i - N + 1, 0): i + 1]
    for N in NS:
        out[f'SMA gap|{N}'] = np.array([(l - win(N, i).mean()) / step for l, i in zip(live, I)])
        out[f'EMA gap|{N}'] = np.array([(l - ema[N][i]) / step for l, i in zip(live, I)])
        w = np.arange(1, N + 1, dtype=float); out[f'WMA gap|{N}'] = np.array([(l - (win(N, i) * w[-len(win(N, i)):]).sum() / w[-len(win(N, i)):].sum()) / step for l, i in zip(live, I)])
        out[f'momentum|{N}'] = np.array([(l - sp[max(i - N, 0)]) / step for l, i in zip(live, I)])
        sd = [max(win(N, i).std(), 1e-6 * sp[i]) for i in I]; out[f'Bollinger z|{N}'] = np.array([(l - win(N, i).mean()) / s_ for l, i, s_ in zip(live, I, sd)])
        atr = [max(np.abs(np.diff(sp[max(i - N, 0): i + 1])).mean() if i > 0 else 1e-6, 1e-6) for i in I]; out[f'gap/ATR|{N}'] = np.array([(l - win(N, i).mean()) / a for l, i, a in zip(live, I, atr)])
    for N in RN:
        sl = []; ln = []
        for l, i in zip(live, I):
            y = win(N, i); x = np.arange(len(y)); b, a = np.polyfit(x, y, 1) if len(y) > 2 else (0.0, y.mean()); sl.append(b * len(y) / step); ln.append((l - (a + b * len(y))) / step)
        out[f'regression drift|{N}'] = np.array(sl); out[f'regression line gap|{N}'] = np.array(ln)
    for a_, b_ in CROSS: out[f'SMA cross|{a_}-{b_}'] = np.array([(win(a_, i).mean() - win(b_, i).mean()) / step for i in I])
    for f_, s_ in MACD: out[f'MACD|{f_}-{s_}'] = np.array([(ema[f_][i] - ema[s_][i]) / step for i in I]) if f_ in ema and s_ in ema else np.array([(pd.Series(sp).ewm(alpha=2 / (f_ + 1), adjust=False).mean().values[i] - pd.Series(sp).ewm(alpha=2 / (s_ + 1), adjust=False).mean().values[i]) / step for i in I])
    for N in DN: out[f'Donchian mid gap|{N}'] = np.array([(l - (win(N, i).max() + win(N, i).min()) / 2) / step for l, i in zip(live, I)])
    # post-hoc extensions (added after Bollinger z led the first search): normalised-distance relatives, RSI, efficiency ratio, normalised momentum
    for N in NS:
        mad = [max(np.abs(win(N, i) - win(N, i).mean()).mean(), 1e-6) for i in I]; out[f'CCI-like gap/MAD|{N}'] = np.array([(l - win(N, i).mean()) / m_ for l, i, m_ in zip(live, I, mad)])
        sd = [max(win(N, i).std(), 1e-6 * sp[i]) for i in I]; out[f'momentum/sigma|{N}'] = np.array([(l - sp[max(i - N, 0)]) / s_ for l, i, s_ in zip(live, I, sd)])
        out[f'Donchian position|{N}'] = np.array([((l - win(N, i).min()) / max(win(N, i).max() - win(N, i).min(), 1e-6) - 0.5) for l, i in zip(live, I)])
        rs = []; er = []
        for i in I:
            dx = np.diff(sp[max(i - N, 0): i + 1]); g_ = dx[dx > 0].sum(); l_ = -dx[dx < 0].sum(); rs.append((100 - 100 / (1 + g_ / l_) - 50) if l_ > 0 else (50.0 if g_ > 0 else 0.0)); er.append((sp[i] - sp[max(i - N, 0)]) / max(np.abs(dx).sum(), 1e-6))
        out[f'RSI minus 50|{N}'] = np.array(rs); out[f'efficiency ratio|{N}'] = np.array(er)
        ewsd = pd.Series(sp).ewm(alpha=2 / (N + 1), adjust=False).std().bfill().values; out[f'EMA z|{N}'] = np.array([(l - ema[N][i]) / max(ewsd[i], 1e-6 * sp[i]) for l, i in zip(live, I)])
    for k, v in out.items():
        if k not in cols: cols[k] = np.full(len(T), np.nan); names.append(k)
        cols[k][idx] = v
D = pd.concat([T, pd.DataFrame(cols)], axis=1); D.to_pickle(f'{OUT}/bl_ind_table.pkl.gz'); pd.DataFrame({'indicator': names, 'family': [x.split('|')[0] for x in names], 'param': [x.split('|')[1] for x in names]}).to_csv(f'{OUT}/bl_ind_meta.csv', index=False); print(D.shape, len(names), 'indicators')
