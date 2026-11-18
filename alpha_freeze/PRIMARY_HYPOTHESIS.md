# Pre-registered primary hypothesis (written before any out-of-sample data was received)

**H1 — BTST overnight short-straddle premium.** Selling the ATM straddle on the afternoon of the last session before a weekly expiry
and buying it back at the next open (or holding to expiry) earns a positive premium net of costs, because expiring options price the
overnight gap risk above what is realised. Mechanism: overnight/1-DTE variance risk premium. Not a timing, indicator or directional signal.

| Item | Locked value |
|---|---|
| Instruments | NIFTY and SENSEX weekly options, ATM = nearest strike to the previous-minute index close |
| Entry | 1 lot CE + 1 lot PE, same strike, at 13:16 on D-1 (secondary: 15:01) |
| Per-lot stop | buy back a leg when its option trades at >= 1.55x its own entry |
| Exit | D0 09:16 open (primary); D0 10:01 and hold-to-expiry (secondaries) |
| Wings / cycle stop / filters | none |
| Fill models reported | entry: open / prev close; stop: level / bar high / next open |
| Costs reported | zero, moderate, conservative, adverse (prior study's registered scenarios) |
| Metrics | total trades, win rate, profit factor, Sharpe (per cycle and annualised x sqrt(104)), total return per lot, max drawdown, frequency |
| Success criterion (proposed - user may change BEFORE the OOS run) | conservative-cost, bar-high stop fill: mean cycle P&L > 0 with cycle-bootstrap 95% CI excluding 0, positive in both indices |

Development evidence (Jun-Oct 2026, 30 cycles; search over 4,512 configs, White reality check p = 0.104, PBO = 0.25):
conservative costs, bar-high stop fill, exit D0 09:16: win 73%, PF 3.25, annualised Sharpe 5.6, +Rs 17.7K per straddle lot, both indices positive.
These are DEVELOPMENT numbers from a searched grid in a falling market; they are not evidence of an edge until the locked OOS test passes.
