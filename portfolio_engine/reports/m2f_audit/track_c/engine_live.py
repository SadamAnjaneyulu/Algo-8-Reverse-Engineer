"""Run the engine live on the full ledger (read-only), cache results as pickle in scratch.  [REPRO] + perturbation tests.  Never writes inside the repo except track_c."""
import sys, os, pickle, time, copy
REPO = '/home/user/Algo-8-Reverse-Engineer'; sys.path.insert(0, REPO + '/portfolio_engine/python')
SCR = '/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_c/'
from pe.schema import *
from pe.lineage_set import LineageSet
from pe import wing_body as wb
from pe.generators import historical as H
def load():
    ins, fills, src = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); rows = H.generate_parents(REPO, ls.roles); meta = {r['parent_order_id']: r for r in rows}; return ins, fills, ls, meta
def sig(R):
    return {m: sorted((l['link_id'], l['dt_s'], l['wing_qty'], l['body_qty'], l.get('weight'), l.get('queue_matched_units'), l.get('nearest'), l.get('nearest_tied'), l.get('link_status'), l.get('in_primary_candidate_set')) for l in v) for m, v in R.links.items()}
if __name__ == '__main__':
    t = time.time(); ins, fills, ls, meta = load(); print('load', time.time() - t)
    R = wb.analyse(ls, meta); print('analyse', time.time() - t); base = sig(R)
    # perturbation 1: drop all app keys; perturbation 2: scramble app keys (alternate); perturbation 3: swap every app key to the other key
    res = {}
    for name, fn in (('none', lambda m: dict(m, app_key_last6=None)), ('swap', lambda m: dict(m, app_key_last6='F88187' if m['app_key_last6'] == '632469' else '632469')), ('all_second', lambda m: dict(m, app_key_last6='F88187')), ('conflict', lambda m: dict(m, app_key_last6='XXXXXX'))):
        meta2 = {k: fn(v) for k, v in meta.items()}; R2 = wb.analyse(ls, meta2); s2 = sig(R2); res[name] = {m: s2[m] == base[m] for m in base}; print(name, res[name])
    pickle.dump(dict(res=res), open(SCR + 'perturb.pkl', 'wb'))
