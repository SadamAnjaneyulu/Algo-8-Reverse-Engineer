"""M2-C acceptance addendum data: longest-chain examples per threshold and the exact membership differences produced by the two open rules (tie-break, C2 predecessor reference). Read-only: no committed M2-C output is changed.
python3 portfolio_engine/tools/m2c_addendum.py -> reports/m2c_addendum.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe.schema import *
from pe.lineage_set import LineageSet
from pe import closing_batches as cb
from pe.generators import historical as H
ins, fills, _ = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); parents, un, multi = cb.closing_parents(ls); V = cb.all_views(parents)
hhmm = lambda t: pd_t(t)
def pd_t(t): s = (t + IST_OFFSET_S) % 86400; return f'{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}'
def describe(b, view):
    rec = cb.batch_record(b, view, ls); return dict(batch_id=rec['batch_id'], parents=rec['n_parents'], closing_portions=rec['n_closing_portions'], units=rec['total_closing_qty'], contracts=rec['n_contracts'], right_class=rec['right_class'], start=pd_t(rec['start_ts']), end=pd_t(rec['end_ts']),
                                                    duration_s=rec['duration_s'], max_link_gap_s=rec['max_link_gap_s'], session=rec['session'], roles=rec['roles'])
OUT = dict(longest_chains={}, alternative_rule_membership_differences=[])
for g in cb.THRESHOLDS:
    v = V[('C1', g)]; top = sorted(v['batches'], key=lambda b: -(max(p.last_ts for p in b['members']) - min(p.first_ts for p in b['members'])))[:3]; OUT['longest_chains'][str(g)] = [describe(b, v) for b in top]
for g in (2, 5, 10):
    base = cb.member_sets(V[('C2', g)]); named = {}
    for label, kw in (('tie_break_by_parent_id', dict(order='parent_id')), ('predecessor_reference_running_max', dict(c2_ref='running_max'))):
        alt = cb.build_view(parents, 'C2', g, **kw); a = cb.member_sets(alt); only_base = base - a; only_alt = a - base
        by = {p.key: p for p in parents}
        OUT['alternative_rule_membership_differences'].append(dict(threshold_s=g, alternative=label, approved_batches=len(base), alternative_batches=len(a), batches_only_in_approved=[[dict(parent=k[0], session=k[3], first_ts=pd_t(by[k].first_ts), last_ts=pd_t(by[k].last_ts), und=k[1]) for k in sorted(s, key=lambda k: (by[k].first_ts, by[k].parent_id))] for s in sorted(only_base, key=lambda s: sorted(s))],
                                                                  batches_only_in_alternative=[[k[0] for k in sorted(s, key=lambda k: (by[k].first_ts, by[k].parent_id))] for s in sorted(only_alt, key=lambda s: sorted(s))]))
json.dump(OUT, open(os.path.join(PE, 'reports', 'm2c_addendum.json'), 'w'), indent=1)
for g, rows in OUT['longest_chains'].items(): print(g, [(r['parents'], r['duration_s'], r['contracts'], r['session']) for r in rows])
for d in OUT['alternative_rule_membership_differences'][:2]: print(d['threshold_s'], d['alternative'], d['approved_batches'], d['alternative_batches'], [len(x) for x in d['batches_only_in_approved']], d['batches_only_in_alternative'])
