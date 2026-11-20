"""Activation study step 1 (plan BODY_REACTIVE_ACTIVATION_PLAN.md): events (D-1 reactive pairs) vs controls (random seconds inside 10:30-15:15), live-spot features, direction-candidate hit rates.
Outputs bl_act_table.pkl.gz (events + controls with features), bl_act_dirs.csv, bl_summary_act1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
rng = np.random.default_rng(501); R = {}; O = load_orders(); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv').sort_values(['und', 'expiry', 'te']); ch = Chain(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); NC = 30
O1 = O[(O.dayno == 0)].copy(); O1['sl'] = np.where(O1.side == 'Buy', O1.lots, -O1.lots); rows = []; dir_rows = []
cid = 0
for (u, e), g in Pr.groupby(['und', 'expiry']):
    c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; step = ref.STEP[u]; near = lambda s: K[np.argmin(np.abs(K - s))]; cid += 1
    ev = g[g.reactive & (g.j >= 20) & (g.j <= 373)]; sched_t = g[g.sched].te.values; react_t = np.sort(g[g.reactive].te.values); react_strike = g[g.reactive].set_index('te').strike
    z = O1[(O1.und == u) & (O1.expiry == e)]; body = z[z.module == 'num'].sort_values(['te', 'row']); sell_t = np.sort(body[(body.role == 'open_short')].te.values); sell_k = body[(body.role == 'open_short')].sort_values('te').strike.values; bb_t = np.sort(body[body.role == 'cover_short'].te.values); oth_t = np.sort(z[z.module != 'num'].te.values)
    sch_t = np.sort(sched_t); sch_k = g[g.sched].sort_values('te').strike.values; rk = g[g.reactive].sort_values('te').strike.values
    # query times: events then controls
    q = [(r.te, 1, r.strike) for r in ev.itertuples()]; n_ev = len(q); nctl = NC * n_ev; ctl = []
    while len(ctl) < nctl:
        t = rng.uniform(37800, 54900)
        if np.abs(sched_t - t).min() < 5 or np.abs(react_t - t).min() < 60: continue
        ctl.append(t)
    q += [(t, 0, np.nan) for t in ctl]; order = np.argsort([x[0] for x in q]); net = {}; ptr = 0; be = list(body.itertuples())
    for qi in order:
        t, y, strike = q[qi]
        while ptr < len(be) and be[ptr].te < t - 3: b = be[ptr]; net[(b.cp, int(b.strike))] = net.get((b.cp, int(b.strike)), 0) + b.sl; ptr += 1
        sh = {k: -v for k, v in net.items() if v < 0}; tot = sum(sh.values()); centre = sum(k[1] * v for k, v in sh.items()) / tot if tot > 0 else np.nan
        j = int((t - 33300) // 60); f = ((t - 33300) % 60) / 60.0; at = lambda k: sp[max(k - 1, 0)] + f * (sp[min(k, 374)] - sp[max(k - 1, 0)]); live = at(j); atm = near(live)
        w = lambda arr, tt: (tt - arr[arr < tt - 3].max()) if (arr < tt - 3).any() else np.nan
        last = lambda ts, ks: (ks[np.searchsorted(ts, t - 3) - 1] if np.searchsorted(ts, t - 3) > 0 else np.nan)
        atms = [near(sp[max(j - 1 - i, 0)]) for i in range(0, 16)]; chg = [i for i in range(1, 16) if atms[i] != atms[i - 1]]; chg5 = sum(1 for i in chg if i <= 5); chg15 = len(chg); since_chg = (chg[0] if chg else 16)
        hi = sp[1:j].max() if j > 1 else sp[1]; lo = sp[1:j].min() if j > 1 else sp[1]; ihi = j - 1 - int(np.argmax(sp[1:j])) if j > 1 else 0; ilo = j - 1 - int(np.argmin(sp[1:j])) if j > 1 else 0
        sma = lambda N: sp[max(j - N, 0):j].mean(); d_ = lambda x: (live - x) / step if x == x else np.nan
        d = {'spot 10 min ago': np.sign(live - at(j - 10)), 'spot 15 min ago': np.sign(live - at(j - 15)), 'spot 30 min ago': np.sign(live - at(j - 30)), 'spot 60 min ago': np.sign(live - at(j - 60)), 'SMA 5': np.sign(live - sma(5)), 'SMA 10': np.sign(live - sma(10)), 'SMA 15': np.sign(live - sma(15)), 'SMA 30': np.sign(live - sma(30)), 'SMA 60': np.sign(live - sma(60)),
             'last timetable pair strike': np.sign(live - last(sch_t, sch_k)), 'last reactive pair strike': np.sign(live - last(react_t, rk)), 'last body sell strike': np.sign(live - last(sell_t, sell_k)), 'short-book centre': np.sign(live - centre) if centre == centre else np.nan, 'opening ATM': np.sign(live - near(sp[1])), 'day mid-range': np.sign(live - (hi + lo) / 2)}
        row = dict(cid=cid, und=u, expiry=e, y=y, t=t, j=j, strike=strike, atm=atm, step=step, live=live, sec_since_1030=t - 37800, nifty=int(u == 'NIFTY'), v2=int(((u == 'NIFTY') and e >= '2026-09-22') or ((u == 'SENSEX') and e >= '2026-09-17')),
                   age_react=w(react_t, t), age_sell=w(sell_t, t), age_sched=w(sch_t, t), age_bb=w(bb_t, t), age_oth=w(oth_t, t),
                   d_last_pair=d_(last(sch_t, sch_k)), d_last_react=d_(last(react_t, rk)), d_last_sell=d_(last(sell_t, sell_k)), d_centre=d_(centre), d_open_atm=d_(near(sp[1])), d_sma10=(live - sma(10)) / step, d_sma30=(live - sma(30)) / step, d_sma60=(live - sma(60)) / step, d_mid=(live - (hi + lo) / 2) / step,
                   d_hi=(hi - live) / step, d_lo=(live - lo) / step, age_hi=ihi, age_lo=ilo, range_steps=(hi - lo) / step, frac_atm=(live - atm) / step, atm_chg5=chg5, atm_chg15=chg15, since_atm_chg=since_chg, m15=(live - at(j - 15)) / step, m5=(live - at(j - 5)) / step, m1=(live - at(j - 1)) / step)
        livec = sp[j - 1]; atc = lambda k: sp[max(k - 1, 0)]; smac = lambda N: sp[max(j - 1 - N, 0):j - 1].mean() if j - 1 > 0 else sp[1]; atmc = near(livec)
        hic = sp[1:j - 1].max() if j > 2 else sp[1]; loc = sp[1:j - 1].min() if j > 2 else sp[1]
        row.update(c_m15=(livec - atc(j - 15)) / step, c_m5=(livec - atc(j - 5)) / step, c_m1=(livec - atc(j - 1)) / step, c_d_last_pair=(livec - last(sch_t, sch_k)) / step, c_d_last_react=(livec - last(react_t, rk)) / step, c_d_last_sell=(livec - last(sell_t, sell_k)) / step, c_d_centre=(livec - centre) / step if centre == centre else np.nan,
                   c_d_open_atm=(livec - near(sp[1])) / step, c_d_sma10=(livec - smac(10)) / step, c_d_sma30=(livec - smac(30)) / step, c_d_sma60=(livec - smac(60)) / step, c_d_mid=(livec - (hic + loc) / 2) / step, c_d_hi=(hic - livec) / step, c_d_lo=(livec - loc) / step, c_frac_atm=(livec - atmc) / step,
                   cm_now=(sp[j] - sp[j - 1]) / step, pm_prev=(sp[j - 1] - sp[j - 2]) / step)
        for k_ in ('c_m15', 'c_m5', 'c_m1', 'cm_now', 'pm_prev', 'c_d_last_pair', 'c_d_last_react', 'c_d_last_sell', 'c_d_centre', 'c_d_open_atm'): row['abs_' + k_] = abs(row[k_]) if row[k_] == row[k_] else np.nan
        for k_ in ('d_last_pair', 'd_last_react', 'd_last_sell', 'd_centre', 'd_open_atm'): row['abs_' + k_] = abs(row[k_]) if row[k_] == row[k_] else np.nan
        row['abs_m15'] = abs(row['m15']); row['abs_m5'] = abs(row['m5'])
        if y == 1:
            for k, v in d.items(): row['dir|' + k] = float(atm + v * step == strike) if v == v else np.nan
        rows.append(row)
T = pd.DataFrame(rows); T.to_pickle(f'{OUT}/bl_act_table.pkl.gz'); E = T[T.y == 1]; print('events', len(E), 'controls', int((T.y == 0).sum()))
cols = [c for c in E.columns if c.startswith('dir|')]; cidv = E.cid.values; ucy = np.unique(cidv); idx = {c_: np.where(cidv == c_)[0] for c_ in ucy}; bs_idx = [np.concatenate([idx[c_] for c_ in rng.choice(ucy, len(ucy))]) for _ in range(400)]; base = E['dir|spot 15 min ago'].values; first = E.expiry.values < '2026-08-25'
for c_ in cols:
    x = E[c_].values; v = ~np.isnan(x); d = [np.nanmean(x[ii]) - np.nanmean(base[ii]) for ii in bs_idx]
    dir_rows.append((c_[4:], int(v.sum()), np.nanmean(x), np.nanmean(x[first]), np.nanmean(x[~first]), np.nanmean(x[(E.und == 'NIFTY').values]), np.nanmean(x[(E.und == 'SENSEX').values]), np.nanmean(x) - np.nanmean(base), np.quantile(d, .025), np.quantile(d, .975)))
DR = pd.DataFrame(dir_rows, columns=['reference X (direction = sign of live spot - X)', 'n', 'hit_rate', 'first_half', 'second_half', 'NIFTY', 'SENSEX', 'diff_vs_spot15', 'diff_lo', 'diff_hi']).sort_values('hit_rate', ascending=False); DR.round(4).to_csv(f'{OUT}/bl_act_dirs.csv', index=False); print(DR.round(3).to_string(index=False)); R['dirs'] = DR.round(4).to_dict('list'); R['n_events'] = len(E); R['n_controls'] = int((T.y == 0).sum())
import json as _j; rec('act1', R)
