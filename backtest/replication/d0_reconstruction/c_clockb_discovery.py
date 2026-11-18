"""DISCOVERY ONLY. Clock-B ticks: (1) which ticks act, (2) which contract is bought back, (3) what is sold after. Single-criterion rules only (no fitted models)."""
from scipy.stats import rankdata
from d0common import *
S = pd.read_csv(f'{RES}/clockb_snapshots.csv'); S = S[S.split == 'DISCOVERY'].copy()
if not S.empty and (S.split == 'HOLDOUT').any(): raise SystemExit('holdout leaked')
S['itm'] = ((S.cp == 'CE') & (S.off_steps < 0)) | ((S.cp == 'PE') & (S.off_steps > 0)); S['absoff'] = S.off_steps.abs(); S['gam'] = S.lots * np.exp(-0.5 * (S.off_steps / 1.5) ** 2)
T = S.groupby(['und', 'expiry', 'tick_min']).agg(acted=('tick_acted', 'first'), spot=('spot', 'first'), lots=('lots', 'sum'), n=('n_contracts', 'first'), lotsCE=('book_short_CE', 'first'), lotsPE=('book_short_PE', 'first'), itm_lots=('lots', lambda x: x[S.loc[x.index, 'itm']].sum()), far_lots=('lots', lambda x: x[S.loc[x.index, 'absoff'] >= 2].sum()), maxabsoff=('absoff', 'max'), wing=('wing_long_CE', 'first'), upnl=('upnl', 'sum'), bought=('tick_bought_lots', 'first')).reset_index().sort_values(['und', 'expiry', 'tick_min'])
T['skew'] = (T.lotsCE - T.lotsPE).abs(); T['itm_share'] = T.itm_lots / T.lots; T['far_share'] = T.far_lots / T.lots; T['dspot_steps'] = T.groupby(['und', 'expiry']).spot.diff() / np.where(T.und == 'NIFTY', 50, 100); T['absdspot'] = T.dspot_steps.abs(); T['hours_left'] = (15.5 * 60 - T.tick_min) / 60
# distance of spot from the spot at the last acting tick
last = {}; ds = []
for r in T.itertuples():
    k = (r.und, r.expiry); ds.append(abs(r.spot - last[k]) / (50 if r.und == 'NIFTY' else 100) if k in last else np.nan)
    if r.acted: last[k] = r.spot
T['dist_from_last_act_steps'] = ds
def auc(x, y):
    m = x.notna(); x, y = x[m], y[m].astype(bool)
    if y.sum() == 0 or (~y).sum() == 0: return np.nan
    r = rankdata(x); n1 = y.sum(); return (r[y.values].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1))
rows = [dict(feature=f, auc_tick_acts=auc(T[f], T.acted), mean_acted=T[T.acted][f].mean(), mean_not=T[~T.acted][f].mean()) for f in ['lots', 'n', 'skew', 'itm_share', 'far_share', 'maxabsoff', 'upnl', 'absdspot', 'dist_from_last_act_steps', 'hours_left', 'wing']]
A = pd.DataFrame(rows).sort_values('auc_tick_acts', ascending=False); A.to_csv(f'{RES}/c1_tick_acts_auc_discovery.csv', index=False); print('ticks', len(T), 'acted', T.acted.mean().round(3)); print(A.round(3).to_string(index=False))
# (2) contract choice at acting ticks
Ac = S[S.tick_acted].copy(); rows = []
crit = {'most lots': 'lots', 'largest |offset|': 'absoff', 'most ITM (signed)': None, 'highest price/cheapest': 'ratio_cheapest', 'worst upnl (most negative)': 'neg_upnl', 'largest gamma proxy': 'gam', 'highest premium': 'price', 'lowest price/avg entry': 'neg_ratio_avg'}
Ac['neg_upnl'] = -Ac.upnl; Ac['neg_ratio_avg'] = -Ac.ratio_avg; Ac['signed_itm'] = np.where(Ac.cp == 'CE', -Ac.off_steps, Ac.off_steps); crit['most ITM (signed)'] = 'signed_itm'
for name, col in crit.items():
    hit = []; hit3 = []
    for k, g in Ac.groupby(['und', 'expiry', 'tick_min']):
        if g.bought_lots.sum() == 0: continue
        gg = g.sort_values(col, ascending=False); hit.append(gg.iloc[0].bought_lots > 0); hit3.append((gg.head(3).bought_lots > 0).any())
    rows.append(dict(criterion=name, hit_at_1=np.mean(hit), hit_at_3=np.mean(hit3), ticks=len(hit)))
rnd = np.mean([ (1 / g.shape[0]) * (g.bought_lots > 0).sum() for k, g in Ac.groupby(['und', 'expiry', 'tick_min']) if g.bought_lots.sum() > 0]); rows.append(dict(criterion='RANDOM (expected)', hit_at_1=rnd, hit_at_3=np.nan, ticks=len(hit)))
C = pd.DataFrame(rows).sort_values('hit_at_1', ascending=False); C.to_csv(f'{RES}/c2_contract_choice_discovery.csv', index=False); print(C.round(3).to_string(index=False))
# bought-back contract characteristics vs candidates (acting ticks)
print(Ac.assign(b=Ac.bought_lots > 0).groupby('b')[['absoff', 'lots', 'ratio_cheapest', 'ratio_avg', 'price']].mean().round(2)); print('bought share ITM', Ac[Ac.bought_lots > 0].itm.mean().round(3), 'candidates ITM', Ac.itm.mean().round(3)); print('lots bought per bought contract', Ac[Ac.bought_lots > 0].bought_lots.describe().round(2).to_dict())
T.to_csv(f'{RES}/c1_ticks_discovery.csv', index=False)
