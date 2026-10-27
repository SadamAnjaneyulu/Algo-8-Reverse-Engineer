"""Predeclared rolling calibration and execution-assumption sensitivity."""
import gzip,json,subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from prepare import ROOT,HERE,OUT,CACHE,SLOTS,ROLES,mode
from search import main_bank,write_kernel_configs,compile_kernel,load_cycle_scores,complexity


def june_calibration():
    w=pd.read_csv(ROOT/'research/outputs/playbook_allocation_windows.csv');w=w[w.expiry_date.le('2026-06-30')]
    g=pd.read_csv(ROOT/'research/outputs/allocation_greek_context.csv.gz');g=g[g.expiry_date.le('2026-06-30')]
    schedules=np.zeros((2,2,18,4));pool=schedules.copy();caps=[]
    for u,name in enumerate(['NIFTY','SENSEX']):
        for ph,phase in enumerate(['preexpiry','expiry']):
            for slot,clock in enumerate(SLOTS):
                for r,role in enumerate(ROLES):
                    schedules[u,ph,slot,r]=mode(w[w.underlying.eq(name)&w.phase.eq(phase)&w.clock.eq(clock)]['units_'+role].dropna())
                    pool[u,ph,slot,r]=mode(w[w.phase.eq(phase)&w.clock.eq(clock)]['units_'+role].dropna())
        q=g[g.underlying.eq(name)];caps.extend([max(q.g_CE_short_units.quantile(.95),q.g_PE_short_units.quantile(.95)),(q.g_book_vega_pct_capital.abs()*200000).quantile(.95),q.g_atm_iv_pct.median()])
    values=schedules.ravel().tolist()+pool.ravel().tolist()+caps
    path=CACHE/'june_calibration.txt';path.write_text(' '.join(map(str,values)))
    (OUT/'rolling_june_calibration.json').write_text(json.dumps(dict(fit_through='2026-06-30',index_clock=schedules.tolist(),pooled_clock=pool.tolist(),caps=caps),indent=2))
    return path


def run():
    compile_kernel();cal=june_calibration();configs=main_bank()
    def work(i):
        path=CACHE/f'rolling_{i}.csv';write_kernel_configs(configs[i::4],path);output=OUT/f'rolling_june_cycle_scores_{i}.csv.gz'
        with gzip.open(output,'wt',compresslevel=3) as out,open(CACHE/f'rolling_{i}.log','w') as err:
            p=subprocess.Popen([str(CACHE/'replay'),str(CACHE/'replay.bin'),str(path),str(cal),'--until=20260731'],stdout=subprocess.PIPE,stderr=err,text=True)
            for chunk in iter(lambda:p.stdout.read(1<<20),''):out.write(chunk)
            if p.wait():raise RuntimeError('rolling replay failed')
        return output
    with ThreadPoolExecutor(max_workers=4) as pool:files=list(pool.map(work,range(4)))
    d=load_cycle_scores(files,configs);meta=json.loads((OUT/'cycle_metadata.json').read_text());d['expiry']=d.cycle_id.map({c['cycle_id']:c['expiry_date'] for c in meta})
    raw=d[d.phase.eq(2)];train=raw[raw.expiry.le('2026-06-30')].groupby('candidate_id').primary_score.mean()
    winner=int(train.sort_values(ascending=False,kind='stable').index[0]);rows=[]
    for candidate in [0,winner]:
        for period,group in [('fit_June',raw.expiry.le('2026-06-30')),('validation_July',raw.expiry.gt('2026-06-30'))]:
            q=raw[group&raw.candidate_id.eq(candidate)]
            rows.append(dict(origin='June fit -> July',period=period,candidate_id=candidate,cycles=len(q),**q[['event_macro_f1','quantity_score','inventory_score','final_score','primary_raw','primary_score']].mean().to_dict()))
    # The second origin uses the original June-July calibrated full main bank.
    full=pd.read_csv(OUT/'cycle_scores.csv.gz');full=full[full.phase.eq(2)&full.candidate_id.lt(13824)]
    fit=full[full.split.eq(0)].groupby('candidate_id').primary_score.mean();winner=int(fit.sort_values(ascending=False,kind='stable').index[0])
    for candidate in [0,winner]:
        for period,sp in [('fit_June_July',0),('validation_August',1)]:
            q=full[full.candidate_id.eq(candidate)&full.split.eq(sp)]
            rows.append(dict(origin='June-July fit -> August',period=period,candidate_id=candidate,cycles=len(q),**q[['event_macro_f1','quantity_score','inventory_score','final_score','primary_raw','primary_score']].mean().to_dict()))
    pd.DataFrame(rows).to_csv(OUT/'rolling_origin_scores.csv',index=False)
    d.to_csv(OUT/'rolling_june_cycle_scores.csv.gz',index=False,compression={'method':'gzip','mtime':0,'compresslevel':3},float_format='%.8g')
    for path in files:path.unlink()
    # Execution-latency sensitivity uses same selected controller definitions,
    # with an explicitly identified override, not a new later-selected winner.
    manifest=json.loads((OUT/'search_manifest.json').read_text());ids=manifest['trace_candidate_ids'];registry=pd.read_csv(OUT/'candidate_registry.csv')
    selected=[]
    for row in registry[registry.candidate_id.isin(ids)].itertuples():
        c=json.loads(row.configuration);c.update(id=int(row.candidate_id),latency=1);selected.append(c)
    path=CACHE/'latency_configs.csv';write_kernel_configs(selected,path)
    with gzip.open(OUT/'latency1_cycle_scores.csv.gz','wt',compresslevel=3) as out:
        p=subprocess.Popen([str(CACHE/'replay'),str(CACHE/'replay.bin'),str(path),str(CACHE/'calibration.txt')],stdout=subprocess.PIPE,text=True)
        for chunk in iter(lambda:p.stdout.read(1<<20),''):out.write(chunk)
        if p.wait():raise RuntimeError('latency sensitivity failed')
    latency=pd.read_csv(OUT/'latency1_cycle_scores.csv.gz')
    from search import with_metrics
    latency=with_metrics(latency[latency.phase.eq(2)]);base=full[full.candidate_id.isin(ids)]
    summary=[]
    for (cid,sp),g in latency.groupby(['candidate_id','split']):
        summary.append(dict(candidate_id=cid,split=sp,assumption='one-minute latency override',cycles=len(g),**g[['event_macro_f1','quantity_score','inventory_score','final_score','primary_raw']].mean().to_dict()))
    pd.DataFrame(summary).to_csv(OUT/'latency1_summary.csv',index=False)
    print('Rolling-origin and latency robustness complete')

if __name__=='__main__':run()
