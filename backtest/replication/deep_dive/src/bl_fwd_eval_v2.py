"""Forward-test evaluation harness v2 (audit of 2026-11-24). v1 (bl_fwd_eval.py) is kept unchanged for the record; its defects are listed in reports/OVERFITTING_AUDIT.md.
What v2 fixes, WITHOUT touching the frozen rule, score, features or endpoint:
  * verifies the frozen hashes before computing anything (rule config, score, and the four frozen files);
  * assigns every cycle a role (development / regime-A forward / burn-in / confirmatory / beyond protocol) from its D-1 date, chronologically, and evaluates the primary endpoint ONLY on confirmatory cycles;
  * uses the Pocock-adjusted interval level at every look (v1 used 95%), with both the cluster bootstrap and the linearised cluster-robust interval reported;
  * de-duplicates real orders, counts rows lost to missing bars (and positives among them) instead of dropping them silently;
  * builds the regime-B clock table from burn-in cycles only, refuses to overwrite it once frozen, and records its hash;
  * labels every output block 'confirmatory' or 'exploratory'.
Nothing is fitted here: the logistic coefficients come from frozen_model.json and are never refitted."""
import sys, os, json, glob, hashlib, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/d1_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_validation as V
from bl_fwd_eval import frozen_score, decision_metrics, strike_size
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(f'{HERE}/../../../..'); FW = f'{HERE}/../outputs/fwd'
SELL_ROLES = ('', 'open_short', 'body_sell', 'ladder_solo', 'scheduled_straddle', 'breakout_straddle', 'breakout_extra')


def load_config(path=None): return json.load(open(path or f'{HERE}/../validation_config.json'))


def verify_frozen(cfg):
    """raises AssertionError if anything frozen has changed"""
    from d1_algo.shadow import LateRuleConfig
    from dataclasses import asdict
    f = cfg['frozen']; assert LateRuleConfig().sha() == f['rule_sha256'], 'rule config hash changed'; assert asdict(LateRuleConfig()) == f['rule_config'], 'rule config fields changed'
    m = json.load(open(f'{FW}/frozen_model.json')); m2 = {k: v for k, v in m.items() if k != 'sha256_of_above'}
    assert V.sha256_json(m2) == m['sha256_of_above'] == f['model_sha256'], 'frozen score changed'
    assert m['features'] == f['model_features'] and m['coef'] == f['model_coef'] and m['intercept'] == f['model_intercept'], 'frozen coefficients changed'
    for rel, h in f['file_sha256'].items(): assert hashlib.sha256(open(f'{ROOT}/{rel}', 'rb').read()).hexdigest() == h, f'frozen file changed: {rel}'
    return True


def regime_of(d1, cfg):
    o = cfg['original_protocol']; return 'development' if d1 < o['freeze_date'] else ('A' if d1 < o['regime_B_start'] else 'B')


def load_rows(log_dir, model, tables_by_regime, cfg):
    """-> orders (deduplicated), fires, primary rows (cycle x minute x side), per-cycle data-quality table. Rows are built only where bars exist; every loss is counted."""
    W0, W1 = model['window']; orders, fires, rows, dq = [], [], [], []
    for fo in sorted(glob.glob(f'{log_dir}/orders_*.jsonl')):
        tag = os.path.basename(fo)[len('orders_'):-len('.jsonl')]; und, d1 = tag.rsplit('_', 1); cyc = f'{und}|{d1}'; reg = regime_of(d1, cfg); step = 50.0 if und == 'NIFTY' else 100.0
        O = [json.loads(x) for x in open(fo)]; Mn = [json.loads(x) for x in open(f'{log_dir}/minutes_{tag}.jsonl')]
        sells = [o for o in O if o['side'] == 'sell' and o.get('role', '') in SELL_ROLES]; raw = pd.DataFrame([dict(cyc=cyc, order_id=str(o.get('order_id', '')), ts=o['ts'], j=o['j'], cp=o['right'], strike=o['strike'], lots=o['lots'], px=o['price'], proposed_strike=o['rule'].get('proposed_strike'), last_strike=o.get('last_sale_strike_same_side'), step=step) for o in sells])
        n_raw = len(raw); raw, n_dup = V.dedupe_orders(raw) if n_raw else (raw, 0)
        if len(raw): raw = raw.assign(und=und, d1=d1, regime=reg); orders.append(raw)
        fut = {m['j']: m['fut'] for m in Mn if m.get('fut')}; tab = tables_by_regime.get(reg)
        for m in Mn:
            for f in m['rule']['fires_this_minute']: fires.append(dict(cyc=cyc, und=und, d1=d1, regime=reg, j=f['minute'], cp=f['right'], lots=f['lots']))
        keep_orders = raw[(raw.j >= W0) & (raw.j <= W1)] if len(raw) else raw; y_cells = {(int(j), c) for j, c in zip(keep_orders.j, keep_orders.cp)} if len(keep_orders) else set(); built = 0; lost_pos = 0; expected = (W1 - W0 + 1) * 2
        for j in range(W0, W1 + 1):
            for side in ('CE', 'PE'):
                ok = j in fut and all(k in fut for k in range(j - 5, j)) and tab is not None
                if not ok:
                    lost_pos += int((j, side) in y_cells); continue
                sg = -1 if side == 'CE' else 1; lo5 = [fut[k][2] for k in range(j - 5, j)]; hi5 = [fut[k][1] for k in range(j - 5, j)]
                rows.append(dict(cyc=cyc, und=und, d1=d1, regime=reg, j=j, side=side, y=int((j, side) in y_cells), FUT_ext5=float((fut[j][2] < min(lo5)) if side == 'CE' else (fut[j][1] > max(hi5))), FUT_mv1=sg * (fut[j][3] - fut[j - 1][3]) / step, clock=tab[f'{j}|{side}'])); built += 1
        dq.append(dict(cyc=cyc, d1=d1, regime=reg, orders_raw=n_raw, orders_duplicates_removed=n_dup, rows_expected=expected, rows_built=built, rows_missing=expected - built, positives_lost_to_missing=lost_pos, share_rows=built / expected))
    cat = lambda L: pd.concat(L, ignore_index=True) if L else pd.DataFrame()
    return cat(orders), pd.DataFrame(fires), pd.DataFrame(rows), pd.DataFrame(dq)


def build_regime_B_table(orders_burnin, burnin_cycles):
    """share of burn-in cycles with at least one real sale in each (minute, side) cell; uses burn-in cycles only"""
    n = len(burnin_cycles); t = {}
    for j in range(360, 385):
        for s in ('CE', 'PE'):
            c = orders_burnin[(orders_burnin.j == j) & (orders_burnin.cp == s)].cyc.nunique() if len(orders_burnin) else 0; t[f'{j}|{s}'] = c / n
    return t


def freeze_regime_B_table(table, path=None, burnin_cycles=()):
    path = path or f'{FW}/regimeB_clock_table.json'
    if os.path.exists(path): raise FileExistsError('regime-B clock table is already frozen; refusing to overwrite')
    rec = dict(table=table, burnin_cycles=list(burnin_cycles), sha256=V.sha256_json(table)); json.dump(rec, open(path, 'w'), indent=1, sort_keys=True); return rec['sha256']


def primary_at_look(rows, model, cfg, look, B=4000, seed=0):
    """confirmatory primary endpoint on the given rows (already restricted to confirmatory cycles up to this look)"""
    K = len(cfg['original_protocol']['confirmatory']['looks_cumulative']); nominal = V.pocock_nominal(K, cfg['original_protocol']['alpha_two_sided_overall']); level = 1 - nominal
    T = rows.copy().reset_index(drop=True); T['score'] = frozen_score(T, model); T['base'] = T.clock; C = V.components(T, ['score', 'base']); est = V.delta_from(C, 'score', 'base'); rng = np.random.default_rng(seed)
    bl, bh = V.boot_ci(C, 'score', 'base', level, B, rng); ll, lh, se = V.lin_ci(C, 'score', 'base', level)
    return dict(evidence='confirmatory', look=look, K=K, nominal_alpha_per_look=nominal, ci_level=level, cycles=int(len(C)), effective_cycles=V.effective_cycles(C), events=int(T.y.sum()), negatives=int((1 - T.y).sum()),
                auc_model=V.auc_from(C, 'score'), auc_clock=V.auc_from(C, 'base'), delta=est, boot_ci=[bl, bh], linearised_ci=[ll, lh], se_linearised=se, leave_one_cycle_out=V.leave_one_cycle_out(C, 'score', 'base'),
                decision_bootstrap=V.sequential_decision(look, K, est, bl), decision_linearised=V.sequential_decision(look, K, est, ll))


def evaluate_confirmatory(log_dir, cfg=None, look=1, tables=None):
    """full v2 evaluation. Returns a dict; the 'primary' block is computed on confirmatory cycles only."""
    cfg = cfg or load_config(); verify_frozen(cfg); model = json.load(open(f'{FW}/frozen_model.json')); tabs = {'A': model['clock_table'], 'development': model['clock_table']}
    bpath = f'{FW}/regimeB_clock_table.json'
    if tables is not None: tabs.update(tables)                                    # tests / dry runs supply tables explicitly and never touch the frozen file
    elif os.path.exists(bpath): tabs['B'] = json.load(open(bpath))['table']
    orders, fires, rows, dq = load_rows(log_dir, model, tabs, cfg)
    allc = pd.concat([x[['cyc', 'd1']] for x in (orders, fires, rows, dq) if len(x)]).drop_duplicates('cyc') if any(len(x) for x in (orders, fires, rows, dq)) else pd.DataFrame(columns=['cyc', 'd1'])
    roles = V.assign_roles(allc.assign(d1=allc.d1), dict(freeze_date=cfg['original_protocol']['freeze_date'], regime_B_start=cfg['original_protocol']['regime_B_start'], burn_in_cycles=cfg['original_protocol']['burn_in_cycles'], confirmatory=cfg['original_protocol']['confirmatory'])); V.assert_chronological_disjoint(roles)
    out = dict(roles=roles.to_dict('records'), data_quality=dq.to_dict('records') if len(dq) else [], frozen_verified=True)
    conf = roles[(roles.role == 'confirmatory') & (roles.look <= look)].cyc.tolist(); out['n_confirmatory_cycles_used'] = len(conf); need = cfg['original_protocol']['confirmatory']['looks_cumulative'][look - 1]
    if len(conf) < need: out['primary'] = None; out['status'] = f'not_ready: look {look} needs {need} confirmatory cycles, have {len(conf)}; the primary endpoint is not computed early (no peeking)'; return out
    if len(conf) and len(rows) and 'B' in tabs:
        r = rows[rows.cyc.isin(conf)]; o = orders[orders.cyc.isin(conf)] if len(orders) else orders; f = fires[fires.cyc.isin(conf)] if len(fires) else fires
        out['primary'] = primary_at_look(r, model, cfg, look)
        out['secondary_exploratory'] = dict(evidence='exploratory', decision=decision_metrics(o, f) if len(o) else None, strike_size=strike_size(o, f) if len(o) else None)
    else: out['primary'] = None
    return out
