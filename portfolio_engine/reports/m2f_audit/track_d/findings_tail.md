
## 7. Not inspected / limits
* M2-C chaining rules and M2-D matching internals (only equality, conservation and a raw re-implementation of W1 / W1_S60 candidate sets); W3 queue arithmetic and W2 weights not re-derived; 107,530 mixed-module closing-wing units NOT VERIFIED.
* Individual PNG pixel content beyond the 20 figures + 7 case PNGs inspected (10 case PNGs not viewed: NIFTY CT3, CT6, CT6b, CT7, CT8; SENSEX CT1, CT2, CT6, CT6b, CT8); the M2-E markdown catalog and final report prose was grepped, not proofread line by line.
* No market bars exist in this environment (ALGO8_MARKET_DIR absent): mark coverage NOT VERIFIED either way; C++ parity and slow tests not run beyond tests/test_forensics.py.
* Same-second fill ordering uses raw row order (convention).
* 337 raw fills outside 09:14-15:31 IST in the full ledger (none in the two cycles) not investigated.

## 8. Defects (severity)
Critical: none. High: none. Medium: D-01 (V4 legend hides widest batch), D-02 (case selection "fixed before" claim), D-03 (selection concentrated on D-1 session start), D-04 (case PNGs generic), D-15 (weak existing selection / presentation tests), D-16 (SENSEX "no reversal" definition-dependent). Low: D-05 .. D-14. Details with repro / fix / test in defects.json.
