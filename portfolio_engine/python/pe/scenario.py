"""Scenario selection for the historical output builders (R1-C, project decision Option C).

A SCENARIO is a fill-order convention applied at replay time. The delivered M2-B..M2-E outputs are the BASELINE scenario (`SOURCE_ROW_ORDER_CONVENTION`) in their delivered directories.
Every other scenario (and a baseline reproduction) must write to an explicit OUT ROOT outside the delivered directories, and every manifest it writes states
`scenario_id`, `tie_order_convention`, `source_hash`, `generator_version`, `execution_mode`. Source data are never modified; ordering keys are derived at load time from the raw columns
(`generators.historical.attach_tie_keys`, which checks the raw file hash against the TP-01 manifest).

Command line of every builder:  [--scenario=baseline|<policy>] [--out-root=<dir>]
  no flags                      -> baseline, delivered directories (unchanged behaviour)
  --out-root=D                  -> baseline written under D/reports/...  (reproduction of the delivered outputs)
  --scenario=P --out-root=D     -> policy P (sensitivity-only) written under D/reports/...; refused without an out root or with an out root inside the delivered report directories.

Ordering semantics (see docs/ORDERING_SEMANTICS.md): a policy orders fills only inside one (instrument, second); the cross-instrument interleaving inside a second is a deterministic SERIALIZATION order,
not chronology; aggregate (portfolio) states between fills of the same second are UNORDERED_WITHIN_SECOND.
"""
import os
from . import tie_policy as tp
from .schema import EngineError

BASELINE = 'baseline'
DELIVERED_DIRS = ('m2c_data', 'm2c_figures', 'm2d_data', 'm2d_figures', 'm2e_data', 'm2e_figures')
ORDERING_SEMANTICS = ('same-instrument fills inside one second are ordered by the scenario policy; the interleaving of different instruments inside a second is the baseline serialization (source-file row order), '
                      'a deterministic output order and NOT chronology; portfolio-level states between fills of the same second are UNORDERED_WITHIN_SECOND; at second end inventory, cash and cumulative gross opened/closed units are order-invariant, but cumulative realized P&L, per-module attribution and reversal counts are NOT (they depend on same-instrument order)')


class Scenario:
    def __init__(self, scenario_id, pe_root, out_root=None):
        self.id = BASELINE if scenario_id in (BASELINE, tp.PRIMARY_POLICY, 'src') else scenario_id
        self.policy = tp.PRIMARY_POLICY if self.id == BASELINE else tp.resolve(self.id).name
        self.tie = tp.engine_order(self.policy); self.pe_root = os.path.abspath(pe_root); self.out_root = os.path.abspath(out_root) if out_root else None
        if self.id != BASELINE and not self.out_root: raise EngineError(f'scenario {self.id!r} is a sensitivity scenario: it needs --out-root (it must never write into the delivered directories)')
        if self.out_root:
            for d in DELIVERED_DIRS:
                p = os.path.join(self.pe_root, 'reports', d)
                if self.out_root == p or self.out_root.startswith(p + os.sep): raise EngineError(f'--out-root {self.out_root} is inside the delivered directory reports/{d}')

    @property
    def baseline(self): return self.id == BASELINE
    @property
    def delivered(self): return self.baseline and self.out_root is None          # writing the delivered outputs themselves
    @property
    def root(self): return self.out_root or self.pe_root                            # base of every relative path the builders write or record
    def reports(self, *parts): return os.path.join(self.root, 'reports', *parts)
    def convention_id(self): return tp.convention_id(self.policy)

    def attach(self, repo, fills):
        from .generators import historical as H
        return H.attach_tie_keys(repo, fills, self.policy)

    def convention_metadata(self):
        return tp.CONVENTION_METADATA if self.baseline else dict(id=self.convention_id(), engine_policy=self.tie, verified_intra_second_chronology=False,
                                                                  statement='SENSITIVITY-ONLY ordering scenario; not verified execution chronology', sensitivity='reports/R1C_DUAL_SCENARIO_COMPARISON.md')

    def manifest_extra(self, source_hashes, generator, execution_mode='HISTORICAL_OBSERVED_REPLAY'):
        """keys appended (in this order) at the end of every manifest the builders write; the delivered manifests keep exactly their existing `tie_order_convention` key"""
        from . import provenance
        extra = dict(tie_order_convention=self.convention_metadata())
        if not self.delivered:
            extra['scenario'] = dict(scenario_id=self.id, tie_order_convention=self.convention_id(), source_hash=dict(source_hashes), generator_version=f'{generator}@{provenance.git_sha(self.pe_root)}',
                                     execution_mode=execution_mode, ordering_semantics=ORDERING_SEMANTICS)
        return extra


def from_argv(argv, pe_root):
    sid, out = BASELINE, None
    for a in argv[1:]:
        if a.startswith('--scenario='): sid = a.split('=', 1)[1]
        elif a.startswith('--out-root='): out = a.split('=', 1)[1]
    return Scenario(sid, pe_root, out)
