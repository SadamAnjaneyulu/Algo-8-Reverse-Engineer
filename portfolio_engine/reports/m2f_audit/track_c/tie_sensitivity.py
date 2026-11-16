"""Methodology ambiguity: order of same-second fills of one instrument (6 mixed-side ties).  Measure impact on items / link counts under (ts,row) [engine default], sells-first, buys-first.  [RAW][IMPL]"""
import json, load_raw, ref_wing_body as R
F = load_raw.load(); out = {}
for name, order in (('src', lambda f: (f['ts'], f['row'])), ('sells_first', lambda f: (f['ts'], 0 if f['sgn'] < 0 else 1, f['row'])), ('buys_first', lambda f: (f['ts'], 0 if f['sgn'] > 0 else 1, f['row']))):
    A = R.analyse(F, 'TAGGED', order); I = A['items']
    out[name] = dict(items=len(I), wing_open_units=sum(i.qty for i in I.values() if i.level == 'OPENING' and i.role == 'WING'), body_open_units=sum(i.qty for i in I.values() if i.level == 'OPENING' and i.role == 'BODY'), wing_close_units=sum(i.qty for i in I.values() if i.level == 'CLOSING' and i.role == 'WING'), body_close_units=sum(i.qty for i in I.values() if i.level == 'CLOSING' and i.role == 'BODY'),
                     links={m: len(v) for m, v in A['links'].items()}, w3=A['w3_resid'], keys=sorted(map(str, I))[:0])
    out[name]['_itemset'] = None
    out[name + '_keys'] = None
    out[name]['_k'] = sorted(map(str, ((k, v.qty) for k, v in I.items())))
base = set(out['src']['_k'])
for n in ('sells_first', 'buys_first'): out[n]['items_differing_vs_src'] = len(base ^ set(out[n]['_k']))
for n in list(out):
    if isinstance(out[n], dict): out[n].pop('_k', None); out[n].pop('_itemset', None)
    else: pass
out = {k: v for k, v in out.items() if v is not None}
json.dump(out, open('tie_sensitivity_result.json', 'w'), indent=1); print(json.dumps(out, indent=1))
