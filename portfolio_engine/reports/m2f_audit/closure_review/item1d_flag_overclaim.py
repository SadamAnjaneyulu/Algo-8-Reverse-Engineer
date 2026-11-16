"""Item 1d / counterexample (a): in a cycle that contains a reordered same-instrument group (NIFTY expiry 2026-09-01, rows 27906-27917), the project's own inventory_series under baseline vs hybrid
differs in cum_opened_* / cum_closed_by_tag_* at second-end rows that intra_second_flag_table labels SECOND_END_ORDER_INVARIANT. [IMPL] code, run on the real ledger."""
import os, sys, json, collections
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.abspath(os.path.join(HERE, '..', '..', '..')); REPO = os.path.dirname(PE)
sys.path.insert(0, os.path.join(PE, 'python'))
from pe import forensics as F, scenario as SC
tmp = sys.argv[1]
base = SC.Scenario('baseline', PE, os.path.join(tmp, 'b')); hyb = SC.Scenario('per_contract_id_sequence', PE, os.path.join(tmp, 'h'))
res = {}
for und, exp in (('NIFTY', '2026-09-01'),):
    cb = F.Cycle(REPO, und, exp, base); ch = F.Cycle(REPO, und, exp, hyb)
    Hb, Rb = F.inventory_series(cb); Hh, Rh = F.inventory_series(ch); assert Hb == Hh
    hdr_f, flags = F.intra_second_flag_table(ch); fl = {r[0]: r[5] for r in flags}
    I = {h: i for i, h in enumerate(Hb)}; ts = I['ts_utc_s']; fid = I['fill_id']
    def se(rows):
        o = {}
        for r in rows: o[r[ts]] = r
        return o
    be, he = se(Rb), se(Rh); cols = [h for h in Hb if h.startswith('cum_') or h in ('short_CE', 'short_PE', 'long_CE', 'long_PE', 'gross_total', 'net_total')]
    d = collections.Counter(); bad = []
    for t, r in he.items():
        dc = [c for c in cols if r[I[c]] != be[t][I[c]]]
        for c in dc: d[c] += 1
        if dc: bad.append(dict(ts=t, fill_id=r[fid], flag=fl[r[fid]], differing_columns=dc, baseline={c: be[t][I[c]] for c in dc}, hybrid={c: r[I[c]] for c in dc}))
    res[f'{und}_{exp}'] = dict(second_end_rows_differing_by_column=dict(d), n_rows=len(bad), flags_of_those_rows=dict(collections.Counter(b['flag'] for b in bad)), first_example=bad[:1])
    print(res[f'{und}_{exp}'])
json.dump(res, open(os.path.join(HERE, 'item1d_flag_overclaim_result.json'), 'w'), indent=1, default=str)
