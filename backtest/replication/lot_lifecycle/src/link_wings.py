"""Association layer (NOT identity): (1) wing link: each body-entry unit lot <- one wing unit lot bought within +/-15 s (decision time decoded from the h_ tag, else fill second), same right and day, optimal one-to-one assignment; confidence POSSIBLE_TIMING_ONLY (no id links them).
(2) replacement link: for lots closed by a body buy-back order (FIFO), the candidate sale order and its class from replacement_pairs.csv.gz. Both are order/lot-level associations with stated confidence; unmatched lots keep NULL links."""
from ledger import *
from scipy.optimize import linear_sum_assignment
L = pd.read_csv(f'{OUT}/lots.csv.gz'); F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv')
def dec(tag, sec):
    try: s = tag[2:]; return ((int(s[2:4]) * 3600 + int(s[4:6]) * 60 + int(s[6:8]) + int(s[8:]) / 1e6) + 19800) % 86400
    except Exception: return sec
body = L[(L.role == 'body') & (L.side == 'SHORT') & (~L.entry_unrecorded)]; wing = L[(L.role == 'wing') & (L.side == 'LONG')].copy(); wing['wt'] = [dec(t, s) for t, s in zip(wing.entry_tag, wing.entry_sec)]
links = []
for (u, e, day, cp), g in body.groupby(['index', 'expiry', 'entry_day', 'cp']):
    w = wing[(wing['index'] == u) & (wing.expiry == e) & (wing.entry_day == day) & (wing.cp == cp)]
    if not len(w): continue
    cost = np.abs(g.entry_sec.values[:, None] - w.wt.values[None, :]).astype(float); c = np.where(cost <= 15, cost, 1e9); r, k = linear_sum_assignment(c)
    for i, j in zip(r, k):
        if c[i, j] < 1e9: links.append(dict(lot_id=g.lot_id.iloc[i], wing_lot_id=w.lot_id.iloc[j], wing_link_delay_s=float(w.wt.iloc[j] - g.entry_sec.iloc[i]), wing_strike=int(w.strike.iloc[j]), wing_entry_price=float(w.entry_price.iloc[j]), wing_close_reason=w.close_reason.iloc[j], wing_link_confidence='POSSIBLE_TIMING_ONLY'))
W = pd.DataFrame(links); LK = body[['lot_id']].merge(W, on='lot_id', how='left'); LK['wing_link_confidence'] = LK.wing_link_confidence.fillna('NO_LINK_UNRESOLVED')
RP = pd.read_csv(f'{OUT}/replacement_pairs.csv.gz')[['b_tag', 's_tag', 'classification', 'delay']].rename(columns={'b_tag': 'close_tag', 's_tag': 'replacement_candidate_order_tag', 'classification': 'replacement_class', 'delay': 'replacement_delay_s'}).drop_duplicates('close_tag')
body = body.assign(close_tag=body.close_tag.astype(str)); RP['close_tag'] = RP.close_tag.astype(str); LK = LK.merge(body[['lot_id', 'close_tag']], on='lot_id', how='left').merge(RP, on='close_tag', how='left'); LK['replacement_class'] = LK.replacement_class.fillna('NOT_APPLICABLE_OR_NOT_D0'); LK.drop(columns='close_tag').to_csv(f'{OUT}/lot_links.csv.gz', index=False)
print('body short lots', len(body), ' with wing link', int(LK.wing_lot_id.notna().sum()), round(LK.wing_lot_id.notna().mean(), 3), ' median |delay| s', LK.wing_link_delay_s.abs().median(), ' wing price/body price median', (LK.wing_entry_price / body.set_index('lot_id').loc[LK.lot_id, 'entry_price'].values).median().round(4)); print('wing link share by day:', body.assign(l=LK.wing_lot_id.notna().values).groupby('entry_day').l.mean().round(2).describe()[['mean']].to_dict())
print(LK.replacement_class.value_counts().to_dict())
# lump / hedge status
print('shorts settled in cycles without D0 data (artefact):', int(((L.side == 'SHORT') & (L.close_reason == 'SETTLEMENT') & L.set_index(['index', 'expiry']).index.isin(C[~C.has_d0].set_index(['und', 'expiry']).index)).sum()))
