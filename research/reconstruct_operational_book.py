"""Independent raw-fill book reconstruction for the operational playbook.

No original allocation IDs are invented. Same-second changes are atomic in the
event timeline; child-fill cost attribution and its reverse-order sensitivity
remain explicit. Market inputs are completed candles preceding the fill minute.
"""
import csv
import hashlib
import json
from bisect import bisect_left
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

from audit_strike_hedge_rules import ROOT,OUT,logs,Market
from analyze_side_allocations import load_parents
from rank_trigger_probabilities import save_records


class IndependentBook:
    def __init__(self):
        self.positions=Counter();self.cost={};self.cash=Decimal(0);self.realized=Decimal(0)

    def apply(self,f):
        key=(f['strike'],f['ot']);old=self.positions[key];quantity=f['q'];price=Decimal(f['price'])
        signed=quantity if f['side']=='Buy' else -quantity
        closed=min(abs(old),quantity) if old*signed<0 else 0
        opened=quantity-closed;old_cost=self.cost.get(key,Decimal(0))
        pnl=Decimal(closed)*(price-old_cost)*(1 if old>0 else -1)
        residual=old+(closed if signed>0 else -closed)
        new=old+signed
        if opened:
            self.cost[key]=(abs(residual)*old_cost+opened*price)/(abs(residual)+opened)
        elif new==0:self.cost.pop(key,None)
        self.positions[key]=new;self.cash-=signed*price;self.realized+=pnl
        return dict(quantity_before=old,quantity_after=new,opening_quantity=opened,closing_quantity=closed,
                    average_cost_before=float(old_cost) if old else None,average_cost_after=float(self.cost[key]) if new else None,
                    realized_pnl_change=float(pnl),cash_change=float(-signed*price))

    def quantities(self):
        return {right+'_'+role:sum(max(sign*q,0) for (k,r),q in self.positions.items() if r==right)
                for right in ('CE','PE') for role,sign in (('short',-1),('long',1))}

    def encoded(self):
        return json.dumps([[k,right,q,float(self.cost[(k,right)])] for (k,right),q in sorted(self.positions.items()) if q],separators=(',',':'))

    def frozen_loss_bound(self):
        if sum(q for (k,right),q in self.positions.items() if right=='CE')<0:return None
        levels={0}|{k for k,right in self.positions}
        worst=min(self.cash+sum(q*max(spot-k if right=='CE' else k-spot,0)
                                for (k,right),q in self.positions.items()) for spot in levels)
        return max(0.,-float(worst))


class PriorSnapshot:
    def __init__(self,market):self.market=market;self.units={}

    def unit(self,day,clock,key,state):
        cache=(day,clock,key)
        if cache not in self.units:
            quote=self.market.bar(day,*key,clock)
            risk=self.market.risk({key:1},state) if quote else None
            self.units[cache]=(quote,risk)
        return self.units[cache]

    def mark(self,book,day,clock,state):
        value=Decimal(0);missing=0;zero=0;unrealized=Decimal(0)
        result=dict(delta=0.,gamma=0.,vega_one_point=0.,theta_calendar_day=0.)
        badrisk=0
        for key,q in book.positions.items():
            if not q:continue
            quote,risk=self.unit(day,clock,key,state)
            if quote is None:missing+=1
            else:
                price=Decimal(str(quote['close']));value+=q*price
                unrealized+=q*(price-book.cost[key]);zero+=quote['volume']<=0
            if risk is None:badrisk+=1
            else:
                for name in result:result[name]+=q*risk[name]
        if badrisk:result={name:None for name in result}
        equity=None if missing else float(book.cash+value)
        if not missing:
            assert abs(float(book.cash+value-book.realized-unrealized))<1e-6
        result.update(equity=equity,unrealized=None if missing else float(unrealized),realized=float(book.realized),
                      missing_quote_contracts=missing,missing_risk_contracts=badrisk,zero_volume_contracts=zero)
        return result


def classify_flow(before,after,flow):
    opens=flow['short_CE_open']+flow['short_PE_open']+flow['long_CE_open']+flow['long_PE_open']
    closes=flow['short_CE_close']+flow['short_PE_close']+flow['long_CE_close']+flow['long_PE_close']
    if not sum(after.values()) and sum(before.values()):return 'all_roles_flat'
    if after['CE_short']+after['PE_short']==0 and before['CE_short']+before['PE_short']>0:return 'short_book_flat'
    if opens and closes:return 'mixed_open_and_close'
    if opens:return 'opening_flow'
    return 'reduction_flow' if closes else 'no_change'


def main():
    fills=logs.read_fills();parents=load_parents();source_parent={int(s):p for p in parents for s in p['sources'].split(';')}
    metadata=defaultdict(list);grouped=defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    for f in fills:grouped[(f['u'],str(f['expiry']))].append(f)
    index,stored=logs.load_index();events=[];fill_rows=[];sessions=[];cycles=[];maxima=[]
    cached=pd.read_csv(OUT/'allocation_greek_context.csv.gz')
    cached_qty={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in cached.to_dict('records')}
    checks=0;pnl_checks=0;max_pnl_error=0.;max_tie_realized=0.;tail_episodes=[]
    replay=pd.read_csv(OUT/'option_minute_portfolio_replay.csv')
    for (u,e),fs in sorted(grouped.items()):
        market=Market(u,e,metadata[(u,e)],index);snapshot=PriorSnapshot(market);book=IndependentBook();reverse=IndependentBook()
        seconds=defaultdict(list)
        for f in fs:seconds[f['t']].append(f)
        sequence=[];flat_times=defaultdict(list);peaks={};tail_start=None;previous_date=None
        for t,batch in sorted(seconds.items()):
            if previous_date is not None and t.date()!=previous_date:
                sessions.append(dict(underlying=u,expiry_date=e,date=str(previous_date),phase='preexpiry' if str(previous_date)<e else 'expiry',
                                     last_execution_ist=sequence[-1]['timestamp_ist'],**{k:v for k,v in sequence[-1].items() if k.startswith('after_')},
                                     last_new_short_ist=next((r['timestamp_ist'] for r in reversed(sequence) if r['date']==str(previous_date) and r['short_CE_open']+r['short_PE_open']>0),'')))
            previous_date=t.date();day=str(t.date());minute=t.replace(second=0,microsecond=0)
            clock=(minute-timedelta(minutes=1)).strftime('%H:%M');state=market.state(day,clock)
            q0=book.quantities();before_positions=book.encoded();a=snapshot.mark(book,day,clock,state);flow=Counter()
            for f in batch:
                parent=source_parent[f['source']];result=book.apply(f)
                assert result['opening_quantity']==f['opening']
                side='long' if f['side']=='Buy' else 'short'
                closing_role='short' if f['side']=='Buy' else 'long'
                flow[side+'_'+f['ot']+'_open']+=result['opening_quantity']
                flow[closing_role+'_'+f['ot']+'_close']+=result['closing_quantity']
                fill_rows.append(dict(source_row=f['source'],parent_id=parent['parent_id'],underlying=u,expiry_date=e,date=day,
                    timestamp_ist=t.isoformat(),order_label_ist=parent['label'].isoformat(),allocation_signal_time='unobserved',
                    parent_requested_quantity=parent['requested_quantity'],parent_total_observed_quantity=parent['quantity'],
                    parent_first_fill_ist=parent['first'].isoformat(),parent_last_fill_ist=parent['last'].isoformat(),parent_observed_role=parent['role'],
                    strike=f['strike'],option_type=f['ot'],instrument_type='option',side=f['side'],incremental_quantity=f['q'],
                    execution_price=float(f['price']),tie_sensitive_role=f['opening']!=f['reverse_opening'],
                    **result))
            for f in reversed(batch):reverse.apply(f)
            assert reverse.positions==book.positions and reverse.cash==book.cash
            max_tie_realized=max(max_tie_realized,abs(float(book.realized-reverse.realized)))
            q1=book.quantities();b=snapshot.mark(book,day,clock,state)
            for name in [role+'_'+right+'_'+direction for right in ('CE','PE') for role in ('short','long') for direction in ('open','close')]:
                flow.setdefault(name,0)
            for role in q1:
                if q0[role]>0 and q1[role]==0:flat_times[role].append(t.isoformat())
                if role not in peaks or q1[role]>peaks[role]['quantity']:
                    peaks[role]=dict(underlying=u,expiry_date=e,role=role,quantity=q1[role],base_units=q1[role]/logs.UNIT[u],timestamp_ist=t.isoformat())
            if sum(q0.values())>0 and sum(q1.values())==0:flat_times['all'].append(t.isoformat())
            if q0['CE_short']+q0['PE_short']>0 and q1['CE_short']+q1['PE_short']==0:flat_times['short'].append(t.isoformat())
            tail=sum(q for (k,right),q in book.positions.items() if right=='CE')
            if tail<0 and tail_start is None:tail_start=t
            if tail>=0 and tail_start is not None:
                tail_episodes.append(dict(underlying=u,expiry_date=e,start_ist=tail_start.isoformat(),end_ist=t.isoformat(),seconds=(t-tail_start).total_seconds(),open_at_export_end=False));tail_start=None
            row=dict(underlying=u,expiry_date=e,date=day,phase='preexpiry' if day<e else 'expiry',timestamp_ist=t.isoformat(),
                     source_rows=';'.join(str(f['source']) for f in batch),fill_records=len(batch),
                     parent_ids=';'.join(sorted({source_parent[f['source']]['parent_id'] for f in batch})),
                     before_positions=before_positions,after_positions=book.encoded(),
                     **{'before_'+k:v for k,v in q0.items()},**{'after_'+k:v for k,v in q1.items()},**flow,
                     event_class=classify_flow(q0,q1,flow),quote_bar_start_ist=(minute-timedelta(minutes=1)).isoformat(),
                     quote_age_seconds=(t-minute).total_seconds(),prior_atm_iv_pct=100*state['iv'] if state else None,
                     prior_forward=state['forward'] if state else None,
                     prior_spot_guide=state['spot_guide'] if state else None,
                     spot_guide_age_minutes=(int(clock[:2])*60+int(clock[3:])-int(state['spot_guide_clock'][:2])*60-int(state['spot_guide_clock'][3:])) if state else None,
                     after_call_tail_quantity=tail,
                     before_call_tail_quantity=q0['CE_long']-q0['CE_short'],
                     after_frozen_expiry_loss_bound=book.frozen_loss_bound(),
                     **{'before_'+k:v for k,v in a.items()},**{'after_'+k:v for k,v in b.items()})
            row['earliest_parent_label_ist']=min(source_parent[f['source']]['label'] for f in batch).isoformat()
            for prefix,qty in (('before',q0),('after',q1)):
                row[prefix+'_gross_short_quantity']=qty['CE_short']+qty['PE_short']
                row[prefix+'_gross_long_quantity']=qty['CE_long']+qty['PE_long']
                row[prefix+'_net_CE_quantity']=qty['CE_long']-qty['CE_short']
                row[prefix+'_net_PE_quantity']=qty['PE_long']-qty['PE_short']
                row[prefix+'_net_total_quantity']=row[prefix+'_gross_long_quantity']-row[prefix+'_gross_short_quantity']
            # Quote age is measured from prior candle completion, not its start.
            events.append(row);sequence.append(row)
        if previous_date is not None:
            sessions.append(dict(underlying=u,expiry_date=e,date=str(previous_date),phase='preexpiry' if str(previous_date)<e else 'expiry',
                                 last_execution_ist=sequence[-1]['timestamp_ist'],**{k:v for k,v in sequence[-1].items() if k.startswith('after_')},
                                 last_new_short_ist=next((r['timestamp_ist'] for r in reversed(sequence) if r['date']==str(previous_date) and r['short_CE_open']+r['short_PE_open']>0),'')))
        if tail_start is not None:tail_episodes.append(dict(underlying=u,expiry_date=e,start_ist=tail_start.isoformat(),end_ist='',seconds=None,open_at_export_end=True))
        final=book.quantities();record=dict(underlying=u,expiry_date=e,observed_sessions=len({str(f['t'].date()) for f in fs}),
            source_fills=len(fs),atomic_seconds=len(sequence),net_cash=float(book.cash),realized_pnl=float(book.realized),
            residual_positions=book.encoded(),**{'final_'+k:v for k,v in final.items()})
        for role in list(final)+['short','all']:
            is_flat=sum(final.values())==0 if role=='all' else final['CE_short']+final['PE_short']==0 if role=='short' else final[role]==0
            record['final_'+role+'_flat_ist']=flat_times[role][-1] if is_flat and flat_times[role] else ''
        cycles.append(record);maxima.extend(peaks.values())
        # Independently reproduce cached minute-boundary gross quantities.
        pointers=0;checkbook=IndependentBook()
        for key,c in sorted(cached_qty.items()):
            if key[:2]!=(u,e):continue
            cutoff=datetime.fromisoformat(key[2]+'T'+key[3]).replace(tzinfo=logs.IST)
            while pointers<len(fs) and fs[pointers]['t']<cutoff:checkbook.apply(fs[pointers]);pointers+=1
            qty=checkbook.quantities()
            for right in ('CE','PE'):
                for role in ('short','long'):
                    assert abs(qty[right+'_'+role]/logs.UNIT[u]-c['g_'+right+'_'+role+'_units'])<1e-9
            checks+=1
        pointers=0;checkbook=IndependentBook()
        original=replay[replay.underlying.eq(u)&replay.expiry_date.eq(e)].sort_values('bar_start_ist')
        for c in original.to_dict('records'):
            bar=datetime.fromisoformat(c['bar_start_ist']);cutoff=bar+timedelta(minutes=1)
            while pointers<len(fs) and fs[pointers]['t']<cutoff:checkbook.apply(fs[pointers]);pointers+=1
            mark=snapshot.mark(checkbook,str(bar.date()),bar.strftime('%H:%M'),market.state(str(bar.date()),bar.strftime('%H:%M')))
            expected=c['marked_equity_close'];actual=mark['equity']
            assert (actual is None)==pd.isna(expected)
            if actual is not None:
                error=abs(actual-expected);assert error<1e-5;max_pnl_error=max(max_pnl_error,error)
            pnl_checks+=1
        print('Reconstructed',u,e,len(sequence),'seconds',flush=True)
    assert len(fill_rows)==len(fills) and len({r['source_row'] for r in fill_rows})==len(fills)
    save_records('playbook_fill_ledger.csv.gz',fill_rows);save_records('playbook_event_book.csv.gz',events)
    save_records('playbook_session_end_books.csv',sessions);save_records('playbook_cycle_books.csv',cycles)
    save_records('playbook_quantity_peaks.csv',maxima);save_records('playbook_negative_call_tail_intervals.csv',tail_episodes)
    summary=dict(fills=len(fills),parents=len(parents),cycles=len(cycles),sessions=len(sessions),atomic_seconds=len(events),
                 cached_minute_quantity_checks=checks,maximum_reverse_tie_realized_difference=max_tie_realized,
                 independent_minute_pnl_checks=pnl_checks,maximum_legacy_pnl_difference=max_pnl_error,
                 preceding_quote_equity_before_available=sum(r['before_equity'] is not None for r in events),
                 preceding_quote_equity_after_available=sum(r['after_equity'] is not None for r in events),
                 greek_before_available=sum(r['before_delta'] is not None for r in events),
                 greek_after_available=sum(r['after_delta'] is not None for r in events),
                 raw_sha256=hashlib.sha256((ROOT/'Trades_GKOHNP140.csv').read_bytes()).hexdigest(),
                 note='Independent pooled-cost accounting; quotes/Greeks are preceding-candle estimates, not executable NAV, broker margin or original allocation ownership. No settlement is invented.')
    (OUT/'playbook_book_audit.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()
