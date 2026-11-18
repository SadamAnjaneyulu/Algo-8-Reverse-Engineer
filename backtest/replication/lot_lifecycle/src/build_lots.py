"""Builds the lot lifecycle dataset under every allocation convention and merges them into one table (FIFO primary + per-convention close/pnl columns + ownership-ambiguity flags)."""
from ledger import *
from lots import *
YAH = {u: pd.read_csv(f'{ROOT}/data_validation/reference/yahoo_daily_{s}.csv').assign(date=lambda x: pd.to_datetime(x.date_ist)).set_index('date').close for u, s in (('NIFTY', 'NSEI'), ('SENSEX', 'BSESN'))}
settle = lambda u, e: float(YAH[u].get(pd.Timestamp(e), np.nan))
F = load_fills(); C = cycle_table(F); C.to_csv(f'{OUT}/cycles.csv', index=False)
T = {c: build_all(F, C, c, settle) for c in CONVENTIONS}
base = T['FIFO'].copy(); key = ['lot_id']
for c in CONVENTIONS:
    t = T[c].set_index('lot_id'); base[f'close_row_{c}'] = base.lot_id.map(t.close_row); base[f'pnl_{c}'] = base.lot_id.map(t.realized_pnl)
rows = [f'close_row_{c}' for c in CONVENTIONS]
base['alloc_agree_all'] = base[rows].nunique(axis=1) == 1                                                        # same closing fill under every convention
base['confidence'] = np.where(base.entry_unrecorded, 'ENTRY_UNRECORDED', np.where(base.alloc_agree_all, 'ALLOCATION_UNAMBIGUOUS', 'ALLOCATION_AMBIGUOUS'))
base['unresolved_flags'] = base.flags
base.to_csv(f'{OUT}/lots.csv.gz', index=False); print(len(base), 'unit lots;', base.groupby(['role', 'side']).size().to_dict())
print('allocation agree (all 4 conventions):', base.alloc_agree_all.mean().round(4), ' by role:', base.groupby('role').alloc_agree_all.mean().round(3).to_dict())
print('flags:', base['flags'].value_counts().to_dict()); print('close reasons:', base.close_reason.value_counts().to_dict())
