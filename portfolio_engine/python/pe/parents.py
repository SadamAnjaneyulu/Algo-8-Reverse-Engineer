"""ParentOrder metadata file (parents.tsv, schema v1.1). Missing values are the literal NA and are NEVER derived from other fields."""
from .schema import *

PARENT_COLUMNS = ['parent_order_id', 'module_tag', 'order_entry_minute_s', 'app_key_full', 'app_key_last6', 'order_number', 'algo_id', 'first_fill_ts', 'last_fill_ts', 'n_fills', 'filled_units', 'requested_units',
                  'first_source_row', 'last_source_row', 'parent_role']
INT_COLS = ('order_entry_minute_s', 'first_fill_ts', 'last_fill_ts', 'n_fills', 'filled_units', 'requested_units', 'first_source_row', 'last_source_row')
ROLES = ('OPENING_ONLY', 'CLOSING_ONLY', 'MIXED')


def parent_roles(observed_rows):
    """convention-independent role of every parent from the observed layer (OA / CP rows): OPENING_ONLY, CLOSING_ONLY or MIXED"""
    has = {}
    for r in observed_rows: has.setdefault(r[3], set()).add(r[0])
    return {p: ('MIXED' if s == {'OA', 'CP'} else ('OPENING_ONLY' if s == {'OA'} else 'CLOSING_ONLY')) for p, s in has.items()}


def write_parents(path, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(PARENT_COLUMNS) + '\n')
        for r in rows: f.write('\t'.join('NA' if r.get(c) is None else str(r[c]) for c in PARENT_COLUMNS) + '\n')


def read_parents(path):
    out = {}
    with open(path, encoding='utf-8') as f:
        header = f.readline().rstrip('\n').split('\t')
        if header != PARENT_COLUMNS: raise EventValidationError(f'{path}: bad parents header')
        for n, line in enumerate(f, 2):
            p = line.rstrip('\n').split('\t')
            if len(p) != len(header): raise EventValidationError(f'{path}:{n}: wrong number of fields')
            r = dict(zip(header, p))
            for c in INT_COLS:
                if r[c] == 'NA': r[c] = None
                else:
                    try: r[c] = int(r[c])
                    except ValueError: raise EventValidationError(f'{path}:{n}: {c}={r[c]!r}')
            for c in ('app_key_full', 'app_key_last6', 'order_number', 'algo_id'):
                if r[c] == 'NA': r[c] = None
            if r['parent_role'] not in ROLES: raise EventValidationError(f'{path}:{n}: parent_role {r["parent_role"]!r}')
            if r['parent_order_id'] in out: raise EventValidationError(f'{path}:{n}: duplicate parent {r["parent_order_id"]}')
            out[r['parent_order_id']] = r
    return out
