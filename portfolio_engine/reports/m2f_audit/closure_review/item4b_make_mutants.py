"""Item 4b / counterexample (d): create two PRICE-DEPENDENT case-selection mutants in scratch copies (never in the repo). usage: item4b_make_mutants.py <scratch_root> <real_worktree>
mutA: CT1 candidates are re-ranked by the RAW-CSV price (col 137) of each candidate episode's first fill (highest first) - a price-dependent selection that reads a source the test's scrambling never touches.
mutB: same ranking but using the pipeline's own fills.tsv exec_price_paise (the path the scrambling test does perturb) - the control: the test should kill this one."""
import sys, os
S, WT = sys.argv[1], sys.argv[2]
HELP_A = '''
import csv as _csv
_RAWPX = {}
def _first_px(D, eid):
    if not _RAWPX:
        for i, r in enumerate(_csv.reader(open(%r))): _RAWPX[i] = r[137]
    fid = next(e['fill_id'] for e in D['events'] if e['episode_id'] == eid)
    return float(_RAWPX[int(D['fills'][fid]['source_row_id'])])
''' % os.path.join(WT, 'Trades_GKOHNP140.csv')
HELP_B = '''
def _first_px(D, eid):
    fid = next(e['fill_id'] for e in D['events'] if e['episode_id'] == eid)
    return float(D['fills'][fid]['exec_price_paise'])
'''
ANCH = "        rule = dict(RULES)[name]\n"
HOOK = "        rule = dict(RULES)[name]\n        if name == 'CT1_INCREMENTAL_OPENING': cands = sorted(cands, key=lambda c: -_first_px(D, c[0]))   # MUTANT: price-dependent ranking\n"
for m, helper in (('mutA', HELP_A), ('mutB', HELP_B)):
    p = os.path.join(S, m, 'portfolio_engine', 'python', 'pe', 'cases.py'); s = open(p).read()
    assert s.count(ANCH) == 1 and s.count('\ndef select(D):') == 1
    s = s.replace(ANCH, HOOK).replace('\ndef select(D):', helper + '\n\ndef select(D):'); open(p, 'w').write(s); print('patched', p)
