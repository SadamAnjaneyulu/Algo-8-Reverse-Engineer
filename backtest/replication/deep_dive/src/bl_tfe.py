"""D-1 per-event teacher-forced run (TF-E), spec v1.1 section 6, pre-registered in reports/D1_TFE_PLAN.md. DIAGNOSTIC ONLY: never a primary score, a closure gate or evidence of reproduction.
After the simulator's step at second t, every real order whose first fill is at t is applied to a rebuilt real book and the simulator's PORTFOLIO book is replaced by it. The simulator's own orders are kept and scored. The simulator sees only real orders strictly before t.
Variants: 'book' (primary: shorts with entry prices, wings, lump) and 'memory' (TF-E-m, labelled sensitivity: also last_sale_price and the wing-controller timer from real body orders).
Usage: python bl_tfe.py [book|memory]   ->  outputs/scoring/d1_TFE_v2_onelot  or  d1_TFE_m_v2_onelot"""
import sys, os, json, time, hashlib, datetime, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
from multiprocessing import Pool
import numpy as np, pandas as pd
from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker
from d1_algo.book import Book
from d1_algo.models import Lot, minute_index, SESSION_OPEN_S

ENGINE_CONVENTION = 'one_lot_v2'
BODY_ROLES = ('open_short', 'cover_short')                                    # real body-module orders that the engine marks as body activity (wing-controller timer): sales and buy-backs, plus the opening wings (num open_long in the first minutes)

def apply_real(book, r):
    """one real order (dict: cp, strike, side, lots, role, module, px, t) applied to the rebuilt real book by its order-log role. Excess of a close_long over holdings becomes a short lot, so the net position per contract stays exact."""
    cp, k, n = r['cp'], float(r['strike']), int(r['lots']); key = (cp, k); role = r['role']
    if role == 'open_short': book.add_short(cp, k, Lot(float(r['t']), minute_index(r['t']), float(r['px']), 'real'), n)
    elif role == 'cover_short': book.remove_shorts(cp, k, n)
    elif role == 'open_long':
        if r['module'] == 'v_': book.lump[key] = book.lump.get(key, 0) + n
        else: book.add_wing(cp, k, n)
    elif role == 'close_long':
        have = book.wings.get(key, 0); a = min(n, have); book.sell_wing(cp, k, a); left = n - a
        m = min(left, book.lump.get(key, 0)); book.lump[key] = book.lump.get(key, 0) - m; left -= m
        if left > 0: book.add_short(cp, k, Lot(float(r['t']), minute_index(r['t']), float(r['px']), 'real'), left)
    else: raise ValueError(f'unknown real role {role!r}')

def net_positions(book):
    """per-contract net lots of a Book (long positive, short negative)"""
    net = {}
    for key, v in book.shorts.items():
        if v: net[key] = net.get(key, 0) - len(v)
    for key, v in book.wings.items():
        if v: net[key] = net.get(key, 0) + v
    for key, v in book.lump.items():
        if v: net[key] = net.get(key, 0) + v
    return {k: v for k, v in net.items() if v != 0}

def drift_record(sim_book, real_book, t, n_real):
    a, b = net_positions(sim_book), net_positions(real_book); keys = set(a) | set(b); d = dict(t=int(t), n_real_orders=int(n_real))
    for cp in ('CE', 'PE'):
        d[f'S_sim_{cp}'] = sum(len(v) for (c, _), v in sim_book.shorts.items() if c == cp); d[f'S_real_{cp}'] = sum(len(v) for (c, _), v in real_book.shorts.items() if c == cp)
        d[f'L_sim_{cp}'] = sum(v for (c, _), v in sim_book.wings.items() if c == cp) + sum(v for (c, _), v in sim_book.lump.items() if c == cp); d[f'L_real_{cp}'] = sum(v for (c, _), v in real_book.wings.items() if c == cp) + sum(v for (c, _), v in real_book.lump.items() if c == cp)
    d['l1'] = float(sum(abs(a.get(k, 0) - b.get(k, 0)) for k in keys)); d['gross_real'] = float(sum(abs(v) for v in b.values())); return d

def run_teacher_forced(eng, feed, real_rows, variant='book', t_start=SESSION_OPEN_S, t_end=SESSION_OPEN_S + 390 * 60):
    """drive the engine second by second with per-event reconciliation. real_rows: list of dicts (t, row, cp, strike, side, lots, role, module, px). Returns (engine, drift list, shadow real book).
    eng.tfe_redecision is set: a list aligned with eng.orders, True for a simulated stop_buyback that only repeats a buy-back the reconciliation undid (plan Addendum 2; post hoc, used only by the first-decision scoring)."""
    assert variant in ('book', 'memory')
    by_t = {}
    for r in sorted(real_rows, key=lambda r: (int(r['t']), r['row'])):
        if not (t_start <= int(r['t']) <= t_end): raise ValueError(f"real order at {r['t']} outside the replay window [{t_start}, {t_end}]")
        by_t.setdefault(int(r['t']), []).append(r)
    shadow = Book(); drift = []; flags = []; pool = {}; epoch_stops = {}; t = int(t_start)
    while t <= t_end:
        rows = by_t.get(t)
        if rows: drift.append(drift_record(eng.book, shadow, t, len(rows)))             # divergence entering second t: simulator book (own orders since the last reset) vs real book (real orders strictly before t); measured BEFORE the simulator decides at t, so same-second orders cannot count as drift
        feed.set_time(t) if hasattr(feed, 'set_time') else setattr(feed, 't', float(t)); n0 = len(eng.orders); eng.step()               # the simulator decides at t knowing only real orders strictly before t
        for o in eng.orders[n0:]:
            k = (o.right, o.strike); redo = False
            if o.role == 'stop_buyback':
                epoch_stops[k] = epoch_stops.get(k, 0) + o.lots
                if pool.get(k, 0) >= o.lots: pool[k] -= o.lots; redo = True
            flags.append(redo)
        if rows:
            for r in rows:
                apply_real(shadow, r)
                if variant == 'memory':
                    if r['role'] == 'open_short': eng.last_sale_price[r['cp']] = float(r['px'])
                    if r['module'] == 'num' and (r['role'] in BODY_ROLES or (r['role'] == 'open_long' and minute_index(r['t']) <= 3)): eng._note_body(float(t))
            for k in set(epoch_stops) | set(pool):
                real_s = len(shadow.shorts.get(k, [])); sim_s = len(eng.book.shorts.get(k, [])); undone = min(epoch_stops.get(k, 0), max(real_s - sim_s, 0)); pool[k] = min(pool.get(k, 0) + undone, real_s)
            epoch_stops = {}
            eng.book.restore(shadow.snapshot())                                           # reconcile the portfolio book (shorts with entry prices, wings, lump) to the real book
        t += 1
    eng.tfe_redecision = flags
    return eng, drift, shadow

# ------------------------------------------------------------------------------------------------------------------ the 32-cycle run
def real_rows_of(REAL, und, expiry):
    z = REAL[(REAL.und == und) & (REAL.expiry == expiry)]
    return [dict(t=int(a), row=int(b), cp=c, strike=float(d), side=e, lots=int(f), role=g, module=h, px=float(p)) for a, b, c, d, e, f, g, h, p in zip(z.t_first, z.row, z.cp, z.strike, z.side, z.lots, z.role, z.module, z.px_avg)]

def run_cycle_tfe(args):
    i, variant = args
    import validate_engine as V, bl_fr_sim as S
    r = V.CY.iloc[i]; d = S.prep(i); o = S.OH[(r.und, r.expiry)]; op = d['op']
    feed = ReplayFeed(o.open.values, o.high.values, o.low.values, o.close.values, d['K'], {k: v for k, v in op.items() if isinstance(k, tuple)})
    cfg = config_for(r.und, r.d1, order_split=ENGINE_CONVENTION); eng = D1Engine(cfg, feed, PaperBroker(feed))
    eng, drift, shadow = run_teacher_forced(eng, feed, real_rows_of(S.REAL, r.und, r.expiry), variant)
    df = eng.orders_frame()
    if len(df): df['redecision'] = eng.tfe_redecision
    if len(df): df['cls'] = df.role.map(V.ROLE2CLS); df['cid'] = i; df['cp'] = df.right; df['j'] = df.minute; df['step'] = cfg.strike_step
    dr = pd.DataFrame(drift); dr['cyc'] = f'{r.und}|{r.expiry}'; rej = [(f'{r.und}|{r.expiry}', q.role, why, q.lots) for q, why in eng.rejected]
    return i, df, rej, dr

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def build_sim_flagged(B, ORD, CY):
    """B.build_sim plus the redecision flag (aligned through the same stable sort by ts)"""
    rows = []
    for i, df in ORD.items():
        if not len(df): continue
        r = CY.iloc[i]; d = df.sort_values('ts', kind='stable').reset_index(drop=True)
        rows.append(pd.DataFrame(dict(cyc=f'{r.und}|{r.expiry}', day=0, cp=d.cp, side=d.side.str.lower(), strike=d.strike, lots=d.lots, t=d.ts, seq=np.arange(len(d)), cls=d.cls, validity=d.validity, module=d.module, role=d.role, t_resolution=np.where(d.role.isin(B.SECOND_ROLES), 'second', 'minute'), redecision=d.redecision.astype(bool))))
    return pd.concat(rows, ignore_index=True)

def write_runs(B, Q, V_, OD, rec, sim, real, attrs, drift, note):
    NA = ('state_after_matched', 'checkpoints', 'state_summary', 'per_cycle_state_error'); os.makedirs(OD, exist_ok=True)
    for nm, R in V_.items():
        d = f'{OD}/{nm}'; os.makedirs(d, exist_ok=True)
        for k, v in R.items():
            if isinstance(v, pd.DataFrame) and not k.startswith('_') and k not in NA: v.to_csv(f'{d}/{k}.csv', index=False)
        for k, v in R['unmatched'].items():
            if isinstance(v, pd.DataFrame): v.to_csv(f'{d}/unmatched_{k}.csv', index=False)
        R['_pairs'].to_csv(f'{d}/pairs.csv', index=False)
        json.dump(B.jsonable({k: v for k, v in R.items() if k not in ('per_cycle', 'unmatched') and k not in NA}), open(f'{d}/report.json', 'w'), indent=1)
        open(f'{d}/STATE_TABLES_NOT_APPLICABLE.txt', 'w').write('In TF-E the simulator portfolio book is forced to the real book after every real order, so state tables computed from cumulative simulated orders do not describe the simulator state. They are dropped; see ../pre_reset_drift.csv.\n')
    sim.to_csv(f'{OD}/sim_orders.csv', index=False); real.to_csv(f'{OD}/real_orders.csv', index=False); attrs.to_csv(f'{OD}/cycle_attributes.csv', index=False); drift.to_csv(f'{OD}/pre_reset_drift.csv', index=False)
    json.dump(dict(rec, treatment_note=note), open(f'{OD}/run_record.json', 'w'), indent=1)

if __name__ == '__main__':
    variant = sys.argv[1] if len(sys.argv) > 1 else 'book'; assert variant in ('book', 'memory')
    import validate_engine as V, bl_fr_sim as S, bl_common, bl_oscore as Q, bl_score_d1_F as B
    OUT = bl_common.OUT; tag = 'TFE' if variant == 'book' else 'TFE_m'; t0 = time.time(); CY = S.CY
    with Pool(max(1, min(8, os.cpu_count() or 1))) as p: res = p.map(run_cycle_tfe, [(i, variant) for i in range(len(CY))])
    ORD = {i: df for i, df, _, _ in res}; REJ = pd.DataFrame([x for _, _, rj, _ in res for x in rj], columns=['cyc', 'role', 'why', 'lots']); drift = pd.concat([d for *_, d in res], ignore_index=True)
    sim = build_sim_flagged(B, ORD, CY); real = B.build_real(CY); attrs = B.build_attrs(CY); first = sim[~sim.redecision].reset_index(drop=True)
    leg = Q.legacy_d1_scores(ORD, CY, S.REAL, bl_common.ref.STEP).set_index('cls').loc['ALL']
    dd = drift.assign(l1_norm=drift.l1 / drift.gross_real.clip(lower=1)); sl_equal = ((drift.S_sim_CE == drift.S_real_CE) & (drift.S_sim_PE == drift.S_real_PE) & (drift.L_sim_CE == drift.L_real_CE) & (drift.L_sim_PE == drift.L_real_PE))
    rec = dict(Q.spec_record(), mode='TF-E', tfe_variant=variant, order_split=ENGINE_CONVENTION, evidence_label='historical reproduction', diagnostic_only=True, never_a_primary_score_or_closure_gate=True, plan='reports/D1_TFE_PLAN.md',
               simulator='d1_strategy/d1_algo (unchanged engine) + bl_tfe.run_teacher_forced', real_orders=int(len(real)), engine_orders_all=int(len(sim)), engine_orders_first_decision=int(len(first)), redecision_orders=int(sim.redecision.sum()), redecision_by_role=sim[sim.redecision].role.value_counts().to_dict(),
               rejected_orders=int(len(REJ)), rejected_by_role_reason={f'{a}|{b}': int(n) for (a, b), n in REJ.groupby(['role', 'why']).size().items()}, rejected_by_cycle=REJ.groupby('cyc').size().to_dict(), legacy_lot_level_F1_info_only_all_orders=float(leg.F1),
               reset_events=int(len(drift)), pre_reset_SL_equal_share=float(sl_equal.mean()), pre_reset_l1_norm_median=float(dd.l1_norm.median()), pre_reset_l1_norm_mean=float(dd.l1_norm.mean()), pre_reset_zero_l1_share=float((drift.l1 == 0).mean()),
               bl_tfe_sha256=sha(os.path.abspath(__file__)), engine_sha256=sha('../../../../d1_strategy/d1_algo/engine.py'), risk_sha256=sha('../../../../d1_strategy/d1_algo/risk.py'), data_cache=sha(f'{OUT}/bl_d1eng_orders.pkl.gz'), run_at=datetime.datetime.utcnow().isoformat() + 'Z')
    os.makedirs(f'{OUT}/scoring/d1_{tag}_v2_onelot', exist_ok=True); pd.to_pickle(ORD, f'{OUT}/scoring/d1_{tag}_v2_onelot/engine_orders_{ENGINE_CONVENTION}.pkl.gz'); REJ.to_csv(f'{OUT}/scoring/d1_{tag}_v2_onelot/rejected_orders.csv', index=False)
    V_all = Q.variants(real, sim.drop(columns=['redecision']), attrs, 'TF-E', 'historical reproduction', bootstrap=2000); write_runs(B, Q, V_all, f'{OUT}/scoring/d1_{tag}_v2_onelot', dict(rec, treatment='all simulated orders (pre-registered definition)'), sim, real, attrs, drift, 'pre-registered: every simulated order is scored')
    V_first = Q.variants(real, first.drop(columns=['redecision']), attrs, 'TF-E', 'historical reproduction', bootstrap=2000); write_runs(B, Q, V_first, f'{OUT}/scoring/d1_{tag}_first_v2_onelot', dict(rec, treatment='first decisions only (POST HOC, plan Addendum 2)'), first, real, attrs, drift, 'POST HOC (added after seeing the first run): re-decision stop buy-backs removed from the simulated stream; same simulation as the pre-registered run')
    rec['seconds'] = round(time.time() - t0); print(json.dumps(rec, indent=1))
    for nm, V_ in (('ALL ORDERS (pre-registered)', V_all), ('FIRST DECISIONS (post hoc)', V_first)): print('\n' + nm); print(V_['all']['tiers'].round(4).to_string(index=False)); print(V_['all']['strictness'].query('level in [\'keys\',\'lots_exact\']').round(4).to_string(index=False))
