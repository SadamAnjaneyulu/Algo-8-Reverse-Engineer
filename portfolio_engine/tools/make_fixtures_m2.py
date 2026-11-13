"""Write the M2-B synthetic fixtures (separate directory so the M1 fixture set and M1 parity counts are untouched)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import tsvio
from pe.generators import synthetic_m2 as S2
D = os.path.join(PE, 'fixtures', 'synthetic_m2'); os.makedirs(D, exist_ok=True)
for name, fn in S2.M2_SCENARIOS.items():
    ins, fills = fn(); note = f'SYNTHETIC_TEST M2-B fixture {name}; not Algo 8 data'
    tsvio.write_events(os.path.join(D, f'{name}_events.tsv'), fills, note); tsvio.write_instruments(os.path.join(D, f'{name}_instruments.tsv'), ins, note)
print(len(S2.M2_SCENARIOS), 'fixtures ->', D)
