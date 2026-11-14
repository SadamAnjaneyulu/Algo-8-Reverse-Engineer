"""[RAW]+[IMPL] TP-03 window label timezone: count raw body-short opening fills (tag num, sell, opening qty>0) in [T-2s, T+180s) with T = label read as IST vs as UTC,
compare with the published n_body_short_fills_in_window (p1_window_dataset.parquet) and with m2e_data tp03_windows.tsv window_start_ts_utc_s.  Usage: verify_tp03_windows.py [PE_ROOT]"""
import sys, os, csv, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raw_truth as T
import pandas as pd
PE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(T.REPO, 'portfolio_engine')
w = pd.read_parquet(os.path.join(T.REPO, 'tp_reconstruction', 'tp03', 'data', 'p1_window_dataset.parquet'))
bad = 0; tot = 0; res = {}
for und, exp in T.CYCLES:
    t = T.truth(und, exp); opens = [a['fill']['ts'] for a in t['R']['oa'] if a['fill']['tag'] == 'num' and a['fill']['side'] < 0]
    ws = w[w.cycle == f'{und}|{exp}']; rows = list(csv.DictReader(open(os.path.join(PE, 'reports', 'm2e_data', f'{und}_{exp}', 'tp03_windows.tsv')), delimiter='\t'))
    ck = {(r['date'], r['window']): r for r in rows}; ist_match = utc_match = 0; n = 0; tsok = 0; both_zero = 0
    for r in ws.itertuples():
        hh, mm = map(int, r.window.split(':')); base = int(pd.Timestamp(r.date).value // 10**9)
        for lab, off in (('IST', base + hh * 3600 + mm * 60 - T.IST), ('UTC', base + hh * 3600 + mm * 60)):
            c = sum(1 for x in opens if off - 2 <= x < off + 180)
            if lab == 'IST': ist_c = c; ist_t = off
            else: utc_c = c
        n += 1; ist_match += ist_c == r.n_body_short_fills_in_window; utc_match += utc_c == r.n_body_short_fills_in_window; both_zero += (ist_c == utc_c == r.n_body_short_fills_in_window)
        m2e = ck.get((str(pd.Timestamp(r.date).date()), r.window)); tsok += (m2e is not None and int(m2e['window_start_ts_utc_s']) == ist_t and m2e['window_start_ist'] == T.ist_str(ist_t))
    res[f'{und}|{exp}'] = dict(windows=n, m2e_rows=len(rows), published_fill_count_matches_raw_IST_interpretation=ist_match, matches_raw_UTC_interpretation=utc_match, both_equal_incl_zero=both_zero, m2e_window_start_utc_and_ist_correct=tsok)
    # off-window class parent list: check parents listed are body-short parents of this cycle
    o = pd.read_csv(os.path.join(T.REPO, 'tp_reconstruction', 'tp03', 'analysis', 'p1_off_window_events.csv')); o = o[o.cycle == f'{und}|{exp}']
    bodyparents = {a['fill']['parent'] for a in t['R']['oa'] if a['fill']['tag'] == 'num' and a['fill']['side'] < 0}; lst = {str(p) for p in o.parent_oid}
    res[f'{und}|{exp}'].update(off_window_parents=len(lst), all_listed_are_raw_body_short_opening_parents=lst <= bodyparents, event_classes=dict(collections.Counter(o.event_class)))
    items = list(csv.DictReader(open(os.path.join(PE, 'reports', 'm2e_data', f'{und}_{exp}', 'opening_items.tsv')), delimiter='\t'))
    cls = collections.Counter(r['tp03_event_class'] for r in items); res[f'{und}|{exp}']['opening_items_tp03_class_counts'] = dict(cls)
    res[f'{und}|{exp}']['items_labelled_listed_but_not_body_short'] = sum(1 for r in items if r['tp03_event_class'] != 'NOT_LISTED_BY_TP03_AS_OFF_WINDOW' and r['tag_role'] != 'BODY_SHORT_BY_TAG')
for k, v in res.items(): print(k, v)
