"""M2-F consolidation: merges the five audit tracks' claims.json / defects.json / mutations.json into the register documents. No judgement is added here: statuses, severities and
classes are the auditors' own; this tool only normalises, sorts and renders (and refuses silently-dropped records: every input record appears in the output).
python3 portfolio_engine/tools/m2f_consolidate.py  -> reports/M2F_CLAIM_EVIDENCE_REGISTER.md, M2F_DEFECT_REGISTER.md, m2f_audit/consolidated.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); A = os.path.join(PE, 'reports', 'm2f_audit')
TRACKS = {'A': 'accounting and lineage', 'B': 'closing batches', 'C': 'wing/body', 'D': 'forensics and visualization', 'E': 'system and reproducibility'}
CLASSES = ['Independently verified fact', 'Reproduced result with limited independent verification', 'Internal consistency only', 'Method-dependent result', 'Inferred association', 'Unresolved', 'Not testable with available data']
SEV = ['Critical', 'High', 'Medium', 'Low']


def load(t, name):
    p = os.path.join(A, f'track_{t.lower()}', name)
    if not os.path.exists(p): return None
    d = json.load(open(p)); return d if isinstance(d, list) else d.get('items') or d.get('claims') or d.get('defects') or d.get('mutations') or list(d.values())


def esc(x): return str(x if x is not None else '').replace('|', '\\|').replace('\n', ' ')


def main():
    C, Dd, M, missing = [], [], [], []
    for t in TRACKS:
        for name, bucket in (('claims.json', C), ('defects.json', Dd), ('mutations.json', M)):
            r = load(t, name)
            if r is None: missing.append(f'track_{t.lower()}/{name}'); continue
            for i, x in enumerate(r): x = dict(x) if isinstance(x, dict) else {'raw': x}; x['track'] = t; x.setdefault('id', f'{t}-{name[0].upper()}{i + 1:03d}'); bucket.append(x)
    json.dump(dict(claims=C, defects=Dd, mutations=M, missing_inputs=missing), open(os.path.join(A, 'consolidated.json'), 'w'), indent=1, default=str)
    L = ['# M2-F — Claim-to-evidence register', '', 'Merged from the five independent audit tracks (`reports/m2f_audit/track_*/claims.json`). Classes are the auditors\' own and use the registered vocabulary. A claim repeated in several reports is registered once per verification, never upgraded by repetition.', '']
    if missing: L += [f'**Missing track inputs (audit incomplete for these):** {", ".join(missing)}', '']
    cnt = {c: sum(1 for x in C if x.get('class') == c) for c in CLASSES}; other = sum(1 for x in C if x.get('class') not in CLASSES)
    L += ['| Class | Count |', '|---|---:|'] + [f'| {c} | {n} |' for c, n in cnt.items()] + ([f'| (unclassified / non-standard) | {other} |'] if other else []) + ['', '| # | Track | Claim | Source | Independent verification | Class | Status | Limitation |', '|---|---|---|---|---|---|---|---|']
    for i, x in enumerate(sorted(C, key=lambda x: (x['track'], str(x.get('claim')))), 1): L.append(f"| {i} | {x['track']} | {esc(x.get('claim'))} | {esc(x.get('source'))} | {esc(x.get('independent_verification'))} | {esc(x.get('class'))} | {esc(x.get('status'))} | {esc(x.get('limitation'))} |")
    open(os.path.join(PE, 'reports', 'M2F_CLAIM_EVIDENCE_REGISTER.md'), 'w').write('\n'.join(L) + '\n')
    L = ['# M2-F — Defect register', '', 'Merged from `reports/m2f_audit/track_*/defects.json`. Severity definitions: **Critical** corrupts observed inventory, accounting, position identity or material research results; **High** changes memberships, methodology interpretation or significant reported conclusions; **Medium** weakens validation, reproducibility or scope reporting; **Low** documentation, presentation or non-material maintainability.', '']
    for s in SEV:
        ds = [x for x in Dd if str(x.get('severity', '')).capitalize() == s]; L += [f'## {s} ({len(ds)})', '']
        for x in ds: L += [f"### {x['id']} (track {x['track']}): {esc(x.get('title'))}", f"* **Location:** {esc(x.get('location'))}", f"* **Evidence:** {esc(x.get('evidence'))}", f"* **Reproduction:** {esc(x.get('repro'))}", f"* **Impact:** {esc(x.get('impact'))}", f"* **Proposed correction:** {esc(x.get('proposed_fix'))}", f"* **Regression test:** {esc(x.get('proposed_test'))}", f"* **Disposition:** {esc(x.get('disposition', 'OPEN'))}", '']
    rest = [x for x in Dd if str(x.get('severity', '')).capitalize() not in SEV]
    if rest: L += [f'## Unclassified severity ({len(rest)})', ''] + [f"* {x['id']}: {esc(x.get('title'))}" for x in rest]
    L += ['## Mutation records', '', '| # | Track | Change | Expected detector | Existing tests caught | Own check caught | Detector independent of mutated path | Notes |', '|---|---|---|---|---|---|---|---|']
    for i, x in enumerate(M, 1): L.append(f"| {i} | {x['track']} | {esc(x.get('change'))} | {esc(x.get('expected_detector'))} | {esc(x.get('existing_tests_caught'))} | {esc(x.get('own_check_caught'))} | {esc(x.get('detector_independent'))} | {esc(x.get('notes'))} |")
    open(os.path.join(PE, 'reports', 'M2F_DEFECT_REGISTER.md'), 'w').write('\n'.join(L) + '\n')
    sev = {sv: sum(1 for x in Dd if str(x.get('severity', '')).capitalize() == sv) for sv in SEV}
    print(f'claims {len(C)}, defects {len(Dd)} {sev}, mutations {len(M)}, missing {missing}')


main()
