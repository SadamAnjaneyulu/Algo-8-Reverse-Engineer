"""Stages 3-4: expiry coverage tables (NIFTY, SENSEX), strike/CE/PE coverage and ATM-centre verification against an independent D-2 close.
Inputs: scan results from session_scan.py (reports/tables) + independent reference series. Outputs CSV tables."""
import csv, io, json, os, sys
from datetime import date, timedelta
import numpy as np, pandas as pd
from . import calendar_evidence as CE
from .gitsrc import GitSource
STEP = {'NIFTY': 50, 'SENSEX': 100}


def load_scans(tab):
    o = pd.DataFrame(json.load(open(f'{tab}/option_session_scan.json'))); u = pd.DataFrame(json.load(open(f'{tab}/underlying_scan.json'))); c = pd.read_parquet(f'{tab}/contract_sessions.parquet'); return o, u, c


def dataset_calendar(g, idx):
    return {r['week']: r for r in csv.DictReader(io.StringIO(g.text(f'metadata/expiry_calendar/expiry_calendar_{idx}.csv')))}


def d0_settlement_error(c, u, idx, exp, day):
    """Expiry-day behaviour check using the dataset itself (DATA evidence): deep in-the-money options should trade near intrinsic value of the spot close (relative gap) and far out-of-the-money options near zero.
    Returns (median ITM gap as % of spot, median last close of options >= 300 points out of the money)."""
    sp = u[(u['index'] == idx) & (u.kind == 'spot') & (u.day == day)]
    if not len(sp) or 'day_close' not in sp or pd.isna(sp.iloc[0].day_close): return None, None
    S = sp.iloc[0].day_close; x = c[(c['index'] == idx) & (c.expiry == exp) & (c.day == day)]
    ce = x[(x.right == 'CE') & (x.strike <= S - 300)]; pe = x[(x.right == 'PE') & (x.strike >= S + 300)]
    err = list(np.abs(ce.close_last - (S - ce.strike))) + list(np.abs(pe.close_last - (pe.strike - S)))
    otm = list(x[(x.right == 'CE') & (x.strike >= S + 300)].close_last) + list(x[(x.right == 'PE') & (x.strike <= S - 300)].close_last)
    return (float(np.median(err)) / S * 100 if len(err) >= 4 else None), (float(np.median(otm)) if len(otm) >= 4 else None)


def build(commit, tab, out):
    g = GitSource(commit); o, u, c = load_scans(tab); os.makedirs(out, exist_ok=True); summary = {}
    for und in ('NIFTY', 'SENSEX'):
        idx = und.lower(); exp = pd.DataFrame(CE.expected_expiries(und)); cal = dataset_calendar(g, idx); y = CE.yahoo_daily(und); td = CE.trading_days(und)
        oi = o[o['index'] == idx]; ui = u[u['index'] == idx]; cal_by_exp = {r['expiry']: r for r in cal.values() if r['expiry']}
        sess = {(r.expiry, r.day): r for r in oi.itertuples()}; spot = {(r.day) for r in ui[ui.kind == 'spot'].itertuples() if getattr(r, 'rows', 0)}; fut = {(r.day) for r in ui[ui.kind == 'futures'].itertuples() if getattr(r, 'rows', 0)}
        cc = c[c['index'] == idx].merge(oi[['expiry', 'day', 'plan_center']], on=['expiry', 'day']); cc = cc[((cc.strike - cc.plan_center).abs() / STEP[und]) <= 5]; near = cc.groupby(['expiry', 'day']).size().to_dict()   # contracts within +-5 steps of the window centre that have rows (22 planned)
        rows = []
        for e in exp.itertuples():
            E_, d1, d0 = e.expected_expiry, e.d1, e.d0; present_dataset_expiry = [k for k in {k[0] for k in sess} if k == E_]
            def has(day, exp_): r = sess.get((exp_, day)); return bool(r is not None and r.rows > 0)
            s0, s1 = has(d0, E_), has(d1, E_)
            both_types = lambda day: (lambda r: r is not None and getattr(r, 'ce_strikes', 0) > 0 and getattr(r, 'pe_strikes', 0) > 0)(sess.get((E_, day)))
            # actual expiry identified in the dataset for this week (any expiry whose D0 falls in the same week)
            wk = date.fromisoformat(e.week_monday); in_week = sorted(k[0] for k in sess if wk <= date.fromisoformat(k[0]) <= wk + timedelta(days=6)); ds_exp = in_week[0] if in_week else ''
            settle, otm = d0_settlement_error(c, u, idx, E_, d0) if s0 else (None, None)
            status = 'Complete' if (s0 and s1) else 'Partial' if (s0 or s1) else 'Missing'
            note = []; E_ = E_
            for dd, lab in ((d1, 'D-1'), (d0, 'D0')):
                if (E_, dd) in sess and near.get((E_, dd), 0) < 20 and status in ('Complete', 'Partial'):
                    note.append(f'{lab} session {dd} is incomplete: only {near.get((E_, dd), 0)} of 22 contracts within +-5 steps of the centre have data'); status = 'Partial' if status == 'Complete' else status
            if status == 'Complete' and not (both_types(d0) and both_types(d1)): note.append('CE or PE absent in a session')
            if status == 'Complete' and not ((d0 in spot) and (d1 in spot)): note.append('spot missing for a session')
            ds_days = sorted(k[1] for k in sess if k[0] == (ds_exp or E_)); ds_d1 = ds_days[0] if ds_days else ''
            if ds_exp and ds_exp != E_: note.append(f'dataset expiry {ds_exp} differs from independently expected {E_}')
            if ds_d1 and ds_d1 != d1 and (ds_exp or E_) == E_:
                special = date.fromisoformat(ds_d1) in CE.SPECIAL_SESSIONS; note.append(f'dataset D-1 {ds_d1} differs from expected previous regular session {d1}' + (' (dataset D-1 is a special Muhurat session)' if special else ''))
                if status == 'Complete': status = 'Partial'; s1 = False
            if e.evidence_status.startswith('UNCONFIRMED'):
                note.append('transition week: exact exchange rule not independently confirmed')
                if status == 'Missing': status = 'Unverified'
            if status != 'Missing' and (otm is None or otm > 2): note.append(f'expiry-day behaviour not confirmed: far-OTM median close {otm} (expired options should sit at the 0.05 minimum tick)')
            rows.append(dict(week_monday=e.week_monday, expected_expiry=E_, holiday_shifted=e.holiday_shifted, evidence_status=e.evidence_status, d1_expected=d1, d0_expected=d0, dataset_calendar_expiry=ds_exp,
                             d1_option_rows=int(sess[(E_, d1)].rows) if (E_, d1) in sess else 0, d0_option_rows=int(sess[(E_, d0)].rows) if (E_, d0) in sess else 0, d1_spot=d1 in spot, d0_spot=d0 in spot, d1_futures=d1 in fut, d0_futures=d0 in fut,
                             d0_itm_gap_pct_of_spot=settle, d0_far_otm_median_close=otm, status=status, notes='; '.join(note)))
        T = pd.DataFrame(rows); T.to_csv(f'{out}/{idx}_expiry_coverage.csv', index=False)
        # dataset sessions with no independently expected expiry
        exp_set = set(exp.expected_expiry); extra = sorted({k[0] for k in sess} - exp_set)
        summary[und] = dict(expected=len(T), complete=int((T.status == 'Complete').sum()), partial=int((T.status == 'Partial').sum()), missing=int((T.status == 'Missing').sum()), unverified=int((T.status == 'Unverified').sum()),
                            complete_with_notes=int(((T.status == 'Complete') & (T.notes != '')).sum()), d1_present=int((T.d1_option_rows > 0).sum()), d0_present=int((T.d0_option_rows > 0).sum()),
                            dataset_expiries_not_in_independent_calendar=extra, expected_expiry_differs_from_dataset=T[(T.dataset_calendar_expiry != '') & (T.dataset_calendar_expiry != T.expected_expiry)][['week_monday', 'expected_expiry', 'dataset_calendar_expiry']].to_dict('records'),
                            missing_expiries=T[T.status == 'Missing'].expected_expiry.tolist())
        # ATM centre check: contract strike window per session vs ATM of independent D-2 close
        sr = []
        for r in oi.itertuples():
            if r.rows == 0 or not r.plan_strikes: continue
            row = exp[exp.expected_expiry == r.expiry]
            if not len(row): continue
            d2 = date.fromisoformat(row.iloc[0].d2); d1 = date.fromisoformat(row.iloc[0].d1); step = STEP[und]
            ref = lambda d, k='close': y.get(d, {}).get(k)
            atm = lambda p: None if p is None else int(round(p / step)) * step
            sr.append(dict(index=idx, expiry=r.expiry, session=r.day, which='D0' if r.day == r.expiry else 'D-1', plan_center=r.plan_center, plan_strikes=r.plan_strikes, plan_min=r.plan_strike_min, plan_max=r.plan_strike_max, plan_step=r.plan_step_values, d2_date=str(d2), d2_close_independent=ref(d2), atm_d2_close=atm(ref(d2)),
                           atm_d1_close=atm(ref(d1)), atm_d2_open=atm(ref(d2, 'open')), center_minus_atm_d2_steps=(None if ref(d2) is None else (r.plan_center - atm(ref(d2))) / step), cal_atm_ref=(cal.get(next((k for k, v in cal.items() if v['expiry'] == r.expiry), ''), {}) or {}).get('atm_ref')))
        pd.DataFrame(sr).to_csv(f'{out}/{idx}_atm_center_check.csv', index=False)
    json.dump(summary, open(f'{out}/coverage_summary.json', 'w'), indent=1, default=str); return summary


if __name__ == '__main__': print(json.dumps(build(sys.argv[1], sys.argv[2], sys.argv[3]), indent=1, default=str)[:6000])
