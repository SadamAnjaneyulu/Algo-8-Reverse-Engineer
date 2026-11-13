# Evidence registry (implemented behaviors only)

Classes: CONFIRMED_OBSERVATION, CONFIRMED_ATTRIBUTION, STRONGLY_SUPPORTED, WEAKLY_SUPPORTED, UNRESOLVED, NOT_TESTABLE, SYNTHETIC_TEST_ONLY. Claim types: OBSERVATION, ATTRIBUTION, TRIGGER.
No finding identifier is invented: where TP-01 assigned none, the section of the source document is cited.

| Behavior implemented in M1 | Source | Field(s) | Class | Claim | Implementation mode | Limitation |
|---|---|---|---|---|---|---|
| Fill-level inventory per contract = signed sum of fills | TP-01 `PHASE0_AUDIT.md` (units, reconciliation), `reconciliation_summary.csv` | raw cols 11, 33, 137, 161, 163 | CONFIRMED_OBSERVATION | OBSERVATION | observed replay | gross only; no charges in the file |
| Fill role (open/close/reversal) decided by the contract's current net inventory | TP-01 `matching.py` documented rule | derived | CONFIRMED_OBSERVATION (accounting identity) | OBSERVATION | observed replay | 6 fills have tie-order-dependent roles (`role_ambiguity_fills.csv`) |
| FIFO / LIFO / AVG lot ownership | TP-01 conventions | derived | UNRESOLVED (ownership is not recorded) | OBSERVATION of three equally valid conventions | observed replay | conventions differ in P&L attribution, not in inventory |
| Module prefix of parent tag (`num`,`h_`,`s_`,`v_`,`m_`) | TP-01 ledger `module`; Stage 1 data map | raw col 163 | CONFIRMED_ATTRIBUTION | ATTRIBUTION | carried as `module_tag` | does not prove why an order was sent |
| Per-fill price (col 137) used, not order average (col 18) | TP-01 `PHASE0_AUDIT.md` | cols 137 vs 18 | CONFIRMED_OBSERVATION | OBSERVATION | observed replay | — |
| Expired contracts with remaining inventory carry no settlement P&L | TP-01 (`EXPIRED_UNCLOSED`, 37,480 units) | derived | NOT_TESTABLE (settlement values absent) | OBSERVATION | observed replay | realized P&L excludes them; book value reported separately |
| Synthetic fixtures | this project | generated | SYNTHETIC_TEST_ONLY | — | synthetic | never mixed with historical results |

Not implemented in M1 (so not registered): entries, strikes, sizing, hedges, exits, basket cut, re-entry, any threshold such as the 4 % carry stop or the ₹2 lakh kill switch (they will be configurable *hypotheses*, not facts).
