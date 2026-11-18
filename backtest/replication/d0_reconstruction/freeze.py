"""Freeze rule set D0-v1: hash code + rules + discovery event table, write FREEZE.json. After this file exists the holdout can be loaded (d0common.load_events(False))."""
import hashlib, json, datetime
from d0common import *
def h(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
files = {n: h(os.path.join(DHERE, n)) for n in ['d0_sim.py', 'compare_events.py', 'fit_discovery.py', 'build_events.py', 'PREREGISTRATION_D0_v1.md']}; files['results/rules_d0_v1.json'] = h(f'{RES}/rules_d0_v1.json'); files['results/d0_events.csv'] = h(f'{RES}/d0_events.csv'); files['../rules.py'] = h(os.path.join(REPL, 'rules.py'))
json.dump(dict(frozen_at_utc=datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds'), rule_set='D0-v1', holdout_start='2026-09-23', hashes=files, pass_criterion='L2 precision >= 0.5 and L2 recall >= 0.5 and better than NULL', note='holdout partially exposed (see PREREGISTRATION_D0_v1.md)'), open(f'{RES}/FREEZE.json', 'w'), indent=1); print(open(f'{RES}/FREEZE.json').read())
