"""Read-only one-minute expired-option history. Default prints a plan, never trades.

Uses the same secure key/session exchange and TLS support as the index downloader.
No secrets are stored. Sparse option bars remain sparse and are not replay-ready.
"""
import argparse
import csv
import getpass
import io
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import fetch_breeze_indices as base

ROOT = base.ROOT
MAPPINGS = {'NIFTY': ('NFO', 'NIFTY'), 'SENSEX': ('BFO', 'BSESEN')}
BAR_FIELDS = {'datetime','stock_code','exchange_code','product_type','expiry_date','right',
              'strike_price','open','high','low','close','volume','open_interest','count'}
PROFILE = dict(normalizer_version=1,response_timezone='Asia/Kolkata',bar_label='start')


@dataclass(frozen=True, order=True)
class Target:
    underlying: str
    expiry_date: str
    strike: int
    option_type: str
    trade_date: str

    def validate(self):
        if self.underlying not in MAPPINGS or self.option_type not in ('CE','PE') or self.strike <= 0:
            raise base.FetchError('Unsupported option contract in request plan.')
        day,expiry = date.fromisoformat(self.trade_date), date.fromisoformat(self.expiry_date)
        if not date(2026,6,22) <= day <= expiry <= base.SESSION_POLICY_END:
            raise base.FetchError('Contract/day outside the verified study interval.')


def parameters(target):
    target.validate()
    exchange,stock = MAPPINGS[target.underlying]
    return dict(interval='1minute',from_date=f'{target.trade_date}T03:30:00.000Z',
                to_date=f'{target.trade_date}T15:45:00.000Z',stock_code=stock,exch_code=exchange,
                product_type='options',expiry_date=f'{target.expiry_date}T07:00:00.000Z',
                right='call' if target.option_type=='CE' else 'put',strike_price=str(target.strike))


def load_fills(root=ROOT):
    result = defaultdict(list)
    with (root/'Trades_GKOHNP140.csv').open(newline='',encoding='utf-8-sig') as f:
        for number,r in enumerate(csv.reader(f),1):
            if len(r)!=167:
                raise base.FetchError('Unexpected original trade-log schema.')
            t=datetime.fromtimestamp(int(r[161]),base.IST)
            if t.replace(tzinfo=None,second=0)!=datetime.strptime(r[138],'%m/%d/%Y %H:%M'):
                raise base.FetchError('Trade-log timestamp cross-check failed.')
            expiry=str(datetime.strptime(r[15],'%m/%d/%Y %H:%M').date())
            key=Target(r[12],expiry,int(r[14]),r[16],str(t.date()))
            result[key].append((t,float(r[137])))
    return result


def targets_for(scope, index, smoke, neighbors=0, root=ROOT):
    if smoke:
        result=[Target(u,e,k,ot,d) for u,e,k,d in
                [('NIFTY','2026-07-07',24350,'2026-07-06'),('SENSEX','2026-10-08',72600,'2026-10-07')]
                for ot in ('CE','PE')]
    elif scope=='sample':
        with (root/'research/outputs/next_option_sample_contract_days.csv').open(newline='') as f:
            result=[Target(r['underlying'],r['expiry_date'],int(r['strike']),r['option_type'],r['trade_date']) for r in csv.DictReader(f)]
    else:
        fills=load_fills(root)
        cycles=defaultdict(set)
        first={}
        for t in fills:
            key=(t.underlying,t.expiry_date)
            cycles[key].add((t.strike,t.option_type))
            first[key]=min(first.get(key,t.trade_date),t.trade_date)
        result=[]
        # Verified index days supply the actual trading-day calendar, including
        # Friday-to-Monday holding intervals. Include every traded contract for
        # every observed holding-cycle day, even without a fill on that day.
        for (u,expiry),contracts in cycles.items():
            days=sorted({p.name[:10] for p in (root/f'data/breeze/metadata/indices/{u}').glob('*.json')
                         if first[(u,expiry)] <= p.name[:10] <= expiry})
            for day in days:
                result.extend(Target(u,expiry,k,ot,day) for k,ot in contracts)
    result={t for t in result if index=='both' or t.underlying==index}
    if neighbors:
        result={Target(t.underlying,t.expiry_date,t.strike+offset*(50 if t.underlying=='NIFTY' else 100),t.option_type,t.trade_date)
                for t in result for offset in range(-neighbors,neighbors+1)
                if t.strike+offset*(50 if t.underlying=='NIFTY' else 100)>0}
    for t in result:
        t.validate()
    return sorted(result)


def parsed_expiry(value):
    text=str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        for fmt in ('%d-%b-%Y','%d-%b-%y'):
            try:
                return datetime.strptime(text,fmt).date()
            except ValueError:
                pass
    raise base.FetchError('Unrecognized returned option expiry format.')


def response_shape(response):
    if not isinstance(response,dict) or set(response)!={'Status','Success'} or response['Status']!=200 or not isinstance(response['Success'],list):
        raise base.FetchError('Unexpected history response schema; no artifact accepted.')
    if any(not isinstance(r,dict) or set(r)-BAR_FIELDS for r in response['Success']):
        raise base.FetchError('Unexpected historical-bar fields; no automatic sharing or persistence.')


def normalize(response,target,profile):
    response_shape(response)
    if not response['Success']:
        raise base.FetchError('Empty option history: expired-contract coverage, listing or entitlement needs review; not complete.')
    exchange,stock=MAPPINGS[target.underlying]
    day=date.fromisoformat(target.trade_date)
    close=time(15,40) if day>=base.CAS_START else time(15,30)
    normalized={}
    for r in response['Success']:
        if (str(r.get('stock_code','')).upper()!=stock or str(r.get('exchange_code','')).upper()!=exchange or
            str(r.get('product_type','')).lower()!='options' or parsed_expiry(r.get('expiry_date',''))!=date.fromisoformat(target.expiry_date) or
            str(r.get('right','')).lower()!=('call' if target.option_type=='CE' else 'put') or
            float(r.get('strike_price',float('nan')))!=target.strike):
            raise base.FetchError('Returned option identity differs from requested stock/exchange/expiry/strike/right.')
        try:
            t=datetime.fromisoformat(str(r['datetime']).replace('Z','+00:00'))
            if t.tzinfo is None:
                t=t.replace(tzinfo=ZoneInfo(profile['response_timezone']))
            t=t.astimezone(base.IST)
            if profile['bar_label']=='end':
                t-=timedelta(minutes=1)
            prices={k:float(r[k]) for k in ('open','high','low','close')}
            volume=float(r['volume'])
            oi=float(r['open_interest']) if r.get('open_interest') not in (None,'') else None
        except (ValueError,KeyError,TypeError):
            raise base.FetchError('Cannot parse option timestamp, OHLC, volume or open interest.') from None
        values=[*prices.values(),volume]+([oi] if oi is not None else [])
        if not all(math.isfinite(v) and v>=0 for v in values) or prices['high']<max(prices.values()) or prices['low']>min(prices.values()):
            raise base.FetchError('Invalid option prices, OHLC bounds, volume or open interest.')
        if t.second or t.microsecond:
            raise base.FetchError('Option candle is off the one-minute grid.')
        if t.date()!=day or not time(9,15)<=t.time()<close:
            continue
        stamp=t.isoformat()
        if stamp in normalized:
            raise base.FetchError('Duplicate option candle timestamp.')
        normalized[stamp]=dict(timestamp_ist=stamp,underlying=target.underlying,expiry_date=target.expiry_date,
            strike=target.strike,option_type=target.option_type,**prices,volume=volume,open_interest=oi if oi is not None else '')
    if not normalized:
        raise base.FetchError('No option observations inside the verified derivatives session; not complete.')
    return [normalized[k] for k in sorted(normalized)]


def csv_bytes(bars):
    f=io.StringIO(newline='')
    w=csv.DictWriter(f,fieldnames=list(bars[0]),lineterminator='\n')
    w.writeheader()
    w.writerows(bars)
    return f.getvalue().encode()


def coverage(bars,target):
    expected=385 if date.fromisoformat(target.trade_date)>=base.CAS_START else 375
    start=datetime.combine(date.fromisoformat(target.trade_date),time(9,15),base.IST)
    missing=sorted({(start+timedelta(minutes=i)).isoformat() for i in range(expected)}-{r['timestamp_ist'] for r in bars})
    zero=sum(min(r[k] for k in ('open','high','low','close'))==0 for r in bars)
    return dict(expected_derivative_minutes=expected,observed_bars=len(bars),missing_minutes_ist=missing,
                full_minute_grid=not missing,zero_price_bars=zero,zero_volume_bars=sum(r['volume']==0 for r in bars))


def fill_alignment(bars,target,fills):
    lookup={r['timestamp_ist']:r for r in bars}
    checks=dict(logged_fills=0,fills_with_bar=0,fills_inside_ohlc_plus_one_tick=0,fills_outside_ohlc_plus_one_tick=0,
                fills_without_bar=0,comparison='Recorded event minute; OHLC range plus 0.05 tolerance; diagnostic, not proof of exchange timestamp semantics.')
    for t,price in fills.get(target,[]):
        checks['logged_fills']+=1
        b=lookup.get(t.replace(second=0,microsecond=0).isoformat())
        if b is None:
            checks['fills_without_bar']+=1
        else:
            checks['fills_with_bar']+=1
            inside=b['low']-.05000001<=price<=b['high']+.05000001
            checks['fills_inside_ohlc_plus_one_tick' if inside else 'fills_outside_ohlc_plus_one_tick']+=1
    return checks


def paths(root,target,profile):
    request_id=base.digest(base.canonical(parameters(target)))[:12]
    profile_id=base.digest(base.canonical(profile))[:10]
    stem=Path('options')/target.underlying/target.expiry_date/f'{target.strike}{target.option_type}'
    return (root/'raw'/stem/f'{target.trade_date}.{request_id}.json',
            root/'normalized'/stem/f'{target.trade_date}.{profile_id}.csv',
            root/'metadata'/stem/f'{target.trade_date}.{profile_id}.json')


def derive(root,target,profile,payload,fills):
    if set(payload)!={'request','response','retrieved_at_utc'} or payload['request']!=parameters(target):
        raise base.FetchError('Cached raw request does not match exact option target.')
    datetime.fromisoformat(payload['retrieved_at_utc'])
    bars=normalize(payload['response'],target,profile)
    raw,normalized,_=paths(root,target,profile)
    content=csv_bytes(bars)
    c=coverage(bars,target)
    alignment=fill_alignment(bars,target,fills)
    metadata=dict(contract=asdict(target),request=payload['request'],interpretation=profile,
        status='validated_observed_option_bars',coverage=c,fill_alignment=alignment,
        minute_grid_price_coverage_complete=c['full_minute_grid'] and c['zero_price_bars']==0,
        note='Observed trade candles only; no interpolation, executable quotes, IV, Greeks or inferred settlement. Coverage does not imply replay readiness.',
        raw_path=raw.relative_to(root).as_posix(),normalized_path=normalized.relative_to(root).as_posix(),
        raw_sha256=base.digest(base.canonical(payload)),normalized_sha256=base.digest(content),
        retrieved_at_utc=payload['retrieved_at_utc'])
    return content,metadata


def fetch_day(client,root,target,profile,fills):
    raw,normalized,meta=paths(root,target,profile)
    if raw.exists():
        payload=json.loads(raw.read_text())
    else:
        response=client.fetch(parameters(target))
        response_shape(response)
        payload=dict(request=parameters(target),response=response,retrieved_at_utc=datetime.now(timezone.utc).isoformat())
        base.save_immutable(raw,base.canonical(payload))
    content,metadata=derive(root,target,profile,payload,fills)
    if base.digest(raw.read_bytes())!=metadata['raw_sha256']:
        raise base.FetchError('Raw option bytes differ from their canonical provenance; preserved without overwrite.')
    base.save_immutable(normalized,content)
    base.save_immutable(meta,base.canonical(metadata))
    return metadata


def validated_files(root):
    data=root/'data/breeze'
    fills=load_fills(root)
    selected=set()
    for meta in sorted((data/'metadata/options').rglob('*.json')):
        m=json.loads(meta.read_text())
        target=Target(**m['contract'])
        target.validate()
        profile=m['interpretation']
        if set(profile)!=set(PROFILE) or profile['normalizer_version']!=1 or profile['bar_label'] not in ('start','end'):
            raise base.FetchError('Unsupported option normalization profile.')
        raw,normalized,expected_meta=paths(data,target,profile)
        if meta!=expected_meta or any(p.is_symlink() or not p.resolve().is_relative_to(data.resolve()) for p in (raw,normalized,meta)):
            raise base.FetchError('Option artifact path differs from exact request/profile.')
        payload=json.loads(raw.read_text())
        content,expected=derive(data,target,profile,payload,fills)
        if m!=expected or base.digest(raw.read_bytes())!=m['raw_sha256'] or normalized.read_bytes()!=content:
            raise base.FetchError('Option provenance or reproducibility check failed; nothing staged.')
        selected.update(p.relative_to(root).as_posix() for p in (raw,normalized,meta))
    if not selected:
        raise base.FetchError('No validated observed option sessions exist; nothing to publish.')
    return sorted(selected)


class CacheOnly:
    def fetch(self,params):
        raise base.FetchError('Raw option response is not cached; no network request made.')


def smoke_ready(metadata):
    a=metadata['fill_alignment']
    return bool(metadata['minute_grid_price_coverage_complete'] and a['logged_fills'] and
                a['fills_inside_ohlc_plus_one_tick']/a['logged_fills']>=.8)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fetch',action='store_true')
    p.add_argument('--smoke',action='store_true',help='ATM CE and PE for NIFTY 6 July and SENSEX 7 October.')
    p.add_argument('--scope',choices=('sample','all'),default='sample')
    p.add_argument('--index',choices=('both','NIFTY','SENSEX'),default='both')
    p.add_argument('--neighbors',type=int,default=0,help='Add this many neighboring strike steps each side; requires listing/quote review.')
    p.add_argument('--revalidate-cached',action='store_true')
    p.add_argument('--continue-unavailable',action='store_true',help='Keep an explicit unavailable list and exit 2; never treat missing data as complete.')
    p.add_argument('--prompt-credentials',action='store_true')
    p.add_argument('--tls-backend',choices=('python','native'),default='python')
    p.add_argument('--response-timezone',default=PROFILE['response_timezone'])
    p.add_argument('--bar-label',choices=('start','end'),default='start')
    p.add_argument('--output',type=Path,default=ROOT/'data/breeze')
    args=p.parse_args()
    if args.fetch and args.revalidate_cached:
        p.error('Choose live fetch or cached revalidation.')
    if not 0<=args.neighbors<=10 or (args.smoke and args.neighbors):
        p.error('--neighbors must be 0–10 and is only for bulk plans.')
    profile=dict(PROFILE,response_timezone=args.response_timezone,bar_label=args.bar_label)
    ZoneInfo(args.response_timezone)
    targets=targets_for(args.scope,args.index,args.smoke,args.neighbors)
    if not targets:
        raise base.FetchError('Request plan is empty.')
    print(json.dumps(dict(mode='fetch' if args.fetch else 'revalidate_cached' if args.revalidate_cached else 'plan',
        contract_days=len(targets),per_index={u:sum(t.underlying==u for t in targets) for u in MAPPINGS},
        first_targets=[asdict(t) for t in targets[:4]],output=str(args.output),
        note='Options grid is 375 minutes before 3 August, 385 after; sparse bars stay sparse. No live orders.')),flush=True)
    if not args.fetch and not args.revalidate_cached:
        return 0
    fills=load_fills()
    if args.fetch and not args.smoke:
        # Check both near-ATM rights for each requested underlying before bulk.
        for t in targets_for('sample',args.index,True):
            if not any(q.underlying==t.underlying for q in targets):
                continue
            m=fetch_day(CacheOnly(),args.output,t,profile,fills)
            if not smoke_ready(m):
                raise base.FetchError('ATM smoke sample lacks full minute coverage or 80% fill-range agreement; investigate before bulk fetching.')
    if args.fetch:
        base.TLS_BACKEND=args.tls_backend
        base.tls_context()
        if args.prompt_credentials:
            for name in ('BREEZE_API_KEY','BREEZE_API_SESSION'):
                if not os.environ.get(name):
                    if not sys.stdin.isatty():
                        p.error('Hidden prompting requires an interactive local terminal.')
                    value=getpass.getpass(f'{name} (hidden): ').strip()
                    if not value:
                        p.error('Credential value was empty.')
                    os.environ[name]=value
        client=base.BreezeHistory()
        client.authenticate()  # Fail once on authentication, not once per contract.
    else:
        client=CacheOnly()
    completed,unavailable,smoke_reviews=[],[],[]
    for t in targets:
        try:
            m=fetch_day(client,args.output,t,profile,fills)
        except base.FetchError as exc:
            print(f'UNAVAILABLE {t.underlying} {t.trade_date} {t.expiry_date} {t.strike}{t.option_type}: {exc}',flush=True)
            unavailable.append(dict(contract=asdict(t),reason=str(exc)))
            # Do not continue a rejected/unauthorized/rate-limited transport.
            if not args.continue_unavailable or any(x in str(exc) for x in ('HTTP ','Request Rejected','session','connection failed')):
                break
            continue
        completed.append(t)
        c,a=m['coverage'],m['fill_alignment']
        print(f"OBSERVED {t.underlying} {t.trade_date} {t.expiry_date} {t.strike}{t.option_type}: {c['observed_bars']}/{c['expected_derivative_minutes']} bars; {len(c['missing_minutes_ist'])} missing; fill-range matches {a['fills_inside_ohlc_plus_one_tick']}/{a['logged_fills']}",flush=True)
        if args.smoke:
            passed=smoke_ready(m)
            print(f"SMOKE CHECK {'PASS' if passed else 'REVIEW REQUIRED'}: {t.underlying} {t.option_type}",flush=True)
            if not passed:
                smoke_reviews.append(asdict(t))
    summary=dict(status='unavailable_or_partial_plan' if unavailable else 'observations_downloaded',planned=len(targets),
                 observed=len(completed),unavailable=unavailable,not_attempted=len(targets)-len(completed)-len(unavailable),
                 note='Observed data are not automatically full coverage or suitable for marked replay.')
    if args.smoke:
        summary.update(smoke_checks_passed=not unavailable and not smoke_reviews,smoke_review_required=smoke_reviews)
    diagnostic=args.output/'diagnostics/options_download_review.json'
    diagnostic.parent.mkdir(parents=True,exist_ok=True)
    diagnostic.write_bytes(base.canonical(summary))
    print(json.dumps(summary))
    return 2 if unavailable or smoke_reviews else 0


if __name__=='__main__':
    try:
        sys.exit(main())
    except (base.FetchError,ValueError,KeyError,TypeError,OSError) as exc:
        print(str(exc) if isinstance(exc,base.FetchError) else f'Option validation stopped: {type(exc).__name__}; details suppressed.',file=sys.stderr)
        sys.exit(1)
