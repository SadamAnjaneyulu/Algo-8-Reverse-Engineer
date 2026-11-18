# Measurement and implementation audit

The59 source motifs, model parameter configurations, scoring weights and
chronological splits are unchanged. No parameters are selected on later results.

- Final implementation uses semantic leg priority (protection before new shorts,
  short covers before protection removal), rather than contract-array order.
- Expiry09:16 is a routine addition when the latent book is active, not another
  three-base seed. Received expiry-only cycles retain unknown initialization.
- A minute-aggregate table cannot identify the first child fill by sorting strike.
  The provisional new9/32 first-wing count used that wrong ordering. Final scoring
  of first wings uses raw event seconds and source-row order for exact ties,
  retains a multiple-strikes-in-first-second flag, and reports17/32. The old
  published0/32 aggregate benchmark remains unchanged; a separate child-second
  re-audit of that prior candidate also returns0/32. Main minute-action scores,
  quantity counts, model definitions and selection are unaffected by this fix.
- Storage is compacted, not sampled to improve scores. All84 models retain full
  scores, latent goals, request-conservation summaries and atomic closure/reversal
  diagnostics. A cohort fixed from August results retains complete minute-action
  traces; detailed child requests/fills cover the selected policy's six regular
  mechanics. The deliberately overactive stale-ignore-pending negative control
  retains full aggregate actions/closures, not gigabytes of repetitive child logs.
- The input adapter can rebuild the exact canonical binary in this module's
  disposable cache. A cold-cache smoke test verifies its hash matches the original
  cache and checked prior committed evidence files remain unchanged.

Base-sized *parent requests* are distinct from base-sized child partial fills.
The fragmentation mode's expansion requests are separately submitted one-base
parents; reductions may remain bulk/partial. This representation correction
changes zero minute-action predictions across all12 policies, verified by replay
fingerprints, and does not change the primary selected model. Parent-size
agreement is reported separately and favors fragmentation over aggregation.
The fixed two-second per-leg staggering itself is not inferred from that result.

Candidate limit-price fields, remaining quantity, fill status and raw event
reference candidates are retained in forensic child records. Their semantics
remain inferred/qualified. Two uninterpreted export-tag values are encoded as
T0/T1 without treating them as different strategies or manual/automated origins.
