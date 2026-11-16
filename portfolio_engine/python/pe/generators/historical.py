"""HISTORICAL generator: TP-01 normalised fill ledger (read-only) -> canonical events / instruments (mode HISTORICAL_OBSERVED_REPLAY).
It reads `tp_reconstruction/data/fill_event_ledger.parquet` and never writes anywhere near it. Optional cycle filter (underlying + expiry) for small real samples."""
import hashlib, json, os
from decimal import Decimal
from ..schema import *
from .. import tsvio, provenance

GENERATOR = 'historical_tp01_ledger'; VERSION = '1'
LOT_SOURCE = 'TP01_config_units_verified_multiples'


# raw csv column indices (audited by M2-F, same as tests/test_m2f_regressions.py): 3 segment, 11 side, 12 underlying, 14 strike, 15 expiry (m/d/Y H:M), 16 right, 33 quantity (units), 137 per-fill price (rupees), 161 UTC epoch s, 163 parent order id
def _paise_exact(text):
    """integer paise from a rupee decimal text, exactly (Decimal, never float); None when the text is not a decimal or not on the paise grid"""
    try: d = Decimal(str(text).strip()) * 100
    except Exception: return None
    return int(d) if d.is_finite() and d == d.to_integral_value() else None


def verify_ledger_against_raw(repo_root, ledger_rows):
    """D-A02: compare EVERY ledger row used (source row id, contract / instrument fields, side, quantity in units, epoch seconds, parent order id, PRICE) with the raw csv row `src_row` (0-based csv row index).
    Prices: the raw rupee text -> integer paise with decimal.Decimal; the ledger float is turned into its shortest round-trip decimal text (repr) and compared as Decimal paise; no float rounding anywhere.
    Raises EngineError naming the first mismatching source row (lowest src_row) and field. Returns {src_row: raw_price_paise}. Reads the raw file only."""
    import csv, datetime as dt
    rows = sorted(ledger_rows, key=lambda r: int(r.src_row)); need = {int(r.src_row) for r in rows}
    if len(need) != len(rows): raise EngineError('ledger has duplicate source row ids')
    if not rows: return {}
    raw = {}
    with open(os.path.join(repo_root, 'Trades_GKOHNP140.csv'), newline='') as fh:
        for i, rr in enumerate(csv.reader(fh)):
            if i in need: raw[i] = rr
    paise = {}
    for r in rows:
        i = int(r.src_row)
        def bad(field, ledger_v, raw_v): raise EngineError(f'ledger row differs from the raw csv at source row {i}: {field}: ledger {ledger_v!r} != raw {raw_v!r}')
        if i not in raw: bad('source row id', i, 'no such raw row')
        c = raw[i]
        try: exp = dt.datetime.strptime(c[15], '%m/%d/%Y %H:%M').date().isoformat(); strike = int(c[14]); units = int(c[33]); epoch = int(c[161])
        except (ValueError, IndexError) as e: bad('raw row not parseable', None, repr(e))
        if r.segment != c[3]: bad('segment', r.segment, c[3])
        if r.und != c[12]: bad('underlying', r.und, c[12])
        if r.cp != c[16]: bad('option right', r.cp, c[16])
        if int(r.strike) != strike: bad('strike', int(r.strike), strike)
        if r.expiry.strftime('%Y-%m-%d') != exp: bad('expiry', r.expiry.strftime('%Y-%m-%d'), exp)
        if r.contract_id != f'{c[12]}|{exp}|{c[16]}|{strike}': bad('contract id', r.contract_id, f'{c[12]}|{exp}|{c[16]}|{strike}')
        side = {'Buy': 1, 'Sell': -1}.get(c[11])
        if side is None or int(r.sgn) != side: bad('side', int(r.sgn), c[11])
        if int(r.qty_units) != units: bad('quantity (units)', int(r.qty_units), units)
        if int(r.epoch) != epoch: bad('epoch seconds', int(r.epoch), epoch)
        if str(r.parent_oid) != c[163]: bad('parent order id', str(r.parent_oid), c[163])
        rp = _paise_exact(c[137]); lp = _paise_exact(repr(float(r.px_fill)))
        if rp is None: bad('raw price not on the paise grid', None, c[137])
        if lp != rp: bad('price (paise)', lp, rp)
        paise[i] = rp
    return paise


def generate(repo_root, cycle=None):
    """returns (instruments dict, fills list, source_hashes dict). cycle = (underlying, 'YYYY-MM-DD') or None for every fill"""
    import pandas as pd
    pq = os.path.join(repo_root, 'tp_reconstruction', 'data', 'fill_event_ledger.parquet'); man = json.load(open(os.path.join(repo_root, 'tp_reconstruction', 'data', 'source_manifest.json')))
    raw = os.path.join(repo_root, 'Trades_GKOHNP140.csv'); raw_hash = provenance.sha256_file(raw)
    if raw_hash != man['sha256']: raise EngineError(f'raw trade file hash {raw_hash} != TP-01 manifest {man["sha256"]}')
    L = pd.read_parquet(pq)
    if cycle: L = L[(L.und == cycle[0]) & (L.expiry == pd.Timestamp(cycle[1]))]
    verify_ledger_against_raw(repo_root, list(L.itertuples()))               # D-A02: every ledger row used is compared with the raw csv before anything is built
    lots = {'NIFTY': 65, 'SENSEX': 20}; ins = {}
    for r in L.drop_duplicates('contract_id').itertuples():
        ins[r.contract_id] = Instrument(r.contract_id, r.und, r.segment, 'OPTION', r.cp, int(r.strike), r.expiry.strftime('%Y-%m-%d'), lots[r.und], TICK_PAISE, LOT_SOURCE)
    fills = []
    for r in L.itertuples():
        px = round(float(r.px_fill) * 100)
        if abs(px - float(r.px_fill) * 100) > 1e-6: raise EngineError(f'price off the paise grid at row {r.src_row}')
        fills.append(Fill(f'F{int(r.src_row):06d}', int(r.src_row), r.parent_oid, r.module, r.contract_id, int(r.epoch), int(r.sgn), int(r.qty_units), px, int(r.qty_order), r.order_status, bool(r.dq_duplicate_fill),
                          'HISTORICAL_OBSERVED_REPLAY', f'TP01_fill_event_ledger.parquet:src_row={int(r.src_row)}'))
    return ins, fills, {'raw_trades_sha256': raw_hash, 'tp01_ledger_sha256': provenance.sha256_file(pq)}


def attach_tie_keys(repo_root, fills, policy):
    """SENSITIVITY-ONLY: return copies of `fills` carrying the raw-csv key of `policy` (trade id col 28, order number col 4). The primary policy leaves fills untouched. The raw file is read, never written;
    its hash is checked against the TP-01 manifest first. Raw row = Fill.source_row_id (verified by the M2-F audit)."""
    import csv, dataclasses
    from .. import tie_policy as tp
    pol = tp.resolve(policy)
    if not pol.keyed: return list(fills)
    raw = os.path.join(repo_root, 'Trades_GKOHNP140.csv'); man = json.load(open(os.path.join(repo_root, 'tp_reconstruction', 'data', 'source_manifest.json')))
    if provenance.sha256_file(raw) != man['sha256']: raise EngineError('raw trade file hash differs from the TP-01 manifest')
    need = {f.source_row_id for f in fills}; keys = {}
    with open(raw, newline='') as fh:
        for i, r in enumerate(csv.reader(fh)):
            if i in need: keys[i] = (r[12], r[28], r[4])
    out = []
    for f in fills:
        und, tid, ono = keys[f.source_row_id]; out.append(dataclasses.replace(f, tie_key=tp.tie_key(pol.name, und, tid, ono, f.timestamp_s)))
    return out


def write(repo_root, out_dir, cycle=None, name='historical'):
    os.makedirs(out_dir, exist_ok=True); ins, fills, src = generate(repo_root, cycle); ev = os.path.join(out_dir, f'{name}_events.tsv'); ip = os.path.join(out_dir, f'{name}_instruments.tsv')
    note = f'generated by {GENERATOR} v{VERSION}; mode HISTORICAL_OBSERVED_REPLAY; cycle={cycle}; raw_sha256={src["raw_trades_sha256"]}'
    tsvio.write_events(ev, fills, note); tsvio.write_instruments(ip, ins, note); return ev, ip, src


def generate_parents(repo_root, roles_by_parent):
    """parents.tsv rows from the TP-01 ledger (read-only) and the raw file's app key / algo id columns (cols 166, 144). Parent metadata must be constant inside a parent; a conflict is written as the literal CONFLICT, never resolved silently."""
    import pandas as pd
    L = pd.read_parquet(os.path.join(repo_root, 'tp_reconstruction', 'data', 'fill_event_ledger.parquet'))
    raw = pd.read_csv(os.path.join(repo_root, 'Trades_GKOHNP140.csv'), header=None, dtype=str, keep_default_na=False, usecols=[144, 166]); L['app_full'] = raw[166].values; L['algo_id'] = raw[144].values
    L['eep'] = ((L.order_entry_minute - pd.Timestamp('1970-01-01')).dt.total_seconds() - IST_OFFSET_S)
    rows = []
    for pid, g in L.groupby('parent_oid', sort=True):
        def one(col, fmt=str):
            v = g[col].unique()
            if len(v) != 1: return 'CONFLICT'
            x = v[0]
            return None if (x is None or x == '' or (isinstance(x, float) and x != x)) else fmt(x)
        rows.append(dict(parent_order_id=pid, module_tag=g.module.iloc[0], order_entry_minute_s=one('eep', lambda x: int(x)), app_key_full=one('app_full'), app_key_last6=None if one('app_full') in (None, 'CONFLICT') else one('app_full')[-6:],
                         order_number=one('order_no'), algo_id=one('algo_id'), first_fill_ts=int(g.epoch.min()), last_fill_ts=int(g.epoch.max()), n_fills=len(g), filled_units=int(g.qty_units.sum()), requested_units=int(g.qty_order.iloc[0]),
                         first_source_row=int(g.src_row.min()), last_source_row=int(g.src_row.max()), parent_role=roles_by_parent.get(pid)))
    return rows
