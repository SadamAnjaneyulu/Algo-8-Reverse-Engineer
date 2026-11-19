"""Render ../reports/DD1_INTRADAY_DECISION_STRUCTURE.md from the computed outputs. Every number in the text is computed here."""
import sys; sys.path.insert(0, '.')
from dd_common import *
F = fills(); T = tagged_orders(F); O = ref.orders(F); B = O[O.module == 'num']; H = T[T.module == 'h_']; S_ = T[T.module == 's_']
HB = pd.read_csv(f'{OUT}/dd_hedge_bursts.csv'); ET = pd.read_csv(f'{OUT}/dd_exit_timing.csv'); RP = pd.read_csv(f'{OUT}/dd_roll_pairs.csv'); RD = pd.read_csv(f'{OUT}/dd_roll_d0_dist.csv'); SS = pd.read_csv(f'{OUT}/dd_slot_sizing.csv')
pct = lambda x: f'{100 * x:.1f} %'
def table(df):
    c = list(df.columns); return '\n'.join(['| ' + ' | '.join(map(str, c)) + ' |', '|' + '---|' * len(c)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in df.values])
def rayleigh(s): z = np.exp(2j * np.pi * s.values / 60); return abs(z.mean())
# hedge latency: body first fill (opposite side, same right, same day) nearest to each wing decision stamp
Bs = B.sort_values(['und', 'expiry', 'dayno', 'sec']); lat = []
for (u, e, d), h in H.groupby(['und', 'expiry', 'dayno']):
    b = Bs[(Bs.und == u) & (Bs.expiry == e) & (Bs.dayno == d)]
    for r in h.itertuples():
        m = (b.side.values == ('Sell' if r.side == 'Buy' else 'Buy')) & (b.cp.values == r.cp)
        if m.any(): o = r.t_dec - b.sec.values[m]; lat.append(o[np.argmin(np.abs(o))])
lat = np.array(lat); q = lambda a, p: np.quantile(a, p)
r = HB[HB.responded]; nr = HB[~HB.responded].copy()
Sx = S_.assign(tt=S_.dayno * 100000 + S_.sec)
def near_stop(x): w = Sx[(Sx.und == x.und) & (Sx.expiry == x.expiry)]; return bool((np.abs(w.tt.values - x.tt) <= 60).any())
nr['near_stop'] = nr.apply(near_stop, axis=1)
d1 = ET[ET.day == 0]; d0 = ET[ET.day == 1]
sl = lambda x, lo, hi: x[(x.ratio >= lo) & (x.ratio < hi)]
g = SS[SS.lots > 0].copy(); g['lots_dm'] = g.lots - g.groupby('k').lots.transform('mean')
cv = lambda s: s.std() / s.mean()
sp = lambda a: abs(g[['lots_dm', a]].dropna().corr(method='spearman').iloc[0, 1])
gg_cv_l = g.groupby('k').lots.apply(cv).mean(); gg_cv_p = g.assign(x=g.lots * g.premium).groupby('k').x.apply(cv).mean()
rows = []
for nm, x in (('D-1', d1), ('D0', d0)):
    for c, y in x.groupby('cls'): rows.append(dict(day=nm, price_ratio_class=c, n=len(y), at_second_0=pct((y.s == 0).mean()), within_0_2=pct((y.s <= 2).mean())))
tt = pd.DataFrame(rows)
bb_lots = B[B.side == 'Buy'].lots.sum()
L = f'''# DD-1 — Intraday decision structure of Algo 8 (35 live cycles)

**Purpose.** Look under the "top layer": find the *structure* of the mid-session activity (what drives what, and when) using the microsecond decision stamps embedded in order tags and the fill clock. **IN-SAMPLE, descriptive, read-only.** Nothing here is a recovered trading rule unless labelled so; the 35 cycles are not a holdout. Code `src/dd_*.py`, tables `outputs/dd_*.csv`, tests `tests/test_dd1.py`, report generator `src/make_dd_report.py` (all numbers below are computed by it).

## 1. Result first
| # | Finding | Evidence | Status |
|---|---|---|---|
| F1 | The hedge module (`h_`) is a **reactive per-right mirror of body lot changes**, lagging the body fill by ≈ {np.median(lat):.1f} s. {len(H):,} of {len(O):,} orders ({pct(len(H) / len(O))}) are therefore largely determined by body activity. | {pct(HB.responded.mean())} of {len(HB):,} body bursts get a wing response within 10 s; wing Δlots = body Δlots in {pct((r.dW.abs() == r.dS.abs()).mean())} of responses; wing level equals body-short level after the response in {pct((r.gap_after == 0).mean())} (the level is not always balanced because bursts start from an existing gap: median |W−S| before a burst {HB.gap_before.abs().median():.0f} lots) | **STRONGLY SUPPORTED** |
| F2 | **D-1 body exits are minute-clocked; D0 body exits are not.** | buy-backs of a recorded short filled in second :00 — D-1 {pct((d1.s == 0).mean())}, D0 {pct((d0.s == 0).mean())}; within :00–:02 D-1 {pct((d1.s <= 2).mean())}, D0 {pct((d0.s <= 2).mean())}; Rayleigh concentration of second-of-minute D-1 {rayleigh(d1.s):.2f} vs D0 {rayleigh(d0.s):.2f}; the :00 share is similar for the stop-like 1.55–1.8× class ({pct((sl(d1, 1.55, 1.8).s == 0).mean())}) and all D-1 exits | **CONFIRMED OBSERVATION** (timing). *Mechanism is inferred, not observed:* D-1 exit logic evaluates once per completed minute; D0 exit logic runs on a different loop |
| F3 | **Slot sizing is not premium-budgeted and not book-state dependent.** | within-slot CV of lots {gg_cv_l:.2f} vs CV of lots×premium {gg_cv_p:.2f} (a premium budget would make the second *smaller*); slot-adjusted size vs premium / book shorts / 15-min move: |Spearman| {sp("premium"):.2f} / {sp("book_short"):.2f} / {sp("move15_bp"):.2f}; slot id explains {pct(1 - g.lots_dm.var() / g.lots.var())} of size variance | premium-budget and book-state hypotheses **REJECTED**; actual size driver **UNKNOWN** |
| F4 | **"Sell-and-re-centre" explains a minority of buy-backs.** | {pct(RP.lots.sum() / bb_lots)} of {bb_lots:,} body buy-back lots are re-sold on the same right within 60 s (median delay {RP.delay.median():.0f} s; same strike in only {pct((RP.k_old == RP.k_new).mean())}); on D0 the new strike is nearer the previous completed spot than the old one in {pct((RD.abs_new < RD.abs_old).mean())} of {len(RD):,} pairs (median distance {RD.abs_old.median():.2f} → {RD.abs_new.median():.2f} strike steps) | re-centring-to-ATM as the general buy-back explanation **REJECTED**; the 60-s pairing is a descriptive filter, not an identified roll rule |
'''
L += f'''
## 2. What the tag stamps give us
Tagged orders (`h_`, `s_`, `v_`, `m_`; {len(T):,} orders) carry `DDHHMMSSffffff` (UTC; +5:30 = IST). Fill time is whole seconds. Fill second minus decoded decision stamp (positive = fill second later than the stamp): wings median {H.lat.median():.2f} s (IQR {H.lat.quantile(.25):.2f}–{H.lat.quantile(.75):.2f}), stop module {S_.lat.median():.2f} s (IQR {S_.lat.quantile(.25):.2f}–{S_.lat.quantile(.75):.2f}). Sub-second values are within the fill-second quantisation and possible clock offset between the stamp and the fill log. Body (`num`) orders carry no stamp, so body decision times are known only to the second.

## 3. The hedge module (F1)
* Body bursts (orders ≤ 3 s apart on one right): **{len(HB):,}**; wing response within 10 s: **{pct(HB.responded.mean())}**.
* Responses to body sells (wings bought) {int((r.dS > 0).sum()):,}; to body buy-backs (wings released) {int((r.dS < 0).sum()):,}.
* Wing level equals body-short level after the response: sells {pct((r[r.dS > 0].gap_after == 0).mean())}, buy-backs {pct((r[r.dS < 0].gap_after == 0).mean())}.
* Latency (wing decision stamp minus nearest opposite-side body fill second): median {np.median(lat):.1f} s, IQR {q(lat, .25):.1f}–{q(lat, .75):.1f} s — the hedge reacts to the *completed* body trade, not to the body decision.
* Non-responses: {len(nr):,} bursts, of which D0 {int((nr.day == 1).sum()):,} and D-1 {int((nr.day == 0).sum()):,}; {int(nr.near_stop.sum()):,} lie within 60 s of an `s_` (stop-module) order of the same cycle. These are the first thing to explain (liquidation, flatten and lump paths are candidates — **hypothesis, untested**).
* **For the engine:** the quantity rule (one wing lot per body short lot, released with it) is right; the wing should be a separate reactive process that follows body fills. The remaining open hedge problem is the wing **strike** only.

## 4. Exit timing (F2)
{table(tt)}

`price_ratio_class` = fill price ÷ average entry price of the recorded open short lots in that contract. D-1 exits of every class fill at the minute boundary far more often than chance (1/60 = 1.7 %); D0 exits do not. **Implication for modelling:** minute-bar evaluation is structurally suited to D-1 exits and structurally unsuited to D0 exits — consistent with the largest parity gap being D0 buy-backs.

## 5. Pre-registered next tests (not yet run — written before looking)
1. **D0 exits as reactions to own fills (H1):** time from the previous algo fill (any module, same underlying) to each D0 body buy-back clusters at a fixed delay (hedge-like) → event-driven chain; otherwise independent clock.
2. **Poll period (H2):** Rayleigh/period scan of D0 buy-back fill seconds over candidate periods 2–59 s with a phase-preserving circular-shift null; a significant period ⇒ polling loop.
3. **Inside-minute price path (H3):** for stop-like D0 exits compare the minute's high/low with 1.55–1.7 × entry; a tick-level trigger predicts crossing within the same minute.
4. **Sizing (H4):** cycle-level scale vs date / spot level / previous-cycle result. Observed so far: std of cycle-mean residual {g.groupby(["und", "expiry"]).lots_dm.mean().std():.2f} vs {g.lots_dm.std() / np.sqrt(14):.2f} expected if independent across 14 slots (indicative only).
5. **What halts a body entry stream:** number of child orders per slot vs a fill-count target, time box or state condition.

## 6. Limits
In-sample; one ~4-month window; body fills at second resolution; no tick data; the LTP at decision time is available only through prices of fills; D0 exits that are re-sales are separated from genuine exits only by the 60-s pairing used in F4; burst/response definitions (3 s / 10 s) are fixed analysis choices, not recovered parameters.

## 7. Evidence labels used
CONFIRMED OBSERVATION · STRONGLY SUPPORTED · HYPOTHESIS · UNKNOWN · REJECTED (as in earlier reports in this programme).
'''
os.makedirs(REP, exist_ok=True); open(os.path.join(REP, 'DD1_INTRADAY_DECISION_STRUCTURE.md'), 'w').write(L); print('written', len(L))
