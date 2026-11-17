"""python3 -m acquisition.cli <command> --store DIR ...   (run from the market_data directory)"""
import argparse, getpass, json, os, sys
from datetime import date
from . import config as C, planner as P, runner as RUN, legacy as L, qc as Q
from .client import BreezeClient
from .store import Store

LOOKBACK_DATES = [date(2023, 10, 23), date(2023, 11, 17), date(2024, 1, 2), date(2024, 6, 3), date(2025, 1, 2), date(2025, 6, 2)]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); s = p.add_subparsers(dest='cmd', required=True)
    s.add_parser('estimate', help='credential-free request projection')
    for name in ('import-legacy', 'plan', 'fetch', 'status', 'qc', 'plan-lookback', 'plan-summary'): 
        q = s.add_parser(name); q.add_argument('--store', required=True); q.add_argument('--und', default='NIFTY')
        if name == 'import-legacy': q.add_argument('--branch-root', required=True)
        if name == 'plan': q.add_argument('--stage', required=True, choices=('index', 'expiries', 'options', 'range', 'futures')); q.add_argument('--max-tier', type=int, default=2)
        if name == 'fetch':
            q.add_argument('--kinds', nargs='*'); q.add_argument('--max-tier', type=int); q.add_argument('--max-requests', type=int); q.add_argument('--daily-cap', type=int, default=C.DEFAULT_DAILY_CAP)
            q.add_argument('--prompt-credentials', action='store_true'); q.add_argument('--native-tls', action='store_true')
        if name == 'qc': q.add_argument('--out', default=None)
    a = p.parse_args(argv)
    if a.cmd == 'estimate': print(json.dumps(P.estimate(), indent=1)); return 0
    st = Store(a.store)
    if a.cmd == 'import-legacy': print('imported contract-days / index-days:', L.import_legacy(st, a.branch_root, a.und))
    elif a.cmd == 'plan-lookback':
        from datetime import timedelta
        n = 0
        for d in LOOKBACK_DATES:
            while d.weekday() > 4: d += timedelta(days=1)
            st.add_task(P._task('index', a.und, [d], 0, 0, meta=dict(purpose='lookback_probe'))); n += 1
        st.commit(); print('lookback probe tasks:', n)
    elif a.cmd == 'plan':
        f = dict(index=lambda: P.plan_index(st, a.und), expiries=lambda: P.plan_expiry_probes(st, a.und), options=lambda: P.plan_options(st, a.und, a.max_tier), range=lambda: P.plan_range_cover(st, a.und), futures=lambda: P.plan_futures(st, a.und))[a.stage]
        print(f'{a.stage}: tasks added', f()); print(json.dumps(st.counts()))
    elif a.cmd == 'fetch':
        if a.native_tls:
            import truststore; truststore.inject_into_ssl()
        if a.prompt_credentials:
            os.environ.setdefault('BREEZE_API_KEY', getpass.getpass('Breeze API key (hidden): ')); os.environ.setdefault('BREEZE_API_SESSION', getpass.getpass('Active API session (hidden): '))
        try: print(json.dumps(RUN.run(st, BreezeClient(), a.kinds, a.max_tier, a.max_requests, a.daily_cap)))
        except RUN.StopRun as e: print('STOPPED:', e); return 2
        print(json.dumps(st.counts()))
    elif a.cmd == 'plan-summary':
        rows = st.db.execute("SELECT kind, tier, status, COUNT(*) FROM tasks GROUP BY kind, tier, status ORDER BY kind, tier, status").fetchall(); pend = sum(r[3] for r in rows if r[2] in ('PENDING', 'FAILED_RETRYABLE'))
        out = dict(by_kind_tier_status=[tuple(r) for r in rows], pending_requests=pend, days_at_daily_cap=round(pend / C.DEFAULT_DAILY_CAP, 2), hours_of_request_time=round(pend * C.MIN_REQUEST_INTERVAL_S / 3600, 2),
                   held_contract_days={f'{r[0]}:{r[1]}:{r[2]}': r[3] for r in st.db.execute('SELECT kind, source, status, COUNT(*) FROM contract_days GROUP BY kind, source, status')}); print(json.dumps(out, indent=1))
    elif a.cmd == 'status': print(json.dumps(dict(tasks=st.counts(), requests_today=st.requests_today(RUN.ist_today())), indent=1))
    elif a.cmd == 'qc': print(json.dumps(Q.report(st, a.und, a.out or os.path.join(a.store, 'qc')), indent=1, default=str)[:4000])
    return 0


if __name__ == '__main__': sys.exit(main())
