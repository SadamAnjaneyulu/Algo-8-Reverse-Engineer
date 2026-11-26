#!/usr/bin/env python3
"""Compare a C++ ledger.csv with the golden ledger produced by the Python reference. Usage: compare_ledgers.py GOLDEN.csv CPP.csv [tol]"""
import sys, csv
g = {(r['und'], r['expiry']): r for r in csv.DictReader(open(sys.argv[1]))}; c = {(r['und'], r['expiry']): r for r in csv.DictReader(open(sys.argv[2]))}; tol = float(sys.argv[3]) if len(sys.argv) > 3 else 1e-3
bad = 0; worst = 0.0
if set(g) != set(c): print('cycle sets differ'); sys.exit(1)
for k in sorted(g):
    for col in ('gross', 'slippage', 'costs', 'net', 'min_path', 'max_path'):
        d = abs(float(g[k][col]) - float(c[k][col])); worst = max(worst, d)
        if d > tol: print('MISMATCH', k, col, g[k][col], c[k][col]); bad += 1
    for col in ('n_orders', 'n_fills', 'd1_stopped', 'd0_stopped', 'stop_minute'):
        a, b = str(g[k][col]).replace('True', '1').replace('False', '0'), str(c[k][col]).replace('True', '1').replace('False', '0')
        if a != b: print('MISMATCH', k, col, a, b); bad += 1
print(f'{len(g)} cycles compared, worst absolute difference {worst:.2e}, {"PARITY OK" if not bad else str(bad) + " mismatches"}'); sys.exit(1 if bad else 0)
