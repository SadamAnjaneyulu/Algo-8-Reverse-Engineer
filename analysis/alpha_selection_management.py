"""ALPHA-1: split body-short P&L into ENTRY SELECTION (hold-to-expiry carry of every lot sold) and MANAGEMENT (actual - hold);
same for wings/lump; and test TIMING skill vs a null that sells the ATM straddle at every minute of the same sessions.
Gross of costs. python3 analysis/alpha_selection_management.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged()
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl'))
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
settle = ix.groupby(['und', ix.ts.dt.normalize()]).close.last()          # last index bar of the day ~ expiry settlement proxy
cyc_ok = d.groupby(['und', 'expiry']).dte.agg(lambda x: (x >= 1).any() and (x == 0).any())
rows = []
for (u, e), c in d.groupby(['und', 'expiry']):
    if not cyc_ok[(u, e)] or (u, e) not in settle.index: continue
    ST = settle[(u, e)]; lot = c.lot.iloc[0]
    intr = np.where(c.cp == 'CE', np.maximum(ST - c.strike, 0), np.maximum(c.strike - ST, 0))
    c = c.assign(intr=intr)
    def part(mask):
        x = c[mask]; return x.cash.sum(), (x.sl * x.lot * x.intr).sum()      # realised cash, value of residual at expiry
    # body shorts: every numeric SELL, closed by numeric/s_ buys of the same contracts
    sells = c[(c.tp == 'num') & (c.side == 'Sell')]
    hold_short = (sells.qty_fill * (sells.px_fill - sells.intr)).sum()        # sold and held to expiry
    short_keys = set(zip(sells.cp, sells.strike))
    is_short_flow = c.apply(lambda r: (r.cp, r.strike) in short_keys and r.tp in ('num', 's_'), axis=1) & ~((c.tp == 'num') & (c.side == 'Buy') & (c.px_fill < 0))
    # actual P&L of body-short contracts (all body/stop flows on those contracts) incl. residual at expiry
    x = c[is_short_flow]; act_short = x.cash.sum() + (x.sl * x.lot * x.intr).sum()
    w = c[c.tp == 'h_']; hold_w = (w.sgn * w.qty_fill * (w.intr - w.px_fill)).where(w.side == 'Buy', 0).sum(); act_w = w.cash.sum() + (w.sl * w.lot * w.intr).sum()
    v = c[c.tp == 'v_']; act_v = v.cash.sum() + (v.sl * v.lot * v.intr).sum(); hold_v = ((v.intr - v.px_fill) * v.qty_fill).where(v.side == 'Buy', 0).sum()
    total = c.cash.sum() + (c.sl * c.lot * c.intr).sum()
    rows.append(dict(und=u, expiry=e.date(), stop=(c.tp == 's_').any(), total_actual=total, short_hold=hold_short, short_actual=act_short,
                     short_mgmt=act_short - hold_short, wings_hold=hold_w, wings_actual=act_w, lump_hold=hold_v, lump_actual=act_v))
R = pd.DataFrame(rows)
pd.set_option('display.width', 220)
print('cycles', len(R))
print((R[['total_actual', 'short_hold', 'short_actual', 'short_mgmt', 'wings_hold', 'wings_actual', 'lump_hold', 'lump_actual']].sum() / 1e5).round(2).rename('Rs lakh, all cycles').to_string())
print('\nby stop/non-stop cycles (Rs lakh):'); print((R.groupby('stop')[['total_actual', 'short_hold', 'short_mgmt', 'wings_actual', 'lump_actual']].sum() / 1e5).round(2).to_string())
print('\nper-cycle short_hold vs short_mgmt: mean (Rs K) and cycles positive:',
      {k: (round(R[k].mean() / 1e3, 1), int((R[k] > 0).sum())) for k in ['short_hold', 'short_mgmt', 'total_actual']})
R.to_pickle(os.path.join(C, 'alpha_split.pkl'))

# TIMING: algo's paired ATM-straddle sales vs selling the ATM straddle at every minute of the same sessions (hold to expiry, per unit, bps of spot)
pr = pd.read_pickle(os.path.join(C, 'p4_pairs_live.pkl'))       # paired CE/PE sales same strike within 3 s (fill prices)
pr = pr[pr.date.isin(pd.to_datetime([x for x in R.expiry]) ) | True]
pr['ST'] = [settle.get((u, e), np.nan) for u, e in zip(pr.und, pr.expiry)]
pr = pr.dropna(subset=['ST'])
pr['prem'] = pr.px_fill + pr.Lpe * 0.0   # placeholder replaced below
# fill-price straddle: CE fill (px_fill) + PE fill; we stored PE recovered quote; use PE quote L (close to its fill)
pr['prem'] = pr.px_fill + pr.Lpe
pr['carry_bp'] = (pr.prem - (pr.ST - pr.strike).abs()) / pr.ST * 1e4
pr['day'] = np.where(pr.dte >= 1, 'D-1', 'D0'); pr['hh'] = pr.t.dt.hour
# market null: every minute 09:16-15:00, nearest-ATM straddle at previous-minute closes
pc = op.assign(m=op.ts + pd.Timedelta(minutes=1)).pivot_table(index=['und', 'expiry', 'm', 'strike'], columns='cp', values='c', aggfunc='last').dropna()
pc = pc.reset_index(); ixc = ix.set_index(['und', 'ts']).close
pc['S1'] = [ixc.get((u, m - pd.Timedelta(minutes=1)), np.nan) for u, m in zip(pc.und, pc.m)]
pc['step'] = np.where(pc.und == 'NIFTY', 50, 100); pc = pc[pc.strike == (pc.S1 / pc.step).round() * pc.step]
pc = pc[(pc.m.dt.strftime('%H:%M') >= '09:16') & (pc.m.dt.strftime('%H:%M') <= '15:00')]
pc['ST'] = [settle.get((u, e), np.nan) for u, e in zip(pc.und, pc.expiry)]; pc = pc.dropna(subset=['ST'])
pc['carry_bp'] = (pc.CE + pc.PE - (pc.ST - pc.strike).abs()) / pc.ST * 1e4
pc['date'] = pc.m.dt.normalize(); pc['hh'] = pc.m.dt.hour
pc['day'] = np.where((pc.expiry - pc.date).dt.days >= 1, 'D-1', 'D0')
sess = set(zip(pr.und, pr.date))
pc = pc[[ (u, dd) in sess for u, dd in zip(pc.und, pc.date)]]
print('\n=== TIMING: hold-to-expiry carry of an ATM straddle, bps of spot (gross) ===')
for day in ['D-1', 'D0']:
    a = pr[pr.day == day]; n = pc[pc.day == day]
    # same-session, same-hour matched null: average null carry over the (session, hour) cells the algo traded, weighted like the algo
    cell = n.groupby(['und', 'date', 'hh']).carry_bp.mean()
    matched = np.array([cell.get((u, dd, h), np.nan) for u, dd, h in zip(a.und, a.date, a.hh)])
    sessmean = n.groupby(['und', 'date']).carry_bp.mean(); sm = np.array([sessmean.get((u, dd), np.nan) for u, dd in zip(a.und, a.date)])
    ok = np.isfinite(matched)
    print(f'{day}: algo sales n={len(a)} mean carry {a.carry_bp.mean():.1f} bp | null every-minute same sessions {n.carry_bp.mean():.1f} bp | '
          f'session-matched {np.nanmean(sm):.1f} | session+hour matched {np.nanmean(matched):.1f} | algo minus session+hour matched {np.nanmean(a.carry_bp.values[ok] - matched[ok]):+.1f} bp')
    # bootstrap by session for the timing difference
    diff = pd.DataFrame({'s': list(zip(a.und, a.date)), 'x': a.carry_bp.values - matched}).dropna().groupby('s').x.mean()
    bs = [diff.sample(len(diff), replace=True, random_state=i).mean() for i in range(2000)]
    print(f'      timing edge per session: mean {diff.mean():+.1f} bp, 95% CI [{np.percentile(bs, 2.5):+.1f}, {np.percentile(bs, 97.5):+.1f}] over {len(diff)} sessions')
