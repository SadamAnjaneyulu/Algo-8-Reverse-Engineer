"""Imports the already-downloaded Breeze files (branch data/local-breeze-fetch layout) into the new store WITHOUT re-requesting anything.
raw files are copied byte-for-byte into raw/legacy/..., normalized CSVs gain a source_id column, every contract-day is registered with source='legacy_local_breeze_v1'."""
import csv, glob, io, json, os
from . import normalize as N
from .store import sha256_bytes, write_once


def import_legacy(store, branch_root, und='NIFTY'):
    n = 0
    for meta_path in sorted(glob.glob(os.path.join(branch_root, 'data', 'breeze', 'metadata', 'options', und, '*', '*', '*.json'))):
        m = json.load(open(meta_path)); c = m['contract']
        if m.get('status') != 'validated_observed_option_bars': continue
        raw_abs = os.path.join(branch_root, 'data', 'breeze', m['raw_path']); norm_abs = os.path.join(branch_root, 'data', 'breeze', m['normalized_path'])
        raw_bytes = open(raw_abs, 'rb').read(); rawsha = sha256_bytes(raw_bytes)
        rows = list(csv.DictReader(open(norm_abs, newline='')))
        if sha256_bytes(open(norm_abs, 'rb').read()) != m['normalized_sha256']: raise ValueError(f'legacy normalized hash mismatch: {norm_abs}')
        rrel = os.path.join('raw', 'legacy', und, c['expiry_date'], f"{c['strike']}{c['option_type']}", f"{c['trade_date']}.{rawsha[:12]}.json"); write_once(store.path(rrel), raw_bytes)
        sid = 'legacy:' + rawsha[:12]; f = io.StringIO(newline=''); w = csv.DictWriter(f, fieldnames=N.COLS['option'], lineterminator='\n'); w.writeheader()
        for r in rows: w.writerow({k: r.get(k, '') for k in N.COLS['option'] if k != 'source_id'} | {'source_id': sid})
        content = f.getvalue().encode(); nrel = os.path.join('normalized', 'option', und, c['expiry_date'], f"{c['strike']}{c['option_type']}", f"{c['trade_date']}.csv"); write_once(store.path(nrel), content)
        store.set_day(dict(kind='option', und=und, expiry=c['expiry_date'], strike=c['strike'], right=c['option_type'], trade_day=c['trade_date']), status='DONE', source='legacy_local_breeze_v1', task_id=sid, normalized_relpath=nrel, normalized_sha256=sha256_bytes(content), bars=len(rows)); n += 1
    for p in sorted(glob.glob(os.path.join(branch_root, 'data', 'breeze', 'normalized', 'indices', und, '*.csv'))):
        day = os.path.basename(p).split('.')[0]
        for mp in glob.glob(os.path.join(branch_root, 'data', 'breeze', 'metadata', 'indices', und, day + '.*.json')):
            rp = json.load(open(mp)).get('raw_path')
            if rp and os.path.exists(os.path.join(branch_root, 'data', 'breeze', rp)):
                b = open(os.path.join(branch_root, 'data', 'breeze', rp), 'rb').read(); write_once(store.path('raw', 'legacy', 'index', und, f'{day}.{sha256_bytes(b)[:12]}.json'), b)
        raw = open(p, 'rb').read(); rows = list(csv.DictReader(io.StringIO(raw.decode())))
        sid = 'legacy:' + sha256_bytes(raw)[:12]; f = io.StringIO(newline=''); w = csv.DictWriter(f, fieldnames=N.COLS['index'], lineterminator='\n'); w.writeheader()
        for r in rows: w.writerow({k: r.get(k, '') for k in N.COLS['index'] if k != 'source_id'} | {'source_id': sid})
        content = f.getvalue().encode(); nrel = os.path.join('normalized', 'index', und, '-', f'{day}.csv'); write_once(store.path(nrel), content)
        store.set_day(dict(kind='index', und=und, expiry=None, strike=None, right=None, trade_day=day), status='DONE', source='legacy_local_breeze_v1', task_id=sid, normalized_relpath=nrel, normalized_sha256=sha256_bytes(content), bars=len(rows)); n += 1
    store.commit(); return n
