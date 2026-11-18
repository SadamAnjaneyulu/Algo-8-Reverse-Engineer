"""Derived tables and charts for the reports (reads results/, writes results/*.csv and reports/figures/*.png)."""
import json, os
from datetime import datetime, timedelta
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from . import experiment as X, metrics as M, config as C, final_run as F, cycles as Cy
R = 'results'; FIG = 'reports/figures'; BASE = F.BASE
dt = lambda t: datetime(1970, 1, 1) + timedelta(seconds=int(t) + 19800)


def tables_for(v, n): return F.table(n, v)


def derived():
    out = {}; mon = []; hedge = []; conc = []; vol = []; worst = []; conc_rows = []
    cyc = Cy.cycle_list(); excl = cyc.groupby(['und', 'split', 'status']).size().reset_index(name='cycles'); excl.to_csv(f'{R}/data_coverage_and_exclusions.csv', index=False)
    for v in X.VARIANTS:
        for n in F.names_for(v):
            d = tables_for(v, n); d['month'] = d.d0.str.slice(0, 7); d['part'] = np.where(d.split == 'IS', 'IS', 'OOS')
            m = d.groupby(['und', 'month', 'part']).agg(cycles=('net', 'size'), gross=('gross', 'sum'), net=('net', 'sum'), costs=('costs', 'sum')).reset_index(); m['net_return_pct_of_capital'] = 100 * m.net / C.CAPITAL_RS; m.insert(0, 'config', n); m.insert(0, 'variant', v); mon.append(m)
            # hedge effectiveness (gross, reference prices): core (short legs) vs full basket
            d['core'] = d.leg_pnl.apply(lambda x: x['SCE'] + x['SPE']); d['wings'] = d.leg_pnl.apply(lambda x: x['WCE'] + x['WPE'])
            for part in ('IS', 'OOS'):
                for und in ('NIFTY', 'SENSEX'):
                    s = d[(d.part == part) & (d.und == und)]
                    if len(s): hedge.append(dict(variant=v, config=n, part=part, und=und, cycles=len(s), core_only_gross=s.core.sum(), with_wings_gross=s.gross.sum(), wings_pnl=s.wings.sum(), core_worst_cycle=s.core.min(), full_worst_cycle=s.gross.min(), worst_cycle_loss_reduction=s.gross.min() - s.core.min(), core_std=s.core.std(), full_std=s.gross.std(), std_reduction_pct=100 * (1 - s.gross.std() / s.core.std())))
            # concentration
            for part in ('IS', 'OOS'):
                s = d[d.part == part].sort_values('net')
                if len(s): conc_rows.append(dict(variant=v, config=n, part=part, cycles=len(s), net=s.net.sum(), net_without_best5=s.net.iloc[:-5].sum(), net_without_worst5=s.net.iloc[5:].sum(), net_without_best5_and_worst5=s.net.iloc[5:-5].sum(), best5_sum=s.net.iloc[-5:].sum(), worst5_sum=s.net.iloc[:5].sum(), top5_share_of_net_pct=(100 * s.net.iloc[-5:].sum() / s.net.sum()) if s.net.sum() else np.nan))
            # volatility regimes: terciles of D-1 spot range (% of spot) from IN-SAMPLE cycles of each index
            d['rng'] = 100 * d.d1_range / d.spot_0915
            for und in ('NIFTY', 'SENSEX'):
                q = d[(d.und == und) & (d.part == 'IS')].rng.quantile([1 / 3, 2 / 3]).values; s = d[d.und == und].copy(); s['regime'] = np.where(s.rng <= q[0], 'low', np.where(s.rng <= q[1], 'mid', 'high'))
                for (part, reg), g in s.groupby(['part', 'regime']): vol.append(dict(variant=v, config=n, und=und, part=part, regime=reg, cycles=len(g), net=g.net.sum(), avg_net=g.net.mean(), win_rate_pct=100 * (g.net > 0).mean(), worst=g.net.min(), tercile_cut_pct=f'{q[0]:.2f}/{q[1]:.2f}'))
            w = d.sort_values('net').head(10)[['und', 'expiry', 'part', 'subset', 'gross', 'net', 'K', 'official_close', 'spot_0915', 'd1_range']].copy(); w['move_pct_close_vs_K'] = 100 * (w.official_close - w.K) / w.K; w.insert(0, 'config', n); w.insert(0, 'variant', v); worst.append(w)
            out[(v, n)] = d
    pd.concat(mon).to_csv(f'{R}/monthly_performance.csv', index=False); pd.DataFrame(hedge).to_csv(f'{R}/hedge_effectiveness.csv', index=False); pd.DataFrame(conc_rows).to_csv(f'{R}/concentration.csv', index=False); pd.DataFrame(vol).to_csv(f'{R}/volatility_regimes.csv', index=False); pd.concat(worst).to_csv(f'{R}/worst_cycles.csv', index=False)
    # exposure / concurrency for the combined portfolio (HOLD, hold-settle)
    d = out[('HOLD_SETTLE', 'HOLD')]; iv = [(scen_t(r.d1, '09:16'), scen_t(r.d0, '15:30'), r.peak_margin, r.und) for r in d.itertuples()]; ev = sorted([(a, 1, m) for a, b, m, u in iv] + [(b, -1, m) for a, b, m, u in iv]); cur = 0; curm = 0.0; mx = 0; mxm = 0.0
    for t, k, m in ev: cur += k; curm += k * m; mx = max(mx, cur); mxm = max(mxm, curm)
    json.dump(dict(max_simultaneous_baskets=mx, peak_combined_margin_proxy_rs=mxm, peak_combined_margin_util_pct=100 * mxm / C.CAPITAL_RS, avg_gross_units_at_entry_nifty=float(12 * d[d.und == 'NIFTY'].lot.mean()), avg_gross_units_at_entry_sensex=float(12 * d[d.und == 'SENSEX'].lot.mean()), net_units_at_entry=0), open(f'{R}/exposure_summary.json', 'w'), indent=1)
    return out


def scen_t(day, hm): from .scen import epoch; return epoch(day, hm)


def charts(out):
    for v in X.VARIANTS:
        fig, ax = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw=dict(height_ratios=[3, 2]))
        for n in F.names_for(v):
            for scope in ('COMBINED', 'NIFTY', 'SENSEX'):
                d = out[(v, n)]; d = d if scope == 'COMBINED' else d[d.und == scope]
                t, e = M.equity_curve(d); x = [dt(i) for i in t]; ls = '-' if scope == 'COMBINED' else ':'
                ax[0].plot(x, e, ls, lw=1.6 if scope == 'COMBINED' else 1.0, label=f'{n} {scope}')
                if scope == 'COMBINED': eq = C.CAPITAL_RS + e; pk = np.maximum.accumulate(eq); ax[1].plot(x, 100 * (eq - pk) / pk, lw=1.2, label=n)
        for a in ax: a.axvline(datetime(2025, 11, 18), color='k', ls='--', lw=0.8); a.axvspan(datetime(2026, 6, 22), datetime(2026, 10, 22), color='orange', alpha=0.15)
        ax[0].set_title(f'{v}: cumulative net P&L (Rs), net of slippage and costs. Dashed = in-sample / out-of-sample boundary; shaded = previously inspected window'); ax[0].set_ylabel('Rs'); ax[0].legend(fontsize=7); ax[1].set_ylabel('drawdown % of equity (combined)'); ax[1].legend(fontsize=7); fig.tight_layout(); fig.savefig(f'{FIG}/equity_drawdown_{v}.png', dpi=130); plt.close(fig)
    m = pd.read_csv(f'{R}/monthly_performance.csv'); m = m[(m.variant == 'HOLD_SETTLE') & (m.config == 'HOLD')].groupby('month').net.sum()
    fig, ax = plt.subplots(figsize=(12, 3.5)); ax.bar(m.index, m.values, color=['#16a34a' if x > 0 else '#dc2626' for x in m.values]); ax.set_title('HOLD_SETTLE / HOLD: monthly net P&L (NIFTY + SENSEX), Rs'); plt.xticks(rotation=90, fontsize=6); fig.tight_layout(); fig.savefig(f'{FIG}/monthly_hold_settle_hold.png', dpi=130); plt.close(fig)


if __name__ == '__main__': charts(derived())
