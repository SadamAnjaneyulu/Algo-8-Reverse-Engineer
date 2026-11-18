"""Phase 1: normalised, chronological fill-event ledger + data-quality report.
python3 tp_reconstruction/scripts/build_event_ledger.py
Writes data/fill_event_ledger.parquet, analysis/data_quality_report.csv, data/source_manifest.json.
Every raw row is kept (flagged, never dropped); `src_row` is the 0-based row of the raw file (file line = src_row + 1)."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp_common as tc

IST = pd.Timedelta(hours=5, minutes=30)


def load_raw(path=None):
    return pd.read_csv(path or tc.RAW, header=None, dtype=str, keep_default_na=False)


def build_ledger(raw):
    """raw string frame -> fill-level ledger (all rows kept, in file order, with quality flags)"""
    C = tc.COL; n = len(raw)
    num = lambda c: pd.to_numeric(raw[C[c]], errors='coerce')
    L = pd.DataFrame({'src_row': np.arange(n), 'src_line': np.arange(n) + 1})
    L['epoch'] = num('epoch_trade'); L['t_fill'] = pd.to_datetime(L.epoch, unit='s') + IST; L['date'] = L.t_fill.dt.normalize()
    L['und'] = raw[C['und']].values; L['segment'] = raw[C['segment']].values
    parts = raw[C['desc']].str.split()
    L['instrument_desc'] = raw[C['desc']].values; L['desc_und'] = parts.str[0].values; L['desc_cp'] = parts.str[2].values
    L['expiry'] = pd.to_datetime(parts.str[1], format='%d%b%Y', errors='coerce').values
    L['strike'] = num('strike').values; L['cp'] = raw[C['cp']].values; L['desc_strike'] = pd.to_numeric(parts.str[3], errors='coerce').values
    L['expiry_col'] = pd.to_datetime(raw[C['expiry_text']].str.split().str[0], format='%m/%d/%Y', errors='coerce').values
    L['contract_id'] = (L.und + '|' + L.expiry.dt.strftime('%Y-%m-%d') + '|' + L.cp + '|' + L.strike.map(lambda v: f'{v:g}')).values
    L['token'] = raw[C['token']].values; L['symbol'] = raw[C['symbol']].values
    L['side'] = raw[C['side']].values; L['sgn'] = np.where(L.side == 'Buy', 1, np.where(L.side == 'Sell', -1, 0))
    L['qty_units'] = num('qty_fill').values; L['lot_units'] = L.und.map(tc.LOT).values; L['qty_lots'] = L.qty_units / L.lot_units
    L['px_fill'] = num('px_fill').values; L['px_order_avg'] = num('px_order_avg').values; L['px_limit'] = num('px_limit').values
    L['qty_order'] = num('qty_order').values; L['qty_remaining_after'] = num('qty_remaining').values
    L['order_status'] = raw[C['status']].values; L['order_status_code'] = raw[C['status_code']].values
    L['parent_oid'] = raw[C['parent_oid']].values; L['order_no'] = raw[C['order_no']].values; L['trade_id'] = raw[C['trade_id']].values
    L['module'] = L.parent_oid.str.extract(r'^([a-z]+_)')[0].fillna('num').values        # num = body; h_ wing; s_ cycle stop; v_ lump; m_ manual
    L['app_key'] = raw[C['app_key']].str[-6:].values
    L['order_entry_minute'] = pd.to_datetime(raw[C['order_entry_text']], format='%m/%d/%Y %H:%M', errors='coerce').values   # NOT an execution time
    # ----- sequence: primary order (second, file row) and tie-group annotation inside one contract-second
    L['seq'] = np.lexsort((L.src_row.values, L.epoch.values)); L['seq'] = pd.Series(L.seq.values).rank(method='first').astype(int).values - 1
    g = L.groupby(['contract_id', 'epoch'])
    L['tie_group_size'] = g.src_row.transform('size').values
    L['tie_group_mixed_side'] = (g.sgn.transform(lambda s: (s > 0).any() and (s < 0).any())).values
    # ----- quality flags (row level; nothing is dropped)
    dkey = ['parent_oid', 'trade_id', 'epoch', 'qty_units', 'px_fill', 'side', 'contract_id']
    L['dq_duplicate_fill'] = L.duplicated(dkey, keep='first').values
    L['dq_missing_field'] = L[['epoch', 'qty_units', 'px_fill', 'strike', 'expiry']].isna().any(axis=1).values | (L.sgn == 0).values | (L.cp == '') | (L.parent_oid == '')
    L['dq_bad_qty'] = ~(L.qty_units > 0) | ((L.qty_units % L.lot_units) != 0)
    L['dq_bad_price'] = ~(L.px_fill > 0) | (np.abs(L.px_fill / tc.TICK - np.round(L.px_fill / tc.TICK)) > 1e-6)
    L['dq_id_mismatch'] = (L.desc_und != L.und) | (L.desc_cp != L.cp) | (L.desc_strike != L.strike) | (L.expiry != L.expiry_col)
    L['dq_post_expiry'] = L.date > L.expiry
    L['dq_price_differs_from_order_avg'] = np.abs(L.px_fill - L.px_order_avg) > 1e-9      # informational: order-average semantics of col 18
    L['dq_partial_fill'] = L.order_status.eq('PartiallyFilled').values | L.groupby('parent_oid').src_row.transform('size').gt(1).values
    L['dq_flag_any'] = L[['dq_duplicate_fill', 'dq_missing_field', 'dq_bad_qty', 'dq_bad_price', 'dq_id_mismatch', 'dq_post_expiry']].any(axis=1)
    L['sess_time_ok'] = (L.t_fill.dt.time >= pd.Timestamp('09:15').time()) & (L.t_fill.dt.time <= pd.Timestamp('15:40').time())
    return L.sort_values('seq').reset_index(drop=True)


def quality_report(L, raw):
    """list of dicts: check, value, status (PASS / FLAG / INFO), note"""
    C = tc.COL; rows = []
    add = lambda check, value, status, note='': rows.append(dict(check=check, value=value, status=status, note=note))
    add('raw rows', len(raw), 'INFO'); add('parent orders (col 163)', raw[C['parent_oid']].nunique(), 'INFO')
    add('order numbers (col 4), reused across days', raw[C['order_no']].nunique(), 'INFO', 'not an order identity')
    add('sessions', L.date.nunique(), 'INFO', f'{L.date.min().date()} to {L.date.max().date()}')
    add('contracts', L.contract_id.nunique(), 'INFO')
    ep = pd.to_numeric(raw[C['epoch_trade']]); add('file order chronological (execution second)', int((ep.diff() < 0).sum()), 'PASS' if (ep.diff() < 0).sum() == 0 else 'FLAG', 'number of backward steps')
    add('duplicate raw rows', int(raw.duplicated().sum()), 'PASS' if not raw.duplicated().any() else 'FLAG')
    add('duplicate fills (order, trade id, time, qty, price, side, contract)', int(L.dq_duplicate_fill.sum()), 'PASS' if not L.dq_duplicate_fill.any() else 'FLAG')
    add('trade id not unique (rows sharing an id)', int(L.trade_id.duplicated(keep=False).sum()), 'FLAG' if L.trade_id.duplicated(keep=False).any() else 'PASS', 'trade id is a reference, never a key')
    add('missing / unparseable key fields', int(L.dq_missing_field.sum()), 'PASS' if not L.dq_missing_field.any() else 'FLAG')
    add('non-positive or non-lot-multiple quantity', int(L.dq_bad_qty.sum()), 'PASS' if not L.dq_bad_qty.any() else 'FLAG')
    add('non-positive or off-tick fill price (col 137)', int(L.dq_bad_price.sum()), 'PASS' if not L.dq_bad_price.any() else 'FLAG', f'tick {tc.TICK}')
    add('instrument fields inconsistent with description', int(L.dq_id_mismatch.sum()), 'PASS' if not L.dq_id_mismatch.any() else 'FLAG')
    tok = L.groupby('token').contract_id.nunique(); add('exchange tokens mapping to >1 contract', int((tok > 1).sum()), 'FLAG' if (tok > 1).any() else 'PASS', 'token reused across expiries; identity uses (underlying, expiry, type, strike)')
    add('fills dated after the contract expiry', int(L.dq_post_expiry.sum()), 'PASS' if not L.dq_post_expiry.any() else 'FLAG')
    add('fills outside 09:15-15:40', int((~L.sess_time_ok).sum()), 'PASS' if L.sess_time_ok.all() else 'FLAG')
    add('fills after 15:30 (post-close)', int((L.t_fill.dt.time > pd.Timestamp('15:30').time()).sum()), 'INFO')
    add('price min / max (col 137)', f'{L.px_fill.min()} / {L.px_fill.max()}', 'INFO')
    add('fills whose per-fill price differs from the running order average (col 18)', int(L.dq_price_differs_from_order_avg.sum()), 'INFO', 'col 18 is a running order average; col 137 is the fill price')
    ao = L.groupby('parent_oid').agg(sq=('qty_units', 'sum'), qo=('qty_order', 'first'), nf=('src_row', 'size'))
    add('orders with several fills', int((ao.nf > 1).sum()), 'INFO'); add('partially-filled rows', int(L.order_status.eq('PartiallyFilled').sum()), 'INFO')
    add('orders whose fills do not add up to the order quantity', int((ao.sq != ao.qo).sum()), 'FLAG' if (ao.sq != ao.qo).any() else 'PASS', 'unfilled remainder; fill rows are kept as executed')
    tg = L.groupby(['contract_id', 'epoch']).agg(n=('src_row', 'size'), mixed=('tie_group_mixed_side', 'first'))
    add('contract-seconds with >= 2 fills', int((tg.n > 1).sum()), 'INFO'); add('contract-seconds mixing buys and sells (ordering ambiguity)', int(tg.mixed.sum()), 'FLAG' if tg.mixed.any() else 'PASS', 'alternative orderings are run in the sensitivity')
    add('module tags', '; '.join(f'{k}:{v}' for k, v in L.module.value_counts().items()), 'INFO', 'num = body, h_ wing, s_ cycle stop, v_ lump, m_ manual')
    add('charge / brokerage fields in the raw file', 0, 'FLAG', 'none exist: net P&L is not computed')
    return pd.DataFrame(rows)


def main():
    raw = load_raw(); L = build_ledger(raw); R = quality_report(L, raw)
    L.to_parquet(os.path.join(tc.DATA, 'fill_event_ledger.parquet'), index=False)
    R.to_csv(os.path.join(tc.ANALYSIS, 'data_quality_report.csv'), index=False)
    json.dump(dict(raw_file=tc.CFG['source']['raw_trades'], sha256=tc.sha256(tc.RAW), rows=len(raw), columns=int(raw.shape[1]), ledger_rows=len(L), flagged_rows=int(L.dq_flag_any.sum())),
              open(os.path.join(tc.DATA, 'source_manifest.json'), 'w'), indent=2)
    pd.set_option('display.width', 220); pd.set_option('display.max_colwidth', 90); print(R.to_string(index=False))


if __name__ == '__main__':
    main()
