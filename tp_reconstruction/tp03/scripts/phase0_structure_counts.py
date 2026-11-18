"""TP-03 Phase 0 amendment: DESCRIPTIVE structural counts only (denominators, attribution classes, module roles, permutation-design size).
No state variables, no hypothesis tests, no thresholds. python3 tp_reconstruction/tp03/scripts/phase0_structure_counts.py  (needs ALGO8_MARKET_DIR for the bar-completeness check)
Window definition as in the source (F07): [T - 2 s, T + 3 min). Order-entry minute is the only submission time available for body orders."""
import os, sys, math
import numpy as np, pandas as pd, yaml
HERE = os.path.dirname(os.path.abspath(__file__)); TP03 = os.path.dirname(HERE); PKG = os.path.dirname(TP03); REPO = os.path.dirname(PKG)
sys.path.insert(0, os.path.join(PKG, 'scripts'))
CFG = yaml.safe_load(open(os.path.join(TP03, 'config.yaml'))); OUT = os.path.join(TP03, 'analysis'); os.makedirs(OUT, exist_ok=True)
import market_data as md
D = os.path.join(PKG, 'data')
L = pd.read_parquet(os.path.join(D, 'fill_event_ledger.parquet')); R = pd.read_parquet(os.path.join(D, 'fill_roles.parquet')); R = R[R.method == 'FIFO']
F = R.merge(L[['src_row', 'und', 'cp', 'strike', 'expiry', 'date', 'module', 'parent_oid', 'order_entry_minute', 't_fill', 'order_status']], on='src_row')
OP = F[F.open_qty > 0].copy(); OP['side'] = np.where(OP.sgn < 0, 'sell(short open)', 'buy(long open)')
BASE = {'NIFTY': 65, 'SENSEX': 20}; OP['base'] = OP.und.map(BASE); OP['open_base_units'] = OP.open_qty / OP.base
cycles = L.groupby(['und', 'expiry']).agg(first=('date', 'min'), last=('date', 'max')).reset_index(); cycles['has_pre'] = cycles['first'] < cycles.expiry; cycles['has_d0'] = cycles['last'] == cycles.expiry
cycles['cycle'] = cycles.und + '|' + cycles.expiry.dt.strftime('%Y-%m-%d')
tm = lambda s: pd.Timedelta(hours=int(s[:2]), minutes=int(s[3:]))
PRE = [tm(x) for x in CFG['entry']['d1_windows']]; CTRL = [tm(x) for x in CFG['entry']['d1_control_windows']]
d0c = CFG['entry']['d0_windows']; D0W = [tm(d0c['start']) + pd.Timedelta(minutes=d0c['step_minutes'] * k) for k in range(int((tm(d0c['end']) - tm(d0c['start'])) / pd.Timedelta(minutes=d0c['step_minutes'])) + 1)]
B0, B1 = pd.Timedelta(seconds=CFG['entry']['window_bounds_seconds']['before']), pd.Timedelta(seconds=CFG['entry']['window_bounds_seconds']['after'])
I = md.index_bars(); I['date'] = I.ts.dt.normalize(); bars = {k: set(g.ts) for k, g in I.groupby(['und', 'date'])}
stops = L[L.module == 's_'].groupby(['und', 'expiry']).t_fill.min()
inv = {}   # (und, expiry) -> sorted arrays of fill time and total short units after each fill, from FIFO roles per contract
Rc = F.sort_values('t_fill')
def short_units_at(und, expiry, t):
    g = Rc[(Rc.und == und) & (Rc.expiry == expiry) & (Rc.t_fill < t)]
    if g.empty: return 0.0
    last = g.groupby('contract_id').inventory_after.last(); return float((-last[last < 0]).sum())
rows = []
for c in cycles.itertuples():
    for kind, dts, wins, ctrl in (('PRE', [c.first] if c.has_pre else [], PRE + CTRL, set(CTRL)), ('D0', [c.expiry] if c.has_d0 else [], D0W, set())):
        for d in dts:
            sess = L[(L.und == c.und) & (L.expiry == c.expiry) & (L.date == d)]; first_fill = sess.t_fill.min(); allT = sorted(sess.t_fill)
            for T in wins:
                t = d + T; w0, w1 = t - B0, t + B1; w0m = w0.floor('min'); inwin = OP[(OP.und == c.und) & (OP.expiry == c.expiry) & (OP.t_fill >= w0) & (OP.t_fill < w1)]
                sh = inwin[inwin.sgn < 0]; shb = sh[sh.module == 'num']; paired = bool(len(shb) and (shb.groupby('strike').cp.nunique() >= 2).any()); lo = inwin[inwin.sgn > 0]
                roles4 = {('CE', -1): False, ('PE', -1): False, ('CE', 1): False, ('PE', 1): False}
                for (cp, sg), g in inwin.groupby(['cp', 'sgn']): roles4[(cp, int(sg))] = True
                a0 = short_units_at(c.und, c.expiry, w0m); a1 = short_units_at(c.und, c.expiry, w1)
                stopped = (c.und, c.expiry) in stops.index and stops.loc[(c.und, c.expiry)] < w0m
                n_other = int(((sh.module != 'num')).sum()); activity = sess[(sess.t_fill >= t - pd.Timedelta(minutes=30)) & (sess.t_fill <= t + pd.Timedelta(minutes=30)) & ~((sess.t_fill >= w0) & (sess.t_fill < w1))]
                have_bars = all(pd.Timestamp(x) in bars.get((c.und, d), set()) for x in pd.date_range(w0m - pd.Timedelta(minutes=60), w0m - pd.Timedelta(minutes=1), freq='min'))
                any_new_short = len(sh) > 0; cls = ('ACTION_BODY' if len(shb) else ('ACTION_OTHER_MODULE_ONLY' if len(sh) else None))
                if cls is None:
                    if stopped or t < first_fill - pd.Timedelta(minutes=0) and w0m < first_fill.floor('min') or (kind == 'D0' and a0 <= 0): cls = 'NOT_APPLICABLE'
                    elif len(activity) and have_bars: cls = 'NO_ACTION_ACTIVE'
                    else: cls = 'NO_ACTION_UNCERTAIN'
                rows.append(dict(cycle=c.cycle, und=c.und, expiry=c.expiry, kind=kind, window=str(T).split(' ')[-1][:5], control_window=T in ctrl, cls=cls, any_new_short=any_new_short, body_short=len(shb) > 0, paired_same_strike=paired,
                                 partial=(len(shb) > 0 and not paired), new_short_base_units=float((shb.open_qty / shb.base).sum()), four_roles=all(roles4.values()), net_short_growth=(a1 > a0), short_units_before=a0, short_units_after=a1, other_module_short=n_other, n_short_parents=shb.parent_oid.nunique()))
W = pd.DataFrame(rows); W.to_csv(os.path.join(OUT, 'phase0_window_level_counts.csv'), index=False)
# ---------------- table 1: reconciliation of 544 / 529
def summ(d):
    return pd.Series(dict(session_windows=len(d), any_new_short_any_module=int(d.any_new_short.sum()), body_new_short=int(d.body_short.sum()), paired_same_strike=int(d.paired_same_strike.sum()), partial_body_short=int(d.partial.sum()),
                          four_roles=int(d.four_roles.sum()), net_short_growth=int(d.net_short_growth.sum()), ACTION_BODY=int((d.cls == 'ACTION_BODY').sum()), ACTION_OTHER_MODULE_ONLY=int((d.cls == 'ACTION_OTHER_MODULE_ONLY').sum()),
                          NO_ACTION_ACTIVE=int((d.cls == 'NO_ACTION_ACTIVE').sum()), NO_ACTION_UNCERTAIN=int((d.cls == 'NO_ACTION_UNCERTAIN').sum()), NOT_APPLICABLE=int((d.cls == 'NOT_APPLICABLE').sum())))
P = W[W.kind == 'PRE']; T1 = pd.concat({'PRE registered 17 windows': summ(P[~P.control_window]), 'PRE 4 control windows (12:15 12:45 13:00 13:15)': summ(P[P.control_window]), 'PRE all 21 candidate windows': summ(P), 'D0 15-minute windows 09:30-15:00': summ(W[W.kind == 'D0'])}, axis=1).T
T1.to_csv(os.path.join(OUT, 'phase0_table1_window_reconciliation.csv'))
# per-window and per-underlying detail for the registered windows
P.groupby(['window', 'control_window']).apply(summ, include_groups=False).to_csv(os.path.join(OUT, 'phase0_pre_window_detail.csv'))
# ---------------- table 2: attribution classes (order-entry minute vs the window)
att = []
for kind, wins in (('PRE', PRE), ('D0', D0W)):
    for c in cycles.itertuples():
        d = c.first if kind == 'PRE' and c.has_pre else (c.expiry if kind == 'D0' and c.has_d0 else None)
        if d is None: continue
        body = OP[(OP.und == c.und) & (OP.expiry == c.expiry) & (OP.date == d) & (OP.sgn < 0) & (OP.module == 'num')]
        par = body.groupby('parent_oid').agg(E=('order_entry_minute', 'first'), first_fill=('t_fill', 'min'), n=('src_row', 'size'))
        for T in wins:
            t = d + T; w0, w1 = t - B0, t + B1; w0m = w0.floor('min'); w1m = w1.floor('min')
            fi = par[(par.first_fill >= w0) & (par.first_fill < w1)]
            for p, r in fi.iterrows():
                cl = 'SUBMITTED_BEFORE_WINDOW' if r.E < w0m else ('AMBIGUOUS_BOUNDARY_MINUTE' if r.E == w0m else 'ENTERED_INSIDE_WINDOW'); att.append(dict(kind=kind, view='fill inside window', cls=cl, window=str(T)[-8:-3]))
            de = par[(par.E > w0m) & (par.E < w1m) & ~((par.first_fill >= w0) & (par.first_fill < w1))]
            for p, r in de.iterrows(): att.append(dict(kind=kind, view='entered inside window, first fill outside', cls='DECISION_IN_WINDOW_FILL_OUTSIDE', window=str(T)[-8:-3]))
A = pd.DataFrame(att); T2 = A.groupby(['kind', 'view', 'cls']).size().rename('parent_orders').reset_index(); T2['share_within_view'] = T2.parent_orders / T2.groupby(['kind', 'view']).parent_orders.transform('sum'); T2.to_csv(os.path.join(OUT, 'phase0_table2_attribution_classes.csv'), index=False)
# ---------------- table 3: which modules open inventory
OP['in_any_window'] = False
for kind, wins in (('PRE', PRE + CTRL), ('D0', D0W)):
    for c in cycles.itertuples():
        d = c.first if kind == 'PRE' and c.has_pre else (c.expiry if kind == 'D0' and c.has_d0 else None)
        if d is None: continue
        m = (OP.und == c.und) & (OP.expiry == c.expiry) & (OP.date == d)
        for T in wins: t = d + T; OP.loc[m & (OP.t_fill >= t - B0) & (OP.t_fill < t + B1), 'in_any_window'] = True
OP['day_type'] = np.where(OP.date == OP.expiry, 'D0', 'pre-expiry')
T3 = OP.groupby(['day_type', 'side', 'module']).agg(fills=('src_row', 'size'), parent_orders=('parent_oid', 'nunique'), units=('open_qty', 'sum'), share_fills_inside_candidate_windows=('in_any_window', 'mean')).reset_index(); T3.to_csv(os.path.join(OUT, 'phase0_table3_opening_modules.csv'), index=False)
# ---------------- table 4: is each registered permutation design non-degenerate?
rows = []
def design(name, g, outcome, kind):
    for und, x in g.groupby('und'):
        ncyc = x.cycle.nunique(); o = x[outcome]; vals = o.nunique()
        nonconst = int(x.groupby('window')[outcome].nunique().gt(1).sum()); minority = int(min(o.sum(), len(o) - o.sum())) if o.dtype == bool else np.nan
        rows.append(dict(design=name, outcome=outcome, und=und, cycles=ncyc, windows=x.window.nunique(), observations=len(x), distinct_outcome_values=vals, windows_with_nonconstant_outcome=nonconst, minority_class_events=minority,
                         obs_per_stratum_if_cycle_x_window=1, obs_per_stratum_if_und_x_window=round(len(x) / max(x.window.nunique(), 1), 1), log10_distinct_cycle_block_permutations=round(math.lgamma(ncyc + 1) / math.log(10), 1)))
Pall = W[W.kind == 'PRE']; Preg = Pall[~Pall.control_window]; D0a = W[(W.kind == 'D0') & (W.cls != 'NOT_APPLICABLE')]
design('E2 action: D-1 registered 17 windows only', Preg, 'body_short', 'PRE'); design('E2 action: D-1 all 21 candidate windows', Pall, 'body_short', 'PRE'); design('E2 action: expiry-day applicable windows', D0a, 'body_short', 'D0')
design('E3 quantity (base units): D-1 registered 17 windows', Preg.assign(q=Preg.new_short_base_units), 'q', 'PRE'); design('E3 quantity (base units): expiry-day action windows', D0a[D0a.body_short].assign(q=D0a[D0a.body_short].new_short_base_units), 'q', 'D0')
T4 = pd.DataFrame(rows); T4.to_csv(os.path.join(OUT, 'phase0_table4_permutation_design.csv'), index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print(T1.T.to_string()); print(T2.to_string(index=False)); print(T3.to_string(index=False)); print(T4.to_string(index=False))
