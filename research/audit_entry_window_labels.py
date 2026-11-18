"""Separate no new shorts from no same-strike CE/PE pair in timer windows."""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from audit_strike_hedge_rules import OUT, logs
from rank_trigger_probabilities import save_records


def main():
    sizes = {(r['underlying'], r['expiry_date'], r['date'], r['clock']): r
             for r in csv.DictReader((OUT/'allocation_window_sizes.csv').open())}
    previous = [r for r in csv.DictReader((OUT/'combo_active_book_predictions.csv').open()) if r['kind'] == 'active_book_only']
    fills = logs.read_fills()
    grouped = defaultdict(list)
    for r in fills:
        grouped[(r['u'], str(r['expiry']), str(r['t'].date()))].append(r)
    rows = []
    for old in previous:
        key = (old['underlying'], old['expiry_date'], old['date'], old['clock'])
        s = sizes[key]
        ce, pe = float(s['new_short_CE_quantity']), float(s['new_short_PE_quantity'])
        t = datetime.fromisoformat(old['date']+'T'+old['clock']).replace(tzinfo=logs.IST)
        opening = [r for r in grouped[key[:3]] if t-timedelta(seconds=2) <= r['t'] < t+timedelta(minutes=3)
                   and r['side'] == 'Sell' and r['opening'] > 0]
        ce_strikes = sorted({r['strike'] for r in opening if r['ot'] == 'CE'})
        pe_strikes = sorted({r['strike'] for r in opening if r['ot'] == 'PE'})
        rows.append(dict(underlying=old['underlying'], expiry_date=old['expiry_date'], date=old['date'], phase=old['phase'],
                         clock=old['clock'], active_book=int(old['predicted']), old_same_strike_pair=int(old['target']),
                         new_short_ce=ce, new_short_pe=pe, any_new_short=int(ce+pe > 0), both_rights_new=int(ce > 0 and pe > 0),
                         ce_strikes=';'.join(map(str, ce_strikes)), pe_strikes=';'.join(map(str, pe_strikes)),
                         same_strike_overlap=';'.join(map(str, sorted(set(ce_strikes)&set(pe_strikes)))),
                         case_type='both_rights' if ce and pe else 'CE_only' if ce else 'PE_only' if pe else 'no_new_short',
                         tie_sensitive_fills=int(s['tie_sensitive_fill_records'])))
    special = [r for r in rows if r['phase'] == 'expiry' and r['active_book'] and not r['old_same_strike_pair']]
    summaries = []
    for u in ('NIFTY', 'SENSEX', 'all'):
        rs = [r for r in rows if r['phase'] == 'expiry' and (u == 'all' or r['underlying'] == u)]
        active = [r for r in rs if r['active_book']]
        summaries.append(dict(underlying=u, later_expiry_windows=len(rs), active_windows=len(active),
                              active_old_same_strike_pairs=sum(r['old_same_strike_pair'] for r in active),
                              active_any_new_short=sum(r['any_new_short'] for r in active),
                              active_both_rights=sum(r['both_rights_new'] for r in active),
                              inactive_but_new_short=sum(r['any_new_short'] for r in rs if not r['active_book'])))
    save_records('allocation_entry_window_labels.csv', rows)
    save_records('allocation_27_window_label_audit.csv', special)
    (OUT/'allocation_entry_label_summary.json').write_text(json.dumps(dict(
        former_27_types=dict(Counter(r['case_type'] for r in special)), summary=summaries,
        correction='The old label required a same-strike CE/PE opening pair. It was incorrectly described as absence of any addition. Both-right and one-right sales require different entry targets, not a fabricated range-filter rejection.'), indent=2)+'\n')
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
