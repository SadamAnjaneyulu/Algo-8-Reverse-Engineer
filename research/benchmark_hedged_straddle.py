"""Paired common-time strategy vs frozen-opening-basket benchmark.

See BENCHMARK_TEST_PLAN.md. Conditional observed-book marks, explicit cost stress,
calibration-only size matching; no margin/tail equality or blinded-holdout claim.
"""
import argparse
import csv
import json
import math
import os
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, stdev

import analyze_index_triggers as logs

ROOT=logs.ROOT
OUT=logs.OUT
CAPITAL=20_000_000
CALIBRATION_END='2026-08-31'
LOT={'NIFTY':65,'SENSEX':20}  # Observed GCD; not independently verified lot rules.
SCENARIOS={'gross':(0,0,0),'low':(10,20,0),'primary':(25,20,.05),'high':(50,20,.10)}


def write(name,rows):
    if rows:
        with (OUT/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
            w.writeheader()
            w.writerows(rows)


class Quotes:
    def __init__(self,root=ROOT):
        self.root=root
        self.metadata={}
        self.cache={}
        for p in (root/'data/breeze/metadata/options').rglob('*.json'):
            m=json.loads(p.read_text())
            c=m['contract']
            self.metadata[(c['underlying'],c['expiry_date'],c['strike'],c['option_type'],c['trade_date'])]=m

    def bar(self,u,expiry,contract,day,clock):
        key=(u,expiry,*contract,day)
        if key not in self.metadata:
            return None
        if key not in self.cache:
            path=self.root/'data/breeze'/self.metadata[key]['normalized_path']
            if logs.fetch.digest(path.read_bytes())!=self.metadata[key]['normalized_sha256']:
                raise ValueError('Benchmark quote file failed its recorded integrity hash.')
            self.cache[key]={r['timestamp_ist'][11:16]:{k:float(r[k]) for k in ('open','high','low','close','volume')}
                             for r in csv.DictReader(path.open(newline=''))}
        return self.cache[key].get(clock)


def actual_at(fills,cutoff,quotes,u,expiry,order_ids):
    inventory=Counter()
    cash=turnover=units=0.
    orders=set()
    for r in fills:
        if r['t']>=cutoff:
            continue
        inventory[(r['strike'],r['ot'])]+=r['signed']
        cash-=r['signed']*float(r['price'])
        turnover+=r['q']*float(r['price'])
        units+=r['q']
        orders.add(order_ids[r['source']])
    gross=cash
    missing=[]
    zero_volume=0
    closing_orders=0
    for contract,q in inventory.items():
        if not q:
            continue
        bar=quotes.bar(u,expiry,contract,str(cutoff.date()),cutoff.strftime('%H:%M'))
        if bar is None:
            missing.append(f'{contract[0]}{contract[1]}')
            continue
        gross+=q*bar['open']
        turnover+=abs(q)*bar['open']
        units+=abs(q)
        closing_orders+=1
        zero_volume+=bar['volume']==0
    return dict(gross=gross if not missing else None,turnover=turnover,units=units,
                orders=len(orders)+closing_orders,synthetic_close_orders=closing_orders,
                active_zero_volume=zero_volume,missing=';'.join(missing),
                terminal_nonzero_contracts=sum(q!=0 for q in inventory.values()))


def basket_at(u,expiry,day,legs,quotes,entry_clock,exit_clock,averaging=False):
    times=[datetime.fromisoformat(day+'T'+entry_clock)]
    if averaging:
        start=datetime.fromisoformat(day+'T09:16')
        times=[start+timedelta(minutes=15*i) for i in range(22)]
        if entry_clock=='09:17':
            times=[t+timedelta(minutes=1) for t in times]
    credit=0.
    turnover=0.
    missing=[]
    zero_volume=0
    for t in times:
        for contract,sign in legs:
            bar=quotes.bar(u,expiry,contract,day,t.strftime('%H:%M'))
            if bar is None:
                missing.append(f'entry:{t:%H:%M}:{contract[0]}{contract[1]}')
                continue
            credit-=sign*bar['open']/len(times)
            turnover+=bar['open']/len(times)
            zero_volume+=bar['volume']==0
    gross=credit
    for contract,sign in legs:
        bar=quotes.bar(u,expiry,contract,expiry,exit_clock)
        if bar is None:
            missing.append(f'exit:{exit_clock}:{contract[0]}{contract[1]}')
            continue
        gross+=sign*bar['open']
        turnover+=bar['open']
        zero_volume+=bar['volume']==0
    # Equal quantity in CE/PE shorts and outward wings: expiry payoff is capped.
    short=next(k for (k,ot),sign in legs if sign<0)
    width=max(abs(k-short) for (k,ot),sign in legs if sign>0)
    return dict(gross_unit=gross if not missing else None,turnover_unit=turnover,
                transacted_units_per_unit=8,orders=4*len(times)+4,
                entry_credit_unit=credit,max_expiry_loss_unit=max(width-credit,0),wing_width=width,
                zero_volume=zero_volume,missing=';'.join(missing),fractional_slot_quantities=averaging)


def cost(turnover,units,orders,scenario):
    bps,broker,extra=SCENARIOS[scenario]
    return turnover*bps/10000+orders*broker+units*extra


def calibrated_quantity(actual,unit,lot):
    if len(actual)<3 or len(actual)!=len(unit) or stdev(unit)==0:
        raise ValueError('Insufficient calibration observations.')
    ideal=stdev(actual)/stdev(unit)
    return max(lot,int(math.floor(ideal/lot+.5))*lot),ideal


def stopped_basket(u,expiry,day,legs,quotes,quantity,threshold=200000):
    """Expiry-only completed-bar monitoring. No threshold-price fills or gap fill."""
    entry=turnover_unit=0.
    for contract,sign in legs:
        bar=quotes.bar(u,expiry,contract,day,'09:16')
        if bar is None:
            return dict(valid=False,reason='Missing stop-baseline entry quote.')
        entry-=sign*bar['open']
        turnover_unit+=bar['open']
    first=datetime.fromisoformat(expiry+'T09:15')
    end=datetime.fromisoformat(expiry+'T15:14')
    equity=entry*quantity
    for contract,sign in legs:
        bar=quotes.bar(u,expiry,contract,expiry,'09:15')
        if bar is None:
            return dict(valid=False,reason='Missing expiry-opening stop monitor.')
        equity+=quantity*sign*bar['open']
    triggered=equity<=-threshold
    execution=first if triggered else end
    t=first
    while not triggered and t<end:
        value=entry*quantity
        for contract,sign in legs:
            bar=quotes.bar(u,expiry,contract,expiry,t.strftime('%H:%M'))
            if bar is None:
                return dict(valid=False,reason=f'Missing stop-monitoring quote at {t:%H:%M}.')
            value+=quantity*sign*bar['close']
        if value<=-threshold:
            triggered=True
            execution=t+timedelta(minutes=1)
            break
        t+=timedelta(minutes=1)
    gross_unit=entry
    for contract,sign in legs:
        bar=quotes.bar(u,expiry,contract,expiry,execution.strftime('%H:%M'))
        if bar is None:
            return dict(valid=False,reason=f'Missing stop-execution quote at {execution:%H:%M}.')
        gross_unit+=sign*bar['open']
        turnover_unit+=bar['open']
    return dict(valid=True,reason='',triggered=triggered,execution_clock=execution.strftime('%H:%M'),
                gross=gross_unit*quantity,turnover=turnover_unit*quantity,units=8*quantity,orders=8,
                threshold=threshold,quantity=quantity)


def percentile(values,p):
    x=sorted(values)
    pos=(len(x)-1)*p
    lower=int(pos)
    return x[lower]+(x[min(lower+1,len(x)-1)]-x[lower])*(pos-lower)


def week_bootstrap(rows,draws=10000):
    groups=defaultdict(list)
    for r in rows:
        d=datetime.fromisoformat(r['expiry_date']).date().isocalendar()
        groups[(d.year,d.week)].append(r['paired_difference'])
    keys=sorted(groups)
    if len(keys)<2:
        return dict(weeks=len(keys),lower=None,upper=None)
    rng=random.Random(20261026)
    values=[]
    for _ in range(draws):
        sample=[v for key in rng.choices(keys,k=len(keys)) for v in groups[key]]
        values.append(mean(sample))
    return dict(weeks=len(keys),draws=draws,lower=percentile(values,.025),upper=percentile(values,.975),
                note='Paired mean difference per cycle; expiry-week cluster bootstrap, not independent minute/order samples.')


def summarize(rows):
    if not rows:
        return dict(cycles=0)
    a=[r['actual_net'] for r in rows]
    b=[r['baseline_net'] for r in rows]
    dif=[r['paired_difference'] for r in rows]
    return dict(cycles=len(rows),actual_total=sum(a),baseline_total=sum(b),difference_total=sum(dif),
                difference_mean=mean(dif),actual_better_cycles=sum(v>0 for v in dif),
                actual_worst_cycle=min(a),baseline_worst_cycle=min(b),
                actual_sd=stdev(a) if len(a)>1 else None,baseline_sd=stdev(b) if len(b)>1 else None,
                bootstrap=week_bootstrap(rows))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plot',action='store_true')
    args=p.parse_args()
    entries=list(csv.DictReader((OUT/'trigger_initial_entries.csv').open()))
    seeds=list(csv.DictReader((OUT/'trigger_initial_wings.csv').open()))
    quotes=Quotes()
    fills=defaultdict(list)
    for r in logs.read_fills():
        fills[(r['u'],str(r['expiry']))].append(r)
    order_ids={}
    with (ROOT/'Trades_GKOHNP140.csv').open(newline='',encoding='utf-8-sig') as f:
        for source,r in enumerate(csv.reader(f),1):
            order_ids[source]=(datetime.strptime(r[23],'%m/%d/%Y %H:%M').date(),r[3],r[4])
    raw=[]
    exclusions=[]
    cycle_definitions={}
    normal={(r['underlying'],r['expiry_date']) for r in entries if r['event_minute_ist'][11:16]=='09:16'}
    for u,expiry in sorted(fills):
        if (u,expiry) not in normal:
            exclusions.append(dict(underlying=u,expiry_date=expiry,variant='all',baseline='all',
                                   reason='Delayed opening or no observed pre-expiry 09:16 four-leg basket.'))
    for e in entries:
        if e['event_minute_ist'][11:16]!='09:16':
            continue
        u,expiry,day=e['underlying'],e['expiry_date'],e['event_minute_ist'][:10]
        ss=[s for s in seeds if s['underlying']==u and s['expiry_date']==expiry]
        legs=[((int(e['strike']),'CE'),-1),((int(e['strike']),'PE'),-1)]+[((int(s['first_bought_strike']),s['option_type']),1) for s in ss]
        if len(legs)!=4:
            raise ValueError('Incomplete initial four-leg selector.')
        cycle_definitions[(u,expiry)]=(day,legs)
        before=datetime.fromisoformat(day+'T09:17:00').replace(tzinfo=logs.IST)
        initial=Counter()
        for r in fills[(u,expiry)]:
            if r['t']<before:
                initial[(r['strike'],r['ot'])]+=r['signed']
        common=min(max(sign*initial[contract],0) for contract,sign in legs)
        for variant,entry_clock,exit_clock in [('primary','09:16','15:14'),('entry_one_minute_later','09:17','15:14'),
                                               ('historical_exit_clock','09:16','15:25' if expiry<'2026-08-03' else '15:14')]:
            cutoff=datetime.fromisoformat(expiry+'T'+exit_clock).replace(tzinfo=logs.IST)
            actual=actual_at(fills[(u,expiry)],cutoff,quotes,u,expiry,order_ids)
            for name,averaging in [('frozen',False),('averaging',True)]:
                baseline=basket_at(u,expiry,day,legs,quotes,entry_clock,exit_clock,averaging)
                if actual['gross'] is None or baseline['gross_unit'] is None:
                    exclusions.append(dict(underlying=u,expiry_date=expiry,variant=variant,baseline=name,
                        reason='Missing exact quote: actual='+actual['missing']+'; baseline='+baseline['missing']))
                    continue
                raw.append(dict(underlying=u,expiry_date=expiry,preexpiry_date=day,variant=variant,baseline=name,
                    phase='calibration' if expiry<=CALIBRATION_END else 'evaluation',observed_initial_common_quantity=common,
                    actual_gross=actual['gross'],actual_turnover=actual['turnover'],actual_units=actual['units'],actual_orders=actual['orders'],
                    synthetic_actual_close_orders=actual['synthetic_close_orders'],actual_active_zero_volume=actual['active_zero_volume'],
                    baseline_unit_gross=baseline['gross_unit'],baseline_turnover_unit=baseline['turnover_unit'],baseline_orders=baseline['orders'],
                    baseline_entry_credit_unit=baseline['entry_credit_unit'],baseline_max_loss_unit=baseline['max_expiry_loss_unit'],
                    baseline_wing_width=baseline['wing_width'],baseline_zero_volume_slots=baseline['zero_volume'],
                    idealized_fractional_slot_quantities=averaging))
    sizes=[]
    size_map={}
    for name in ('frozen','averaging'):
        for u in LOT:
            train=[r for r in raw if r['baseline']==name and r['underlying']==u and r['variant']=='primary' and r['phase']=='calibration']
            q,ideal=calibrated_quantity([r['actual_gross'] for r in train],[r['baseline_unit_gross'] for r in train],LOT[u])
            size_map[(name,u)]=q
            sizes.append(dict(baseline=name,underlying=u,training_cycles=len(train),ideal_quantity=ideal,frozen_quantity=q,
                actual_calibration_sd=stdev(r['actual_gross'] for r in train),
                baseline_calibration_sd=stdev(r['baseline_unit_gross']*q for r in train)))
    detailed=[]
    unscaled=[]
    for r in raw:
        target=size_map[(r['baseline'],r['underlying'])]
        capital_cap=int(CAPITAL/r['baseline_wing_width']/LOT[r['underlying']])*LOT[r['underlying']]
        q=min(target,capital_cap)
        for scenario in SCENARIOS:
            ac=cost(r['actual_turnover'],r['actual_units'],r['actual_orders'],scenario)
            bc=cost(r['baseline_turnover_unit']*q,8*q,r['baseline_orders'],scenario)
            a=r['actual_gross']-ac
            b=r['baseline_unit_gross']*q-bc
            detailed.append(dict(**r,cost_scenario=scenario,calibrated_quantity=target,used_quantity=q,capital_cap_binding=q<target,
                baseline_max_expiry_loss_gross=r['baseline_max_loss_unit']*q,actual_cost_stress=ac,baseline_cost_stress=bc,
                actual_net=a,baseline_net=b,paired_difference=a-b))
        if r['baseline']=='frozen' and r['variant']=='primary':
            q0=r['observed_initial_common_quantity']
            unscaled.append(dict(underlying=r['underlying'],expiry_date=r['expiry_date'],phase=r['phase'],
                opening_quantity=q0,actual_gross=r['actual_gross'],opening_quantity_baseline_gross=r['baseline_unit_gross']*q0,
                note='Initial-size diagnostic; actual later position growth is not size matched.'))
    results=[]
    for name in ('frozen','averaging'):
        for variant in ('primary','entry_one_minute_later','historical_exit_clock'):
            for scenario in SCENARIOS:
                for phase in ('calibration','evaluation'):
                    chosen=[r for r in detailed if r['baseline']==name and r['variant']==variant and r['cost_scenario']==scenario and r['phase']==phase]
                    results.append(dict(baseline=name,variant=variant,cost_scenario=scenario,phase=phase,**summarize(chosen)))
    main_rows=[r for r in detailed if r['baseline']=='frozen' and r['variant']=='primary' and r['cost_scenario']=='primary']
    by_index=[]
    for u in LOT:
        for phase in ('calibration','evaluation'):
            by_index.append(dict(underlying=u,phase=phase,**summarize([r for r in main_rows if r['underlying']==u and r['phase']==phase])))
    validation=[r for r in main_rows if r['phase']=='evaluation']
    weeks=defaultdict(list)
    for r in validation:
        d=datetime.fromisoformat(r['expiry_date']).date().isocalendar()
        weeks[(d.year,d.week)].append(r)
    leave_week_out=[]
    total=sum(r['paired_difference'] for r in validation)
    for (year,week),rs in sorted(weeks.items()):
        contribution=sum(r['paired_difference'] for r in rs)
        leave_week_out.append(dict(expiry_iso_year=year,expiry_iso_week=week,cycles=len(rs),
                                   week_contribution=contribution,evaluation_difference_without_week=total-contribution))
    stop_rows=[]
    stop_exclusions=[]
    # Same actual marks as the primary cohort; no primary missing-quote cycle is
    # opportunistically added just because a stopped baseline exits earlier.
    for r in [x for x in detailed if x['baseline']=='frozen' and x['variant']=='primary' and x['cost_scenario']=='gross']:
        u,expiry=r['underlying'],r['expiry_date']
        day,legs=cycle_definitions[(u,expiry)]
        s=stopped_basket(u,expiry,day,legs,quotes,r['used_quantity'])
        if not s['valid']:
            stop_exclusions.append(dict(underlying=u,expiry_date=expiry,reason=s['reason']))
            continue
        for scenario in SCENARIOS:
            ac=cost(r['actual_turnover'],r['actual_units'],r['actual_orders'],scenario)
            bc=cost(s['turnover'],s['units'],s['orders'],scenario)
            stop_rows.append(dict(underlying=u,expiry_date=expiry,phase=r['phase'],cost_scenario=scenario,
                actual_net=r['actual_gross']-ac,baseline_net=s['gross']-bc,
                paired_difference=r['actual_gross']-ac-s['gross']+bc,
                stop_triggered=s['triggered'],baseline_exit_clock=s['execution_clock'],baseline_quantity=s['quantity']))
    stop_results=[]
    same_cohort_unstopped=[]
    for phase in ('calibration','evaluation'):
        for scenario in SCENARIOS:
            picked=[r for r in stop_rows if r['phase']==phase and r['cost_scenario']==scenario]
            stop_results.append(dict(phase=phase,cost_scenario=scenario,**summarize(picked)))
            keys={(r['underlying'],r['expiry_date']) for r in picked}
            unstopped=[r for r in detailed if r['baseline']=='frozen' and r['variant']=='primary' and r['phase']==phase and
                       r['cost_scenario']==scenario and (r['underlying'],r['expiry_date']) in keys]
            assert len(unstopped)==len(picked)
            same_cohort_unstopped.append(dict(phase=phase,cost_scenario=scenario,**summarize(unstopped)))
    summary=dict(specification='research/BENCHMARK_TEST_PLAN.md',calibration_end=CALIBRATION_END,
        nominal_capital=CAPITAL,ordinary_opening_cycles=len(normal),sizing=sizes,results=results,
        primary_by_index=by_index,primary_full_sample_descriptive=summarize(main_rows),
        primary_evaluation_leave_one_week_out=leave_week_out,
        supplemental_stopped_baseline=dict(results=stop_results,same_cohort_unstopped_results=same_cohort_unstopped,excluded=stop_exclusions,
            note='Exploratory ₹200k cycle-loss stop on expiry day, added after inspecting primary outcomes. Same sizing; no refit or threshold-price execution.'),
        excluded=exclusions,primary_definition='Frozen same observed opening contracts; 09:16 entry, expiry 15:14 exit, 25bps premium turnover + ₹20/order + ₹0.05/unit stress.',
        limits=['Opening strikes are shared with the actual strategy; this tests later trading, not an independent opening-alpha signal.',
                'Variability-calibrated size is not equal historical margin, equal delta/gamma or equal tail risk. Actual margin and funding are unavailable.',
                'September–October has been inspected in previous work; evaluation is chronological, not blinded.',
                'All values depend on zero initial inventory, complete recorded fills, trade-candle opens and hypothetical costs; no verified broker net P&L.',
                'Missing quotes exclude paired cycles and can bias the result. No forward fill, inferred settlement or zero-valued missing wings.',
                'Averaging is idealized fractional-slot exposure and is a diagnostic, not an executable lot schedule.',
                'Small weekly clusters, no liquidity/depth reconstruction and shared observed entry contracts limit repeatable-edge claims.'])
    write('benchmark_cycle_comparisons.csv',detailed)
    write('benchmark_initial_size_diagnostic.csv',unscaled)
    write('benchmark_exclusions.csv',exclusions)
    write('benchmark_stopped_control.csv',stop_rows)
    write('benchmark_stop_control_exclusions.csv',stop_exclusions)
    (OUT/'hedged_straddle_benchmark_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(sizing=sizes,primary=[r for r in results if r['baseline']=='frozen' and r['variant']=='primary' and r['phase']=='evaluation']),indent=2))
    if args.plot:
        plot(detailed)


def plot(rows):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/algo8-matplotlib')
    os.environ.setdefault('XDG_CACHE_HOME','/tmp/algo8-font-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    picked=sorted([r for r in rows if r['baseline']=='frozen' and r['variant']=='primary' and r['phase']=='evaluation' and r['cost_scenario']=='primary'],key=lambda r:r['expiry_date'])
    x=list(range(len(picked)))
    labels=[r['expiry_date'][5:]+' '+r['underlying'][0] for r in picked]
    axs[0].bar([v-.18 for v in x],[r['actual_net']/1000 for r in picked],width=.36,label='Recorded book at cutoff',color='#177e89')
    axs[0].bar([v+.18 for v in x],[r['baseline_net']/1000 for r in picked],width=.36,label='Frozen opening basket',color='#b55a30')
    axs[0].set(xticks=x,xticklabels=labels,title='September–October paired cycles',ylabel='P&L after hypothetical cost stress, ₹ thousand')
    axs[0].tick_params(axis='x',rotation=65)
    axs[0].legend(fontsize=8)
    for scenario,color in [('gross','#6b7280'),('low','#177e89'),('primary','#b55a30'),('high','#8a4a8b')]:
        selected=[r for r in rows if r['baseline']=='frozen' and r['variant']=='primary' and r['phase']=='evaluation' and r['cost_scenario']==scenario]
        s=summarize(selected)
        m=s['difference_mean']/1000
        lo=s['bootstrap']['lower']/1000
        hi=s['bootstrap']['upper']/1000
        axs[1].errorbar(m,scenario,xerr=[[m-lo],[hi-m]],fmt='o',capsize=4,color=color)
    axs[1].axvline(0,color='gray',linestyle=':')
    axs[1].set(title='Mean recorded minus baseline outcome',xlabel='₹ thousand per cycle; 95% expiry-week bootstrap interval')
    fig.suptitle('Approximate risk comparison: size fixed from June–August; no verified margin match',fontsize=11)
    fig.savefig(OUT/'hedged_straddle_benchmark.png',dpi=150)
    svg=OUT/'hedged_straddle_benchmark.svg'
    fig.savefig(svg)
    svg.write_text('\n'.join(s.rstrip() for s in svg.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':
    main()
