"""Defect E audit: independent opening book (lot engine, exact fills) vs d0_sim.start_book v1.1 and ledger net shorts -> outputs/opening_book_audit.csv"""
from opening_book import *
import d0_sim as S1
from d0common import load_events
F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv'); C = C[C.carry_in_known]; E = load_events(False); rows = []
for r in C.itertuples():
    body, wing, passive, cash = opening_book(F, r.und, r.expiry, r.d1); g = F[(F.und == r.und) & (F.expiry == r.expiry) & (F.day == r.d1)]
    net = g.assign(x=lambda z: z.sgn * z.n_lots).groupby(['cp', 'strike']).x.sum(); shorts_ledger = (-net[net < 0]).sum()
    b1, w1, p1, c1 = S1.start_book(E[(E.und == r.und) & (E.expiry == r.expiry) & (E.day == 'D-1')])
    rows.append(dict(und=r.und, expiry=r.expiry, ledger_short_net=shorts_ledger, lot_engine_body_short=sum(x[0] for L in body.values() for x in L), d0sim_v11_body_short=sum(x[0] for L in b1.values() for x in L), lot_engine_wing=sum(x[0] for L in wing.values() for x in L), d0sim_v11_wing=sum(x[0] for L in w1.values() for x in L), cash_lot=cash, cash_v11=c1))
R = pd.DataFrame(rows); R['d_body'] = R.lot_engine_body_short - R.d0sim_v11_body_short; R['cash_diff'] = R.cash_lot - R.cash_v11; R.to_csv(f'{OUT}/opening_book_audit.csv', index=False); print(len(R), 'cycles; body equal in', int((R.d_body.abs() < 1e-9).sum()), '; wings equal in', int(((R.lot_engine_wing - R.d0sim_v11_wing).abs() < 1e-9).sum()), '; max |cash diff|', round(R.cash_diff.abs().max(), 4))
