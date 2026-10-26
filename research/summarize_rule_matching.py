"""Combine completed rule searches and draw an observed execution example."""
import argparse
import csv
import json
import os
from datetime import datetime,timedelta

from audit_strike_hedge_rules import OUT,logs,write


def load(name):return json.loads((OUT/name).read_text())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plot',action='store_true');args=p.parse_args()
    association=load('rule_match_association_summary.json');mass=load('rule_match_mass_summary.json')
    fast=load('rule_match_fast_indicator_summary.json');short=load('rule_match_short_strike_summary.json')
    hedge=load('rule_match_hedge_summary.json');carry=load('rule_match_carry_contract_summary.json');ratio=load('rule_match_leg_ratio_summary.json')
    comparisons=dict(indicator_contexts=mass['indicator_scan']['calibration_comparisons'],
        faster_indicator_contexts=fast['calibration_comparisons'],short_strike_contexts=short['parameter_rows'],
        hedge_selectors=hedge['calibration_parameter_rows'],portfolio_exit_contexts=mass['exit_scan']['parameter_comparisons'],
        carried_contract_contexts=carry['parameter_comparisons'],hedge_leg_ratio_contexts=ratio['parameter_comparisons'])
    links=list(csv.DictReader((OUT/'rule_match_hedge_short_links.csv').open()));trace=[]
    for r in csv.DictReader((OUT/'rule_match_short_hedge_associations.csv').open()):
        if r['underlying']!='NIFTY' or r['date']!='2026-07-13':continue
        selected=[p for p in links if p['event_id']==r['event_id'] and float(p['nearest_short_parent_distance_seconds'])<=5]
        trace.append(dict(event_time_ist=r['start_ist'],short_strikes=r['paired_strikes'],short_ce_quantity=r['new_short_ce'],short_pe_quantity=r['new_short_pe'],
            nearby_fresh_ce_wings=';'.join(sorted({p['long_strike'] for p in selected if p['option_type']=='CE'})),
            nearby_fresh_pe_wings=';'.join(sorted({p['long_strike'] for p in selected if p['option_type']=='PE'})),source_rows=r['source_rows']))
    write('rule_match_example_13_july.csv',trace)
    summary=dict(calibration_comparisons=comparisons,total_comparisons=sum(comparisons.values()),
        distinct_indicator_predicates=mass['indicator_scan']['distinct_indicator_predicates'],
        normal_minute_opportunities=mass['minute_opportunities'],faster_minute_opportunities=fast['minute_opportunities'],
        interpretation='Execution-rule matching, not independently validated original code or an economic alpha backtest.',
        intraday_associations=[r for r in association['groups'] if r['cohort']=='intraday_0918_1445'],
        short_strike_candidates=[r for r in short['selected_comparisons'] if r['kind']=='selected'],
        hedge_ratio_candidates=[r for r in ratio['selected_comparisons'] if r['reference']=='atm_leg'])
    (OUT/'rule_match_overview.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(calibration_comparisons=comparisons,total=sum(comparisons.values())),indent=2))
    if args.plot:plot(summary)


def plot(summary):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/algo8-matplotlib');os.environ.setdefault('XDG_CACHE_HOME','/tmp/algo8-font-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    index,_=logs.load_index();bars=[r for r in index[('NIFTY','2026-07-13')] if r['t'].strftime('%H:%M')<'14:45']
    fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    axs[0].plot([r['t'] for r in bars],[r['close'] for r in bars],color='#7b8794',linewidth=1,label='Spot minute close')
    events=[r for r in csv.DictReader((OUT/'rule_match_short_strike_inputs.csv').open()) if r['underlying']=='NIFTY' and r['event_time_ist'][:10]=='2026-07-13']
    for cohort,color,marker,title in [('scheduled','#087e8b','o','Scheduled short pairs'),('off_quarter','#c65d21','^','Extra short pairs')]:
        rs=[r for r in events if r['cohort']==cohort]
        axs[0].scatter([datetime.fromisoformat(r['event_time_ist']) for r in rs],[int(r['strike']) for r in rs],s=30,color=color,marker=marker,label=title,zorder=3)
    axs[0].xaxis.set_major_locator(dates.HourLocator());axs[0].xaxis.set_major_formatter(dates.DateFormatter('%H:%M',tz=logs.IST))
    axs[0].set(title='13 July NIFTY: later sales change strike',xlabel='Time, IST',ylabel='Index / sold strike')
    axs[0].legend(fontsize=8,loc='upper left');axs[0].grid(alpha=.15)
    rs=summary['intraday_associations'];labels=[];rates=[];notes=[]
    for r in rs:
        labels.append(r['underlying']+' '+('pre-expiry' if r['phase']=='preexpiry' else 'expiry'))
        rates.append(100*r['both_fresh_outward_buys_within_5s']/r['paired_batches'])
        notes.append(f"{r['both_fresh_outward_buys_within_5s']}/{r['paired_batches']}")
    axs[1].barh(labels,rates,color=['#087e8b' if 'pre-expiry' in s else '#c65d21' for s in labels])
    for i,(rate,note) in enumerate(zip(rates,notes)):axs[1].text(rate-1,i,f'{rate:.1f}% ({note})',va='center',ha='right',color='white',fontsize=9)
    axs[1].set(xlim=(0,100),xlabel='% of paired short batches, 09:18–14:45',title='Fresh outward CE and PE buys within 5 seconds')
    fig.suptitle('Observed orders: changing short strikes and nearby fresh protection',fontsize=12)
    fig.savefig(OUT/'rule_match_evidence.png',dpi=150);fig.savefig(OUT/'rule_match_evidence.svg')
    svg=OUT/'rule_match_evidence.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':main()
