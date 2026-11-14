"""M2-E case studies: predefined structural selection (pe.cases), forensic records, per-case episode charts, and reports/M2E_POSITION_CASE_STUDIES.md (generated; no hand-typed numbers).
python3 portfolio_engine/tools/m2e_cases.py"""
import json, os, sys, importlib
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python')); sys.path.insert(0, HERE)
from pe import forensics as F, cases as K
CH = importlib.import_module('m2e_charts')
DATA = os.path.join(PE, 'reports', 'm2e_data')


def short(item_id): _, _, p, i = K.item_parts(item_id); x = i.split('|'); return f'{p} {x[2]}{x[3]}'


def render(rec, cy):
    if rec['status'] != 'AVAILABLE': return f"### {rec['case_type']} — **UNAVAILABLE**\n\n* Rule: {rec['selection_rule']}\n* Reason: {rec['reason']}\n"
    lc = rec['lifecycle']; from collections import Counter; ev = Counter(e['event'] for e in lc); fl = rec['fills']
    o = [f"### {rec['case_type']} — {rec['position_id']}", '', f"* **Selection rule (predefined, outcome-free; chronological first qualifying candidate whose episode was not already used by an earlier case type):** {rec['selection_rule']}" + (f" — *{rec['selection_note']}*" if rec['selection_note'] else ''),
         f"* **Instrument:** {rec['instrument_id']} ({rec['direction']}); **lifecycle events:** " + ', '.join(f'{k} {v}' for k, v in sorted(ev.items())) + f"; started by reversal: {rec['started_by_reversal']}; ended by: {rec['ended_by']}",
         f"* **Quantity:** opened {rec['opened']:,} · closed {rec['closed']:,} · remaining {rec['remaining']:,} · terminal status **{rec['terminal_status']}**",
         f"* **First → last event (IST):** {lc[0]['ts_ist']} ({lc[0]['event']}, inventory {lc[0]['inventory_after']:+d}) → {lc[-1]['ts_ist']} ({lc[-1]['event']}, inventory {lc[-1]['inventory_after']:+d})",
         f"* **Fill IDs ({len(fl)}):** " + ', '.join(f['fill_id'] for f in fl), f"* **Opening parents ({len(rec['opening_parents'])}):** " + ', '.join(rec['opening_parents'][:12]) + (f" … (+{len(rec['opening_parents']) - 12})" if len(rec['opening_parents']) > 12 else ''),
         f"* **Closing parents ({len(rec['closing_parents'])}):** " + ', '.join(rec['closing_parents'][:12]) + (f" … (+{len(rec['closing_parents']) - 12})" if len(rec['closing_parents']) > 12 else ''),
         f"* **Convention:** {rec['convention']['observed_layer']}; {rec['convention']['closing_portions']} closing portions, {rec['convention']['closing_portions_convention_sensitive_FIFO_vs_LIFO']} attribute to different opening lots under FIFO vs LIFO; AVG {rec['convention']['avg']}"]
    for x in rec.get('related_reversal_episodes', []): o.append(f"* **Related reversal episode:** `{x['episode_id']}` ({x['direction']}, opened {x['opened']:,} · closed {x['closed']:,} · remaining {x['remaining']:,}; started by reversal: {x['started_by_reversal']}; ended by: {x['ended_by']}). The reversing fill is split between the two episodes; its opening portion belongs to the successor.")
    for m in ('C1', 'C2'):
        b = rec['closing_batch_association_10s'][m]; ids = sorted({x['batch_id'] for x in b})
        o.append(f"* **Closing batch {m} (10 s):** {len(rec['closing_parents'])} closing parents fall in {len(ids)} batch(es)" + (f"; batch sizes (parents) {sorted({x['batch_n_parents'] for x in b})}, durations (s) {sorted({x['batch_duration_s'] for x in b})}" if b else '') + (f"; first: `{ids[0].split('@')[1]}`" if ids else ''))
    wb = rec['wing_body_candidates']; inscope = [w for w in wb if 'item_id' in w]; out = [w for w in wb if 'item_id' not in w]
    c1 = lambda w, m: len(w[m]); o.append(f"* **Wing/body (opening items of this position):** {len(inscope)} in M2-D tagged scope (items with an opening allocation in this episode), {len(out)} outside it (module tag unclassified: not a claim of no wing). W1 candidates: none for {sum(1 for w in inscope if c1(w, 'W1') == 0)}, one for {sum(1 for w in inscope if c1(w, 'W1') == 1)}, several for {sum(1 for w in inscope if c1(w, 'W1') >= 2)}; W1_S60: none {sum(1 for w in inscope if c1(w, 'W1_S60') == 0)}, one {sum(1 for w in inscope if c1(w, 'W1_S60') == 1)}, several {sum(1 for w in inscope if c1(w, 'W1_S60') >= 2)}")
    if rec['anchor'] and rec['anchor'].startswith('WBI'):
        a = next(w for w in inscope if w['item_id'] == rec['anchor']); o.append(f"* **Anchor item:** `{short(rec['anchor'])}` ({a['role']}, {a['quantity']} units, tag role {a['tag_role']})")
        for m in ('W1', 'W1_S60'):
            L = a[m]; o.append(f"  * {m} candidates: {len(L)}" + (' — ' + '; '.join(f"{short(x['counterpart'])} (dt {x['dt_s']:+d}s, qty ratio {float(x['qty_ratio']):.2f})" for x in L[:5]) + (f"; +{len(L) - 5} more" if len(L) > 5 else '') if L else ' (none)') + (f" — *{L[0]['evidence_class']}*" if L else ' — an empty candidate set is a finding about THIS method only; it does not show that no wing existed'))
        o.append(f"  * W2 weighted units (weights, not allocations): " + (', '.join(f"{short(x['counterpart'])} {float(x['weighted_wing_units']):.2f}" for x in a['W2_weighted_units'][:5]) or 'none') + f"; W3 queue-matched units (queue arithmetic, not ownership): " + (', '.join(f"{short(x['counterpart'])} {float(x['queue_matched_units']):g}" for x in a['W3_queue_matched_units'][:5]) or 'none'))
    if rec['anchor'] and rec['anchor'].startswith('INF:CLOSING'): o.append(f"* **Anchor batch:** `{rec['anchor'].split('@')[1]}`")
    o += ['* **Evidence class:** lifecycle CONFIRMED_OBSERVATION · batch = temporal clustering only (decision UNRESOLVED) · W1 WEAKLY_SUPPORTED · W1_S60 UNRESOLVED · W3 UNRESOLVED · lot ownership / protective intent UNRESOLVED',
          '* **Missing information:** ' + '; '.join(rec['missing_information']), '* **Can conclude:** ' + '; '.join(rec['can_conclude']), '* **Cannot conclude:** ' + '; '.join(rec['cannot_conclude']), '', f"![{rec['case_type']}](../reports/m2e_figures/{cy}/cases/{rec['case_type']}.png)".replace('../reports/', ''), '']
    return '\n'.join(o)


def main():
    out = {}; md = ['# M2-E — Position case studies', '', '**Purpose:** make single positions inspectable. **Not** an explanation of why Algo 8 acted: no rationale is offered or inferred.', '',
                    '## 1. Selection method (fixed before any case was looked at)', '', 'Candidates are scanned **chronologically** (first fill time, then id) and the **first qualifying candidate whose episode was not already used by an earlier case type** is taken (reuse only if every qualifying candidate was used; any skipped chronologically-first candidate is named in the case note). Profit, loss, price and every outcome are never consulted. A case type with no qualifying candidate in a cycle is **UNAVAILABLE** for that cycle (never borrowed from the other cycle). Rules (`pe/cases.py`, `RULES`):', '', '| Case type | Rule |', '|---|---|'] + [f'| {n} | {r} |' for n, r in K.RULES]
    avail = {}; cman = {}
    for und, exp in F.CYCLES:
        cy = F.cycle_key(und, exp); c = F.Cycle(REPO, und, exp); D = K.load_data(os.path.join(DATA, cy)); S = K.select(D); recs = {n: K.record(c, D, n, S[n]) for n in S}; out[cy] = recs; avail[cy] = S; cman[cy] = []
        for n, r in recs.items():
            if r['status'] == 'AVAILABLE':
                E = {e['episode_id']: e for e in D['episodes']}; me = E[r['position_id']]; ids = {r['position_id']}
                for e in D['episodes']:     # a reversal ends one episode and starts another on the SAME instrument at the same instant: show both, never a plain close
                    if e['instrument_id'] == me['instrument_id'] and ((e['started_by_reversal'] == '1' and e['first_ts_utc_s'] == me['last_ts_utc_s'] and me['ended_by'] == 'reversal') or (me['started_by_reversal'] == '1' and e['ended_by'] == 'reversal' and e['last_ts_utc_s'] == me['first_ts_utc_s'])): ids.add(e['episode_id'])
                e_ = CH.v2(cy, ids, f'cases/{n}'); e_['case_type'] = n; cman[cy].append(e_); r['chart_episode_ids'] = sorted(ids)
        json.dump(dict(cycle=cy, version=F.VERSION, figures=cman[cy]), open(os.path.join(CH.FIG, cy, 'case_figure_manifest.json'), 'w'), indent=1)
        json.dump(dict(cycle=cy, selection_rules=dict(K.RULES), selection=S, records=recs), open(os.path.join(DATA, cy, 'case_studies.json'), 'w'), indent=1, default=str)

    md += ['', '## 2. Availability by cycle', '', '| Case type | ' + ' | '.join(F.cycle_key(*c) for c in F.CYCLES) + ' |', '|---|' + '---|' * len(F.CYCLES)]
    for n, _ in K.RULES:
        cells = []
        for und, exp in F.CYCLES:
            s = avail[F.cycle_key(und, exp)][n]; cells.append(f"`{s['episode_id'].replace('|', chr(92) + '|')}`" + (' (reused)' if s['note'].startswith('reuses') else ' (earlier-chronological candidate skipped; see case note)' if s['note'] else '') if s['status'] == 'AVAILABLE' else '**UNAVAILABLE**')
        md.append(f'| {n} | ' + ' | '.join(cells) + ' |')
    md += ['', 'UNAVAILABLE items are reported, not substituted. Neither frozen cycle has a position that expired unclosed; SENSEX has no reversal.', '', 'Every case below links to a single-episode V2 chart (`m2e_figures/<cycle>/cases/<case>.png` + its CSV). Full records (all fills, all candidates, all batch rows): `m2e_data/<cycle>/case_studies.json`.', '']
    for und, exp in F.CYCLES:
        cy = F.cycle_key(und, exp); md += [f'## 3. {cy.replace("_", " ")}', '']
        for n, _ in K.RULES: md += [render(out[cy][n], cy), '']
    open(os.path.join(PE, 'reports', 'M2E_POSITION_CASE_STUDIES.md'), 'w').write('\n'.join(md) + '\n'); print(len('\n'.join(md).splitlines()), 'lines'); [print(cy, {n: r['status'] for n, r in v.items()}) for cy, v in out.items()]


main()
