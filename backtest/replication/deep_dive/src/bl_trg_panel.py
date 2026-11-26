"""Trigger study step 2 (plan BODY_REACTIVE_TRIGGER_PLAN.md, Panel B): D-1 cycle-minute panel 10:30-15:15, completed-bar (causal) features at the minute start, label = >=1 reactive pair in the minute.
Output outputs/bl_trg_panel.pkl.gz"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
O = load_orders(); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv').sort_values(['und', 'expiry', 'te']); ch = Chain(); O1 = O[(O.dayno == 0)].copy(); O1['sl'] = np.where(O1.side == 'Buy', O1.lots, -O1.lots)
rows = []; cid = 0; NB = [45, 60, 90]
for (u, e), g in Pr.groupby(['und', 'expiry']):
    c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; step = ref.STEP[u]; near = lambda s: K[np.argmin(np.abs(K - s))]; cid += 1
    v2 = int(((u == 'NIFTY') and e >= '2026-09-22') or ((u == 'SENSEX') and e >= '2026-09-17'))
    react = g[g.reactive].sort_values('te'); react_t = react.te.values; sch_t = np.sort(g[g.sched].te.values)
    z = O1[(O1.und == u) & (O1.expiry == e)]; body = z[z.module == 'num'].sort_values(['te', 'row']); sell_t = np.sort(body[body.role == 'open_short'].te.values); bb_t = np.sort(body[body.role == 'cover_short'].te.values); oth_t = np.sort(z[z.module != 'num'].te.values); be = list(body.itertuples()); ptr = 0; net = {}
    bflag = {N: np.zeros(375, dtype=int) for N in NB}                                              # +1 close beyond previous N closes (up), -1 down, per completed bar
    for N in NB:
        for i in range(10, 375): pr = sp[max(i - N, 0):i]; bflag[N][i] = 1 if sp[i] > pr.max() else (-1 if sp[i] < pr.min() else 0)
    rt_j = ((react_t - 33300) // 60).astype(int); rdir = np.sign(react.strike.values - np.array([near(sp[max(jj - 1, 0)]) for jj in rt_j])) if len(react) else np.array([])
    for j in range(75, 361):
        T0 = 33300 + 60 * j
        while ptr < len(be) and be[ptr].te < T0 - 3: b = be[ptr]; net[(b.cp, int(b.strike))] = net.get((b.cp, int(b.strike)), 0) + b.sl; ptr += 1
        cl = sp[j - 1]; step_ = step; atm = near(cl); sh = {k: -v for k, v in net.items() if v < 0}; tot = sum(sh.values()); centre = sum(k[1] * v for k, v in sh.items()) / tot if tot > 0 else np.nan
        r = dict(cid=cid, und=u, expiry=e, j=j, v2=v2, min_since_1030=j - 75, y=int(((rt_j == j)).any()), n_pairs=int((rt_j == j).sum()), pair_dir=float(rdir[rt_j == j][0]) if (rt_j == j).any() else np.nan)
        for N in NB:
            pr = sp[max(j - 1 - N, 0):j - 1]; hi_, lo_ = pr.max(), pr.min(); up = cl > hi_; dn = cl < lo_; r[f'bk{N}'] = 1 if up else (-1 if dn else 0); r[f'depth{N}'] = max(cl - hi_, lo_ - cl) / step_
            k_ = 0; i = j - 1
            while i > 10 and bflag[N][i] == r[f'bk{N}'] and r[f'bk{N}'] != 0: k_ += 1; i -= 1
            r[f'run{N}'] = k_; r[f'posprev{N}'] = (cl - lo_) / max(hi_ - lo_, 1e-6) - 0.5; r[f'width{N}'] = (hi_ - lo_) / step_
            pc = sp[max(j - N, 0):j]; r[f'bkLA{N}'] = 1 if sp[j] > pc.max() else (-1 if sp[j] < pc.min() else 0)         # LOOK-AHEAD: uses the current minute's close
        side = r['bk60'] if r['bk60'] != 0 else (1 if r['posprev60'] >= 0 else -1); tgt = near(cl) + side * step_; r['side'] = side; r['target'] = tgt
        for nm, arr in (('age_pair', np.sort(np.r_[sch_t, react_t])), ('age_react', react_t), ('age_sell', sell_t), ('age_bb', bb_t), ('age_oth', oth_t)): r[nm] = (T0 - arr[arr < T0 - 3].max()) if (arr < T0 - 3).any() else np.nan
        r['n_react_sofar'] = int((react_t < T0 - 3).sum()); r['n_sell_sofar'] = int((sell_t < T0 - 3).sum()); r['n_bb_sofar'] = int((bb_t < T0 - 3).sum())
        r['last_react_same_side'] = float(np.sign(react.strike.values[react_t < T0 - 3][-1] - near(sp[max(int((react_t[react_t < T0 - 3][-1] - 33300) // 60) - 1, 0)])) == side) if (react_t < T0 - 3).any() else np.nan
        r['short_ce'] = sum(v for k, v in sh.items() if k[0] == 'CE'); r['short_pe'] = sum(v for k, v in sh.items() if k[0] == 'PE'); r['short_tot'] = tot
        r['tgt_short_ce'] = sh.get(('CE', int(tgt)), 0); r['tgt_short_pe'] = sh.get(('PE', int(tgt)), 0); r['tgt_pair_open'] = int(r['tgt_short_ce'] > 0 and r['tgt_short_pe'] > 0); r['centre_d'] = (cl - centre) / step_ if centre == centre else np.nan
        pce = ch.px(u, e, 0, 'CE', tgt, j - 1); ppe = ch.px(u, e, 0, 'PE', tgt, j - 1); ace = ch.px(u, e, 0, 'CE', atm, j - 1); ape = ch.px(u, e, 0, 'PE', atm, j - 1)
        r['prem_tgt'] = pce + ppe; r['prem_atm'] = ace + ape; r['prem_ratio'] = (pce + ppe) / (ace + ape) if (ace + ape) > 0 else np.nan
        vt = ch.px(u, e, 0, 'CE', tgt, j - 1, 'volume') + ch.px(u, e, 0, 'PE', tgt, j - 1, 'volume'); vh = np.nanmean([ch.px(u, e, 0, 'CE', tgt, jj, 'volume') + ch.px(u, e, 0, 'PE', tgt, jj, 'volume') for jj in range(max(j - 31, 0), j - 1)]); r['vol_tgt'] = vt; r['vol_rel'] = vt / vh if vh and vh > 0 else np.nan
        r['absm1'] = abs(cl - sp[j - 2]) / step_; r['absm5'] = abs(cl - sp[j - 6]) / step_; r['vol30'] = np.std(np.diff(sp[j - 31:j])) / step_
        rows.append(r)
P = pd.DataFrame(rows); P.to_pickle(f'{OUT}/bl_trg_panel.pkl.gz'); print(P.shape, 'pair minutes', int(P.y.sum()), 'cycles', cid, 'pairs', int(P.n_pairs.sum()), 'minutes in breakout60', int((P.bk60 != 0).sum()), 'pair minutes in breakout', int(((P.bk60 != 0) & (P.y == 1)).sum()), 'pair minutes in LA breakout', int(((P.bkLA60 != 0) & (P.y == 1)).sum()))
print(P[['prem_tgt', 'vol_rel', 'centre_d', 'tgt_pair_open', 'short_tot']].describe().round(2).T)
