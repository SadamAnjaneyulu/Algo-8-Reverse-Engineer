"""Regenerate committed fixtures: seeded synthetic scenarios (SYNTHETIC_TEST), invalid-input fixtures, two small REAL cycles (HISTORICAL_OBSERVED_REPLAY).
python3 portfolio_engine/tools/make_fixtures.py   (reads tp_reconstruction/ read-only; writes only under portfolio_engine/fixtures)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import tsvio
from pe.schema import *
from pe.generators import synthetic as S, historical as H

SYN = os.path.join(PE, 'fixtures', 'synthetic'); BAD = os.path.join(PE, 'fixtures', 'invalid'); REAL = os.path.join(PE, 'fixtures', 'historical_sample')
for d in (SYN, BAD, REAL): os.makedirs(d, exist_ok=True)
for name, fn in S.SCENARIOS.items():
    ins, fills = fn(); note = f'SYNTHETIC_TEST fixture {name}; generator synthetic v{S.VERSION}; not Algo 8 data'
    tsvio.write_events(os.path.join(SYN, f'{name}_events.tsv'), fills, note); tsvio.write_instruments(os.path.join(SYN, f'{name}_instruments.tsv'), ins, note)
# invalid fixtures: each must be rejected by BOTH implementations, nothing partially applied
ins, fills = S.open_close_full(); tsvio.write_instruments(os.path.join(BAD, 'base_instruments.tsv'), ins)
import dataclasses as dc
def variant(name, mutate):
    f2 = mutate(list(fills)); tsvio.write_events(os.path.join(BAD, f'{name}_events.tsv'), f2, f'INVALID fixture: {name}')
variant('off_tick_price', lambda f: [dc.replace(f[0], price_paise=10003)] + f[1:])
variant('zero_quantity', lambda f: [dc.replace(f[0], quantity=0)] + f[1:])
variant('bad_side', lambda f: [dc.replace(f[0], side=2)] + f[1:])
variant('unknown_instrument', lambda f: [dc.replace(f[0], instrument_id='NIFTY|2026-01-08|CE|99999')] + f[1:])
variant('duplicate_fill_id', lambda f: [f[0], dc.replace(f[1], fill_id=f[0].fill_id)])
variant('mixed_modes', lambda f: [f[0], dc.replace(f[1], execution_mode='HISTORICAL_OBSERVED_REPLAY')])
with open(os.path.join(BAD, 'missing_column_events.tsv'), 'w') as fh: fh.write('\t'.join(EVENT_COLUMNS[:-1]) + '\n')
inv = open(os.path.join(BAD, 'base_instruments.tsv')).read().replace('\tCE\t', '\tXX\t'); open(os.path.join(BAD, 'bad_option_type_instruments.tsv'), 'w').write(inv)
# small REAL cycles (read-only from the TP-01 ledger)
for und, exp in (('NIFTY', '2026-07-14'), ('SENSEX', '2026-10-15')):
    ev, ip, src = H.write(REPO, REAL, (und, exp), name=f'{und}_{exp}'); print(ev)
