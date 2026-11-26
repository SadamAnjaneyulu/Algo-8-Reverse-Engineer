"""Gate 6: integrated D-1 (frozen B1, one_lot_v2) + D0 (D0-C = engine + X1) cycles, mode F (free-running, no real input). Plan and criteria: reports/PHASE1_GATE6_PLAN.md (fixed before this ran).
Real logs are used only for scoring. Outputs outputs/phase1/6/."""
import sys, os, json, time, warnings; os.environ['ORDER_SPLIT'] = 'one_lot_v2'
for p in ('.', '../../../../d0_strategy', '../../../../d1_strategy', '../../../..', '..', '../..'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
from multiprocessing import Pool
import numpy as np, pandas as pd
import bl_common, bl_fr_sim as S, bl_oscore as Q, bl_p1_5a_port as A, bl_p1_5b as B, bl_p1_5c as C
import bl_score_d1_F as F1M
from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker, run_replay
from d1_algo.models import minute_index
from algo8_integrated import d1_state_to_d0_opening, HandoffError
from d0_algo import D0Engine
OUT = bl_common.OUT; CFG = os.environ.get('P1_CFG', 'legacy'); OD = f'{OUT}/phase1/6' if CFG == 'legacy' else f'{OUT}/phase1/9/final_{CFG}_integrated'; CY = S.CY
def d1_cycle(i):
    r = CY.iloc[i]; d = S.prep(i); o = S.OH[(r.und, r.expiry)]; op = d['op']; feed = ReplayFeed(o.open.values, o.high.values, o.low.values, o.close.values, d['K'], {k: v for k, v in op.items() if isinstance(k, tuple)})
    cfg = config_for(r.und, r.d1, order_split='one_lot_v2'); br = PaperBroker(feed); eng = D1Engine(cfg, feed, br); run_replay(eng, feed); df = eng.orders_frame()
    if len(df):
        import validate_engine as V
        df['cls'] = df.role.map(V.ROLE2CLS); df['cid'] = i; df['cp'] = df.right; df['j'] = df.minute; df['step'] = cfg.strike_step
    shorts = [(cp, float(k), float(l.entry_price)) for (cp, k), L in sorted(eng.book.shorts.items()) for l in L]
    return dict(i=i, df=df, shorts=shorts, wings={k: int(v) for k, v in eng.book.wings.items() if v > 0}, lump={k: int(v) for k, v in eng.book.lump.items() if v > 0}, fills=[(f.side, float(f.price), int(f.lots)) for f in br.all_fills], pos={k: int(v) for k, v in br.positions().items()}, rejected=len(eng.rejected))
class _Fill:
    def __init__(s, side, price, lots): s.side, s.price, s.lots = side, price, lots
class _Book:
    pass
def opening_from(d1, chain, unit):
    from algo8_integrated.handoff import d1_state_to_d0_opening
    b = _Book(); b.shorts = {}; 
    from d1_algo.models import Lot
    for cp, k, e in d1['shorts']: b.shorts.setdefault((cp, k), []).append(Lot(0.0, 0, e, 'x'))
    b.wings = d1['wings']; b.lump = d1['lump']; return d1_state_to_d0_opening(b, [_Fill(*f) for f in d1['fills']], unit, chain=chain)
def identity(op, d1):
    net = {}
    for cp, k, e in op.lots: net[(cp, float(k))] = net.get((cp, float(k)), 0) - 1
    for (md, cp, k), n in op.longs.items(): net[(cp, float(k))] = net.get((cp, float(k)), 0) + n
    net = {k: v for k, v in net.items() if v}; pos = {(cp, float(k)): v for (cp, k), v in d1['pos'].items() if v}
    cash = sum((1.0 if s == 'SELL' else -1.0) * p * n for s, p, n in d1['fills'])
    return net == pos, cash
def peak_shorts(df):
    if not len(df): return 0
    z = df.sort_values('ts', kind='stable'); peak = 0; cur = {'CE': 0, 'PE': 0}
    for r_, side, lots, role in zip(z.right, z.side, z.lots, z.role):
        if role in ('scheduled_straddle', 'breakout_straddle', 'breakout_extra', 'ladder_solo'): cur[r_] += int(lots)
        elif role == 'stop_buyback': cur[r_] = max(cur[r_] - int(lots), 0)
        peak = max(peak, cur[r_])
    return peak
if __name__ == '__main__':
    t0 = time.time(); os.makedirs(OD, exist_ok=True); PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl')
    with Pool(4) as p: D1 = {x['i']: x for x in p.map(d1_cycle, range(len(CY)))}
    print('D-1 replays', round(time.time() - t0), 's', flush=True)
    ORD = {i: x['df'] for i, x in D1.items()}; leg = Q.legacy_d1_scores(ORD, CY, S.REAL, bl_common.ref.STEP).set_index('cls').loc['ALL']; print('D-1 legacy F1 (all 32)', round(float(leg.F1), 4), flush=True)
    res = dict(d1_legacy_F1=float(leg.F1), d1_rejected=int(sum(x['rejected'] for x in D1.values())), d1_peak_short_lots_per_right=int(max(peak_shorts(x['df']) for x in D1.values())), sets={})
    sim_d1_all = F1M.build_sim(ORD, CY); real_d1_all = F1M.build_real(CY)
    for sname, keys in C.SETS.items():
        items = []; opens = {}; meta = dict(identity_ok=0, runs=0, handoff_errors=[], reconciled=0, deterministic=0, rejected=0, peak_short=0, peak_dec=0, stopped=[], cash_diff_max=0.0, carry_contracts=[])
        for k in keys:
            P = PR[k]
            for i in P['test']:
                r = A.CY.iloc[i]; m = A.market_of(i); unit = float(r.unit)
                try: op = opening_from(D1[i], m.K, unit)
                except HandoffError as ex: meta['handoff_errors'].append(dict(cyc=f'{r.und}|{r.expiry}', error=str(ex))); continue
                ok, cash = identity(op, D1[i]); meta['identity_ok'] += int(ok); meta['cash_diff_max'] = max(meta['cash_diff_max'], abs(cash * unit - op.cash)); meta['runs'] += 1
                def mk():
                    c = (C.mod_clk(363) if CFG == 'legacy' else C.MODS[CFG])(A.config_of(P, i), i); c.risk_mode = 'enforce'; e = D0Engine(c, m, opening_from(D1[i], m.K, unit)); e.run(); return e
                e = mk(); e2 = mk(); items.append((i, e)); opens[i] = op; meta['reconciled'] += int(e.reconcile(op)); meta['deterministic'] += int(e2.events_frame().equals(e.events_frame())); meta['rejected'] += len(e.rejected)
                meta['peak_short'] = max(meta['peak_short'], e.max_short_seen); meta['peak_dec'] = max(meta['peak_dec'], max(e._decisions.values(), default=0))
                if e.stopped: meta['stopped'].append(f'{r.und}|{r.expiry}')
        cids = [i for i, _ in items]; real0 = B.real_frame(cids); attrs = B.attrs_of(cids, real0); sim0 = B.sim_frame(items); cycs = set(real0.cyc)
        sim1 = sim_d1_all[sim_d1_all.cyc.isin(cycs)].copy(); real1 = real_d1_all[real_d1_all.cyc.isin(cycs)].copy()
        R0 = Q.score(real0, sim0, attrs, 'F', 'historical reproduction', shift_placebo=True, bootstrap=1000); st = R0['strictness']; f = lambda R, tol, lvl: float(R['strictness'][(R['strictness'].cumulative_tolerance_s == tol) & (R['strictness'].level == lvl)].F1.iloc[0])
        R1 = Q.score(real1, sim1, attrs, 'F', 'historical reproduction', shift_placebo=True, bootstrap=0)
        both_real = pd.concat([real1, real0], ignore_index=True); both_sim = pd.concat([sim1, sim0], ignore_index=True)
        Rb = Q.score(both_real, both_sim, attrs, 'F', 'historical reproduction', shift_placebo=True, bootstrap=0)
        CS = B.carry_state(Q.prepare_real(real0), Q.prepare_sim(sim0), R0['_pairs'], opens)
        # carry error at the D0 open: book distance sim vs real opening (contract level, normalised by real gross lots)
        dist = []
        for i in cids:
            r = A.CY.iloc[i]; ro = A.opening_of(i); so = opens[i]
            def vec(op):
                v = {}
                for cp, k, e in op.lots: v[(cp, float(k))] = v.get((cp, float(k)), 0) - 1
                for (md, cp, k), n in op.longs.items(): v[(cp, float(k))] = v.get((cp, float(k)), 0) + n
                for (md, cp, k), n in op.oshort.items(): v[(cp, float(k))] = v.get((cp, float(k)), 0) - n
                return v
            a, b = vec(ro), vec(so); keys_ = set(a) | set(b); l1 = sum(abs(a.get(x, 0) - b.get(x, 0)) for x in keys_); gross = sum(abs(v) for v in a.values())
            sh_r = sum(1 for _ in ro.lots) + sum(ro.oshort.values()); sh_s = len(so.lots); dist.append(dict(cyc=f'{r.und}|{r.expiry}', l1=l1, gross_real=gross, l1_norm=l1 / max(gross, 1), real_shorts=sh_r, sim_shorts=sh_s, real_longs=sum(ro.longs.values()), sim_longs=sum(so.longs.values())))
        DD = pd.DataFrame(dist); DD.to_csv(f'{OD}/{sname}_carry_at_open.csv', index=False)
        for nm, R in (('d0', R0), ('d1', R1), ('both', Rb)):
            d = f'{OD}/{sname}_{nm}'; os.makedirs(d, exist_ok=True)
            for k_, v in R.items():
                if isinstance(v, pd.DataFrame) and not k_.startswith('_'): v.to_csv(f'{d}/{k_}.csv', index=False)
        res['sets'][sname] = dict(meta=meta, cycles=len(cids), d0=dict(real=int(len(real0)), sim=int(len(sim0)), keys_F1_60s=f(R0, 60, 'keys'), strict_F1_60s=f(R0, 60, 'lots_exact'), placebo=R0['time_shift_placebo']['F1_keys_at_60s'], ci=R0['pooled_F1_ci95'], per_cycle=R0['per_cycle_F1'], book_L1_median=float(CS.l1_norm.median())), d1=dict(real=int(len(real1)), sim=int(len(sim1)), keys_F1_60s=f(R1, 60, 'keys'), strict_F1_60s=f(R1, 60, 'lots_exact'), placebo=R1['time_shift_placebo']['F1_keys_at_60s']), both=dict(real=int(len(both_real)), sim=int(len(both_sim)), keys_F1_60s=f(Rb, 60, 'keys'), strict_F1_60s=f(Rb, 60, 'lots_exact'), placebo=Rb['time_shift_placebo']['F1_keys_at_60s']),
            carry_at_open=dict(median_l1_norm=float(DD.l1_norm.median()), p25=float(DD.l1_norm.quantile(.25)), p75=float(DD.l1_norm.quantile(.75)), max=float(DD.l1_norm.max()), real_shorts_median=float(DD.real_shorts.median()), sim_shorts_median=float(DD.sim_shorts.median()), shorts_ratio_median=float((DD.sim_shorts / DD.real_shorts.clip(lower=1)).median())))
        print(sname, 'D0 keys F1', round(res['sets'][sname]['d0']['keys_F1_60s'], 4), 'D-1', round(res['sets'][sname]['d1']['keys_F1_60s'], 4), 'both', round(res['sets'][sname]['both']['keys_F1_60s'], 4), 'carry L1 med', round(res['sets'][sname]['carry_at_open']['median_l1_norm'], 3), meta['identity_ok'], '/', meta['runs'], flush=True)
    json.dump(res, open(f'{OD}/summary.json', 'w'), indent=1, default=float); print('seconds', round(time.time() - t0))
