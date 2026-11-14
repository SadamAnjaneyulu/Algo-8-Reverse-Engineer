"""Track E: input-boundary parity probe. Feeds malformed / unusual-but-parseable TSV variants to the Python reader+engine and the C++ pe_replay and reports ACCEPT/REJECT per engine and whether accepted outputs are byte-identical.
usage: parse_probe.py --root <scratch tree> --work <dir>"""
import argparse, os, subprocess, sys, json
ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--work', required=True); a = ap.parse_args()
PE = os.path.join(a.root, 'portfolio_engine'); sys.path.insert(0, os.path.join(PE, 'python')); os.makedirs(a.work, exist_ok=True)
from pe import tsvio, replay as rp
from pe.schema import *
BIN = os.path.join(PE, 'build', 'pe_replay')
base_ev = open(os.path.join(PE, 'fixtures', 'synthetic', 'open_close_full_events.tsv'), newline='').read(); base_in = open(os.path.join(PE, 'fixtures', 'synthetic', 'open_close_full_instruments.tsv'), newline='').read()
lines = base_ev.split('\n'); hdr_i = [i for i, l in enumerate(lines) if l.startswith('schema_version')][0]; row0 = lines[hdr_i + 1].split('\t'); cols = lines[hdr_i].split('\t')
def variant(name, fn_ev=None, fn_in=None, ev_text=None, in_text=None): return (name, ev_text if ev_text is not None else (fn_ev(base_ev) if fn_ev else base_ev), in_text if in_text is not None else (fn_in(base_in) if fn_in else base_in))
def setcol(col, val):
    def f(t):
        L = t.split('\n'); i = cols.index(col)
        for k in range(hdr_i + 1, len(L)):
            if L[k]:
                p = L[k].split('\t'); p[i] = val; L[k] = '\t'.join(p)
        return '\n'.join(L)
    return f
V = [variant('baseline'), variant('crlf_events', lambda t: t.replace('\n', '\r\n')), variant('crlf_both', lambda t: t.replace('\n', '\r\n'), lambda t: t.replace('\n', '\r\n')), variant('utf8_bom_events', lambda t: '﻿' + t),
     variant('plus_sign_qty', setcol('quantity', '+130')), variant('leading_space_qty', setcol('quantity', ' 130')), variant('underscore_qty', setcol('quantity', '1_30')), variant('trailing_space_qty', setcol('quantity', '130 ')),
     variant('fullwidth_digit_qty', setcol('quantity', '１３０')), variant('float_qty', setcol('quantity', '130.0')), variant('hex_qty', setcol('quantity', '0x82')), variant('leading_zero_qty', setcol('quantity', '0130')),
     variant('empty_line_mid', lambda t: t.replace('\n', '\n\n', 2)), variant('comment_mid', lambda t: t.replace('\n', '\n# note\n', 2)), variant('no_trailing_newline', lambda t: t.rstrip('\n')), variant('lone_cr_newlines', lambda t: t.replace('\n', '\r')),
     variant('space_only_line', lambda t: t + '   \n'), variant('tab_only_extra_col', lambda t: t.replace('\n', '\textra\n', 3)), variant('minus_zero_side', setcol('side', '-0')), variant('side_plus1', setcol('side', '+1')),
     variant('unicode_parent', setcol('parent_order_id', 'ÜÄ-é')), variant('ts_huge', setcol('timestamp_s', '99999999999999999999')), variant('dup_flag_2', setcol('is_duplicate_fill', '2')), variant('quote_in_field', setcol('evidence_source', '"x"'))]
res = []
for name, ev, ins in V:
    ep = os.path.join(a.work, name + '_ev.tsv'); ip = os.path.join(a.work, name + '_in.tsv'); open(ep, 'w', newline='', encoding='utf-8').write(ev); open(ip, 'w', newline='', encoding='utf-8').write(ins)
    try:
        I = tsvio.read_instruments(ip); F = tsvio.read_events(ep, I); R = rp.replay(F, I, MODE := 'SYNTHETIC_TEST', 'FIFO', 'src', 0, True, True); py = 'ACCEPT'; pyd = R.dump
    except Exception as e: py = 'REJECT:' + type(e).__name__; pyd = None
    r = subprocess.run([BIN, '--events', ep, '--instruments', ip, '--mode', 'SYNTHETIC_TEST', '--method', 'FIFO', '--tie', 'src', '--dump', ep + '.cdump'], capture_output=True, text=True)
    cp = 'ACCEPT' if r.returncode == 0 else 'REJECT'; same = (open(ep + '.cdump').read() == pyd) if (py == 'ACCEPT' and cp == 'ACCEPT') else None
    res.append(dict(variant=name, python=py, cpp=cp, outputs_identical=same, cpp_err=r.stderr.strip()[:100])); print(res[-1])
json.dump(res, open(os.path.join(a.work, 'parse_probe_result.json'), 'w'), indent=1)
