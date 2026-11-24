"""Forward-test evaluation harness (pre-defined in reports/FORWARD_TEST.md; nothing here is tuned on forward data).
Inputs: the recorder logs of d1_algo.shadow (orders_*.jsonl, minutes_*.jsonl). Outputs, per regime (pre-3-Aug / 3-Aug-to-6-Dec / from-7-Dec):
  PRIMARY    stratified AUC(frozen score) - AUC(frozen clock table), within (cycle, side) blocks, cluster bootstrap over cycles
  DECISION   order-level and event-level precision / recall of the frozen rule (+-0 and +-1 minute, same side), vs a same-count random baseline
  STRIKE     agreement of the rule's proposed strike with the real strike on matched orders (exact, within 1 step)
  SIZE       share of matched orders whose real lots equal the rule's lots
  CYCLE      teacher-forced D0 P&L agreement (bl_clr_test) with stop flips reported separately (computed from the cycle table, see cycle_pnl)
`python bl_fwd_eval.py --dev-dry-run` replays the development cycles through the live-form rule and checks it reproduces the batch results exactly."""
import sys, os, json, glob, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/d1_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from bl_trig_test import blocks, strat
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); FW = f'{OUT}/fwd'; RNG = np.random.default_rng(404)
def regime(d1_date):
    d0 = d1_date  # D-1 date is enough: the auction regime changes on the first D-1 session
    return 'pre_3Aug' if d0 < '2026-08-03' else ('3Aug_6Dec' if d0 < '2026-12-07' else 'from_7Dec')
def load_forward(log_dir, model):
    """-> (orders df of real sells in the window, fires df, event-table df for the primary test). One row per (cycle, minute, side) in the window."""
    W0, W1 = model['window']; orders, fires, rows = [], [], []
    for fo in sorted(glob.glob(f'{log_dir}/orders_*.jsonl')):
        tag = os.path.basename(fo)[len('orders_'):-len('.jsonl')]; fm = f'{log_dir}/minutes_{tag}.jsonl'
        O = [json.loads(x) for x in open(fo)]; M = [json.loads(x) for x in open(fm)]; und, d1 = tag.rsplit('_', 1); cyc = f'{und}|{d1}'
        step = 50.0 if und == 'NIFTY' else 100.0; sells = [o for o in O if o['side'] == 'sell' and o.get('role', '') in ('', 'open_short', 'body_sell', 'ladder_solo', 'scheduled_straddle', 'breakout_straddle', 'breakout_extra')]
        for o in sells:
            if W0 <= o['j'] <= W1: orders.append(dict(cyc=cyc, und=und, d1=d1, regime=regime(d1), j=o['j'], cp=o['right'], strike=o['strike'], lots=o['lots'], px=o['price'], proposed_strike=o['rule'].get('proposed_strike'), last_strike=o.get('last_sale_strike_same_side'), step=step))
        fut = {m['j']: m['fut'] for m in M if m.get('fut')}; reg = regime(d1); tab = model.get('clock_table_by_regime', {}).get(reg, model['clock_table'] if reg == '3Aug_6Dec' else None)
        for m in M:
            for f in m['rule']['fires_this_minute']: fires.append(dict(cyc=cyc, und=und, d1=d1, regime=regime(d1), j=f['minute'], cp=f['right'], lots=f['lots']))
        for j in range(W0, W1 + 1):
            if j not in fut or j - 1 not in fut or tab is None: continue                                  # no clock table for this regime yet: counted in decision metrics only
            for side in ('CE', 'PE'):
                sg = -1 if side == 'CE' else 1; lo5 = [fut[k][2] for k in range(j - 5, j) if k in fut]; hi5 = [fut[k][1] for k in range(j - 5, j) if k in fut]
                if len(lo5) < 5: continue
                ext5 = float((fut[j][2] < min(lo5)) if side == 'CE' else (fut[j][1] > max(hi5))); mv1 = sg * (fut[j][3] - fut[j - 1][3]) / step
                y = int(any(o['j'] == j and o['right'] == side for o in sells))
                rows.append(dict(cyc=cyc, und=und, d1=d1, regime=regime(d1), j=j, side=side, y=y, FUT_ext5=ext5, FUT_mv1=mv1, clock=tab[f'{j}|{side}']))
    return pd.DataFrame(orders), pd.DataFrame(fires), pd.DataFrame(rows)
def frozen_score(T, model):
    X = T[model['features']].copy()
    for c in model['features']: X[c] = X[c].fillna(model['medians'][c])
    z = (X.values - np.array(model['mean'])) / np.array(model['std']); return z @ np.array(model['coef']) + model['intercept']
def primary_test(T, model, B=2000):
    T = T.copy().reset_index(drop=True); T['score'] = frozen_score(T, model); T['block'] = T.cyc + '|' + T.side; R, y, bl = blocks(T.assign(clock_tab=T.clock), ['score', 'clock_tab']); a = strat(R, y, bl)
    ub = np.unique(bl); cyc_of = {b: b.rsplit('|', 1)[0] for b in ub}; cs = sorted(set(cyc_of.values())); d = []
    for _ in range(B):
        k = RNG.integers(0, len(cs), len(cs)); cnt = pd.Series(k).map(lambda i: cs[i]).value_counts(); w = {b: cnt.get(cyc_of[b], 0) for b in ub}; v = strat(R, y, bl, w); d.append(v[0] - v[1])
    d = np.array(d); return dict(n_cycles=len(cs), n_events=int(T.y.sum()), auc_model=float(a[0]), auc_clock=float(a[1]), delta=float(a[0] - a[1]), ci=[float(x) for x in np.nanquantile(d, [.025, .975])])
def decision_metrics(orders, fires, tol=1):
    """order-level (each real order matched if a rule fire on the same side within +-tol minutes) and event-level ((minute, side) sets)"""
    out = {}
    for cyc in sorted(set(orders.cyc) | set(fires.cyc)):
        o = orders[orders.cyc == cyc] if len(orders) else orders; f = fires[fires.cyc == cyc] if len(fires) else fires
        fs = {(int(j), c) for j, c in zip(f.j, f.cp)} if len(f) else set(); os_ = {(int(j), c) for j, c in zip(o.j, o.cp)} if len(o) else set()
        om = int(sum(any((int(j) + d, c) in fs for d in range(-tol, tol + 1)) for j, c in zip(o.j, o.cp))) if len(o) else 0
        tp = sum(1 for x in fs if any((x[0] + d, x[1]) in os_ for d in range(-tol, tol + 1))); hit = sum(1 for x in os_ if any((x[0] + d, x[1]) in fs for d in range(-tol, tol + 1)))
        out[cyc] = dict(orders=len(o), orders_matched=om, events_real=len(os_), events_hit=hit, fires=len(fs), fires_matched=tp)
    D = pd.DataFrame(out).T; s = D.sum(); p = s.fires_matched / max(s.fires, 1); r = s.events_hit / max(s.events_real, 1)
    return dict(cycles=len(D), order_recall=float(s.orders_matched / max(s.orders, 1)), orders=int(s.orders), event_precision=float(p), event_recall=float(r), event_f1=float(2 * p * r / (p + r)) if p + r else 0.0, fires=int(s.fires), events=int(s.events_real))
def strike_size(orders, fires, tol=1):
    m = []
    for cyc, o in orders.groupby('cyc'):
        f = fires[fires.cyc == cyc] if len(fires) else fires; fs = {(int(j), c) for j, c in zip(f.j, f.cp)} if len(f) else set()
        for q in o.itertuples():
            if any((int(q.j) + d, q.cp) in fs for d in range(-tol, tol + 1)) and q.proposed_strike is not None and q.proposed_strike == q.proposed_strike: m.append((abs(q.proposed_strike - q.strike) / q.step, q.lots))
    if not m: return dict(matched_with_proposal=0)
    a = np.array(m); out = dict(matched_with_proposal=len(a), strike_exact=float((a[:, 0] < 1e-9).mean()), strike_within_1_step=float((a[:, 0] <= 1.0 + 1e-9).mean()), size_equal=float((a[:, 1] == 1).mean()))
    ml = [abs(q.last_strike - q.strike) / q.step for q in orders.itertuples() if q.last_strike is not None and q.last_strike == q.last_strike]
    if ml: out.update(last_strike_n=len(ml), last_strike_exact=float(np.mean(np.array(ml) < 1e-9)), last_strike_within_1_step=float(np.mean(np.array(ml) <= 1.0 + 1e-9)))
    return out
def evaluate(log_dir, model):
    orders, fires, T = load_forward(log_dir, model); res = {}
    for reg in sorted(set(T.regime) | set(orders.regime if len(orders) else [])):
        o = orders[orders.regime == reg] if len(orders) else orders; f = fires[fires.regime == reg] if len(fires) else fires; t = T[T.regime == reg]
        res[reg] = dict(decision=decision_metrics(o, f) if len(o) else None, strike_size=strike_size(o, f) if len(o) else None, primary=primary_test(t, model) if t.y.sum() > 0 else None)
    return res
if __name__ == '__main__':
    if '--dev-dry-run' in sys.argv:
        import bl_bt3_sim as S, bl_d0x_diag as DG, algo8_d1 as A
        from d1_algo.shadow import FrozenLateRule, LateRuleConfig, solo_strike
        model = json.load(open(f'{FW}/frozen_model.json')); Od = DG.real_orders(); Od = Od.assign(jj=(Od.t_last // 60 - 555).astype(int)); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]
        Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); LT = pd.read_csv(f'{OUT}/trig/ladder_scores.csv'); LT = LT[(LT.era == 'after') & (LT.underlying == 'FUT') & (LT.G == 5)].set_index(['und', 'expiry'])
        orders, fires, ident, rows = [], [], True, []
        for r in T.itertuples():
            if (r.und, r.expiry) not in keep or r.d0 < '2026-08-03' or (r.und, r.d1) == ('NIFTY', '2026-10-16'): continue
            g = Od[(Od.und == r.und) & (Od.expiry == r.expiry) & (Od.dayno == 0) & (Od.role == 'open_short')].sort_values('t_last'); fut = pd.read_pickle(f'{OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')['spot1']; step = 50.0 if r.und == 'NIFTY' else 100.0
            h, l, c, o_ = (fut[k].values.astype(float) for k in ('high', 'low', 'close', 'open')); ev = {cp: sorted(set(g[g.cp == cp].jj.tolist())) for cp in ('CE', 'PE')}; cyc = f'{r.und}|{r.d1}'
            rule = FrozenLateRule(LateRuleConfig(), step); T0 = 555 * 60.0
            for j in range(len(c)):
                for k, p in enumerate((o_[j], h[j], l[j], c[j])): rule.on_tick(T0 + 60.0 * j + 10 * k, p)
                for cp in ('CE', 'PE'):
                    if j in ev[cp]: rule.on_real_sale(cp, j)
            rule.flush(); live = {(f['minute'], f['right']) for f in rule.fires}; cfg = A.Config(); cfg.ladder_gate_min = 5; cfg.strike_step = step; bat = {(j, cp) for j, cps in A.ladder_fires(c, h, l, ev, cfg).items() for cp in cps if 360 <= j <= 384}
            ident &= (live == bat)
            for f in rule.fires: fires.append(dict(cyc=cyc, j=f['minute'], cp=f['right'], lots=1, regime='3Aug_6Dec'))
            cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); K = cx['opt1']['K']; ki = {int(k): i for i, k in enumerate(K)}; ops = pd.read_pickle(f'{OUT}/bt3s/{r.und}_{r.expiry}.pkl.gz')['spot1'].close.values
            for q in g[g.jj >= 360].itertuples():
                j = int(q.jj); prior = g[(g.cp == q.cp) & (g.jj < j)]; lastp = float(prior.px_avg.iloc[-1]) if len(prior) else None
                prem = lambda k, cp=q.cp, j=j: float(cx['opt1'][(cp, 'close')][ki[int(k)], j - 1]) if int(k) in ki else float('nan')
                prop = solo_strike(K, float(K[np.argmin(np.abs(K - ops[j - 1]))]), prem, lastp, step, 4); orders.append(dict(cyc=cyc, regime='3Aug_6Dec', j=j, cp=q.cp, strike=float(q.strike), lots=int(q.lots), proposed_strike=prop, last_strike=(float(prior.strike.iloc[-1]) if len(prior) else None), step=step))
        orders, fires = pd.DataFrame(orders), pd.DataFrame(fires); dm = decision_metrics(orders, fires); ss = strike_size(orders, fires)
        ref = LT.reset_index(); tp, npred, hit, nreal = ref.tp.sum(), ref.npred.sum(), ref.hit.sum(), ref.nreal.sum()
        res = dict(live_form_identical_to_batch=bool(ident), decision=dm, strike_size=ss, reference_from_bl_trig_ladder=dict(event_precision=float(tp / npred), event_recall=float(hit / nreal), events=int(nreal)))
        json.dump(res, open(f'{FW}/dev_dry_run.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3)))
