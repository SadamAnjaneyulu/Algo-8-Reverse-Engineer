"""Meaningful chronology, leakage, accounting, matching and censoring tests."""
import numpy as np
import pandas as pd
from types import SimpleNamespace
from .features import market_features,Regimes,strict_event_matches
from .dataset import CanonicalState,actions_for
from .models import chronological_folds,feature_columns,event_scores
from .first_passage import first_passages


def test_market_bar_not_available_until_completed():
    times=pd.date_range('2026-07-13 09:15',periods=40,freq='min',tz='Asia/Kolkata')
    b=pd.DataFrame({'open':100.,'high':101.,'low':99.,'close':np.arange(100.,140.),'volume':0.},index=times)
    original=market_features(b)
    b.loc[times[20]:,'close']=99999.
    changed=market_features(b)
    pd.testing.assert_frame_equal(original.loc[:times[20]],changed.loc[:times[20]])
    assert original.index[0]==times[0]+pd.Timedelta(minutes=1)
    assert original.vwap_distance_pct.isna().all()


def test_missing_bar_does_not_compress_time():
    times=pd.date_range('2026-07-13 09:15',periods=10,freq='min',tz='Asia/Kolkata')
    b=pd.DataFrame({'open':100.,'high':101.,'low':99.,'close':100.},index=times).drop(times[5])
    f=market_features(b)
    assert pd.isna(f.loc[times[6],'spot'])
    assert pd.isna(f.loc[times[8],'return_3'])


def test_regime_fit_does_not_consume_future():
    f=pd.DataFrame({'underlying':['NIFTY']*20,'second':range(20),'return_15':np.arange(20.),'rv_15':np.arange(20.)})
    r=Regimes().fit(f.iloc[:10]);before=dict(r.thresholds)
    _=r.transform(f.assign(return_15=100000.))
    assert r.thresholds==before


def test_no_outcome_or_identifier_feature_leakage():
    f=pd.DataFrame(columns=['cycle_id','strike','second','expiry_date','y_close_contract','y_future_entry','after_quantity','clock_minute','book_gamma','return_15'])
    cols=feature_columns(f,'full')
    assert set(cols)=={'clock_minute','book_gamma','return_15'}


def test_cycle_splits_purge_overlapping_sessions():
    meta=[dict(cycle_id=i,expiry_date=f'2026-07-{i+2:02}',underlying='NIFTY',dates=[f'2026-07-{i+1:02}']) for i in range(12)]
    protocol={'minimum_training_cycles':3,'test_block_cycles':2}
    for _,train,test in chronological_folds(meta,protocol):
        assert set(train).isdisjoint(test)
        assert max(meta[i]['expiry_date'] for i in train)<min(meta[i]['dates'][0] for i in test)


def test_canonical_ledger_costs_are_consumed_not_recomputed():
    b=CanonicalState(1,np.array([0]),65)
    r=SimpleNamespace(quantity_before=0,quantity_after=-65,cash_change=6500.,realized_pnl_change=0.,average_cost_after=100.,second=10,opening_quantity=65,closing_quantity=0,source_row=1)
    b.consume(r,0)
    assert b.q[0]==-65 and b.cost[0]==100 and b.cash[0]==6500
    r=SimpleNamespace(quantity_before=-65,quantity_after=0,cash_change=-5200.,realized_pnl_change=1300.,average_cost_after=np.nan,second=20,opening_quantity=0,closing_quantity=65,source_row=2)
    b.consume(r,0)
    assert b.q[0]==0 and b.cash[0]==1300 and b.realized[0]==1300


def test_long_wing_sale_is_not_short_stop():
    flow=np.zeros((2,4));flow[0,3]=65
    a=actions_for(np.array([65,65]),np.array([65,65]),flow)
    assert a['sell_protection'] and not a['reduce_ce'] and not a['reduce_pe']


def test_simultaneous_actions_remain_multilabel():
    flow=np.zeros((2,4));flow[0,0]=65;flow[0,1]=130;flow[1,2]=65
    a=actions_for(np.array([195,195]),np.array([130,195]),flow)
    assert a['add_ce'] and a['reduce_ce'] and a['buy_protection']


def test_timing_match_is_one_to_one():
    assert len(strict_event_matches([100,110],[105],60))==1
    assert strict_event_matches([100,200],[40,160,201],60)==[(100,40),(200,160)]


def test_no_cross_contract_timing_credit():
    f=pd.DataFrame({'cycle_id':[1,1],'option_type':['CE','CE'],'strike':[100,200], 'second':[60,60], 'target':[1,0], 'prediction':[0,1]})
    s,_=event_scores(f,'close_contract',120)
    assert s['matched_episodes']==0 and s['event_recall']==0


def test_first_passage_is_once_per_epoch_and_missing_is_censored():
    f=pd.DataFrame({'cycle_id':[1]*5,'strike':[100]*5,'option_type':['CE']*5,'second':[60,120,180,240,300],
        'position_age_minutes':[1,2,3,4,5],'premium_loss_pct':[0,np.nan,60,70,80]})
    p=first_passages(f,'premium_loss_pct',50)
    assert len(p)==1 and p.second.iloc[0]==180
    assert p.crossing_resolution.iloc[0]=='left_or_gap_censored'


def test_new_epoch_can_generate_new_first_passage():
    f=pd.DataFrame({'cycle_id':[1]*4,'strike':[100]*4,'option_type':['CE']*4,'second':[60,120,180,240],
        'position_age_minutes':[1,2,1,2],'premium_loss_pct':[0,60,0,70]})
    p=first_passages(f,'premium_loss_pct',50)
    assert p.second.tolist()==[120,240]
