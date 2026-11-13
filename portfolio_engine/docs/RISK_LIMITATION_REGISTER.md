# Risk and limitation register

| # | Risk / limitation | Effect | Mitigation |
|---|---|---|---|
| 1 | Original basket membership is unrecoverable | any basket is inferred | provenance label `INFERRED:<convention>`, several conventions in parallel |
| 2 | Export has fills only: no cancels, rejects, modifications, decision logs | order lifecycle (accepted/rejected/cancelled) cannot be replayed historically | those states exist only in simulation/synthetic modes, labelled |
| 3 | Six fills have tie-order-dependent roles | their open/close role is not identifiable | alternative tie orders; report the set; never choose |
| 4 | 37,480 units remain in expired contracts, no settlement price | realized P&L incomplete for them | status `EXPIRED_UNCLOSED`, excluded from realized P&L, shown as book value |
| 5 | No charges, margin, Greeks, IV, capital data | net P&L, margin and Greek limits impossible | not implemented; `NOT_TESTABLE` |
| 6 | Lot size / tick are data-inferred | may differ in other periods | instrument table field with source; policies read it, never hardcode |
| 7 | Two implementations can drift | silent accounting divergence | identical dump parity on every shared fixture + all real fills |
| 8 | AVG pools use floating point | last-digit differences | declared tolerance 1e-6, bit-identity measured and reported |
| 9 | Simulated results mistaken for actual | misleading performance | mode stamped everywhere; engine rejects mixed modes; separate output dirs |
| 10 | Minute-precision order entry time for body orders | decision timing unknown | not used by M1 accounting |
| 11 | Raw market bars are outside the repo | marks/unrealized P&L unavailable | reported as `MISSING_MARKS`, never zero |
| 12 | Branch is built on TP-02; TP-03 Phase 0/1 live on another branch | no TP-03 code available here | by design (isolation) |
