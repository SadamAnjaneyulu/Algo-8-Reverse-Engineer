"""Data-quality and coverage report computed from the normalized files + manifest. Distinguishes: observed, empty (provider returned nothing), no_bars (contract listed but no candle that day), failed, pending."""
import glob, json, os
import numpy as np, pandas as pd
from datetime import date
from . import config as C
from .calendar_rules import expected_option_minutes, split_of


def load(store, kind, und):
    parts = []
    for f in sorted(glob.glob(store.path('normalized', kind, und, '**', '*.csv'), recursive=True)):
        x = pd.read_csv(f); x['_file'] = os.path.relpath(f, store.root); parts.append(x)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def report(store, und, out_dir):
    os.makedirs(out_dir, exist_ok=True); R = dict(underlying=und, generated_for_window=[str(C.WINDOW_START), str(C.WINDOW_END)])
    db = store.db
    R['manifest_tasks'] = store.counts()
    R['contract_day_status'] = {f'{k}:{s}': n for k, s, n in db.execute('SELECT kind,status,COUNT(*) FROM contract_days GROUP BY kind,status')}
    R['request_log_total'] = db.execute('SELECT COUNT(*) FROM request_log').fetchone()[0]
    ix = load(store, 'index', und)
    if len(ix):
        ix['ts'] = pd.to_datetime(ix.timestamp_ist.str.slice(0, 19)); ix['day'] = ix.ts.dt.date
        g = ix.groupby('day').agg(bars=('ts', 'size'), first=('ts', 'min'), last=('ts', 'max'))
        R['index'] = dict(sessions=len(g), first=str(g.index.min()), last=str(g.index.max()), bars_per_session=g.bars.value_counts().sort_index().to_dict(), duplicate_timestamps=int(ix.duplicated('ts').sum()),
                          ohlc_inconsistent=int(((ix.high < ix[['open', 'close', 'low']].max(axis=1)) | (ix.low > ix[['open', 'close', 'high']].min(axis=1))).sum()), provider_volume_all_zero_or_blank=bool((pd.to_numeric(ix.provider_volume, errors='coerce').fillna(0) == 0).all()))
        wk = [d.date() for d in pd.bdate_range(C.WINDOW_START, C.WINDOW_END)]
        R['index']['weekdays_in_window'] = len(wk); R['index']['weekdays_without_data'] = [str(d) for d in wk if d not in set(g.index)][:200]
        R['index']['weekdays_without_data_count'] = len([d for d in wk if d not in set(g.index)])
        R['index']['weekdays_empty_response'] = [r[0] for r in db.execute("SELECT trade_day FROM contract_days WHERE kind='index' AND und=? AND status='EMPTY' ORDER BY trade_day", (und,))]
    op = load(store, 'option', und)
    if len(op):
        op['ts'] = pd.to_datetime(op.timestamp_ist.str.slice(0, 19)); op['day'] = op.ts.dt.date; op['expiry'] = pd.to_datetime(op.expiry_date).dt.date
        key = ['expiry', 'strike', 'option_type', 'day']
        cd = op.groupby(key).agg(bars=('ts', 'size'), vol0=('volume', lambda s: int((s == 0).sum())), oi_blank=('open_interest', lambda s: int(s.isna().sum())), src=('source_id', 'first')).reset_index()
        cd['expected'] = cd.day.map(expected_option_minutes); cd['missing'] = cd.expected - cd.bars; cd['split'] = cd.day.map(split_of); cd['dte_days'] = (pd.to_datetime(cd.expiry) - pd.to_datetime(cd.day)).dt.days
        cd.to_csv(os.path.join(out_dir, f'{und}_option_contract_day_quality.csv'), index=False)
        R['options'] = dict(rows=len(op), contract_days=len(cd), expiries=int(op.expiry.nunique()), first_day=str(op.day.min()), last_day=str(op.day.max()), duplicate_keys=int(op.duplicated(['ts', 'expiry', 'strike', 'option_type']).sum()),
                            ohlc_inconsistent=int(((op.high < op[['open', 'close', 'low']].max(axis=1)) | (op.low > op[['open', 'close', 'high']].min(axis=1))).sum()), zero_price_rows=int((op[['open', 'high', 'low', 'close']] == 0).any(axis=1).sum()),
                            off_tick_close_rows=int((((op.close * 20).round(6) % 1) != 0).sum()), zero_volume_rows=int((op.volume == 0).sum()), blank_volume_rows=int(op.volume.isna().sum()), blank_open_interest_rows=int(op.open_interest.isna().sum()),
                            contract_days_complete_grid=int((cd.missing <= 0).sum()), contract_days_with_missing_minutes=int((cd.missing > 0).sum()), missing_minutes_total=int(cd.missing.clip(lower=0).sum()),
                            by_split=cd.groupby('split').agg(contract_days=('bars', 'size'), expiries=('expiry', 'nunique')).to_dict('index'), by_source=cd.src.str.startswith('legacy').map({True: 'legacy_local_breeze_v1', False: 'breeze_v2'}).value_counts().to_dict())
        ex = pd.DataFrame(db.execute("SELECT expiry, tier, status, COUNT(*) n FROM tasks WHERE kind='option' AND tier>0 GROUP BY expiry,tier,status").fetchall(), columns=['expiry', 'tier', 'status', 'n'])
        ex.to_csv(os.path.join(out_dir, f'{und}_option_task_status_by_expiry.csv'), index=False)
        cov = cd.groupby('expiry').agg(contract_days=('bars', 'size'), strikes=('strike', 'nunique'), bars=('bars', 'sum')).reset_index(); cov.to_csv(os.path.join(out_dir, f'{und}_option_coverage_by_expiry.csv'), index=False)
        R['options']['expiries_with_any_data'] = len(cov)
    json.dump(R, open(os.path.join(out_dir, f'{und}_coverage_report.json'), 'w'), indent=1, default=str); return R
