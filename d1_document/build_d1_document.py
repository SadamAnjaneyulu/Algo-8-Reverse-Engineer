"""Builds D1_Strategy_Document.docx (and the PDF via LibreOffice). Run from this folder: python build_d1_document.py"""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

NAVY = RGBColor(0x1F, 0x3A, 0x5F); GREY = RGBColor(0x55, 0x5B, 0x66)
doc = Document()
sec = doc.sections[0]; sec.page_width = Cm(21.0); sec.page_height = Cm(29.7)
for s in ('left_margin', 'right_margin'): setattr(sec, s, Cm(2.0))
sec.top_margin = Cm(1.8); sec.bottom_margin = Cm(1.8)
st = doc.styles['Normal']; st.font.name = 'Calibri'; st.font.size = Pt(10.5); st.element.rPr.rFonts.set(qn('w:eastAsia'), 'Calibri')
st.paragraph_format.space_after = Pt(5); st.paragraph_format.line_spacing = 1.08
for name, size, col in (('Heading 1', 16, NAVY), ('Heading 2', 12.5, NAVY), ('Heading 3', 11, GREY)):
    h = doc.styles[name]; h.font.name = 'Calibri'; h.font.size = Pt(size); h.font.bold = True; h.font.color.rgb = col; h.element.rPr.rFonts.set(qn('w:eastAsia'), 'Calibri')
    h.paragraph_format.space_before = Pt(12 if name != 'Heading 3' else 8); h.paragraph_format.space_after = Pt(4); h.paragraph_format.keep_with_next = True

def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), hexcolor); tcPr.append(shd)

def para(text='', bold=False, italic=False, size=None, color=None, align=None, after=None, style=None):
    p = doc.add_paragraph(style=style); add_runs(p, text, bold, italic, size, color)
    if align: p.alignment = align
    if after is not None: p.paragraph_format.space_after = Pt(after)
    return p

def add_runs(p, text, bold=False, italic=False, size=None, color=None):
    """**bold** segments inside text"""
    parts = text.split('**')
    for k, t in enumerate(parts):
        if not t: continue
        r = p.add_run(t); r.bold = bold or (k % 2 == 1); r.italic = italic
        if size: r.font.size = Pt(size)
        if color: r.font.color.rgb = color

def bullets(items, size=None):
    for t in items:
        p = doc.add_paragraph(style='List Bullet'); add_runs(p, t, size=size); p.paragraph_format.space_after = Pt(2)

def no_split(row):
    trPr = row._tr.get_or_add_trPr(); cs = OxmlElement('w:cantSplit'); cs.set(qn('w:val'), 'true'); trPr.append(cs)

def table(header, rows, widths=None, size=9, header_fill='1F3A5F', zebra=True, bold_first=False):
    t = doc.add_table(rows=1, cols=len(header)); t.style = 'Table Grid'; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]; c.text = ''; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(size); r.font.color.rgb = RGBColor(255, 255, 255); shade(c, header_fill)
    for n, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ''; p = cells[i].paragraphs[0]; add_runs(p, str(v), size=size, bold=(bold_first and i == 0)); p.paragraph_format.space_after = Pt(1)
            if zebra and n % 2 == 1: shade(cells[i], 'F2F5F9')
    if widths:
        t.autofit = False
        tblPr = t._tbl.tblPr; lay = OxmlElement('w:tblLayout'); lay.set(qn('w:type'), 'fixed'); tblPr.append(lay)
        for i, w in enumerate(widths): t.columns[i].width = Cm(w)
        for row in t.rows:
            for i, w in enumerate(widths): row.cells[i].width = Cm(w)
    for row in t.rows: no_split(row)
    hdr = t.rows[0]._tr.get_or_add_trPr(); th = OxmlElement('w:tblHeader'); th.set(qn('w:val'), 'true'); hdr.append(th)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t

def callout(title, lines, fill='EAF1FB'):
    t = doc.add_table(rows=1, cols=1); t.style = 'Table Grid'; no_split(t.rows[0]); c = t.rows[0].cells[0]; shade(c, fill); c.text = ''
    p = c.paragraphs[0]; r = p.add_run(title); r.bold = True; r.font.size = Pt(10.5); r.font.color.rgb = NAVY
    for l in lines:
        p = c.add_paragraph(); add_runs(p, l, size=10); p.paragraph_format.space_after = Pt(2)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

FIGN = [0]
def figure(path, caption, width=16.5):
    FIGN[0] += 1
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next = True; p.add_run().add_picture(path, width=Cm(width))
    c = doc.add_paragraph(); add_runs(c, f'**Figure {FIGN[0]}.** ' + caption, size=9, color=GREY); c.paragraph_format.space_after = Pt(8)

# ===================================================================== title
para('How the strategy behaves on the day before expiry', bold=True, size=22, color=NAVY, after=0)
para('What it sells, how it exits, how it protects itself, and why it looks designed this way', size=13, color=GREY, after=4)
para('Research summary for Rahul  |  23 November 2026  |  Based on 32 live expiry cycles (late June to late October 2026), NIFTY and SENSEX index options', size=9.5, color=GREY, after=10)

callout('The short version', [
    '**What it is.** A systematic short-premium strategy on index options. On the session before expiry (we call it **D-1**) it builds a book of short at-the-money (ATM) straddles and single-sided shorts, protects every short with a far out-of-the-money (OTM) long on the same side, stops out individual losing lots, adds a block of extra OTM longs shortly before the close, and carries the book into expiry day. The system we studied is referred to internally as Algo 8; everything below is read from its order log and the market data, not from source code.',
    '**Three ways of selling.** (1) **Scheduled straddles**: a fixed clock, 33 straddles a day, no market condition. (2) **Breakout straddles**: when the spot breaks the range of the last two 30-minute candles, a straddle one strike beyond ATM in the break direction, plus extra lots on the favourable side. (3) **Solo selling**: one-lot sales of the option the market is moving away from, repeated as the move extends.',
    '**Exits.** Each lot has its own stop at about 1.6 times its entry price. Lots that never get near it are carried overnight (68% of sold lots).',
    '**Protection.** Long lots on each side are kept equal to short lots on that side, about 15 to 19 strikes out of the money (the "wings"). Before the close an extra block of longs about 2.2 one-day standard deviations out covers a gap on the heavier side.',
    '**How much we can reproduce.** Timing and side of the decisions: well (AUC 0.92 on cycles not used for fitting). Exact lot counts and exact stop timing: no, because they are set inside the minute (F1 0.63 on unseen cycles). Details and the open items are in sections 7 and 8.'])

# ===================================================================== 1 setting and terms
doc.add_heading('1. The setting and the terms used', 1)
para('The strategy trades weekly index options on two indices, NIFTY (listed strikes every 50 points, one lot = 65 units) and SENSEX (strikes every 100 points, one lot = 20 units). One lot is about Rs 15 lakh of notional on either. Each expiry cycle has two sessions that matter here: **D-1**, the session before expiry day, and **D0**, expiry day itself. This document covers D-1 only. D0 is a separate process (position management and liquidation) and is not described here.')
table(['Term', 'Meaning in this document'], [
    ['ATM, strike step', 'The strike nearest the spot. "One strike beyond ATM" means one listed step further in the direction named. The strike step is 50 (NIFTY) or 100 (SENSEX).'],
    ['Straddle', 'A call and a put sold at the same strike. Here usually 1 lot of each.'],
    ['Premium, ratio', 'Premium is an option\'s price. **Ratio** = the option\'s current price divided by the price at which that lot was sold. A short loses money when the ratio is above 1.'],
    ['Stop, buy-back', 'Buying a short lot back (covering). A stop at 1.6 means buying back when the price reaches 1.6 times the sale price.'],
    ['Wing', 'A far out-of-the-money long option bought to cap the loss of a short on the same side (call wings for short calls, put wings for short puts).'],
    ['Right, CE / PE', 'Call (CE) or put (PE).'],
    ['Cycle', 'One expiry: its D-1 and its D0.'],
    ['AUC, F1', 'Accuracy measures. AUC (0.5 = coin flip, 1 = perfect) asks whether the minutes where the system acts rank above the others. F1 asks whether a reconstructed order matches a real one (same side, within one minute); it is the harder test.'],
    ['Evidence labels', '**Observed** = read directly from the order log or market data. **Interpretation** = our reading of why, inferred from behaviour; the intent itself cannot be observed. **Unresolved** = not determined.']],
    widths=[3.4, 13.6])
para('**Data.** The complete order log of the strategy for 32 cycles (21 under timetable A, 11 under timetable B; see 3.1) and one-minute open/high/low/close bars for the spot and for every listed option strike. Everything here is in-sample (the rules were found on these 32 cycles), except the forward test in section 7.', size=10)

# ===================================================================== 2 the book at a glance
doc.add_heading('2. What the book looks like through D-1', 1)
para('Over a typical D-1 the strategy sells a median of 141 lots (both sides together), buys back some of them, and ends with a median of 104 net short lots. The sells come from three sources: the timetable (median 66 lots), breakout straddles (30) and solo selling (40). Across all 4,671 lots sold in the 32 cycles, **scheduled straddles are 45%, breakout straddles 16% and solo selling 38%**.')
para('Selling is front-loaded and then irregular. The timetable supplies almost all the lots before noon, then thins out; after noon most of the volume comes from breakouts and solo sells. Nothing stops the selling: the last sale is at a median 15:25, and 81% of cycles still sell after 15:15. About **68% of the lots sold on D-1 are carried overnight**: a median of 102 short lots in about 11 contracts, against 157 long lots.')
figure('figures/fig01_book_buildup_and_sizing.png', 'The book through D-1 (32 cycles). **A:** scheduled pairs per 15-minute block under the two timetable versions (V1 = timetable A, V2 = timetable B). **B:** cumulative lots sold, of which the timetable, and net short after buy-backs (median and range over cycles). **C:** where the lots come from by hour: timetable (green), breakout straddles (orange), solo (purple). **D:** the lot unit did not change during the sample; the shaded window is where the timetable was edited.', 17)

# ===================================================================== 3 selling
doc.add_page_break(); doc.add_heading('3. The three ways it sells', 1)
table(['', 'Scheduled straddles', 'Breakout straddles', 'Solo selling'], [
    ['Share of D-1 lots sold', '45%', '16%', '38%'],
    ['What triggers it', 'The clock only', 'Spot breaks the high/low of the previous two completed 30-minute candles (10:30 to 15:15)', 'Spot makes a fresh extreme away from the right being sold (calls on a fresh low, puts on a fresh high), repeated as the move extends'],
    ['What is sold', '1 lot call + 1 lot put', '1 to 3 straddles plus 0 to 7 extra single lots on the favourable side', 'Single lots, mostly 1 lot per order, often in short bursts'],
    ['Strike', 'ATM of the previous minute\'s close', 'ATM of the previous close, shifted one strike in the break direction', 'First sale at ATM; later sales at the strike whose premium is nearest the previous sale on that side'],
    ['Reproduced (F1, timing)', '0.98', '0.68 (first entry of each candle side: 93%)', '0.47'],
    ['Status', 'Solved', 'Timing solved; repeat entries and exact lots not', 'Understood, not a deterministic rule']],
    widths=[3.2, 4.0, 4.9, 4.9], size=8.5, bold_first=True)

doc.add_heading('3.1 Scheduled straddles: a fixed clock', 2)
para('**How it executes.** At fixed seconds inside the 15-minute blocks of the session the strategy sells one straddle: 1 lot call and 1 lot put at the same strike, placed within a few seconds of each other. There are **33 such waves a day**, 0 to 4 per 15-minute block, dense in the morning (about 8 an hour) and sparse after noon (2 to 3 an hour). Each wave fires in at least 95% of cycles (all waves under timetable A, 90% of waves under timetable B). Per index and per right that is 33 lots a day, 66 lots in total, in 1-lot orders.')
para('**Which strike.** The ATM strike of the **previous completed minute\'s close**, not the current price and not a delta or forward-based strike. This matches the sold strike exactly 93.6% of the time; the alternatives we tested (call delta nearest 0.5, a delta-neutral straddle, the forward price, the strike with the smallest call-put gap) all score 56 to 68%. Repeated waves tend to stay at an already-short strike (87%), and the strike migrates with the market from slot to slot.')
para('**What does not matter.** We tested 36 state variables (spot moves, book profit and loss, delta, gamma, vega, implied volatility and its change, inventory, recent buy-backs and solo sales). None explains whether or how much is sold in a slot better than chance. The selling continues in every market state; the only thing that stops it is the cycle-level stop module (it fired in one D-1 of the 32).')
para('**Two timetable versions.** Between the D-1 of 9 September and the D-1 of 16 September 2026 seven waves were moved to different seconds; the total stayed at 33 straddles. The lot unit did not change. We do not know why the timetable has these particular seconds or why it was edited.')
para('**How the lots exit.** Each lot has its own stop (section 4). Lots that never reach it are carried overnight.')
callout('Why (interpretation)', [
    'A fixed clock with no market condition is what a **systematic, time-diversified premium harvest** looks like: the same small size is added at set times so that no single entry price or timing decision matters. ATM is the point of maximum time value per unit of risk, and using the previous completed bar is what a system that reads a bar feed would do. The loading is heaviest in the morning, when there is the most time value left and the most session in which to collect it, and thins after noon, when each extra lot of gamma risk costs more as expiry approaches. We cannot observe the intent, but the pattern, a fixed ladder per slot that does not react to anything, is consistent with this.'], fill='F5F5F0')
figure('figures/fig02_timetable_heatmap.png', 'Scheduled straddle lots per right at each 15-minute slot (columns, from 09:16) for every cycle (rows, by expiry date; N = NIFTY, S = SENSEX). The ladder is the same in every cycle; the red line marks the timetable edit in September (rows below it follow timetable B).', 12.5)

doc.add_heading('3.2 Breakout straddles', 2)
para('**The rule.** From 10:30 to 15:15, each minute is compared with the **highest high and lowest low of the previous two completed 30-minute candles** (the candles are aligned to the clock: 10:00 to 10:30, 10:30 to 11:00, and so on; the current candle is excluded). If the minute\'s high breaks above that range, or its low below it, the strategy sells a straddle (call and put) at the strike **one step beyond ATM in the break direction**, on the **first break per side per candle**. There is no margin: breaking the level by even one NIFTY point counts. Shifting the candle clock by 5 or 15 minutes (the exchange\'s own 09:15-aligned candles) destroys the match, so the candles are clock-aligned at the hour and half hour.')
para('**How many lots.** The size grows with the **depth of the break** beyond the range: on average about 1.1 straddles per entry for a hairline break rising to about 2 for a break of more than a strike step (the rule caps it at 3), plus **extra single lots on the favourable side** (puts on an upside break, calls on a downside break: 315 of 320 observed cases). The average total goes from about 2.4 lots for a hairline break to about 5.7 for a break of more than one strike step (Figure 4B).')
para('**How accurate.** The rule reproduces the first entry of each candle side in 93% of cases (90% in the exact minute) and the reactive straddle minutes with F1 0.82 (precision 90%, recall 75%). What is not reproduced: repeat entries inside the same candle (about 29% of entry candles have more than one entry; no price, volume, premium or book rule explains them) and the exact number of lots.')
para('**How the lots exit.** Besides the price stop, breakout lots are cut when the breakout **continues**: the leg on the break side is bought back while the spot keeps moving in the break direction (buy-back rate 2.9% a minute against 0.3% otherwise, 7.9% a minute at 1 to 2 steps of continuation), mostly within 5 minutes of the sale.')
callout('Why (interpretation)', [
    'A break of the last hour\'s range means the market has moved to a new area. Moving the straddle one strike toward the break **re-centres the new short exposure on where the market now trades**, and the extra lots go on the side that is moving away (the option that loses value as the break runs), with more size the deeper the break. The system is therefore adding premium risk at the new price level, on the side that is currently working, and cutting the breakout lots quickly if the move keeps going against the straddle. We infer the purpose from the structure (strike shift, favourable-side extras, depth-scaled size, fast cut on continuation); the data do not state it.'], fill='F5F5F0')
figure('figures/fig03_breakout_example.png', 'One NIFTY D-1 (8 September 2026). Blue lines: high and low of the previous two completed 30-minute candles. Crosses: the first minute that breaks the level, per side and candle, according to the rule. Triangles: the real breakout straddles. The bars below compare real fires (red), rule fires (black) and the scheduled straddles (grey).', 17)

doc.add_heading('3.3 Solo selling: the drip', 2)
para('**What it is.** Single-sided sales that are not part of a straddle. About **30% of solo decisions place 2 to 8 one-lot orders within 3 seconds**; the rest are single lots. Overall 69% are calls. 21% of solo lots belong to breakout entries (the favourable-side extras above); about 61% are stand-alone intraday sales; and about 18% come after 15:00.')
para('**Trigger (intraday).** A solo **call is sold on a fresh low of the spot, a solo put on a fresh high** (a break over 5 to 60 minutes; 60 minutes on true highs and lows fits best). It happens while the **market is moving away from that side** and while **the own side of the book is in profit and the other side is losing**, typically 1 to 2 minutes after the previous sale on that side, with the last-sold option\'s price dipping about 6% inside the minute. This is a **drip**: the best rule sells one lot each time the spot moves another **0.2 strike steps** beyond the previous reference, gated by a fresh 60-minute extreme. Most fresh extremes do not produce a sale, so the rule is necessary-looking but not sufficient (precision about 24% to 52% depending on the variant).')
para('**Which strike.** The first sale on a side is at ATM. Later sales go to the strike whose **premium is nearest the premium of the previous sale on that side** (exact 37%, within one strike 74%), rather than to the ATM of the day.')
para('**How many lots.** Mostly one lot per order. The number of lots per minute grows with how far the spot has broken beyond its 60-minute extreme (about 1.3 lots for a hairline break, about 6.6 for 0.7 to 1 strike step), but only weakly predictably (rank correlation 0.30): the lots are **dripped over about 5 seconds**, one each time the price prints a new extreme inside the minute. One-minute bars cannot show that.')
para('**After 15:00.** A different-looking regime (18 to 25% of solo lots) with spikes at 15:00, 15:23 and 15:29. It uses the same trigger plus one input: the sold option\'s **own premium making a fresh 15-minute low**. Into the close time decay and falling volatility push premiums to new lows without a spot extreme, so the system sells on the premium falling, not only on the spot. A rule "spot fresh 15-minute extreme or premium fresh 15-minute low" finds 90% of these sales but about half of the qualifying minutes have no sale (F1 0.65).')
para('**Not solo selling.** In a few cycles (3 of 32) there are **deep OTM batch sells** after 14:00 (five or more strikes from ATM, premiums of Rs 0.3 to 5, orders of up to 54 lots, 6% of the lots sold on D-1). They are not modelled. We also found that solo selling is **not** portfolio balancing or delta hedging: balancing by premium value, lot count or book delta all sit at chance, and lots go to the side that is already larger.')
callout('Why (interpretation)', [
    'Solo selling looks like **adding to a short that is working**: the system sells more of the option that is losing value as the market runs away from it, while that side of the book is in profit. It is a pyramiding rule on premium decay, with a small step (0.2 strike steps) so that the position builds gradually as the move extends. Whether the design intent is momentum in premium decay or a way to rebuild exposure after buy-backs cannot be settled from the data; the balancing explanations were tested and rejected. A related pattern: about 30% of older-lot buy-backs coincide, within 5 seconds, with a new solo sale on the **other** side (base rate 3%): when calls are cut in a rally, puts are sold.'], fill='F5F5F0')
figure('figures/fig04_solo_selling.png', 'Solo selling. **A:** time since the previous solo sale on the same side (bursts of 1-lot orders). **B:** breakout entry size grows with the depth of the break (grey = straddles per entry, red = extra favourable lots). **C:** how well each state variable separates solo-sale minutes from other minutes (0.5 = no information; red = the informative ones: the other side losing, own side in profit, recent sale, last-sold premium dipping). **D:** share of regular solo lots by class and how much of each the reconstruction reproduces; all D-1 sells together reach F1 0.78 out-of-fold.', 16.5)
figure('figures/fig05_after_1500_solo.png', 'After-15:00 solo sales. **A:** late solo lots by minute and what coincides with them (blue: spot at a fresh 15-minute extreme; green: the sold option\'s premium at a fresh 15-minute low only). **B:** probability of a sale per minute and side given each condition, intraday (grey) vs late (blue). **C:** which blocks of variables predict late solo minutes (market variables alone reach AUC 0.82). **D:** portfolio-shaping explanations all near a coin flip, so rejected.', 16.5)

# ===================================================================== 4 exits
doc.add_heading('4. How positions exit', 1)
para('There is **no scheduled exit** on D-1. Selling and closing are separate processes: the number of lots sold in a slot does not depend on how many were bought back since the last slot (rank correlation -0.04), and only 3.2% of lots sold are re-sales within 60 seconds of a buy-back. Closing is done lot by lot.')
para('**The stop.** Each lot is bought back when its option price reaches a multiple of **its own entry price**. The buy-back rate rises steadily with that ratio: about 1 to 6 buy-backs per 1,000 contract-minutes up to 1.2 times, 12 at 1.2 to 1.4, 37 at 1.4 to 1.55, 74 at 1.55 to 1.7 and 113 at 1.7 to 2.0. It is **graded, not a single threshold**, but nearly certain by 1.7 to 1.8 times. The best single rule is the **minute high reaching about 1.6 times entry** (the current minute\'s high, not the close: the stop reacts to intrabar touches). It is a ratio, not a number of points: the points lost scale with the entry price. Delta, how far in the money the contract is, and time held add almost nothing beyond the ratio.')
para('**How many lots per stop.** Lots are bought back one at a time (1-lot orders), the **cheapest-entry (highest-ratio) lots first**; a stop closes the open lots above roughly 1.55 times (71% of stops are within one lot of that), not the whole contract (only 18% of stops close every lot on it). 87% of buy-backs are on lots that are in loss at the decision price. The remaining 13% are mostly the same-strike partner leg of a stopped straddle or a two-sided cut-back.')
para('**Each sell type has its own exit behaviour** (Figure 6): scheduled straddle lots follow a price stop (hazard about zero below 1.5 times, then 4%, 15%, 47% a minute above 1.5, 1.6, 1.7 times; fitted threshold 1.6 to 1.65). Breakout lots are cut when the breakout continues. Solo lots are cut when the market reverses (4.8% a minute at 2 or more strike steps of reversal, 2.0% after an opposite two-candle break, against 0.24%). Lots held under 10 minutes exit at about 1.1 times, lots held over 30 minutes at about 1.55 to 1.6 times: the low-ratio exits are fresh directional lots.')
para('**Clusters.** Buy-backs are rebalancing events more than isolated stops: 67 to 77% come with buy-backs on other strikes of the same right within 5 seconds. A fast adverse move explains much of the rest: the best variable is the 3-minute rise in the option\'s own price (AUC 0.80). A fresh 30 to 60-minute spot breakout against the position multiplies the buy-back rate about 10 times at every premium level, but it is an accelerator, not the stop: waiting for it delays exits that the price stop would have taken.')
para('**What is carried.** Lots that never reach 1.2 times are the bulk: 61% of lots sold on D-1 never reach 1.2 times on a minute close, and 82% of those are carried overnight. That is the 68% of sold lots that end D-1 still short.')
para('**Not decoded.** About 15 to 21% of buy-backs have no identified rule; a drawdown or percent-of-capital rule does not fit; the exact stop timing sits inside the minute. The stop module, which can liquidate the whole book, fired in 1 of the 32 D-1 sessions.')
callout('Why (interpretation)', [
    'A ratio stop on each lot **caps the loss per lot at roughly 60% of the premium collected** (before slippage or a gap through the stop) and leaves the rest of the book undisturbed, so one bad strike does not force closing the whole position. The stop is wide (1.6 times) because short premium positions are meant to be held: a profitable short decays towards expiry, so lots that stay below the stop are simply carried. Breaking the stop into one-lot buy-backs, cheapest entry first, closes the worst lots and keeps the rest. We read the straddle partner and cluster buy-backs as closing the other side of a position that has stopped being balanced.'], fill='F5F5F0')
figure('figures/fig06_exits_by_sell_type.png', 'Exits. **(a)** Low-ratio exits are fresh lots, not a random threshold: median ratio at buy-back by minutes the lot was held. **(b)** Buy-back rate by ratio (minute high divided by own entry), per sell type. **(c)** Breakout lots are cut when the spot keeps going in the entry direction (orange); solo lots when it reverses (green). **(d)** What coincides with buy-backs that are in profit.', 16.5)

# ===================================================================== 5 wings
doc.add_heading('5. The protective long wings', 1)
para('Every short sold is matched by a long on the same side, so the book is, in effect, **an iron butterfly pooled by right**: the shorts earn the premium and the far-OTM longs cap the loss. There are four kinds of long orders on D-1 (about 7,200 lots in total across the 32 cycles).')
table(['Long order', 'When and how many', 'Which strike', 'Evidence'], [
    ['**1. Controller wings**', 'About **4 seconds after each short is sold**, buy exactly the gap between short lots and long lots on that right (all strikes). Long lots therefore equal short lots on each right all day.', 'The OTM strike whose premium is nearest **2.5% of the ATM option\'s price** on that right (about 15 strikes out for NIFTY, 19 for SENSEX, at about Rs 4.5). Exact strike 65%, within one strike 93%.', 'Quantity equals the gap in 98% of 3,141 buy decisions; long = short in 99% of quiet-time samples (100% from 09:15 to 13:00). Reproduced at F1 0.92 when given the real short orders.'],
    ['**2. Wing releases**', 'When shorts are bought back, sell exactly the excess longs.', 'The outermost or cheapest wing first (44% each against 26% by chance); almost never the innermost.', 'Quantity right in 96% of 500 sell decisions; the choice of wing is a preference, not a rule.'],
    ['**3. Opening wings**', 'At 09:16, before the first three scheduled straddles: 1 far call and 1 far put each, about **6 lots per cycle**; sold back during the day.', 'About 39.5 strikes out of the money, median premium Rs 1.4.', '31 of 32 cycles. The form is solved.'],
    ['**4. Overnight lump**', 'One decision between 15:06 and 15:35, split into exchange-size chunks (27 lots NIFTY, 50 lots SENSEX per order, immediate-or-cancel), on the **heavier short side only** in 80% of cycles.', 'About **2.2 one-day standard deviations** out of the money (median 1.5% of spot; premium about Rs 6.2); sigma comes from the ATM straddle price.', 'Size about 0.83 times the heavy-side short lots (NIFTY), 0.50 times (SENSEX), median error about 24% (unresolved).']],
    widths=[2.6, 5.4, 4.9, 4.1], size=8.3)
para('**The lump\'s clock.** The time it is placed moved on fixed dates: 15:06 to 15:14 until 5 August 2026, 15:23 to 15:24 for the cycles of 12 to 19 August, and 15:30 to 15:35 from 24 August. These look like configuration changes, not a market signal. A lump is placed whenever shorts are carried overnight; the two cycles without one had a flat book or only 34 heavy-side shorts.')
para('**What the lump does.** Before it, a move in the heavier direction would lose a median Rs 29 lakh within a 6% move (value at expiry); after it, Rs 15 lakh. The tail is roughly halved and becomes much more uniform across cycles (coefficient of variation 0.34 to 0.17). It is **not a delta hedge**: it removes only about 5% of the book\'s delta, although it always leans against it (93% of cycles). It costs about Rs 19,000 per cycle (median), and when it was later sold on expiry day it recovered at most about half its premium (median 7%).')
callout('Why (interpretation)', [
    'The controller wings turn every short into a **defined-risk position**: the loss of a short is capped by a long on the same side that costs only 2.5% of the ATM price, so a tail move cannot be unlimited whatever the stops do. They are bought within seconds of the sale so the protection is in place as the exposure appears; the opening wings put the hedge in place before the first sale of the day. Releasing wings as shorts are bought back stops paying for protection that is no longer needed. The lump is **gap insurance for the overnight carry**: before the close, when the book is about to be held through a gap, the system adds an extra layer on the side that would lose most, about 2 sigmas out, so a large gap in the dangerous direction turns the book net long beyond that strike. In every cycle where it was sold back, it recovered little of its cost, which is what insurance against a gap that did not happen looks like.'], fill='F5F5F0')
figure('figures/fig07_protective_wings.png', 'Protective wings. **(a)** One NIFTY D-1: short lots (solid) and long lots (dashed) per right; long lots track short lots all day and the overnight lump adds longs after 15:00. **(b)** Wing strike rule: exact-strike hit rate (blue), the same with the reference shuffled (grey) and within-one-strike rate (black tick) for different reference prices; the ATM option price works best. **(c)** Which wing is sold when shorts are bought back (outermost and cheapest, chance 26%). **(d)** Lump size against the heavy-side short lots (blue NIFTY, orange SENSEX; dotted = one for one).', 16.5)
figure('figures/fig08_overnight_lump.png', 'The overnight lump. **(a)** Time of the lump against the D-1 date: three clock regimes. **(b)** Size against heavy-side shorts, about 24% median error. **(c)** The lump halves the worst loss in the heavy direction (a move of 0 to 6%, value at expiry). **(d)** On expiry day the lump module itself sold lump lots in 18 of 30 cycles, never above cost (zero = not sold by that module).', 16.5)

# ===================================================================== 6 why
doc.add_heading('6. Why the strategy looks designed this way', 1)
para('This section collects the logic in one place. It is an **interpretation**: the order log shows what the system does, not what its designers intended. Where we say "why", the support is the structure of the behaviour, and we say so.')
table(['Design feature', 'What it achieves', 'What supports the reading'], [
    ['Sell ATM straddles on a fixed clock', 'Collects time value evenly through the session with no timing view; size is built by repetition, not by a large single entry.', 'Each wave fires in at least 95% of cycles; no market or book variable changes it (36 tested); ladder identical for calls and puts.'],
    ['Heavy in the morning, thin after noon', 'Takes premium while the most time value remains; limits new gamma risk as expiry approaches.', 'About 8 waves an hour in the morning, 2 to 3 after noon. Intent not observable.'],
    ['Breakout straddles one strike toward the break, with favourable-side extras', 'Re-centres new exposure on the new price and leans on the side that is losing value; deeper breaks get more size.', 'Strike shifts with the break; extras on the favourable side in 315 of 320 cases; size rises with depth (rank correlation 0.42).'],
    ['Solo drip of 1-lot sales', 'Builds the position gradually in the direction in which it is already working.', 'Triggered by fresh extremes while own side is in profit and the other losing; balancing hypotheses rejected.'],
    ['Per-lot stop at about 1.6 times', 'Caps each lot\'s loss; the rest of the book is untouched; profitable shorts keep decaying.', 'Buy-back rate climbs with each lot\'s own ratio; delta, depth and time add little; 87% of buy-backs are in loss.'],
    ['Cut breakout lots on continuation, solo lots on reversal', 'Directional lots are closed when the market proves them wrong, faster than the price stop would.', 'Buy-back rate 10 to 25 times higher in those states; exact trigger not recoverable from minute bars.'],
    ['Wings equal to shorts on each right', 'Every short has a capped loss; the book is an iron butterfly pooled by right.', 'Long = short in 99% of quiet samples; the quantity is the gap in 98% of decisions.'],
    ['Overnight lump on the heavier side', 'Gap insurance for the carry into expiry day; roughly halves the worst heavy-direction loss.', 'About 2.2 sigma out; reduces the worst case but only about 5% of delta, so not a delta hedge.'],
    ['Carry 68% of lots overnight', 'Expiry-day decay on lots that never reached the stop.', '61% of lots never reach 1.2 times; 82% of those are carried. What happens on expiry day is outside this document.']],
    widths=[4.6, 6.2, 6.2], size=8.5)
para('**Taken together:** a premium-selling book that adds risk by clock, by breakout and by drip; limits the loss of each lot with a ratio stop; limits the loss of each short with a wing; and buys one extra layer of gap protection before holding the book overnight. Three kinds of entry mean three different reasons to be short; two kinds of protection (stop and wing) mean the loss of any one short is bounded twice.')

# ===================================================================== 7 accuracy
doc.add_heading('7. How well we can reproduce it, and the Python code', 1)
para('We rebuilt the whole D-1 as a rule-based program that sees only the market data (spot and option one-minute bars) and never the real orders, then compared its orders with the real ones, lot by lot (same side and class, within one minute of the real order).')
table(['Measure', 'Result'], [
    ['Lot-level F1, all D-1 lots (fitted on the 32 cycles, out-of-fold halves)', '**0.68** (precision 78%, recall 61%; 8,368 of 13,655 real lots matched)'],
    ['Lot-level F1 on cycles not used for fitting', '**0.63** (same timetable version), **0.62** after a timetable change'],
    ['AUC, "is the system active in this minute" (unseen cycles)', '**0.92** (0.96 in-sample)'],
    ['Strike also right (within one step / exact)', 'F1 0.62 / 0.45'],
    ['By class (F1, timing)', 'Body sells 0.76; opening wings 0.97; wing buys 0.73 (0.92 given the real short orders); overnight lump 0.64; buy-backs 0.55; wing releases 0.54'],
    ['Book through the day (short and long lots per right)', 'Correlation 0.83 / 0.89 with the real book, median error about 18%']],
    widths=[8.4, 8.6], size=9)
para('**What limits it.** The remaining gap sits inside the minute: solo lots are dripped over about 5 seconds and stops fire on intrabar touches, which one-minute bars cannot show. If the exact lot count were known at every event we found, F1 would rise from 0.67 to 0.83; with exact timing too, 0.89. We tried eleven further ideas (learned models for solo sells and buy-backs, alternative stop designs, rebalancing rules, joint tuning). None beat the simple decoded rules on unseen cycles, and the largest gains were under +0.01. More modelling on the same minute data mostly fits noise. Two things would help: one-second or tick data for the D-1 sessions, and more live cycles as a true holdout.')
figure('figures/fig09_reconstruction_accuracy.png', 'Reconstruction against the real D-1 order log. **(a)** F1 by class: timing (blue), timing plus strike within one step (green), timing plus exact strike (orange); black diamonds = the hedge rules given the real body orders. **(b)** Short and long lots through the day, real vs rebuilt (mean over cycles). **(c)** F1 per cycle (blue NIFTY, orange SENSEX; dashed = overall). **(d)** Lots by class, real vs rebuilt. "h_" = protective wing orders, "v_" = overnight lump.', 16.5)
figure('figures/fig10_accuracy_limits.png', '**(a)** Every accuracy attempt against the decoded rules (blue); none beats them on unseen cycles. **(b)** What the remaining gap is made of (oracle ceilings): exact lot counts at the events already found, exact timing, and the events not found.', 16.5)
doc.add_heading('The Python code', 2)
para('The accompanying package (`d1_strategy/`: `algo8_d1.py`, a README, a synthetic-data example and unit tests) implements the strategy above in general terms: a scheduled-straddle timetable, a two-candle breakout generator, the solo ladder, per-lot stops, the wing controller, opening wings and the overnight lump. The input is one-minute spot bars and option bars; the output is the list of orders and the end-of-day book.')
bullets([
    '**Checked against our research simulator:** on identical parameters it produces the same orders on all 32 cycles.',
    '**Checked against the real order log:** F1 0.69 (precision 79%, recall 62%) with parameters fitted on the same 32 cycles, so in-sample; the out-of-sample figure to expect is the 0.63 above.',
    '**Unit tests:** 9, covering the timetable, ATM strike rule, wing equals short, wings out of the money, breakout once per side per candle, ladder gating, stops, the lump and the configuration dates.',
    '**What it does not do:** exact lot counts inside a minute, the stop module, deep out-of-the-money batch sells, repeat breakout entries, and the expiry-day process.'])

# ===================================================================== 8 unknowns
doc.add_heading('8. What we do not know', 1)
table(['Open item', 'Where it stands'], [
    ['Exact solo-sale trigger and lot count', 'Understood in direction and context (fresh extreme, own side in profit, other side losing); not a deterministic rule. Lots are dripped within seconds, so tick data is needed.'],
    ['Repeat breakout entries inside a candle', 'About 29% of entry candles have more than one entry; no rule found.'],
    ['Buy-backs without a rule', '15 to 21% have no identified trigger; the stops on continuation and reversal are seen as hazards but have no sharp threshold in minute data.'],
    ['Overnight lump size', 'Roughly 0.83 times (NIFTY) or 0.50 times (SENSEX) the heavy-side shorts, with about 24% median error; no tested rule does better.'],
    ['Why the timetable has those seconds, and why it changed in September', 'Not observable. The change moved seven waves with no change in total lots.'],
    ['Why the lump clock moved on three dates', 'Looks like configuration changes; cause unknown.'],
    ['Deep out-of-the-money batches, the stop module\'s liquidation, the 15:15 closes and re-buys of body-stream longs', 'About 3% of D-1 lots; not modelled.'],
    ['Generalisation', 'All rules were found on 32 cycles from one four-month period; structure was chosen after seeing all of them, so even the forward numbers are somewhat optimistic for genuinely new data. A true check needs new live cycles scored with the rules frozen.']],
    widths=[6.0, 11.0], size=9)

# ===================================================================== appendix
doc.add_heading('Appendix: the figures and what each shows', 1)
table(['Figure', 'Shows', 'Used for'], [
    ['1', 'Scheduled pairs per block, the build-up of lots through D-1, where lots come from by hour, lot unit and timetable edit', 'Section 2'],
    ['2', 'Scheduled straddle lots per slot for every cycle, with the timetable edit', 'Section 3.1'],
    ['3', 'One NIFTY D-1: the two-candle channel, rule breaks and real breakout straddles', 'Section 3.2'],
    ['4', 'Solo selling: bursts, breakout entry size, the state variables that separate solo minutes, reproduction by class', 'Section 3.3'],
    ['5', 'After-15:00 solo sales: coincident conditions, probabilities, variable blocks, rejected explanations', 'Section 3.3'],
    ['6', 'Exits: ratio by holding time, buy-back rate by ratio and sell type, continuation and reversal, in-profit buy-backs', 'Section 4'],
    ['7', 'Protective wings: long lots equal short lots, wing strike rule, which wing is released, lump size', 'Section 5'],
    ['8', 'Overnight lump: clock regimes, size, tail reduction, what happened on expiry day', 'Section 5'],
    ['9', 'Reconstruction accuracy against the real log: by class, book through the day, per cycle, lots by class', 'Section 7'],
    ['10', 'Every accuracy attempt and the ceiling analysis', 'Section 7']],
    widths=[1.6, 11.6, 3.8], size=9)
para('Figures not used here are exploratory plots from the research (intermediate tests, rejected hypotheses, earlier versions of rules that were later replaced). Evidence level for everything: in-sample on 32 cycles unless stated; the forward test (section 7) uses cycles not used for fitting.', size=9, color=GREY)

doc.save('D1_Strategy_Document.docx'); print('saved')
