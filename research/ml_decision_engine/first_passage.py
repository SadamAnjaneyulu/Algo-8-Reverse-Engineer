"""Fixed diagnostic thresholds accompany ML hazards; no new rule-bank search."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .features import strict_event_matches


def first_passages(frame,column,threshold):
    """One first passage per active epoch; missing intervals stay censored.

    Passing an end-of-minute mark cannot identify the first tick crossing.
    At the first available mark already above threshold, activation is left
    censored. A gap in marks makes the interval unresolved, never exact.
    """
    result=[]
    for key,g in frame.sort_values('second').groupby(['cycle_id','strike','option_type']):
        epoch=None;fired=False;last_value=np.nan;last_time=None
        for row in g.itertuples():
            origin=row.second-round(row.position_age_minutes*60) if np.isfinite(row.position_age_minutes) else None
            if epoch!=origin:
                epoch=origin;fired=False;last_value=np.nan;last_time=None
            value=getattr(row,column,np.nan)
            if np.isfinite(value) and value>=threshold and not fired:
                exact=last_time is not None and row.second-last_time==60 and np.isfinite(last_value) and last_value<threshold
                result.append(dict(cycle_id=key[0],strike=key[1],option_type=key[2],second=int(row.second),
                    feature=column,threshold=threshold,value=float(value),
                    crossing_resolution='preceding_minute_interval' if exact else 'left_or_gap_censored',
                    earliest_known_below_second=last_time if np.isfinite(last_value) and last_value<threshold else np.nan,
                    source='completed marks; activation before this boundary is intrabar ambiguous'))
                fired=True
            if np.isfinite(value):last_value=value;last_time=row.second
    return pd.DataFrame(result)


def run_first_passage(data,protocol,out,meta):
    g=data[data.level.eq('contract')&data.contract_units.lt(0)].copy()
    g['basket_loss_rupees']=-g.basket_equity
    g['basket_drawdown_rupees']=g.basket_drawdown
    g['side_loss_rupees']=np.where(g.option_type.eq('CE'),-g.ce_equity,-g.pe_equity)
    g['side_drawdown_rupees']=np.where(g.option_type.eq('CE'),g.ce_drawdown,g.pe_drawdown)
    g['iv_rise_points']=g.iv_change_5
    ledgers=[];scores=[]
    for column,thresholds in protocol['predeclared_first_passage'].items():
        for threshold in thresholds:
            signals=first_passages(g,column,threshold)
            if len(signals)==0:continue
            ledgers.append(signals)
            for cid,cycle in g.groupby('cycle_id'):
                predicted=signals[signals.cycle_id.eq(cid)]
                for outcome in ['reduce_contract','close_contract','flatten_short','final_liquidation']:
                    for tolerance in [60,120]:
                        total_actual=total_pred=total_match=0
                        for key,c in cycle.groupby(['strike','option_type']):
                            actual=c.loc[c['y_'+outcome].gt(0),'second'].tolist()
                            # Do not count multiple partial fill minutes as separate onsets.
                            starts=[];last=None
                            for t in actual:
                                if last is None or t-last>120:starts.append(int(t))
                                last=t
                            p=predicted[predicted.strike.eq(key[0])&predicted.option_type.eq(key[1])].second.tolist()
                            total_actual+=len(starts);total_pred+=len(p)
                            total_match+=len(strict_event_matches(starts,p,tolerance))
                        scores.append(dict(cycle_id=cid,underlying=cycle.underlying.iloc[0],feature=column,threshold=threshold,
                            outcome=outcome,tolerance_seconds=tolerance,actual=total_actual,predicted=total_pred,matched=total_match,
                            precision=total_match/total_pred if total_pred else 0.,recall=total_match/total_actual if total_actual else 0.,
                            causal_stop_identity='unobserved',independent_threshold_optimization=False,
                            test_type='fixed first-passage diagnostic, not selected policy'))
    pd.concat(ledgers,ignore_index=True).to_csv(out/'first_passage_activation_ledger.csv.gz',index=False,compression='gzip') if ledgers else pd.DataFrame(columns=['feature','threshold','second']).to_csv(out/'first_passage_activation_ledger.csv.gz',index=False,compression='gzip')
    pd.DataFrame(scores).to_csv(out/'first_passage_scores.csv',index=False)
    return pd.DataFrame(scores)
