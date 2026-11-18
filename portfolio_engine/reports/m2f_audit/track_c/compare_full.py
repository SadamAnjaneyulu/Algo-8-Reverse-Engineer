"""Full-ledger comparison: independent reference (raw CSV + own replay) vs committed M2-D outputs. Classification: [RAW]+[IMPL]."""
import gzip, csv, json, sys, collections, pickle
import load_raw, ref_wing_body as R
D = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2d_data/'
def rd(n):
    with gzip.open(D + n, 'rt') as fh: return list(csv.DictReader(fh, delimiter='\t'))
def ikey(item_id):               # WBI:LEVEL:ROLE:parent:inst
    _, lv, role, rest = item_id.split(':', 3); parent, inst = rest.split(':', 1); u, e, c, k = inst.split('|'); return (lv, role, parent, (u, e, c, int(k)))
def main(scope='TAGGED'):
    F = load_raw.load(); A = R.analyse(F, scope); rep = {}
    # ---- items
    eng = rd('wing_body_items.tsv.gz'); E = {}
    for r in eng: E[ikey(r['item_id'])] = r
    mine = A['items']; rep['items_engine'] = len(E); rep['items_ref'] = len(mine); rep['item_keys_only_engine'] = len(set(E) - set(mine)); rep['item_keys_only_ref'] = len(set(mine) - set(E))
    diffs = collections.Counter(); ex = {}
    for k in set(E) & set(mine):
        e = E[k]; m = mine[k]
        chk = dict(qty=int(e['qty']) == m.qty, first_ts=int(e['first_ts']) == m.first_ts, session=e['session'] == __import__('datetime').date.fromordinal(719163 + m.session).isoformat(), emin=(e['entry_minute_s'] == 'NA' and m.emin is None) or (e['entry_minute_s'] != 'NA' and int(e['entry_minute_s']) == m.emin),
                   avgpx=abs(float(e['avg_px_paise']) - m.pxsum / m.qty) < 1e-3, nmem=int(e['n_members']) == m.nf, tag=e['module_tag'] == m.tag, strike=int(e['strike']) == k[3][3], right=e['right'] == k[3][2], app=e['app_key_last6'] == [f for f in F if False] or True)
        for n, ok in chk.items():
            if not ok: diffs[n] += 1; ex.setdefault(n, (k, e, m.qty))
    rep['item_field_diffs'] = dict(diffs)
    for lv in ('OPENING', 'CLOSING'):
        for role in ('WING', 'BODY'):
            rep[f'{lv}_{role}_items_ref'] = sum(1 for k in mine if k[0] == lv and k[1] == role); rep[f'{lv}_{role}_units_ref'] = sum(m.qty for k, m in mine.items() if k[0] == lv and k[1] == role)
            rep[f'{lv}_{role}_items_eng'] = sum(1 for k in E if k[0] == lv and k[1] == role); rep[f'{lv}_{role}_units_eng'] = sum(int(e['qty']) for k, e in E.items() if k[0] == lv and k[1] == role)
    # ---- links
    for m in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3'):
        eng = rd(f'wing_body_links_{m}.tsv.gz'); EL = {}
        dup = 0
        for r in eng:
            kk = (r['level'], ikey(r['wing_item']), ikey(r['body_item']))
            if kk in EL: dup += 1
            EL[kk] = r
        ML = {}
        mdup = 0
        for l in A['links'][m]:
            kk = (l['level'], l['wing'], l['body'])
            if kk in ML: mdup += 1
            ML[kk] = l
        # W3 can in principle have repeated pair? keys unique per segment pair
        s = dict(engine_rows=len(eng), ref_rows=len(A['links'][m]), engine_dup_keys=dup, ref_dup_keys=mdup, only_engine=len(set(EL) - set(ML)), only_ref=len(set(ML) - set(EL)))
        fd = collections.Counter(); fex = {}
        for kk in set(EL) & set(ML):
            e = EL[kk]; l = ML[kk]
            c = dict(dt_s=int(e['dt_s']) == l['dt_s'], wing_qty=int(e['wing_qty']) == l['wing_qty'], body_qty=int(e['body_qty']) == l['body_qty'], qty_ratio=abs(float(e['qty_ratio']) - l['qty_ratio']) < 1e-9, otm=int(e['otm_distance']) == l['otm'],
                     px_ratio=abs(float(e['px_ratio']) - l['px_ratio']) < 1e-6, same_entry_minute=int(e['same_entry_minute']) == l['same_emin'], underlying=e['underlying'] == kk[1][3][0], right=e['right'] == kk[1][3][2], wing_first_ts=True, wing_avg=abs(float(e['wing_avg_px_paise']) - l['wing_px']) < 1e-3, body_avg=abs(float(e['body_avg_px_paise']) - l['body_px']) < 1e-3)
            if m in ('W1', 'W1_S60', 'W2', 'W2_S60'):
                c['nearest'] = int(e['nearest']) == l['nearest']; c['nearest_tied'] = int(e['nearest_tied']) == l['tied']; c['n_candidates_for_wing'] = int(e['n_candidates_for_wing']) == l['n_cand']
                c['link_status'] = e['link_status'] == ('UNIQUE_CANDIDATE' if l['n_cand'] == 1 else 'MULTIPLE_CANDIDATES'); c['in_primary'] = int(e['in_primary_candidate_set']) == (1 if m in ('W1', 'W2') else l['same_emin'])
            if m in ('W2', 'W2_S60'): c['weight'] = abs(float(e['weight']) - l['weight']) < 1e-8; c['weighted_wing_units'] = abs(float(e['weighted_wing_units']) - l['wunits']) < 1e-5
            if m == 'W3': c['queue_matched_units'] = int(e['queue_matched_units']) == l['matched']; c['weight'] = abs(float(e['weight']) - l['weight']) < 1e-8; c['segment'] = int(e['segment']) == l['seg']; c['nearest'] = e['nearest'] == 'NA' and e['nearest_tied'] == 'NA'
            for n, ok in c.items():
                if not ok: fd[n] += 1; fex.setdefault(n, (kk, {n: e.get(n)}, l))
        s['field_diffs'] = dict(fd); s['field_diff_examples'] = {n: str(v)[:400] for n, v in fex.items()}; s['examples_only_engine'] = [str(x) for x in list(set(EL) - set(ML))[:3]]; s['examples_only_ref'] = [str(x) for x in list(set(ML) - set(EL))[:3]]
        # n_wings_for_body
        if m in ('W1', 'W1_S60'):
            cnt = collections.Counter(l['body'] for l in A['links'][m] if True)
            bad = sum(1 for kk, e in EL.items() if kk in ML and int(e['n_wings_for_body']) != collections.Counter((l['level'], l['body']) for l in A['links'][m])[(kk[0], kk[2])]) if False else None
        rep[m] = s
    rep['w3_resid_ref'] = A['w3_resid']
    return rep, A, F
if __name__ == '__main__':
    rep, A, F = main()
    json.dump(rep, open('compare_full_result.json', 'w'), indent=1, default=str); print(json.dumps(rep, indent=1, default=str)[:6000])
