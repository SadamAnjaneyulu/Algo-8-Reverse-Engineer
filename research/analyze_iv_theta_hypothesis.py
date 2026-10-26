"""Model-estimated IV/Greeks and symmetric endpoint attribution, not causal proof.

Run: python research/analyze_iv_theta_hypothesis.py --plot
Study choices and limitations: IV_THETA_TEST_PLAN.md.
"""
import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from statistics import median

import analyze_index_triggers as logs
import option_pricing_model as model

ROOT=logs.ROOT
OUT=logs.OUT
MODELS={'primary':(0,0),'rate_6pct':(.06,0),'expiry_5min_earlier':(0,-5),'expiry_5min_later':(0,5)}


def write(name,rows):
    if rows:
        with (OUT/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
            w.writeheader()
            w.writerows(rows)


class Market:
    def __init__(self,u,expiry,metadata,index):
        self.u,self.expiry=u,expiry
        self.index=index
        self.quotes={}
        self.days=set()
        self.strikes=defaultdict(set)
        self.states={}
        for m in metadata:
            c=m['contract'];day=c['trade_date'];k=c['strike'];right=c['option_type']
            path=ROOT/'data/breeze'/m['normalized_path']
            if logs.fetch.digest(path.read_bytes())!=m['normalized_sha256']:
                raise ValueError('Option quote hash mismatch.')
            self.quotes[(day,k,right)]={r['timestamp_ist'][11:16]:{f:float(r[f]) for f in ('open','close','volume')}
                for r in csv.DictReader(path.open(newline=''))}
            self.days.add(day)
            self.strikes[day].add(k)

    def bar(self,day,k,right,clock):
        return self.quotes.get((day,k,right),{}).get(clock)

    def state(self,day,clock,field='close',variant='primary',fixed_strike=None):
        key=(day,clock,field,variant,fixed_strike)
        if key in self.states:
            return self.states[key]
        self.states[key]=None
        rate,shift=MODELS[variant]
        t=datetime.fromisoformat(day+'T'+clock).replace(tzinfo=logs.IST)
        if field=='close':
            t+=timedelta(minutes=1)
        expiry_clock='15:35' if self.expiry>='2026-08-03' else '15:30'
        expiry_time=datetime.fromisoformat(self.expiry+'T'+expiry_clock).replace(tzinfo=logs.IST)+timedelta(minutes=shift)
        tau=(expiry_time-t).total_seconds()/(365*86400)
        if tau<=0:
            return None
        candidates=[b for b in self.index.get((self.u,day),[]) if b['t'].strftime('%H:%M')<=clock]
        if not candidates:
            return None
        guide=candidates[-1]
        spot=guide[field] if guide['t'].strftime('%H:%M')==clock else guide['close']
        pairs=[]
        for k in ([fixed_strike] if fixed_strike is not None else self.strikes[day]):
            c,p=self.bar(day,k,'CE',clock),self.bar(day,k,'PE',clock)
            if c is None or p is None or min(c[field],p[field])<=.025:
                continue
            # Volume is known at candle close. For opening proxies it is an
            # ex-post flag only and is not used to choose a pair.
            if field=='close' and min(c['volume'],p['volume'])<=0:
                continue
            forward=k+(c[field]-p[field])*math.exp(rate*tau)
            if forward<=0 or abs(forward/spot-1)>.03:
                continue
            pairs.append((k,c,p,forward))
        if not pairs:
            return None
        near=sorted(pairs,key=lambda x:abs(x[0]-spot))[:5]
        center=median(x[3] for x in near)
        k,c,p,forward=min(near,key=lambda x:abs(x[0]-center))
        iv=model.implied_vol(c[field],forward,k,tau,'CE',rate)
        if iv is None:
            return None
        result=dict(day=day,clock=clock,field=field,time=t,tau=tau,rate=rate,forward=forward,strike=k,iv=iv,
                    spot_guide=spot,spot_guide_clock=guide['t'].strftime('%H:%M'),
                    pair_zero_volume=min(c['volume'],p['volume'])<=0)
        self.states[key]=result
        return result

    def risk(self,inventory,state):
        if state is None:
            return None
        result=dict(vega_one_point=0.,gamma=0.,delta=0.,theta_calendar_day=0.,zero_volume_legs=0,low_premium_legs=0)
        for (k,right),q in inventory.items():
            if not q:
                continue
            b=self.bar(state['day'],k,right,state['clock'])
            if b is None:
                return None
            p=b[state['field']]
            iv=model.implied_vol(p,state['forward'],k,state['tau'],right,state['rate'])
            if iv is None:
                return None
            g=model.greeks(state['forward'],k,state['tau'],iv,right,state['rate'])
            for name in ('vega_one_point','gamma','delta','theta_calendar_day'):
                result[name]+=q*g[name]
            result['zero_volume_legs']+=b['volume']==0
            result['low_premium_legs']+=p<=.10
        return result


def iv_change(market,current,past_day,past_clock,past_field='close',variant='primary'):
    if current is None:
        return None
    old=market.state(past_day,past_clock,past_field,variant,current['strike'])
    if old is None:
        return None
    return dict(iv_change_points=100*(current['iv']-old['iv']),forward_return_pct=100*(current['forward']/old['forward']-1))


def endpoint_attribution(market,positions,day0,clock0,field0,day1,clock1,field1,kind,variant):
    a=market.state(day0,clock0,field0,variant)
    b=market.state(day1,clock1,field1,variant)
    result=dict(underlying=market.u,expiry_date=market.expiry,kind=kind,model=variant,
        contracts=sum(q!=0 for q in positions.values()),priced_contracts=0,fitted_contracts=0,
        observed_price_pnl='',fitted_price_pnl=0.,movement_pnl=0.,time_pnl=0.,iv_pnl=0.,
        unattributed_price_pnl='',fit_reconciliation_error=0.,low_premium_endpoint_legs=0,zero_volume_endpoint_legs=0,
        full_price_coverage=False,full_model_coverage=False,forward0=a['forward'] if a else '',forward1=b['forward'] if b else '',
        atm_iv0_pct=a['iv']*100 if a else '',atm_iv1_pct=b['iv']*100 if b else '')
    observed=0.
    for (k,right),q in positions.items():
        if not q:
            continue
        p0,p1=market.bar(day0,k,right,clock0),market.bar(day1,k,right,clock1)
        if p0 is None or p1 is None:
            continue
        x,y=p0[field0],p1[field1]
        change=q*(y-x)
        result['priced_contracts']+=1
        observed+=change
        result['low_premium_endpoint_legs']+=min(x,y)<=.10
        result['zero_volume_endpoint_legs']+=min(p0['volume'],p1['volume'])==0
        if a is None or b is None:
            continue
        iv0=model.implied_vol(x,a['forward'],k,a['tau'],right,a['rate'])
        iv1=model.implied_vol(y,b['forward'],k,b['tau'],right,b['rate'])
        if iv0 is None or iv1 is None:
            continue
        parts=model.attribute(a['forward'],a['tau'],iv0,b['forward'],b['tau'],iv1,k,right,a['rate'])
        result['fitted_contracts']+=1
        result['fitted_price_pnl']+=change
        for out,name in [('movement_pnl','movement'),('time_pnl','time'),('iv_pnl','iv')]:
            result[out]+=q*parts[name]
    result['full_price_coverage']=result['priced_contracts']==result['contracts']
    result['full_model_coverage']=result['fitted_contracts']==result['contracts'] and result['contracts']>0
    if result['full_price_coverage']:
        result['observed_price_pnl']=observed
        result['unattributed_price_pnl']=observed-result['fitted_price_pnl']
    result['fit_reconciliation_error']=result['fitted_price_pnl']-sum(result[k] for k in ('movement_pnl','time_pnl','iv_pnl'))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plot',action='store_true')
    args=p.parse_args()
    metadata=defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text())
        metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    fills=defaultdict(list)
    for r in logs.read_fills():
        fills[(r['u'],str(r['expiry']))].append(r)
    entries={(r['underlying'],r['expiry_date']):r for r in csv.DictReader((OUT/'trigger_initial_entries.csv').open())}
    wings=list(csv.DictReader((OUT/'trigger_initial_wings.csv').open()))
    cycles={(r['underlying'],r['expiry_date']):r for r in csv.DictReader((OUT/'option_marked_cycle_summary.csv').open())}
    large={(r['underlying'],r['expiry_date'],r['event_minute_ist'][:16]) for r in csv.DictReader((OUT/'trigger_hedge_events.csv').open()) if r['large_late']=='True'}
    index,_=logs.load_index()
    reference_exits=[]
    for (u,expiry),c in cycles.items():
        t=c['terminal_95pct_short_reduction_ist']
        if c['matched_full_flow_cashflow']=='True' and float(c['final_cashflow_before_costs'])<0 and t and t[11:16]<'15:00':
            reference_exits.append((u,expiry,t[11:16]))
    events=[];initial=[];attributions=[];loss_exits=[];controls=[];carry_exposures=[]
    for (u,expiry),rows in sorted(fills.items()):
        market=Market(u,expiry,metadata[(u,expiry)],index)
        e=entries.get((u,expiry))
        normal=e is not None and e['event_minute_ist'][11:16]=='09:16'
        carry=Counter()
        for r in rows:
            if str(r['t'].date())<expiry:
                carry[(r['strike'],r['ot'])]+=r['signed']
        prior_days=sorted(d for d in market.days if d<expiry)
        if prior_days and any(carry.values()):
            last=prior_days[-1];clock='15:39' if last>='2026-08-03' else '15:29'
            carried_before=market.risk(carry,market.state(last,clock))
            carried_after=market.risk(carry,market.state(expiry,'09:15','open'))
            carry_exposures.append(dict(underlying=u,expiry_date=expiry,
                **{f'{name}_{side}':r[name] if r else '' for side,r in [('previous_close',carried_before),('expiry_open',carried_after)]
                   for name in ('vega_one_point','gamma','delta','theta_calendar_day','zero_volume_legs','low_premium_legs')}))
            for variant in MODELS:
                attributions.append(endpoint_attribution(market,carry,last,clock,'close',expiry,'09:15','open','actual_overnight_carry',variant))
        for ref_u,ref_expiry,ref_clock in reference_exits:
            if ref_u!=u or ref_expiry==expiry or not prior_days:
                continue
            asof=datetime.fromisoformat(expiry+'T'+ref_clock).replace(tzinfo=logs.IST)
            active=Counter()
            for r in rows:
                if r['t']<asof:
                    active[(r['strike'],r['ot'])]+=r['signed']
            if not any(q<0 for q in active.values()):
                continue
            opening=ref_clock=='09:15'
            priorclock=ref_clock if opening else (asof-timedelta(minutes=1)).strftime('%H:%M')
            state=market.state(expiry,priorclock,'open' if opening else 'close')
            last=prior_days[-1];oldclock='15:39' if last>='2026-08-03' else '15:29'
            change=iv_change(market,state,last,oldclock)
            if change:
                controls.append(dict(underlying=u,reference_loss_expiry=ref_expiry,control_expiry=expiry,
                    matched_clock_ist=ref_clock,opening_proxy=opening,
                    iv_change_points=change['iv_change_points'],forward_return_pct=change['forward_return_pct']))
        if normal:
            day=e['event_minute_ist'][:10]
            chosen=[w for w in wings if w['underlying']==u and w['expiry_date']==expiry]
            pos=Counter({(int(e['strike']),'CE'):-1,(int(e['strike']),'PE'):-1})
            for w in chosen:
                pos[(int(w['first_bought_strike']),w['option_type'])]+=1
            for variant in MODELS:
                attributions.append(endpoint_attribution(market,pos,day,'09:16','open',expiry,'15:14','open','frozen_opening_unit_basket',variant))
        inventory=Counter()
        byminute=defaultdict(list)
        for r in rows:
            byminute[r['minute']].append(r)
        for t,batch in sorted(byminute.items()):
            before=inventory.copy()
            for r in batch:
                inventory[(r['strike'],r['ot'])]+=r['signed']
            if normal and str(t.date())==e['event_minute_ist'][:10] and t.strftime('%H:%M')=='09:16':
                state=market.state(str(t.date()),'09:16')
                risk=market.risk(inventory,state)
                core=market.risk({k:q for k,q in inventory.items() if q<0},state)
                protection=market.risk({k:q for k,q in inventory.items() if q>0},state)
                initial.append(dict(underlying=u,expiry_date=expiry,model_available=risk is not None,
                    short_core_vega_one_point=core['vega_one_point'] if core else '',
                    long_protection_vega_one_point=protection['vega_one_point'] if protection else '',
                    initial_vega_offset_fraction=protection['vega_one_point']/(-core['vega_one_point']) if core and protection and core['vega_one_point']<0 else '',
                    **{name:risk[name] if risk else '' for name in ('vega_one_point','gamma','delta','theta_calendar_day','zero_volume_legs','low_premium_legs')}))
            stable=[r for r in batch if r['opening']>0 and r['opening']==r['reverse_opening']]
            shorts=defaultdict(set)
            for r in stable:
                if r['side']=='Sell':
                    shorts[r['strike']].add(r['ot'])
            paired=any(s=={'CE','PE'} for s in shorts.values())
            islarge=(u,expiry,t.isoformat()[:16]) in large
            if not paired and not islarge:
                continue
            if t.strftime('%H:%M')<'09:18':
                continue
            prev=t-timedelta(minutes=1)
            state=market.state(str(t.date()),prev.strftime('%H:%M'))
            rb,ra=market.risk(before,state),market.risk(inventory,state)
            past=prev-timedelta(minutes=15)
            change=iv_change(market,state,str(t.date()),past.strftime('%H:%M')) if past.date()==t.date() else None
            events.append(dict(underlying=u,expiry_date=expiry,event_minute_ist=t.isoformat(),
                phase='preexpiry' if str(t.date())<expiry else 'expiry',paired_short_add=paired,large_late_long_event=islarge,
                model_available=rb is not None and ra is not None,
                iv_change_15min_points=change['iv_change_points'] if change else '',
                forward_return_15min_pct=change['forward_return_pct'] if change else '',
                **{f'{name}_{side}':r[name] if r else '' for side,r in [('before',rb),('after',ra)] for name in ('vega_one_point','gamma','delta','theta_calendar_day','zero_volume_legs','low_premium_legs')},
                vega_change=(ra['vega_one_point']-rb['vega_one_point']) if rb and ra else '',
                net_vega_abs_reduced=abs(ra['vega_one_point'])<abs(rb['vega_one_point']) if rb and ra else '',
                more_short_vega=ra['vega_one_point']<rb['vega_one_point'] if rb and ra else ''))
        c=cycles[(u,expiry)]
        exit_time=c['terminal_95pct_short_reduction_ist']
        if c['matched_full_flow_cashflow']=='True' and float(c['final_cashflow_before_costs'])<0 and exit_time and exit_time[11:16]<'15:00':
            t=datetime.fromisoformat(exit_time)
            opening=t.strftime('%H:%M')=='09:15'
            clock='09:15' if opening else (t-timedelta(minutes=1)).strftime('%H:%M')
            state=market.state(str(t.date()),clock,'open' if opening else 'close')
            last=prior_days[-1] if prior_days else None
            oldclock='15:39' if last and last>='2026-08-03' else '15:29'
            change=iv_change(market,state,last,oldclock) if last else None
            loss_exits.append(dict(underlying=u,expiry_date=expiry,material_exit_ist=exit_time,
                observation='opening_proxy_not_strict_pre_event' if opening else 'previous_completed_candle',
                priorclose_iv_change_points=change['iv_change_points'] if change else '',
                priorclose_forward_return_pct=change['forward_return_pct'] if change else '',
                atm_iv_before_exit_pct=state['iv']*100 if state else '',recorded_cycle_cashflow=float(c['final_cashflow_before_costs'])))
        print(f'Analyzed {u} {expiry}',flush=True)
    summary=dict(initial_books=initial,actual_carry_books=carry_exposures,event_cohorts=[],attribution_cohorts=[],early_losing_exits=loss_exits,matched_exit_comparisons=[])
    for r in loss_exits:
        available=[x['iv_change_points'] for x in controls if x['underlying']==r['underlying'] and x['reference_loss_expiry']==r['expiry_date']]
        case=r['priorclose_iv_change_points']
        summary['matched_exit_comparisons'].append(dict(underlying=r['underlying'],expiry_date=r['expiry_date'],
            observation=r['observation'],case_iv_change_points=case,active_same_clock_controls=len(available),
            control_median_iv_change_points=median(available) if available else None,
            controls_with_iv_rise=sum(x>0 for x in available),
            fraction_controls_below_case=sum(x<case for x in available)/len(available) if available and case!='' else None))
    for phase in ('preexpiry','expiry'):
        for kind in ('paired_short_add','large_late_long_event'):
            selected=[r for r in events if r['phase']==phase and r[kind]]
            valid=[r for r in selected if r['model_available']]
            strict=[r for r in valid if all(r[k]==0 for k in ('zero_volume_legs_before','zero_volume_legs_after','low_premium_legs_before','low_premium_legs_after'))]
            changes=[r['iv_change_15min_points'] for r in selected if r['iv_change_15min_points']!='']
            summary['event_cohorts'].append(dict(phase=phase,kind=kind,event_minutes=len(selected),fully_modeled_minutes=len(valid),
                distinct_cycles=len({(r['underlying'],r['expiry_date']) for r in selected}),
                more_short_vega=sum(r['more_short_vega'] for r in valid),absolute_vega_reduced=sum(r['net_vega_abs_reduced'] for r in valid),
                strict_no_floor_or_zero_volume_minutes=len(strict),strict_more_short_vega=sum(r['more_short_vega'] for r in strict),
                strict_absolute_vega_reduced=sum(r['net_vega_abs_reduced'] for r in strict),
                with_iv_change=len(changes),iv_flat_or_down=sum(x<=0 for x in changes),iv_up_at_least_one_point=sum(x>=1 for x in changes),
                median_iv_change_points=median(changes) if changes else None))
    for kind in ('actual_overnight_carry','frozen_opening_unit_basket'):
        for variant in MODELS:
            selected=[r for r in attributions if r['kind']==kind and r['model']==variant]
            valid=[r for r in selected if r['full_model_coverage']]
            priced=[r for r in selected if r['full_price_coverage']]
            summary['attribution_cohorts'].append(dict(kind=kind,model=variant,attempted=len(selected),fully_modeled=len(valid),
                full_price_coverage_cases=len(priced),full_price_coverage_pnl=sum(r['observed_price_pnl'] for r in priced),
                modeled_subset_exclusions_price_pnl=sum(r['observed_price_pnl'] for r in priced if not r['full_model_coverage']),
                observed_total=sum(r['observed_price_pnl'] for r in valid),movement_total=sum(r['movement_pnl'] for r in valid),
                time_total=sum(r['time_pnl'] for r in valid),iv_total=sum(r['iv_pnl'] for r in valid),
                time_positive=sum(r['time_pnl']>0 for r in valid),iv_negative=sum(r['iv_pnl']<0 for r in valid),
                low_price_endpoint_cases=sum(r['low_premium_endpoint_legs']>0 for r in selected),
                diagnostic_only=kind=='frozen_opening_unit_basket',
                warning='Far-wing expiry prices near the tick floor and very large IV/time counterfactual offsets make long-horizon frozen-basket components unsuitable as economic proof.' if kind=='frozen_opening_unit_basket' else 'Calendar-time model allocation, not direct theta/IV cash flows.'))
    illustrative_pos={(24000,'CE'):-1,(24000,'PE'):-1,(26000,'CE'):1,(22000,'PE'):1}
    illustrative={name:0. for name in ('movement','time','iv','total')}
    for (k,right),q in illustrative_pos.items():
        a=model.attribute(24000,1/365,.2,24240,.25/365,.2,k,right)
        for name in illustrative:
            illustrative[name]+=q*a[name]
    summary['constant_iv_illustration']=dict(description='Hypothetical unit basket, not an observed trade: forward 24000 to 24240, time 1 day to 0.25 day, IV fixed at 20%, wings 22000/26000.',**illustrative)
    summary['limitations']=['Model-derived IV is not observed VIX or a unique exogenous volatility shock; candle asynchrony and smile/moneyness effects remain.',
        'ACT/365 calendar time can allocate overnight repricing differently from a trading-time model. Modeled time/IV contributions are convention-dependent.',
        'Attribution applies to frozen quantities, not the full actively traded strategy P&L. Use only disclosed fully fitted endpoint cases for aggregate interpretations.',
        'Net before/after event Greeks use the same prior completed market state; the full minute batch can mix new shorts, hedge buys and covers.',
        'Counts of repeated event minutes are not independent trials, and event coincidence cannot prove the original decision trigger.',
        'Opening proxies are not precise subminute causal evidence; missing prices, failed IV fits and nonpositive modeled time remain unavailable.',
        'Expiry anchor, discount rates, zero-volume/low-premium prices and retrospective traded-contract candidate universe limit inference.']
    write('iv_adjustment_event_checks.csv',events)
    write('iv_endpoint_attribution.csv',attributions)
    write('iv_initial_book_exposures.csv',initial)
    write('iv_carry_book_exposures.csv',carry_exposures)
    write('iv_early_loss_exit_checks.csv',loss_exits)
    write('iv_early_exit_matched_controls.csv',controls)
    (OUT/'iv_theta_hypothesis_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    if args.plot:
        plot(summary)


def plot(summary):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/algo8-matplotlib')
    os.environ.setdefault('XDG_CACHE_HOME','/tmp/algo8-font-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    initial=[r for r in summary['initial_books'] if r['model_available']]
    axs[0].scatter([r['theta_calendar_day'] for r in initial],[r['vega_one_point'] for r in initial],color='#177e89')
    axs[0].axhline(0,color='gray',linewidth=.8)
    axs[0].axvline(0,color='gray',linewidth=.8)
    axs[0].set(title='Modeled net opening-book exposures',xlabel='Time decay, ₹ per calendar day, fixed forward/IV',ylabel='Vega, ₹ per absolute IV point')
    cohorts=[r for r in summary['event_cohorts'] if r['kind']=='paired_short_add']
    x=list(range(len(cohorts)))
    axs[1].bar([a-.18 for a in x],[r['more_short_vega']/r['fully_modeled_minutes']*100 if r['fully_modeled_minutes'] else 0 for r in cohorts],width=.36,label='Adds more short Vega',color='#b55a30')
    axs[1].bar([a+.18 for a in x],[r['absolute_vega_reduced']/r['fully_modeled_minutes']*100 if r['fully_modeled_minutes'] else 0 for r in cohorts],width=.36,label='Reduces absolute Vega',color='#177e89')
    axs[1].set(xticks=x,xticklabels=[r['phase'] for r in cohorts],ylabel='% of fully modeled event minutes',title='Effect of paired short-addition minute batches')
    axs[1].legend(fontsize=8)
    fig.suptitle('Approximate model estimates: evidence about exposures, not a decoded IV trigger',fontsize=12)
    fig.savefig(OUT/'iv_theta_hypothesis.png',dpi=150)
    svg=OUT/'iv_theta_hypothesis.svg'
    fig.savefig(svg)
    svg.write_text('\n'.join(s.rstrip() for s in svg.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':
    main()
