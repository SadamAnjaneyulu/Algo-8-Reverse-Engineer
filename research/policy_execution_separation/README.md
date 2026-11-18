# Latent policy versus execution reconstruction

The two layers are explicit: `policy.hpp` generates desired contract positions
from preceding market data and its own confirmed state; `execution.cpp` converts
targets to hypothetical requests/fills. Historical positions/actions are used
only by inherited scoring. The frozen-target intervention feeds identical
safe-generated target streams to all execution variants.

From the repository root (Python3.12, C++17 g++):

```bash
python -m pip install -r research/hypothesis_controller_search/requirements.txt
OPENBLAS_NUM_THREADS=1 python research/policy_execution_separation/forensics.py
OPENBLAS_NUM_THREADS=1 python research/policy_execution_separation/model_runner.py
OPENBLAS_NUM_THREADS=1 python research/policy_execution_separation/analyse.py
python research/policy_execution_separation/write_report.py
python -m unittest discover -s research -p 'test_*.py'
python research/policy_execution_separation/validate.py
```

Existing research outputs are read-only inputs. `replay_inputs.py` regenerates
missing disposable canonical arrays under this module's `.cache/`, preserving
old result files. No broker authentication or new download is required.

`REGISTERED_PLAN.md` defines the59-case cohort, hypotheses, opening rules,
12policies,7mechanics, splits and scores. `MEASUREMENT_NOTES.md` records important
measurement and implementation qualifications. Reconstructed parent references
are not confirmed decision/submission/cancellation records. Compatibility scores
are not probabilities that an original condition was decoded.

The selected configuration can be replayed without selecting new parameters:

```bash
python research/policy_execution_separation/model_runner.py \
  --replay-config research/policy_execution_separation/selected_model_config.yaml
```

All84 models retain scores, latent target changes, request-quantity audits and
atomic closure diagnostics. Complete minute actions and mismatch traces cover
the fixed August-selected cohort in `trace_cohort.json`. Detailed child requests,
fills and minute books are retained for six mechanics of the selected policy.
The overactive stale-state negative control has complete aggregate/reversal data;
its full child dump is reproducible but is not committed. `.cache/` is disposable.

Execution prices are minute-open proxies at the simulated time, not tick quotes.
Missing/zero execution prices do not fill requests. Seed contracts missing from
the stored traded-only universe remain explicitly unfilled theoretical targets;
no price/settlement/margin is invented. First-execution matching uses child
seconds and source-row ties, separately from minute action matching.
