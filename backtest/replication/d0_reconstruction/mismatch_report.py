"""Event-level mismatch report (V1, v1.1 simulator) + cycle-level bootstrap CIs of key agreement metrics."""
from d0common import *
E = load_events(False); rng = np.random.default_rng(2); S_ = pd.read_csv(f'{RES}/cycle_status.csv'); out = []; boot = []
def l2(sim, act):
    k = ['cp', 'b2']; s = sim.groupby(k).lots.sum(); a = act.groupby(k).lots.sum(); m = pd.concat([s, a], axis=1).fillna(0); m.columns = ['s', 'a']; return np.minimum(m.s, m.a).sum(), m.s.sum(), m.a.sum()
for sp in ('DISCOVERY', 'HOLDOUT'):
    ok = S_[(S_.split == sp) & S_.carry_in_known][['und', 'expiry']]; O = pd.read_csv(f'{RES}/replay_orders_{sp}_V1.csv').merge(ok, on=['und', 'expiry']); A = E[(E.day == 'D0') & (E.module == 'num')].merge(ok, on=['und', 'expiry']); A['j'] = A.sec // 60 - 555; A['b2'] = A.j // 2; O['b2'] = O.j // 2; O['cp'] = O.cp
    O = O[O.role == 'body']
    for r in A.itertuples():
        if r.event_class in ('UNCLASSIFIED', 'POSITION_REDUCTION_OF_LONG'): continue
        side = -1 if r.side == 'Sell' else 1; s = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.cp == r.cp) & (O.side == side)]
        if not len(s): lab = 'MISSING_RULE_or_missing_state'; dt = np.nan
        else:
            d = (s.j - r.j).abs(); i = d.idxmin(); dt = d.min(); same_strike = s.loc[i, 'strike'] == r.strike
            lab = 'L1_exact' if dt <= 2 and same_strike else ('L2_strike_mismatch' if dt <= 2 else ('L3_timing_mismatch' if dt <= 10 else 'MISSING_RULE_or_missing_state'))
        out.append(dict(split=sp, und=r.und, expiry=r.expiry, tag=r.tag, actual_class=r.event_class, side=r.side, cp=r.cp, strike=r.strike, lots=r.lots, minute=r.j, label=lab, nearest_sim_dt_min=dt))
    # cycle bootstrap for key categories
    for lab, simf, actf in (('scheduled sales', lambda o: o[o.cls == 'SCHEDULED_SALE'], lambda a: a[a.event_class == 'SCHEDULED_SALE']), ('final liquidation', lambda o: o[o.cls == 'FINAL_LIQUIDATION'], lambda a: a[a.event_class == 'FINAL_LIQUIDATION']), ('price-stop-like buybacks', lambda o: o[o.cls == 'PRICE_STOP_BUYBACK'], lambda a: a[(a.event_class == 'BUYBACK') & (a.ratio_cheapest >= 1.55)])):
        per = []
        for (u, e), g in ok.groupby(['und', 'expiry']): per.append(l2(simf(O[(O.und == u) & (O.expiry == e)]), actf(A[(A.und == u) & (A.expiry == e)])))
        per = np.array(per); P = lambda x: x[:, 0].sum() / x[:, 1].sum() if x[:, 1].sum() else np.nan; R = lambda x: x[:, 0].sum() / x[:, 2].sum() if x[:, 2].sum() else np.nan
        bs = [per[rng.integers(0, len(per), len(per))] for _ in range(4000)]; pb = np.nanpercentile([P(b) for b in bs], [2.5, 97.5]); rb = np.nanpercentile([R(b) for b in bs], [2.5, 97.5])
        boot.append(dict(split=sp, category=lab, cycles=len(per), L2_precision=P(per), p_lo=pb[0], p_hi=pb[1], L2_recall=R(per), r_lo=rb[0], r_hi=rb[1]))
M = pd.DataFrame(out); M.to_csv(f'{RES}/mismatch_events_V1.csv', index=False); B = pd.DataFrame(boot); B.to_csv(f'{RES}/bootstrap_agreement_V1.csv', index=False); pd.set_option('display.width', 250)
t = M.groupby(['split', 'actual_class', 'label']).agg(orders=('lots', 'size'), lots=('lots', 'sum')).reset_index(); t['share_of_class_lots'] = t.lots / t.groupby(['split', 'actual_class']).lots.transform('sum'); t.to_csv(f'{RES}/mismatch_summary_V1.csv', index=False)
print(t[t.split == 'HOLDOUT'].pivot(index='actual_class', columns='label', values='share_of_class_lots').round(2).fillna(0).to_string()); print(B.round(3).to_string(index=False))
