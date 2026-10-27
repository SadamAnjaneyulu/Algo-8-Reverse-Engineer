"""Separate protection replacement from protection accompanying fresh shorts."""
import csv
import json
from collections import Counter,defaultdict
from datetime import timedelta

from audit_strike_hedge_rules import ROOT,OUT,logs,Market
from analyze_side_allocations import load_parents,match_parents
from clarify_position_lifecycle import inventory_at
from rank_trigger_probabilities import save_records


def main():
    ps=load_parents();group=defaultdict(list);meta=defaultdict(list);fills=defaultdict(list)
    for p in ps:group[(p['underlying'],p['expiry_date'])].append(p)
    for f in logs.read_fills():fills[(f['u'],str(f['expiry']))].append(f)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());meta[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    index,_=logs.load_index();rows=[]
    for (u,e),parents in sorted(group.items()):
        market=Market(u,e,meta[(u,e)],index)
        for right in ('CE','PE'):
            longs=[p for p in parents if p['role']=='new_long' and p['option_type']==right]
            sells=[p for p in parents if p['role']=='long_sell' and p['option_type']==right]
            shorts=[p for p in parents if p['role']=='new_short' and p['option_type']==right]
            for buy,sell,distance,candidates in match_parents(longs,sells,lambda a,b:a['quantity']==b['quantity'] and a['strike']!=b['strike'],seconds=5):
                if any(abs((p['first']-buy['first']).total_seconds())<=5 for p in shorts):continue
                first=min(buy['first'],sell['first']);cutoff=first.replace(second=0,microsecond=0)
                day=str(first.date());clock=(cutoff-timedelta(minutes=1)).strftime('%H:%M')
                state=market.state(day,clock)
                before=inventory_at(fills[(u,e)],first)
                after=before.copy();after[(sell['strike'],right)]-=sell['quantity'];after[(buy['strike'],right)]+=buy['quantity']
                a,b=market.risk(before,state),market.risk(after,state)
                sign=1 if right=='CE' else -1
                row=dict(underlying=u,expiry_date=e,phase='preexpiry' if day<e else 'expiry',option_type=right,
                         buy_parent=buy['parent_id'],sell_parent=sell['parent_id'],first_ist=first.isoformat(),
                         quantity=buy['quantity'],old_strike=sell['strike'],new_strike=buy['strike'],
                         inward_strike_change=sign*(sell['strike']-buy['strike']),
                         old_execution_price=sell['price'],new_execution_price=buy['price'],
                         net_premium_spend=buy['quantity']*(buy['price']-sell['price']),
                         candidate_old_longs=candidates,association_ambiguous=candidates>1,
                         prior_forward=state['forward'] if state else '',prior_atm_iv_pct=100*state['iv'] if state else '',
                         full_model_available=a is not None and b is not None,abs_delta_change='',abs_vega_change='',gamma_change='')
                if a is not None and b is not None:
                    row.update(abs_delta_change=abs(b['delta'])-abs(a['delta']),
                               abs_vega_change=abs(b['vega_one_point'])-abs(a['vega_one_point']),
                               gamma_change=b['gamma']-a['gamma'])
                rows.append(row)
    save_records('deep_hedge_refresh_pairs.csv',rows)
    summaries=[]
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            rs=[r for r in rows if r['underlying']==u and r['phase']==phase]
            priced=[r for r in rs if r['full_model_available']]
            summaries.append(dict(underlying=u,phase=phase,paired_refreshes=len(rs),
                inward_refreshes=sum(r['inward_strike_change']>0 for r in rs),
                positive_net_premium_spend=sum(r['net_premium_spend']>0 for r in rs),
                old_premium_at_or_below_010=sum(r['old_execution_price']<=.100001 for r in rs),
                ambiguous_pairs=sum(r['association_ambiguous'] for r in rs),full_model_cases=len(priced),
                abs_delta_reduced=sum(r['abs_delta_change']<0 for r in priced),
                abs_vega_reduced=sum(r['abs_vega_change']<0 for r in priced),gamma_increased=sum(r['gamma_change']>0 for r in priced)))
    save_records('deep_hedge_refresh_summary.csv',summaries)
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
