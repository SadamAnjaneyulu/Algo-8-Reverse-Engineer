"""Intraday indicators with explicit warm-up; each output uses only its prefix.

No volume-weighted index indicator is fabricated from the cash index OHLC data.
Wilder series reset on a missing input; callers split discontinuous sessions.
"""
import math
import numpy as np


def smooth(values,period,alpha=None):
    alpha=1/period if alpha is None else alpha
    result=np.full(len(values),np.nan);seed=[];last=None
    for i,value in enumerate(values):
        if not math.isfinite(value):seed=[];last=None;continue
        if last is None:
            seed.append(value)
            if len(seed)<period:continue
            last=sum(seed)/period
        else:last=alpha*value+(1-alpha)*last
        result[i]=last
    return result


def rolling(values,period,kind):
    out=np.full(len(values),np.nan)
    for i in range(period-1,len(values)):
        x=values[i-period+1:i+1]
        if np.isfinite(x).all():out[i]={'mean':np.mean,'std':np.std,'max':np.max,'min':np.min}[kind](x)
    return out


def supertrend(close,high,low,atr,multiplier):
    direction=np.full(len(close),np.nan);line=np.full(len(close),np.nan)
    upper=lower=None;previous=1
    for i in range(len(close)):
        if not np.isfinite(atr[i]):upper=lower=None;continue
        bu=(high[i]+low[i])/2+multiplier*atr[i]
        bl=(high[i]+low[i])/2-multiplier*atr[i]
        if upper is None:upper,lower=bu,bl;previous=1
        else:
            upper=bu if bu<upper or close[i-1]>upper else upper
            lower=bl if bl>lower or close[i-1]<lower else lower
            previous=(-1 if close[i]<lower else 1) if previous>0 else (1 if close[i]>upper else -1)
        direction[i]=previous;line[i]=lower if previous>0 else upper
    return direction,line


def indicator_arrays(bars,previous_close=None):
    """Arrays aligned to bar start. A completed bar is required by the caller."""
    c=np.array([b['close'] for b in bars]);h=np.array([b['high'] for b in bars]);l=np.array([b['low'] for b in bars])
    n=len(c);out={}
    if not n:return out
    change=np.r_[np.nan,np.diff(c)];up=np.maximum(change,0);down=np.maximum(-change,0)
    tr=np.maximum(h-l,np.maximum(abs(h-np.r_[np.nan,c[:-1]]),abs(l-np.r_[np.nan,c[:-1]])))
    tr[0]=h[0]-l[0]
    atrs={p:smooth(tr,p) for p in (5,7,10,14,20,21,28,30)}
    for p in (5,7,10,14,21,28):
        gain,loss=smooth(up,p),smooth(down,p)
        r=np.full(n,np.nan);valid=np.isfinite(gain)&np.isfinite(loss)
        r[valid]=50
        positive=valid&(loss>0);r[positive]=100-100/(1+gain[positive]/loss[positive])
        r[valid&(loss==0)&(gain>0)]=100
        out[f'rsi_{p}']=r;out[f'rsi_neutral_distance_{p}']=abs(r-50)
    emas={p:smooth(c,p,2/(p+1)) for p in (3,5,8,9,12,15,20,21,26,30,50,100)}
    for fast in (3,5,8,9,12,20):
        for slow in (15,20,21,26,30,50,100):
            if fast<slow:out[f'ema_gap_{fast}_{slow}']=100*(emas[fast]-emas[slow])/c
    for p in (10,20,30,50):
        avg,std=rolling(c,p,'mean'),rolling(c,p,'std')
        z=np.divide(c-avg,std,out=np.full(n,np.nan),where=std>0)
        z[np.isfinite(std)&(std==0)]=0
        out[f'bollinger_z_{p}']=z;out[f'bollinger_abs_z_{p}']=abs(z)
    for p,a in atrs.items():out[f'atr_pct_{p}']=100*a/c
    dh=np.r_[np.nan,np.diff(h)];dl=np.r_[np.nan,-np.diff(l)]
    plus=np.where((dh>dl)&(dh>0),dh,0.);minus=np.where((dl>dh)&(dl>0),dl,0.)
    plus[0]=minus[0]=np.nan
    for p in (7,14,21,28):
        a=atrs[p]
        positive=np.divide(100*smooth(plus,p),a,out=np.full(n,np.nan),where=a>0)
        negative=np.divide(100*smooth(minus,p),a,out=np.full(n,np.nan),where=a>0)
        den=positive+negative
        dx=np.divide(100*abs(positive-negative),den,out=np.full(n,np.nan),where=den>0)
        dx[np.isfinite(den)&(den==0)]=0
        out[f'adx_{p}']=smooth(dx,p)
    for p in (7,10,14):
        for mult in (1,1.5,2,2.5,3):
            direction,line=supertrend(c,h,l,atrs[p],mult)
            out[f'supertrend_direction_{p}_{mult}']=direction
    for p in (5,10,15,20,30,60):
        hi=np.r_[np.nan,rolling(h,p,'max')[:-1]];lo=np.r_[np.nan,rolling(l,p,'min')[:-1]]
        valid=np.isfinite(hi)&np.isfinite(lo)
        dc=np.full(n,np.nan);dc[valid]=0;dc[valid&(c>hi)]=1;dc[valid&(c<lo)]=-1
        out[f'donchian_direction_{p}']=dc
    for p in (1,3,5,10,15,30,60):
        r=np.full(n,np.nan)
        if p<n:r[p:]=100*(c[p:]/c[:-p]-1)
        out[f'spot_return_{p}']=r;out[f'spot_abs_return_{p}']=abs(r)
    out['open_to_now_pct']=100*(c/bars[0]['open']-1)
    out['twap_gap_pct']=100*(c/(np.cumsum(c)/np.arange(1,n+1))-1)
    out['opening_gap_pct']=np.full(n,100*(bars[0]['open']/previous_close-1) if previous_close else np.nan)
    return out


def predicate_grid(columns):
    """Predeclared thresholds; no evaluation-target-dependent search range."""
    result=[]
    for name in columns:
        cross=True
        if name.startswith('rsi_neutral_'):levels=range(5,36,5);cross=False
        elif name.startswith('rsi_'):levels=range(20,81,5)
        elif name.startswith('ema_gap_'):levels=(-.1,-.05,-.025,0,.025,.05,.1)
        elif name.startswith('bollinger_abs_z_'):levels=(.5,1,1.5,2,2.5,3);cross=False
        elif name.startswith('bollinger_z_'):levels=(-3,-2.5,-2,-1.5,-1,-.5,0,.5,1,1.5,2,2.5,3)
        elif name.startswith('atr_pct_'):levels=(.01,.02,.03,.04,.05,.075,.1,.15,.2);cross=False
        elif name.startswith('adx_'):levels=range(10,51,5)
        elif name.startswith(('supertrend_direction_','donchian_direction_')):levels=(0,)
        elif name.startswith('spot_abs_return_'):levels=(.025,.05,.1,.15,.2,.3,.5,1);cross=False
        elif name.startswith('spot_return_') or name in ('open_to_now_pct','twap_gap_pct','opening_gap_pct'):
            levels=(-1,-.5,-.3,-.2,-.1,-.05,0,.05,.1,.2,.3,.5,1)
        elif name in ('equity_pct_capital','equity_change5_pct_capital','drawdown_pct_capital'):
            levels=(-1.5,-1.25,-1,-.75,-.5,-.4,-.3,-.2,-.1,0,.1,.2,.3,.5,.75,1,1.5)
        elif name in ('reference_iv_pct',):levels=(8,10,12,14,16,18,20,22,25,30)
        elif name in ('iv_change15_points',):levels=(-2,-1,-.5,-.25,-.1,0,.1,.25,.5,1,2)
        elif name in ('last_pair_premium_change_pct','reference_premium_change5_pct'):
            levels=(-30,-20,-15,-10,-7.5,-5,-4,-2,0,2,4,5,7.5,10,15,20,30,50)
        elif name=='last_pair_max_leg_change_pct':levels=(0,2,4,5,7.5,10,15,20,25,30,40,50,75,100)
        elif name in ('last_pair_abs_spot_gap_steps',):levels=(.25,.5,1,1.5,2,3,4,5)
        elif name in ('recent_short_covers5_units',):levels=(0,.5,1,2,3,5,10,20)
        elif name in ('time_since_last_pair_min',):levels=(1,2,3,5,10,14,15,16,20,30)
        else:continue
        for level in levels:
            for op in ('le','gt'):
                result.append((name,op,float(level),'state'))
                if cross:result.append((name,op,float(level),'cross'))
    return result
