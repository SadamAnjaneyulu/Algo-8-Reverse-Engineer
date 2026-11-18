"""P&L reconciliation: lot-level P&L vs exact fill-level ledger cash, per cycle and per allocation convention; coverage of short activity; comparison with the earlier order-level gross."""
from ledger import *
from lots import CONVENTIONS
L = pd.read_csv(f'{OUT}/lots.csv.gz'); F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv'); LU = L['index'].map(LOT)
F['cash'] = -F.sgn * F.qty_fill * F.px; cash = F.groupby(['und', 'expiry']).cash.sum()
L['u'] = L['index'].map(LOT); L['settle_cash'] = np.where(L.close_reason == 'SETTLEMENT', np.where(L.side == 'SHORT', -1, 1) * L.close_price * L.u, 0.0)
L['unrec_close_cash'] = np.where(L.entry_unrecorded, -L.close_price * L.u, 0.0)
rows = []
for r in C.itertuples():
    x = L[(L['index'] == r.und) & (L.expiry == r.expiry)]; row = dict(und=r.und, expiry=r.expiry, carry_in_known=r.carry_in_known, ledger_cash=cash[(r.und, r.expiry)], settlement_cash=x.settle_cash.sum(), unrecorded_carry_in_lots=int(x.entry_unrecorded.sum()), unrecorded_close_cash=x.unrec_close_cash.sum())
    for c in CONVENTIONS: row[f'lot_pnl_{c}'] = x[f'pnl_{c}'].sum()
    row['identity_residual_FIFO'] = row['ledger_cash'] + row['settlement_cash'] - (row['lot_pnl_FIFO'] + row['unrecorded_close_cash']); row['anomalous_long_lots'] = int((x['flags'] == 'ANOMALOUS_OPEN_LONG_BY_BODY_BUY').sum()); row['open_short_lots'] = int((x.side == 'SHORT').sum()); rows.append(row)
R = pd.DataFrame(rows); old = pd.read_csv(f'{REPL}/results/live_cycle_pnl.csv'); old['expiry'] = old.expiry.str[:10]; R = R.merge(old[['und', 'expiry', 'gross']].rename(columns={'gross': 'earlier_order_level_gross'}), on=['und', 'expiry'])
R['reconstructed_gross_exact'] = R.ledger_cash + R.settlement_cash; R['diff_vs_earlier'] = R.reconstructed_gross_exact - R.earlier_order_level_gross; R.to_csv(f'{OUT}/cycle_reconciliation.csv', index=False)
pd.set_option('display.width', 250); print('max |identity residual| over cycles:', R.identity_residual_FIFO.abs().max().round(6)); print('total gross (ledger cash + settlement):', R.reconstructed_gross_exact.sum().round(0), ' earlier:', R.earlier_order_level_gross.sum().round(0), ' diff', R.diff_vs_earlier.sum().round(0), ' max |diff| per cycle', R.diff_vs_earlier.abs().max().round(0))
k = R[R.carry_in_known]; print('cycles with known carry-in:', len(k), ' sum lot pnl (all conventions equal):', {c: round(k[f'lot_pnl_{c}'].sum()) for c in CONVENTIONS}, ' ledger gross', round(k.reconstructed_gross_exact.sum()))
print('unknown-carry-in cycles: unrecorded lots', int(R[~R.carry_in_known].unrecorded_carry_in_lots.sum()), ' their closing cash', round(R.unrecorded_close_cash.sum()))
# coverage of short activity
sell_lots = int(F[F.side == 'Sell'].n_lots.sum()); short_open = int(((L.side == 'SHORT') & (~L.entry_unrecorded)).sum()); long_closed_by_sell = int(((L.side == 'LONG') & (L.close_module != '') & (L.close_reason != 'SETTLEMENT') & L.close_row.ge(0)).sum())
buy_lots = int(F[F.side == 'Buy'].n_lots.sum()); print('sell lots in ledger', sell_lots, '= short lots opened', short_open, '+ long lots closed by sells', long_closed_by_sell, '(sum', short_open + long_closed_by_sell, ')')
print('buy lots', buy_lots, '= long lots opened', int((L.side == 'LONG').sum()), '+ short lots closed by buys (incl. unrecorded)', int(((L.side == 'SHORT') & L.close_row.ge(0) & (L.close_reason != 'SETTLEMENT')).sum()))
print('short lots by disposition:', L[L.side == 'SHORT'].close_reason.value_counts().to_dict()); print('short lots with confidence:', L[L.side == 'SHORT'].confidence.value_counts().to_dict(), ' body shorts:', L[(L.side == 'SHORT') & (L.role == 'body')].confidence.value_counts().to_dict())
# convention spread of per-lot class P&L (body shorts)
b = L[(L.side == 'SHORT') & (L.role == 'body') & (~L.entry_unrecorded)]; print('body short lot pnl totals by convention:', {c: round(b[f'pnl_{c}'].sum()) for c in CONVENTIONS})
