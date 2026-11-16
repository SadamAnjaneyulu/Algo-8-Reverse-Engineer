"""Run the risk-rule validation end to end and write every deliverable.  python3 risk_rule_validation/run_all.py  (about 2-3 minutes)"""
import os, time
import numpy as np, pandas as pd
from rr_common import RES, HERE, markets, cycle_keys, d_bounds, CARRY_PCT, EXPIRY_LIMIT
import phases

def main():
    t0 = time.time(); mk = markets()
    P1, AMB = phases.phase1(); P1.to_csv(os.path.join(RES, 'phase1_inventory_by_cycle.csv'), index=False); AMB.to_csv(os.path.join(RES, 'phase1_ownership_ambiguity.csv'), index=False)
    print(f'phase 1 done {time.time() - t0:.0f}s')
    S2, E2 = phases.phase2(); S2.to_csv(os.path.join(HERE, 'carry_forward_4pct_tests.csv'), index=False); E2.to_csv(os.path.join(RES, 'carry_forward_4pct_events.csv'), index=False)
    phases.phase2_placebo().to_csv(os.path.join(RES, 'carry_forward_placebo_ladder.csv'), index=False)
    print(f'phase 2 done {time.time() - t0:.0f}s')
    P3 = phases.phase3(); P3.to_csv(os.path.join(HERE, 'expiry_day_1pct_tests.csv'), index=False)
    print(f'phase 3 done {time.time() - t0:.0f}s')
    P4 = phases.phase4(); P4.to_csv(os.path.join(RES, 'cycle_stop_control.csv'), index=False)
    print(f'phase 4 done {time.time() - t0:.0f}s')
    # order-action matching: every threshold crossing with the actions that followed
    tm = lambda u, e, i: (mk[(u, pd.Timestamp(e))]['grid'][int(i)].strftime('%Y-%m-%d %H:%M') if pd.notna(i) else '')
    a = E2[E2.cross_minute.notna()].copy(); a['rule'] = '4 % carry-forward ' + a.definition
    a['cross_time'] = [tm(u, e, i) for u, e, i in zip(a.und, a.expiry, a.cross_minute)]
    a['first_action_time'] = [tm(u, e, i) if 'first_action_minute' in a and pd.notna(i) else '' for u, e, i in zip(a.und, a.expiry, a.get('first_action_minute', pd.Series(np.nan, index=a.index)))]
    b = P3[P3.cross_minute.notna()].copy(); b['rule'] = '1 % expiry-day: ' + b.series; b['unit'] = 'whole book'
    b['classification'] = np.where(b.kill_switch_consistent, np.where(b.crossing_vs_cycle_stop.isin(['before', 'same minute']), 'kill-switch behaviour, coincides with the cycle stop',
                                   np.where(b.crossing_vs_cycle_stop.str.startswith('after'), 'crossing after the cycle stop had already fired', 'kill-switch behaviour without cycle stop')),
                                   np.where(b.liquidated, 'liquidation but new short entries continue', 'no kill-switch behaviour (no liquidation; trading continues)'))
    b['cross_time'] = [f'{e} {t}' for e, t in zip(b.expiry, b.cross_time)]
    cols = ['rule', 'convention', 'und', 'expiry', 'split', 'unit', 'cross_time', 'classification', 'delay_min', 'first_action_time', 'first_action_label', 'first_action_oid',
            'cycle_stop_within_5', 'open_short_lots_at_cross', 'short_lots_bought_within_5', 'share_bought_within_5', 'last_order_before', 'first_order_after',
            'new_short_entries_after', 'new_short_entries_after_5min', 'entries_cease', 'kill_switch_consistent', 'continues_trading_15min_later', 'crossing_vs_cycle_stop']
    OA = pd.concat([a, b], ignore_index=True).reindex(columns=cols); OA.to_csv(os.path.join(HERE, 'order_action_matching.csv'), index=False)
    # cycle-level reconciliation
    rows = []
    for (u, e) in cycle_keys():
        m = mk[(u, e)]; ed = e.date(); p1 = P1[(P1.und == u) & (P1.expiry == ed)].iloc[0]; p4 = P4[(P4.und == u) & (P4.expiry == ed)].iloc[0]
        r = dict(expiry=ed, underlying=u, split=p1.split, has_D1=p1.has_D1, has_D0=p1.has_D0,
                 carried_short_lots=p1.get('carried_short_lots_fills'), carried_long_lots=p1.get('carried_long_lots_fills'),
                 carried_short_value_D1_close=p1.get('carried_short_value_D1_close'), carried_short_entry_premium_fifo=p1.get('carried_short_entry_premium_fifo'),
                 threshold_C_rs=CARRY_PCT * p1.get('carried_short_value_D1_close') if pd.notna(p1.get('carried_short_value_D1_close')) else np.nan,
                 threshold_E_fifo_rs=CARRY_PCT * p1.get('carried_short_entry_premium_fifo') if pd.notna(p1.get('carried_short_entry_premium_fifo')) else np.nan,
                 mtm_at_D1_close=p1.get('mtm_at_D1_close'))
        for dfn in 'ABCDE':
            g = E2[(E2.und == u) & (E2.expiry == ed) & (E2.definition == dfn) & (E2.convention == 'fifo')]
            r[f'{dfn}_fifo_first_cross'] = tm(u, e, g.cross_minute.min()) if len(g) and g.cross_minute.notna().any() else ''
            r[f'{dfn}_fifo_matched/crossings'] = f"{(g.classification == 'matched stop').sum()}/{int(g.cross_minute.notna().sum())}" if len(g) else ''
        for dfn in 'ABD':
            g = E2[(E2.und == u) & (E2.expiry == ed) & (E2.definition == dfn) & (E2.convention == 'fifo')]
            if len(g): r[f'{dfn}_fifo_threshold_range_rs'] = f'{g.threshold_rs.min():,.0f} - {g.threshold_rs.max():,.0f} per position'
        for dfn, conv in (('C', 'held, convention-free'), ('E', 'fifo')):
            g = E2[(E2.und == u) & (E2.expiry == ed) & (E2.definition == dfn) & (E2.convention == conv)]
            r[f'{dfn}_{conv.split(",")[0]}_classification'] = g.classification.iloc[0] if len(g) else 'not tested (no carried book or no D0)'
        r['D1_close_mark_ambiguity_rs'] = p1.get('ledger_vs_fills_mtm_abs_diff_D1_close')
        q = P3[(P3.und == u) & (P3.expiry == ed)]
        for key, lab in (('S1', 'realised_fifo'), ('S2', 'unrealised_fifo'), ('S3', 'combined'), ('S4', 'carried_fifo'), ('S5', 'new_fifo')):
            g = q[q.series.str.startswith(key) & q.convention.isin(['fifo', 'convention-free'])]
            r[f'D0_{lab}_min'] = float(g.min_value_D0.iloc[0]) if len(g) else np.nan
            r[f'D0_{lab}_cross_2L'] = g.cross_time.iloc[0] if len(g) else ''
        g = q[q.series.str.startswith('S3')]
        if len(g): r['D0_combined_close'] = float(g.value_at_D0_close.iloc[0])
        r.update(observed_stop_time=p4.get('stop_time', ''), observed_stop_day=p4.get('stop_day', ''), mtm_at_stop_quote=p4.get('mtm_at_stop_quote'),
                 short_entries_after_stop=p4.get('short_entries_after_stop'), min_cycle_mtm_minute_close=p4.min_cycle_mtm_minute_close)
        g = q[q.series.str.startswith('S3')]
        if len(g) and pd.notna(g.cross_minute.iloc[0]):
            x = OA[(OA.rule.str.contains('S3')) & (OA.und == u) & (OA.expiry == ed)]
            r['S3_2L_classification'] = x.classification.iloc[0] if len(x) else ''
        else: r['S3_2L_classification'] = 'no crossing' if len(g) else 'no D0 session'
        r['after_2L_D0_crossing'] = (g.iloc[0].get('crossing_vs_cycle_stop', '') if len(g) and pd.notna(g.cross_minute.iloc[0]) else 'no crossing')
        lim = []
        if not p1.has_D1: lim.append('no D-1 session: nothing carried')
        if not p1.has_D0: lim.append('no D0 fills in the export')
        if p1.lots_platform_or_manual > 0: lim.append(f"platform/manual orders {int(p1.orders_platform_or_manual)}")
        r['data_limitations'] = '; '.join(lim)
        rows.append(r)
    pd.DataFrame(rows).to_csv(os.path.join(HERE, 'cycle_level_risk_reconciliation.csv'), index=False)
    print(f'all done {time.time() - t0:.0f}s')

if __name__ == '__main__':
    main()
