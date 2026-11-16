"""Builds the six plots for the portfolio-construction prototype, each with its data exported next to it.
  python3 tools/make_plots.py <out_dir>
All new-engine plots use SYNTHETIC scenarios (labelled on the figure). Plot 1 is a diagram of the system, not data."""
import csv, os, sys, textwrap
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'python'))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pc import generators as G
from pc.engine import Simulation

OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
INK, MUTED, EDGE = '#1f2933', '#52606d', '#334155'
BLUE, GREEN, AMBER, RED, GREY, VIOLET = '#dbeafe', '#d1fae5', '#fde68a', '#fecaca', '#e5e7eb', '#e9d5ff'
SYN = 'Synthetic example: simulation output from a generated scenario, not historical Algo 8 behaviour'
SC = G.all_scenarios()
RUN = {n: Simulation(s).run() for n, s in SC.items()}


def tsv_rows(sim, key):
    h, *r = [l.split('\t') for l in sim.files()[key].split('\n') if l and not l.startswith('#')]; return [dict(zip(h, x)) for x in r]


def save_csv(name, cols, rows, origin=None):
    """origin: a fixed text for every row, or a function row -> text. Every data file carries a data_origin column so its provenance travels with it."""
    with open(os.path.join(OUT, name), 'w', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n'); w.writerow(list(cols) + ['data_origin'])
        for r in rows: w.writerow(list(r) + [origin(r) if callable(origin) else origin])


def box(ax, x, y, w, h, title, body, fc, tsize=10.5, bsize=8.8, wrap=26):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.1', fc=fc, ec=EDGE, lw=1.3))
    ax.text(x + w / 2, y + h - 0.18, title, ha='center', va='top', fontsize=tsize, fontweight='bold', color=INK)
    ax.text(x + w / 2, y + h - 0.62, '\n'.join(textwrap.fill(p, wrap) for p in body.split('\n')), ha='center', va='top', fontsize=bsize, color=INK, linespacing=1.3)


def arrow(ax, x1, y1, x2, y2, style='-|>', color=EDGE, ls='-'):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=15, lw=1.8, color=color, linestyle=ls))


# ---------------------------------------------------------------- 1. architecture
HIST, PROTO = 'historical reconstruction', 'portfolio-construction prototype'
COMP = [('Historical fills (observed)', HIST, 'data', 'external, not in this ZIP'), ('Validation + ordering', HIST, 'Python + C++', 'reconstruction engine'), ('Replay / PortfolioState.apply_fill', HIST, 'Python + C++', 'the one position state'),
        ('Lineage, closing batches, wing/body links', HIST, 'Python', 'reconstruction outputs'), ('Synthetic scenarios', PROTO, 'scenario files', 'synthetic examples'), ('Simulation loop', PROTO, 'Python + C++', 'prototype'),
        ('Plugin registry', PROTO, 'Python + C++', 'prototype'), ('basket_cut / basket_reentry / scripted_actions / your own plugins', PROTO, 'Python + C++', 'sample policies you can change'),
        ('Risk validator', PROTO, 'Python + C++', 'prototype'), ('Basket book (claims + cut lineage)', PROTO, 'Python + C++', 'prototype'), ('Decision / action / state / lineage logs', PROTO, 'Python + C++', 'identical from Python and C++')]
save_csv('01_architecture_components.tsv', ['component', 'part', 'language', 'role'], COMP, lambda r: 'historical observations (external, not included in this ZIP)' if r[2] == 'data' else ('synthetic scenario files' if r[2] == 'scenario files' else ('code that processes historical data' if r[1] == HIST else 'code that processes synthetic scenarios')))
fig, ax = plt.subplots(figsize=(15.5, 8.4)); ax.set_xlim(0, 15.5); ax.set_ylim(0, 8.4); ax.axis('off')
ax.text(7.75, 8.2, 'Architecture: historical position reconstruction + portfolio-construction prototype', ha='center', va='top', fontsize=15, fontweight='bold', color=INK)
ax.text(7.75, 7.72, 'Left: positions rebuilt from the observed Algo 8 fills. Right: the prototype, which runs on synthetic scenarios. The two parts meet at the ledger (PortfolioState.apply_fill).', ha='center', va='top', fontsize=10, color=MUTED)
ax.add_patch(FancyBboxPatch((0.3, 0.5), 4.4, 6.8, boxstyle='round,pad=0.02,rounding_size=0.12', fc='#f8fafc', ec='#94a3b8', lw=1.2)); ax.text(2.5, 7.12, 'Historical position reconstruction (observed fills)', ha='center', fontsize=11, fontweight='bold', color=INK)
for k, (t, b, c) in enumerate([('Historical fills (observed)', 'trade export + ledger (external, not in this ZIP)', GREY), ('Validation + ordering', 'Python + C++', GREEN), ('Replay / accounting', 'apply_fill (Python + C++):\nthe only place inventory changes', GREEN), ('Reconstruction outputs', 'lineage, closing batches, wing/body, case studies (Python)', BLUE)]):
    box(ax, 0.55, 5.55 - k * 1.5, 3.9, 1.25, t, b, c, wrap=34); (arrow(ax, 2.5, 5.55 - k * 1.5, 2.5, 5.55 - k * 1.5 - 0.2) if k < 3 else None)
ax.add_patch(FancyBboxPatch((5.4, 0.5), 9.8, 6.8, boxstyle='round,pad=0.02,rounding_size=0.12', fc='#fffbeb', ec='#d97706', lw=1.2)); ax.text(10.3, 7.12, 'Portfolio-construction prototype (synthetic scenarios)', ha='center', fontsize=11, fontweight='bold', color=INK)
box(ax, 5.65, 5.2, 2.9, 1.6, 'Synthetic scenarios', '13 scenario files: 9 named cases, a lifecycle demo, 3 fixed-seed stress runs', VIOLET, bsize=8.3); box(ax, 5.65, 3.35, 2.9, 1.6, 'Simulation loop', 'at each time t plugins see only data up to t (Python + C++)', AMBER, bsize=8.3)
box(ax, 9.1, 5.2, 2.9, 1.6, 'Plugin registry', 'register, enable, configure; rejects duplicates and bad versions', AMBER, bsize=8.3); box(ax, 9.1, 3.35, 2.9, 1.6, 'Plugins', 'basket_cut, basket_reentry, scripted_actions, drop-ins', AMBER, bsize=8.3)
box(ax, 12.35, 3.35, 2.6, 1.6, 'Risk validator', 'prototype limits, lineage, cooldown, look-ahead', RED, bsize=8.3); box(ax, 12.35, 5.2, 2.6, 1.6, 'Basket book', 'claims on inventory and cut lineage', AMBER, bsize=8.3)
box(ax, 5.65, 1.25, 9.3, 1.5, 'Accepted actions become NEW synthetic fills', 'events.tsv (the same format the reconstruction engine reads) -> PortfolioState.apply_fill. Logs: decisions, actions, states, lineage, summary (identical from Python and C++).', GREEN, wrap=100)
arrow(ax, 7.1, 5.2, 7.1, 4.97); arrow(ax, 8.55, 4.15, 9.1, 4.15); arrow(ax, 10.55, 5.2, 10.55, 4.97, style='<|-'); arrow(ax, 12.0, 4.15, 12.35, 4.15); arrow(ax, 13.65, 3.35, 13.65, 2.77); arrow(ax, 13.65, 5.2, 13.65, 4.97, style='<|-')
arrow(ax, 5.65, 2.0, 4.5, 3.6, color='#b45309'); ax.text(5.55, 0.62, 'Bias controls: every row records what was configured, which plugin decided and what risk validation rejected.\nLook-ahead, ordering, duplicates, lineage and limit bypass are tested.', fontsize=8.5, color=MUTED)
for k, (c, l) in enumerate([(GREY, 'historical data (external)'), (VIOLET, 'synthetic scenario data'), (GREEN, 'engine code (Python + C++)'), (AMBER, 'prototype components'), (RED, 'risk validation')]):
    ax.add_patch(FancyBboxPatch((0.35 + k * 2.95, 0.12), 0.22, 0.22, boxstyle='round,pad=0.01', fc=c, ec=EDGE)); ax.text(0.65 + k * 2.95, 0.23, l, fontsize=8.5, va='center', color=INK)
ax.text(0.3, -0.12, 'Historical observations are confined to the reconstruction part. The prototype\'s scenarios and simulation outputs are synthetic examples.', fontsize=9, color=MUTED)
fig.savefig(os.path.join(OUT, '01_architecture.png'), dpi=160, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------------------------------------------------------------- 2. basket lifecycle
sim = RUN['s11_basket_lifecycle_demo']; st = tsv_rows(sim, 'states.tsv'); act = tsv_rows(sim, 'actions.tsv'); base = min(int(r['ts']) for r in st)
source_of = {a['action_id']: a['plugin'] for a in act}
by_event = {}
for r in st:
    if r['event_id'] not in ('-',): by_event.setdefault(r['event_id'], []).append(r)
life = []                      # (minutes, total units held by the basket, status, event, action, who proposed it)
for ev, rs in by_event.items():
    life.append(((int(rs[0]['ts']) - base) / 60, sum(int(x['qty_after']) for x in rs), rs[0]['basket_status'], ev, rs[0]['action_id'], source_of.get(rs[0]['action_id'], 'scenario seed fill')))
life = sorted(life, key=lambda x: (x[0], x[3]))
save_csv('02_basket_lifecycle.tsv', ['minutes_since_creation', 'basket_total_units_after', 'basket_status', 'event_id', 'action_id', 'action_source'], life, 'synthetic simulation: s11_basket_lifecycle_demo')
fig, ax = plt.subplots(figsize=(12, 5.6)); colors = {'ACTIVE': '#34d399', 'PARTIALLY_CUT': '#fbbf24', 'FULLY_CUT': '#f87171'}; shapes = {'scenario seed fill': 's', 'basket_cut': 'o', 'scripted_actions': 'D', 'basket_reentry': '^'}
xs = [x[0] for x in life]; ys = [x[1] for x in life]; ax.step(xs, ys, where='post', color=EDGE, lw=1.6)
for x, y, s_, ev, aid, src in life: ax.scatter([x], [y], color=colors[s_], marker=shapes[src], s=60, zorder=3, edgecolor=EDGE)
for lab, minute in (('creation\n(seed fills from the scenario)', 0), ('partial cut\n(basket_cut plugin, 1/3 of each leg)', 5), ('full cut\n(scripted_actions, rest of each leg)', 15), ('re-entry\n(scripted_actions, 65 units of the\nshort CE, cites the first cut)', 25)):
    ax.axvline(minute, color='#cbd5e1', ls=':'); ax.text(minute + 0.2, max(ys) * 1.03, lab, fontsize=8.5, color=MUTED, va='bottom')
leg1 = ax.legend(handles=[plt.Line2D([], [], marker='o', ls='', color=c, markeredgecolor=EDGE, label=s_) for s_, c in colors.items()], title='basket status after the event', fontsize=8.5, loc='center right'); ax.add_artist(leg1)
ax.legend(handles=[plt.Line2D([], [], marker=m, ls='', color='#cbd5e1', markeredgecolor=EDGE, label=k) for k, m in shapes.items() if k in {x[5] for x in life}], title='who produced the event', fontsize=8.5, loc='upper right', bbox_to_anchor=(1.0, 0.8))
ax.set_xlabel('minutes since basket creation (synthetic clock)'); ax.set_ylabel('total units held by the basket (sum over legs)'); ax.set_ylim(-30, max(ys) * 1.3)
ax.set_title('Basket lifecycle: creation, partial cut, full cut, re-entry (s11_basket_lifecycle_demo)', fontsize=12.5, fontweight='bold', color=INK, loc='left'); fig.text(0.01, -0.04, SYN, fontsize=8.5, color='#b45309')
fig.savefig(os.path.join(OUT, '02_basket_lifecycle.png'), dpi=160, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------------------------------------------------------------- 3. exposure over time
rows3 = []; fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True)
for ax, n, title in zip(axes, ('s05_reentry_success', 's07_reentry_rejected_risk_limit', 's11_basket_lifecycle_demo'), ('s05: cut then re-entry', 's07: re-entry rejected by the short-unit limit', 's11: partial, full cut, re-entry')):
    sim = RUN[n]; st = tsv_rows(sim, 'states.tsv'); b0 = min(int(r['ts']) for r in st); seen = {}
    for r in st: seen[(r['ts'], r['event_id'])] = (int(r['gross_units']), int(r['short_units']))
    pts = sorted(((int(k[0]) - b0) / 60, k[1], v[0], v[1]) for k, v in seen.items()); [rows3.append((n, p[0], p[1], p[2], p[3])) for p in pts]
    ax.step([p[0] for p in pts], [p[2] for p in pts], where='post', color='#2563eb', label='gross units'); ax.step([p[0] for p in pts], [p[3] for p in pts], where='post', color='#dc2626', label='short units')
    for key, c in (('max_gross_units', '#2563eb'), ('max_short_units', '#dc2626')):
        if key in SC[n].risk: ax.axhline(SC[n].risk[key], color=c, ls='--', lw=1, alpha=.7); ax.text(0.2, SC[n].risk[key] + 8, f'limit {key.split("_")[1]} = {SC[n].risk[key]}', fontsize=7.5, color=c)
    ax.set_title(title, fontsize=10, loc='left'); ax.set_xlabel('minutes since creation')
axes[0].set_ylabel('units'); axes[0].legend(fontsize=8, loc='lower left'); fig.suptitle('Gross and short unit exposure from per-instrument net inventory after each event', fontsize=12.5, fontweight='bold', x=0.01, ha='left'); fig.text(0.01, -0.02, SYN, fontsize=8.5, color='#b45309')
save_csv('03_exposure_over_time.tsv', ['scenario', 'minutes_since_creation', 'event_id', 'gross_units', 'short_units'], rows3, lambda r: 'synthetic simulation: ' + r[0])
fig.savefig(os.path.join(OUT, '03_exposure_over_time.png'), dpi=160, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------------------------------------------------------------- 4. per-leg quantity before / after each cut
rows4 = []
for n in ('s02_partial_basket_cut', 's03_full_basket_cut', 's05_reentry_success', 's08_overlapping_baskets'):
    st = tsv_rows(RUN[n], 'states.tsv'); acc = {a['action_id']: a for a in tsv_rows(RUN[n], 'actions.tsv') if a['status'] == 'ACCEPTED' and a['type'] == 'CUT'}
    for r in st:
        if r['action_id'] in acc and r['leg_id'] == acc[r['action_id']]['leg_id'] and r['basket_id'] == acc[r['action_id']]['basket_id']: rows4.append((n, r['basket_id'], r['action_id'].split('|')[-1] if False else r['action_id'], r['leg_id'], r['qty_before'], r['qty_after'], acc[r['action_id']]['qty']))
save_csv('04_leg_quantity_before_after_cuts.tsv', ['scenario', 'basket_id', 'action_id', 'leg_id', 'qty_before', 'qty_after', 'cut_qty'], rows4, lambda r: 'synthetic simulation: ' + r[0])
fig, axes = plt.subplots(1, 4, figsize=(16, 4.6), sharey=True)
for ax, n in zip(axes, ('s02_partial_basket_cut', 's03_full_basket_cut', 's05_reentry_success', 's08_overlapping_baskets')):
    rr = [r for r in rows4 if r[0] == n]; labels = [f'{r[1]}:{r[3]}' for r in rr]; x = range(len(rr))
    ax.bar([i - 0.2 for i in x], [int(r[4]) for r in rr], 0.4, color='#93c5fd', label='before the cut', edgecolor=EDGE); ax.bar([i + 0.2 for i in x], [int(r[5]) for r in rr], 0.4, color='#f59e0b', label='after the cut', edgecolor=EDGE)
    for i, r in enumerate(rr): ax.text(i - 0.2, int(r[4]) + 3, r[4], ha='center', fontsize=7.5); ax.text(i + 0.2, int(r[5]) + 3, r[5], ha='center', fontsize=7.5)
    ax.set_xlim(-0.8, max(len(rr) - 0.2, 1.8)); ax.set_ylim(0, 225); ax.set_xticks(list(x)); ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8); ax.set_title(n.replace('_', ' ', 1), fontsize=9.5, loc='left')
axes[0].set_ylabel('units in the basket leg'); axes[3].legend(fontsize=8, loc='upper right'); fig.suptitle('Per-leg quantity before and after each accepted cut', fontsize=12.5, fontweight='bold', x=0.01, ha='left'); fig.text(0.01, -0.03, SYN, fontsize=8.5, color='#b45309')
fig.savefig(os.path.join(OUT, '04_leg_quantity_before_after_cuts.png'), dpi=160, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------------------------------------------------------------- 5. re-entry decision timeline
REASON_COLOR = {'COOLDOWN_ACTIVE': '#9ca3af', 'REENTRY_ELIGIBLE': '#10b981', 'PRICE_CONDITION_NOT_MET': '#f59e0b', 'WINDOW_EXPIRED': '#8b5cf6', 'REENTRY_LIMIT_REACHED': '#d1d5db', 'NO_MARK_AVAILABLE': '#6b7280'}
SRC_SHAPE = {'basket_cut': '^', 'basket_reentry': 's', 'scripted_actions': 'D'}; OK_C, BAD_C = '#047857', '#dc2626'
rows5 = []; names = ('s05_reentry_success', 's06_reentry_rejected_cooldown', 's07_reentry_rejected_risk_limit'); fig, ax = plt.subplots(figsize=(13, 5))
for k, n in enumerate(names):
    sim = RUN[n]; b0 = min(int(r['ts']) for r in tsv_rows(sim, 'states.tsv'))
    for d in tsv_rows(sim, 'decisions.tsv'):
        if d['plugin'] != 'basket_reentry': continue
        x = (int(d['ts']) - b0) / 60; ax.scatter([x], [k + 0.2], marker='o', s=90, color=REASON_COLOR.get(d['reason'], '#000'), edgecolor=EDGE, zorder=3); rows5.append((n, x, 'plugin decision', 'basket_reentry', d['reason'], d['detail']))
    for a in tsv_rows(sim, 'actions.tsv'):
        x = (int(a['ts']) - b0) / 60; ok = a['status'] == 'ACCEPTED'; y = k - 0.2 + (0.18 if a['type'] == 'CUT' else 0)
        ax.scatter([x], [y], marker=SRC_SHAPE[a['plugin']], s=95, color=OK_C if ok else BAD_C, edgecolor=EDGE, zorder=3)
        rows5.append((n, x, f"action ({a['type']})", a['plugin'], 'ACCEPTED' if ok else 'REJECTED: ' + a['reason'], a['detail']))
ax.set_yticks(range(len(names))); ax.set_yticklabels([n.replace('_', ' ', 1) for n in names], fontsize=9); ax.set_ylim(-0.7, len(names) - 0.1); ax.set_xlabel('minutes since basket creation (synthetic clock)')
for r, c in REASON_COLOR.items(): ax.scatter([], [], color=c, marker='o', label=f'basket_reentry decision: {r}', edgecolor=EDGE)
for src, m in SRC_SHAPE.items(): ax.scatter([], [], color='#cbd5e1', marker=m, label=f'action proposed by {src}', edgecolor=EDGE)
ax.scatter([], [], color=OK_C, marker='o', label='green = accepted by risk validation', edgecolor=EDGE); ax.scatter([], [], color=BAD_C, marker='o', label='red = rejected by risk validation', edgecolor=EDGE)
ax.legend(fontsize=7.5, loc='center left', bbox_to_anchor=(1.01, 0.5)); ax.set_title('Re-entry decisions: what basket_reentry decided (circles, upper row) and what happened to each proposed action (shape = who proposed it)', fontsize=10.5, fontweight='bold', loc='left'); fig.text(0.01, -0.02, SYN, fontsize=8.5, color='#b45309')
save_csv('05_reentry_decision_timeline.tsv', ['scenario', 'minutes_since_creation', 'layer', 'action_source', 'outcome_or_reason', 'detail'], rows5, lambda r: 'synthetic simulation: ' + r[0])
fig.savefig(os.path.join(OUT, '05_reentry_decision_timeline.png'), dpi=160, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------------------------------------------------------------- 6. risk validation and rejected actions
cnt = {}; plug = {}
for n, sim in RUN.items():
    for a in tsv_rows(sim, 'actions.tsv'): cnt.setdefault((a['reason'] if a['status'] == 'REJECTED' else 'ACCEPTED'), {}).setdefault(n, 0); cnt[a['reason'] if a['status'] == 'REJECTED' else 'ACCEPTED'][n] += 1
    for d in tsv_rows(sim, 'decisions.tsv'):
        if d['outcome'] == 'NOT_PROPOSED': plug.setdefault(d['reason'], {}).setdefault(n, 0); plug[d['reason']][n] += 1
rows6 = [('validator', r, n, c) for r, d in cnt.items() for n, c in d.items()] + [('plugin (not proposed)', r, n, c) for r, d in plug.items() for n, c in d.items()]
save_csv('06_risk_validation_and_rejections.tsv', ['layer', 'outcome_or_reason', 'scenario', 'count'], rows6, lambda r: 'synthetic simulation: ' + r[2])
fig, axes = plt.subplots(1, 2, figsize=(16, 5.4)); fig.subplots_adjust(wspace=0.75); order = sorted(cnt, key=lambda r: (r != 'ACCEPTED', -sum(cnt[r].values())))
axes[0].barh(order, [sum(cnt[r].values()) for r in order], color=['#10b981' if r == 'ACCEPTED' else '#ef4444' for r in order], edgecolor=EDGE); axes[0].invert_yaxis(); axes[0].set_xscale('log'); axes[0].set_xlim(0.8, 300); axes[0].set_xlabel('number of proposed actions (log scale)')
for i, r in enumerate(order): axes[0].text(sum(cnt[r].values()) * 1.08, i, str(sum(cnt[r].values())), va='center', fontsize=8)
axes[0].set_title('Risk validation: accepted and rejected actions across the generated scenarios', fontsize=10.5, loc='left')
po = sorted(plug, key=lambda r: -sum(plug[r].values())); axes[1].barh(po, [sum(plug[r].values()) for r in po], color='#94a3b8', edgecolor=EDGE); axes[1].invert_yaxis(); axes[1].set_xscale('log'); axes[1].set_xlim(1, 600); axes[1].set_xlabel('number of plugin decisions (log scale)')
axes[1].set_title('Plugin decisions that proposed nothing (before risk validation)', fontsize=10.5, loc='left'); fig.text(0.01, -0.03, 'Counts come from the generated test scenarios, including three random stress runs that send many invalid actions on purpose. They are not real trading rejection rates.', fontsize=9, color='#b45309')
fig.savefig(os.path.join(OUT, '06_risk_validation_and_rejections.png'), dpi=160, bbox_inches='tight', facecolor='white'); plt.close(fig)
print('wrote', sorted(os.listdir(OUT)))
