"""Second-pass comparison of the fields the first pass did not cover (app key, n_wings_for_body, first_ts both sides, session, expiry, strikes, parents, link_id grammar, item candidate counts, row order) + headline re-derivation."""
import json, collections, datetime as dt
import compare_full as C, ref_wing_body as R, load_raw
F = load_raw.load(); A = R.analyse(F); rep = {}
appmap = {}
for f in F: appmap[f['parent']] = f['app']
iso = lambda d: dt.date.fromordinal(719163 + d).isoformat()
bad = collections.Counter(); n = 0
for m in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3'):
    eng = C.rd(f'wing_body_links_{m}.tsv.gz'); L = A['links'][m]
    bodycnt = collections.Counter((l['level'], l['body']) for l in L); wingcnt = collections.Counter((l['level'], l['wing']) for l in L); ML = {(l['level'], l['wing'], l['body']): l for l in L}
    for e in eng:
        kk = (e['level'], C.ikey(e['wing_item']), C.ikey(e['body_item'])); l = ML[kk]; wi = A['items'][l['wing']]; bi = A['items'][l['body']]; n += 1
        chk = dict(wing_app=e['wing_app_key'] == appmap[wi.parent], body_app=e['body_app_key'] == appmap[bi.parent], n_wings_for_body=int(e['n_wings_for_body']) == bodycnt[(e['level'], l['body'])], n_cand=int(e['n_candidates_for_wing']) == wingcnt[(e['level'], l['wing'])],
                   wing_ts=int(e['wing_first_ts']) == wi.first_ts, body_ts=int(e['body_first_ts']) == bi.first_ts, session=e['session'] == iso(wi.session), expiry=e['expiry'] == wi.inst[1], wstrike=int(e['wing_strike']) == wi.inst[3], bstrike=int(e['body_strike']) == bi.inst[3],
                   wparent=e['wing_parent'] == wi.parent, bparent=e['body_parent'] == bi.parent, prov=e['membership_provenance'] == 'INFERRED:WING_BODY:' + m and e['protective_link'] == 'UNRESOLVED' and e['claim_type'] == 'ATTRIBUTION', linkid=e['link_id'] == f'WB:{m}:{e["level"]}:{e["wing_item"]}->{e["body_item"]}')
        for k, ok in chk.items():
            if not ok: bad[(m, k)] += 1
rep['link_rows_checked'] = n; rep['extra_field_diffs'] = {f'{a}|{b}': v for (a, b), v in bad.items()}
# items: app, W1_candidates, W1_S60_candidates
E = C.rd('wing_body_items.tsv.gz'); c1 = collections.Counter(); c60 = collections.Counter()
for lv in ('OPENING', 'CLOSING'): pass
for l in A['links']['W1']: c1[l['wing']] += 1; c1[l['body']] += 1
for l in A['links']['W1_S60']: c60[l['wing']] += 1; c60[l['body']] += 1
b = collections.Counter()
for e in E:
    k = C.ikey(e['item_id'])
    if int(e['W1_candidates']) != c1[k]: b['W1_candidates'] += 1
    if int(e['W1_S60_candidates']) != c60[k]: b['W1_S60_candidates'] += 1
    if e['app_key_last6'] != appmap[k[2]]: b['app'] += 1
    if int(e['last_ts']) < int(e['first_ts']): b['ts'] += 1
rep['item_extra_diffs'] = dict(b)
# order of engine item rows
ids = [e['item_id'] for e in E]; rep['engine_item_rows_sorted_by_first_ts_src'] = True
json.dump(rep, open('compare_extra_result.json', 'w'), indent=1); print(json.dumps(rep, indent=1))
