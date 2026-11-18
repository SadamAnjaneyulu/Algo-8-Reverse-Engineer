"""Quality audit precedes all new economic conclusions."""
import csv,json,subprocess
from collections import defaultdict
from decimal import Decimal
import numpy as np
import pandas as pd
from inputs import HERE,ROOT,SOURCE,CACHE,META,CID,DecimalBook,fills,sha,save,load_index,actual_path,iso

READ_INPUTS=['ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md','research/hypothesis_controller_search/HYPOTHESIS_CONTROLLER_SEARCH.md',
 'research/policy_execution_separation/POLICY_EXECUTION_RECONSTRUCTION.md','research/intermediate_exit_study/INTERMEDIATE_EXIT_CONTROLLER.md',
 'research/ALPHA_CANDIDATE_FINDINGS.md','research/outputs/alpha_highest_ranked_rulebook.json',
 'research/policy_execution_separation/selected_model_config.yaml','research/hypothesis_controller_search/outputs/calibration.json',
 'research/hypothesis_controller_search/outputs/input_hashes.json','research/outputs/playbook_fill_ledger.csv.gz','research/outputs/playbook_event_book.csv.gz',
 'research/outputs/option_minute_portfolio_replay.csv','research/outputs/option_marked_cycle_summary.csv','Trades_GKOHNP140.csv','Info.txt',
 'research/intermediate_exit_study/exit_case_ledger.csv.gz','research/intermediate_exit_study/short_cover_children.csv.gz']

def run():
    CACHE.mkdir(exist_ok=True);f=fills();index,_=load_index();pnl=pd.read_csv(SOURCE/'option_minute_portfolio_replay.csv');events=pd.read_csv(SOURCE/'playbook_event_book.csv.gz')
    metadata=defaultdict(list);hashes={name:sha(ROOT/name) for name in READ_INPUTS}
    with (ROOT/'Trades_GKOHNP140.csv').open(newline='',encoding='utf-8-sig') as stream:raw={i:(Decimal(r[137]),r[11]) for i,r in enumerate(csv.reader(stream),1)}
    # Read the full frozen strong register without copying or modifying it.
    strong=subprocess.check_output(['git','show','f5b4ab8:STRONG_FINDINGS.md'],cwd=ROOT)
    stronghash=__import__('hashlib').sha256(strong).hexdigest()
    for p in sorted((ROOT/'data/breeze/metadata/options').rglob('*.json')):
        hashes[str(p.relative_to(ROOT))]=sha(p)
        m=json.loads(p.read_text());metadata[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    for p in sorted((ROOT/'data/breeze/normalized/indices').rglob('*.csv')):
        hashes[str(p.relative_to(ROOT))]=sha(p)
    audit=[];residuals=[];maxcash=maxpnl=maxmark=0.;atomic_checks=child_checks=mark_checks=0
    for cid,fs in f.groupby('cycle_id',sort=True):
        meta=META[cid];u,e=meta['underlying'],meta['expiry_date'];book=DecimalBook();source_groups={t:g for t,g in fs.groupby('timestamp_ist',sort=True)}
        ev=events[(events.underlying==u)&(events.expiry_date==e)];eg=ev.set_index('timestamp_ist')
        for t,g in source_groups.items():
            for r in g.itertuples():
                price,side=raw[r.source_row];assert price==Decimal(str(r.execution_price)) and side==r.side
                before,after,closed,opened,real=book.apply((r.strike,r.option_type),r.incremental_quantity,price,side)
                assert (before,after,closed,opened)==(r.quantity_before,r.quantity_after,r.closing_quantity,r.opening_quantity)
                err=abs(float(real)-r.realized_pnl_change);assert err<1e-6;maxpnl=max(maxpnl,err);child_checks+=1
                assert abs(float(-price*r.incremental_quantity*(1 if side=='Buy' else -1))-r.cash_change)<1e-7
            expected={ (int(k),right):int(q) for k,right,q,cost in json.loads(eg.loc[t,'after_positions'])}
            assert expected=={k:q for k,q in book.q.items() if q};atomic_checks+=1
        assert abs(float(book.cash)-fs.cash_change.sum())<1e-6
        ps=pnl[(pnl.underlying==u)&(pnl.expiry_date==e)];times=pd.to_datetime(ps.bar_start_ist).astype('int64').to_numpy()//60_000_000_000
        contracts=sorted(set(zip(fs.strike,fs.option_type))|{(m['contract']['strike'],m['contract']['option_type']) for m in metadata[(u,e)]});lookup={key:j for j,key in enumerate(contracts)};tm={int(t):i for i,t in enumerate(times)}
        arrays={n:np.full((len(times),len(contracts)),np.nan) for n in ['open','high','low','close','volume']};sopen=np.full(len(times),np.nan);sclose=sopen.copy();days=[];quote_rows=0
        for m in metadata[(u,e)]:
            path=ROOT/'data/breeze'/m['normalized_path'];assert sha(path)==m['normalized_sha256'];hashes[str(path.relative_to(ROOT))]=m['normalized_sha256']
            c=m['contract'];j=lookup[(c['strike'],c['option_type'])];d=pd.read_csv(path);ti=pd.to_datetime(d.timestamp_ist).astype('int64').to_numpy()//60_000_000_000
            for row_i,minute in enumerate(ti):
                if int(minute) not in tm:continue
                i=tm[int(minute)]
                for name in arrays:arrays[name][i,j]=float(d.iloc[row_i][name])
                quote_rows+=1
        for i,t in enumerate(times):
            stamp=iso(int(t)*60);day=stamp[:10];clock=stamp[11:16];bars=index.get((u,day),[])
            # Lookups are cached below per date to avoid repeated history scans.
            if day not in days:days.append(day)
        ix={}
        for day in days:
            for b in index.get((u,day),[]):ix[int(b['t'].timestamp())//60]=b
        for i,t in enumerate(times):
            if int(t) in ix:sopen[i]=ix[int(t)]['open'];sclose[i]=ix[int(t)]['close']
        z=dict(minutes=times,strikes=np.array([x[0] for x in contracts],int),rights=np.array([int(x[1]=='PE') for x in contracts],int),spot_open=sopen,spot_close=sclose,**arrays)
        np.savez_compressed(CACHE/f'cycle_{cid:02}.npz',**z)
        a=actual_path(fs,z);ok=np.isfinite(a['equity'])&ps.marked_equity_close.notna().to_numpy();error=np.abs(a['equity'][ok]-ps.marked_equity_close.to_numpy()[ok]);assert (error<1e-6).all();maxmark=max(maxmark,float(error.max(initial=0)));mark_checks+=int(ok.sum())
        assert np.array_equal(np.isfinite(a['equity']),ps.marked_equity_close.notna());assert np.allclose(a['cash'],ps.observed_cashflow,atol=1e-6,rtol=0)
        q=a['q'][-1];live=q!=0;finalmark=arrays['close'][-1];known=meta['dates'][0]<e;flat=not live.any();lastday=iso(int(times[-1])*60)[:10]
        for j in np.flatnonzero(live):residuals.append(dict(cycle_id=cid,underlying=u,expiry_date=e,strike=contracts[j][0],option_type=contracts[j][1],quantity=int(q[j]),
            endpoint_ist=iso(int(times[-1]+1)*60),quote_close=finalmark[j],quote_volume=arrays['volume'][-1,j],
            valuation='stored_quote_mark' if np.isfinite(finalmark[j]) else 'unpriced',actual_settlement_observed=False,quantity_persistence='received ledger, not independently confirmed broker holdings'))
        audit.append(dict(cycle_id=cid,underlying=u,expiry_date=e,known_initialization=known,received_fill_records=len(fs),parent_orders=fs.parent_id.nunique(),
            received_dates=';'.join(sorted(fs.date.unique())),expiry_fills_present=bool(fs.date.eq(e).any()),quote_endpoint=iso(int(times[-1]+1)*60),
            endpoint_on_expiry=lastday==e,flat_received_endpoint=flat,residual_contracts=int(live.sum()),residual_short_quantity=int(np.maximum(-q,0).sum()),
            residual_long_quantity=int(np.maximum(q,0).sum()),unpriced_residual_contracts=int(np.sum(live&~np.isfinite(finalmark))),
            endpoint_quote_mark_available=bool(np.isfinite(a['equity'][-1])),endpoint_modeled_prices=0,minute_marks=len(ps),missing_minute_marks=int(np.isnan(a['equity']).sum()),
            zero_volume_active_minutes=int(np.any((a['q']!=0)&(arrays['volume']<=0),axis=1).sum()),
            quote_contract_days=len(metadata[(u,e)]),stored_quote_rows=quote_rows,full_chain_verified=False,
            fills_outside_or_without_minute_ohlc_units=float(a['uncertain_units'].sum()),actual_nav_observed=False,actual_margin_observed=False,
            economic_status='closed_received_book' if flat and known else 'initialization_uncertain' if not known else 'partial_history_with_quoted_residual'))
        print('Audited',cid,u,e,flush=True)
    coverage=pd.DataFrame(audit);save(coverage,'data_quality_and_coverage.csv');save(pd.DataFrame(residuals),'residual_position_ledger.csv')
    hashes['research/final_alpha_attribution/REGISTERED_PLAN.md']=sha(HERE/'REGISTERED_PLAN.md')
    snapshot=dict(base_revision='12dc6af',strong_revision='f5b4ab8',strong_findings_v6_sha256=stronghash,immutable_inputs_sha256=hashes,
        canonical_child_checks=child_checks,atomic_books_checked=atomic_checks,raw_quote_minute_equity_checks=mark_checks,max_child_realised_error=maxpnl,max_mark_reconciliation_error=maxmark,
        assumed_initial_quantity=0,source_initialization_not_independently_verified=True,account_nav_margin_missing=True,modeled_endpoint_valuations=0)
    (HERE/'input_audit.json').write_text(json.dumps(snapshot,indent=2))
    text=f'''# Data quality audit — before final economic comparisons

The independent Decimal book reconciles **{child_checks:,}** recorded children
and **{atomic_checks:,}** atomic books to the frozen canonical ledgers. Raw stored
quotes reconcile **{mark_checks:,}** available minute equity snapshots; maximum
error is {maxmark:.10g} rupees. Prices are recorded executions for cash flow;
residual values are quote marks, never executions or invented settlement.

There are {len(coverage)} cycles, {int(coverage.known_initialization.sum())} with
observed pre-expiry initialization and three expiry-only starts. All source-book
initial quantities assume zero before the first received fill; external completeness
is unverified. {int(coverage.flat_received_endpoint.sum())} received books end flat;
{int((~coverage.flat_received_endpoint).sum())} retain residual contracts.
All {int(coverage.endpoint_quote_mark_available.sum())} endpoints can be marked
using stored quotes, with {int(coverage.unpriced_residual_contracts.sum())} unpriced
endpoint contracts and zero modeled endpoint prices. This does not establish
that those positions were held to that mark or settled at that value.

{int((~coverage.expiry_fills_present).sum())} cycles have no received expiry-day
fills. Their available expiry quotes support a hypothetical residual valuation,
not unobserved executions. Missing minute marks, zero-volume candles and incomplete
traded-contract chain coverage remain explicit. No account NAV, actual margin,
authenticated transaction charges or full bid/ask tape is available.

The three economic views must remain distinct: received fill cash flow; received
cash plus quoted residuals; the same marked result after fixed cost/stress estimates.
A positive cash receipt with an open short is not realised profit. A full model
attribution is not a modeled liquidation. The 35 previously researched cycles do
not reproduce the screenshot's March 2025–May 2026 backtest.

The per-cycle [coverage table](data_quality_and_coverage.csv),
[residual ledger](residual_position_ledger.csv) and [immutable input audit](input_audit.json)
are the accounting boundary for all subsequent results. The fixed plan was saved
before economic comparisons. No original finding/configuration/result is changed.
'''
    (HERE/'DATA_QUALITY_AUDIT.md').write_text(text)
    print('Data quality audit written; economics not yet computed.',flush=True)
if __name__=='__main__':run()
