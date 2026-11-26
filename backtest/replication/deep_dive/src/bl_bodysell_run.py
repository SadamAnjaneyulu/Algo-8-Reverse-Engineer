"""Driver: body-sell mismatch ledger on the accepted F run (plan reports/BODY_SELL_MISMATCH_PLAN.md). Writes outputs/bodysell/. No engine change, no fitting, no P&L."""
import sys, os, json, time, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
from multiprocessing import Pool
import numpy as np, pandas as pd
import bl_bodysell_ledger as L

def probe_cycle(args):
    """replay one cycle with the accepted engine (one_lot_v2) and record the engine view at the requested seconds; also returns the engine's body-sell count for an integrity check"""
    i, secs = args
    import validate_engine as V, bl_fr_sim as S
    from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker
    from d1_algo.models import SESSION_OPEN_S, minute_index
    r = V.CY.iloc[i]; d = S.prep(i); o = S.OH[(r.und, r.expiry)]; op = d['op']
    feed = ReplayFeed(o.open.values, o.high.values, o.low.values, o.close.values, d['K'], {k: v for k, v in op.items() if isinstance(k, tuple)})
    cfg = config_for(r.und, r.d1, order_split='one_lot_v2'); eng = D1Engine(cfg, feed, PaperBroker(feed)); st = cfg.strike_step * cfg.ladder_step; views = {}; secs = set(int(x) for x in secs)
    for t in range(int(SESSION_OPEN_S), int(SESSION_OPEN_S + 390 * 60) + 1):
        feed.set_time(t); eng.step()
        if t in secs:
            j = minute_index(t); sb = eng.spot_bars; lo, hi = max(j - cfg.ladder_gate_min, 0), j; v = dict(spot=float(sb.cur_close), minute=int(j))
            for right in ('CE', 'PE'):
                ref = eng.ladder_ref[right]; live = ref is not None and j >= eng.ladder_from[right]
                if ref is None or sb.completed() < 1: v[f'ref_{right}'] = None; v[f'gap_{right}'] = None; v[f'newext_{right}'] = None; v[f'live_{right}'] = False; continue
                if right == 'CE': v[f'gap_{right}'] = float(sb.cur_low - (ref - st)); v[f'newext_{right}'] = bool(sb.cur_low < min(sb.low[lo:hi])) if hi > lo else None
                else: v[f'gap_{right}'] = float((ref + st) - sb.cur_high); v[f'newext_{right}'] = bool(sb.cur_high > max(sb.high[lo:hi])) if hi > lo else None
                v[f'ref_{right}'] = float(ref); v[f'live_{right}'] = bool(live)
            b0 = ((SESSION_OPEN_S + 60 * j) // 1800) * 1800; ch = eng._channel(b0); v['in_breakout_window'] = bool(cfg.breakout_start_min <= j <= cfg.breakout_end_min)
            if ch is not None: top, bot = ch; v['ch_top'] = float(top); v['ch_bottom'] = float(bot); v['above_top_steps'] = float((sb.cur_close - top) / cfg.strike_step); v['below_bottom_steps'] = float((bot - sb.cur_close) / cfg.strike_step)
            else: v['ch_top'] = v['ch_bottom'] = v['above_top_steps'] = v['below_bottom_steps'] = None
            fired = [s for s in cfg.timetable if SESSION_OPEN_S + 60 + s <= t]; v['secs_since_wave'] = float(t - (SESSION_OPEN_S + 60 + max(fired))) if fired else None
            views[t] = v
    df = eng.orders_frame(); return i, views, int(len(eng.orders)), int(((df.role.isin(['scheduled_straddle', 'breakout_straddle', 'breakout_extra', 'ladder_solo'])) & (df.side == 'SELL')).sum()) if len(df) else 0

def main():
    import bl_common, bl_oscore as Q, bl_fr_sim as S
    from d1_algo.config import SCHEDULE_A, SCHEDULE_B
    OUT = bl_common.OUT; F = f'{OUT}/scoring/d1_F_v2_onelot'; T = f'{OUT}/scoring/d1_TFE_first_v2_onelot'; OD = f'{OUT}/bodysell'; os.makedirs(OD, exist_ok=True); t0 = time.time()
    real = Q.prepare_real(pd.read_csv(f'{F}/real_orders.csv')); sim = Q.prepare_sim(pd.read_csv(f'{F}/sim_orders.csv')); pairs = pd.read_csv(f'{F}/all/pairs.csv'); tpairs = pd.read_csv(f'{T}/all/pairs.csv'); CY = S.CY
    tt = {f'{r.und}|{r.expiry}': (SCHEDULE_B if r.d1 >= '2026-09-16' else SCHEDULE_A) for r in CY.itertuples()}
    LR, LS, r_, s_ = L.build_ledgers(real, sim, pairs, tt)
    # ---- software verification (pre-set 1): reconciliation
    chk = {}
    chk['real_body_sells'] = int(len(LR)); chk['sim_body_sells'] = int(len(LS)); chk['real_missing'] = int((LR.category.str.startswith('M')).sum()); chk['sim_extra'] = int((LS.category.str.startswith('X')).sum())
    chk['every_real_has_one_status'] = bool(LR.category.notna().all()); chk['every_sim_has_one_status'] = bool(LS.category.notna().all())
    fcls = pd.read_csv(f'{F}/all/by_class.csv').set_index('cls'); chk['F_table_real_body_sell'] = int(fcls.loc['body_sell', 'real']); chk['F_table_sim_body_sell'] = int(fcls.loc['body_sell', 'sim'])
    mu = pd.read_csv(f'{F}/all/unmatched_missing_by_cls.csv').set_index('cls'); eu = pd.read_csv(f'{F}/all/unmatched_extra_by_cls.csv').set_index('cls'); chk['F_table_missing_body_sell'] = int(mu.loc['body_sell', 'orders']); chk['F_table_extra_body_sell'] = int(eu.loc['body_sell', 'orders'])
    chk['reconciles_to_F_tables'] = bool(chk['real_body_sells'] == chk['F_table_real_body_sell'] and chk['sim_body_sells'] == chk['F_table_sim_body_sell'] and chk['real_missing'] == chk['F_table_missing_body_sell'] and chk['sim_extra'] == chk['F_table_extra_body_sell'])
    m1 = LR[LR.category == 'M1']; chk['M1_with_unmatched_neighbour_(must_be_0)'] = int(sum(1 for ix, row in m1.iterrows() if not L._nearest(L._pool(s_, 'sec'), row.cyc, row.cp, int(row.t))[1]))
    # ---- persistence in TF-E (first decisions)
    tm = np.zeros(len(real), bool); tm[tpairs.ri.values] = True; LR['persistent_in_TFE'] = LR.index.map(lambda ix: bool(not tm[ix])) & LR.category.str.startswith('M')
    # ---- books before (real: log order; sim: (sec, seq)); cross books at the same second
    rb = L.books_before(r_, 't', ['t', 'row']); sb = L.books_before(s_, 'sec', ['sec', 'seq']); LR = LR.join(rb.add_prefix('real_before_')); LS = LS.join(sb.add_prefix('sim_before_'))
    cross = lambda df, other, tcol, pre: pd.DataFrame([dict(zip([f'{pre}_S_CE', f'{pre}_L_CE', f'{pre}_S_PE', f'{pre}_L_PE'], [*(lambda S_, L_: (S_['CE'], L_['CE'], S_['PE'], L_['PE']))(*L.book_at_second(other, ocol, row.cyc, int(row[tcol])))])) for _, row in df.iterrows()], index=df.index) if False else None
    def cross_books(df, tcol, other, ocol, pre):
        rows = []
        for _, row in df.iterrows():
            S_, L_ = L.book_at_second(other, ocol, row.cyc, int(row[tcol])); rows.append((S_['CE'], L_['CE'], S_['PE'], L_['PE']))
        return pd.DataFrame(rows, columns=[f'{pre}_S_CE', f'{pre}_L_CE', f'{pre}_S_PE', f'{pre}_L_PE'], index=df.index)
    LR = LR.join(cross_books(LR, 't', s_, 'sec', 'sim_before')); LS = LS.join(cross_books(LS, 'sec', r_, 't', 'real_before'))
    # ---- spot and engine view from a probe replay (same engine and convention as F)
    cyc_ix = {f'{r.und}|{r.expiry}': i for i, r in enumerate(CY.itertuples())}; need = {i: set() for i in range(len(CY))}
    for _, row in LR.iterrows(): need[cyc_ix[row.cyc]].add(int(row.t))
    for _, row in LS.iterrows(): need[cyc_ix[row.cyc]].add(int(row.sec))
    with Pool(max(1, min(8, os.cpu_count() or 1))) as p: pr = p.map(probe_cycle, [(i, sorted(need[i])) for i in range(len(CY))])
    views = {i: v for i, v, _, _ in pr}; sim_cycle_counts = pd.Series({f'{CY.iloc[i].und}|{CY.iloc[i].expiry}': n for i, _, _, n in pr}); chk['probe_body_sell_orders'] = int(sim_cycle_counts.sum()); chk['probe_equals_F_simulated_body_sells'] = bool(chk['probe_body_sell_orders'] == chk['sim_body_sells'])
    def attach(df, tcol):
        rows = [views[cyc_ix[row.cyc]].get(int(row[tcol]), {}) for _, row in df.iterrows()]; V_ = pd.DataFrame(rows, index=df.index).add_prefix('eng_'); return df.join(V_)
    LR = attach(LR, 't'); LS = attach(LS, 'sec')
    LR['minute'] = ((LR.t - L.OPEN_S) // 60).astype(int); LS['minute'] = ((LS.sec - L.OPEN_S) // 60).astype(int)
    LR.to_csv(f'{OD}/ledger_real.csv', index=False); LS.to_csv(f'{OD}/ledger_sim.csv', index=False)
    # ---- tables
    R = {}; mis = LR[LR.category.str.startswith('M')]; R['checks'] = chk
    R['missing_by_category'] = mis.groupby('category').agg(orders=('t', 'size'), persistent_in_TFE=('persistent_in_TFE', 'sum')).reset_index().assign(share=lambda d: d.orders / d.orders.sum(), meaning=lambda d: d.category.map(L.MISS_CATS)).round(4).to_dict('records')
    R['missing_total'] = dict(orders=int(len(mis)), persistent_in_TFE=int(mis.persistent_in_TFE.sum()), recovered_by_TFE=int((~mis.persistent_in_TFE).sum()))
    R['missing_by_category_x_module'] = pd.crosstab(mis.category, mis.inferred_module).reset_index().to_dict('records'); R['missing_by_category_x_late'] = pd.crosstab(mis.category, mis.late).reset_index().to_dict('records')
    R['missing_M4_by_module_x_late'] = pd.crosstab(mis[mis.category == 'M4'].inferred_module, mis[mis.category == 'M4'].late).reset_index().to_dict('records')
    R['missing_by_cp_x_category'] = pd.crosstab(mis.cp, mis.category).reset_index().to_dict('records')
    R['missing_by_hour'] = pd.crosstab((mis.minute // 60 + 9 + (mis.minute % 60 + 15) // 60), mis.category).reset_index().rename(columns={0: 'hour'}).to_dict('records')
    R['M1_holder_role'] = mis[mis.category == 'M1'].nearest_sim_role.value_counts().rename_axis('role').reset_index(name='orders').to_dict('records'); R['M1_nearest_dist_quantiles'] = mis[mis.category == 'M1'].nearest_sim_dist.quantile([.1, .25, .5, .75, .9]).round(1).to_dict()
    R['M3_nearest_dist_quantiles'] = mis[mis.category == 'M3'].nearest_sim_dist.quantile([.1, .25, .5, .75, .9]).round(1).to_dict(); R['M3_nearest_sim_role'] = mis[mis.category == 'M3'].nearest_sim_role.value_counts().rename_axis('role').reset_index(name='orders').to_dict('records')
    m4s = mis[(mis.category == 'M4') & (mis.inferred_module == 'solo')]; R['M4_solo_engine_gap_quantiles_points'] = {k: m4s[f'eng_gap_{k}'].dropna().quantile([.1, .25, .5, .75, .9]).round(2).to_dict() for k in ('CE', 'PE')} if len(m4s) else {}
    R['M4_solo_engine_view'] = dict(n=int(len(m4s)), ladder_live_share=float(np.nanmean([m4s.apply(lambda r: bool(r[f'eng_live_{r.cp}']), axis=1).mean()])) if len(m4s) else None, new_extreme_share=float(m4s.apply(lambda r: bool(r[f'eng_newext_{r.cp}']) if r[f'eng_newext_{r.cp}'] is not None else False, axis=1).mean()) if len(m4s) else None)
    pcyc = mis.groupby('cyc').size().sort_values(ascending=False); R['missing_cycle_concentration'] = dict(top5=pcyc.head(5).to_dict(), share_top5=float(pcyc.head(5).sum() / pcyc.sum()), per_cycle_median=float(pcyc.median()), cycles=int(len(pcyc)))
    R['missing_state_before'] = dict(real_short_lots_median=float(mis[['real_before_S_CE', 'real_before_S_PE']].sum(axis=1).median()), sim_short_lots_median=float(mis[['sim_before_S_CE', 'sim_before_S_PE']].sum(axis=1).median()), median_abs_diff_shorts=float((mis[['real_before_S_CE', 'real_before_S_PE']].sum(axis=1) - mis[['sim_before_S_CE', 'sim_before_S_PE']].sum(axis=1)).abs().median()))
    ext = LS[LS.category.str.startswith('X')]; R['extra_by_category'] = ext.groupby('category').size().reset_index(name='orders').assign(share=lambda d: d.orders / d.orders.sum(), meaning=lambda d: d.category.map(L.EXTRA_CATS)).round(4).to_dict('records')
    R['extra_by_role_x_category'] = pd.crosstab(ext.role, ext.category).reset_index().to_dict('records'); R['extra_by_late'] = pd.crosstab(ext.category, ext.late).reset_index().to_dict('records')
    R['sim_body_sells_by_role'] = LS.groupby('role').agg(orders=('sec', 'size'), matched=('m', 'sum')).assign(extra=lambda d: d.orders - d.matched).reset_index().to_dict('records')
    mt = LR[LR.m].copy(); mt['partner_role'] = mt.partner.map(s_.role); mt['partner_cls'] = mt.partner.map(s_.cls); mt['abs_dstrike'] = mt.dstrike.abs()
    R['matched_detail_by_partner_role'] = mt.groupby('partner_role').agg(orders=('t', 'size'), exact_second=('tier', lambda x: float((x == 0).mean())), near=('tier', lambda x: float((x == 1).mean())), broad=('tier', lambda x: float((x == 2).mean())), strike_exact=('abs_dstrike', lambda x: float((x == 0).mean())), strike_1=('abs_dstrike', lambda x: float((x == 1).mean())), strike_2plus=('abs_dstrike', lambda x: float((x >= 2).mean())), lots_exact=('dlots', lambda x: float((x == 0).mean()))).reset_index().round(3).to_dict('records')
    R['matched_detail_all'] = dict(orders=int(len(mt)), strike_exact=float((mt.abs_dstrike == 0).mean()), strike_1=float((mt.abs_dstrike == 1).mean()), strike_2plus=float((mt.abs_dstrike >= 2).mean()), strike_wrong=int((mt.abs_dstrike >= 1).sum()), lots_exact=float((mt.dlots == 0).mean()), lots_wrong=int((mt.dlots != 0).sum()), partner_cls=mt.partner_cls.value_counts().to_dict())
    R['matched_strike_wrong_by_module_late'] = mt[mt.abs_dstrike >= 1].assign(late=lambda d: d.t >= L.OPEN_S + 345 * 60).groupby(['partner_role', 'late']).size().reset_index(name='orders').to_dict('records')
    def jsonable(o):
        if isinstance(o, dict): return {str(k): jsonable(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [jsonable(v) for v in o]
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.floating,)): return None if np.isnan(o) else float(o)
        if isinstance(o, (np.bool_,)): return bool(o)
        if isinstance(o, float) and np.isnan(o): return None
        return o
    R['seconds'] = round(time.time() - t0); json.dump(jsonable(R), open(f'{OD}/breakdown.json', 'w'), indent=1)
    # ---- examples: up to 3 per category from distinct cycles, earliest first
    cols_r = ['cyc', 't', 'cp', 'strike', 'lots', 'category', 'inferred_module', 'nearest_sim_dist', 'nearest_sim_role', 'persistent_in_TFE', 'real_before_S_CE', 'real_before_S_PE', 'sim_before_S_CE', 'sim_before_S_PE', 'eng_spot', 'eng_gap_CE', 'eng_gap_PE', 'eng_above_top_steps', 'eng_below_bottom_steps', 'eng_secs_since_wave']
    ex = []
    for c in ('M1', 'M2', 'M3', 'M4'):
        z = LR[LR.category == c].sort_values(['cyc', 't']).drop_duplicates('cyc'); ex.append(z.head(3)[cols_r])
    pd.concat(ex).to_csv(f'{OD}/examples_missing.csv', index=False)
    exs = []
    for c in ('X1', 'X2', 'X3', 'X4'):
        z = LS[LS.category == c].sort_values(['cyc', 'sec']).drop_duplicates('cyc'); exs.append(z.head(3))
    pd.concat(exs).to_csv(f'{OD}/examples_extra.csv', index=False)
    print(json.dumps(jsonable({k: R[k] for k in ('checks', 'missing_total', 'missing_by_category', 'extra_by_category')}), indent=1)); return R

if __name__ == '__main__': main()
