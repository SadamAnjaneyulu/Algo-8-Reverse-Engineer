"""Reconcile role ledgers and test whether an exit uses a narrower P&L scope.

These are first-crossing diagnostics on actual observed positions, not an exit
backtest. No position mark is invented for a missing option minute.
"""
import csv
import argparse
import gzip
import json
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from statistics import mean

from audit_strike_hedge_rules import ROOT,OUT,Market,logs,write,reconstruct_parents
from mass_match_strategy_rules import numeric,exit_match_score


class RoleBook:
    def __init__(self):
        self.inventory=Counter();self.average={};self.cash=Counter();self.realized=Counter()

    def apply(self,r):
        key=(r['strike'],r['ot']);old=self.inventory[key];p=float(r['price']);q=r['q'];opening=r['opening'];closing=q-opening
        expected=min(q,max(-old if r['side']=='Buy' else old,0))
        if closing!=expected:raise ValueError('Role ledger disagrees with forward inventory classification.')
        ot=r['ot'];oldcost=self.average.get(key,0)
        if r['side']=='Buy':
            self.cash[('short',ot)]-=closing*p;self.cash[('long',ot)]-=opening*p
            self.realized[('short',ot)]+=closing*(oldcost-p)
        else:
            self.cash[('short',ot)]+=opening*p;self.cash[('long',ot)]+=closing*p
            self.realized[('long',ot)]+=closing*(p-oldcost)
        remaining=old+(closing if r['side']=='Buy' else -closing)
        new=old+r['signed'];self.inventory[key]=new
        if opening:self.average[key]=(abs(remaining)*oldcost+opening*p)/(abs(remaining)+opening)
        elif new==0:self.average.pop(key,None)

    def mark(self,market,day,clock,field='close'):
        unrealized=Counter();marked=Counter();missing=Counter();zero=Counter();gross_loss=0.;credit=0.
        for (k,ot),q in self.inventory.items():
            if not q:continue
            role='short' if q<0 else 'long';bar=market.bar(day,k,ot,clock)
            if role=='short':credit+=-q*self.average[(k,ot)]
            if not bar:missing[(role,ot)]+=1;continue
            value=q*(bar[field]-self.average[(k,ot)]);unrealized[(role,ot)]+=value
            marked[(role,ot)]+=q*bar[field];gross_loss+=min(value,0);zero[(role,ot)]+=bar['volume']==0
        def available(keys,part):
            return None if any(missing[k] for k in keys) else sum(part[k] for k in keys)
        short=[('short',ot) for ot in ('CE','PE')];long=[('long',ot) for ot in ('CE','PE')];allkeys=short+long
        equity={k:self.cash[k]+marked[k] for k in allkeys}
        net=available(allkeys,equity);short_eq=available(short,equity);long_eq=available(long,equity)
        su=available(short,unrealized);lu=available(long,unrealized)
        realized=sum(self.realized.values())
        if net is not None and abs(net-(realized+su+lu))>1e-5:raise ValueError('Realized/unrealized ledger reconciliation failed.')
        return dict(net_equity=net,short_book_equity=short_eq,long_book_equity=long_eq,
            short_ce_equity=available([('short','CE')],equity),short_pe_equity=available([('short','PE')],equity),
            realized_equity=realized,unrealized_equity=su+lu if su is not None and lu is not None else None,
            short_unrealized=su,gross_losing_open= gross_loss if not sum(missing.values()) else None,
            short_unrealized_pct_credit=100*su/credit if su is not None and credit>0 else None,
            short_quantity=sum(max(-q,0) for q in self.inventory.values()),missing_contracts=sum(missing.values()),
            zero_volume_contracts=sum(zero.values()))


def build_paths():
    fills=defaultdict(list);metadata=defaultdict(list);references={}
    for r in logs.read_fills():fills[(r['u'],str(r['expiry']))].append(r)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    for r in csv.DictReader((OUT/'option_minute_portfolio_replay.csv').open()):references[(r['underlying'],r['expiry_date'],r['bar_start_ist'])]=numeric(r['marked_equity_close'])
    index,_=logs.load_index();paths={};records=[];checks=0;tie_difference=Counter()
    rawfields=['net_equity','short_book_equity','long_book_equity','short_ce_equity','short_pe_equity','realized_equity',
               'unrealized_equity','short_unrealized','gross_losing_open']
    for (u,e),rs in sorted(fills.items()):
        market=Market(u,e,metadata[(u,e)],index);book=RoleBook();reverse_book=RoleBook();byminute=defaultdict(list);points=[];prior=None;opened=None;peak={}
        for r in rs:byminute[r['minute']].append(r)
        for day in sorted(market.days):
            count=385 if day>='2026-08-03' else 375;start=datetime.fromisoformat(day+'T09:15').replace(tzinfo=logs.IST)
            for i in range(count):
                t=start+timedelta(minutes=i);clock=t.strftime('%H:%M')
                if day==e and i==0:
                    opened=book.mark(market,day,clock,'open');reverse_open=reverse_book.mark(market,day,clock,'open')
                    opened['reverse_tie_short_book_equity']=reverse_open['short_book_equity']
                    opened['reverse_tie_short_unrealized']=reverse_open['short_unrealized']
                    points.append(dict(t=t,opening_proxy=True,**opened))
                for r in byminute[t]:book.apply(r)
                for r in sorted(byminute[t],key=lambda r:(r['t'],-r['source'])):
                    reverse_book.apply({**r,'opening':r['reverse_opening']})
                mark=book.mark(market,day,clock)
                reversed_mark=reverse_book.mark(market,day,clock)
                for field in rawfields:
                    if mark[field] is not None and reversed_mark[field] is not None:
                        tie_difference[field]=max(tie_difference[field],abs(mark[field]-reversed_mark[field]))
                mark['reverse_tie_short_book_equity']=reversed_mark['short_book_equity']
                mark['reverse_tie_short_unrealized']=reversed_mark['short_unrealized']
                expected=references[(u,e,t.isoformat())]
                if (mark['net_equity'] is None)!=(expected is None) or (expected is not None and abs(mark['net_equity']-expected)>1e-5):
                    raise ValueError('Role ledger does not reproduce original full-book equity.')
                checks+=1
                if day<e and i==count-1:prior=mark
                if day==e:points.append(dict(t=t+timedelta(minutes=1),opening_proxy=False,**mark))
        for p in points:
            for name in rawfields:p[name+'_pct_capital']=p[name]/20_000_000*100 if p[name] is not None else None
            for scope in ('net_equity','short_book_equity'):
                current=p[scope]
                for basis,ref in [('previous_close',prior),('expiry_open',opened)]:
                    base=ref[scope] if ref else None
                    p[scope+'_change_'+basis+'_pct_capital']=(current-base)/20_000_000*100 if current is not None and base is not None else None
                if current is not None:peak[scope]=max(peak.get(scope,current),current)
                p[scope+'_drawdown_pct_capital']=(current-peak[scope])/20_000_000*100 if current is not None else None
            records.append(dict(underlying=u,expiry_date=e,available_at_ist=p['t'].isoformat(),**{k:v for k,v in p.items() if k!='t'}))
        paths[(u,e)]=points
        print('Reconciled role ledger',u,e,flush=True)
    write('rule_refine_role_ledger.csv.gz',records)
    return paths,checks,dict(tie_difference)


def signal(cycle,field,threshold,op,completed_only=False):
    if field=='fixed_time':return cycle['fallback']
    for p in cycle['path']:
        if p['t']>=cycle['fallback']:break
        if p['short_quantity']<=0 or (completed_only and p['opening_proxy']):continue
        value=p.get(field)
        if value is not None and ((value<=threshold) if op=='le' else (value>=threshold)):return p['t']
    return cycle['fallback']


def score(cycles,predictions):
    result=exit_match_score(cycles,predictions)
    early=[(c,p) for c,p in zip(cycles,predictions) if datetime.fromisoformat(c['target']).strftime('%H:%M')<'14:45']
    result.update(observed_early_exits=len(early),early_matches_2m=sum(abs((p-datetime.fromisoformat(c['target'])).total_seconds())<=120 for c,p in early),
        false_early_signals=sum(p.strftime('%H:%M')<'14:45' and datetime.fromisoformat(c['target']).strftime('%H:%M')>='14:45' for c,p in zip(cycles,predictions)))
    return result


def observed_flat_times():
    """Whole short-book closures at second resolution, with same-second ties netted."""
    groups=defaultdict(list)
    for r in logs.read_fills():groups[(r['u'],str(r['expiry']))].append(r)
    result={};events=[]
    for (u,e),rs in groups.items():
        bysecond=defaultdict(list);inventory=Counter();flats=[]
        for r in rs:bysecond[r['t']].append(r)
        for t,batch in sorted(bysecond.items()):
            before=sum(max(-q,0) for q in inventory.values())
            for r in batch:inventory[(r['strike'],r['ot'])]+=r['signed']
            after=sum(max(-q,0) for q in inventory.values())
            if str(t.date())==e and before>0 and after==0:
                flats.append(t);events.append(dict(underlying=u,expiry_date=e,flat_time_ist=t.isoformat(),short_quantity_before_second=before))
        result[(u,e)]=dict(first_flat=flats[0].isoformat() if flats else '',
            final_flat=flats[-1].isoformat() if flats and not any(q<0 for q in inventory.values()) else '',
            closure_episodes=len(flats))
    write('rule_refine_observed_short_flat_episodes.csv',events)
    return result


def orders_after_first_flat(flats):
    rows=[]
    for p in reconstruct_parents(logs.read_fills()):
        u,e=p['underlying'],p['expiry_date'];first=flats[(u,e)]['first_flat']
        if p['role']!='new_short' or not first or str(p['first'].date())!=e:continue
        cutoff=datetime.fromisoformat(first)
        if p['first']<=cutoff:continue
        certainty='later_minute_label' if p['label']>cutoff else 'earlier_minute_label' if p['label']+timedelta(minutes=1)<=cutoff else 'overlapping_label_minute'
        rows.append(dict(underlying=u,expiry_date=e,first_short_flat_ist=first,new_short_first_fill_ist=p['first'].isoformat(),
            order_label_ist=p['label'].isoformat(),label_relation=certainty,strike=p['strike'],option_type=p['option_type'],
            quantity=p['quantity'],source_rows=p['sources']))
    write('rule_refine_new_shorts_after_first_flat.csv',rows)
    return dict(parents=len(rows),cycles=len({(r['underlying'],r['expiry_date']) for r in rows}),
        parents_with_later_minute_label=sum(r['label_relation']=='later_minute_label' for r in rows),
        cycles_with_later_minute_labels=len({(r['underlying'],r['expiry_date']) for r in rows if r['label_relation']=='later_minute_label'}),
        note='Order-label minutes are inferred. Later first fills alone do not distinguish new decisions from pending fills.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reuse-ledger',action='store_true');args=parser.parse_args()
    if args.reuse_ledger:
        old=json.loads((OUT/'rule_refine_exit_scope_summary.json').read_text());reconciled=old['reconciled_full_book_minutes']
        tie_sensitivity=old.get('maximum_absolute_currency_difference_under_reversed_ties',{});paths=defaultdict(list)
        with gzip.open(OUT/'rule_refine_role_ledger.csv.gz','rt') as f:
            for r in csv.DictReader(f):
                p={k:(v=='True' if k=='opening_proxy' else numeric(v)) for k,v in r.items() if k not in ('underlying','expiry_date','available_at_ist')}
                p['t']=datetime.fromisoformat(r['available_at_ist']);paths[(r['underlying'],r['expiry_date'])].append(p)
    else:paths,reconciled,tie_sensitivity=build_paths()
    cycles=[];excluded=[];flats=observed_flat_times();post_flat=orders_after_first_flat(flats);target_comparisons=[]
    for r in csv.DictReader((OUT/'option_marked_cycle_summary.csv').open()):
        u,e=r['underlying'],r['expiry_date'];target=r['terminal_95pct_short_reduction_ist']
        if float(r['short_carry_quantity'])<=0:
            excluded.append(dict(underlying=u,expiry_date=e,reason='No positive carried short book.'));continue
        targets=dict(material_95pct=target,first_short_flat=flats[(u,e)]['first_flat'],final_short_flat=flats[(u,e)]['final_flat'])
        if not any(targets.values()):
            excluded.append(dict(underlying=u,expiry_date=e,reason='No observed material reduction or whole short-book closure.'));continue
        target_comparisons.append(dict(underlying=u,expiry_date=e,**targets,closure_episodes=flats[(u,e)]['closure_episodes']))
        for kind,time in targets.items():
            if time:
                cycles.append(dict(underlying=u,expiry_date=e,target=time,target_kind=kind,path=paths[(u,e)],
                    fallback=datetime.fromisoformat(e+('T15:14' if e>='2026-08-03' else 'T15:29')).replace(tzinfo=logs.IST)))
    fields=[k for k in cycles[0]['path'][0] if k.endswith('_pct_capital')]
    levels=(.1,.15,.2,.25,.3,.4,.5,.6,.75,1,1.25,1.5)
    rules=[('fixed_time',0,'time')]+[(f,sign*x,op) for f in fields for sign,op in [(-1,'le'),(1,'ge')] for x in levels]
    rules.extend(('short_unrealized_pct_credit',-x,'le') for x in (1,2,3,4,5,7.5,10,15,20,25,30,40,50))
    calibration=[];evaluation=[];predictions=[]
    for target_kind,completed_only in [(k,c) for k in ('material_95pct','first_short_flat','final_short_flat') for c in (False,True)]:
        train=[c for c in cycles if c['expiry_date']<='2026-08-31' and c['target_kind']==target_kind]
        test=[c for c in cycles if c['expiry_date']>'2026-08-31' and c['target_kind']==target_kind]
        rank=[]
        for rule in rules:
            pr=[signal(c,*rule,completed_only) for c in train]
            r=dict(target_kind=target_kind,feature=rule[0],threshold=rule[1],operator=rule[2],completed_only=completed_only,**score(train,pr));rank.append((r,rule));calibration.append(r)
        best=min(rank,key=lambda x:(-x[0]['matches_within_2m'],x[0]['mean_abs_error_minutes']))
        chosen=[('selected',best[1]),('fixed_time',('fixed_time',0,'time'))]
        for field in ('net_equity_pct_capital','short_book_equity_pct_capital','short_unrealized_pct_capital','gross_losing_open_pct_capital',
                      'net_equity_change_previous_close_pct_capital','short_book_equity_change_previous_close_pct_capital'):
            chosen.append(('stated_1pct_scope_test',(field,-1,'le')))
        chosen.append(('open_short_credit_4pct_test',('short_unrealized_pct_credit',-4,'le')))
        for kind,rule in chosen:
            pr=[signal(c,*rule,completed_only) for c in test]
            evaluation.append(dict(target_kind=target_kind,kind=kind,feature=rule[0],threshold=rule[1],operator=rule[2],completed_only=completed_only,
                calibration_matches_2m=next(r['matches_within_2m'] for r,rule2 in rank if rule2==rule),**score(test,pr)))
            for c,p in zip(test,pr):
                predictions.append(dict(underlying=c['underlying'],expiry_date=c['expiry_date'],target_kind=target_kind,kind=kind,feature=rule[0],threshold=rule[1],completed_only=completed_only,
                    observed_terminal_reduction_ist=c['target'],predicted_ist=p.isoformat(),error_minutes=(p-datetime.fromisoformat(c['target'])).total_seconds()/60))
    write('rule_refine_exit_scope_calibration.csv',calibration);write('rule_refine_exit_scope_evaluation.csv',evaluation)
    write('rule_refine_exit_scope_predictions.csv',predictions);write('rule_refine_exit_scope_exclusions.csv',excluded)
    contexts=[]
    for c in cycles:
        target=datetime.fromisoformat(c['target']);known=[p for p in c['path'] if p['t']<=target and p['short_quantity']>0]
        if known:
            p=known[-1]
            contexts.append(dict(underlying=c['underlying'],expiry_date=c['expiry_date'],target_kind=c['target_kind'],observed_terminal_reduction_ist=c['target'],
                last_known_mark_ist=p['t'].isoformat(),**{k:v for k,v in p.items() if k!='t'}))
    write('rule_refine_exit_scope_at_reductions.csv',contexts)
    write('rule_refine_exit_target_comparison.csv',target_comparisons)
    summary=dict(reconciled_full_book_minutes=reconciled,calibration_cycles=len({(c['underlying'],c['expiry_date']) for c in cycles if c['expiry_date']<='2026-08-31'}),
        evaluation_cycles=len({(c['underlying'],c['expiry_date']) for c in cycles if c['expiry_date']>'2026-08-31'}),calibration_comparisons=len(calibration),
        evaluation=evaluation,new_shorts_after_first_flat=post_flat,maximum_absolute_currency_difference_under_reversed_ties=tie_sensitivity,
        note='Separate short/long and realized/unrealized scopes reconcile with every original complete mark. Actual-book first-crossing diagnostics with fixed time fallback, not a cloned strategy. Opening marks are proxies; short-credit denominator includes fresh and carried shorts. Role/cost decomposition uses forward ties, with reverse-tie sensitivity retained.')
    (OUT/'rule_refine_exit_scope_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
