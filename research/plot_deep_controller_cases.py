"""Illustrative side-by-side spot/options/IV, not rule-selection evidence."""
import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'algo8-matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME',str(Path(tempfile.gettempdir())/'algo8-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from audit_strike_hedge_rules import ROOT,OUT,logs,Market


def main():
    meta=defaultdict(list)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());meta[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    index,_=logs.load_index();ctx=pd.read_csv(OUT/'allocation_greek_context.csv.gz')
    cases=[('NIFTY','2026-07-14','2026-07-13','09:16','10:05',[(24000,'CE'),(24000,'PE')],
            [('09:30','Add 24050 CE/PE'),('09:50','Cover initial CE'),('09:53','Cover initial CE'),('09:59','Cover initial CE')],
            'deep_case_nifty_side_exits','NIFTY: rising spot, CE loss covers, earlier PE retained'),
           ('SENSEX','2026-06-25','2026-06-25','13:55','14:25',[(75500,'PE'),(76600,'PE')],
            [('14:14','PE hedge 75500 to 76600'),('14:17','Another PE hedge refresh')],
            'deep_case_sensex_hedge_refresh','SENSEX: replace farther PE protection with closer PE protection')]
    for u,e,day,start,end,contracts,events,name,title in cases:
        market=Market(u,e,meta[(u,e)],index)
        fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True,layout='constrained')
        bars=[b for b in index[(u,day)] if start<=b['t'].strftime('%H:%M')<=end]
        axes[0].plot([b['t'].hour*60+b['t'].minute for b in bars],[b['close'] for b in bars],color='#264b96')
        axes[0].set_ylabel('Index close')
        for k,right in contracts:
            prices=sorted((clock,b['close']) for clock,b in market.quotes.get((day,k,right),{}).items() if start<=clock<=end)
            axes[1].plot([int(t[:2])*60+int(t[3:]) for t,p in prices],[p for t,p in prices],label=f'{k} {right}')
        axes[1].set_ylabel('Option close (₹)');axes[1].legend(loc='upper left')
        cs=ctx[(ctx.underlying==u)&(ctx.expiry_date==e)&(ctx.date==day)&(ctx.clock>=start)&(ctx.clock<=end)]
        axes[2].plot(cs.clock.str[:2].astype(int)*60+cs.clock.str[3:].astype(int),cs.g_atm_iv_pct,color='#19836a')
        axes[2].set_ylabel('Prior ATM IV (%)')
        for j,(clock,label) in enumerate(events):
            minute=int(clock[:2])*60+int(clock[3:])
            for ax in axes:ax.axvline(minute,color='#a3462a',alpha=.5,ls='--',lw=.8)
            axes[0].text(minute,.98-.16*(j%3),label,transform=axes[0].get_xaxis_transform(),rotation=0,fontsize=8,va='top')
        for ax in axes:ax.grid(alpha=.16)
        positions=axes[2].get_xticks();axes[2].set_xticks(positions,[f'{int(t)//60:02d}:{int(t)%60:02d}' for t in positions])
        axes[2].set_xlabel(f'{day}, IST. Minute candles are descriptive; event lines mark executions.')
        fig.suptitle(title)
        fig.savefig(OUT/(name+'.png'),dpi=160)
        svg=OUT/(name+'.svg');fig.savefig(svg)
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
        plt.close(fig)


if __name__=='__main__':main()
