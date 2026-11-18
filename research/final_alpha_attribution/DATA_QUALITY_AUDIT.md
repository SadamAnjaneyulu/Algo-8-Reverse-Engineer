# Data quality audit — before final economic comparisons

The independent Decimal book reconciles **41,421** recorded children
and **21,882** atomic books to the frozen canonical ledgers. Raw stored
quotes reconcile **25,458** available minute equity snapshots; maximum
error is 4.365574569e-11 rupees. Prices are recorded executions for cash flow;
residual values are quote marks, never executions or invented settlement.

There are 35 cycles, 32 with
observed pre-expiry initialization and three expiry-only starts. All source-book
initial quantities assume zero before the first received fill; external completeness
is unverified. 24 received books end flat;
11 retain residual contracts.
All 35 endpoints can be marked
using stored quotes, with 0 unpriced
endpoint contracts and zero modeled endpoint prices. This does not establish
that those positions were held to that mark or settled at that value.

2 cycles have no received expiry-day
fills. Their available expiry quotes support a hypothetical residual valuation,
not unobserved executions. Missing minute marks, zero-volume candles and incomplete
traded-contract chain coverage remain explicit. No account NAV, actual margin,
authenticated transaction charges or full bid/ask tape is available.

The three economic views must remain distinct: received fill cash flow; received
cash plus quoted residuals; the same marked result after fixed cost/stress estimates.
A positive cash receipt with an open short is not realised profit. A full model
attribution is not a modeled liquidation. The 35 previously researched cycles do
not reproduce the screenshot's March 2025–May 2026 backtest.

The per-cycle [coverage table](data_quality_and_coverage.csv),
[residual ledger](residual_position_ledger.csv) and [immutable input audit](input_audit.json)
are the accounting boundary for all subsequent results. The fixed plan was saved
before economic comparisons. No original finding/configuration/result is changed.
