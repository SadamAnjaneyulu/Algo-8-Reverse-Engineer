"""TP-02 Phase 1-3 summaries: mechanism attribution, clock, expiry, replacement, basket, populations, reconciliation, confidence.
python3 tp_reconstruction/tp02/scripts/analyze_mechanisms.py  (needs ALGO8_MARKET_DIR for the strike-migration part)
Registered flag rates are always shown next to a chance baseline (time-shift null for association flags, exposure share for calendar flags)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp02_common as c
CFG = c.CFG; A = c.ANALYSIS
FLAGS = ['flag_clock', 'flag_expiry_mgmt', 'flag_replacement', 'flag_replacement_strict', 'flag_wing_module', 'flag_wing_linked', 'flag_wing_linked_strict', 'flag_basket']


def load():
    T = pd.read_parquet(os.path.join(c.DATA, 'exit_event_mechanisms.parquet')); T['cycle'] = T.und + '|' + T.expiry.dt.strftime('%Y-%m-%d')
    return T


# ------------------------------------------------------------------ chance baselines
class Null:
    def __init__(self, L, R):
        Rf = R[R.method == 'FIFO'].merge(L[['src_row', 'und', 'cp', 'parent_oid', 'date']], on='src_row')
        mk = lambda d: {u: g.sort_values('epoch') for u, g in d.groupby('und')}
        self.OS = mk(Rf[(Rf.open_qty > 0) & (Rf.sgn < 0)]); self.CL = mk(Rf[(Rf.close_qty > 0) & (Rf.inventory_before > 0)]); self.CS = mk(Rf[(Rf.close_qty > 0) & (Rf.inventory_before < 0)])
        self.reg = set(pd.read_csv(os.path.join(c.REPO, CFG['inputs']['clock_clusters'])).query('is_cluster').key)

    def rates(self, T, shifts):
        rw = CFG['replacement']['window_seconds']; ww = CFG['wing']['link_window_seconds']; bw = CFG['basket']['window_seconds']; out = {k: [] for k in ('replacement', 'wing', 'basket')}
        S = T[T.direction == -1]
        for sh in shifts:
            for u, g in S.groupby('und'):
                os_, cl, cs = self.OS[u], self.CL[u], self.CS[u]; eo, ec, es = os_.epoch.values, cl.epoch.values, cs.epoch.values
                t = g.epoch.values + sh; tod = ((pd.to_datetime(t + c.IST_S, unit='s') - g.date.values).total_seconds() // 60 - 555) if False else (t - g.epoch.values + (g.t_exec - g.date).dt.total_seconds().values) // 60 - 555
                ok = (tod >= 0) & (tod < 375)
                for i in np.where(ok)[0]:
                    r = g.iloc[i]; ti = t[i]
                    s = os_.iloc[np.searchsorted(eo, ti, 'right'):np.searchsorted(eo, ti + rw, 'right')]; out['replacement'].append(bool(((s.cp == r.cp) & (s.parent_oid != r.parent_oid)).any()))
                    s = cl.iloc[np.searchsorted(ec, ti - ww, 'left'):np.searchsorted(ec, ti + ww, 'right')]; out['wing'].append(bool(((s.cp == r.cp) & (s.parent_oid != r.parent_oid)).any()) if r.module == 'num' else False)
                    s = cs.iloc[np.searchsorted(es, ti - bw, 'left'):np.searchsorted(es, ti + bw, 'right')]; s = s[(s.parent_oid != r.parent_oid) & (s.contract_id != r.contract_id)]; out['basket'].append(s.contract_id.nunique() >= CFG['basket']['min_other_contracts'])
        return {k: float(np.mean(v)) for k, v in out.items()}


def exposure_shares(panel, reg):
    """share of exposed short-inventory minutes at registered clock minutes and in expiry-management phases (the chance share for calendar flags)"""
    p = panel.copy(); p['date'] = pd.to_datetime(p.date); p['expiry'] = pd.to_datetime(p.expiry); m = 555 + p.tod_min
    hhmm = (m // 60).astype(int).astype(str).str.zfill(2) + ':' + (m % 60).astype(int).astype(str).str.zfill(2); phase = c.phase_of(m.values)
    em = CFG['expiry']['expiry_management_flag']
    return dict(clock=float(hhmm.isin(reg).mean()), expiry=float(((p.date == p.expiry).values & np.isin(phase, em['phases'])).mean()), rows=len(p))


# ------------------------------------------------------------------ summaries
def mechanism_tables(T, null, expo):
    short = T[T.direction == -1]; pops = {'short closings (all)': short, 'short, stable PROFIT': short[short.pop1_profit_stable], 'short body, stable PROFIT, clean non-stop (Pop 3)': short[short.pop3_clean_nonstop],
                                          'short, stable PROFIT, stop-related (Pop 2 ∩ profit)': short[short.pop1_profit_stable & short.pop2_stop_related], 'long closings (wings and other)': T[T.direction == 1]}
    chance = null.rates(short, CFG['replacement']['null_shifts_seconds']); rows = []
    for name, d in pops.items():
        n = len(d); u = d.qty_closed.sum()
        def add(item, mask, chance_rate=np.nan, note=''):
            k = int(mask.sum()); rate = k / n if n else np.nan
            rows.append(dict(population=name, item=item, events=k, units=int(d.qty_closed[mask].sum()), share_of_events=rate, share_of_units=d.qty_closed[mask].sum() / u if u else np.nan, chance_rate=chance_rate,
                             excess_over_chance=rate - chance_rate if not np.isnan(chance_rate) else np.nan, cycles=d.cycle[mask].nunique(), note=note))
        add('STOP_CONFIRMED (module s_)', d.stop_class == 'STOP_CONFIRMED'); add('STOP_POSSIBLE', d.stop_class == 'STOP_POSSIBLE'); add('STOP_NOT_EVIDENCED', d.stop_class == 'STOP_NOT_EVIDENCED', note='not proof that no stop occurred')
        for s_ in CFG['stop']['adverse_ratio_sensitivity']: add(f'sensitivity: adverse premium >= {s_}x reference in the previous 15 min', d[f'stop_adverse_premium_{s_}'])
        add('  of which: inside a cycle-stop window', d.in_cycle_stop_window); add('  of which: adverse premium >= 1.25x', d.stop_adverse_premium); add('  of which: exit price >= 1.25x reference', d.stop_own_price)
        add('CLOCK (registered minute)', d.flag_clock, chance_rate=expo['clock'], note='chance = share of exposed short-inventory minutes at those minutes')
        add('EXPIRY_MGMT (expiry day, 14:30 onward)', d.flag_expiry_mgmt, chance_rate=expo['expiry'], note='chance = share of exposed minutes in those phases')
        add('REPLACEMENT (same right, <= 60 s, registered)', d.flag_replacement, chance_rate=chance['replacement'], note='chance = time-shift null')
        add('REPLACEMENT_STRICT (+ later order number, same units)', d.flag_replacement_strict, note='post-hoc sensitivity')
        add('WING_MODULE (h_)', d.flag_wing_module)
        add('WING_LINKED (wing closing same right, +-10 s, registered)', d.flag_wing_linked, chance_rate=chance['wing'] if name != 'long closings (wings and other)' else np.nan, note='chance = time-shift null (body closings only)')
        add('WING_LINKED_STRICT (+ same units)', d.flag_wing_linked_strict, note='post-hoc sensitivity')
        add('BASKET (>= 2 other contracts, +-5 s)', d.flag_basket, chance_rate=chance['basket'], note='chance = time-shift null; analysed in H4, not used to remove events')
        add('any registered non-stop flag', d.flag_clock | d.flag_expiry_mgmt | d.flag_replacement | d.flag_wing_linked | d.flag_wing_module)
        add('any strict non-stop flag', d.flag_clock | d.flag_expiry_mgmt | d.flag_replacement_strict | d.flag_wing_linked_strict | d.flag_wing_module)
        add('no registered flag at all (unexplained)', ~(d.flag_clock | d.flag_expiry_mgmt | d.flag_replacement | d.flag_wing_linked | d.flag_wing_module | (d.stop_class != 'STOP_NOT_EVIDENCED')))
    S = pd.DataFrame(rows); S.to_csv(os.path.join(A, 'mechanism_summary.csv'), index=False)
    # candidate mechanism distribution and confidence
    cm = short.groupby(['module', 'candidate_mechanism', 'confidence']).agg(events=('close_row', 'size'), units=('qty_closed', 'sum')).reset_index(); cm['share_of_short_events'] = cm.events / len(short)
    cm.to_csv(os.path.join(A, 'mechanism_confidence_summary.csv'), index=False)
    return S, chance, cm


def clock_tables(T):
    reg = sorted(pd.read_csv(os.path.join(c.REPO, CFG['inputs']['clock_clusters'])).query('is_cluster').key); rows = []
    S = T[T.direction == -1].copy(); S['sec'] = S.t_exec.dt.second
    for m in reg:
        d = S[S.exec_minute == m]; allm = T[T.exec_minute == m]
        for scope, g in [('ALL', d)] + [(f'und={u}', d[d.und == u]) for u in ('NIFTY', 'SENSEX')] + [(f'day={k}', d[d.day_type == k]) for k in ('EXPIRY_DAY', 'CARRY_DAY')] + [(f'module={k}', d[d.module == k]) for k in ('num', 's_', 'h_')]:
            if not len(g): continue
            rows.append(dict(minute=m, scope=scope, short_closings=len(g), all_closings=len(allm) if scope == 'ALL' else np.nan, cycles=g.cycle.nunique() if 'cycle' in g else np.nan, share_expiry_day=(g.day_type == 'EXPIRY_DAY').mean(), share_body_module=(g.module == 'num').mean(),
                             share_stop_class_confirmed_or_possible=g.stop_class.isin(['STOP_CONFIRMED', 'STOP_POSSIBLE']).mean(), share_stable_profit=g.pop1_profit_stable.mean(), median_second=g.sec.median(), q25_second=g.sec.quantile(.25), q75_second=g.sec.quantile(.75),
                             median_lots_closed=g.exit_qty_lots.median(), median_position_lots_before=g.inventory_before_lots.median(), share_closing_whole_position=(g.exit_type != 'PARTIAL').mean(),
                             median_other_contracts_within_10s=g.n_C_short_other_contracts_pm30s.median(), share_with_ge3_other_contracts_within_30s=(g.n_C_short_other_contracts_pm30s >= 3).mean()))
    CS = pd.DataFrame(rows); CS.to_csv(os.path.join(A, 'clock_mechanism_summary.csv'), index=False)
    # minute-of-hour structure of body short closings (15-minute grid): residue = minute % 15
    B = S[(S.module == 'num')].copy(); B['res15'] = B.t_exec.dt.minute % 15; B['hour'] = B.t_exec.dt.hour
    R = B.groupby(['day_type', 'res15']).agg(events=('close_row', 'size'), stable_profit=('pop1_profit_stable', 'sum')).reset_index(); R['share_within_day_type'] = R.events / R.groupby('day_type').events.transform('sum')
    R.to_csv(os.path.join(A, 'clock_minute_of_15_structure.csv'), index=False)
    return CS, R


def expiry_tables(T):
    S = T[T.direction == -1]
    X = S.groupby(['expiry_category', 'module']).agg(events=('close_row', 'size'), units=('qty_closed', 'sum'), stable_profit=('pop1_profit_stable', 'sum'), stable_loss=('consensus_label', lambda s: (s == 'LOSS').sum()), cycles=('cycle', 'nunique')).reset_index()
    X['share_of_short_events'] = X.events / len(S); X['share_stable_profit'] = X.stable_profit / X.events
    X.to_csv(os.path.join(A, 'expiry_exit_summary.csv'), index=False); return X


def replacement_tables(T):
    S = T[T.direction == -1].copy(); rows = []
    for w in c.WINDOWS:
        for rel, col in (('same_contract', f'n_O_short_same_contract_next{w}s'), ('same_right_other_strike', f'n_O_short_same_right_other_strike_next{w}s'), ('opposite_right', f'n_O_short_opposite_right_next{w}s')):
            for scope, g in [('all short', S), ('stable PROFIT short', S[S.pop1_profit_stable]), ('Pop 3', S[S.pop3_clean_nonstop])]:
                rows.append(dict(window_s=w, relation=rel, population=scope, events=len(g), share_followed=(g[col] > 0).mean(), mean_openings=g[col].mean()))
    R = pd.DataFrame(rows)
    f = S[S.first_open_relation.notna() & (S.first_open_dt_s <= 60)].copy(); f['qty_relation'] = np.where(f.first_open_units == f.qty_closed, 'same units', np.where(f.first_open_units > f.qty_closed, 'more units', 'fewer units'))
    D = f.groupby(['first_open_relation', 'qty_relation', 'first_open_sequence_evidence']).agg(events=('close_row', 'size'), median_dt_s=('first_open_dt_s', 'median'), stable_profit_share=('pop1_profit_stable', 'mean')).reset_index()
    R.to_csv(os.path.join(A, 'replacement_sequence_summary.csv'), index=False); D.to_csv(os.path.join(A, 'replacement_sequence_detail.csv'), index=False); return R, D


def basket_tables(T):
    S = T[T.direction == -1].copy(); S['basket_bin'] = pd.cut(S.basket_other_contracts, [-1, 0, 1, 2, 4, 9, 1000], labels=['0', '1', '2', '3-4', '5-9', '10+'])
    B = S.groupby('basket_bin', observed=True).agg(events=('close_row', 'size'), stable_profit_share=('pop1_profit_stable', 'mean'), both_rights_share=('basket_both_rights', 'mean'), loss_leg_share=('basket_has_loss_leg', 'mean'), stop_class_possible_or_confirmed=('pop2_stop_related', 'mean')).reset_index()
    B.to_csv(os.path.join(A, 'basket_exit_summary.csv'), index=False); return B


def population_tables(T):
    S = T[T.direction == -1]; rows = []
    for name, m in [('Pop1 stable PROFIT short', S.pop1_profit_stable), ('Pop1b convention-sensitive PROFIT short', S.profit_class == 'SENSITIVE_PROFIT'), ('Pop2 stop-related short', S.pop2_stop_related), ('Pop2 ∩ stable profit', S.pop2_stop_related & S.pop1_profit_stable),
                    ('Pop3 clean profitable non-stop body', S.pop3_clean_nonstop), ('Pop4 unexplained (registered flags)', S.pop4_unexplained_body), ('Pop4S unexplained (strict flags)', S.pop4s_unexplained_strict)]:
        d = S[m]; rows.append(dict(population=name, events=len(d), units=int(d.qty_closed.sum()), lots=round(d.exit_qty_lots.sum(), 1), nifty=int((d.und == 'NIFTY').sum()), sensex=int((d.und == 'SENSEX').sum()), cycles=d.cycle.nunique(), expiry_day_share=(d.day_type == 'EXPIRY_DAY').mean() if len(d) else np.nan,
                                  gross_pnl_FIFO=round(d.pnl_rupees_FIFO.sum(), 1), gross_pnl_LIFO=round(d.pnl_rupees_LIFO.sum(), 1), gross_pnl_AVG=round(d.pnl_rupees_AVG.sum(), 1)))
    P = pd.DataFrame(rows); P.to_csv(os.path.join(A, 'profitable_nonstop_summary.csv'), index=False)
    # by-convention sensitivity: PROFIT under each convention
    rows = []
    for m in c.METHODS:
        d = S[S[f'label_{m}'] == 'PROFIT']; n3 = d[(d.module == 'num') & (d.stop_class == 'STOP_NOT_EVIDENCED') & ~d.order_ambiguous & ~d.dq_flag_any]
        rows.append(dict(convention=m, profit_short_closings=len(d), stop_confirmed=int((d.stop_class == 'STOP_CONFIRMED').sum()), stop_possible=int((d.stop_class == 'STOP_POSSIBLE').sum()), clean_nonstop_body=len(n3),
                         clean_nonstop_unexplained_registered=int((~(n3.flag_clock | n3.flag_expiry_mgmt | n3.flag_replacement | n3.flag_wing_linked)).sum()), clean_nonstop_unexplained_strict=int((~(n3.flag_clock | n3.flag_expiry_mgmt | n3.flag_replacement_strict | n3.flag_wing_linked_strict)).sum())))
    P2 = pd.DataFrame(rows); P2.to_csv(os.path.join(A, 'profitable_by_convention_summary.csv'), index=False); return P, P2


def reconcile(T):
    """counts and quantities must reconcile with TP-01"""
    E = c.tp01('exit_events.parquet'); X = c.tp01('exit_event_consensus.parquet'); f = E[E.method == 'FIFO']
    rows = [dict(check='closing fills', tp01=len(X), tp02=len(T)), dict(check='closed units', tp01=int(X.qty_closed.sum()), tp02=int(T.qty_closed.sum())),
            dict(check='short closing fills', tp01=int((f.direction == -1).sum()), tp02=int((T.direction == -1).sum())), dict(check='long closing fills', tp01=int((f.direction == 1).sum()), tp02=int((T.direction == 1).sum()))]
    for m in c.METHODS:
        for lab in ('PROFIT', 'LOSS', 'BREAKEVEN', 'UNRESOLVED'): rows.append(dict(check=f'{m} {lab} closing fills', tp01=int((E[E.method == m].label == lab).sum()), tp02=int((T[f'label_{m}'] == lab).sum())))
    for mod in ('num', 'h_', 's_', 'v_', 'm_'): rows.append(dict(check=f'module {mod} closing fills', tp01=int((f.module == mod).sum()), tp02=int((T.module == mod).sum())))
    rows.append(dict(check='candidate_mechanism assigned to every closing fill', tp01=len(T), tp02=int(T.candidate_mechanism.notna().sum())))
    rows.append(dict(check='stop_class partitions closing fills (3 classes)', tp01=len(T), tp02=int(T.stop_class.isin(['STOP_CONFIRMED', 'STOP_POSSIBLE', 'STOP_NOT_EVIDENCED']).sum())))
    R = pd.DataFrame(rows); R['difference'] = R.tp02 - R.tp01; R.to_csv(os.path.join(c.DATA, 'mechanism_reconciliation.csv'), index=False); return R


def main():
    T = load(); L = c.tp01('fill_event_ledger.parquet'); R = c.tp01('fill_roles.parquet'); panel = c.tp01('short_exposure_panel.parquet')
    reg = set(pd.read_csv(os.path.join(c.REPO, CFG['inputs']['clock_clusters'])).query('is_cluster').key); expo = exposure_shares(panel, reg); null = Null(L, R)
    S, chance, cm = mechanism_tables(T, null, expo); clock_tables(T); expiry_tables(T); replacement_tables(T); basket_tables(T); P, P2 = population_tables(T); Rc = reconcile(T)
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 70); pd.set_option('display.max_rows', 200)
    print('chance', chance, expo); print(S[S.population == 'short closings (all)'][['item', 'events', 'share_of_events', 'chance_rate', 'excess_over_chance']].round(3).to_string(index=False))
    print(S[S.population.str.startswith('short body')][['item', 'events', 'share_of_events', 'chance_rate', 'excess_over_chance']].round(3).to_string(index=False)); print(P.to_string(index=False)); print(P2.to_string(index=False)); print(Rc[Rc['difference'] != 0])


if __name__ == '__main__':
    main()
