"""Decision-level agreement: simulated (R1/R2) vs actual Algo 8 decisions on the 35 live cycles. Matching is count-based (a simulated order is 'matched' if the live ledger contains an unmatched order of the same category inside the tolerance window)."""
from common import *
S = pd.read_csv(f'{RES}/replay_sim_events.csv'); E = pd.read_csv(f'{RES}/live_decision_events.csv')
E['d'] = np.where(E.day == 'D-1', 0, 1); E['slot'] = (E.minute - 1) // 15; E['off'] = (E.minute - 1) % 15
S['slot'] = (S.j - 1) // 15; S['cp'] = S.right
live_b = E[(E.tp == 'num') & (E.side == 'Sell')]; live_w = E[(E.tp == 'h_') & (E.side == 'Buy')]; live_bb = E[(E.tp == 'num') & (E.side == 'Buy')]; live_ws = E[(E.tp == 'h_') & (E.side == 'Sell')]
out = []
def agree(cat, sim, live, keys, tol=None, v='R1', d=None):
    """count-matching on keys; live rows weighted by lots (1 lot units)"""
    sc = sim.groupby(keys).size().rename('s'); lc = live.groupby(keys).lots.sum().round().rename('l')
    m = pd.concat([sc, lc], axis=1).fillna(0); mt = np.minimum(m.s, m.l).sum()
    out.append(dict(variant=v, category=cat, sim_orders=int(m.s.sum()), live_lots=int(m.l.sum()), matched=int(mt), precision=mt / m.s.sum() if m.s.sum() else np.nan, recall=mt / m.l.sum() if m.l.sum() else np.nan))
for v in ('R1', 'R2'):
    sv = S[S.variant == v]
    sb1 = sv[(sv.role == 'body') & (sv.tag == 'ENTRY') & (sv.d == 0)]; lb1 = live_b[(live_b.d == 0) & (live_b.off < 3)]
    # slot+side only (timing & quantity), then slot+side+strike (contract)
    agree('D-1 body entries: slot x right', sb1, lb1, ['und', 'expiry', 'slot', 'cp'], v=v)
    agree('D-1 body entries: slot x right x strike', sb1, lb1, ['und', 'expiry', 'slot', 'cp', 'strike'], v=v)
    sw1 = sv[(sv.role == 'wing') & (sv.tag == 'ENTRY') & (sv.d == 0)]; lw1 = live_w[(live_w.d == 0) & (live_w.off < 3)]
    agree('D-1 wing entries: slot x right', sw1, lw1, ['und', 'expiry', 'slot', 'cp'], v=v)
    agree('D-1 wing entries: slot x right x strike', sw1, lw1, ['und', 'expiry', 'slot', 'cp', 'strike'], v=v)
    # D-1 leg stop buy-backs: match on cycle,cp,strike and 5-min bucket
    sl1 = sv[(sv.role == 'body') & (sv.tag == 'LEG_STOP') & (sv.d == 0)].assign(bk=lambda x: x.j // 5); ll1 = live_bb[live_bb.d == 0].assign(bk=lambda x: x.minute // 5)
    agree('D-1 body buy-backs (leg stop): cycle x right x strike x 5-min', sl1, ll1, ['und', 'expiry', 'cp', 'strike', 'bk'], v=v)
    agree('D-1 body buy-backs: cycle x right (count only)', sl1, ll1, ['und', 'expiry', 'cp'], v=v)
    sl0 = sv[(sv.role == 'body') & (sv.tag.isin(['LEG_STOP', 'FLATTEN', 'CYCLE_STOP'])) & (sv.d == 1)].assign(bk=lambda x: x.j // 5); ll0 = live_bb[live_bb.d == 1].assign(bk=lambda x: x.minute // 5)
    agree('D0 body buy-backs: cycle x right (count only)', sl0, ll0, ['und', 'expiry', 'cp'], v=v)
    agree('D0 body buy-backs: cycle x right x strike', sl0, ll0, ['und', 'expiry', 'cp', 'strike'], v=v)
    agree('D0 body buy-backs: cycle x right x 5-min bucket', sl0, ll0, ['und', 'expiry', 'cp', 'bk'], v=v)
    sb0 = sv[(sv.role == 'body') & (sv.tag == 'ENTRY') & (sv.d == 1)]; lb0 = live_b[(live_b.d == 0) | (live_b.d == 1)][lambda x: x.d == 1]
    agree('D0 body sells: cycle x right (count only)', sb0, lb0, ['und', 'expiry', 'cp'], v=v)
A_ = pd.DataFrame(out); A_.to_csv(f'{RES}/decision_agreement.csv', index=False); pd.set_option('display.width', 250); print(A_.round(3).to_string(index=False))
# quantities: overnight carried lots
def carried_live(): 
    x = E[(E.d == 0) & (E.tp.isin(['num']))].assign(sgn=lambda x: np.where(x.side == 'Sell', -1, 1)).groupby(['und', 'expiry']).apply(lambda g: -(g.sgn * g.lots).sum()); return x
cl_ = carried_live().rename('live_net_short_lots_overnight_body')
for v in ('R1', 'R2'):
    sv = S[(S.variant == v) & (S.d == 0) & (S.role == 'body')].assign(sg=lambda x: -x.side)
    sim_ = sv.groupby(['und', 'expiry']).sg.sum().rename('sim_net_short_lots_overnight_body'); t = pd.concat([cl_, sim_], axis=1).fillna(0); print(v, 'overnight net short body lots: live mean', t.iloc[:, 0].mean().round(1), 'sim mean', t.iloc[:, 1].mean().round(1), 'corr', np.corrcoef(t.iloc[:, 0], t.iloc[:, 1])[0, 1].round(2))
    t.to_csv(f'{RES}/overnight_lots_{v}.csv')
