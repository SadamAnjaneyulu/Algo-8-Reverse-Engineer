"""[REPRO] Compare a committed tree (scratch mirror) with a regenerated tree (scratch copy where tools/m2e_build.py, m2e_charts.py, m2e_cases.py, m2e_catalog/coverage_report/report were run).
Usage: regen_compare.py <committed_pe_reports> <regen_pe_reports>   Text/CSV/JSON compared byte-wise; PNG byte-wise (informational)."""
import os, sys
A, B = sys.argv[1], sys.argv[2]; diffs = []; same = 0; png = pd = 0
for root in ('m2e_data', 'm2e_figures'):
    for dp, dn, fn in os.walk(f'{A}/{root}'):
        for f in fn:
            pa = os.path.join(dp, f); pb = pa.replace(A, B)
            if not os.path.exists(pb): diffs.append(('MISSING_IN_REGEN', pa)); continue
            same_ = open(pa, 'rb').read() == open(pb, 'rb').read()
            if f.endswith('.png'): png += 1; pd += (not same_)
            elif same_: same += 1
            else: diffs.append(('DIFF', pa))
for f in sorted(os.listdir(A)):
    if f.startswith('M2E_') and f.endswith('.md'):
        if open(f'{A}/{f}', 'rb').read() == open(f'{B}/{f}', 'rb').read(): same += 1
        else: diffs.append(('DIFF', f'{A}/{f}'))
print('identical non-PNG files', same, '| png files', png, 'png byte-different', pd)
for d in diffs: print(d)
