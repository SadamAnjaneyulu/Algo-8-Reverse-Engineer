"""MODE 3 (accounting diagnostics): replay ALL original fills through the engine's PortfolioState under the four allocation conventions.
Proves arithmetic/bookkeeping only. Checks: (1) contract-level net position after every fill equals the independent cumulative-sum path, (2) cash conservation, (3) allocation-independent cycle gross
(cash + settlement of open positions) equals the lot engine's exact gross (30 complete cycles), (4) realized + open-lot settlement P&L equals cash-based gross for every convention. NOT behavioural evidence."""
import numpy as np, pandas as pd
import ref
from exec_core import PortfolioState, OrderIntent, Fill, CONVENTIONS
from common import YAHOO
F = ref.load_fills(); R = pd.read_csv(f'{ref.REPL}/lot_lifecycle/outputs/cycle_reconciliation.csv'); rows = []
for (und, exp), g in F.groupby(['und', 'expiry']):
    g = g.sort_values(['t', 'row']); u = ref.LOT[und]; S0 = YAHOO[und].close.get(pd.Timestamp(exp), np.nan); indep = g.groupby(['cp', 'strike']).sgn_lots.sum().to_dict()
    ledger_cash = float((-g.sgn * g.qty_fill * g.px).sum())
    for conv in CONVENTIONS:
        P = PortfolioState(None, u, conv); path_ok = True; running = {}
        for r in g.itertuples():
            for _ in range(int(r.n_lots)):
                it = OrderIntent(module=r.module, rule_id='replay', evidence='CONFIRMED_OBSERVATION', day=int(r.dayno), j=int(min(max(r.j, 0), 374)), right=r.cp, si=int(r.strike), side=int(r.sgn), role=r.role, tag=r.tag, teacher_forced=True, price=float(r.px))
                P.apply_external(Fill(it, float(r.px), float(r.px)))
            running[(r.cp, r.strike)] = running.get((r.cp, r.strike), 0) + r.sgn_lots
            if P.net.get((r.cp, r.strike), 0) != running[(r.cp, r.strike)]: path_ok = False
        net_ok = {k: v for k, v in P.net.items() if v != 0} == {k: v for k, v in indep.items() if v != 0}
        settle = 0.0; open_pnl = 0.0
        for L in P.lots:
            iv = max(S0 - L['si'], 0) if L['right'] == 'CE' else max(L['si'] - S0, 0); sv = (1 if L['side'] == 1 else -1) * u * iv; settle += sv; open_pnl += L['side'] * (iv - L['entry']) * u
        gross_cash = P.cash + settle; gross_lots = P.realized + open_pnl
        rec = R[(R.und == und) & (R.expiry == exp)].iloc[0]
        rows.append(dict(und=und, expiry=exp, convention=conv, fills=len(g), path_equal_after_every_fill=path_ok, final_net_equal=net_ok, cash_equals_ledger=abs(P.cash - ledger_cash) < 0.01, gross_cash_based=gross_cash, gross_lot_based=gross_lots, identity_residual=gross_cash - gross_lots,
                         lot_engine_gross=rec.reconstructed_gross_exact, diff_vs_lot_engine=gross_cash - rec.reconstructed_gross_exact, carry_in_known=bool(rec.carry_in_known), open_lots=len(P.lots)))
M = pd.DataFrame(rows); M.to_csv(f'{ref.OUT}/mode3_accounting_replay.csv', index=False)
print(len(M), 'cycle x convention rows'); print('path equal after every fill:', M.path_equal_after_every_fill.all(), '| final net equal:', M.final_net_equal.all(), '| cash == ledger:', M.cash_equals_ledger.all())
print('max |identity residual| (cash-based vs realized+open):', M.identity_residual.abs().max().round(6)); k = M[M.carry_in_known]; print('30 complete cycles: max |gross - lot engine gross|:', k.diff_vs_lot_engine.abs().max().round(4))
print('gross identical across conventions:', (M.groupby(['und', 'expiry']).gross_cash_based.nunique() == 1).all())
