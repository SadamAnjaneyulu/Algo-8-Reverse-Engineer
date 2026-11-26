"""Render reports/BODY_SELL_TRIGGERS_D1.md (clock-driven vs single-leg sales on D-1). Numbers computed from bl_trig_* outputs."""
import sys; sys.path.insert(0, '.')
from bl_common import *
from scipy import stats
rd = lambda f, **k: pd.read_csv(f'{OUT}/{f}', **k); pct = lambda x, d=1: f'{100 * float(x):.{d}f} %'
def table(df):
    c = list(df.columns); return '\n'.join(['| ' + ' | '.join(map(str, c)) + ' |', '|' + '---|' * len(c)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in df.values])
S = pd.read_pickle(f'{OUT}/bl_trig_sells_d1.pkl.gz'); PR = rd('bl_trig_pairing.csv', index_col=0); AU = rd('bl_trig_auc.csv'); P = rd('bl_trig_panel.csv'); SR = rd('bl_trig_strike_rules.csv'); SQ = rd('bl_trig_slot_qty.csv'); TM = rd('bl_trig_timing.csv', index_col=0)
def ray(x, p): return abs(np.exp(2j * np.pi * (x % p) / p).mean())
sg = S[~S.paired]; pd_ = S[S.paired]; base = P.event.mean()
single_share = sg.lots.sum() / S.lots.sum(); by_right = (sg.groupby('cp').lots.sum() / S.groupby('cp').lots.sum())
haz = lambda f, bins: P.groupby(pd.cut(P[f], bins)).event.agg(['size', 'sum', 'mean']).assign(lift=lambda d: d['mean'] / base)
def hz_tab(f, bins, name):
    t = haz(f, bins).reset_index(); t[f] = t[f].astype(str); return table(pd.DataFrame({name: t[f], 'minutes': t['size'], 'episode starts': t['sum'], 'rate per 1000 min': (t['mean'] * 1000).round(1), 'lift vs base': t.lift.round(2)}))
O_ = load_orders(); C_ = O_[(O_.module == 'num') & (O_.role == 'cover_short') & (O_.dayno == 0)]; cov_flags = []
for r in sg.itertuples():
    c = C_[(C_.und == r.und) & (C_.expiry == r.expiry) & (C_.cp == r.cp) & (C_.tod < r.tod) & (C_.tod >= r.tod - 900)]; cov_flags.append(len(c) > 0)
cov_share = np.mean(cov_flags)
rho = {f: stats.spearmanr(SQ[f], SQ.resid) for f in ('S_before', 'cov15', 'absmove15')}
au = AU.copy(); au['AUC (95 % CI)'] = [f'{a:.3f} ({l:.3f}–{h:.3f})' for a, l, h in zip(au.AUC, au.lo, au.hi)]; au['holm_p'] = au.holm_p.round(3)
L = []; w = L.append
w('# What makes Algo 8 sell on D-1: the 15-minute clock vs single-leg sales\n')
w(f"*In-sample, observational (32 cycles with a D-1 log, {len(S):,} body short-sale orders, {S.lots.sum():,.0f} lots). Observed / Inferred / Unresolved tags. Scripts `src/bl_trigger1-3.py`, `bl_trigger_fig.py`; figure `figures/bl_trigger_NIFTY_2026-06-30.png`.*\n")
w('## 1. Answer in one view\n')
w(f"""| | Paired straddle sales (CE + PE together) | Single-leg sales (CE only or PE only) |
|---|---|---|
| Share of D-1 sold lots | {pct(1 - single_share)} | **{pct(single_share)}** (CE {pct(by_right['CE'])} of CE lots, PE {pct(by_right['PE'])}) |
| Time structure | **clock**: 15-minute period concentration R = {ray(pd_.tod.values, 900):.2f}; {pct(PR.loc['slot_minute', 'True'] / PR['True'].sum())} of paired lots in the slot minutes (09:16 + 15 k) | **none**: R = {ray(sg.tod.values, 900):.2f} (15 min), {ray(sg.tod.values, 60):.2f} (1 min); seconds-of-minute flat |
| What decides it | the clock (+ a per-slot lot ladder) | **an event**: the market has moved *away from that right's existing shorts* (book in profit) — a tendency, no exact threshold found |
| Strike | ATM of the previous minute ({pct(SR.set_index('group').loc['paired slot-minute (comparison)', 'ATM_exact'])}) | premium of the previous sale on that right ({pct(SR.set_index('group').loc['single-leg (all)', 'PREVPX_exact'])} exact) rather than ATM ({pct(SR.set_index('group').loc['single-leg (all)', 'ATM_exact'])}) |
""")
w('## 2. The 15-minute clock (Observed)\n')
w(f"""* Paired sales sit in the slot minute: share of paired **orders** by minute of the 15-minute cycle (0 = slot minute 09:16 + 15 k): minute 0 {pct(TM.loc[0, 'paired'])}, minute 14 (the minute before) {pct(TM.loc[14, 'paired'])}, minute 1 {pct(TM.loc[1, 'paired'])}, all other 12 minutes {pct(TM.loc[2:13, 'paired'].sum())}. Within the slot minute {pct((pd_[pd_.cls == 'slot_minute'].sec <= 15).mean(), 0)} of paired orders fill in seconds 0–15 and {pct((pd_[pd_.cls == 'minute_before_slot'].sec >= 55).mean(), 0)} of the minute-before orders fill at seconds 55–59 (i.e. the order fires about at the minute mark, a few seconds early).
* **Strike:** nearest strike to the previous completed minute's spot close (Body lifecycle study: 84 % exact on slot-minute sells).
* **Quantity:** a fixed lots-per-right ladder by slot index (table in the Body lifecycle report §3B; 3 lots per right in the 09:16 slot, then mostly 1–2, differing somewhat between NIFTY and SENSEX; stable across cycles: {pct((SQ.resid == 0).mean())} of {len(SQ)} slot-rights equal the modal ladder). The deviation from the ladder is **not** explained by state: Spearman of the residual with shorts held before the slot {rho['S_before'].statistic:.2f}, with lots bought back in the previous 15 minutes {rho['cov15'].statistic:.2f} (a refill rule would give a positive value), with the 15-minute spot move {rho['absmove15'].statistic:.2f}. **Unresolved:** where the ladder comes from.
""")
w('## 3. Single-leg sales (the calls or puts that appear alone)\n')
w(f"""**Not time-based (Observed).** Their times show no period (R ≤ {max(ray(sg.tod.values, p) for p in (30, 60, 120, 300, 600, 900)):.2f} for periods 30 s – 15 min, vs {ray(pd_.tod.values, 900):.2f} for the paired sales) and the second-of-minute is flat. They come in short runs: median gap to the previous sale on the same right {sg.sort_values(['und','expiry','cp','te']).groupby(['und','expiry','cp']).tt_first.diff().median():.0f} s.

**What precedes them (Observed, AUC test).** I defined an *episode start* as the first single-leg sale on a right with none in the previous 5 minutes ({int(P.event.sum())} starts in {P.groupby(['und','expiry']).ngroups} cycles) and compared the minute before it with all other minutes of the same cycle-right ({len(P):,} minutes). Features use only data available before the minute; the list was fixed in advance (Holm over 13 features, cluster bootstrap over cycles). AUC 0.5 = no association; < 0.5 = lower at episode starts.

{table(au[['feature', 'AUC (95 % CI)', 'holm_p']])}

(`adv k` = spot move over the last k minutes in steps, **positive = adverse to a short of that right** — up for calls, down for puts; `dev_book` = spot minus the weighted strike of the right's shorts, + = shorts ITM; `ratio_book` = current price ÷ average entry price of the right's short book; `ratio_last` = current price of the last-sold contract ÷ its sale price; `imb` = shorts of this right minus the other right.)

Reading: single-leg sales start when the market has just moved **in favour of the right's existing shorts** (adv AUC 0.24–0.30), the shorts are OTM-ward of the spot (`dev_book` 0.28) and the book is **in profit** (`ratio_book` 0.27, `ratio_last` 0.33). Hazard per minute:

{hz_tab('ratio_book', [0, .7, .8, .9, 1.0, 1.1, 10], 'book price ratio')}

{hz_tab('adv5', [-10, -.5, -.25, 0, .25, .5, 10], 'adverse spot move, 5 min (steps)')}

The rate is about 2–2.4× the base rate ({base * 1000:.1f} per 1,000 minutes) when the book price ratio is ≤ 0.9 and about 0.2–0.3× when the book is losing (> 1.1); adverse moves almost never start an episode. **There is no sharp threshold** (rule "book ratio ≤ 0.85" flags {pct((P.ratio_book <= .85).mean(), 0)} of minutes and catches {pct(P[P.ratio_book <= .85].event.sum() / P.event.sum(), 0)} of starts; "last-sold ratio ≤ 0.8" flags {pct((P.ratio_last <= .8).mean())} and catches {pct(P[P.ratio_last <= .8].event.sum() / P.event.sum(), 0)}). **Inferred:** the single legs are *adds on the profitable side* after premium has decayed on that right; the exact trigger level is **Unresolved**.

**Which strike (Inferred).** Not the ATM (hit {pct(SR.set_index('group').loc['single-leg (all)', 'ATM_exact'])}): the sale price is close to the previous sale's price on that right (median ratio 1.0), so after a favourable move the strike moves one step further ITM. Rule "strike whose current price is nearest to the previous sale price on that right":

{table(SR.assign(**{c: SR[c].map(pct) for c in SR.columns if c != 'group' and c != 'n'}))}

The premium-continuity rule beats the ATM rule for single legs ({pct(SR.iloc[0].PREVPX_exact)} vs {pct(SR.iloc[0].ATM_exact)}) and the shuffled-price null ({pct(SR.iloc[0].PREVPX_null_exact)}), while paired slot-minute sales follow the ATM ({pct(SR.iloc[2].ATM_exact)}). The null is high because prices barely change within minutes, so this is **PARTIALLY SUPPORTED**, not a recovered rule.
""")
w('## 4. Exceptions and what remains unresolved\n')
w(f"""* Not every single-leg sale follows a favourable move: {pct((P[P.event == 1].ratio_book > 1).mean(), 0)} of episode starts have a losing book (e.g. the NIFTY 2026-06-30 burst at 14:55, where puts were sold with the put book at 1.2–1.35× entry — this is part of the heavy end-of-day selling).
* No explicit trigger level, no per-lot timer, and no link to buy-backs (only {pct(cov_share)} of single-leg sales follow a body buy-back on the same right within the previous 15 minutes) was found. **Unresolved:** exact threshold, the quantity per episode, and why the end-of-day bursts differ.
* Pairing is defined as a sale on the other right at the same strike within 3 s; a looser definition would move a few lots between the two groups but not change the clock/non-clock split.
""")
open(os.path.join(REP, 'BODY_SELL_TRIGGERS_D1.md'), 'w').write('\n'.join(L)); print('written', len('\n'.join(L)))
