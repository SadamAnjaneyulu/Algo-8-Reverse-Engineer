"""Statistics for the design-thesis tests (plan reports/DESIGN_THESIS_PLAN.md): week-cluster bootstrap (2,000 draws, seed 20261124), splits, Holm over the five primary predictions.
Input outputs/thesis/thesis_*.csv; output outputs/thesis/thesis_stats.csv, thesis_t2_profile.csv, thesis_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); TH = f'{OUT}/thesis'; B = 2000
T1 = pd.read_csv(f'{TH}/thesis_t1.csv'); T2 = pd.read_csv(f'{TH}/thesis_t2.csv'); T3 = pd.read_csv(f'{TH}/thesis_t3_events.csv'); T4 = pd.read_csv(f'{TH}/thesis_t4.csv')
wk = lambda d: pd.to_datetime(d.expiry).dt.strftime('%G-%V')
for d in (T1, T2, T3, T4): d['wk'] = wk(d)
def boot(df, stat):
    """stat(df) -> float; week-cluster bootstrap. returns point, lo, hi, two-sided p (share of draws on the other side of zero, doubled)"""
    rng = np.random.default_rng(20261124); w = df.wk.unique(); g = {k: v for k, v in df.groupby('wk')}; pt = stat(df)
    bs = np.array([stat(pd.concat([g[k] for k in rng.choice(w, len(w))])) for _ in range(B)]); bs = bs[np.isfinite(bs)]
    p = 2 * min((bs <= 0).mean(), (bs >= 0).mean()); return pt, np.quantile(bs, .025), np.quantile(bs, .975), min(p, 1.0)
rows = []
def add(test, label, df, stat, unit):
    pt, lo, hi, p = boot(df, stat); r = dict(test=test, label=label, n=len(df), value=pt, lo=lo, hi=hi, p=p, unit=unit)
    for s in ('IS', 'OOS', 'LIVE_FITTED'):
        sub = df[df.split == s]; r[s] = stat(sub) if len(sub) else np.nan
    for u in ('NIFTY', 'SENSEX'):
        sub = df[df.und == u]; r[u] = stat(sub) if len(sub) else np.nan
    rows.append(r); return r
# ---- T1
for seg in ('D-1 day', 'overnight', 'D0 day', 'overnight (D0 09:15 open)'):
    d = T1[(T1.segment == seg)].dropna(subset=['pnl_pts']).copy()
    add('T1', f'{seg}: short ATM straddle, % of premium', d, lambda x: x.pnl_pts.sum() / x.prem_in.sum(), '% of premium')
    add('T1', f'{seg}: short ATM straddle, Rs per cycle (constant lot)', d, lambda x: x.pnl_rs.mean(), 'Rs per cycle')
    dv = T1[(T1.segment == seg)].dropna(subset=['iv_used', 'rv']).copy(); dv = dv[dv.iv_used > 0]
    add('T1v', f'{seg}: realised / implied variance', dv, lambda x: x.rv.sum() / x.iv_used.sum(), 'ratio')
# ---- T3: per cycle-session means, then the mean over cycle-sessions
for sess in ('D-1', 'D0'):
    e = T3[T3.session == sess]
    for col, nm in (('fwd15_bp', '+15 min'), ('fwd30_bp', '+30 min'), ('fwd60_bp', '+60 min'), ('fwd_end_bp', 'to session end')):
        c = e.groupby(['und', 'expiry', 'split', 'wk'])[col].mean().reset_index()
        add('T3', f'{sess} ladder trigger: index continuation {nm} (bp, signed)', c, lambda x, col=col: x[col].mean(), 'bp')
    e2 = e.assign(diff_rs=(e.lad_pts - e.opp_pts) * e.lot); c = e2.groupby(['und', 'expiry', 'split', 'wk']).diff_rs.mean().reset_index()
    add('T3o', f'{sess} ladder trigger: ladder right minus opposite right, held to session end (Rs per lot-event)', c, lambda x: x.diff_rs.mean(), 'Rs per event')
    if sess == 'D-1':
        e3 = e.assign(diff_rs=(e.lad_pts_toD0 - e.opp_pts_toD0) * e.lot); c = e3.groupby(['und', 'expiry', 'split', 'wk']).diff_rs.mean().reset_index()
        add('T3o', 'D-1 ladder trigger: ladder right minus opposite right, held to D0 15:14 (Rs per lot-event)', c, lambda x: x.diff_rs.mean(), 'Rs per event')
# both sessions pooled per cycle (primary T3 predictions)
c = T3.groupby(['und', 'expiry', 'split', 'wk']).fwd_end_bp.mean().reset_index(); add('T3P', 'PRIMARY: ladder trigger, index continuation to session end (bp), D-1 and D0 pooled', c, lambda x: x.fwd_end_bp.mean(), 'bp')
e = T3.assign(diff_rs=(T3.lad_pts - T3.opp_pts) * T3.lot); c = e.groupby(['und', 'expiry', 'split', 'wk']).diff_rs.mean().reset_index(); add('T3P', 'PRIMARY: ladder right minus opposite right to session end (Rs per lot-event), pooled', c, lambda x: x.diff_rs.mean(), 'Rs per event')
# ---- T4
d = T4.dropna(subset=['CE_pts', 'PE_pts']).copy()
add('T4', 'short ATM call, D-1 open -> D0 15:14, % of call premium', d, lambda x: x.CE_pts.sum() / x.CE_prem.sum(), '% of premium')
add('T4', 'short ATM put, D-1 open -> D0 15:14, % of put premium', d, lambda x: x.PE_pts.sum() / x.PE_prem.sum(), '% of premium')
add('T4', 'short call minus short put, Rs per cycle', d, lambda x: (x.CE_rs - x.PE_rs).mean(), 'Rs per cycle')
add('T4', 'index move D-1 open -> D0 15:14 (bp)', d, lambda x: (1e4 * np.log(x.spot_out / x.spot_in)).mean(), 'bp')
S = pd.DataFrame(rows)
# Holm over the five primary predictions
prim = S.index[S.label.isin(['D-1 day: short ATM straddle, % of premium', 'overnight: short ATM straddle, % of premium', 'D0 day: short ATM straddle, % of premium']) | (S.test == 'T3P')]
ps = S.loc[prim, 'p'].sort_values(); m = len(ps); adj = {}; run = 0
for k, (ix, p) in enumerate(ps.items()): run = max(run, min(1.0, (m - k) * p)); adj[ix] = run
S['p_holm'] = S.index.map(adj)
def verdict(r):
    if pd.isna(r.p_holm): return ''
    same = np.sign(r.IS) == np.sign(r.OOS) == np.sign(r.value)
    if r.value > 0 and r.lo > 0 and same: return 'supported'
    if r.value > 0 and same: return 'weakly supported'
    return 'not supported'
S['verdict'] = S.apply(verdict, axis=1); S.to_csv(f'{TH}/thesis_stats.csv', index=False)
# ---- T2 profile
P = T2.dropna(subset=['pnl_pct']).groupby(['session', 'block_start']).agg(cycles=('pnl_pct', 'size'), mean_pct=('pnl_pct', 'mean'), median_pct=('pnl_pct', 'median'), win=('pnl_pct', lambda x: (x > 0).mean()), abs_move_bp=('abs_move_bp', 'mean')).reset_index()
P['clock'] = P.block_start.map(lambda j: f'{9 + (15 + j) // 60:02d}:{(15 + j) % 60:02d}'); P.to_csv(f'{TH}/thesis_t2_profile.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 90)
print(S[['test', 'label', 'n', 'value', 'lo', 'hi', 'p', 'p_holm', 'IS', 'OOS', 'LIVE_FITTED', 'NIFTY', 'SENSEX', 'verdict']].round(4).to_string())
print(P.groupby('session')[['mean_pct', 'win']].mean().round(4)); print(P[['session', 'clock', 'mean_pct', 'win', 'abs_move_bp']].round(4).to_string())
