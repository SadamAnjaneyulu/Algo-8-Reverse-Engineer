"""Attribute recorded round-trip profits to short and long option positions.

FIFO within contracts; complete-cycle totals reconcile exactly to cashflow.
This is trade accounting, not a theta/IV attribution or a counterfactual backtest.
"""
import csv
import json
from collections import defaultdict, deque
from decimal import Decimal

import analyze_index_triggers as logs

OUT=logs.OUT


def attribute(fills):
    lots=defaultdict(deque)
    short_pnl=Decimal(0)
    long_pnl=Decimal(0)
    cash=Decimal(0)
    for r in fills:
        q,price=r['signed'],Decimal(r['price'])
        cash-=q*price
        queue=lots[(r['strike'],r['ot'])]
        while q and queue and (q>0)!=(queue[0][0]>0):
            old_q,old_price=queue[0]
            matched=min(abs(q),abs(old_q))
            if old_q>0:
                long_pnl+=matched*(price-old_price)
            else:
                short_pnl+=matched*(old_price-price)
            old_q+=matched if old_q<0 else -matched
            q+=matched if q<0 else -matched
            if old_q:
                queue[0]=(old_q,old_price)
            else:
                queue.popleft()
        if q:
            queue.append((q,price))
    residual=sum(bool(v) for v in lots.values())
    if not residual:
        assert short_pnl+long_pnl==cash
    return dict(short_position_realized_pnl_fifo=str(short_pnl),long_position_realized_pnl_fifo=str(long_pnl),
                observed_cashflow_before_costs=str(cash),residual_contracts=residual,fully_flat=not residual,
                conditional_on_zero_opening_inventory=True)


def main():
    groups=defaultdict(list)
    for r in logs.read_fills():
        groups[(r['u'],str(r['expiry']))].append(r)
    records=[dict(underlying=u,expiry_date=e,**attribute(fills)) for (u,e),fills in sorted(groups.items())]
    with (OUT/'option_profit_source_cycles.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator='\n')
        w.writeheader()
        w.writerows(records)
    summary=dict(cycles=len(records),fully_flat_cycles=sum(r['fully_flat'] for r in records),
                 example_nifty_2026_07_07=next(r for r in records if r['underlying']=='NIFTY' and r['expiry_date']=='2026-07-07'),
                 note='No all-strategy return estimate. Residual positions, opening inventory, external settlement and costs remain unresolved; short/long attribution does not identify theta, IV or directional effects.')
    (OUT/'option_profit_source_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
