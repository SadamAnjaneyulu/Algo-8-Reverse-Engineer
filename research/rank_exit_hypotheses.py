"""Evidence rates for named exit hypotheses, including failed/absent triggers."""
import json

from audit_strike_hedge_rules import OUT
from rank_trigger_probabilities import save_records, wilson
from search_exit_combinations import build_inputs, condition, minute


def main():
    cycles = build_inputs()
    atoms = {
        'time_only': dict(kind='false'),
        'net_cycle_loss_0.5pct': dict(kind='threshold', field='net_equity_pct_capital', threshold=-.5, operator='le'),
        'net_cycle_loss_1pct': dict(kind='threshold', field='net_equity_pct_capital', threshold=-1, operator='le'),
        'short_book_loss_1pct': dict(kind='threshold', field='short_book_equity_pct_capital', threshold=-1, operator='le'),
        'net_from_previous_close_loss_1pct': dict(kind='threshold', field='net_equity_change_previous_close_pct_capital', threshold=-1, operator='le'),
        'open_short_credit_loss_4pct': dict(kind='threshold', field='short_unrealized_pct_credit', threshold=-4, operator='le'),
    }
    records = []
    for cycle in cycles:
        points = [p for p in cycle['path'] if p['short_quantity'] > 0]
        for name, atom in atoms.items():
            first = next((minute(p['t']) for p in points if condition(atom, p)), None)
            for cutoff in (914, 915):
                clock = 925 if cycle['expiry_date'] < '2026-08-03' else cutoff
                guess = min(first, clock) if first is not None else clock
                for target_kind in ('material_95pct', 'first_short_flat', 'final_short_flat'):
                    target = cycle['targets'][target_kind]
                    if target is None:
                        continue
                    records.append(dict(underlying=cycle['underlying'], expiry_date=cycle['expiry_date'],
                                        split='calibration' if cycle['expiry_date'] <= '2026-08-31' else 'evaluation',
                                        hypothesis=name + '_OR_time', after_aug3_cutoff=cutoff,
                                        target_kind=target_kind, first_price_trigger=first,
                                        predicted_minute=guess, observed_minute=target,
                                        observed_regime='early' if target < 885 else 'late',
                                        matched_2m=abs(target - guess) <= 2, error_minutes=guess - target))
    summaries = []
    for name in atoms:
        for cutoff in (914, 915):
            for target_kind in ('material_95pct', 'first_short_flat', 'final_short_flat'):
                for split in ('calibration', 'evaluation'):
                    for regime in ('all', 'early', 'late'):
                        rows = [r for r in records if r['hypothesis'] == name + '_OR_time'
                                and r['after_aug3_cutoff'] == cutoff and r['target_kind'] == target_kind
                                and r['split'] == split and (regime == 'all' or r['observed_regime'] == regime)]
                        hits, n = sum(r['matched_2m'] for r in rows), len(rows)
                        low, high = wilson(hits, n)
                        summaries.append(dict(hypothesis=name + '_OR_time', after_aug3_cutoff=cutoff,
                                              target_kind=target_kind, split=split, regime=regime, cycles=n,
                                              matches_2m=hits, match_probability=hits / n if n else None,
                                              wilson_lower=low, wilson_upper=high,
                                              mean_abs_error_minutes=sum(abs(r['error_minutes']) for r in rows) / n if n else None))
    save_records('prob_exit_hypotheses.csv', summaries)
    save_records('prob_exit_hypothesis_predictions.csv', records)
    (OUT / 'prob_exit_hypotheses.json').write_text(json.dumps(dict(
        later=[r for r in summaries if r['split'] == 'evaluation'],
        note='Named hypothetical first-crossing controllers on the actual book. Match frequency is not a posterior probability of original-code identity. Early/late strata use observed outcomes and are descriptive, not an executable regime classifier. Opening proxies and partial quote coverage apply.'), indent=2) + '\n')


if __name__ == '__main__':
    main()
