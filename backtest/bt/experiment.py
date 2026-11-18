"""Configuration grid, parallel engine runs (Python + C++ on the same text) and accounting."""
import os, pickle, sys
from functools import lru_cache
from multiprocessing import Pool
import pandas as pd
from . import config as C, cycles as Cy, scen, account as A
RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results'); ENG = os.path.join(RES, 'engine')
VARIANTS = ('HOLD_SETTLE', 'FLATTEN_1525')


def grid():
    """PRE-REGISTERED configuration grid (see PREREGISTRATION.md). Names are stable ids."""
    g = {'HOLD': dict(cut=None, reentry=None, stop=False)}
    cuts = {}
    for trig in (5000, 10000, 20000):
        for frac in (10000, 5000):
            cuts[f't{trig}_f{frac}'] = dict(policy='MARK_ADVERSE_MOVE', trigger_bp=trig, leg_side_filter='SHORT', scope='LEG', qty_mode='FRACTION_BP', fraction_bp=frac, max_cuts_per_leg=1)
    res = {'none': None, 'cd1800': dict(cooldown_s=1800, price_condition='NONE'), 'cd1800band': dict(cooldown_s=1800, price_condition='WITHIN_BAND', band_bp=2000)}
    for cn, cc in cuts.items():
        for rn, rc in res.items(): g[f'cut_{cn}_re_{rn}'] = dict(cut=cc, reentry=rc, stop=False)
    g['STOP_ONLY'] = dict(cut=None, reentry=None, stop=True)
    for cn, cc in cuts.items(): g[f'cut_{cn}_re_none_STOP'] = dict(cut=cc, reentry=None, stop=True)
    return g


def stop_cfg(c, lots):
    inv = {l: c['legs'][l]['side'] * lots * scen.lot_of(c) for l in c['legs']}; ml = A.max_loss(c, inv)
    return dict(phase_switch_ts=scen.epoch(c['d0'], '09:15'), carry_limit_paise=int(0.04 * ml * 100), expiry_limit_paise=int(0.01 * C.CAPITAL_RS * 100))


def cfg_for(spec, c, lots):
    return dict(cut=spec['cut'], reentry=spec['reentry'], stop=stop_cfg(c, lots) if spec['stop'] else None)


@lru_cache(maxsize=512)
def _cyc(und, expiry): return Cy.load(und, expiry)


def _job(a):
    name, spec, variant, und, expiry, lots, check, drop, dseed = a; c = _cyc(und, expiry)
    r = scen.run(c, cfg_for(spec, c, lots), variant, lots, check_cpp=check, drop_frac=drop, drop_seed=dseed)
    return (und, expiry), dict(fills=r['fills'], parity=r['parity'], parity_detail=r.get('parity_detail', ''), summary=r['files']['summary.tsv'], actions=r['files']['actions.tsv'], decisions_n=r['files']['decisions.tsv'].count('\n'))


def usable():
    cyc = Cy.cycle_list(); return cyc[(cyc.status == 'Complete') & cyc.split.isin(['IS', 'OOS'])].reset_index(drop=True)


def run_engine(names, variant, cyc=None, lots=3, check=True, drop=0.0, dseed=0, tag='', procs=4, force=False):
    """engine stage: writes results/engine/<variant><tag>/<name>.pkl = {(und, expiry): {...}}; skips existing files unless force"""
    g = grid(); cyc = usable() if cyc is None else cyc; out = os.path.join(ENG, variant + tag); os.makedirs(out, exist_ok=True)
    with Pool(procs) as p:
        for n in names:
            f = os.path.join(out, n + '.pkl')
            if os.path.exists(f) and not force:
                done = pickle.load(open(f, 'rb'))
                if all((r.und, r.expiry) in done for r in cyc.itertuples()): continue
            jobs = [(n, g[n], variant, r.und, r.expiry, lots, check, drop, dseed) for r in cyc.itertuples()]
            pickle.dump(dict(p.imap_unordered(_job, jobs, chunksize=4)), open(f, 'wb'))
    return out


def load_engine(name, variant, tag=''): return pickle.load(open(os.path.join(ENG, variant + tag, name + '.pkl'), 'rb'))


def account_all(name, variant, params, cyc=None, tag='', lots=3):
    """accounting stage -> DataFrame, one row per cycle"""
    eng = load_engine(name, variant, tag); cyc = usable() if cyc is None else cyc; rows = []
    for r in cyc.itertuples():
        e = eng[(r.und, r.expiry)]; c = _cyc(r.und, r.expiry); a = A.account(c, e['fills'], variant, params)
        rows.append(dict(und=r.und, expiry=r.expiry, d1=r.d1, d0=r.d0, split=r.split, subset=r.subset, gross=a['gross'], net=a['net'], slippage=a['slippage'], costs=a['costs'], n_orders=a['n_orders'], n_engine_orders=a['n_engine_orders'], peak_margin=a['peak_margin'],
                         min_path=a['min_path'], max_path=a['max_path'], path=a['path'], leg_pnl=a['leg_pnl'], trades=a['trades'], settle=a['settle'], close_src=a['official_close_src'], d1_range=float(c['spot_d1'].close.max() - c['spot_d1'].close.min()), parity=e['parity'], K=c['K'], official_close=c['official_close'], lot=scen.lot_of(c), spot_0915=c['spot_0915']))
    return pd.DataFrame(rows)
