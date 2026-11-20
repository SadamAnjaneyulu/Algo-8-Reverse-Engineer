"""Strike rule for the scheduled paired sales (plan C). Unit = first scheduled paired sale per (cycle, day, slot, right) in the slot minute. Reference data = chain at minute j-1 (previous completed minute).
Rules: ATM (nearest to previous-minute spot) | FWD (nearest to forward spot*exp(rT)) | DELTA50 (call delta nearest 0.50) | DELTA_NEUTRAL (|call delta + put delta| smallest) | MINCP (|C-P| smallest) | HYST_h (keep the previous slot's strike unless the spot is more than h steps from it, then ATM), h in 0.5..2.
Null for ATM: nearest strike to the spot of a random other minute of the same day. Output outputs/bl_slot_strike_rules.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from bl_greeks import surface, R_
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); ALL = pd.read_pickle(f'{OUT}/bl_move_solo_sales.pkl.gz'); rng = np.random.default_rng(0); rows = []
for d, flag in ((0, 'has_d1'), (1, 'has_d0')):
    for u, e, h in zip(cyc.und, cyc.expiry, cyc[flag]):
        if not h: continue
        c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); spot = np.array(c[(d, 'spot')], dtype=float); step = ref.STEP[u]; T = np.maximum(((1 if d == 0 else 0) + (375 - np.arange(375)) / 375) / 252.0, 1e-4)
        Pc = np.array(c[(d, 'CE', 'close')], dtype=float); Pp = np.array(c[(d, 'PE', 'close')], dtype=float); ivc, dec, _, _ = surface(Pc, spot, K, T, 'CE'); ivp, dep, _, _ = surface(Pp, spot, K, T, 'PE')
        prev_k = {}
        for cp in ('CE', 'PE'):
            S = ALL[(ALL.und == u) & (ALL.expiry == e) & (ALL.cp == cp) & (ALL.dayno == d) & ALL.paired & (ALL.cls == 'slot_minute')].sort_values('tod'); S['slot'] = np.round((S.tod - (9 * 3600 + 16 * 60)) / 900).astype(int)
            for slot, g in S.groupby('slot'):
                r = g.iloc[0]; j = int((r.tod - ref.OPEN_SEC) // 60)
                if j < 1: continue
                s1 = spot[j - 1]
                if not np.isfinite(s1): continue
                atm = K[np.argmin(np.abs(K - s1))]; fwd = K[np.argmin(np.abs(K - s1 * np.exp(R_ * T[j - 1])))]; okd = np.isfinite(dec[:, j - 1]) & np.isfinite(dep[:, j - 1]) & (Pc[:, j - 1] > 0.5) & (Pp[:, j - 1] > 0.5)
                d50 = K[okd][np.argmin(np.abs(dec[okd, j - 1] - 0.5))] if okd.any() else np.nan; dn = K[okd][np.argmin(np.abs(dec[okd, j - 1] + dep[okd, j - 1]))] if okd.any() else np.nan
                okc = np.isfinite(Pc[:, j - 1]) & np.isfinite(Pp[:, j - 1]) & (Pc[:, j - 1] > 0.5) & (Pp[:, j - 1] > 0.5); mcp = K[okc][np.argmin(np.abs(Pc[okc, j - 1] - Pp[okc, j - 1]))] if okc.any() else np.nan
                sr = spot[int(rng.integers(1, 375))]; null = K[np.argmin(np.abs(K - sr))] if np.isfinite(sr) else np.nan
                row = dict(day=['D-1', 'D0'][d], und=u, cp=cp, slot=slot, K=r.strike, step=step, ATM=atm, FWD=fwd, DELTA50=d50, DELTA_NEUTRAL=dn, MINCP=mcp, NULL=null)
                pk = prev_k.get(cp)
                for hh in (0.5, 0.75, 1.0, 1.5, 2.0): row[f'HYST_{hh}'] = (pk if (pk is not None and abs(s1 - pk) <= hh * step) else atm)
                prev_k[cp] = r.strike; rows.append(row)
Z = pd.DataFrame(rows); res = []
for day, q in Z.groupby('day'):
    for rule in ('ATM', 'FWD', 'DELTA50', 'DELTA_NEUTRAL', 'MINCP', 'HYST_0.5', 'HYST_0.75', 'HYST_1.0', 'HYST_1.5', 'HYST_2.0', 'NULL'):
        v = q[rule]; ok = v.notna(); res.append((day, rule, ok.sum(), (q.K == v)[ok].mean(), ((q.K - v).abs() <= q.step * 1.0001)[ok].mean()))
R = pd.DataFrame(res, columns=['day', 'rule', 'n', 'exact', 'within_1_step']).round(3); R.to_csv(f'{OUT}/bl_slot_strike_rules.csv', index=False); print(R.pivot(index='rule', columns='day', values='exact').round(3).to_string()); print(R.pivot(index='rule', columns='day', values='within_1_step').round(3).to_string())
q = Z[Z.day == 'D-1']; print('\nD-1: exact ATM by right', q.assign(h=q.K == q.ATM).groupby('cp').h.mean().round(3).to_dict())
Z.to_csv(f'{OUT}/bl_slot_strike_units.csv', index=False)
