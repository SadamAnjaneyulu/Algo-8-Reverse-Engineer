"""Validation of the live engine (d1_strategy/d1_algo) by replaying the real one-minute bars of the 32 D-1 sessions through it, second by second, and scoring its orders
against the real order log with the same lot matching as the earlier reconstruction (same side and class, +-1 minute; lump +-3).
Compared with the batch reconstruction (which sees whole minute bars at once), the engine is causal: it decides with prices that exist at that second.
Outputs bl_d1eng_orders.pkl.gz, bl_d1eng_scores.csv, bl_summary_d1eng.json"""
import sys, warnings, json, time; sys.path.insert(0, '.'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
from multiprocessing import Pool
from bl_common import *
import bl_fr_sim as S
from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker, run_replay
from d1_algo.models import minute_index
CY, REAL = S.CY, S.REAL
ROLE2CLS = {'scheduled_straddle': 'body_sell', 'breakout_straddle': 'body_sell', 'breakout_extra': 'body_sell', 'ladder_solo': 'body_sell', 'stop_buyback': 'body_buyback', 'protective_wing_buy': 'wing_buy', 'protective_wing_sell': 'wing_sell', 'opening_wing_buy': 'opening_wings', 'overnight_lump': 'lump'}
def run_cycle(i, overrides=None):
    r = CY.iloc[i]; d = S.prep(i); o = S.OH[(r.und, r.expiry)]; op = d['op']
    feed = ReplayFeed(o.open.values, o.high.values, o.low.values, o.close.values, d['K'], {k: v for k, v in op.items() if isinstance(k, tuple)})
    cfg = config_for(r.und, r.d1, **(overrides or {})); eng = D1Engine(cfg, feed, PaperBroker(feed)); run_replay(eng, feed)
    df = eng.orders_frame()
    if len(df): df['cls'] = df.role.map(ROLE2CLS); df['cid'] = i; df['cp'] = df.right; df['j'] = df.minute; df['step'] = cfg.strike_step
    return i, df, len(eng.rejected)
if __name__ == '__main__':
    ids = list(range(len(CY))); t0 = time.time()
    with Pool(max(1, min(8, __import__('os').cpu_count() or 1))) as p: res = p.map(run_cycle, ids)
    print('replay seconds', round(time.time() - t0)); ORD = {i: df for i, df, _ in res}; REJ = {i: n for i, _, n in res}
    pd.to_pickle(ORD, f'{OUT}/bl_d1eng_orders.pkl.gz')
    # ---- scoring (same matching as validate_d1_package.py)
    CLASS = {('num', 'open_short'): 'body_sell', ('num', 'cover_short'): 'body_buyback', ('h_', 'open_long'): 'wing_buy', ('h_', 'close_long'): 'wing_sell', ('num', 'open_long'): 'opening_wings', ('v_', 'open_long'): 'lump'}
    REAL['cls'] = [CLASS.get((m, r_), 'not_modelled') for m, r_ in zip(REAL.module, REAL.role)]; REAL.loc[(REAL.cls == 'opening_wings') & (REAL.j > 2), 'cls'] = 'not_modelled'
    NMOD = ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'opening_wings', 'lump']; TOL = {c: 1 for c in NMOD}; TOL['lump'] = 3
    lots_of = lambda df: df.loc[df.index.repeat(df.lots.astype(int))]
    RL = {}
    for i, r in enumerate(CY.itertuples()):
        z = REAL[(REAL.und == r.und) & (REAL.expiry == r.expiry)]
        for (cls, cp), g in z.groupby(['cls', 'cp']): g = lots_of(g); RL[(i, cls, cp)] = (g.j.values.astype(int), g.strike.values.astype(float))
    def match(rj, rk, sj, sk, tol):
        bucket = {}
        for n, j in enumerate(sj): bucket.setdefault(int(j), []).append(n)
        used = np.zeros(len(sj), bool); done = np.zeros(len(rj), bool); dk = []
        for ps in range(tol + 1):
            for a in range(len(rj)):
                if done[a]: continue
                best = None
                for jj in ({rj[a]} if ps == 0 else {rj[a] - ps, rj[a] + ps}):
                    for n in bucket.get(int(jj), []):
                        if used[n]: continue
                        dd = abs(sk[n] - rk[a])
                        if best is None or dd < best[0]: best = (dd, n)
                if best: used[best[1]] = True; done[a] = True; dk.append(best[0])
        return np.array(dk)
    rows = {c: dict(real=0, sim=0, tp=0, exact=0, within1=0) for c in NMOD + ['not_modelled']}
    for i in ids:
        o = ORD[i]; ol = lots_of(o) if len(o) else o; st = ref.STEP[CY.iloc[i].und]
        for cls in NMOD + ['not_modelled']:
            for cp in ('CE', 'PE'):
                rj, rk = RL.get((i, cls, cp), (np.array([], int), np.array([], float))); rows[cls]['real'] += len(rj)
                if cls == 'not_modelled' or not len(ol): continue
                g = ol[(ol.cls == cls) & (ol.cp == cp)]; rows[cls]['sim'] += len(g)
                if len(rj) and len(g):
                    dk = match(rj, rk, g.j.values.astype(int), g.strike.values.astype(float), TOL[cls]); rows[cls]['tp'] += len(dk); rows[cls]['exact'] += int((dk == 0).sum()); rows[cls]['within1'] += int((dk <= st).sum())
    f1 = lambda tp, sim, real: 2 * tp / max(sim + real, 1)
    tp = sum(rows[c]['tp'] for c in NMOD); sm = sum(rows[c]['sim'] for c in NMOD); rl = sum(rows[c]['real'] for c in rows); w1 = sum(rows[c]['within1'] for c in NMOD); ex = sum(rows[c]['exact'] for c in NMOD)
    out = [dict(cls='ALL', real_lots=rl, sim_lots=sm, matched=tp, precision=tp / sm, recall=tp / rl, F1=f1(tp, sm, rl), F1_strike_within_one=f1(w1, sm, rl), F1_exact_strike=f1(ex, sm, rl))]
    for c in NMOD: d = rows[c]; out.append(dict(cls=c, real_lots=d['real'], sim_lots=d['sim'], matched=d['tp'], precision=d['tp'] / max(d['sim'], 1), recall=d['tp'] / max(d['real'], 1), F1=f1(d['tp'], d['sim'], d['real']), F1_strike_within_one=f1(d['within1'], d['sim'], d['real']), F1_exact_strike=f1(d['exact'], d['sim'], d['real'])))
    SC = pd.DataFrame(out); SC.round(4).to_csv(f'{OUT}/bl_d1eng_scores.csv', index=False); print(SC.round(3).to_string(index=False))
    # roles breakdown and per-cycle
    allo = pd.concat([d for d in ORD.values() if len(d)]); print(allo.groupby('role').lots.agg(['size', 'sum']).to_string())
    rec('d1eng', dict(scores=SC.round(4).to_dict('records'), rejected_orders=int(sum(REJ.values())), cycles=len(ids), replay_seconds=round(time.time() - t0), roles=allo.groupby('role').lots.agg(['size', 'sum']).to_dict('index')))
