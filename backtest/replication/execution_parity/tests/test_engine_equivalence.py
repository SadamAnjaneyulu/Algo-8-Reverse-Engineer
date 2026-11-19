"""The refactored event-driven core must reproduce the stored R1/R2 simulator event by event (same decisions, same fills)."""
import os, sys, pytest, numpy as np, pandas as pd
REPL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, REPL)
CACHE = os.path.join(REPL, 'cache')
pytestmark = pytest.mark.skipif(not os.path.isdir(CACHE), reason='per-cycle cache absent')


def _cycle(und, e):
    import sim, data, runner
    from bt import cycles as Cy
    cl = Cy.cycle_list(); m = cl[(cl.und == und) & (cl.expiry == e)].iloc[0]; return data.load_cycle(und, e, m.d1, m.d0), sim, runner


@pytest.mark.parametrize('und,e', [('NIFTY', '2026-07-14'), ('SENSEX', '2026-09-24'), ('NIFTY', '2026-10-13')])
@pytest.mark.parametrize('variant', ['R1', 'R2'])
def test_matches_legacy_simulator(und, e, variant):
    c, sim, runner = _cycle(und, e); d0l = sim.d0_median_ladder(); old = sim.simulate(c, runner.LOT[und], variant, d0l); loop = runner.build(c, und, variant, d0l).run(); ev = runner.events(loop)
    O = pd.DataFrame(old['events']); assert len(O) == len(ev) > 0
    for col in ('d', 'j', 'right', 'strike', 'side', 'role', 'tag'): assert (O[col].values == ev[col].values).all(), col
    assert np.allclose(O.px.values, ev.px.values, equal_nan=True) and np.allclose(O.ref.values, ev.ref.values, equal_nan=True)
    assert abs(old['gross'] - loop.gross_pnl()) < 1e-6 and (old['stopped'] is None) == (loop.stopped is None)
