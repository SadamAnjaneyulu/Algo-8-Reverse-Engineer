"""Render reports/BODY_SOLO_SELL_MOVE_TEST.md from the bl_move_* outputs."""
import sys; sys.path.insert(0, '.')
from bl_common import *
rd = lambda f, **k: pd.read_csv(f'{OUT}/{f}', **k); pct = lambda x, d=1: f'{100 * float(x):.{d}f} %'
def table(df):
    c = list(df.columns); return '\n'.join(['| ' + ' | '.join(map(str, c)) + ' |', '|' + '---|' * len(c)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in df.values])
A = rd('bl_move_auc.csv'); Dz = rd('bl_move_dose.csv'); LG = rd('bl_move_logit.csv'); TH = rd('bl_move_thresholds.csv'); AB = rd('bl_move_asym_bins.csv'); DS = rd('bl_move_drip_sales.csv'); DW = rd('bl_move_drip_windows.csv'); HS = rd('bl_move_drip_spells.csv'); RB = rd('bl_move_robust.csv'); P = rd('bl_move_panel.csv')
a1 = A[A.day == 'D-1'].set_index('feature'); a0 = A[A.day == 'D0'].set_index('feature')
f30 = Dz[(Dz.day == 'D-1') & (Dz.feature == 'fav30')][['bin', 'minutes', 'events', 'rate_per_1000', 'lift']]
rb = lambda d, s: RB[(RB.day == d) & (RB.subset == s) & (RB.feature == 'fav30')].iloc[0]
Q = P[P.day == 'D-1']; Q = Q.assign(fb=pd.cut(Q.fav30, [-100, 0, .2, 100], labels=['<=0', '0-0.2 %', '>0.2 %']), ob=pd.cut(Q.other_ratio, [0, .9, 1.1, 100], labels=['other leg <=0.9 (profit)', 'other 0.9-1.1', 'other >1.1 (loss)']))
t2 = Q.groupby(['fb', 'ob']).ep.agg(['size', 'sum']); t2['rate'] = (t2['sum'] / t2['size'] * 1000).round(1); t2 = t2.rate.unstack().reset_index().rename(columns={'fb': 'favourable 30-min move'})
import json; J2 = json.load(open(f'{OUT}/bl_summary_move2.json'))
L = []; w = L.append
w('# Test of the hypothesis: solo CE / PE sells are triggered by a heavy market move or a loss of x %, and are injected slowly\n')
w(f"*In-sample, observational. Panel: every minute of every cycle-right ({len(Q):,} minutes on D-1, {len(P[P.day == 'D0']):,} on D0), episode start = first solo (single-leg) sale on that right with none in the previous 5 minutes ({int(Q.ep.sum())} on D-1, {int(P[P.day == 'D0'].ep.sum())} on D0). All features use only data before the minute. 'Favourable move' = fall for a call, rise for a put, in % of spot. Scripts `src/bl_move_*.py`; figure `figures/bl_move_drip_examples.png`.*\n")
w('## 1. Verdict\n')
w(f"""| Your hypothesis | Verdict (D-1) | Evidence |
|---|---|---|
| A solo **CE is added after a fall, a solo PE after a rise** | **Supported** | AUC of the 30-min favourable move {a1.loc['fav30', 'AUC']:.2f} (CI {a1.loc['fav30', 'lo']:.2f}–{a1.loc['fav30', 'hi']:.2f}); calls into falls {rb('D-1', 'CE only (calls into falls)').AUC:.2f}, puts into rises {rb('D-1', 'PE only (puts into rises)').AUC:.2f}; NIFTY {rb('D-1', 'NIFTY').AUC:.2f}, SENSEX {rb('D-1', 'SENSEX').AUC:.2f}; excluding the last 15 minutes {rb('D-1', 'excluding last 15 min (j<360)').AUC:.2f} |
| It needs a **heavy move above some x %** | **Not as a threshold** | the rate jumps from {f30.iloc[0].rate_per_1000} per 1,000 minutes (no favourable move) to ≈ {f30.iloc[2].rate_per_1000}–{f30.iloc[3].rate_per_1000} once the 30-minute move is only 0.1–0.35 %, then does **not** rise further; moves above 0.5 % are rare ({int(f30.iloc[5:].minutes.sum())} minutes) |
| A **loss of x %** triggers the add | **Partly** | a losing *other* leg and a winning *own* leg each add to the effect (logistic, per SD, D-1: favourable move {LG[(LG.day=='D-1')&(LG.term=='fav30')].coef_per_SD.iloc[0]:+.2f}, own-leg book ratio {LG[(LG.day=='D-1')&(LG.term=='own_ratio')].coef_per_SD.iloc[0]:+.2f}, other-leg book ratio {LG[(LG.day=='D-1')&(LG.term=='other_ratio')].coef_per_SD.iloc[0]:+.2f}; all CIs exclude 0); the **combined** book P&L does not matter (AUC {a1.loc['book_loss', 'AUC']:.2f}); no x % cut-off found |
| Sells are **injected slowly** during a heavy move | **Partly** | single 1-lot sales repeated through the move; more lots when the move is bigger (window-level Spearman {J2['rho_d1']:.2f} D-1), but the gaps get **shorter**, not longer, with bigger moves, and most short heavy spells get no solo sale at all |
| Same on **D0** | **Not supported** | AUC {a0.loc['fav30', 'AUC']:.2f} (CI {a0.loc['fav30', 'lo']:.2f}–{a0.loc['fav30', 'hi']:.2f}); logistic terms include 0; D0 solo selling is mostly inventory-driven |
""")
w('## 2. How strong must the move be? (no heavy-move threshold)\n')
w(f"""D-1, episode-start rate by the favourable move over the last 30 minutes:

{table(f30.assign(bin=f30.bin.astype(str)))}

The relationship is a **step from "no favourable move" to "any favourable move"**, then flat — not a jump at some large x. Rules of the form "30-min favourable move ≥ θ" (D-1): {', '.join(f"θ = {r.rule.split('>= ')[1]}: flags {pct(r.share_of_minutes_flagged)} of minutes, catches {pct(r.recall_of_episode_starts, 0)} of starts, lift {r.lift:.1f}" for r in TH[(TH.day == 'D-1') & TH.rule.str.startswith('fav30')].itertuples() if r.rule.split('>= ')[1].startswith(('0.1', '0.2', '0.5')))}. Every θ catches only a minority of episodes, so no single move threshold is the trigger.
""")
w('## 3. Loss of x %: own leg winning vs other leg losing\n')
w(f"""The two are confounded (a fall makes the call book profit and the put book lose), so the 2-D table separates them — D-1 rate per 1,000 minutes:

{table(t2)}

At the same favourable move (0–0.2 %), the rate roughly triples when the other leg is losing (> 10 %) versus profitable; with no favourable move even a losing other leg gives little. Leg asymmetry (other-leg price ratio minus own-leg price ratio) alone: AUC {J2['asym_auc']:.2f}, episode rate {AB.iloc[0].rate_per_1000} per 1,000 minutes at asymmetry ≤ −0.2 up to {AB.iloc[-1].rate_per_1000} above 0.6 (lift {AB.iloc[-1].lift:.1f}). Own-leg profit ≥ 20 % flags {pct(TH[(TH.day=='D-1')&(TH.rule=='own-leg book profit >= 20 %')].share_of_minutes_flagged.iloc[0], 0)} of minutes and catches {pct(TH[(TH.day=='D-1')&(TH.rule=='own-leg book profit >= 20 %')].recall_of_episode_starts.iloc[0], 0)} of starts; other-leg loss ≥ 20 % flags {pct(TH[(TH.day=='D-1')&(TH.rule=='other-leg book loss >= 20 %')].share_of_minutes_flagged.iloc[0], 0)} and catches {pct(TH[(TH.day=='D-1')&(TH.rule=='other-leg book loss >= 20 %')].recall_of_episode_starts.iloc[0], 0)}. **Inferred:** the algorithm reacts to the *imbalance between the two legs* produced by a directional move, not to the size of the overall loss; the spot move and the option-price ratios are too collinear to say which one it reads (**Unresolved**).
""")
w('## 4. Slow injection (drip)\n')
w(f"""![examples](figures/bl_move_drip_examples.png)

The six largest favourable 60-minute moves on D-1: in the **call-into-fall** panels (1, 4, 6) the single-lot call sales arrive one after another while the spot keeps falling (the step line is the running solo lot count, up to 15–17 lots). The three **put-into-rise** panels are dominated by jumps in the closing minutes and show only 2–3 solo sales, so they say little on their own; the statistical tests above cover both rights separately.

* Solo sales by the favourable 30-minute move at the moment of the sale (D-1): {', '.join(f"{r.cond}: {int(r.sales)} sales, {r.lots_per_sale:.2f} lots/sale, median gap {r.median_gap_s:.0f} s" for r in DS.itertuples())}. {pct((~(DS.cond == '<=0')).mul(DS.sales).sum() / DS.sales.sum(), 0)} of the solo sales after the first 30 minutes occur with a favourable 30-minute move; with bigger moves the gap to the previous solo sale on the right gets **shorter** ({DS.iloc[0].median_gap_s:.0f} → {DS.iloc[-1].median_gap_s:.0f} s). Orders are 1 lot except in the unfavourable bucket (end-of-day bursts).
* Solo lots per 15-minute window by the favourable move inside the window (D-1): {', '.join(f"{r.fb}: {r.mean_solo_lots:.2f}" for r in DW[DW.day == 'D-1'].itertuples())}. More fall ⇒ more solo lots (rank correlation {J2['rho_d1']:.2f} over {J2['n_d1']:,} windows).
* Heavy spells (30-min favourable move ≥ 0.2 % for consecutive minutes), D-1: {len(HS[HS.day == 'D-1'])} spells, median duration {HS[HS.day == 'D-1'].minutes.median():.0f} min, **{pct((HS[HS.day == 'D-1'].solo_lots == 0).mean(), 0)} of them received no solo sale**; averaged over all heavy spells (including those with none) that is about {HS[HS.day == 'D-1'].lots_per_hour.mean():.0f} solo lots per hour versus {J2['per_hour_d1']:.1f} per hour over the whole day. So a heavy move **raises** the chance and the number of solo sales but does not guarantee them.
""")
w('## 5. What this means and what is still open\n')
w("""* **Supported:** on D-1 the solo legs are *adds on the side the market is moving away from* — calls while it falls, puts while it rises — fed in as repeated 1-lot orders, more of them in bigger moves.
* **Not supported:** a fixed "move ≥ x %" trigger or a "loss of x %" trigger; the dependence is graded and a single threshold catches only a minority of episodes.
* **Open (Unresolved):** the exact quantity that is compared (spot move vs the option price of the own leg vs the leg asymmetry), whether a per-lot or per-position level is used, what throttles the repeats, and why D0 does not show the same dependence.
* **Not tested:** a trigger in rupees of mark-to-market loss (lot sizes differ by index, so percentages were used).
""")
open(os.path.join(REP, 'BODY_SOLO_SELL_MOVE_TEST.md'), 'w').write('\n'.join(L)); print('written', len('\n'.join(L)))
