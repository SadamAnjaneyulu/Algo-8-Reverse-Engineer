"""Event-by-event equality of the refactored core with replication/sim.py on ALL live cycles (R1 and R2)."""
import sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import ref
sys.path.insert(0, ref.REPL)
import sim, data, runner
from bt import cycles as Cy
cl = Cy.cycle_list(); cyc = pd.read_csv(ref.CYCLES); d0l = sim.d0_median_ladder(); rows = []
for r in cyc.itertuples():
    m = cl[(cl.und == r.und) & (cl.expiry == r.expiry)].iloc[0]; c = data.load_cycle(r.und, r.expiry, m.d1, m.d0)
    for v in ('R1', 'R2'):
        old = sim.simulate(c, runner.LOT[r.und], v, d0l); lp = runner.build(c, r.und, v, d0l).run(); ev = runner.events(lp); O = pd.DataFrame(old['events']); same = len(O) == len(ev)
        if same:
            for col in ('d', 'j', 'right', 'strike', 'side', 'role', 'tag'): same &= bool((O[col].values == ev[col].values).all())
            same &= bool(np.allclose(O.px.values, ev.px.values, equal_nan=True))
        rows.append(dict(und=r.und, expiry=r.expiry, variant=v, events_legacy=len(O), events_core=len(ev), identical=bool(same), gross_diff=abs(old['gross'] - lp.gross_pnl())))
D = pd.DataFrame(rows); D.to_csv(f'{ref.OUT}/engine_equivalence_all_cycles.csv', index=False); print(len(D), 'cycle x variant;', 'identical:', int(D.identical.sum()), '; max |gross diff|:', D.gross_diff.max())
