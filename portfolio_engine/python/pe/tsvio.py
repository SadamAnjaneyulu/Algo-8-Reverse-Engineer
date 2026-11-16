"""TSV reading/writing for the shared files; strict validation with line numbers."""
import os
from .schema import *


def _rows(path, expected):
    with open(path, 'r', encoding='utf-8') as f:
        header = None
        for n, line in enumerate(f, 1):
            line = line.rstrip('\n')
            if not line or line.startswith('#'): continue
            parts = line.split('\t')
            if header is None:
                header = parts
                if header != expected: raise EventValidationError(f'{path}: bad header {header}')      # validated even when the file has no data rows
                continue
            yield n, header, parts


def read_instruments(path):
    out = {}; cols = None
    for n, h, p in _rows(path, INSTRUMENT_COLUMNS):
        if len(p) != len(h): raise EventValidationError(f'{path}:{n}: {len(p)} fields, expected {len(h)}')
        r = dict(zip(h, p))
        try: ins = Instrument(r['instrument_id'], r['underlying'], r['exchange_segment'], r['instrument_type'], r['option_type'], int(r['strike']), r['expiry'], int(r['lot_size']), int(r['tick_size_paise']), r['lot_size_source'])
        except ValueError as e: raise EventValidationError(f'{path}:{n}: {e}')
        if ins.option_type not in ('CE', 'PE'): raise EventValidationError(f'{path}:{n}: invalid option_type {ins.option_type!r}')
        if ins.instrument_id in out: raise EventValidationError(f'{path}:{n}: duplicate instrument {ins.instrument_id}')
        try: iso_day(ins.expiry)
        except Exception: raise EventValidationError(f'{path}:{n}: bad expiry {ins.expiry!r}')
        out[ins.instrument_id] = ins
    return out


def _int(r, k, path, n):
    try: return int(r[k])
    except ValueError: raise EventValidationError(f'{path}:{n}: {k}={r[k]!r} is not an integer')


def read_events(path, instruments):
    """returns the list of Fill in FILE order; raises on any structural problem (nothing is applied)"""
    fills = []; seen = set()
    for n, h, p in _rows(path, EVENT_COLUMNS):
        if len(p) != len(h): raise EventValidationError(f'{path}:{n}: {len(p)} fields, expected {len(h)}')
        r = dict(zip(h, p))
        if r['schema_version'] != SCHEMA_FILL: raise EventValidationError(f'{path}:{n}: schema_version {r["schema_version"]!r}')
        if r['execution_mode'] not in MODES: raise EventValidationError(f'{path}:{n}: unknown execution_mode {r["execution_mode"]!r}')
        side = _int(r, 'side', path, n); q = _int(r, 'quantity', path, n); px = _int(r, 'price_paise', path, n); ts = _int(r, 'timestamp_s', path, n)
        if side not in (1, -1): raise EventValidationError(f'{path}:{n}: side must be +1 or -1')
        if q <= 0: raise EventValidationError(f'{path}:{n}: quantity must be positive')
        if px <= 0 or px % TICK_PAISE: raise EventValidationError(f'{path}:{n}: price_paise {px} is not a positive multiple of the tick ({TICK_PAISE})')
        if ts <= 0: raise EventValidationError(f'{path}:{n}: bad timestamp')
        if r['instrument_id'] not in instruments: raise EventValidationError(f'{path}:{n}: unknown instrument {r["instrument_id"]!r}')
        if r['fill_id'] in seen: raise EventValidationError(f'{path}:{n}: duplicate fill_id {r["fill_id"]!r} (a fill is applied exactly once)')
        seen.add(r['fill_id'])
        dup = _int(r, 'is_duplicate_fill', path, n)
        if dup not in (0, 1): raise EventValidationError(f'{path}:{n}: is_duplicate_fill must be 0/1')
        if r['order_status'] not in ('Filled', 'PartiallyFilled'): raise EventValidationError(f'{path}:{n}: order_status {r["order_status"]!r}')
        fills.append(Fill(r['fill_id'], _int(r, 'source_row_id', path, n), r['parent_order_id'], r['module_tag'], r['instrument_id'], ts, side, q, px, _int(r, 'requested_quantity', path, n), r['order_status'], bool(dup), r['execution_mode'], r['evidence_source'], n))
    return fills


def write_events(path, fills, header_comment=None):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        if header_comment: f.write(f'# {header_comment}\n')
        f.write('\t'.join(EVENT_COLUMNS) + '\n')
        for x in fills:
            f.write('\t'.join([SCHEMA_FILL, x.execution_mode, x.fill_id, str(x.source_row_id), x.parent_order_id, x.module_tag, x.instrument_id, str(x.timestamp_s), str(x.side), str(x.quantity), str(x.price_paise),
                               str(x.requested_quantity), x.order_status, '1' if x.is_duplicate_fill else '0', x.evidence_source]) + '\n')


def write_instruments(path, instruments, header_comment=None):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        if header_comment: f.write(f'# {header_comment}\n')
        f.write('\t'.join(INSTRUMENT_COLUMNS) + '\n')
        for i in sorted(instruments.values(), key=lambda z: z.instrument_id):
            f.write('\t'.join([i.instrument_id, i.underlying, i.exchange_segment, i.instrument_type, i.option_type, str(i.strike), i.expiry, str(i.lot_size), str(i.tick_size_paise), i.lot_size_source]) + '\n')
