"""D-1 long side, L3-L5: (L3) h_ waves (orders on one right with decision stamps within 0.05 s) vs the contract-level gap S - L just before (all modules, flat at the D-1 open);
(L4) which long is sold on an h_ close_long when >= 2 long strikes are held on that right: outermost (farthest OTM), innermost, cheapest / dearest (previous minute close), oldest / newest bought, nearest to 2.5% of the ATM same-right price; chance = 1 / strikes held;
(L5) body-stream (num) open_long / close_long on D-1: time, strike offset, and the gap S - L before/after. Outputs bl_hg_waves.csv, bl_hg_release.csv, bl_hg_bodywing.csv, bl_summary_hg345.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_sd_build, bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); d1 = O[O.dayno == 0]; R = {}; WV = []; RL = []; BW = []
for i, r in enumerate(CY.itertuples()):
    z = d1[(d1.und == r.und) & (d1.expiry == r.expiry)].copy(); z['ts'] = z.t_dec.fillna(z.te); z = z.sort_values(['ts', 'row']); z['sg'] = np.where(z.side.str.lower() == 'buy', 1, -1)
    op = OP[(r.und, r.expiry)]; K = op['K']; c = OH[(r.und, r.expiry)].close.values; st = ref.STEP[r.und]
    pos = {}; first_buy = {}; last_buy = {}; rows = list(z.itertuples()); n = len(rows); k = 0
    def gap(cp): s = -sum(v for (c2, _), v in pos.items() if c2 == cp and v < 0); l = sum(v for (c2, _), v in pos.items() if c2 == cp and v > 0); return s, l
    while k < n:
        q = rows[k]
        if q.module == 'h_':
            grp = [q]; m = k + 1
            while m < n and rows[m].module == 'h_' and rows[m].cp == q.cp and rows[m].ts - q.ts <= 0.05: grp.append(rows[m]); m += 1
            s, l = gap(q.cp); WV.append(dict(cid=i, cp=q.cp, ts=q.ts, lots_signed=sum(g.sg * g.lots for g in grp), gap=s - l, n_orders=len(grp), kind='buy' if grp[0].sg > 0 else 'sell'))
            for g in grp:
                if g.role == 'close_long':
                    held = [(kk, v) for (c2, kk), v in pos.items() if c2 == g.cp and v > 0]
                    if len(held) >= 2:
                        j = min(max(int((g.te - 33300) // 60), 1), 374); hk = np.array([h_[0] for h_ in held], float); px = np.array([op[(g.cp, 'close')][np.argmin(np.abs(K - kk)), j - 1] for kk in hk])
                        otm = (hk - c[j - 1]) * (1 if g.cp == 'CE' else -1); atm = op[(g.cp, 'close')][np.argmin(np.abs(K - c[j - 1])), j - 1]
                        cand = dict(outermost=hk[np.argmax(otm)], innermost=hk[np.argmin(otm)], cheapest=hk[np.argmin(px)], dearest=hk[np.argmax(px)], oldest=min(hk, key=lambda kk: first_buy.get((g.cp, kk), 1e9)), newest=max(hk, key=lambda kk: last_buy.get((g.cp, kk), -1)), near_2p5_atm=hk[np.argmin(np.abs(np.log(np.maximum(px, 1e-3) / (0.025 * atm))))])
                        RL.append(dict(cid=i, cp=g.cp, te=g.te, sold=float(g.strike), n_held=len(held), chance=1 / len(held), **{f'hit_{a}': float(b == g.strike) for a, b in cand.items()}))
                key = (g.cp, int(g.strike)); pos[key] = pos.get(key, 0) + g.sg * g.lots
                if g.sg > 0: first_buy.setdefault((g.cp, float(g.strike)), g.ts); last_buy[(g.cp, float(g.strike))] = g.ts
            k = m; continue
        if q.module == 'num' and q.role in ('open_long', 'close_long'):
            s0, l0 = gap(q.cp); j = min(max(int((q.te - 33300) // 60), 1), 374)
            BW.append(dict(cid=i, cp=q.cp, te=q.te, hhmm=f'{int(q.te // 3600):02d}:{int(q.te % 3600 // 60):02d}', role=q.role, lots=q.lots, strike=q.strike, otm_steps=(q.strike - c[j - 1]) / st * (1 if q.cp == 'CE' else -1), S_before=s0, L_before=l0))
        key = (q.cp, int(q.strike)); pos[key] = pos.get(key, 0) + q.sg * q.lots
        if q.sg > 0: first_buy.setdefault((q.cp, float(q.strike)), q.ts); last_buy[(q.cp, float(q.strike))] = q.ts
        k += 1
W = pd.DataFrame(WV); L = pd.DataFrame(RL); B = pd.DataFrame(BW); W.to_csv(f'{OUT}/bl_hg_waves.csv', index=False); L.to_csv(f'{OUT}/bl_hg_release.csv', index=False); B.to_csv(f'{OUT}/bl_hg_bodywing.csv', index=False)
R['L3'] = {kd: dict(waves=int(len(g)), equals_gap=float((g.lots_signed == g.gap).mean()), sign_right=float((np.sign(g.lots_signed) == np.sign(g.gap)).mean())) for kd, g in W.groupby('kind')}
R['L3']['all'] = dict(waves=len(W), equals_gap=float((W.lots_signed == W.gap).mean()))
R['L4'] = dict(n=len(L), chance=float(L.chance.mean()), **{c[4:]: float(L[c].mean()) for c in L.columns if c.startswith('hit_')})
B['window'] = np.where(B.te < 33300 + 180, '09:15-09:17', np.where(B.te >= 54000, 'after 15:00', 'other'))
R['L5'] = B.groupby(['role', 'window']).agg(orders=('lots', 'size'), lots=('lots', 'sum'), otm_steps_median=('otm_steps', 'median'), L_ge_S_before=('S_before', lambda s: float((B.loc[s.index, 'L_before'] >= s).mean()))).round(3).reset_index().to_dict('records')
print(R['L3']); print(R['L4']); print(pd.DataFrame(R['L5']).to_string(index=False)); rec('hg345', R)
