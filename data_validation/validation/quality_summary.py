"""Aggregates scan outputs into the figures used by the reports (counts only; every number is recomputed from the committed files)."""
import json, sys, collections
import numpy as np, pandas as pd


def build(tab):
    o = pd.DataFrame(json.load(open(f'{tab}/option_session_scan.json'))); c = pd.read_parquet(f'{tab}/contract_sessions.parquet'); u = pd.DataFrame(json.load(open(f'{tab}/underlying_scan.json')))
    R = {}
    for idx in ('nifty', 'sensex'):
        oi = o[o['index'] == idx]; ci = c[c['index'] == idx].copy(); ui = u[u['index'] == idx]
        ci = ci.merge(oi[['expiry', 'day', 'plan_center']], on=['expiry', 'day'], how='left'); step = 50 if idx == 'nifty' else 100; ci['k'] = ((ci.strike - ci.plan_center) / step).round().astype(int)
        planned = oi.planned_contracts.sum(); withrows = len(ci)
        cov = ci.groupby(['right', pd.cut(ci.k.abs(), [-1, 5, 10, 20, 30, 40, 45], labels=['0-5', '6-10', '11-20', '21-30', '31-40', '41-45'])], observed=True).size().unstack(0)
        # share of planned contracts with rows by distance: 2 sessions per expiry, one contract per (strike,right)
        sessions = len(oi); per_k = ci.groupby('k').size() / (sessions * 2)
        R[idx] = dict(sessions=sessions, planned_contracts=int(planned), contracts_with_rows=withrows, contracts_without_rows=int(planned - withrows), share_with_rows=round(withrows / planned, 4),
                      rows=int(oi.rows.sum()), strike_coverage_by_abs_distance_steps=cov.to_dict(), share_of_planned_with_rows_by_k={int(k): round(float(v), 3) for k, v in per_k.items() if k in (-45, -40, -30, -20, -10, -5, 0, 5, 10, 20, 30, 40, 45)},
                      sessions_with_both_ce_and_pe=int(((oi.ce_strikes > 0) & (oi.pe_strikes > 0)).sum()), ce_strikes_without_pe_same_session=int(oi.ce_not_pe.sum()), pe_strikes_without_ce_same_session=int(oi.pe_not_ce.sum()),
                      strikes_with_rows_per_session=oi.n_strikes_with_rows.describe().round(1).to_dict(), plan_strikes_values=oi.plan_strikes.value_counts().to_dict(),
                      candle=dict(contract_sessions=withrows, full_grid=int((ci.bars_in_grid >= ci.grid).sum()), coverage_ge_90pct=int((ci.bars_in_grid / ci.grid >= .9).sum()), coverage_50_90=int(((ci.bars_in_grid / ci.grid >= .5) & (ci.bars_in_grid / ci.grid < .9)).sum()), coverage_lt_50=int((ci.bars_in_grid / ci.grid < .5).sum()),
                                  median_coverage=float((ci.bars_in_grid / ci.grid).median()), max_gap_gt_30min=int((ci.max_gap > 30).sum()), leading_late_open_after_0930=int((ci['first'] > '09:30').sum()), early_end_before_1500=int((ci['last'] < '15:00').sum())),
                      zero_volume_bar_share=round(float(ci.zero_vol.sum() / ci.bars.sum()), 4), flat_bar_share=round(float(ci.flat_bars.sum() / ci.bars.sum()), 4), contract_sessions_all_zero_volume=int((ci.zero_vol == ci.bars).sum()),
                      oi=dict(contract_sessions_oi_all_zero=int((ci.oi_zero == ci.bars).sum()), share_rows_oi_zero=round(float(ci.oi_zero.sum() / ci.bars.sum()), 4), contract_sessions_oi_constant=int((ci.oi_nunique == 1).sum())),
                      dup_series_hash_nontrivial=int((ci[(ci.bars >= 20) & (ci.close_nunique > 1)].groupby('series_hash').size() > 1).sum()),
                      out_of_order_contract_sessions=int((~ci.ordered).sum()), dup_ts_rows=int(ci.dup_ts.sum()),
                      raw_vs_norm=dict(sessions_compared=int(oi.raw_rows.notna().sum()), raw_only=int(oi.raw_only_rows.sum()), norm_only=int(oi.norm_only_rows.sum()), value_mismatch=int(oi.value_mismatch_rows.sum()), raw_dup_rows=int(oi.raw_dup_rows_full.sum()), raw_rows=int(oi.raw_rows.sum()), norm_rows=int(oi.rows.sum())),
                      underlying=dict(spot_sessions=int((ui.kind == 'spot').sum()), futures_sessions=int((ui.kind == 'futures').sum()), spot_preopen_rows=int(ui[ui.kind == 'spot'].before_0915.sum()), spot_sessions_with_missing_minutes=int((ui[ui.kind == 'spot'].session_missing_minutes > 0).sum()),
                                      spot_missing_minutes=int(ui[ui.kind == 'spot'].session_missing_minutes.sum()), spot_volume_nonzero_rows=int(ui[ui.kind == 'spot'].volume_nonzero_rows.sum()), raw_mismatch_rows=int(ui.value_mismatch_rows.fillna(0).sum()), raw_only=int(ui.raw_only_rows.fillna(0).sum()), norm_only=int(ui.norm_only_rows.fillna(0).sum())))
    json.dump(R, open(f'{tab}/quality_summary.json', 'w'), indent=1, default=str); return R


if __name__ == '__main__': print(json.dumps(build(sys.argv[1]), indent=1, default=str)[:7000])
