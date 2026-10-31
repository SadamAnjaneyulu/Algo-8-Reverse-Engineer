# Fault-tolerant execution and honest partial assessments

PR #1 remains a draft; nothing here authorizes merging or declaring Algo 8 recovered.
The registered protocol, complete-cycle splits, model families, feature sets,
threshold selection, support requirements and 75% precision/recall target are unchanged.

## Failure evidence

Run 41206225359 completed six action-model folds and entered quantity training
at 14:32:50 UTC on 31 October 2026. At 14:47:14 UTC its runner reported a shutdown
signal. Its final upload was skipped and it has no artifacts. Shared-memory
joblib mapping warnings appeared during cleanup. Those warnings do **not** prove
the shutdown was an out-of-memory event; the root cause is not established.
The original unpersisted fitted folds cannot honestly be called reusable.
One fresh action run is therefore necessary to seed durable checkpoints.

## What changes

1. Dataset preparation is a separately audited job, with per-cycle local
   checkpoints, complete input hashes, metadata and the unchanged dynamic fold plan.
2. Action prediction is one job per chronological fold. Basket, side and contract
   groups each upload immediately. Candidate metrics are atomically written after
   every model. Selected predictions, model files and explanations are checkpointed
   after each action task; folds commit an output hash manifest.
3. Quantity prediction is separate, also one job per fold. Every quantity task
   checkpoints its fitted result, errors and selected model. Side and contract
   groups upload separately. No action model is fitted in a quantity job.
4. Exit analysis and autonomous replay run independently of training. Replay uses
   saved action/quantity models and its own state, with one job per fold.
5. A report job runs with `always()` whenever the dataset job succeeded. It lists
   completed and missing folds, preserves available metrics, and prominently marks
   an incomplete study. Missing stages never count as successful assessments.
6. All native/model workers are serial. EBM no longer launches a joblib process
   pool; joblib uses a threading backend with memory mapping disabled. A private
   disk temp directory replaces `/dev/shm`. Each stage records peak RSS and temp
   usage to support diagnosis without asserting a cause for the old shutdown.

## Resume

- **Same workflow run:** use GitHub's **Re-run failed jobs**. Successful jobs and
  their artifacts remain. Retried jobs restore their own partial artifact from
  the same run and reuse completed tasks without fitting them again.
- **New workflow run:** choose **Run workflow**, set `resume_run_id` to the earlier
  compatible run ID. Jobs restore dataset, market cache and their respective fold
  outputs, verify inputs/protocol/code/package signatures and output checksums,
  then skip completed work.
- **Local:** repeat the same stage command with the same `--root`. Complete stage
  manifests cause a verified skip. A partial stage reuses complete task checkpoints.
- **Incompatible code/data:** reuse fails explicitly. Keep the old artifact and
  choose a new root/run rather than weakening the signature guard.

Artifact names: `algo8-dataset`, `algo8-canonical-cache`,
`algo8-action-fold-N`, `algo8-quantity-fold-N`, `algo8-exits`,
`algo8-replay-fold-N`, and `algo8-research-report`. Artifacts are retained for
30 days; exported copies are needed for longer retention. A successful group
upload survives a later hard shutdown. No workflow can guarantee an upload
after the runner has already disappeared.

## Integrity and tests

Atomic commit markers are written after payloads and dependency hashes.
Missing markers, modified model files, stale signatures and corrupt stages
cannot be accepted as completed work. Checkpoints are trusted-workflow Python
pickles; do not load artifacts from an untrusted run.

Fault-injection tests cover an interrupted write, fresh-process reuse without a
second fit, stale input rejection, model corruption, independent quantity failure,
complete-stage skips, and partial-report labelling. Chronology and accounting
tests still run before any expensive study job. Resource changes do not relax
the scientific protocol. No final ML assessment is available from the failed run.
