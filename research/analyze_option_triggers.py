"""Audit real option bars and test premium-selection / portfolio-loss hypotheses.

python research/analyze_option_triggers.py --plot
Marks use observed trade candles, not executable bid/ask quotes. Never fills gaps.
"""
import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path
from statistics import median

import analyze_index_triggers as logs
import fetch_breeze_options as options

ROOT=options.ROOT
OUT=ROOT/'research/outputs'


def write(name,rows):
    if rows:
        with (OUT/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
            w.writeheader()
            w.writerows(rows)


def mark(cash,inventory,quotes,day,clock,field='close'):
    """All active contracts need this exact minute. No stale-price substitution."""
    missing=[]
    zero_volume=0
    result=cash
    for contract,q in inventory.items():
        if not q:
            continue
        bar=quotes.get((day,*contract),{}).get(clock)
        if bar is None:
            missing.append(contract)
            continue
        zero_volume+=bar['volume']==0
        if field=='adverse_bound':
            price=bar['low'] if q>0 else bar['high']
        elif field=='favorable_bound':
            price=bar['high'] if q>0 else bar['low']
        else:
            price=bar[field]
        result+=q*price
    return (None if missing else result),len(missing),zero_volume


def closure_states(fills):
    bysecond=defaultdict(list)
    inventory=Counter()
    carry=Counter()
    for r in fills:
        bysecond[r['t']].append(r)
        if r['t'].date()<r['expiry']:
            carry[(r['strike'],r['ot'])]+=r['signed']
    states=[]
    for t,batch in sorted(bysecond.items()):
        for r in batch:
            inventory[(r['strike'],r['ot'])]+=r['signed']
        states.append(dict(t=t,short=sum(max(-q,0) for q in inventory.values()),gross=sum(abs(q) for q in inventory.values())))
    return states,carry,inventory


def terminal_reduction(states,expiry,carried,remaining_fraction):
    es=[s for s in states if str(s['t'].date())==expiry]
    if not carried or not es or es[-1]['short']>carried*remaining_fraction:
        return ''
    last=max((i for i,s in enumerate(es) if s['short']>carried*remaining_fraction),default=-1)
    return es[last+1]['t'].isoformat() if last+1<len(es) else ''


def replay(u,expiry,fills,quotes):
    states,carry,final=closure_states(fills)
    carried=sum(max(-q,0) for q in carry.values())
    byminute=defaultdict(list)
    for r in fills:
        byminute[(str(r['t'].date()),r['t'].strftime('%H:%M'))].append(r)
    inventory=Counter()
    cash=0.
    records=[]
    preclose=None
    expiry_open=None
    carry_debit_close=None
    carry_value_close=None
    dates=sorted({key[0] for key in quotes})
    for day in dates:
        count=385 if day>='2026-08-03' else 375
        start=datetime.fromisoformat(day+'T09:15:00').replace(tzinfo=logs.IST)
        for i in range(count):
            t=start+timedelta(minutes=i)
            clock=t.strftime('%H:%M')
            prev=(t-timedelta(minutes=1)).strftime('%H:%M')
            prior,prior_missing,_=mark(cash,inventory,quotes,day,prev)
            # At 09:15 there is no earlier same-session candle. Report opening
            # marks separately; do not silently reuse yesterday's close.
            opened,open_missing,_=mark(cash,inventory,quotes,day,clock,'open')
            low,_,_=mark(cash,inventory,quotes,day,clock,'adverse_bound')
            high,_,_=mark(cash,inventory,quotes,day,clock,'favorable_bound')
            if day==expiry and i==0:
                expiry_open=opened
            before_short=sum(max(-q,0) for q in inventory.values())
            carry_value,_,_=mark(0.,carry,quotes,day,clock)
            carry_short={k:min(q,0) for k,q in carry.items()}
            short_value,_,_=mark(0.,carry_short,quotes,day,clock)
            batch=byminute.get((day,clock),[])
            for r in batch:
                inventory[(r['strike'],r['ot'])]+=r['signed']
                cash-=r['signed']*float(r['price'])
            equity,missing,zero_volume=mark(cash,inventory,quotes,day,clock)
            records.append(dict(underlying=u,expiry_date=expiry,bar_start_ist=t.isoformat(),
                equity_available_at_ist=(t+timedelta(minutes=1)).isoformat(),
                observed_cashflow=cash,marked_equity_close=equity if equity is not None else '',
                prior_completed_minute_equity_before_fills=prior if prior is not None else '',
                opening_mark_before_fills=opened if opened is not None else '',
                frozen_preminute_inventory_adverse_ohlc_bound=low if low is not None else '',
                frozen_preminute_inventory_favorable_ohlc_bound=high if high is not None else '',
                missing_active_contracts=missing,prior_missing_active_contracts=prior_missing,
                active_zero_volume_contracts=zero_volume,fill_records=len(batch),
                short_quantity_before_minute=before_short,short_quantity_after_minute=sum(max(-q,0) for q in inventory.values()),
                gross_quantity_after_minute=sum(abs(q) for q in inventory.values()),
                fixed_carry_marked_value=carry_value if carry_value is not None else '',
                fixed_carry_short_debit=-short_value if short_value is not None else ''))
            if day<expiry and i==count-1:
                preclose=equity
                carry_value_close=carry_value
                carry_debit_close=-short_value if short_value is not None else None
    last=records[-1]
    short_flat=terminal_reduction(states,expiry,carried,0)
    material=terminal_reduction(states,expiry,carried,.05)
    rec=dict(underlying=u,expiry_date=expiry,observed_dates=';'.join(dates),short_carry_quantity=carried,
        residual_contracts=sum(v!=0 for v in final.values()),residual_short_quantity=sum(max(-v,0) for v in final.values()),
        final_cashflow_before_costs=cash,preexpiry_last_minute_equity=preclose if preclose is not None else '',
        expiry_opening_equity_before_fills=expiry_open if expiry_open is not None else '',
        final_observed_marked_equity=last['marked_equity_close'],
        final_short_book_flat_ist=short_flat,terminal_95pct_short_reduction_ist=material,
        minute_snapshots=len(records),unmarkable_snapshots=sum(r['marked_equity_close']=='' for r in records),
        nonflat_zero_volume_snapshots=sum(r['active_zero_volume_contracts']>0 for r in records),
        matched_full_flow_cashflow=not any(final.values()),
        carry_net_value_at_previous_close=carry_value_close if carry_value_close is not None else '',
        carry_short_debit_at_previous_close=carry_debit_close if carry_debit_close is not None else '')
    snap=next((r for r in records if material and r['bar_start_ist'][:16]==material[:16]),None)
    for key in ('material_exit_prior_minute_equity','material_exit_opening_mark','material_exit_adverse_bound','material_exit_favorable_bound','material_exit_prior_minus_previous_close','material_exit_prior_minus_expiry_open'):
        rec[key]=''
    if snap:
        rec['material_exit_prior_minute_equity']=snap['prior_completed_minute_equity_before_fills']
        rec['material_exit_opening_mark']=snap['opening_mark_before_fills']
        rec['material_exit_adverse_bound']=snap['frozen_preminute_inventory_adverse_ohlc_bound']
        rec['material_exit_favorable_bound']=snap['frozen_preminute_inventory_favorable_ohlc_bound']
        if rec['material_exit_prior_minute_equity']!='':
            if preclose is not None:
                rec['material_exit_prior_minus_previous_close']=rec['material_exit_prior_minute_equity']-preclose
            if expiry_open is not None:
                rec['material_exit_prior_minus_expiry_open']=rec['material_exit_prior_minute_equity']-expiry_open
    # Candidate crossings are evaluated on the ACTUAL evolving book, not a
    # counterfactual replay of a different stop. Exclude already-flat snapshots.
    for threshold in (140000,150000,200000):
        candidates=[r for r in records if r['bar_start_ist'][:10]==expiry and r['gross_quantity_after_minute']>0 and
                    r['marked_equity_close']!='' and r['marked_equity_close']<=-threshold]
        rec[f'first_observed_nonflat_close_below_minus_{threshold}_ist']=candidates[0]['equity_available_at_ist'] if candidates else ''
    if carry_debit_close and carry_value_close is not None:
        grow=[r for r in records if r['bar_start_ist'][:10]==expiry and r['fixed_carry_short_debit']!='' and
              r['fixed_carry_short_debit']>=1.04*carry_debit_close]
        # Fixed overnight inventory at current quotes is a hypothetical retained
        # basket, including after its actual buybacks; this tests a candidate only.
        rec['fixed_carry_short_debit_4pct_first_cross_ist']=grow[0]['equity_available_at_ist'] if grow else ''
    else:
        rec['fixed_carry_short_debit_4pct_first_cross_ist']=''
    return rec,records


def premium_checks(u,expiry,fills,quotes,index):
    groups=defaultdict(list)
    for r in fills:
        if r['t'].date()<r['expiry'] and r['side']=='Buy' and r['opening']>0 and r['opening']==r['reverse_opening']:
            groups[(r['minute'],r['strike'],r['ot'])].append(r)
    result=[]
    for (minute,strike,ot),batch in sorted(groups.items()):
        day=str(minute.date())
        clock=(minute-timedelta(minutes=1)).strftime('%H:%M')
        selected=quotes.get((day,strike,ot),{}).get(clock)
        phase='initial' if minute.time()<time(9,18) else 'routine' if minute.time()<time(14,45) else 'late'
        target=(2 if u=='NIFTY' else 7) if phase!='late' else (5 if u=='NIFTY' else 20)
        ib,_=logs.reference(index,u,minute)
        spot=ib['close'] if ib else None
        candidates=[]
        if selected and spot:
            for (d,k,right),bars in quotes.items():
                if d!=day or right!=ot or not (k>spot if ot=='CE' else k<spot):
                    continue
                b=bars.get(clock)
                if b and b['close']>0:
                    candidates.append((k,b))
        selected_error=abs(selected['close']-target) if selected else None
        best=min((abs(b['close']-target) for k,b in candidates),default=None)
        q=sum(r['opening'] for r in batch)
        result.append(dict(underlying=u,expiry_date=expiry,event_minute_ist=minute.isoformat(),option_type=ot,bought_strike=strike,
            opening_quantity=q,phase=phase,hypothesis_target_premium=target,
            weighted_executed_price=float(sum(r['price']*r['opening'] for r in batch)/q),
            prior_completed_close=selected['close'] if selected else '',prior_completed_volume=selected['volume'] if selected else '',
            prior_index_close=spot if spot else '',candidate_contracts=len(candidates),
            selected_in_restricted_candidates=any(k==strike for k,b in candidates),
            selected_abs_error=selected_error if selected_error is not None else '',best_abs_error=best if best is not None else '',
            selected_tied_closest_to_target=selected_error is not None and best is not None and any(k==strike for k,b in candidates) and selected_error<=best+.0000001,
            closer_candidate_count=sum(abs(b['close']-target)<selected_error-.0000001 for k,b in candidates) if selected_error is not None else '',
            source_rows=';'.join(str(r['source']) for r in batch)))
    return result


def carry_stop_checks(u,expiry,fills,quotes):
    """Bound original carried-short attribution; test a specified 4% reference.

    Contract-level diagnostics, not asserted strategy lots or stop instructions.
    FIFO closes carried shorts first; opposite allocation closes new shorts first.
    """
    _,carry,_=closure_states(fills)
    prior_dates=sorted({d for d,k,ot in quotes if d<expiry})
    if not prior_dates:
        return []
    day=prior_dates[-1]
    close_clock='15:39' if day>='2026-08-03' else '15:29'
    records=[]
    for (k,ot),q in sorted(carry.items()):
        if q>=0:
            continue
        reference=quotes.get((day,k,ot),{}).get(close_clock)
        if not reference:
            continue
        threshold=1.04*reference['close']
        remaining_first=remaining_last=-q
        inventory=q
        earliest=latest=''
        for r in fills:
            if str(r['t'].date())!=expiry or (r['strike'],r['ot'])!=(k,ot):
                continue
            if r['signed']>0 and inventory<0:
                covered=min(r['signed'],-inventory)
                remaining_first=max(remaining_first-covered,0)
                remaining_last=min(remaining_last,max(-inventory-covered,0))
            inventory+=r['signed']
            if not earliest and remaining_first==0:
                earliest=r['t'].isoformat()
            if not latest and remaining_last==0:
                latest=r['t'].isoformat()
        bars=quotes.get((expiry,k,ot),{})
        hits=[]
        for clock,b in sorted(bars.items()):
            t=datetime.fromisoformat(expiry+'T'+clock).replace(tzinfo=logs.IST)
            if clock=='09:15' and b['open']>=threshold:
                hits.append((t,b['volume']))
            if b['close']>=threshold:
                hits.append((t+timedelta(minutes=1),b['volume']))
        hit=min(hits,key=lambda item:item[0]) if hits else None
        unambiguous=bool(earliest and earliest==latest)
        delay=(datetime.fromisoformat(earliest)-hit[0]).total_seconds()/60 if hit and unambiguous else ''
        records.append(dict(underlying=u,expiry_date=expiry,strike=k,option_type=ot,carried_short_quantity=-q,
            prior_derivative_close=reference['close'],candidate_4pct_price=threshold,
            earliest_original_carry_cover_bound_ist=earliest,latest_original_carry_cover_bound_ist=latest,
            original_carry_completion_unambiguous=unambiguous,
            first_open_or_completed_close_cross_ist=hit[0].isoformat() if hit else '',
            crossing_candle_zero_volume=(hit[1]==0) if hit else '',
            unambiguous_completion_minus_cross_minutes=delay))
    return records


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plot',action='store_true')
    args=p.parse_args()
    print('Validating all raw/normalized/metadata option triples...',flush=True)
    verified=options.validated_files(ROOT)
    audit=defaultdict(Counter)
    metas=defaultdict(list)
    for name in verified:
        if '/metadata/' not in name:
            continue
        m=json.loads((ROOT/name).read_text())
        c,a=m['coverage'],m['fill_alignment']
        u=m['contract']['underlying']
        v=audit[u]
        v.update(dict(contract_days=1,bars=c['observed_bars'],full_minute_grid=c['full_minute_grid'],
                      missing_minutes=len(c['missing_minutes_ist']),zero_price_bars=c['zero_price_bars'],zero_volume_bars=c['zero_volume_bars']))
        v.update({k:a[k] for k in ('logged_fills','fills_with_bar','fills_inside_ohlc_plus_one_tick','fills_outside_ohlc_plus_one_tick','fills_without_bar')})
        metas[(u,m['contract']['expiry_date'])].append(m)
    index,_=logs.load_index()
    cycles=defaultdict(list)
    for r in logs.read_fills():
        cycles[(r['u'],str(r['expiry']))].append(r)
    replay_rows=[]
    cycle_rows=[]
    premium_rows=[]
    carry_rows=[]
    for (u,expiry),fills in sorted(cycles.items()):
        quotes={}
        for m in metas[(u,expiry)]:
            c=m['contract']
            path=ROOT/'data/breeze'/m['normalized_path']
            quotes[(c['trade_date'],c['strike'],c['option_type'])]={r['timestamp_ist'][11:16]:
                {k:float(r[k]) for k in ('open','high','low','close','volume')} for r in csv.DictReader(path.open(newline=''))}
        cycle,minute_rows=replay(u,expiry,fills,quotes)
        cycle_rows.append(cycle)
        replay_rows.extend(minute_rows)
        premium_rows.extend(premium_checks(u,expiry,fills,quotes,index))
        carry_rows.extend(carry_stop_checks(u,expiry,fills,quotes))
        print(f'Replayed {u} {expiry}: {cycle["unmarkable_snapshots"]}/{len(minute_rows)} minute marks unavailable; residual contracts {cycle["residual_contracts"]}',flush=True)
    summary=dict(audit={k:dict(v) for k,v in audit.items()},cycles=len(cycle_rows),minute_snapshots=len(replay_rows),
                 unavailable_equity_snapshots=sum(r['marked_equity_close']=='' for r in replay_rows),premium_cohorts=[])
    for u in ('NIFTY','SENSEX'):
        for phase in ('initial','routine','late'):
            rows=[r for r in premium_rows if r['underlying']==u and r['phase']==phase]
            valid=[r for r in rows if r['selected_in_restricted_candidates'] and r['candidate_contracts']>=3]
            prices=[r['prior_completed_close'] for r in rows if r['prior_completed_close']!='']
            summary['premium_cohorts'].append(dict(underlying=u,phase=phase,minute_strike_groups=len(rows),
                with_prior_candle=len(prices),median_prior_close=median(prices) if prices else None,
                restricted_rank_comparisons=len(valid),selected_closest=sum(r['selected_tied_closest_to_target'] for r in valid),
                median_closer_candidates=median(r['closer_candidate_count'] for r in valid) if valid else None))
    summary['limitations']=[
        'All inventory/MTM is conditional on zero opening inventory, complete recorded fills and inferred event clock; no fees, funding or external settlement.',
        'Missing active-contract minute makes equity unavailable; no interpolation or forward fill. Observed zero-volume trade candles may be stale and are flagged.',
        'OHLC adverse/favorable bounds freeze the preminute book and combine nonsimultaneous extremes. They are not observed equity, executable losses or proof a stop fired.',
        'Premium rank candidates are restricted to contracts traded anywhere in this cycle; this retrospective universe is not the complete eligible chain.',
        'One-minute trade candles and internally inferred event times cannot identify exact intraminute stop chronology, quote-side selection or execution latency.',
        'Fixed loss candidates 140k/150k are exploratory after inspecting execution cashflows; the documented 1% of 2Cr is 200k.',
        'Fixed carry 4% candidate uses short option debit relative to prior close, not a confirmed denominator; it can include hypothetical quotes after real buybacks.',
        'Chronological October comparisons have been inspected and are not a blinded holdout; no strategy Sharpe, return curve or causal theta/IV attribution is inferred.']
    comparable=[r for r in carry_rows if r['original_carry_completion_unambiguous'] and r['unambiguous_completion_minus_cross_minutes']!='']
    summary['carry_4pct_prior_close_candidate']=dict(carried_short_contracts_with_reference=len(carry_rows),
        attribution_unambiguous=sum(r['original_carry_completion_unambiguous'] for r in carry_rows),
        unambiguous_with_price_cross=len(comparable),completion_within_0_to_2min_of_cross=sum(0<=r['unambiguous_completion_minus_cross_minutes']<=2 for r in comparable),
        completion_more_than_10min_after_cross=sum(r['unambiguous_completion_minus_cross_minutes']>10 for r in comparable),
        completion_before_candidate_cross=sum(r['unambiguous_completion_minus_cross_minutes']<0 for r in comparable),
        note='4% price increase relative to previous derivative close is one candidate only. No original basket IDs, confirmed stop reference or intraminute crossing are supplied.')
    OUT.mkdir(exist_ok=True)
    write('option_marked_cycle_summary.csv',cycle_rows)
    write('option_minute_portfolio_replay.csv',replay_rows)
    write('option_premium_selection_checks.csv',premium_rows)
    write('option_carry_stop_checks.csv',carry_rows)
    (OUT/'option_trigger_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
    if args.plot:
        plot(replay_rows,premium_rows)


def plot(replay_rows,premiums):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/algo8-matplotlib')
    os.environ.setdefault('XDG_CACHE_HOME','/tmp/algo8-font-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for ax,(u,expiry) in zip(axs[0],[('NIFTY','2026-07-14'),('SENSEX','2026-10-15')]):
        rows=[r for r in replay_rows if r['underlying']==u and r['expiry_date']==expiry]
        y=[r['marked_equity_close']/1000 if r['marked_equity_close']!='' else float('nan') for r in rows]
        boundary=next(i for i,r in enumerate(rows) if r['bar_start_ist'][:10]==expiry)
        ax.plot(range(len(rows)),y,color='#177e89',linewidth=1)
        ax.axvline(boundary,color='gray',linestyle=':',label='Expiry open; overnight interval compressed')
        ax.axhline(-150,color='#b55a30',linestyle='--',label='Exploratory −₹150k')
        ax.axhline(-200,color='gray',linestyle='--',label='Documented 1% of ₹2Cr')
        ax.set(title=f'{u} expiry {expiry}: observed book marks',xlabel='Recorded session-minute index (overnight compressed)',ylabel='Marked equity, ₹ thousand, before costs')
        ax.legend(fontsize=7)
    for ax,u,target in zip(axs[1],('NIFTY','SENSEX'),(2,7)):
        rows=[r for r in premiums if r['underlying']==u and r['phase']=='routine' and r['prior_completed_close']!='']
        ax.scatter([r['prior_completed_close'] for r in rows],[r['weighted_executed_price'] for r in rows],s=7,alpha=.35,color='#177e89')
        ax.axvline(target,color='#b55a30',linestyle=':')
        ax.axhline(target,color='#b55a30',linestyle=':')
        ax.set(title=f'{u} routine new-long purchases',xlabel='Previous completed option close, ₹',ylabel='Quantity-weighted executed price, ₹')
    fig.suptitle('Algo 8: observed option prices and conditional portfolio replay',fontsize=13)
    fig.savefig(OUT/'option_trigger_evidence.png',dpi=150)
    svg=OUT/'option_trigger_evidence.svg'
    fig.savefig(svg)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':
    main()
