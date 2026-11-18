"""Small European Black model for explicit, approximate attribution studies."""
import itertools
import math


def cdf(x):
    return .5*(1+math.erf(x/math.sqrt(2)))


def pdf(x):
    return math.exp(-.5*x*x)/math.sqrt(2*math.pi)


def price(forward,strike,tau,sigma,right,rate=0):
    intrinsic=max(forward-strike,0) if right=='CE' else max(strike-forward,0)
    if tau<=0 or sigma<=0:
        return math.exp(-rate*max(tau,0))*intrinsic
    vol=sigma*math.sqrt(tau)
    d1=math.log(forward/strike)/vol+vol/2
    d2=d1-vol
    undiscounted=forward*cdf(d1)-strike*cdf(d2) if right=='CE' else strike*cdf(-d2)-forward*cdf(-d1)
    return math.exp(-rate*tau)*undiscounted


def implied_vol(observed,forward,strike,tau,right,rate=0):
    if not all(math.isfinite(v) for v in (observed,forward,strike,tau,rate)) or min(forward,strike,tau)<=0:
        return None
    intrinsic=price(forward,strike,tau,0,right,rate)
    if observed-intrinsic<=.025 or observed>=math.exp(-rate*tau)*(forward if right=='CE' else strike):
        return None
    lo,hi=.0001,5.
    if price(forward,strike,tau,hi,right,rate)<observed:
        return None
    for _ in range(48):
        mid=(lo+hi)/2
        if price(forward,strike,tau,mid,right,rate)<observed:
            lo=mid
        else:
            hi=mid
    return (lo+hi)/2


def greeks(forward,strike,tau,sigma,right,rate=0):
    vol=sigma*math.sqrt(tau)
    d1=math.log(forward/strike)/vol+vol/2
    discount=math.exp(-rate*tau)
    p=price(forward,strike,tau,sigma,right,rate)
    return dict(delta=discount*(cdf(d1) if right=='CE' else -cdf(-d1)),
                gamma=discount*pdf(d1)/(forward*vol),
                vega_one_point=discount*forward*pdf(d1)*math.sqrt(tau)*.01,
                theta_calendar_day=(rate*p-discount*forward*pdf(d1)*sigma/(2*math.sqrt(tau)))/365)


def attribute(forward0,tau0,iv0,forward1,tau1,iv1,strike,right,rate=0):
    old=[forward0,tau0,iv0]
    new=[forward1,tau1,iv1]
    components=[0.,0.,0.]
    for ordering in itertools.permutations(range(3)):
        state=list(old)
        previous=price(state[0],strike,state[1],state[2],right,rate)
        for factor in ordering:
            state[factor]=new[factor]
            current=price(state[0],strike,state[1],state[2],right,rate)
            components[factor]+=(current-previous)/6
            previous=current
    result=dict(movement=components[0],time=components[1],iv=components[2])
    result['total']=price(forward1,strike,tau1,iv1,right,rate)-price(forward0,strike,tau0,iv0,right,rate)
    return result
