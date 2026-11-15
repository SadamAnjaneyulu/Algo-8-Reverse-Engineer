"""R1 disclosure addenda: APPENDS a dated 'R1 ADDENDUM' section to the historical reports (earlier text is never edited; idempotent via a marker). Numbers come from reports/r1_tie_order/r1_tie_order_sensitivity.json.
python3 portfolio_engine/tools/r1_addenda.py [--dry-run]"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE)
P = json.load(open(os.path.join(PE, 'reports', 'r1_tie_order', 'r1_tie_order_sensitivity.json')))['policies']; MARK = '## R1 ADDENDUM'
dry = '--dry-run' in sys.argv; n = lambda x: f'{x:,}'
ORDER = ['sells_first', 'buys_first', 'trade_id', 'order_no', 'sensex_trade_id_time']
COMMON = ('**Convention.** Source timestamps have one-second resolution. All lineage, closing-batch, wing/body and forensic outputs use **`SOURCE_ROW_ORDER_CONVENTION`**: fills of the same instrument within the same second are processed in source-file row order. '
          'This is a deterministic convention, **not verified intra-second execution chronology**. Under the sensitivity-only policies (`sells_first`, `buys_first`, `trade_id`, `order_no`, `sensex_trade_id_time`) aggregate opening/closing units, final inventory and cash are unchanged, '
          'but episode identity, reversal counts, opening/closing allocation membership, FIFO/LIFO attribution, closing-batch membership and wing/body membership can change for a small number of instruments. These must not be treated as order-independent facts. '
          '**No number in this report changed**; the delivered outputs are byte-identical to the pre-R1 baseline except for a `tie_order_convention` field added to four manifests. Full evidence and the five separately reported populations: `reports/R1_TIE_ORDER_CONVENTION.md`.')


def lineage_table():
    t = ['| Policy | Fills whose open/close split changes | Episodes changed | Instruments changed | Reversal-ended episodes (primary 23) |', '|---|---:|---:|---:|---:|']
    for k in ORDER: a = P[k]['2_groups_changing_open_close_allocation']; e = P[k]['3_episode_identity']; t.append(f"| `{k}` | {a['fills_changed']} | {e['episodes_changed']} | {e['instruments_changed']} | {e['reversal_episodes_alt']} |")
    return '\n'.join(t)


def batch_table():
    t = ['| Policy | Batches not in the alternative @2 / 5 / 10 / 30 / 60 s (C1 = C2; baseline 7,127 / 3,777 / 3,065 / 2,171 / 1,502) |', '|---|---|']
    for k in ORDER: b = P[k]['4_closing_batch_membership']; t.append(f"| `{k}` | " + ' / '.join(str(b[f'C1@{s}s']['baseline_batches_not_in_alternative']) for s in (2, 5, 10, 30, 60)) + ' |')
    return '\n'.join(t)


def wb_table():
    t = ['| Policy | Items only in one | W1 | W1_S60 | W2 | W2_S60 | W3 links changed | Opening / closing body units (primary 626,765 / 540,250) |', '|---|---:|---:|---:|---:|---:|---:|---|']
    for k in ORDER: w = P[k]['5_wing_body_membership']; lc = w['links_changed']; t.append(f"| `{k}` | {w['items_only_in_one']} | {lc['W1']} | {lc['W1_S60']} | {lc['W2']} | {lc['W2_S60']} | {lc['W3']} | {n(w['opening_body_units'])} / {n(w['closing_body_units'])} |")
    return '\n'.join(t)


M2B_NOTE = ('**What this supersedes.** The sentence above that quotes "20 fills (42 rows) in 5 instruments" under `sells_first` / `buys_first` counted a broader, differently defined population (it states that it includes downstream fills of the affected instruments). R1 did **not** reproduce the "20 fills / 42 rows" count under its populations '
            '(`sells_first`: 2 fills whose open/close split changes; `buys_first`: 4); its 5-instrument count equals R1\'s `buys_first` instrument count. The M2-F note that this figure "reproduced exactly" was not verified. Use the R1 populations below for interpretation.')
BLOCKS = {
 'reports/M2B_REPORT.md': [COMMON, M2B_NOTE, lineage_table()],
 'reports/M2B_RECONCILIATION_REPORT.md': [COMMON, M2B_NOTE, lineage_table()],
 'docs/POSITION_LINEAGE_RULES.md': ['**Rule.** The fill-order rule inside one second is the declared convention **`SOURCE_ROW_ORDER_CONVENTION`** (source-file row order), implemented as the engine tie order `src` (alias `source_row`). ' + COMMON.split('**Convention.** ')[1], lineage_table()],
 'reports/M2C_CLOSING_BATCH_REPORT.md': [COMMON, '**Closing-batch consequence (replay-level tie order).** Which fills are closing portions depends on the replay order of same-second fills, so batch membership is conditional on the convention. This is **distinct** from the approved parent-ordering tie-break and the C2 predecessor reference measured in §3 of this report.', batch_table(),
                                         'C1 and C2 change identically. Thresholds, rules and all primary outputs are unchanged.'],
 'reports/M2D_WING_BODY_REPORT.md': [COMMON, '**Wing/body consequence.** Items and links are built from opening/closing portions, so membership and the headline integers (e.g. 626,765 opening body units) are conditional on the convention.', wb_table(), 'No evidence class changes: W1 stays WEAKLY_SUPPORTED, W1_S60 and W3 UNRESOLVED, lot ownership and protective intent UNRESOLVED / NOT_TESTABLE.'],
}


def main():
    for rel, parts in BLOCKS.items():
        path = os.path.join(PE, rel); s = open(path).read()
        if MARK in s: print('already present', rel); continue
        block = '\n\n' + MARK + ' — intra-second fill-order convention (appended 2026-11-15; earlier text unchanged)\n\n' + '\n\n'.join(parts) + '\n'
        if not dry: open(path, 'w').write(s.rstrip('\n') + block)
        print('appended' if not dry else 'dry-run', rel)


main()
