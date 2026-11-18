"""Mutation testing of the new plugin layer. Each mutant changes one rule in a COPY of this directory; a mutant is KILLED only when a test ASSERTION fails
(an import error, crash or collection error is reported as ERROR and does not count). Survivors are listed, not hidden.
  python3 tools/mutation_harness.py [--out mutation_results.json] [--only py|cpp]"""
import json, os, shutil, subprocess, sys, tempfile, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'python'))
from pc._hist import HIST_PATH

PY = [   # (id, file, old, new, what it breaks)
 ('P01', 'python/pc/risk.py', "    if action.action_id in b.seen_ids: return DUPLICATE_ACTION_ID, action.action_id\n", "", 'duplicate action ids no longer rejected'),
 ('P02', 'python/pc/risk.py', "    if action.info_ts > action.ts: return LOOKAHEAD_VIOLATION", "    if False: return LOOKAHEAD_VIOLATION", 'information newer than the action time is accepted'),
 ('P03', 'python/pc/risk.py', "    if action.ts != now: return STALE_ACTION_TIMESTAMP", "    if False: return STALE_ACTION_TIMESTAMP", 'back-dated actions accepted'),
 ('P04', 'python/pc/risk.py', "        if action.qty > leg.current: return INSUFFICIENT_INVENTORY", "        if False: return INSUFFICIENT_INVENTORY", 'cut larger than the leg accepted'),
 ('P05', 'python/pc/risk.py', "    if g1 > limits['max_gross_units'] and g1 > g0:", "    if g1 > limits['max_gross_units']:", 'de-risking blocked when already above the gross limit'),
 ('P06', 'python/pc/risk.py', "    if s1 > limits['max_short_units'] and s1 > s0: return EXPOSURE_LIMIT_EXCEEDED", "    if False: return EXPOSURE_LIMIT_EXCEEDED", 'short-unit limit ignored'),
 ('P07', 'python/pc/risk.py', "        if cut is None or cut.basket_id != action.basket_id or cut.leg_id != action.leg_id: return INVALID_CUT_LINEAGE", "        if cut is None: return INVALID_CUT_LINEAGE", 'a cut of another basket or leg can be used as lineage'),
 ('P08', 'python/pc/risk.py', "        if action.ts < cut.ts + limits['reentry_min_cooldown_s']: return COOLDOWN_NOT_ELAPSED", "        if action.ts < cut.ts + 0: return COOLDOWN_NOT_ELAPSED", 'validator cooldown ignored'),
 ('P09', 'python/pc/risk.py', "if cut.reentered + action.qty > cut.qty or", "if cut.reentered + action.qty > cut.qty + 65 or", 're-entry may exceed the cut quantity'),
 ('P10', 'python/pc/risk.py', "    if action.plugin != producer.name or action.version != producer.version: return PLUGIN_MISMATCH", "    if False: return PLUGIN_MISMATCH", 'plugin may act under another plugin\'s name'),
 ('P11', 'python/pc/risk.py', "    if action.qty <= 0 or action.qty % lot != 0: return INVALID_QUANTITY", "    if action.qty <= 0: return INVALID_QUANTITY", 'non-lot quantities accepted'),
 ('P12', 'python/pc/engine.py', "    def _reconcile(self):\n", "    def _reconcile(self):\n        return\n", 'ledger/claims reconciliation disabled'),
 ('P13', 'python/pc/engine.py', "            if failed is not None: reasons.append((R.GROUP_REJECTED, f'group member {failed[0]} failed')); continue", "            if False: continue", 'group atomicity broken (later members of a failed group still validated)'),
 ('P14', 'python/pc/engine.py', "px = m[0] if m else leg.last_price", "px = leg.last_price", 'fills ignore the mark'),
 ('P15', 'python/pc/engine.py', "side = -leg.side if a.type == 'CUT' else leg.side; self._pc += 1", "side = leg.side; self._pc += 1", 'cut fills have the wrong side'),
 ('P16', 'python/pc/model.py', "            k = bisect.bisect_right(t, ts)\n            if k: d[iid]", "            k = bisect.bisect_right(t, ts + 600)\n            if k: d[iid]", 'marks up to 600 s in the future are placed in the plugin context'),
 ('P17', 'python/pc/model.py', "        if t > self.ts: raise LookAheadError", "        if False: raise LookAheadError", 'context no longer refuses future timestamps'),
 ('P18', 'python/pc/plugins/cut.py', "return ((lots * c['fraction_bp'] + 5000) // 10000) * lot", "return ((lots * c['fraction_bp'] + 0) // 10000) * lot", 'fractional cuts round down instead of to the nearest lot'),
 ('P19', 'python/pc/plugins/cut.py', "hit = px * 10000 >= l.entry_price * (10000 + c['trigger_bp']) if l.side < 0", "hit = px * 10000 > l.entry_price * (10000 + c['trigger_bp']) if l.side < 0", 'trigger boundary (>=) changed to >'),
 ('P20', 'python/pc/plugins/reentry.py', "if ts < cut.ts + c['cooldown_s']:", "if ts <= cut.ts + c['cooldown_s']:", 'cooldown boundary changed'),
 ('P21', 'python/pc/plugins/reentry.py', "abs(px - cut.price) * 10000 > c['band_bp'] * cut.price", "abs(px - cut.price) * 10000 >= c['band_bp'] * cut.price", 'price band boundary changed'),
 ('P22', 'python/pc/plugins/reentry.py', "((cut.qty // lot) * c['max_reentry_fraction_bp'] // 10000) * lot - cut.reentered", "((cut.qty // lot) * 10000 // 10000) * lot - cut.reentered", 'max re-entry fraction ignored'),
 ('P23', 'python/pc/registry.py', "        if plugin.name in self._items: raise RegistryError('DUPLICATE_NAME', plugin.name)\n", "", 'duplicate plugin names accepted'),
 ('P24', 'python/pc/registry.py', "        if plugin.api_version != self.api_version: raise", "        if False: raise", 'incompatible API versions accepted'),
 ('P25', 'python/pc/scenario.py', "        if meta.get('evidence') != EVIDENCE: raise", "        if False: raise", 'scenario need not be marked synthetic'),
 ('P26', 'python/pc/scenario.py', "        s.seeds.sort(key=lambda d: (d['ts'], d['fill_id']));", "        pass;", 'seed order depends on file order'),
 ('P27', 'python/pc/model.py', "        if any(l.current != l.initial for l in legs): return PARTIALLY_CUT", "        if False: return PARTIALLY_CUT", 'PARTIALLY_CUT status never reported'),
 ('P28', 'python/pc/contract.py', "';'.join(f'{k}={self.config[k]}' for k in sorted(self.config))", "';'.join(f'{k}={self.config[k]}' for k in self.config)", 'config hash depends on key order'),
 ('P29', 'python/pc/engine.py', "        proj = R.Projection(self.book); inv = self._inv()", "        proj = R.Projection(self.book); proj.book = self.book; inv = self._inv()", 'validation writes into the real book'),
 ('P30', 'python/pc/engine.py', "(proj.book.cut(a, ts, 0, '-') if a.type == 'CUT' else proj.book.reenter(a))", "pass", 'projection ignores earlier actions of the same group'),

 ('P31', 'python/pc/scenario.py', "    if v < lo or v > hi: raise ScenarioError", "    if False: raise ScenarioError", 'integer ranges not enforced by the loader'),
 ('P32', 'python/pc/engine.py', "        if res.status not in ('OK', 'NO_ACTION', 'ERROR') or not isinstance(res.actions, list)", "        return False\n        if res.status not in ('OK', 'NO_ACTION', 'ERROR') or not isinstance(res.actions, list)", 'plugin output is not validated'),
 ('P33', 'python/pc/model.py', "            k = bisect.bisect_right(t, ts)\n            if k: d[iid]", "            k = len(t)\n            if k: d[iid]", 'the whole mark series is placed in the plugin context'),
 ('P34', 'python/pc/plugins/reentry.py', "|REENTRY|{cut.cut_id}'", "|REENTRY'", 're-entry action ids can collide for two cuts of one leg'),
 ('P35', 'python/pc/engine.py', "px = m[0] if m else leg.last_price", "px = m[0] if m else leg.entry_price", 'a fill without a mark uses the (non-tick) entry price'),
 ('P36', 'python/pc/scenario.py', "            if a['ts'] not in s.ticks: raise ScenarioError", "            if False: raise ScenarioError", 'ACTION lines at non-tick times are accepted'),
 ('P37', 'python/pc/plugins/cut.py', "px * 10000 <= l.entry_price * (10000 - c['trigger_bp'])", "px * 10000 < l.entry_price * (10000 - c['trigger_bp'])", 'long-leg trigger boundary changed'),
 ('P38', 'python/pc/plugins/reentry.py', "if c['max_wait_s'] and ts > cut.ts + c['max_wait_s']:", "if c['max_wait_s'] and ts >= cut.ts + c['max_wait_s']:", 'max_wait window boundary changed'),
 ('P39', 'python/pc/plugins/cut.py', "(lots * c['fraction_bp'] + 5000) // 10000", "(lots * c['fraction_bp'] + 4999) // 10000", 'round-half tie of fractional cuts changed'),
 ('P40', 'python/pc/plugins/cut.py', "if c['basket_filter'] not in ('*', bk.basket_id) or bk.status == 'FULLY_CUT': continue", "if bk.status == 'FULLY_CUT': continue", 'basket_filter ignored by the cut plugin'),
 ('P41', 'python/pc/plugins/reentry.py', "if c['basket_filter'] not in ('*', cut.basket_id): continue", "if False: continue", 'basket_filter ignored by the re-entry plugin'),
 ('P42', 'python/pc/scenario.py', "or d['price'] % 5: raise ScenarioError(f'seed", ": raise ScenarioError(f'seed", 'seed prices need not be tick multiples'),
 ('P43', 'python/pc/scenario.py', "if iid not in s.instruments or px % 5: raise", "if iid not in s.instruments: raise", 'mark prices need not be tick multiples'),
 ('P44', 'python/pc/plugins/cut.py', "max(used) if used else ts", "ts", 'NO_TRIGGER decisions record the wrong information time'),
 ('P45', 'python/pc/plugins/cut.py', "max([v[1] for v in trig.values()])", "min([v[1] for v in trig.values()])", 'basket-scope actions record the oldest instead of the newest trigger data'),
 ('P46', 'python/pc/risk.py', "        if b.status(action.basket_id) == 'FULLY_CUT': return INVALID_BASKET_STATE, 'basket already fully cut'\n", "", 'cut of a fully cut basket gives a different reason'),
 ('P47', 'python/pc/engine.py', "reasons.append(None)\n            else: failed = (a.action_id, r); reasons.append(r)", "reasons.append(None)\n            else: reasons.append(r)", 'a failed member does not stop its group'),
]
CPP = [
 ('C01', 'cpp/include/pc/core.hpp', "if (e1.first > L.max_gross_units && e1.first > e0.first)", "if (e1.first > L.max_gross_units)", 'de-risking blocked above the gross limit'),
 ('C02', 'cpp/include/pc/core.hpp', "if (a.ts < c.ts + L.reentry_min_cooldown_s)", "if (a.ts <= c.ts + L.reentry_min_cooldown_s)", 'validator cooldown boundary'),
 ('C03', 'cpp/include/pc/core.hpp', "  if (b.seen_ids.count(a.action_id)) return R(\"DUPLICATE_ACTION_ID\", a.action_id);\n", "", 'duplicate ids accepted'),
 ('C04', 'cpp/include/pc/plugins.hpp', "((lots * geti(\"fraction_bp\") + 5000) / 10000) * lot", "((lots * geti(\"fraction_bp\") + 0) / 10000) * lot", 'fraction rounding'),
 ('C05', 'cpp/include/pc/plugins.hpp', "* 10000 > geti(\"band_bp\") * cut.price", "* 10000 >= geti(\"band_bp\") * cut.price", 'band boundary'),
 ('C06', 'cpp/include/pc/engine.hpp', "  void reconcile() {\n", "  void reconcile() {\n    return;\n", 'reconciliation disabled'),
 ('C07', 'cpp/include/pc/core.hpp', "it->second.basket_id != a.basket_id || it->second.leg_id != a.leg_id) return R(\"INVALID_CUT_LINEAGE\"", "false) return R(\"INVALID_CUT_LINEAGE\"", 'cut lineage not checked'),
 ('C08', 'cpp/include/pc/engine.hpp', "const i64 px = m ? m->first : leg->last_price;", "const i64 px = leg->last_price;", 'fills ignore the mark'),
 ('C09', 'cpp/include/pc/core.hpp', "if (a.info_ts > a.ts) return R(\"LOOKAHEAD_VIOLATION\"", "if (false) return R(\"LOOKAHEAD_VIOLATION\"", 'look-ahead stamp not checked'),
 ('C10', 'cpp/include/pc/plugins.hpp', "if (ts < cut.ts + geti(\"cooldown_s\"))", "if (ts <= cut.ts + geti(\"cooldown_s\"))", 'plugin cooldown boundary'),
 ('C11', 'cpp/include/pc/engine.hpp', "if (failed) { auto rr = reasons[i] ?", "if (false) { auto rr = reasons[i] ?", 'group atomicity broken'),
 ('C12', 'cpp/include/pc/core.hpp', "    if (a.qty > leg->current) return R(\"INSUFFICIENT_INVENTORY\"", "    if (false) return R(\"INSUFFICIENT_INVENTORY\"", 'oversized cut accepted'),

 ('C13', 'cpp/include/pc/core.hpp', "  if (v < lo || v > hi) throw ScenarioError", "  if (false) throw ScenarioError", 'integer ranges not enforced by the loader'),
 ('C14', 'cpp/include/pc/engine.hpp', "    if (r.status != \"OK\" && r.status != \"NO_ACTION\" && r.status != \"ERROR\") return true;", "    return false;", 'plugin output is not validated'),
 ('C15', 'cpp/include/pc/core.hpp', "if (e.first <= ts) v->m_[kv.first].push_back(e);", "v->m_[kv.first].push_back(e);", 'the whole mark series is placed in the plugin context'),
 ('C16', 'cpp/include/pc/plugins.hpp', "\"|REENTRY|\" + cut.cut_id, name()", "\"|REENTRY\", name()", 're-entry action ids can collide'),
 ('C17', 'cpp/include/pc/engine.hpp', "std::filesystem::create_directories(dir); ", "", 'output directory is not created'),
 ('C18', 'cpp/include/pc/engine.hpp', "const i64 px = m ? m->first : leg->last_price;", "const i64 px = m ? m->first : leg->entry_price();", 'a fill without a mark uses the entry price'),
 ('C19', 'cpp/include/pc/core.hpp', "if (!std::binary_search(s.ticks.begin(), s.ticks.end(), a.ts)) throw ScenarioError", "if (false) throw ScenarioError", 'ACTION lines at non-tick times are accepted'),
 ('C20', 'cpp/include/pc/plugins.hpp', "if (geti(\"max_wait_s\") && ts > cut.ts + geti(\"max_wait_s\"))", "if (geti(\"max_wait_s\") && ts >= cut.ts + geti(\"max_wait_s\"))", 'max_wait boundary changed'),
 ('C21', 'cpp/include/pc/plugins.hpp', "l.side < 0 ? px * 10000 >= l.entry_price * (10000 + bp) : px * 10000 <= l.entry_price * (10000 - bp)", "l.side < 0 ? px * 10000 >= l.entry_price * (10000 + bp) : px * 10000 < l.entry_price * (10000 - bp)", 'long-leg trigger boundary changed'),
 ('C22', 'cpp/include/pc/plugins.hpp', "if ((gets(\"basket_filter\") != \"*\" && gets(\"basket_filter\") != bk.basket_id) || bk.status == \"FULLY_CUT\") continue;", "if (bk.status == \"FULLY_CUT\") continue;", 'basket_filter ignored'),
]


def run_mutant(mid, rel, old, new, what, quick):
    tmp = tempfile.mkdtemp(prefix='mut_'); dst = os.path.join(tmp, 'c')
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns('__pycache__', 'runs', 'output*', 'build*', '.pytest_cache'))
    p = os.path.join(dst, rel); src = open(p).read()
    if src.count(old) != 1: return dict(id=mid, what=what, result='ERROR', note=f'pattern occurs {src.count(old)} times')
    open(p, 'w').write(src.replace(old, new))
    env = dict(os.environ, ALGO8_HISTORICAL_PYTHON=HIST_PATH, ALGO8_HISTORICAL_CPP_INCLUDE=os.path.join(os.path.dirname(HIST_PATH), 'cpp', 'include'), PYTHONDONTWRITEBYTECODE='1')
    sel = ['tests/test_plugins.py', 'tests/test_registry.py', 'tests/test_scenarios.py', 'tests/test_bias_controls.py', 'tests/test_hardening.py'] if quick else ['tests']
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-x'] + sel, cwd=dst, env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr; shutil.rmtree(tmp, ignore_errors=True)
    failed = re.search(r'(\d+) failed', out); errors = re.search(r'(\d+) error', out)
    if r.returncode == 0: return dict(id=mid, what=what, result='SURVIVED', note='')
    if failed: first = re.findall(r'^FAILED (\S+)', out, re.M); return dict(id=mid, what=what, result='KILLED', note=first[0] if first else 'assertion failed')
    return dict(id=mid, what=what, result='ERROR', note=(errors.group(0) if errors else out[-200:]))


def main():
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    outp = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else os.path.join(ROOT, 'mutation_results.json'); res = []
    ids = sys.argv[sys.argv.index('--ids') + 1].split(',') if '--ids' in sys.argv else None
    for mid, rel, old, new, what in PY + CPP:
        if ids and mid not in ids: continue
        if only == 'py' and mid[0] != 'P' or only == 'cpp' and mid[0] != 'C': continue
        r = run_mutant(mid, rel, old, new, what, quick=mid[0] == 'P')
        if r['result'] == 'SURVIVED' and mid[0] == 'P': r2 = run_mutant(mid, rel, old, new, what, quick=False); r = r2 if r2['result'] != 'SURVIVED' else r         # a quick-suite survivor gets the full suite incl. parity
        print(mid, r['result'], '-', what, '-', r['note'], flush=True); res.append(r)
    summary = dict(total=len(res), killed=sum(r['result'] == 'KILLED' for r in res), survived=[r['id'] for r in res if r['result'] == 'SURVIVED'], errors=[r['id'] for r in res if r['result'] == 'ERROR'])
    json.dump(dict(summary=summary, mutants=res), open(outp, 'w'), indent=1); print(json.dumps(summary))


if __name__ == '__main__': main()
