"""Required cycles for 80/90/95% power (interpolated from the simulations) and assurance under explicit priors. Output outputs/audit/required_cycles.json"""
import os, json, numpy as np, pandas as pd
AU = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs', 'audit')
P = pd.read_csv(f'{AU}/power_sim.csv'); L = pd.read_csv(f'{AU}/power_large_n.csv'); L['effect'] = L.effect.map(lambda x: f'+{float(x):.3f}'); CF = pd.read_csv(f'{AU}/power_crossfit.csv')
def need(Ns, ps, target):
    Ns, ps = np.array(Ns, float), np.array(ps, float)
    if ps.max() < target: return None
    k = int(np.argmax(ps >= target)); return float(Ns[0]) if k == 0 else float(np.interp(target, [ps[k - 1], ps[k]], [Ns[k - 1], Ns[k]]))
out = {}
for scen in ('exact', 'burnin'):
    for meth in ('lin', 'boot'):
        for eff in ('+0.098', '+0.075', '+0.050', '+0.025'):
            d = P[(P.scenario == scen) & (P.method == meth) & (P.design == 'fixed') & (P.effect == eff)].sort_values('N_or_maxN'); Ns, ps = list(d.N_or_maxN), list(d.rejection_rate)
            if scen == 'exact' and meth == 'lin' and eff in ('+0.050', '+0.025'): e = L[L.effect == eff].sort_values('N'); Ns += list(e.N); ps += list(e.power); o = np.argsort(Ns); Ns = list(np.array(Ns)[o]); ps = list(np.array(ps)[o])
            out[f'{scen}|{meth}|{eff}'] = {f'{int(t * 100)}%': need(Ns, ps, t) for t in (0.8, 0.9, 0.95)}
# power of the pre-registered K=2 design and assurance
def pw(scen, meth, design, eff):
    if scen == 'crossfit': d = CF[(CF.method == meth) & (CF.design == design) & (CF.effect == eff)]
    else: d = P[(P.scenario == scen) & (P.method == meth) & (P.design == design) & (P.effect == eff)]
    return float(d.rejection_rate.iloc[0])
priors = {'equal weights on {0,.025,.05,.075,.098}': {'0.000': .2, '+0.025': .2, '+0.050': .2, '+0.075': .2, '+0.098': .2}, 'skeptical {0:.30,.025:.25,.05:.20,.075:.15,.098:.10}': {'0.000': .30, '+0.025': .25, '+0.050': .20, '+0.075': .15, '+0.098': .10}, 'very skeptical {0:.50,.025:.25,.05:.15,.075:.07,.098:.03}': {'0.000': .50, '+0.025': .25, '+0.050': .15, '+0.075': .07, '+0.098': .03}}
out['assurance'] = {}
for scen in ('exact', 'crossfit'):
    for design in ('pocock2', 'pocock3'):
        for pn, w in priors.items(): out['assurance'][f'{scen}|{design}|{pn}'] = float(sum(w[e] * pw(scen, 'lin', design, e) for e in w))
out['K2_power'] = {f'{scen}|{meth}|{e}': pw(scen, meth, 'pocock2', e) for scen in ('exact', 'crossfit', 'burnin') for meth in ('lin', 'boot') for e in ('+0.098', '+0.075', '+0.050', '+0.025', '0.000')}
json.dump(out, open(f'{AU}/required_cycles.json', 'w'), indent=1); 
for k, v in out.items():
    if k not in ('K2_power',): print(k, v if not isinstance(v, dict) else {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()})
