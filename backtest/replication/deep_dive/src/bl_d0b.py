"""D0 study, parts C (management) and D (ending logic)."""
import sys; sys.path.insert(0, '.')
from bl_common import *
from scipy import stats
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); b0 = O[(O.module == 'num') & (O.dayno == 1)]; D0 = O[O.dayno == 1]
hrs = lambda x: (x.tod // 3600).astype(int)
# ---- C1 category x hour (lots)
t = b0.assign(h=hrs(b0)).groupby(['h', 'cls']).lots.sum().unstack(fill_value=0); t.to_csv(f'{OUT}/bl_d0_C_hour_class.csv'); print('C1 D0 body lots by hour x class:'); print(t.to_string())
# ---- C2 re-entry after buy-back: cover -> sell on the same right within 60 s; shuffled null (sell times shifted)
SH = [137, -211, 389, -523, 701]; cov = b0[b0.role == 'cover_short']; sell = b0[b0.role == 'open_short']; real = 0; null = np.zeros(len(SH)); tot = 0; mig = []
for (u, e, cp), c in cov.groupby(['und', 'expiry', 'cp']):
    s = sell[(sell.und == u) & (sell.expiry == e) & (sell.cp == cp)].sort_values('tt_first'); st = s.tt_first.values
    for r in c.itertuples():
        tot += r.lots; i = np.searchsorted(st, r.tt_first, side='left'); j = np.searchsorted(st, r.tt_first + 60, side='right')
        if j > i: real += r.lots; k = s.iloc[i]; mig.append((u, e, cp, r.strike, k.strike, r.spot_prev, r.step, r.tt_first, k.tt_first - r.tt_first, r.lots))
        for n_, sh_ in enumerate(SH):
            i2 = np.searchsorted(st + sh_, r.tt_first, side='left'); j2 = np.searchsorted(st + sh_, r.tt_first + 60, side='right'); null[n_] += r.lots if j2 > i2 else 0
print('C2 D0 body buy-back lots %d; followed by a sale on the same right within 60 s: %.3f ; shifted-time null (5 shifts) %.3f (range %.3f-%.3f)' % (tot, real / tot, null.mean() / tot, null.min() / tot, null.max() / tot))
M = pd.DataFrame(mig, columns=['und', 'expiry', 'cp', 'k_old', 'k_new', 'spot_prev', 'step', 'tt', 'delay', 'lots']); sgn = np.where(M.cp == 'CE', -1, 1); M['itm_old'] = sgn * (M.k_old - M.spot_prev) / M.step; M['itm_new'] = sgn * (M.k_new - M.spot_prev) / M.step; M['dk_itm'] = sgn * (M.k_new - M.k_old) / M.step
print('   roll pairs', len(M), '| same strike %.3f | new strike more ITM %.3f, more OTM %.3f | old strike ITM share %.3f | median ITM-offset old %.2f new %.2f | |offset| old %.2f new %.2f | new closer to spot %.3f' % ((M.dk_itm == 0).mean(), (M.dk_itm > 0).mean(), (M.dk_itm < 0).mean(), (M.itm_old > 0).mean(), M.itm_old.median(), M.itm_new.median(), M.itm_old.abs().median(), M.itm_new.abs().median(), (M.itm_new.abs() < M.itm_old.abs()).mean()))
Mk = M.dropna(subset=['dk_itm', 'itm_old']); print('   corr(dk, -itm_old) (does the new strike move back toward spot?) %.3f' % np.corrcoef(Mk.dk_itm, -Mk.itm_old)[0, 1]); M.to_csv(f'{OUT}/bl_d0_C_roll_pairs.csv', index=False)
# ---- C3 clock structure of D0 sells and covers (minute of hour)
for nm, X in (('sells', sell), ('covers', cov)):
    mh = ((X.tod % 3600) // 60).astype(int); share = mh.value_counts(normalize=True).sort_index(); print('C3 D0', nm, 'minute-of-hour: ', 'slot minutes (:16 :31 :46 :01) %.3f ; clock-B minutes (:14 :29 :44 :59) %.3f ; chance for 4 minutes = %.3f ; top minutes %s' % (share.reindex([16, 31, 46, 1]).sum(), share.reindex([14, 29, 44, 59]).sum(), 4 / 60, share.sort_values(ascending=False).head(6).round(3).to_dict()))
# ---- C4 buy-back hazard on the D0 contract-minute panel: single-driver AUCs (pre-registered 6 drivers), cluster bootstrap CI
P = pd.read_csv('../../lot_lifecycle/outputs/contract_minute_panel.csv.gz'); P = P[(P.lots > 0)].dropna(subset=['ratio_avg', 'off_steps', 'd_price_5m']).copy(); P['dist'] = P.off_steps.abs(); P['itm_i'] = P.itm.astype(int); P['clk'] = P.clockB.astype(int); P['mins'] = 375 - P.hours_left * 60
P['cyc'] = P.und + P.expiry; y = P.event.values.astype(int); rng = np.random.default_rng(0); res = []
def auc(x, y): r = stats.rankdata(x); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
cy = P.cyc.values; ucy = np.unique(cy); idx = {c: np.where(cy == c)[0] for c in ucy}
for nm in ('ratio_avg', 'dist', 'itm_i', 'mins', 'd_price_5m', 'clk'):
    x = P[nm].values.astype(float); a = auc(x, y); bs = []
    for _ in range(400):
        ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); yy = y[ii]
        if yy.sum() and yy.sum() < len(yy): bs.append(auc(x[ii], yy))
    p = 2 * min((np.array(bs) <= .5).mean(), (np.array(bs) >= .5).mean()); res.append((nm, a, np.quantile(bs, .025), np.quantile(bs, .975), max(p, 1 / 400)))
R = pd.DataFrame(res, columns=['driver', 'AUC', 'lo', 'hi', 'p_boot']).sort_values('p_boot'); m = len(R); R['holm_p'] = [min(1, (m - i) * p) for i, p in enumerate(R.p_boot)]; R['holm_p'] = R.holm_p.cummax(); R.round(3).to_csv(f'{OUT}/bl_d0_C_hazard_auc.csv', index=False); print('C4 hazard AUC (buy-back in the minute vs not, open D0 body-short contract-minutes) n=%d events=%d' % (len(P), y.sum())); print(R.round(3).to_string(index=False))
P['rb'] = pd.cut(P.ratio_avg, [0, .5, .8, 1, 1.2, 1.5, 1.7, 3, 20]); print('   hazard by price/entry:', P.groupby('rb').event.mean().round(4).to_dict()); P['db'] = pd.cut(P.dist, [-1, .5, 1.5, 3, 6, 100]); print('   hazard by |steps from spot|:', P.groupby('db').event.mean().round(4).to_dict())

mh_s = ((sell.tod % 3600) // 60).astype(int).value_counts(normalize=True); mh_c = ((cov.tod % 3600) // 60).astype(int).value_counts(normalize=True)
rec('d0b', dict(cover_lots=tot, roll_real=real / tot, roll_null_mean=null.mean() / tot, roll_null_min=null.min() / tot, roll_null_max=null.max() / tot, roll_pairs=len(M), same_strike=(M.dk_itm == 0).mean(), more_itm=(M.dk_itm > 0).mean(), more_otm=(M.dk_itm < 0).mean(), old_itm=(M.itm_old > 0).mean(), med_old=M.itm_old.median(), med_new=M.itm_new.median(), abs_old=M.itm_old.abs().median(), abs_new=M.itm_new.abs().median(), new_closer=(M.itm_new.abs() < M.itm_old.abs()).mean(), roll_corr=np.corrcoef(Mk.dk_itm, -Mk.itm_old)[0, 1], delay_q=M.delay.quantile([.25, .5, .75]),
  sell_slot=mh_s.reindex([16, 31, 46, 1]).sum(), sell_b=mh_s.reindex([14, 29, 44, 59]).sum(), cover_slot=mh_c.reindex([16, 31, 46, 1]).sum(), cover_b=mh_c.reindex([14, 29, 44, 59]).sum(), cover_top=mh_c.sort_values(ascending=False).head(6).round(3).to_dict(), sell_top=mh_s.sort_values(ascending=False).head(6).round(3).to_dict(), panel_n=len(P), panel_events=int(y.sum()),
  haz_ratio={str(k): float(v) for k, v in P.groupby('rb').event.mean().items()}, haz_dist={str(k): float(v) for k, v in P.groupby('db').event.mean().items()}))
