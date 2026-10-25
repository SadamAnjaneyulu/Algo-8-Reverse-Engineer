"""Join inferred fills to validated index bars; no option marks or P&L invented.

Run: python research/analyze_index_triggers.py
Requires only the standard library. --plot optionally uses matplotlib.
"""
import argparse
import bisect
import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

import fetch_breeze_indices as fetch
from push_validated_breeze_data import validated_files

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/outputs"
IST = ZoneInfo("Asia/Kolkata")
STEP = {"NIFTY": 50, "SENSEX": 100}
UNIT = {"NIFTY": 65, "SENSEX": 20}  # Observed quantity GCD, not verified lot size.


def write_csv(name, rows):
    if rows:
        with (OUT / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
            w.writeheader()
            w.writerows(rows)


def pct(a, b):
    return 100 * (a / b - 1)


def describe(values):
    values = sorted(values)
    return dict(n=len(values), minimum=min(values), median=median(values), maximum=max(values)) if values else dict(n=0)


def round_strike(spot, underlying):
    step = STEP[underlying]
    return int(math.floor(spot / step + .5)) * step


def read_fills():
    rows = []
    quantities, notionals = {}, {}
    with (ROOT / "Trades_GKOHNP140.csv").open(newline="", encoding="utf-8-sig") as f:
        for number, r in enumerate(csv.reader(f), 1):
            assert len(r) == 167
            t = datetime.fromtimestamp(int(r[161]), IST)
            assert t.replace(tzinfo=None, second=0) == datetime.strptime(r[138], "%m/%d/%Y %H:%M")
            identity = (r[23][:10], r[3], r[4])
            cumulative = int(r[19]) - int(r[20])
            q = cumulative - quantities.get(identity, 0)
            assert q == int(r[33]) and q > 0
            price = Decimal(r[137])
            notional = Decimal(r[18]) * cumulative
            assert abs((notional - notionals.get(identity, Decimal(0))) / q - price) < Decimal('.00001')
            quantities[identity], notionals[identity] = cumulative, notional
            expiry = datetime.strptime(r[15], "%m/%d/%Y %H:%M").date()
            rows.append(dict(source=number, t=t, minute=t.replace(second=0), u=r[12], expiry=expiry,
                             strike=int(r[14]), ot=r[16], side=r[11], q=q, price=price,
                             signed=q if r[11] == 'Buy' else -q))
    rows.sort(key=lambda r: (r['t'], r['source']))
    for reverse in (False, True):
        inventory = Counter()
        for r in sorted(rows, key=lambda r: (r['t'], -r['source'] if reverse else r['source'])):
            key = (r['u'], r['expiry'], r['strike'], r['ot'])
            previous = inventory[key]
            closing = min(r['q'], max(-previous if r['side'] == 'Buy' else previous, 0))
            r['reverse_opening' if reverse else 'opening'] = r['q'] - closing
            inventory[key] += r['signed']
    return rows


def load_index():
    files = validated_files(ROOT)
    sessions, stored = {}, 0
    for name in files:
        if '/metadata/' not in name:
            continue
        m = json.loads((ROOT / name).read_text())
        path = ROOT / 'data/breeze' / m['normalized_path'].replace('\\', '/')
        bars = []
        for r in csv.DictReader(path.open(newline='')):
            t = datetime.fromisoformat(r['timestamp_ist'])
            if fetch.session_phase(t, fetch.session_version(t.date())) != 'continuous_cash':
                stored += 1
                continue
            bars.append(dict(t=t, **{k: float(r[k]) for k in ('open', 'high', 'low', 'close')}))
            stored += 1
        sessions[(m['underlying'], m['date'])] = bars
    return sessions, stored


def reference(sessions, u, t):
    """Only the immediately preceding completed continuous minute is usable."""
    bars = sessions.get((u, str(t.date())), [])
    cutoff = t.replace(second=0, microsecond=0)
    i = bisect.bisect_left([r['t'] for r in bars], cutoff) - 1
    if i < 0 or bars[i]['t'] + timedelta(minutes=1) != cutoff:
        return None, {}
    b = bars[i]
    prior = bars[:i+1]
    close = b['close']
    old = next((r['close'] for r in prior if r['t'] == b['t']-timedelta(minutes=15)), None)
    result = dict(reference_bar_start_ist=b['t'].isoformat(), reference_close=close,
                  completed_open_to_now_pct=pct(close, prior[0]['open']),
                  completed_range_pct=100*(max(r['high'] for r in prior)-min(r['low'] for r in prior))/prior[0]['open'],
                  completed_15min_return_pct=pct(close, old) if old else '',
                  minute_boundary_open=next((r['open'] for r in bars if r['t'] == cutoff), ''))
    return b, result


def pairing(rows, sessions):
    groups = defaultdict(list)
    for r in rows:
        if r['side'] == 'Sell' and r['opening'] > 0 and r['opening'] == r['reverse_opening']:
            groups[(r['u'], r['expiry'], r['minute'], r['strike'])].append(r)
    pairs = []
    for (u, expiry, minute, strike), records in sorted(groups.items()):
        if {r['ot'] for r in records} != {'CE', 'PE'}:
            continue
        first = min(r['t'] for r in records)
        both = max(min(r['t'] for r in records if r['ot'] == ot) for ot in ('CE', 'PE'))
        b, features = reference(sessions, u, first)
        p = dict(underlying=u, expiry_date=str(expiry), event_minute_ist=minute.isoformat(),
                 first_leg_time_ist=first.isoformat(), both_legs_started_ist=both.isoformat(),
                 calendar_dte=(expiry-first.date()).days, strike=strike,
                 ce_opening_quantity=sum(r['opening'] for r in records if r['ot']=='CE'),
                 pe_opening_quantity=sum(r['opening'] for r in records if r['ot']=='PE'),
                 source_rows=';'.join(str(r['source']) for r in records),
                 **{k: features.get(k, '') for k in ('reference_bar_start_ist','reference_close', 'completed_open_to_now_pct', 'completed_range_pct', 'completed_15min_return_pct', 'minute_boundary_open')})
        p['nearest_prior_close_strike'] = round_strike(b['close'], u) if b else ''
        p['sold_minus_nearest_prior_close_strike'] = strike-p['nearest_prior_close_strike'] if b else ''
        p['nearest_boundary_open_strike'] = round_strike(features['minute_boundary_open'], u) if features.get('minute_boundary_open') else ''
        p['clock_offset_mod15'] = (minute.hour*60+minute.minute-(9*60+16)) % 15
        p['weighted_sold_ce_premium'] = float(sum(r['price']*r['opening'] for r in records if r['ot']=='CE')/p['ce_opening_quantity'])
        p['weighted_sold_pe_premium'] = float(sum(r['price']*r['opening'] for r in records if r['ot']=='PE')/p['pe_opening_quantity'])
        pairs.append(p)
    return pairs


def build_schedule(pre, sessions):
    dates = sorted({(p['underlying'],p['expiry_date'],p['event_minute_ist'][:10]) for p in pre})
    opportunities = []
    for u, expiry, day in dates:
        bars = sessions[(u,day)]
        start = datetime.combine(datetime.fromisoformat(day).date(), time(9,16), IST)
        while start < bars[-1]['t']:
            events = [p for p in pre if p['underlying']==u and p['expiry_date']==expiry and
                      start <= datetime.fromisoformat(p['event_minute_ist']) < start+timedelta(minutes=3)]
            _, features = reference(sessions,u,start)
            opportunities.append(dict(underlying=u, expiry_date=expiry, slot_start_ist=start.isoformat(),
                                      observed_paired_opening_event=bool(events), pair_minute_strike_groups=len(events),
                                      **features))
            start += timedelta(minutes=15)
    return opportunities


def final_flat(states, field):
    if not states or states[-1][field]:
        return ''
    last = max((i for i,r in enumerate(states) if r[field]), default=-1)
    return states[last+1]['t'].isoformat()


def cycle_paths(rows, pre, sessions):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r['u'],str(r['expiry']))].append(r)
    records = []
    for (u,expiry), fills in sorted(grouped.items()):
        inventory, carry, states = Counter(), Counter(), []
        seconds = defaultdict(list)
        for r in fills:
            seconds[r['t']].append(r)
        for t,batch in sorted(seconds.items()):
            for r in batch:
                inventory[(r['strike'],r['ot'])] += r['signed']
                if str(t.date()) < expiry:
                    carry[(r['strike'],r['ot'])] += r['signed']
            states.append(dict(t=t, short=sum(max(-v,0) for v in inventory.values()), gross=sum(abs(v) for v in inventory.values())))
        starts = [p for p in pre if p['underlying']==u and p['expiry_date']==expiry]
        first = min(starts,key=lambda p:p['first_leg_time_ist']) if starts else None
        e = sessions[(u,expiry)]
        short_flat = final_flat(states,'short') if any(v<0 for v in carry.values()) else ''
        flat = not any(inventory.values())
        rec = dict(underlying=u, expiry_date=expiry, replication_block='October' if expiry>='2026-10-01' else 'June_September',
                   preexpiry_date=first['event_minute_ist'][:10] if first else '',
                   entry_strike=first['strike'] if first else '',
                   entry_reference_close=first['reference_close'] if first else '',
                   initial_sold_straddle_premium=first['weighted_sold_ce_premium']+first['weighted_sold_pe_premium'] if first else '',
                   net_flow_flat=flat, residual_contracts=sum(v!=0 for v in inventory.values()),
                   observed_execution_cashflow_before_costs=float(sum((-r['signed']*r['price'] for r in fills),Decimal(0))),
                   comparable_flat_preexpiry_cycle=bool(first) and flat,
                   short_carry_quantity=sum(max(-v,0) for v in carry.values()),
                   final_short_book_flat_ist=short_flat, final_full_book_flat_ist=final_flat(states,'gross'),
                   expiry_continuous_open=e[0]['open'], expiry_last_continuous_close=e[-1]['close'],
                   expiry_continuous_open_close_pct=pct(e[-1]['close'],e[0]['open']),
                   expiry_continuous_range_pct=100*(max(b['high'] for b in e)-min(b['low'] for b in e))/e[0]['open'])
        for k in ('preexpiry_open_to_continuous_close_pct','preexpiry_continuous_range_pct','expiry_open_vs_previous_continuous_close_pct','entry_to_expiry_continuous_close_pct','maximum_completed_close_move_in_initial_straddle_premiums','prior_close_move_at_short_exit_in_initial_premiums','entry_opening_gap_vs_previous_continuous_close_pct'):
            rec[k] = ''
        if first and first['reference_close']:
            p = sessions[(u,rec['preexpiry_date'])]
            rec['preexpiry_open_to_continuous_close_pct'] = pct(p[-1]['close'],p[0]['open'])
            rec['preexpiry_continuous_range_pct'] = 100*(max(b['high'] for b in p)-min(b['low'] for b in p))/p[0]['open']
            # Post-CAS this includes the auction-to-open move; it is not a pure overnight gap.
            rec['expiry_open_vs_previous_continuous_close_pct'] = pct(e[0]['open'],p[-1]['close'])
            rec['entry_to_expiry_continuous_close_pct'] = pct(e[-1]['close'],first['reference_close'])
            path = [b for b in p+e if b['t'] >= datetime.fromisoformat(first['reference_bar_start_ist'])]
            rec['maximum_completed_close_move_in_initial_straddle_premiums'] = max(abs(b['close']-first['reference_close']) for b in path)/rec['initial_sold_straddle_premium']
            if short_flat:
                b,_ = reference(sessions,u,datetime.fromisoformat(short_flat))
                if b:
                    rec['prior_close_move_at_short_exit_in_initial_premiums'] = abs(b['close']-first['reference_close'])/rec['initial_sold_straddle_premium']
            prior_dates=sorted(day for underlying,day in sessions if underlying==u and day<rec['preexpiry_date'])
            if prior_dates:
                previous = sessions[(u,prior_dates[-1])]
                rec['entry_opening_gap_vs_previous_continuous_close_pct'] = pct(p[0]['open'],previous[-1]['close'])
        records.append(rec)
    return records


def hedge_events(rows, sessions):
    groups=defaultdict(list)
    for r in rows:
        if r['side']=='Buy' and r['t'].date()<r['expiry'] and r['opening']>0 and r['opening']==r['reverse_opening']:
            groups[(r['u'],r['expiry'],r['minute'],r['strike'],r['ot'])].append(r)
    result=[]
    for (u,expiry,minute,strike,ot),batch in sorted(groups.items()):
        q=sum(r['opening'] for r in batch)
        _,features=reference(sessions,u,min(r['t'] for r in batch))
        result.append(dict(underlying=u,expiry_date=str(expiry),event_minute_ist=minute.isoformat(),strike=strike,option_type=ot,
                           opening_quantity=q,quantity_gcd_units=q/UNIT[u],
                           weighted_fill_price=float(sum(r['opening']*r['price'] for r in batch)/q),
                           descriptive_phase='initial' if minute.time()<time(9,18) else 'routine' if minute.time()<time(14,45) else 'late',
                           large_late=minute.time()>=time(14,45) and q/UNIT[u]>=10,
                           source_rows=';'.join(str(r['source']) for r in batch),
                           **{k:features.get(k,'') for k in ('reference_bar_start_ist','reference_close','completed_open_to_now_pct','completed_range_pct','completed_15min_return_pct')}))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plot',action='store_true')
    args=parser.parse_args()
    sessions,stored=load_index()
    rows=read_fills()
    pairs=pairing(rows,sessions)
    pre=[p for p in pairs if p['calendar_dte']>0]
    starts={}
    for p in pre:
        key=(p['underlying'],p['expiry_date'],p['event_minute_ist'][:10])
        if key not in starts or p['both_legs_started_ist']<starts[key]['both_legs_started_ist']:
            starts[key]=p
    initial=list(starts.values())
    slots=build_schedule(pre,sessions)
    cycles=cycle_paths(rows,pre,sessions)
    hedges=hedge_events(rows,sessions)
    summary=dict(input_sha256=hashlib.sha256((ROOT/'Trades_GKOHNP140.csv').read_bytes()).hexdigest(),
                 validated_index_days=len(sessions),stored_index_bars=stored,fill_records=len(rows),cycles=len(cycles),
                 preexpiry_pair_events=len(pre),observed_preexpiry_dates=len(initial),
                 initial_0916_dates=sum(p['event_minute_ist'][11:16]=='09:16' for p in initial),
                 initial_nearest_prior_close_matches=sum(p['sold_minus_nearest_prior_close_strike']==0 for p in initial),
                 initial_nearest_prior_close_available=sum(p['reference_close']!='' for p in initial),
                 initial_exceptions=[p for p in initial if p['sold_minus_nearest_prior_close_strike']!=0],
                 cohorts=[])
    for u in STEP:
        for block in ('all','June_September','October'):
            choose=lambda p:p['underlying']==u and (block=='all' or (p['expiry_date']>='2026-10-01')==(block=='October'))
            ps=[p for p in pre if choose(p)]
            fs=[p for p in initial if choose(p)]
            ss=[p for p in slots if choose(p)]
            valid=[p for p in ps if p['reference_close']!='']
            hc=[h for h in hedges if choose(h) and h['large_late'] and h['reference_close']!='']
            complete=[c for c in cycles if choose(c) and c['comparable_flat_preexpiry_cycle']]
            summary['cohorts'].append(dict(underlying=u,block=block,first_pairs=len(fs),initial_at_nearest=sum(p['sold_minus_nearest_prior_close_strike']==0 for p in fs),
                opening_gap_pct=describe([c['entry_opening_gap_vs_previous_continuous_close_pct'] for c in cycles if choose(c) and c['entry_opening_gap_vs_previous_continuous_close_pct']!='']),
                pair_groups=len(ps),prior_index_available=len(valid),all_pairs_at_nearest_prior_close=sum(p['sold_minus_nearest_prior_close_strike']==0 for p in valid),
                all_pairs_within_one_strike_step=sum(abs(p['sold_minus_nearest_prior_close_strike'])<=STEP[u] for p in valid),
                clock_mod15_counts=dict(Counter(p['clock_offset_mod15'] for p in ps)),
                events_within_3min_clock_window=sum(p['clock_offset_mod15']<3 for p in ps),
                scheduled_opportunities=len(ss),scheduled_opportunities_with_event=sum(p['observed_paired_opening_event'] for p in ss),
                dates_with_any_clock_event=sum(any(p['clock_offset_mod15']<3 for p in ps if p['event_minute_ist'][:10]==day) for day in {p['event_minute_ist'][:10] for p in ps}),
                large_late_groups_with_prior_index=len(hc),large_late_call_after_up_or_put_after_down=sum((h['option_type']=='CE' and h['completed_open_to_now_pct']>0) or (h['option_type']=='PE' and h['completed_open_to_now_pct']<0) for h in hc),
                flat_preexpiry_cycles=len(complete),negative_flow_cycles=sum(c['observed_execution_cashflow_before_costs']<0 for c in complete),
                negative_flow_amounts=describe([c['observed_execution_cashflow_before_costs'] for c in complete if c['observed_execution_cashflow_before_costs']<0])))
    summary['limitations']=['Clock opportunities are descriptive windows, not verified scheduled decisions. Missing events do not establish skipped strategy signals.',
        'Cashflow is conditional on zero initial inventory, complete export and no residual positions; costs and external settlement are unavailable.',
        'Initial straddle premium is a gross sold price; it excludes hedge costs and is a scale for path description, not the current-book breakeven or stop.',
        'Cycle path features use full sessions and can extend after exits; they are outcome descriptions, never entry predictors.',
        'Post-CAS prior continuous close to expiry open includes the closing auction; it is not an isolated overnight return.',
        'No neighboring option prices, IV, theta, marked P&L, fills-to-quote latency or definitive causal trigger are inferred.',
        'October has already been inspected; chronological replication is not a blinded holdout.']
    summary['quarter_hour_sensitivity'] = dict(
        definition='Additional descriptive window after inspecting phase counts: quarter-hour minute and two following minutes; not a newly validated strategy rule.',
        pair_groups_in_window=sum(p['clock_offset_mod15'] in (14,0,1) for p in pre),
        total_pair_groups=len(pre))
    summary['large_late_groups'] = sum(h['large_late'] for h in hedges)
    summary['large_late_groups_without_immediately_prior_continuous_bar'] = sum(h['large_late'] and h['reference_close']=='' for h in hedges)
    summary['initial_completed_minute_returns_pct'] = describe([p['completed_open_to_now_pct'] for p in initial if p['reference_close']!=''])
    summary['initial_completed_minute_return_signs'] = dict(positive=sum(p['completed_open_to_now_pct']>0 for p in initial if p['reference_close']!=''),
                                                          negative=sum(p['completed_open_to_now_pct']<0 for p in initial if p['reference_close']!=''))
    summary['scheduled_event_direction_splits'] = []
    for feature in ('completed_open_to_now_pct','completed_15min_return_pct'):
        for direction in ('nonpositive','positive'):
            chosen=[s for s in slots if s[feature]!='' and (s[feature]>0)==(direction=='positive')]
            summary['scheduled_event_direction_splits'].append(dict(feature=feature,direction=direction,opportunities=len(chosen),
                opportunities_with_pair=sum(s['observed_paired_opening_event'] for s in chosen)))
    summary['routine_new_long_fill_prices'] = []
    for u in STEP:
        chosen=[r for r in rows if r['u']==u and r['side']=='Buy' and r['t'].date()<r['expiry'] and
                r['opening']>0 and r['opening']==r['reverse_opening'] and time(9,18)<=r['t'].time()<time(14,45)]
        lo,hi=(1.5,2.5) if u=='NIFTY' else (5,9)
        summary['routine_new_long_fill_prices'].append(dict(underlying=u,fill_records=len(chosen),
            median_executed_price=float(median(r['price'] for r in chosen)),concentration_interval=[lo,hi],
            fills_in_interval=sum(Decimal(str(lo))<=r['price']<=Decimal(str(hi)) for r in chosen)))
    seeds=[]
    for p in initial:
        if p['event_minute_ist'][11:16]!='09:16':
            continue
        for ot in ('CE','PE'):
            chosen=[r for r in rows if r['u']==p['underlying'] and str(r['expiry'])==p['expiry_date'] and
                    str(r['t'].date())==p['event_minute_ist'][:10] and r['ot']==ot and r['side']=='Buy' and
                    r['opening']>0 and r['opening']==r['reverse_opening'] and time(9,15)<=r['t'].time()<time(9,17)]
            if chosen:
                r=min(chosen,key=lambda r:(r['t'],r['source']))
                seeds.append(dict(underlying=r['u'],expiry_date=str(r['expiry']),event_time_ist=r['t'].isoformat(),
                    option_type=ot,first_bought_strike=r['strike'],sold_reference_strike=p['strike'],
                    outward_gap=(r['strike']-p['strike'])*(1 if ot=='CE' else -1),
                    executed_price=float(r['price']),source_row=r['source']))
    summary['initial_wing_gaps']=[]
    for u,period,nominal,tolerance in [('NIFTY','all',2000,100),('SENSEX','before_2026_09_16',4000,200),('SENSEX','from_2026_09_16',2000,200)]:
        selected=[r for r in seeds if r['underlying']==u and (period=='all' or (r['event_time_ist'][:10]>='2026-09-16')==(period=='from_2026_09_16'))]
        summary['initial_wing_gaps'].append(dict(underlying=u,period=period,observations=len(selected),nominal_gap=nominal,
            exact=sum(r['outward_gap']==nominal for r in selected),tolerance=tolerance,
            within_tolerance=sum(abs(r['outward_gap']-nominal)<=tolerance for r in selected)))
    option_manifest=[]
    sample_cycles={('NIFTY','2026-07-07'),('NIFTY','2026-07-14'),('SENSEX','2026-10-08'),('SENSEX','2026-10-15')}
    for u,expiry in sorted(sample_cycles):
        selected=[r for r in rows if r['u']==u and str(r['expiry'])==expiry]
        first_day=min(str(r['t'].date()) for r in selected)
        days=sorted(day for underlying,day in sessions if underlying==u and first_day<=day<=expiry)
        for strike,ot in sorted({(r['strike'],r['ot']) for r in selected}):
            for day in days:
                option_manifest.append(dict(underlying=u,expiry_date=expiry,strike=strike,option_type=ot,trade_date=day,
                    requested_interval='1minute',scope='full regular option session; verify date-effective exchange hours',
                    purpose='Exact traded-contract sample for price/stop replay; unselected neighboring strikes needed separately'))
    summary['next_option_sample'] = dict(cycles=4,contract_days=len(option_manifest),
        note='Request plan only. No options have been fetched; expired-series/BSE derivatives support needs a small verified sample. Does not include unselected neighbors.')
    OUT.mkdir(exist_ok=True)
    for name,data in [('trigger_pair_events.csv',pairs),('trigger_initial_entries.csv',initial),('trigger_clock_opportunities.csv',slots),('trigger_cycle_paths.csv',cycles),('trigger_hedge_events.csv',hedges),('trigger_initial_wings.csv',seeds),('next_option_sample_contract_days.csv',option_manifest)]:
        write_csv(name,data)
    (OUT/'index_trigger_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    if args.plot:
        plot(initial,pre,cycles)


def plot(initial,pre,cycles):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/algo8-matplotlib')
    os.environ.setdefault('XDG_CACHE_HOME','/tmp/algo8-font-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for u,color in [('NIFTY','#177e89'),('SENSEX','#b55a30')]:
        fs=[p for p in initial if p['underlying']==u and p['reference_close']!='']
        axs[0,0].scatter([datetime.fromisoformat(p['event_minute_ist']).date() for p in fs],
                         [p['sold_minus_nearest_prior_close_strike']/STEP[u] for p in fs],label=u,color=color,s=25,alpha=.7)
        ps=[p for p in pre if p['underlying']==u]
        counts=Counter(p['clock_offset_mod15'] for p in ps)
        axs[0,1].plot(range(15),[counts[i]/len(ps)*100 for i in range(15)],marker='o',label=u,color=color)
        for c in cycles:
            if c['underlying']!=u or not c['comparable_flat_preexpiry_cycle']:
                continue
            axs[1,0].scatter(c['maximum_completed_close_move_in_initial_straddle_premiums'],c['observed_execution_cashflow_before_costs']/1000,color=color,marker='x' if c['replication_block']=='October' else 'o',s=35)
        ex=[c for c in cycles if c['underlying']==u and c['final_short_book_flat_ist']]
        for c in ex:
            t=datetime.fromisoformat(c['final_short_book_flat_ist'])
            axs[1,1].scatter(t.date(),t.hour+t.minute/60+t.second/3600,color=color,s=25)
    axs[0,0].set(title='Initial sold strike: 31/32 match nearest prior index close',xlabel='Entry date',ylabel='Sold minus nearest strike, in strike steps')
    axs[0,0].tick_params(axis='x',rotation=25)
    axs[0,0].legend()
    axs[0,1].set(title='Further paired opening-short events: clock concentration',xlabel='Minute offset from 09:16 modulo 15',ylabel='% of minute/strike events',xticks=range(15))
    axs[0,1].legend()
    axs[1,0].axhline(0,color='gray',linewidth=.8)
    axs[1,0].set(title='Exploratory: complete observed net-flow cycles only',xlabel='Max close movement / initial gross straddle premium',ylabel='Observed net cashflow, ₹ thousand, before costs')
    axs[1,1].axvline(datetime(2026,8,3),color='gray',linestyle=':',label='CAS effective')
    axs[1,1].axhline(15+14/60,color='gray',linewidth=.8)
    axs[1,1].set(title='Final short-book closure; residual longs may remain',xlabel='Date',ylabel='IST')
    axs[1,1].yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{int(x):02}:{int(round((x-int(x))*60)):02}'))
    axs[1,1].tick_params(axis='x',rotation=25)
    fig.suptitle('Algo 8: index-data evidence, not an identified option-price trigger',fontsize=13)
    fig.savefig(OUT/'index_trigger_evidence.png',dpi=150)
    fig.savefig(OUT/'index_trigger_evidence.svg')
    svg=OUT/'index_trigger_evidence.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':
    main()
