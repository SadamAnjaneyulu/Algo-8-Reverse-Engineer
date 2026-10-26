"""Observed allocation quantities and premium flows; no inferred margin budget."""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import median

from audit_strike_hedge_rules import OUT, logs, reconstruct_parents
from rank_trigger_probabilities import save_records
from clarify_position_lifecycle import inventory_at


def frozen_expiry_bound(inventory, cash):
    if sum(q for (k, ot), q in inventory.items() if ot == 'CE') < 0:
        return None
    levels = {0} | {k for k, ot in inventory}
    minimum = min(cash+sum(q*(max(spot-k, 0) if ot == 'CE' else max(k-spot, 0))
                            for (k, ot), q in inventory.items()) for spot in levels)
    return max(0., -minimum)


def main():
    fills = logs.read_fills()
    parents = reconstruct_parents(fills)
    grouped = defaultdict(list)
    for r in fills:
        grouped[(r['u'], str(r['expiry']))].append(r)
    rows = []
    clocks = ['09:16'] + [f'{m // 60:02}:{m % 60:02}' for m in range(570, 871, 15)]
    for (u, expiry), records in sorted(grouped.items()):
        for day in sorted({str(r['t'].date()) for r in records}):
            phase = 'preexpiry' if day < expiry else 'expiry'
            for clock in clocks:
                t = datetime.fromisoformat(day + 'T' + clock).replace(tzinfo=logs.IST)
                start = t - timedelta(minutes=1) if clock == '09:16' else t - timedelta(seconds=2)
                end = t + timedelta(minutes=1 if clock == '09:16' else 3)
                selected = [r for r in records if start <= r['t'] < end]
                parent_group = [p for p in parents if p['underlying'] == u and p['expiry_date'] == expiry and start <= p['first'] < end]
                inv = inventory_at(records, end)
                row = dict(underlying=u, expiry_date=expiry, date=day, phase=phase, clock=clock,
                           split='calibration' if expiry <= '2026-08-31' else 'evaluation',
                           window_start_ist=start.isoformat(), window_end_exclusive_ist=end.isoformat())
                for right in ('CE', 'PE'):
                    for side, name in [('Sell', 'short'), ('Buy', 'long')]:
                        rs = [r for r in selected if r['ot'] == right and r['side'] == side]
                        q = sum(r['opening'] for r in rs)
                        row[f'new_{name}_{right}_quantity'] = q
                        row[f'new_{name}_{right}_units'] = q / logs.UNIT[u]
                        row[f'new_{name}_{right}_premium_cash'] = sum(float(r['price']) * r['opening'] for r in rs)
                        role = 'new_short' if name == 'short' else 'new_long'
                        row[f'new_{name}_{right}_pure_parents'] = sum(p['option_type'] == right and p['role'] == role for p in parent_group)
                        row[f'inventory_{name}_{right}'] = sum(abs(qty) for (k, ot), qty in inv.items() if ot == right and (qty < 0 if name == 'short' else qty > 0))
                row['new_short_premium_receipts'] = row['new_short_CE_premium_cash'] + row['new_short_PE_premium_cash']
                row['new_long_premium_spend'] = row['new_long_CE_premium_cash'] + row['new_long_PE_premium_cash']
                row['net_new_opening_premium_credit'] = row['new_short_premium_receipts'] - row['new_long_premium_spend']
                row['tie_sensitive_fill_records'] = sum(r['opening'] != r['reverse_opening'] for r in selected)
                known_cash = -sum(r['signed']*float(r['price']) for r in records if r['t'] < end)
                row['after_window_frozen_expiry_max_loss_before_costs'] = frozen_expiry_bound(inv, known_cash)
                rows.append(row)
    save_records('allocation_window_sizes.csv', rows)
    summaries = []
    for u in ('NIFTY', 'SENSEX'):
        for phase in ('preexpiry', 'expiry'):
            for clock in clocks:
                rs = [r for r in rows if r['underlying'] == u and r['phase'] == phase and r['clock'] == clock]
                if not rs:
                    continue
                quantities = [(r['new_short_CE_quantity'], r['new_short_PE_quantity'], r['new_long_CE_quantity'], r['new_long_PE_quantity']) for r in rs]
                modal, count = Counter(quantities).most_common(1)[0]
                summaries.append(dict(underlying=u, phase=phase, clock=clock, sessions=len(rs),
                                      modal_short_CE=modal[0], modal_short_PE=modal[1], modal_long_CE=modal[2], modal_long_PE=modal[3],
                                      modal_joint_sessions=count, modal_joint_fraction=count / len(rs),
                                      sessions_with_new_short=sum(r['new_short_CE_quantity'] + r['new_short_PE_quantity'] > 0 for r in rs),
                                      median_short_CE=median(r['new_short_CE_quantity'] for r in rs),
                                      median_short_PE=median(r['new_short_PE_quantity'] for r in rs),
                                      median_short_receipts=median(r['new_short_premium_receipts'] for r in rs),
                                      median_long_spend=median(r['new_long_premium_spend'] for r in rs),
                                      median_net_opening_credit=median(r['net_new_opening_premium_credit'] for r in rs)))
    save_records('allocation_size_schedule.csv', summaries)
    (OUT / 'allocation_size_summary.json').write_text(json.dumps(dict(
        windows=len(rows), schedules=summaries,
        limitation='Observed quantities/premium flows, not broker margin, capital allocation, maximum loss or original exchange lot rules. Four roles can contain multiple strikes and parents; cohort modes can have exceptions. Opening fields use inferred inventory roles; tie-sensitive fills remain flagged.'), indent=2) + '\n')
    for r in summaries:
        if r['phase'] == 'preexpiry' and r['clock'] in ('09:16', '09:30', '09:45', '10:00', '12:30', '14:30'):
            print(r, flush=True)


if __name__ == '__main__':
    main()
