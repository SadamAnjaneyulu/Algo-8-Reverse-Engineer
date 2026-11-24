"""Anatomy of the real late D-1 sales (15:15-15:40, post-auction, 18 cycles, 16 Oct excluded) that the best candidate (engine ladder on FUT, gate 5, teacher-forced
reference = last real sale) does not match (+-1 minute, same side). Descriptive only; nothing is fitted. Output outputs/fwd/unmatched_orders.csv, unmatched_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG, algo8_d1 as A
OUT = S.OUT; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16')
if __name__ == '__main__':
    O = DG.real_orders(); O = O.assign(jj=(O.t_last // 60 - 555).astype(int)); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; B = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(B.und, B.expiry)); rows = []
    for r in T.itertuples():
        if (r.und, r.expiry) not in keep or (r.und, r.d1) == OUTLIER or r.d0 < CAS: continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; sells = g[(g.role == 'open_short')].sort_values('t_last'); covers = g[g.role == 'cover_short']
        ev = {cp: sorted(set(sells[sells.cp == cp].jj.tolist())) for cp in ('CE', 'PE')}; fut = pd.read_pickle(f'{OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')['spot1']; h, l, c = (fut[k].values.astype(float) for k in ('high', 'low', 'close'))
        cfg = A.Config(); cfg.ladder_gate_min = 5; cfg.strike_step = 50.0 if r.und == 'NIFTY' else 100.0; lad = A.ladder_fires(c, h, l, ev, cfg); pred = {(j, cp) for j, cps in lad.items() for cp in cps}
        cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); K = cx['opt1']['K']; spot_ref = float(c[359])
        late = sells[(sells.jj >= 360)]
        for q in late.itertuples():
            j = int(q.jj); matched = any((j + d, q.cp) in pred for d in (-1, 0, 1)); other = 'PE' if q.cp == 'CE' else 'CE'
            same_min_other = bool(((late.cp == other) & (late.jj == j)).any()); same_min_same = int(((late.cp == q.cp) & (late.jj == j)).sum()) - 1
            near_other10 = bool(((late.cp == other) & ((late.t_last - q.t_last).abs() <= 10)).any()); prior_same = sells[(sells.cp == q.cp) & (sells.jj < j)]
            held_strike = bool((prior_same.strike == q.strike).any()); sh = lambda s: int(sells[(sells.cp == s) & (sells.jj < j)].lots.sum() - covers[(covers.cp == s) & (covers.jj < j)].lots.sum())
            atm_off = (q.strike - spot_ref) / cfg.strike_step * (1 if q.cp == 'CE' else -1)
            rows.append(dict(und=r.und, d1=r.d1, j=j, hms=f'{int(q.t_last) // 3600:02d}:{int(q.t_last) % 3600 // 60:02d}:{int(q.t_last) % 60:02d}', cp=q.cp, lots=int(q.lots), strike=int(q.strike), px=float(q.px_avg), matched=matched, paired_other_side_same_minute=same_min_other,
                             paired_other_side_10s=near_other10, n_same_side_same_minute=same_min_same, held_strike=held_strike, lighter_side=sh(q.cp) < sh(other), imb_same_minus_other=sh(q.cp) - sh(other), otm_steps=float(atm_off),
                             minute_bucket='15:15-15:19' if j < 365 else '15:20-15:24' if j < 370 else '15:25-15:29' if j < 375 else '15:30-15:39'))
    D = pd.DataFrame(rows); D.to_csv(f'{OUT}/fwd/unmatched_orders.csv', index=False)
    g = lambda m: dict(n=int(m.sum()), lots=int(D[m].lots.sum()), paired_10s=float(D[m].paired_other_side_10s.mean()), paired_same_min=float(D[m].paired_other_side_same_minute.mean()), held=float(D[m].held_strike.mean()), lighter=float(D[m].lighter_side.mean()), one_lot=float((D[m].lots == 1).mean()), median_lots=float(D[m].lots.median()))
    res = dict(orders=len(D), lots=int(D.lots.sum()), matched=g(D.matched), unmatched=g(~D.matched), by_bucket=D.groupby(['minute_bucket', 'matched']).size().unstack(fill_value=0).to_dict('index'), cycles=int(D.groupby(['und', 'd1']).ngroups))
    # of unmatched, how many are the other-side leg of a pair whose partner IS matched, or pairs that are both unmatched
    um = D[~D.matched]; partner_matched = []
    for x in um.itertuples():
        p = D[(D.und == x.und) & (D.d1 == x.d1) & (D.cp != x.cp) & (((D.j - x.j).abs() <= 0))]; partner_matched.append(bool(p.matched.any()) if len(p) else None)
    um = um.assign(partner=partner_matched); res['unmatched_with_partner_matched'] = int((um.partner == True).sum()); res['unmatched_with_partner_unmatched'] = int((um.partner == False).sum()); res['unmatched_no_partner'] = int(um.partner.isna().sum())
    json.dump(res, open(f'{OUT}/fwd/unmatched_summary.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3)))
