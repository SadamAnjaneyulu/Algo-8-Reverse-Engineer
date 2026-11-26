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

def why(title, items):
    callout(title, ['\u2022 ' + t for t in items], fill='FFF6E0')

FIGN = [0]
def figure(path, caption, width=16.5):
    FIGN[0] += 1
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next = True; p.add_run().add_picture(path, width=Cm(width))
    c = doc.add_paragraph(); add_runs(c, f'**Figure {FIGN[0]}.** ' + caption, size=9, color=GREY); c.paragraph_format.space_after = Pt(8)

# ===================================================================== title
para('How the strategy behaves on the day before expiry', bold=True, size=22, color=NAVY, after=0)
para('What it sells, how it exits and how it protects itself', size=13, color=GREY, after=4)
para('Research summary for Rahul  |  23 November 2026  |  Based on 32 live expiry cycles (late June to late October 2026), NIFTY and SENSEX index options', size=9.5, color=GREY, after=10)

callout('The short version', [
    '**What it is.** A systematic short-premium strategy on index options. On the session before expiry (we call it **D-1**) it builds a book of short at-the-money (ATM) straddles and single-sided shorts, protects every short with a far out-of-the-money (OTM) long on the same side, stops out individual losing lots, adds a block of extra OTM longs shortly before the close, and carries the book into expiry day. Everything below is read from the strategy\'s order log and the market data. The system is referred to internally as Algo 8.',
    '**Three ways of selling.** (1) **Scheduled straddles**: a fixed clock, 33 straddles a day. (2) **Breakout straddles**: when the spot breaks the range of the last two 30-minute candles, a straddle one strike beyond ATM in the break direction, plus extra lots on the favourable side. (3) **Solo selling**: one-lot sales of the option the market is moving away from, repeated as the move extends.',
    '**Exits.** Each lot has its own stop at about 1.6 times its entry price. Lots that stay below it are carried overnight (68% of sold lots).',
    '**Protection.** Long lots on each side equal the short lots on that side, about 15 to 19 strikes out of the money (the "wings"). Before the close an extra block of longs about 2.2 one-day standard deviations out covers a gap on the heavier side.',
    '**How well we reproduce it.** Rebuilt from the market data alone, the rules rank the minutes where the strategy acts with **AUC 0.96** (0.92 on cycles not used for fitting) and match **68% of its lot decisions** (F1 0.68; 0.63 on unseen cycles) in the right minute and on the right side.'])

# ===================================================================== 1 setting and terms
doc.add_heading('1. The setting and the terms used', 1)
para('The strategy trades weekly index options on two indices, NIFTY (listed strikes every 50 points, one lot = 65 units) and SENSEX (strikes every 100 points, one lot = 20 units). One lot is about Rs 15 lakh of notional on either. Each expiry cycle has two sessions that matter here: **D-1**, the session before expiry day, and **D0**, expiry day itself. This document covers D-1.')
table(['Term', 'Meaning in this document'], [
    ['ATM, strike step', 'The strike nearest the spot. "One strike beyond ATM" means one listed step further in the direction named. The strike step is 50 (NIFTY) or 100 (SENSEX).'],
    ['Straddle', 'A call and a put sold at the same strike. Here usually 1 lot of each.'],
    ['Premium, ratio', 'Premium is an option\'s price. **Ratio** = the option\'s current price divided by the price at which that lot was sold. A short loses money when the ratio is above 1.'],
    ['Stop, buy-back', 'Buying a short lot back (covering). A stop at 1.6 means buying back when the price reaches 1.6 times the sale price.'],
    ['Wing', 'A far out-of-the-money long option bought to cap the loss of a short on the same side (call wings for short calls, put wings for short puts).'],
    ['Right, CE / PE', 'Call (CE) or put (PE).'],
    ['Cycle', 'One expiry: its D-1 and its D0.'],
    ['AUC, F1', 'Accuracy measures. AUC (0.5 = coin flip, 1 = perfect) asks whether the minutes where the strategy acts rank above the others. F1 asks whether a rebuilt order matches a real one (same side, within one minute); it is the harder test.']],
    widths=[3.4, 13.6])
para('**Data.** The complete order log of the strategy for 32 cycles (21 under timetable A, 11 under timetable B; see 3.1) and one-minute open/high/low/close bars for the spot and for every listed option strike.', size=10)
para('**The yellow "Why they do this" boxes** give the purpose of each rule. They are drawn from how the rule behaves in the data and from standard option-selling logic; the strategy\'s designers have not confirmed them.', size=10)

# ===================================================================== 2 the book at a glance
doc.add_heading('2. What the book looks like through D-1', 1)
para('Over a typical D-1 the strategy sells a median of 141 lots (both sides together), buys back some of them, and ends with a median of 104 net short lots. The sells come from three sources: the timetable (median 66 lots), breakout straddles (30) and solo selling (40). Across all 4,671 lots sold in the 32 cycles, **scheduled straddles are 45%, breakout straddles 16% and solo selling 38%**.')
para('The timetable supplies almost all the lots before noon, then thins out; after noon most of the volume comes from breakouts and solo sells. The last sale is at a median 15:25, and 81% of cycles still sell after 15:15. About **68% of the lots sold on D-1 are carried overnight**: a median of 102 short lots in about 11 contracts, against 157 long lots.')
why('Why they do this on the day before expiry', [
    '**The goal is to earn time decay.** An option is worth less every hour as expiry approaches, and an at-the-money option one day from expiry loses most of its remaining value within a session or two. A seller of options collects that decay, and it arrives fastest at the end of an option\'s life.',
    '**So the book is built on D-1 and carried into D0.** The strategy sells through D-1 and holds the lots that have not been stopped into expiry day, where the last of the decay is earned (68% of sold lots are carried; 61% of lots never get close to their stop).',
    '**The price of that decay is risk.** Close to expiry the price of an option reacts sharply to a move in the index (gamma), and a short option can lose many times the premium it collected. Almost every rule below does one of two things: it adds premium, or it limits the loss.'])
figure('figures/fig01_book_buildup_and_sizing.png', 'The book through D-1 (32 cycles). **A:** scheduled pairs per 15-minute block under the two timetable versions (V1 = timetable A, V2 = timetable B). **B:** cumulative lots sold, of which the timetable, and net short after buy-backs (median and range over cycles). **C:** where the lots come from by hour: timetable (green), breakout straddles (orange), solo (purple). **D:** the lot unit is unchanged across the sample; the shaded window is where the timetable was edited.', 17)

# ===================================================================== 3 selling
doc.add_page_break(); doc.add_heading('3. The three ways it sells', 1)
table(['', 'Scheduled straddles', 'Breakout straddles', 'Solo selling'], [
    ['Share of D-1 lots sold', '45%', '16%', '38%'],
    ['What triggers it', 'The clock only', 'Spot breaks the high/low of the previous two completed 30-minute candles (10:30 to 15:15)', 'Spot makes a fresh extreme away from the right being sold (calls on a fresh low, puts on a fresh high), repeated as the move extends'],
    ['What is sold', '1 lot call + 1 lot put', '1 to 3 straddles plus 0 to 7 extra single lots on the favourable side', 'Single lots, mostly 1 lot per order, often in short bursts'],
    ['Strike', 'ATM of the previous minute\'s close', 'ATM of the previous close, shifted one strike in the break direction', 'First sale at ATM; later sales at the strike whose premium is nearest the previous sale on that side']],
    widths=[3.2, 4.0, 4.9, 4.9], size=8.5, bold_first=True)

doc.add_heading('3.1 Scheduled straddles: a fixed clock', 2)
para('**How it executes.** At fixed seconds inside the 15-minute blocks of the session the strategy sells one straddle: 1 lot call and 1 lot put at the same strike, placed within a few seconds of each other. There are **33 such waves a day**, 0 to 4 per 15-minute block, dense in the morning (about 8 an hour) and sparse after noon (2 to 3 an hour). Each wave fires in at least 95% of cycles (all waves under timetable A, 90% of waves under timetable B). Per right that is 33 lots a day, 66 lots in total, in 1-lot orders.')
para('**Which strike.** The ATM strike of the **previous completed minute\'s close**, not the current price and not a delta or forward-based strike. This matches the sold strike exactly 93.6% of the time; the alternatives we tested (call delta nearest 0.5, a delta-neutral straddle, the forward price, the strike with the smallest call-put gap) score 56 to 68%. Repeated waves tend to stay at an already-short strike (87%), and the strike migrates with the market from slot to slot.')
para('**What drives it.** Only the clock. We tested 36 state variables (spot moves, book profit and loss, delta, gamma, vega, implied volatility and its change, inventory, recent buy-backs and solo sales); none changes whether or how much is sold in a slot. The selling continues in every market state.')
para('**Two timetable versions.** Between the D-1 of 9 September and the D-1 of 16 September 2026 seven waves were moved to different seconds; the total stayed at 33 straddles and the lot unit did not change.')
para('**How the lots exit.** Each lot has its own stop (section 4); lots that stay below it are carried overnight.')
why('Why they do this', [
    '**Premium without a market view.** A straddle sells a call and a put at the same strike. It collects both premiums and gains if the index stays near the strike; at the moment of sale the call and put roughly offset each other in direction, so the strategy is not betting on up or down.',
    '**A fixed clock removes timing risk.** Spreading 33 small entries over the session means the average entry level does not depend on any one moment, and no single entry decides the day. The base position exists whatever the market does.',
    '**Small, repeated size.** Each wave is 1 lot per side, so the book builds in small steps and no single order moves the market or commits much capital.',
    '**At the money, on the last completed bar.** The ATM option carries the most time value, so it has the most decay to earn. Using the previous completed minute means the strike comes from a finished price, not a moving one.',
    '**More waves in the morning, fewer after noon.** Building the base early leaves the most session in which to earn decay. Slowing down later limits new at-the-money exposure when little time is left and the cost of a sharp move is higher.'])
figure('figures/fig02_timetable_heatmap.png', 'Scheduled straddle lots per right at each 15-minute slot (columns, from 09:16) for every cycle (rows, by expiry date; N = NIFTY, S = SENSEX). The ladder is the same in every cycle; the red line marks the timetable edit in September (rows below it follow timetable B).', 12.5)

doc.add_heading('3.2 Breakout straddles', 2)
para('**The rule.** From 10:30 to 15:15, each minute is compared with the **highest high and lowest low of the previous two completed 30-minute candles** (the candles are aligned to the clock: 10:00 to 10:30, 10:30 to 11:00, and so on; the current candle is excluded). If the minute\'s high breaks above that range, or its low below it, the strategy sells a straddle (call and put) at the strike **one step beyond ATM in the break direction**, on the **first break per side per candle**. There is no margin: breaking the level by even one NIFTY point counts. Shifting the candle clock by 5 or 15 minutes (the exchange\'s own 09:15-aligned candles) destroys the match, so the candles are aligned at the hour and half hour.')
para('**How many lots.** The size grows with the **depth of the break** beyond the range: on average about 1.1 straddles per entry for a hairline break rising to about 2 for a break of more than a strike step (the rule caps it at 3), plus **extra single lots on the favourable side** (puts on an upside break, calls on a downside break: 315 of 320 observed cases). The average total goes from about 2.4 lots for a hairline break to about 5.7 for a break of more than one strike step.')
para('**How accurate.** The rule reproduces the first entry of each candle side in 93% of cases (90% in the exact minute) and the breakout straddle minutes with F1 0.82 (precision 90%, recall 75%).')
para('**How the lots exit.** Besides the price stop, breakout lots are cut when the breakout **continues**: the leg on the break side is bought back while the spot keeps moving in the break direction (buy-back rate 2.9% a minute against 0.3% otherwise, 7.9% a minute at 1 to 2 steps of continuation), mostly within 5 minutes of the sale.')
why('Why they do this', [
    '**A straddle sold at one level goes lopsided once the market moves.** After an up-move the short calls are losing and the short puts are far from the money and almost worthless. A break of the last hour\'s range marks such a move, so it is the moment the book needs rebalancing.',
    '**A new straddle one strike toward the break re-centres the premium selling on the new price.** At-the-money options at the new level carry fresh time value, so the strategy earns premium where the index now trades rather than where it used to.',
    '**Extra lots go on the side the market is moving away from** (puts on an up-break, calls on a down-break). That side is decaying and is the least likely to be hit, so it is the cheapest place to add premium. A deeper break is a stronger move, so it gets more lots.',
    '**If the break keeps going, the idea has failed.** The new straddle assumes the market settles around the new level. When the move continues against it, those lots are cut within minutes instead of waiting for the 1.6 times stop.',
    '**Two completed 30-minute candles** (one hour of range) keep the trigger to meaningful moves: a shorter range would fire on every wiggle.'])
figure('figures/fig03_breakout_example.png', 'One NIFTY D-1 (8 September 2026). Blue lines: high and low of the previous two completed 30-minute candles. Crosses: the first minute that breaks the level, per side and candle, according to the rule. Triangles: the real breakout straddles. The bars below compare real fires (red), rule fires (black) and the scheduled straddles (grey).', 17)

doc.add_heading('3.3 Solo selling: the drip', 2)
para('**What it is.** Single-sided sales that are not part of a straddle. About **30% of solo decisions place 2 to 8 one-lot orders within 3 seconds**; the rest are single lots. Overall 69% are calls. 21% of solo lots belong to breakout entries (the favourable-side extras above); about 61% are stand-alone intraday sales; and about 18% come after 15:00.')
para('**Trigger (intraday).** A solo **call is sold on a fresh low of the spot, a solo put on a fresh high** (a break over 5 to 60 minutes; 60 minutes on true highs and lows fits best). It happens while the **market is moving away from that side** and while **the own side of the book is in profit and the other side is losing**, typically 1 to 2 minutes after the previous sale on that side, with the last-sold option\'s price dipping about 6% inside the minute. This is a **drip**: one lot each time the spot moves another **0.2 strike steps** beyond the previous reference, gated by a fresh 60-minute extreme.')
para('**Which strike.** The first sale on a side is at ATM. Later sales go to the strike whose **premium is nearest the premium of the previous sale on that side** (within one strike 74% of the time), rather than to the ATM of the day.')
para('**How many lots.** Mostly one lot per order. The number of lots per minute grows with how far the spot has broken beyond its 60-minute extreme (about 1.3 lots for a hairline break, about 6.6 for 0.7 to 1 strike step). The lots are **dripped over about 5 seconds**, one each time the price prints a new extreme inside the minute.')
para('**After 15:00.** Solo sales continue into the close, with spikes at 15:00, 15:23 and 15:29. They use the same trigger plus one input: the sold option\'s **own premium making a fresh 15-minute low**. Into the close time decay and falling volatility push premiums to new lows without a spot extreme, so the strategy also sells on the premium falling. The rule "spot fresh 15-minute extreme or premium fresh 15-minute low" finds 90% of these sales.')
para('**Link to buy-backs.** About 30% of older-lot buy-backs coincide, within 5 seconds, with a new solo sale on the **other** side (base rate 3%): when calls are cut in a rally, puts are sold.')
why('Why they do this', [
    '**Press the side that is working.** When the index moves steadily one way, the option on the other side keeps losing value (calls in a falling market). Each fresh extreme is evidence the move is continuing, so the strategy sells another lot of that option.',
    '**Only where it is already right.** It adds while that side of the book is in profit and the other side is under pressure; it does not add to a losing side.',
    '**Small steps.** One lot per 0.2 strike steps keeps the commitment proportional to how far the move has gone and avoids selling everything at the first sign of a move.',
    '**Strike with a similar premium.** Later sales go to the strike whose premium is near the last sale\'s, so each added lot collects about the same premium as the one before, even as the market moves away.',
    '**After 15:00 the premium itself decays fast.** Into the close time decay pushes premiums to new lows even without a new spot extreme, so a fresh premium low is a signal to sell: it harvests the last hour of decay.',
    '**Counter-sell.** The same move that hurts the calls (a rally) helps the puts, so when calls are bought back, puts are sold: premium keeps being collected on the side the market is moving away from.'])

# ===================================================================== 4 exits
doc.add_heading('4. How positions exit', 1)
para('There is **no scheduled exit** on D-1. Selling and closing are separate processes: the number of lots sold in a slot does not depend on how many were bought back since the last slot (rank correlation -0.04), and only 3.2% of lots sold are re-sales within 60 seconds of a buy-back. Closing is done lot by lot.')
para('**The stop.** Each lot is bought back when its option price reaches a multiple of **its own entry price**. The buy-back rate rises steadily with that ratio: about 1 to 6 buy-backs per 1,000 contract-minutes up to 1.2 times, 12 at 1.2 to 1.4, 37 at 1.4 to 1.55, 74 at 1.55 to 1.7 and 113 at 1.7 to 2.0, and it is nearly certain by 1.7 to 1.8 times. The best single rule is the **minute high reaching about 1.6 times entry** (the current minute\'s high, not the close: the stop reacts to intrabar touches). It is a ratio, not a number of points: the points lost scale with the entry price.')
para('**How many lots per stop.** Lots are bought back one at a time (1-lot orders), the **cheapest-entry (highest-ratio) lots first**; a stop closes the open lots above roughly 1.55 times (71% of stops are within one lot of that), not the whole contract (only 18% of stops close every lot on it). 87% of buy-backs are on lots that are in loss at the decision price; most of the rest are the same-strike partner leg of a stopped straddle or a two-sided cut-back.')
para('**Each sell type has its own exit behaviour** (Figure 4). Scheduled straddle lots follow a price stop (buy-back rate about zero below 1.5 times, then 4%, 15%, 47% a minute above 1.5, 1.6, 1.7 times; fitted threshold 1.6 to 1.65). Breakout lots are cut when the breakout continues. Solo lots are cut when the market reverses (4.8% a minute at 2 or more strike steps of reversal, 2.0% after an opposite two-candle break, against 0.24%). Lots held under 10 minutes exit at about 1.1 times, lots held over 30 minutes at about 1.55 to 1.6 times: the low-ratio exits are fresh directional lots.')
para('**Clusters.** Buy-backs often come as rebalancing events: 67 to 77% come with buy-backs on other strikes of the same right within 5 seconds. A fast adverse move accelerates them: a fresh 30 to 60-minute spot breakout against the position multiplies the buy-back rate about 10 times at every premium level.')
para('**What is carried.** 61% of lots sold on D-1 never reach 1.2 times on a minute close, and 82% of those are carried overnight. That is the 68% of sold lots that end D-1 still short.')
why('Why they do this', [
    '**A short option can lose many times its premium, so every lot needs a limit.** A stop at about 1.6 times the entry price caps the loss on a lot at roughly 60% of the premium collected (before slippage or a gap through the stop).',
    '**Wide, and measured as a ratio.** At-the-money prices fluctuate, so a tight stop would be hit by noise. A ratio to the lot\'s own entry price treats cheap and expensive options alike.',
    '**Per lot, not for the whole book.** A lot sold at a bad moment is closed without disturbing lots that are fine, and cheapest-entry first closes the largest losses.',
    '**The straddle partner is closed with it.** When one leg is stopped, the other leg alone is a directional position, so it is often closed at the same moment (34% of in-profit buy-backs are the same-strike partner).',
    '**Each type of entry is cut when its premise fails.** Breakout lots assume the market settles after the break, so they go when the break continues. Solo lots assume the market keeps moving away, so they go when it reverses. Scheduled lots rest on time alone, so only the price stop applies.',
    '**Lots that never reach the stop are left alone.** They are decaying as intended; closing them would cost the spread and give up the last of the decay. That is why 68% of sold lots are carried into expiry day.'])
figure('figures/fig06_exits_by_sell_type.png', 'Exits. **(a)** Median ratio at buy-back by minutes the lot was held: low-ratio exits are fresh lots. **(b)** Buy-back rate by ratio (minute high divided by own entry), per sell type. **(c)** Breakout lots are cut when the spot keeps going in the entry direction (orange); solo lots when it reverses (green). **(d)** What coincides with buy-backs that are in profit.', 16.5)

# ===================================================================== 5 wings
doc.add_page_break(); doc.add_heading('5. The protective long wings', 1)
para('Every short sold is matched by a long on the same side, so the book is, in effect, **an iron butterfly pooled by right**: the shorts earn the premium and the far-OTM longs cap the loss. There are four kinds of long orders on D-1 (about 7,200 lots in total across the 32 cycles).')
table(['Long order', 'When and how many', 'Which strike', 'Evidence'], [
    ['**1. Controller wings**', 'About **4 seconds after each short is sold**, buy exactly the gap between short lots and long lots on that right (all strikes). Long lots therefore equal short lots on each right all day.', 'The OTM strike whose premium is nearest **2.5% of the ATM option\'s price** on that right (about 15 strikes out for NIFTY, 19 for SENSEX, at about Rs 4.5). Exact strike 65%, within one strike 93%.', 'Quantity equals the gap in 98% of 3,141 buy decisions; long = short in 99% of quiet-time samples (100% from 09:15 to 13:00). Reproduced at F1 0.92 when given the real short orders.'],
    ['**2. Wing releases**', 'When shorts are bought back, sell exactly the excess longs.', 'The outermost or cheapest wing first (44% each against 26% by chance); almost never the innermost.', 'Quantity right in 96% of 500 sell decisions.'],
    ['**3. Opening wings**', 'At 09:16, before the first three scheduled straddles: 1 far call and 1 far put each, about **6 lots per cycle**; sold back during the day.', 'About 39.5 strikes out of the money, median premium Rs 1.4.', '31 of 32 cycles.'],
    ['**4. Overnight lump**', 'One decision between 15:06 and 15:35, split into exchange-size chunks (27 lots NIFTY, 50 lots SENSEX per order, immediate-or-cancel), on the **heavier short side only** in 80% of cycles.', 'About **2.2 one-day standard deviations** out of the money (median 1.5% of spot; premium about Rs 6.2); sigma comes from the ATM straddle price.', 'Size about 0.83 times the heavy-side short lots (NIFTY), 0.50 times (SENSEX).']],
    widths=[2.6, 5.4, 4.9, 4.1], size=8.3)
para('**The lump\'s clock.** The time it is placed moved on fixed dates: 15:06 to 15:14 until 5 August 2026, 15:23 to 15:24 for the cycles of 12 to 19 August, and 15:30 to 15:35 from 24 August. A lump is placed whenever shorts are carried overnight.')
para('**What the lump does.** Before it, a move in the heavier direction would lose a median Rs 29 lakh within a 6% move (value at expiry); after it, Rs 15 lakh. The tail is roughly halved and becomes much more uniform across cycles (coefficient of variation 0.34 to 0.17). It costs about Rs 19,000 per cycle (median).')
why('Why they do this', [
    '**Controller wings cap the loss of every short.** A short option can lose without limit; a long far-out-of-the-money option on the same side turns that into a capped loss (an iron butterfly). Matching long lots to short lots one for one means every short is protected.',
    '**Far out, so cheap.** The wing is chosen to cost about 2.5% of the ATM option\'s price, so each lot keeps about 97% of the premium it collects. Nearer wings would protect more but would cost a large share of the premium; at 15 to 19 strikes out only an extreme move reaches them.',
    '**Bought within seconds.** About 4 seconds after each sale, so no short sits unprotected, even between stops.',
    '**Released when shorts are bought back.** Protection no longer needed is sold, outermost wings first: the outermost are the least protective, so the book keeps the wings that matter most.',
    '**Opening wings before the first sale.** The first straddles go in within seconds of the open, when moves can be large. Very cheap wings (median Rs 1.4) bought first mean the first shorts are never unprotected.',
    '**The overnight lump covers a gap.** Stops cannot act while the market is closed, and a gap can jump straight through them. Before the close the strategy adds a block of longs on the heavier short side, where the exposure is largest, about 2.2 one-day standard deviations out. It costs about Rs 19,000 per cycle (median) and cuts the worst loss in the heavy direction from Rs 29 lakh to Rs 15 lakh.'])
figure('figures/fig07_protective_wings.png', 'Protective wings. **(a)** One NIFTY D-1: short lots (solid) and long lots (dashed) per right; long lots track short lots all day and the overnight lump adds longs after 15:00. **(b)** Wing strike rule: exact-strike hit rate (blue), the same with the reference shuffled (grey) and within-one-strike rate (black tick) for different reference prices; the ATM option price works best. **(c)** Which wing is sold when shorts are bought back (outermost and cheapest, chance 26%). **(d)** Lump size against the heavy-side short lots (blue NIFTY, orange SENSEX; dotted = one for one).', 16.5)
figure('figures/fig08_overnight_lump.png', 'The overnight lump. **(a)** Time of the lump against the D-1 date: three clock regimes. **(b)** Size against heavy-side shorts. **(c)** The lump halves the worst loss in the heavy direction (a move of 0 to 6%, value at expiry). **(d)** On expiry day the lump module itself sold lump lots in 18 of 30 cycles, never above cost (zero = not sold by that module).', 16.5)

# ===================================================================== 6 summary table
doc.add_heading('6. Why each part exists: the whole design in one table', 1)
table(['Part', 'Why they do it', 'What the data shows'], [
    ['Build the book on D-1 and carry it', 'Earn the fastest part of time decay, at the end of the options\' life.', '68% of sold lots carried; 61% of lots never reach 1.2 times.'],
    ['Scheduled ATM straddles on a fixed clock', 'Collect premium with no market view and no timing risk; build a base position in small, evenly spread steps.', 'Each wave fires in at least 95% of cycles; no market or book variable changes it (36 tested).'],
    ['Breakout straddles one strike toward the break, with favourable-side extras', 'Re-centre the premium selling on the new price after a move; lean on the side that is losing value.', 'Strike shifts with the break; extras on the favourable side in 315 of 320 cases; size rises with depth.'],
    ['Solo drip of 1-lot sales', 'Press the side that is working, in small steps, only where the book is already in profit; harvest the last hour of decay.', 'Triggered by fresh extremes while the own side is in profit and the other side is losing.'],
    ['Per-lot stop at about 1.6 times', 'Limit the loss on each short; leave the rest of the book alone; let decaying shorts run.', 'Buy-back rate climbs with each lot\'s own ratio; 87% of buy-backs are in loss.'],
    ['Cut breakout lots on continuation, solo lots on reversal', 'Close a directional entry as soon as its premise fails.', 'Buy-back rate 10 to 25 times higher in those states.'],
    ['Wings equal to shorts, far out of the money', 'Cap the loss of every short at a small cost (2.5% of the ATM price).', 'Long = short in 99% of quiet samples; the quantity is the gap in 98% of decisions.'],
    ['Opening wings at 09:16', 'Make sure the first shorts of the day are never unprotected.', 'In 31 of 32 cycles, about 6 lots, median premium Rs 1.4.'],
    ['Overnight lump on the heavier side', 'Cover a gap that the stops cannot act on while the market is closed.', 'About 2.2 sigma out; worst case Rs 29 lakh to Rs 15 lakh; cost about Rs 19,000 per cycle.']],
    widths=[4.4, 6.6, 6.0], size=8.5)
para('**Taken together:** the strategy sells time decay on the day before expiry and carries what has not been stopped into expiry day. It adds premium three ways (by clock, by breakout, by drip). It limits the loss of each lot with a ratio stop and the loss of each short with a wing, and it adds one extra layer of protection before holding the book through the night.')

# ===================================================================== 7 accuracy
doc.add_heading('7. How well we reproduce it', 1)
para('We rebuilt the whole D-1 as a rule-based program that sees only the market data (spot and option one-minute bars) and never the real orders, then compared its orders with the real ones, lot by lot (same side and class, within one minute of the real order).')
table(['Measure', 'Result'], [
    ['**AUC**, is the strategy active in this minute (all D-1 activity)', '**0.96** on the 32 cycles; **0.92** on cycles not used for fitting (0.91 after a timetable change)'],
    ['**Lot-level F1**, all D-1 lots', '**0.68** (precision 78%, recall 61%; 8,368 of 13,655 real lots matched); **0.63** on cycles not used for fitting'],
    ['Strike also right (within one step / exact)', 'F1 0.62 / 0.45'],
    ['Book through the day (short and long lots per right)', 'Correlation 0.83 / 0.89 with the real book']],
    widths=[8.4, 8.6], size=9)
para('AUC by activity (95% confidence intervals from resampling cycles):')
table(['Activity', 'AUC'], [
    ['Body sells (all three types)', '0.977 (0.972 to 0.981)'],
    ['Body buy-backs', '0.915 (0.890 to 0.934)'],
    ['Wing buys (given the real body orders)', '0.996 (0.993 to 0.998)'],
    ['Wing releases (given the real body orders)', '0.997 (0.992 to 1.000)'],
    ['Opening wings', '0.932 (0.904 to 0.958)'],
    ['Overnight lump', '0.958 (0.920 to 0.984)'],
    ['**Any D-1 activity**', '**0.961 (0.955 to 0.967)**']],
    widths=[8.4, 8.6], size=9)
figure('figures/fig09_reconstruction_accuracy.png', 'Reconstruction against the real D-1 order log. **(a)** F1 by class: timing (blue), timing plus strike within one step (green), timing plus exact strike (orange); black diamonds = the hedge rules given the real body orders. **(b)** Short and long lots through the day, real vs rebuilt (mean over cycles). **(c)** F1 per cycle (blue NIFTY, orange SENSEX; dashed = overall). **(d)** Lots by class, real vs rebuilt. "h_" = protective wing orders, "v_" = overnight lump.', 16.5)
doc.add_heading('The Python code', 2)
para('The accompanying package (`d1_strategy/`) is the strategy written the way it would be built to run: an **event-driven algo engine** (`d1_algo`) that reads prices every second, builds one-minute bars, applies the rules using only the information available at that second, and sends orders to a broker. It contains:')
bullets([
    '**Interfaces** for the two things a live deployment must supply: market data (index price, option prices, listed strikes) and a broker (place order, fills, positions).',
    '**The rules**: opening wings, the scheduled-straddle clock, the two-candle breakout, the solo ladder, per-lot stops, the wing controller and the overnight lump, in that order each second.',
    '**A position book** with every short lot and its entry price, the wings and the lump, plus pending-order counts so wings are never ordered twice.',
    '**A risk guard**: kill-switch file, halt flag, short-lot limit, orders-per-minute limit, valid-price check, and splitting at the exchange freeze quantity (27 lots NIFTY, 50 SENSEX).',
    '**A state file** so the engine can restart mid-session, and a paper broker and replay feed so it can be run and tested without a broker.',
    '**A template for a live broker adapter** (nothing in the package talks to a broker until one is implemented and tested).'])
para('**Checked on the real data:** the one-minute bars of the 32 D-1 sessions were replayed second by second through the engine with the paper broker. Its orders matched the real order log with **lot-level F1 0.69 (precision 75%, recall 64%)**, the same as the batch reconstruction; the earlier forward test of the same rules gave 0.63 on cycles not used for fitting. The package has 10 engine tests (clock and ATM strike, late waves, wings equal shorts, breakout once per side per candle, stop, ladder, kill switch, order splitting, restart state, full-day invariants).')

# ===================================================================== 8 D0
doc.add_heading('8. Moving to D0', 1)
para('D0, expiry day, is where the book built on D-1 is managed and closed. It is **much more complex than D-1**: where D-1 has three ways of selling, D0 has nine; buy-backs follow eight different reasons instead of one graded stop; the timetable differs by index and adds 14 extra marks; and a cycle-level stop module and a 15:14 clearance sit on top. The D0 work is the next phase.')

# ===================================================================== appendix
doc.add_heading('Appendix: the figures and what each shows', 1)
table(['Figure', 'Shows', 'Used for'], [
    ['1', 'Scheduled pairs per block, the build-up of lots through D-1, where lots come from by hour, lot unit and timetable edit', 'Section 2'],
    ['2', 'Scheduled straddle lots per slot for every cycle, with the timetable edit', 'Section 3.1'],
    ['3', 'One NIFTY D-1: the two-candle channel, rule breaks and real breakout straddles', 'Section 3.2'],
    ['4', 'Exits: ratio by holding time, buy-back rate by ratio and sell type, continuation and reversal, in-profit buy-backs', 'Section 4'],
    ['5', 'Protective wings: long lots equal short lots, wing strike rule, which wing is released, lump size', 'Section 5'],
    ['6', 'Overnight lump: clock regimes, size, tail reduction, what happened on expiry day', 'Section 5'],
    ['7', 'Reconstruction accuracy against the real log: by class, book through the day, per cycle, lots by class', 'Section 7']],
    widths=[1.6, 11.6, 3.8], size=9)

doc.save('D1_Strategy_Document.docx'); print('saved')
