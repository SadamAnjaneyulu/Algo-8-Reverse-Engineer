"""Plan / fetch Breeze 1-minute option history for an arbitrary period (e.g. Mar 2025 - Jun 2026) by REUSING the research-branch
fetchers (research/fetch_breeze_options.py + fetch_breeze_indices.py): same auth, TLS, caching, normalisation and metadata.
Only two things change: (1) the contract-date window check is widened to --start/--end, (2) targets come from a strike-band plan
instead of the June-October 2026 trade log.

Order of work (run from the research checkout root, branch data/local-breeze-fetch or research/ml-decision-engine):
  0. index minutes first, with the existing index fetcher:   py research/fetch_breeze_indices.py --fetch --prompt-credentials --start 2025-03-01 --end 2026-06-19 --continue-incomplete
     (its holiday snapshot only covers 2026, so pre-2026 exchange holidays show up as 'empty history' and are skipped/recorded.)
  1. plan only (no credentials):      py <this-repo>/analysis/history_fetch.py --research-dir research --start 2025-03-01 --end 2026-06-19
  2. discover expiries + fetch tier 1: py ... --fetch --prompt-credentials --tier 1
  3. optional wider wings:             py ... --fetch --prompt-credentials --tier 2
Expiry dates are DISCOVERED by probing the ATM CE for candidate weekdays (priority order below is only a probe order, not an assumption);
a week whose expiry cannot be confirmed is reported, never guessed.
"""
import argparse, json, os, sys, getpass, csv, math
from datetime import date, timedelta
from pathlib import Path
from dataclasses import asdict

def load_fetchers(research_dir):
    sys.path.insert(0, str(Path(research_dir).resolve()))
    import fetch_breeze_indices as base
    import fetch_breeze_options as opt
    return base, opt

STEP = {'NIFTY': 50, 'SENSEX': 100}
# probe order of expiry weekdays by period (Mon=0). Verified per week by an actual ATM-CE request; holidays shift to earlier days.
PROBE = {'NIFTY': [(date(2000, 1, 1), date(2025, 8, 31), [3, 2, 1, 4]), (date(2025, 9, 1), date(2099, 1, 1), [1, 0, 2, 3])],
         'SENSEX': [(date(2000, 1, 1), date(2025, 8, 31), [1, 0, 2, 4]), (date(2025, 9, 1), date(2099, 1, 1), [3, 2, 1, 4])]}
TIERS = {1: dict(core=5, wing_to=0, stride=1), 2: dict(core=5, wing_to=30, stride=2), 3: dict(core=5, wing_to=42, stride=4)}

def index_days(data_dir, und):
    """trading days and day low/high from the validated normalized index CSVs."""
    out = {}
    for f in sorted((Path(data_dir) / 'normalized' / 'indices' / und).glob('*.csv')):
        rows = list(csv.DictReader(f.open()))
        if not rows: continue
        d = date.fromisoformat(rows[0]['timestamp_ist'][:10])
        out[d] = dict(lo=min(float(r['low']) for r in rows), hi=max(float(r['high']) for r in rows),
                      open=float(rows[0]['open']), close=float(rows[-1]['close']))
    return out

def candidate_expiries(und, week_monday, days):
    for lo, hi, order in PROBE[und]:
        if lo <= week_monday <= hi:
            return [week_monday + timedelta(days=k) for k in order if (week_monday + timedelta(days=k)) in days]
    return []

def band(und, lo, hi, tier):
    s = STEP[und]; t = TIERS[tier]; a = math.floor(lo / s); b = math.ceil(hi / s)
    ks = set(range((a - t['core']) * s, (b + t['core']) * s + s, s))
    if t['wing_to']:
        for j in range(t['core'] + 1, t['wing_to'] + 1, t['stride']):
            ks.add((a - j) * s); ks.add((b + j) * s)
    return sorted(k for k in ks if k > 0)

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--research-dir', default='research'); p.add_argument('--data', type=Path, default=Path('data/breeze'))
    p.add_argument('--start', type=date.fromisoformat, required=True); p.add_argument('--end', type=date.fromisoformat, required=True)
    p.add_argument('--index', choices=('both', 'NIFTY', 'SENSEX'), default='both'); p.add_argument('--tier', type=int, choices=(1, 2, 3), default=1)
    p.add_argument('--fetch', action='store_true'); p.add_argument('--prompt-credentials', action='store_true')
    p.add_argument('--tls-backend', choices=('python', 'native'), default='native'); p.add_argument('--continue-unavailable', action='store_true')
    p.add_argument('--expiries-json', type=Path, default=Path('data/breeze/diagnostics/history_expiries.json'))
    a = p.parse_args()
    base, opt = load_fetchers(a.research_dir)
    lo_ok, hi_ok = a.start, min(a.end, base.SESSION_POLICY_END)
    def validate(self):                                   # widened window; identity checks unchanged
        if self.underlying not in opt.MAPPINGS or self.option_type not in ('CE', 'PE') or self.strike <= 0:
            raise base.FetchError('Unsupported option contract in request plan.')
        d, e = date.fromisoformat(self.trade_date), date.fromisoformat(self.expiry_date)
        if not lo_ok <= d <= e <= hi_ok + timedelta(days=7):
            raise base.FetchError('Contract/day outside the requested history window.')
    opt.Target.validate = validate
    unds = ['NIFTY', 'SENSEX'] if a.index == 'both' else [a.index]
    profile = dict(opt.PROFILE)
    client = None
    if a.fetch:
        base.TLS_BACKEND = a.tls_backend; base.tls_context()
        if a.prompt_credentials:
            for name in ('BREEZE_API_KEY', 'BREEZE_API_SESSION'):
                if not os.environ.get(name): os.environ[name] = getpass.getpass(f'{name} (hidden): ').strip()
        client = base.BreezeHistory(); client.authenticate()
    fills = {}
    known = json.loads(a.expiries_json.read_text()) if a.expiries_json.exists() else {}
    plan, unresolved = [], []
    for und in unds:
        days = index_days(a.data, und); tdays = sorted(d for d in days if a.start <= d <= a.end)
        if not tdays: print(f'{und}: no validated index days in window - fetch index minutes first'); continue
        weeks = sorted({d - timedelta(days=d.weekday()) for d in tdays})
        for wk in weeks:
            key = f'{und}|{wk}'
            exp = date.fromisoformat(known[key]) if key in known else None
            cands = candidate_expiries(und, wk, set(tdays))
            if exp is None and client is not None:
                for c in cands:
                    atm = round(days[c]['open'] / STEP[und]) * STEP[und]
                    t = opt.Target(und, str(c), int(atm), 'CE', str(c))
                    try: opt.fetch_day(client, a.data, t, profile, fills); exp = c; break
                    except base.FetchError: continue
                if exp: known[key] = str(exp)
            if exp is None:
                unresolved.append(dict(und=und, week=str(wk), probe_order=[str(c) for c in cands])); exp_guess = cands[0] if cands else None
                if exp_guess is None: continue
                exp = exp_guess
            i = tdays.index(exp) if exp in tdays else None
            if i is None or i == 0: continue
            d1, d0 = tdays[i - 1], exp
            s1 = band(und, days[d1]['lo'], days[d1]['hi'], a.tier); s0 = sorted(set(s1) | set(band(und, days[d0]['lo'], days[d0]['hi'], a.tier)))
            for dd, ks in ((d1, s1), (d0, s0)):
                for k in ks:
                    for cp in ('CE', 'PE'): plan.append(opt.Target(und, str(exp), int(k), cp, str(dd)))
    a.expiries_json.parent.mkdir(parents=True, exist_ok=True); a.expiries_json.write_text(json.dumps(known, indent=1, sort_keys=True))
    plan = sorted(set(plan))
    print(json.dumps(dict(mode='fetch' if a.fetch else 'plan', tier=a.tier, contract_days=len(plan), per_index={u: sum(t.underlying == u for t in plan) for u in unds},
                          est_hours_at_1_25s=round(len(plan) * 1.25 / 3600, 1), expiry_weeks_confirmed=len(known),
                          expiry_weeks_unconfirmed=len(unresolved), note='unconfirmed weeks use the first probe weekday ONLY for counting; they are not fetched')))
    if not a.fetch: return 0
    done = bad = 0
    for t in plan:
        if any(u['und'] == t.underlying and u['week'] == str(date.fromisoformat(t.expiry_date) - timedelta(days=date.fromisoformat(t.expiry_date).weekday())) for u in unresolved):
            continue
        try: opt.fetch_day(client, a.data, t, profile, fills); done += 1
        except base.FetchError as exc:
            bad += 1; print(f'UNAVAILABLE {asdict(t)}: {exc}', flush=True)
            if not a.continue_unavailable or any(x in str(exc) for x in ('HTTP ', 'Request Rejected', 'session', 'connection failed')): break
    print(json.dumps(dict(fetched=done, unavailable=bad, planned=len(plan))))
    return 2 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
