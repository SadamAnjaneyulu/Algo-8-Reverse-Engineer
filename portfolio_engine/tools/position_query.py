"""Position query on the real ledger: python3 portfolio_engine/tools/position_query.py --episode 'NIFTY|2026-06-23|CE|24300#1' [--convention FIFO|LIFO|AVG] | --oa OA:F000123 | --cp CP:F000456 | --parent 11078391
Prints the observed layer and the analytical layer separately (JSON)."""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe.lineage_set import LineageSet
from pe.generators import historical as H
ap = argparse.ArgumentParser(); ap.add_argument('--episode'); ap.add_argument('--oa'); ap.add_argument('--cp'); ap.add_argument('--parent'); ap.add_argument('--convention', default='FIFO'); a = ap.parse_args()
ins, fills, _ = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src')
out = ls.episode_view(a.episode, a.convention) if a.episode else ls.trace_forward(a.oa, a.convention) if a.oa else ls.trace_backward(a.cp, a.convention) if a.cp else ls.parent_view(a.parent)
print(json.dumps(out, indent=1, default=str))
