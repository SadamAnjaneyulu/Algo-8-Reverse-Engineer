# Implementation clarifications before economic/model comparisons

Saved while the quality audit is running, before any new benchmark or cost
result is calculated. The registered definitions and thresholds do not change.

- B includes the actual opening prefix strictly before 09:18, with its cash,
  inventory and incurred parent/turnover/unit costs. It then freezes the book.
- To prevent a horizon mismatch, paired B/C comparisons use an additional
  `D_common_clock` view: actual cash and inventory strictly before the same fixed
  deadline, followed by a hypothetical close at that candle open. This is modeled
  execution, not an observed final trade. Full observed endpoint D remains the
  principal accounting view and is never silently replaced by this counterfactual.
- Simulated benchmark entries and terminal closes pay one hypothetical parent
  fee for every base-unit request (ceiling for an irregular remainder). B's actual
  opening prefix keeps actual parent counts. This avoids an artificial fee
  advantage from netting all benchmark quantities into one large close request.
- Quote-volume at simulated fill bars is an ex-post execution-quality diagnostic,
  never a pre-signal eligibility feature. Prior-volume eligibility is available
  for C's hedge selector. Primary quoted comparisons and stricter nonzero-fill-
  volume common samples remain separate.
- Model attribution includes a spot-only-forward sensitivity, alongside the
  registered parity-forward primary and rate/expiry-clock sensitivities. Parity
  forward moves include basis/synchronization effects; they are not pure cash-
  index delta. Fitted per-contract IV absorbs residual surface/model effects,
  not a measured exogenous volatility shock. No sensitivity is selected on P&L.
