"""Render config/rule_evidence.yaml to reports/RULE_EVIDENCE_REGISTER.md (generated; never edit the markdown by hand)."""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import rulemeta as RM
doc = RM.load(); err = RM.validate(doc); assert not err, err
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cnt = collections.Counter(r['classification'] for r in doc['rules']); hist = collections.Counter(str(r['may_run_historically']) for r in doc['rules'])
L = ['# Rule evidence register (generated from `config/rule_evidence.yaml`)', '',
     f"Register sha256 `{RM.sha256()}` · base commit `{doc['base_commit']}` · {len(doc['rules'])} rules. **Classifications come from earlier evidence only and are never upgraded because a rule performs well in a backtest.**", '',
     '| Class | Rules |', '|---|---:|'] + [f'| {c} | {cnt.get(c, 0)} |' for c in RM.CLASSES] + ['', f"May run historically: {dict(hist)}", '']
groups = collections.OrderedDict()
for r in doc['rules']: groups.setdefault(r['group'], []).append(r)
for g, rs in groups.items():
    L += [f'## {g}', '', '| ID | Rule | Class | Mode | Historical run | Evidence | Key limitation |', '|---|---|---|---|---|---|---|']
    for r in rs: L.append(f"| {r['id']} | {r['description']} | **{r['classification']}** | {r['mode']} | {r['may_run_historically']} | {r['evidence_source']} | {r['limitations']} |")
    L.append('')
open(os.path.join(ROOT, 'reports', 'RULE_EVIDENCE_REGISTER.md'), 'w').write('\n'.join(L) + '\n'); print('rules', len(doc['rules']), dict(cnt))
