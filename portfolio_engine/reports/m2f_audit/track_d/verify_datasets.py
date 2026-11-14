"""[RAW]+[IMPL] Compare M2-E datasets and V1/V2/V3 figure CSVs with values recomputed from the RAW ledger by raw_truth.py (no pe.* imports).
Usage: python3 -I verify_datasets.py [ROOT]   ROOT = a portfolio_engine dir (default: the repo); used by the mutation harness with a scratch mirror."""
import sys, os, csv, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raw_truth as T

PE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(T.REPO, 'portfolio_engine')
DATA = os.path.join(PE, 'reports', 'm2e_data'); FIG = os.path.join(PE, 'reports', 'm2e_figures')
FAIL = []; OK = collections.Counter()


def rd(path, delim='\t'):
    with open(path, newline='') as fh: return list(csv.DictReader(fh, delimiter=delim))
def ck(name, cond, detail=''):
    if cond: OK[name] += 1
    else: FAIL.append((name, detail))


def check_cycle(und, exp):
    cy = f'{und}_{exp}'; t = T.truth(und, exp); fl = t['fills']; R = t['R']; ses = t['sessions']; D = os.path.join(DATA, cy); G = os.path.join(FIG, cy)
    # ---- fills.tsv
    F = rd(os.path.join(D, 'fills.tsv')); ck(f'{cy} fills count', len(F) == len(fl), f'{len(F)} vs raw {len(fl)}')
    oq = collections.Counter(); cq = collections.Counter()
    for a in R['oa']: oq[a['fill']['row']] += a['qty']
    for a in R['cp']: cq[a['fill']['row']] += a['qty']
    for r, f in zip(F, fl):
        ok = (int(r['source_row_id']) == f['row'] and r['parent_order_id'] == f['parent'] and r['module_tag'] == f['tag'] and r['instrument_id'] == f['iid'] and int(r['ts_utc_s']) == f['ts'] and int(r['side']) == f['side'] and int(r['quantity']) == f['qty']
              and int(r['exec_price_paise']) == f['px_paise'] and int(r['requested_quantity']) == f['req'] and r['order_status'] == f['status'] and r['ts_ist'] == T.ist_str(f['ts']) and r['session_ist'] == T.ist_date(f['ts']) and r['d_label'] == T.d_label(ses, exp, T.ist_date(f['ts']))
              and r['right'] == f['right'] and int(r['strike']) == f['strike'] and int(r['opening_qty']) == oq[f['row']] and int(r['closing_qty']) == cq[f['row']])
        ck(f'{cy} fills row', ok, f"row {f['row']}: {r}")
    ck(f'{cy} fills: price column discriminates (fills where col137 != col18)', sum(1 for f in fl if f['px_paise'] != f['px_order_avg_paise']) > 0)
    # ---- inventory_series.tsv (V1 dataset): state after each fill, from signed raw replay
    S = rd(os.path.join(D, 'inventory_series.tsv')); ck(f'{cy} inventory rows', len(S) == len(fl))
    co = cc = 0; cum_o = collections.Counter(); cum_c = collections.Counter(); oi = collections.defaultdict(list); ci = collections.defaultdict(list)
    for a in R['oa']: oi[a['fill']['row']].append(a)
    for a in R['cp']: ci[a['fill']['row']].append(a)
    for r, sv, f in zip(S, R['series'], fl):
        for a in oi[f['row']]:
            cum_o['all'] += a['qty']; k = 'num_short' if (f['tag'] == 'num' and f['side'] < 0) else 'h_long' if (f['tag'] == 'h_' and f['side'] > 0) else 'other'; cum_o[k] += a['qty']
        for a in ci[f['row']]: cum_c['all'] += a['qty']
        ok = (r['fill_id'] == f"F{f['row']:06d}" and all(int(r[c]) == sv[c] for c in ('short_CE', 'short_PE', 'long_CE', 'long_PE')) and int(r['net_CE']) == sv['long_CE'] - sv['short_CE'] and int(r['net_PE']) == sv['long_PE'] - sv['short_PE']
              and int(r['net_total']) == sv['long_CE'] + sv['long_PE'] - sv['short_CE'] - sv['short_PE'] and int(r['gross_total']) == sv['long_CE'] + sv['long_PE'] + sv['short_CE'] + sv['short_PE']
              and int(r['cum_opened_units']) == cum_o['all'] and int(r['cum_closed_units']) == cum_c['all'] and int(r['cum_opened_num_short']) == cum_o['num_short'] and int(r['cum_opened_h_long']) == cum_o['h_long'] and int(r['cum_opened_other']) == cum_o['other']
              and int(r['ts_utc_s']) == f['ts'] and int(r['fill_quantity']) == f['qty'] and int(r['fill_side']) == f['side'] and r['instrument_id'] == f['iid'] and r['d_label'] == T.d_label(ses, exp, T.ist_date(f['ts'])))
        ck(f'{cy} inventory row', ok, f'{r["seq"]} {f["row"]}')
    # ---- session_carry.tsv
    C = rd(os.path.join(D, 'session_carry.tsv')); last = {}
    for sv, f in zip(R['series'], fl): last[T.ist_date(f['ts'])] = (sv, f)
    ck(f'{cy} carry sessions', [r['session_ist'] for r in C] == ses)
    for r in C:
        sv, f = last[r['session_ist']]; ck(f'{cy} carry row', all(int(r[c]) == sv[c] for c in ('short_CE', 'short_PE', 'long_CE', 'long_PE')) and r['last_fill_id'] == f"F{f['row']:06d}" and int(r['gross_total']) == sum(sv[c] for c in ('short_CE', 'short_PE', 'long_CE', 'long_PE')), str(r))
    # ---- lifecycle_events.tsv
    L = rd(os.path.join(D, 'lifecycle_events.tsv')); ck(f'{cy} lifecycle count', len(L) == len(R['events']), f'{len(L)} vs {len(R["events"])}')
    byk = collections.defaultdict(list)
    for e in R['events']: byk[(e['eid'], e['fill']['row'])].append(e)
    for r in L:
        cand = byk.get((r['episode_id'], int(r['source_row_id'])), [])
        ok = any(e['kind'] == r['event_type'] and e['qty'] == int(r['quantity']) and e['inv_after'] == int(r['inventory_after']) and r['parent_order_id'] == e['fill']['parent'] and r['ts_utc_s'] == str(e['fill']['ts']) and r['direction'] == R['episodes'][e['eid']]['direction'] for e in cand)
        ck(f'{cy} lifecycle row', ok, str(r))
    # started_by_reversal flags / event multiset
    ck(f'{cy} lifecycle event multiset', collections.Counter((e['eid'], e['kind'], e['fill']['row'], e['qty']) for e in R['events']) == collections.Counter((r['episode_id'], r['event_type'], int(r['source_row_id']), int(r['quantity'])) for r in L))
    # ---- episodes.tsv
    E = rd(os.path.join(D, 'episodes.tsv')); ck(f'{cy} episode count', len(E) == len(R['episodes']), f'{len(E)} vs {len(R["episodes"])}')
    par = collections.defaultdict(set)
    for a in R['oa'] + R['cp']: par[a['eid']].add(a['fill']['parent'])
    for r in E:
        X = R['episodes'].get(r['episode_id']); ok = X is not None and int(r['opened']) == X['opened'] and int(r['closed']) == X['closed'] and int(r['remaining']) == X['opened'] - X['closed'] and r['direction'] == X['direction'] and int(r['n_open_fills']) == X['n_open'] and int(r['n_close_fills']) == X['n_close'] \
            and int(r['first_ts_utc_s']) == X['first_ts'] and int(r['last_ts_utc_s']) == X['last_ts'] and int(r['n_parents']) == len(par[r['episode_id']]) and int(r['started_by_reversal']) == int(X['by_reversal']) and r['ended_by'] == X['ended_by']
        ck(f'{cy} episode row', ok, str(r))
        if X: ck(f'{cy} episode terminal status consistent', (r['terminal_status'] in ('CLOSED', 'REVERSED')) == (X['opened'] == X['closed']), str(r))
    # ---- opening_items.tsv (V3 dataset)
    I = rd(os.path.join(D, 'opening_items.tsv')); items = t['items']; ck(f'{cy} item count', len(I) == len(items), f'{len(I)} vs {len(items)}')
    ck(f'{cy} item total qty == opening units', sum(int(r['quantity']) for r in I) == sum(a['qty'] for a in R['oa']))
    for r in I:
        k = (r['parent_order_id'], r['instrument_id']); d = items.get(k)
        if d is None: ck(f'{cy} item exists', False, str(k)); continue
        role = 'BODY_SHORT_BY_TAG' if (d['tag'] == 'num' and d['side'] < 0) else 'WING_LONG_BY_TAG' if (d['tag'] == 'h_' and d['side'] > 0) else f"UNCLASSIFIED({d['tag']},{'SELL' if d['side'] < 0 else 'BUY'})"
        ok = (int(r['quantity']) == d['qty'] and abs(float(r['avg_exec_price_paise']) - d['notional'] / d['qty']) < 1e-3 and int(r['n_opening_fills']) == d['n'] and int(r['first_ts_utc_s']) == d['first'] and int(r['last_ts_utc_s']) == d['last'] and r['tag_role'] == role
              and r['module_tag'] == d['tag'] and int(r['side']) == d['side'] and int(r['order_entry_minute_s']) == d['em'] and r['order_entry_minute_ist'] == T.ist_str(d['em']) and int(r['requested_units']) == d['req'] and r['order_number'] == d['order_no']
              and r['d_label'] == T.d_label(ses, exp, T.ist_date(d['first'])) and set(r['episode_ids'].split(';')) == d['eids'])
        ck(f'{cy} item row', ok, str(r))
    # ---- V1 figure CSV
    V1 = rd(os.path.join(G, 'V1_inventory_evolution.csv'), ','); fillrows = [r for r in V1 if r['row_kind'] == 'FILL']; ck(f'{cy} V1 FILL rows', len(fillrows) == len(fl))
    ck(f'{cy} V1 CARRY_IN rows = sessions', [r['session_ist'] for r in V1 if r['row_kind'] == 'CARRY_IN'] == ses)
    for r, sv, f in zip(fillrows, R['series'], fl): ck(f'{cy} V1 fill row', all(int(r[c]) == sv[c] for c in ('short_CE', 'short_PE', 'long_CE', 'long_PE')) and int(r['ts_utc_s']) == f['ts'] and r['ts_ist'] == T.ist_str(f['ts']) and r['d_label'] == T.d_label(ses, exp, r['session_ist']) and int(r['gross_total']) == sum(sv[c] for c in ('short_CE', 'short_PE', 'long_CE', 'long_PE')), str(r))
    for i, r in enumerate(V1):
        if r['row_kind'] == 'CARRY_IN':
            prev = [x for x in V1[:i] if x['row_kind'] == 'FILL']; z = prev[-1] if prev else None
            ck(f'{cy} V1 carry-in = previous state', all(int(r[c]) == (int(z[c]) if z else 0) for c in ('short_CE', 'short_PE', 'long_CE', 'long_PE', 'gross_total', 'cum_opened_units', 'cum_closed_units')), str(r))
            t0 = int(r['ts_utc_s']); ck(f'{cy} V1 carry-in time 09:15 IST of session', T.ist_str(t0) == r['session_ist'] + ' 09:15:00', r['ts_ist'])
    # ---- V2 figure CSV
    V2 = rd(os.path.join(G, 'V2_position_lifecycle_timeline.csv'), ','); ev = [r for r in V2 if r['record'] == 'EVENT']; ep = [r for r in V2 if r['record'] == 'EPISODE']
    ck(f'{cy} V2 episodes', len(ep) == len(R['episodes']) and {r['episode_id'] for r in ep} == set(R['episodes']), f'{len(ep)}')
    ck(f'{cy} V2 events multiset', collections.Counter((r['episode_id'], r['event_type'], int(r['source_row_id']), int(r['quantity'])) for r in ev) == collections.Counter((e['eid'], e['kind'], e['fill']['row'], e['qty']) for e in R['events']))
    for r in ev:
        ck(f'{cy} V2 event ts_ist', any(T.ist_str(e['fill']['ts']) == r['ts_ist'] and e['inv_after'] == int(r['inventory_after']) for e in byk[(r['episode_id'], int(r['source_row_id']))] if e['kind'] == r['event_type']), str(r))
    for r in ep: X = R['episodes'][r['episode_id']]; ck(f'{cy} V2 episode row', int(r['opened']) == X['opened'] and int(r['closed']) == X['closed'] and int(r['remaining']) == X['opened'] - X['closed'] and r['direction'] == X['direction'], str(r))
    # ---- V3 figure CSVs
    V3 = rd(os.path.join(G, 'V3_opening_activity_cohort_map.csv'), ','); ck(f'{cy} V3 items', len(V3) == len(items))
    for r in V3:
        d = items.get((r['parent_order_id'], r['instrument_id']))
        ck(f'{cy} V3 item', d is not None and int(r['quantity']) == d['qty'] and int(r['first_fill_ts_utc_s']) == d['first'] and r['first_fill_ts_ist'] == T.ist_str(d['first']) and r['order_entry_minute_ist'] == T.ist_str(d['em']) and r['session_ist'] == T.ist_date(d['first']) and r['d_label'] == T.d_label(ses, exp, T.ist_date(d['first'])), str(r))
    # cohorts: units per (session, entry minute) by tag-role class  (units of OPENING allocations grouped by the PARENT's order-entry minute)
    coh = collections.defaultdict(lambda: collections.Counter()); npar = collections.defaultdict(set)
    for (p, iid), d in items.items():
        cls = 'body' if (d['tag'] == 'num' and d['side'] < 0) else 'wing' if (d['tag'] == 'h_' and d['side'] > 0) else 'unclassified'
        k = (T.ist_date(d['first']), T.ist_str(d['em'])); coh[k][cls] += d['qty']; npar[k].add(p)
    CO = rd(os.path.join(G, 'V3_opening_activity_cohort_map__entry_minute_cohorts.csv'), ','); ck(f'{cy} V3 cohort rows', len(CO) == len(coh), f'{len(CO)} vs {len(coh)}')
    for r in CO:
        k = (r['session_ist'], r['order_entry_minute_ist']); v = coh.get(k)
        ck(f'{cy} V3 cohort row', v is not None and int(r['body_units_by_tag']) == v['body'] and int(r['wing_units_by_tag']) == v['wing'] and int(r['unclassified_units']) == v['unclassified'] and int(r['n_parent_orders']) == len(npar[k]), str(r))
    return t


def main():
    for und, exp in T.CYCLES: check_cycle(und, exp)
    print('PASSED checks by family:', dict(OK)); print('FAILED:', len(FAIL))
    for n, d in FAIL[:30]: print('  FAIL', n, d[:300])
    return 1 if FAIL else 0


if __name__ == '__main__': sys.exit(main())
