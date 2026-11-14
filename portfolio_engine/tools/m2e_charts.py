"""M2-E visualization suite V1-V6. Charts are drawn ONLY from the assembled data files in reports/m2e_data/<cycle>/ and every figure writes the exact plotted values to a sibling CSV
(reports/m2e_figures/<cycle>/). All times are IST (UTC+05:30) and labelled as such. No price interpolation, no marks. Grouping layers are never summed with each other.
python3 portfolio_engine/tools/m2e_charts.py [--cycle NIFTY_2026-06-30] [--episode <episode_id>]"""
import csv, datetime as dt, hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as mdates, matplotlib.ticker
from collections import Counter, defaultdict
from pe import forensics as F, cases as K

DATA = os.path.join(PE, 'reports', 'm2e_data'); FIG = os.path.join(PE, 'reports', 'm2e_figures')
C = dict(short='#D55E00', long='#0072B2', grey='#8a8a8a', green='#009E73', purple='#CC79A7', orange='#E69F00', sky='#56B4E9', dark='#222222')
plt.rcParams.update({'font.size': 8, 'axes.titlesize': 9, 'axes.grid': True, 'grid.alpha': 0.25, 'figure.dpi': 110, 'savefig.dpi': 110})
SUM_D = json.load(open(os.path.join(PE, 'reports', 'm2d_data', 'm2d_summary.json')))
FULL_W1 = SUM_D['coverage']['OPENING|W1']; FULL_S60 = SUM_D['coverage']['OPENING|W1_S60']; FULL_CLOSING_WING_MIXED = SUM_D['closing_wing_episode_origin_units']
EXCL_CLOSING_UNITS = sum(v for k, v in SUM_D['scope_exclusions_TAGGED_units'].items() if k.startswith('CLOSING'))


def pct(a, b): return f'{100 * a / b:.1f}%'
SCOPE_WARNING = (f"SCOPE (full ledger, M2-D): W1 {FULL_W1['wing_items']:,} wing items, {FULL_W1['wing_items_with_candidate']:,} with >=1 candidate ({FULL_W1['wing_items_unique_candidate']:,} unique, {FULL_W1['wing_items_multiple_candidates']:,} multiple), {FULL_W1['wing_items_no_candidate']:,} none; "
                 f"{FULL_W1['wing_units_unmatched']:,} unmatched wing units ({pct(FULL_W1['wing_units_unmatched'], FULL_W1['wing_units'])}). Group-level 1:1 is NOT lot ownership. "
                 f"W1_S60: {FULL_S60['wing_items_with_candidate']:,} with candidate, {FULL_S60['wing_items_no_candidate']:,} none, {FULL_S60['wing_units_unmatched']:,} unmatched units (first-fill execution times, same IST session; not decision-time evidence). "
                 f"Tag-based roles exclude {EXCL_CLOSING_UNITS:,} closing units; `s_` stop-closed bodies are not in short-body; `num` seed wings are not identified as wings; {FULL_CLOSING_WING_MIXED['opened_by_mixed_modules']:,} closing wing units sit in mixed-module episodes. "
                 "A position absent from the role-specific analysis is NOT claimed to lack a wing. App keys are not a filter anywhere.")
EVID = {'W1': 'W1 = WEAKLY_SUPPORTED (inferred candidate: same underlying, expiry, right and order-entry minute)', 'W1_S60': 'W1_S60 = UNRESOLVED (first-fill execution times within +-60 s, same IST session; not decision-time evidence)',
        'W2': 'W2 = WEAKLY_SUPPORTED weights; weighted_wing_units are NOT allocations and NOT ownership', 'W3': 'W3 = UNRESOLVED: opening-level FIFO queue arithmetic, NOT ownership'}


def T(ts): return dt.datetime(1970, 1, 1) + dt.timedelta(seconds=int(ts) + F.IST)             # tz-naive wall-clock IST
def rows(cycle, name): return F.read_tsv_text(open(os.path.join(DATA, cycle, name)).read())[1]
def wcsv(path, header, rws):
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n'); w.writerow(header); w.writerows(rws)
def sha_file(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()


class Fig:
    """One figure + its data CSV + a manifest entry."""
    def __init__(self, cycle, vid, title, size, nrows=1, ncols=1, **kw):
        self.cycle, self.vid, self.dir = cycle, vid, os.path.join(FIG, cycle); os.makedirs(self.dir, exist_ok=True)
        self.fig = plt.figure(figsize=size); self.title = title; self.sources = []
    def head(self, text, fontsize=8, width=165, **kw):
        import textwrap
        self.fig.text(0.01, 0.995, '\n'.join(textwrap.wrap(text.replace('\n', ' '), width)), fontsize=fontsize, va='top', ha='left')

    def finish(self, header, data, sources, warning=None, extra=None, more=None):
        import textwrap
        und = self.cycle.replace('_', ' ')
        foot = f'{und} | HISTORICAL_OBSERVED_REPLAY | times IST (UTC+05:30) | execution prices only, historical marks missing (source absent), unrealized P&L = NA | data: {self.vid}.csv'
        self.fig.text(0.005, 0.004, foot, fontsize=6, color='#555')
        if warning: self.fig.text(0.005, 0.018, '\n'.join(textwrap.wrap(warning, 270)), fontsize=5.6, color='#7a1f1f', va='bottom')
        png = os.path.join(self.dir, f'{self.vid}.png'); cs = os.path.join(self.dir, f'{self.vid}.csv'); os.makedirs(os.path.dirname(png), exist_ok=True); self.fig.savefig(png); plt.close(self.fig); wcsv(cs, header, data); add = []
        for name, (h2, r2) in (more or {}).items():
            p2 = os.path.join(self.dir, f'{self.vid}__{name}.csv'); wcsv(p2, h2, r2); add.append(dict(name=name, data_csv=os.path.relpath(p2, PE), rows=len(r2), sha256=sha_file(p2)))
        return dict(figure=self.vid, title=self.title, png=os.path.relpath(png, PE), data_csv=os.path.relpath(cs, PE), data_rows=len(data), additional_data_csv=add, source_datasets=[os.path.join('reports', 'm2e_data', self.cycle, x) for x in sources],
                    data_csv_sha256=sha_file(cs), png_sha256_informational=sha_file(png), scope_warning_shown=bool(warning), **(extra or {}))


def two_panel(fig, outer, cycle):
    cov = json.load(open(os.path.join(DATA, cycle, 'coverage.json')))['d1_d0']; ss = list(cov)
    w = []
    for s in ss:
        a = dt.datetime.strptime(cov[s]['first_fill_ist'], '%Y-%m-%d %H:%M:%S'); b = dt.datetime.strptime(cov[s]['last_fill_ist'], '%Y-%m-%d %H:%M:%S'); w.append(max(60.0, (b - a).total_seconds() + 1800))
    inner = outer.subgridspec(1, 2, width_ratios=w, wspace=0.04); a0 = fig.add_subplot(inner[0]); a1 = fig.add_subplot(inner[1], sharey=a0); a1.tick_params(labelleft=False)
    for ax, s in zip((a0, a1), ss):
        lo = dt.datetime.strptime(cov[s]['first_fill_ist'], '%Y-%m-%d %H:%M:%S') - dt.timedelta(minutes=10); hi = dt.datetime.strptime(cov[s]['last_fill_ist'], '%Y-%m-%d %H:%M:%S') + dt.timedelta(minutes=10)
        ax.set_xlim(lo, hi); ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M')); ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=8)); ax.set_title(f"{cov[s]['d_label']}  {s} (IST)", fontsize=8, loc='left')
    return (a0, a1), ss, cov


# ------------------------------------------------------------------------------------------------------------------------ V1 inventory evolution
def v1(cycle):
    inv = rows(cycle, 'inventory_series.tsv'); carry = {r['session_ist']: r for r in rows(cycle, 'session_carry.tsv')}; cov = json.load(open(os.path.join(DATA, cycle, 'coverage.json')))['d1_d0']; ss = list(cov)
    cols = ['short_CE', 'short_PE', 'long_CE', 'long_PE', 'net_CE', 'net_PE', 'net_total', 'gross_total', 'cum_opened_units', 'cum_closed_units', 'cum_opened_num_short', 'cum_opened_h_long', 'cum_opened_other']
    chart = []                                    # explicit CARRY_IN row at each session start so the step at the boundary is visible and is not a price/inventory interpolation
    prev = {k: 0 for k in cols}
    for s in ss:
        first = next(r for r in inv if r['session_ist'] == s); t0 = int(first['ts_utc_s']) - (int(first['ts_utc_s']) + F.IST) % 86400 + 9 * 3600 + 15 * 60 - 0
        chart.append(['CARRY_IN', s, cov[s]['d_label'], F.ist_str(t0), t0] + [prev[k] for k in cols]); 
        for r in inv:
            if r['session_ist'] == s: chart.append(['FILL', s, cov[s]['d_label'], r['ts_ist'], int(r['ts_utc_s'])] + [int(r[k]) for k in cols]); prev = {k: int(r[k]) for k in cols}
    H = ['row_kind', 'session_ist', 'd_label', 'ts_ist', 'ts_utc_s'] + cols
    F_ = Fig(cycle, 'V1_inventory_evolution', 'V1 inventory evolution (short/long CE/PE, net, gross; D-1 | D0)', (13, 9.6)); gs = F_.fig.add_gridspec(3, 1, hspace=0.45, top=0.87, bottom=0.075)
    D = [dict(zip(H, r)) for r in chart]; idx = {k: i for i, k in enumerate(H)}
    panels = [('Short and long inventory by right (units)', [('short_CE', 'short CE', C['short'], '-'), ('short_PE', 'short PE', C['orange'], '-'), ('long_CE', 'long CE', C['long'], '-'), ('long_PE', 'long PE', C['sky'], '-')]),
              ('Net (long - short) and gross (long + short) units', [('net_CE', 'net CE', C['purple'], '-'), ('net_PE', 'net PE', C['green'], '-'), ('net_total', 'net total', C['dark'], '-'), ('gross_total', 'gross total', C['grey'], '--')]),
              ('Cumulative units opened / closed (observed). Opened-by-class uses the MODULE TAG only: it is a label, not ownership; net inventory by role is NOT identifiable', [('cum_opened_units', 'opened (all)', C['dark'], '-'), ('cum_closed_units', 'closed (all)', C['grey'], '--'), ('cum_opened_num_short', 'opened: num short (body by tag)', C['short'], '-'), ('cum_opened_h_long', 'opened: h_ long (wing by tag)', C['long'], '-'), ('cum_opened_other', 'opened: other tags (unclassified)', C['purple'], ':')])]
    for pi, (ttl, ser) in enumerate(panels):
        axs, _, _ = two_panel(F_.fig, gs[pi], cycle); axs[0].set_ylabel('units')
        for ax, s in zip(axs, ss):
            sub = [d for d in D if d['session_ist'] == s]; x = [T(d['ts_utc_s']) for d in sub]
            for k, lab, col, ls_ in ser: ax.step(x, [d[k] for d in sub], where='post', color=col, ls=ls_, lw=1.3, label=lab if ax is axs[0] else None)
        axs[0].legend(fontsize=6.5, loc='upper left', ncol=3); axs[0].annotate(ttl, xy=(0.0, 1.13), xycoords='axes fraction', fontsize=8, fontweight='bold')
    c0 = carry[ss[0]]; F_.head(f"V1 inventory evolution | {cycle.replace('_', ' ')} | carried from {cov[ss[0]]['d_label']} into D0: short CE {c0['short_CE']}, short PE {c0['short_PE']}, long CE {c0['long_CE']}, long PE {c0['long_PE']} units (gross {c0['gross_total']}); a CARRY_IN row marks each session start", fontsize=9, x=0.01, y=0.985, ha='left')
    return F_.finish(H, chart, ['inventory_series.tsv', 'session_carry.tsv', 'coverage.json'], extra=dict(reconciles_to='M1/M2-B: series recomputed from side*quantity per fill in tests; cumulative opened/closed = M2-B OA/CP totals'))


# ------------------------------------------------------------------------------------------------------------------------ V2 lifecycle timeline
MARK = {'CREATED': ('^', 'create'), 'ADDED': ('+', 'add'), 'PARTIALLY_REDUCED': ('v', 'partial reduction (position remains)'), 'CLOSED': ('s', 'closure (flat)'), 'REVERSED': ('D', 'reversal')}


def v2(cycle, episode_ids=None, vid='V2_position_lifecycle_timeline'):
    ev = rows(cycle, 'lifecycle_events.tsv'); eps = rows(cycle, 'episodes.tsv'); cov = json.load(open(os.path.join(DATA, cycle, 'coverage.json')))['d1_d0']; ss = list(cov)
    eps = [e for e in sorted(eps, key=lambda r: (int(r['first_ts_utc_s']), r['episode_id'])) if (episode_ids is None or e['episode_id'] in episode_ids)]; order = {e['episode_id']: i for i, e in enumerate(eps)}; ev = [e for e in ev if e['episode_id'] in order]
    n = len(eps); h = max(3.2, 0.2 * n + 1.8); F_ = Fig(cycle, vid, 'V2 position lifecycle timeline', (13, h)); gs = F_.fig.add_gridspec(1, 1, top=0.955 if n > 6 else 0.8, bottom=0.04 if n > 6 else 0.2)
    axs, _, _ = two_panel(F_.fig, gs[0], cycle); chart = []
    for e in eps:
        y = order[e['episode_id']]; col = C['short'] if e['direction'] == 'SHORT' else C['long']; chart.append(['EPISODE', e['episode_id'], e['instrument_id'], e['direction'], e['terminal_status'], e['opened'], e['closed'], e['remaining'], y, '', '', '', '', '', ''])
        for ax in axs: ax.hlines(y, T(e['first_ts_utc_s']), T(e['last_ts_utc_s']), color=col, lw=1.0, alpha=0.55)
    for x in ev:
        y = order[x['episode_id']]; col = C['short'] if x['direction'] == 'SHORT' else C['long']; m, _ = MARK[x['event_type']]; k = [a for a, s in zip(axs, ss) if s == x['session_ist']][0]
        if x['event_type'] == 'ADDED': k.plot([T(x['ts_utc_s'])], [y], marker='+', color=col, ms=4.5, mew=1.0, ls='', zorder=3)
        else: k.scatter([T(x['ts_utc_s'])], [y], marker=m, s=34, facecolors='none' if x['event_type'] == 'PARTIALLY_REDUCED' else col, edgecolors=col, linewidths=1.1, zorder=3)
        chart.append(['EVENT', x['episode_id'], x['instrument_id'], x['direction'], '', '', '', '', y, x['event_type'], x['fill_id'], x['source_row_id'], x['ts_ist'], x['quantity'], x['inventory_after']])
    axs[0].set_yticks(range(n)); axs[0].set_yticklabels([f"{e['right']} {e['strike']} #{e['episode_id'].split('#')[1]} ({e['direction'][0]})" for e in eps], fontsize=5.5 if n > 30 else 7); 
    for m, lab in [(v[0], v[1]) for v in MARK.values()]:
        if m == '+': axs[1].plot([], [], marker='+', color=C['grey'], ls='', label=lab)
        else: axs[1].scatter([], [], marker=m, facecolors='none' if 'partial' in lab else C['grey'], edgecolors=C['grey'], label=lab)
    axs[1].plot([], [], marker='x', color='k', ls='', label='expired unclosed: none in this cycle'); axs[1].legend(fontsize=6.5, loc='upper right', ncol=2); axs[0].set_ylim(n - 0.5, -0.5)
    F_.head(f"V2 position lifecycle timeline | {cycle.replace('_', ' ')} | {n} episode{'s' if n != 1 else ''}. Red = short, blue = long. Hollow triangle-down = PARTIAL reduction (position remains); square = closure to flat. Rows ordered by first fill.", fontsize=8.5, x=0.01, y=0.99, ha='left')
    H = ['record', 'episode_id', 'instrument_id', 'direction', 'terminal_status', 'opened', 'closed', 'remaining', 'row_index', 'event_type', 'fill_id', 'source_row_id', 'ts_ist', 'quantity', 'inventory_after']
    return F_.finish(H, chart, ['lifecycle_events.tsv', 'episodes.tsv'], extra=dict(episodes=n, filter='episode_ids' if episode_ids else 'all'))



# ------------------------------------------------------------------------------------------------------------------------ V3 opening activity / cohort map
ROLE_STYLE = {'BODY_SHORT_BY_TAG': ('v', C['short'], 'body short by tag (num sell open)'), 'WING_LONG_BY_TAG': ('^', C['long'], 'wing long by tag (h_ buy open)')}


def v3(cycle):
    items = rows(cycle, 'opening_items.tsv'); win = rows(cycle, 'tp03_windows.tsv'); cov = json.load(open(os.path.join(DATA, cycle, 'coverage.json')))['d1_d0']; ss = list(cov)
    F_ = Fig(cycle, 'V3_opening_activity_cohort_map', 'V3 opening activity / cohort map', (13, 11.5)); gs = F_.fig.add_gridspec(4, 1, height_ratios=[0.5, 3, 3, 1.6], hspace=0.45, top=0.86, bottom=0.085)
    minq = min(int(r['quantity']) for r in items)
    # row 0: TP-03 window overlay (external attribution, deliberately NOT a grouping of these items)
    ax0, _, _ = two_panel(F_.fig, gs[0], cycle); cmap = {'ACTION': C['green'], 'NO_ACTION_ACTIVE': C['orange'], 'ACTION_OTHER_CLASS': C['sky'], 'NO_ACTION_UNCERTAIN': C['grey'], 'AMBIGUOUS_ACTION': C['purple']}
    for ax, s in zip(ax0, ss):
        for w in [w for w in win if w['date'] == s]:
            ax.axvline(T(w['window_start_ts_utc_s']), color=cmap.get(w['view2_class'], C['grey']), lw=2.2 if not int(w['control_window']) else 1.0, ls='-' if not int(w['control_window']) else ':')
        ax.set_yticks([]); ax.set_ylim(0, 1)
    ax0[0].set_ylabel('TP-03\nwindows', fontsize=7)
    for k, col in cmap.items(): ax0[1].plot([], [], color=col, lw=2, label=k)
    ax0[1].plot([], [], color='k', lw=1, ls=':', label='control window'); hh, ll = ax0[1].get_legend_handles_labels(); F_.fig.legend(hh, ll, fontsize=5.5, ncol=6, loc='upper right', bbox_to_anchor=(0.995, 0.935), title='TP-03 window class (view 2)', title_fontsize=5.5)
    chart = []; unc = []
    for ri, rt in enumerate(('CE', 'PE')):
        axs, _, _ = two_panel(F_.fig, gs[1 + ri], cycle); axs[0].set_ylabel(f'{rt} strike')
        for ax, s in zip(axs, ss):
            for r in items:
                if r['right'] != rt or r['session_ist'] != s: continue
                m, col, _ = ROLE_STYLE.get(r['tag_role'], ('s', C['grey'], ''))
                ax.scatter([T(r['first_ts_utc_s'])], [int(r['strike'])], marker=m, s=5 + 6 * (int(r['quantity']) / minq) ** 0.5, color=col, alpha=0.75 if r['tag_role'] in ROLE_STYLE else 0.5, edgecolors='none')
        if ri == 0:
            for m, col, lab in ROLE_STYLE.values(): axs[0].scatter([], [], marker=m, color=col, label=lab)
            axs[0].scatter([], [], marker='s', color=C['grey'], label='UNCLASSIFIED by tag (s_, v_, num buy ...)'); axs[0].legend(fontsize=6, loc='upper left', ncol=3)
    for r in items: chart.append([r['item_key'], r['parent_order_id'], r['instrument_id'], r['right'], r['strike'], r['module_tag'], r['side'], r['tag_role'], r['quantity'], r['first_ts_ist'], r['first_ts_utc_s'], r['session_ist'], r['d_label'], r['order_entry_minute_ist'], r['tp03_event_class']])
    # row 3: entry-minute cohorts = items sharing the order-entry minute (observed parent metadata; the W1 group key). No gap clustering exists for openings.
    coh = defaultdict(lambda: Counter()); npar = defaultdict(set)
    for r in items:
        if r['order_entry_minute_ist'] == 'NA': unc.append(r['item_key']); continue
        k = (r['session_ist'], r['order_entry_minute_ist']); cls = 'body' if r['tag_role'] == 'BODY_SHORT_BY_TAG' else 'wing' if r['tag_role'] == 'WING_LONG_BY_TAG' else 'unclassified'; coh[k][cls] += int(r['quantity']); npar[k].add(r['parent_order_id'])
    axs, _, _ = two_panel(F_.fig, gs[3], cycle); axs[0].set_ylabel('units opened\nper entry minute', fontsize=7); cr = []
    for ax, s in zip(axs, ss):
        for (sess, em), v in sorted(coh.items()):
            if sess != s: continue
            x = dt.datetime.strptime(em, '%Y-%m-%d %H:%M:%S'); b = 0
            for cls, col in (('body', C['short']), ('wing', C['long']), ('unclassified', C['grey'])): ax.bar(x, v[cls], bottom=b, width=1 / 1440 * 0.9, color=col, align='edge'); b += v[cls]
    for (sess, em), v in sorted(coh.items()): cr.append([sess, em, v['body'], v['wing'], v['unclassified'], len(npar[(sess, em)])])
    F_.head(f"V3 opening activity | {cycle.replace('_', ' ')} | one marker = one (parent order, instrument) opening item at its first-fill time; marker area ~ sqrt(quantity). Role = MODULE TAG label, not ownership.  Top strip: TP-03 entry windows (separate attribution, not a grouping).  Bottom: units per ORDER-ENTRY MINUTE (observed cohort key; no gap clustering applies to openings).", fontsize=7.5, x=0.01, y=0.985, ha='left', wrap=True)
    H = ['item_key', 'parent_order_id', 'instrument_id', 'right', 'strike', 'module_tag', 'side', 'tag_role', 'quantity', 'first_fill_ts_ist', 'first_fill_ts_utc_s', 'session_ist', 'd_label', 'order_entry_minute_ist', 'tp03_event_class']
    tw = [[w['cycle'], w['kind'], w['date'], w['window'], w['window_start_ist'], w['control_window'], w['view1_class'], w['view2_class'], w['view3_class'], w['n_parents_inside']] for w in win]
    return F_.finish(H, chart, ['opening_items.tsv', 'tp03_windows.tsv'], more={'entry_minute_cohorts': (['session_ist', 'order_entry_minute_ist', 'body_units_by_tag', 'wing_units_by_tag', 'unclassified_units', 'n_parent_orders'], cr),
                     'tp03_windows_overlay': (['cycle', 'kind', 'date', 'window_ist', 'window_start_ist', 'control_window', 'view1_class', 'view2_class', 'view3_class', 'n_parents_inside'], tw)}, warning=SCOPE_WARNING, extra=dict(items_without_entry_minute=len(unc)))


# ------------------------------------------------------------------------------------------------------------------------ V4 closing batches (C1 and C2 separate)
THR = (2, 5, 10, 30, 60)
RC = {'CE_ONLY': C['orange'], 'PE_ONLY': C['sky'], 'MIXED': C['purple']}


def v4(cycle, method):
    B = rows(cycle, f'm2c_closing_batches_{method}.tsv'); Mm = rows(cycle, f'm2c_closing_batch_members_{method}.tsv'); name = {'C1': 'C1 first-fill gap', 'C2': 'C2 last-to-first gap'}[method]; ss = list(json.load(open(os.path.join(DATA, cycle, 'coverage.json')))['d1_d0'])
    F_ = Fig(cycle, f'V4_{method}_closing_batches', f'V4 closing batches {method}', (13, 11)); gs = F_.fig.add_gridspec(3, 1, height_ratios=[3, 1.7, 2.4], hspace=0.55, top=0.86, bottom=0.085)
    b10 = [b for b in B if b['threshold_s'] == '10']; axs, _, _ = two_panel(F_.fig, gs[0], cycle); axs[0].set_ylabel('parent orders in batch'); top = max(b10, key=lambda b: int(b['n_parents']))
    for ax, s in zip(axs, ss):
        for b in b10:
            if b['session'] != s: continue
            x0, x1 = T(b['start_ts']), T(b['end_ts']); y = int(b['n_parents']); col = RC[b['right_class']]
            ax.hlines(y, x0, x1, color=col, lw=2.5, alpha=0.85); ax.scatter([x0, x1], [y, y], s=7, color=col, zorder=3)
    for k, col in RC.items(): axs[1].plot([], [], color=col, lw=3, label={'CE_ONLY': 'CE contracts only', 'PE_ONLY': 'PE contracts only', 'MIXED': 'CE and PE'}[k])
    axs[1].legend(fontsize=6.5, loc='upper right'); axs[0].set_yscale('log'); axs[0].set_yticks([1, 2, 5, 10, 20, 50, 100]); axs[0].get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    axs[0].annotate(f"{name}, 10 s PRIMARY batches: bar = first to last closing second of the batch's member orders; y (log) = parent orders in the batch. Widest batch: {top['n_parents']} parents, {top['duration_s']} s", xy=(0, 1.16), xycoords='axes fraction', fontsize=7.5, fontweight='bold')
    sens = []
    for t in THR:
        bt = [b for b in B if b['threshold_s'] == str(t)]; n = [int(b['n_parents']) for b in bt]; d = sorted(int(b['duration_s']) for b in bt)
        sens.append([t, len(bt), sum(1 for x in n if x == 1), max(n), d[len(d) // 2], d[-1], sum(int(b['n_closing_portions']) for b in bt), sum(int(b['total_closing_qty']) for b in bt)])
    sub = gs[1].subgridspec(1, 3, wspace=0.28); lab = [f'{t}s' for t in THR]
    for i, (col, ttl, c_) in enumerate(((1, 'batches', C['dark']), (3, 'max parent orders in one batch', C['purple']), (5, 'longest chain (s) [log]', C['orange']))):
        ax = F_.fig.add_subplot(sub[i]); ax.bar(lab, [r[col] for r in sens], color=c_, alpha=0.8); ax.set_title(ttl, fontsize=7.5); ax.tick_params(labelsize=7)
        for j, r in enumerate(sens): ax.text(j, r[col], str(r[col]), ha='center', va='bottom', fontsize=6)
        if i == 2: ax.set_yscale('log')
    sub = gs[2].subgridspec(1, 2, wspace=0.35); lc = []
    for i, t in enumerate((60, 10)):
        ax = F_.fig.add_subplot(sub[i]); top8 = sorted([b for b in B if b['threshold_s'] == str(t)], key=lambda b: (-int(b['duration_s']), b['batch_id']))[:8]
        ax.barh(range(len(top8)), [int(b['duration_s']) for b in top8], color=C['orange'] if t == 60 else C['dark'], alpha=0.8); ax.set_yticks(range(len(top8))); ax.invert_yaxis()
        ax.set_yticklabels([f"{b['batch_id'].rsplit(':', 1)[1]} {F.ist_str(int(b['start_ts']))[5:16]}-{F.ist_str(int(b['end_ts']))[11:16]} ({b['n_parents']} orders)" for b in top8], fontsize=5.5); ax.set_xlabel('chain duration (seconds, first to last closing second)', fontsize=7)
        ax.set_title(f'longest chains at {t} s' + (' (single-linkage chaining makes batches very long)' if t == 60 else ' (primary)'), fontsize=7.5)
        for b in top8: lc.append([t, b['batch_id'], b['n_parents'], b['duration_s'], F.ist_str(int(b['start_ts'])), F.ist_str(int(b['end_ts'])), b['max_link_gap_s']])
    F_.head(f"V4 closing batches {method} ({name}) | {cycle.replace('_', ' ')} | batches are TIME-CONNECTED CLOSING-ORDER CLUSTERS, not decisions (decision unit UNRESOLVED). 10 s primary; 2/5/30/60 s are sensitivities. C1 and C2 are separate views, never summed.", fontsize=7.8, x=0.01, y=0.985, ha='left')
    H = ['batch_id', 'grouping_convention', 'threshold_s', 'session', 'd_label_of_session', 'start_ts_utc_s', 'end_ts_utc_s', 'start_ist', 'end_ist', 'duration_s', 'n_parents', 'n_closing_portions', 'total_closing_qty', 'n_contracts', 'contracts', 'right_class', 'max_link_gap_s']
    ex = lambda b: [b['batch_id'], b['grouping_convention'], b['threshold_s'], b['session'], 'D0' if b['session'] == b['expiry'] else 'D-1', b['start_ts'], b['end_ts'], F.ist_str(int(b['start_ts'])), F.ist_str(int(b['end_ts'])), b['duration_s'], b['n_parents'], b['n_closing_portions'], b['total_closing_qty'], b['n_contracts'], b['contracts'], b['right_class'], b['max_link_gap_s']]
    mem = [[m['batch_id'], m['threshold_s'], m['parent_order_id'], m['parent_first_closing_ts'], F.ist_str(int(m['parent_first_closing_ts'])), m['n_closing_portions'], m['closing_qty'], m['join_gap_s'], m['cp_ids']] for m in Mm if m['threshold_s'] == '10']
    return F_.finish(H, [ex(b) for b in b10], [f'm2c_closing_batches_{method}.tsv', f'm2c_closing_batch_members_{method}.tsv'], warning='Single-linkage chaining lengthens batches as the threshold grows (bottom row, and longest chain per threshold above): chain duration is reported next to every threshold. A batch is a temporal cluster of closing orders, NOT a decision or a basket. Each parent order belongs to exactly one batch per view (parent order = unit).',
                     more={'sensitivity_by_threshold': (['threshold_s', 'batches', 'singleton_batches', 'max_parents_in_batch', 'median_duration_s', 'max_duration_s', 'closing_portions', 'closing_units'], sens), 'longest_chains': (['threshold_s', 'batch_id', 'n_parents', 'duration_s', 'start_ist', 'end_ist', 'max_link_gap_s'], lc),
                           'members_10s': (['batch_id', 'threshold_s', 'parent_order_id', 'parent_first_closing_ts_utc_s', 'parent_first_closing_ist', 'n_closing_portions', 'closing_qty', 'join_gap_s', 'cp_ids'], mem)}, extra=dict(method=method))


# ------------------------------------------------------------------------------------------------------------------------ V5 wing / body comparison (one figure per method)
STYLE = {'OBSERVED': dict(hatch=None, ls='-', alpha=0.95), 'W1': dict(hatch='////', ls='-', alpha=0.6), 'W2': dict(hatch='////', ls='-', alpha=0.6), 'W1_S60': dict(hatch=None, ls=':', alpha=0.25), 'W3': dict(hatch=None, ls=':', alpha=0.25)}   # solid = observed, hatched = weakly supported, pale + dotted edge = unresolved
CLASS = {'W1': 'WEAKLY_SUPPORTED', 'W2': 'WEAKLY_SUPPORTED (weights)', 'W1_S60': 'UNRESOLVED', 'W3': 'UNRESOLVED'}


def _bar(ax, x, h, color, method, bottom=0, label=None, width=0.6):
    st = STYLE[method]; unres = st['ls'] == ':'
    return ax.bar(x, h, bottom=bottom, width=width, facecolor=color, edgecolor='#222' if unres else 'white', hatch=st['hatch'], ls=st['ls'], lw=1.3 if unres else 0.6, alpha=st['alpha'], label=label)


def _cand_maps(D, method):
    b = defaultdict(set); w = defaultdict(set)
    for l in D['links'][method]:
        if l['level'] == 'OPENING': b[l['body_item']].add(l['wing_item']); w[l['wing_item']].add(l['body_item'])
    return b, w


def v5(cycle, method):
    D = K.load_data(os.path.join(DATA, cycle)); W = [r for r in D['wb_items'].values() if r['level'] == 'OPENING' and r['role'] == 'WING']; Bd = [r for r in D['wb_items'].values() if r['level'] == 'OPENING' and r['role'] == 'BODY']
    wu = sum(int(r['qty']) for r in W); bu = sum(int(r['qty']) for r in Bd); L = [l for l in D['links'][method] if l['level'] == 'OPENING']
    base = 'W1' if method in ('W1', 'W2') else 'W1_S60' if method == 'W1_S60' else 'W3'; bmap, wmap = _cand_maps(D, method if method != 'W2' else 'W1')
    if method == 'W3': bmap, wmap = _cand_maps(D, 'W3')
    F_ = Fig(cycle, f'V5_{method}_wing_body', f'V5 wing/body {method}', (13, 6.6)); gs = F_.fig.add_gridspec(1, 3, wspace=0.32, top=0.76, bottom=0.2); data = []
    a1 = F_.fig.add_subplot(gs[0]); cats = ['0', '1', '2', '3', '4', '5+']
    def mult(m, items): c = Counter(min(len(m.get(i['item_id'], ())), 5) for i in items); return [c.get(k, 0) for k in range(6)]
    mw, mb = mult(wmap, W), mult(bmap, Bd); x = list(range(6))
    _bar(a1, [i - 0.2 for i in x], mw, C['long'], base, width=0.38, label='wing items by # candidate bodies'); _bar(a1, [i + 0.2 for i in x], mb, C['short'], base, width=0.38, label='body items by # candidate wings'); a1.set_xticks(x); a1.set_xticklabels(cats); a1.set_xlabel('number of candidates (0 = unmatched)'); a1.set_ylabel('opening items'); a1.legend(fontsize=6.5)
    a1.set_title('Candidate multiplicity (opening items)', fontsize=8)
    for k, c in enumerate(cats): data += [['candidate_multiplicity', f'wing items with {c} candidate bodies', mw[k], 'items', CLASS[method]], ['candidate_multiplicity', f'body items with {c} candidate wings', mb[k], 'items', CLASS[method]]]
    a2 = F_.fig.add_subplot(gs[1])
    def split(items, m): u = sum(int(i['qty']) for i in items if len(m.get(i['item_id'], ())) == 1); mu = sum(int(i['qty']) for i in items if len(m.get(i['item_id'], ())) >= 2); z = sum(int(i['qty']) for i in items if len(m.get(i['item_id'], ())) == 0); return u, mu, z
    if method == 'W3':
        mq = sum(float(l['queue_matched_units']) for l in L); parts = {'wing units': (mq, wu - mq), 'body units': (mq, bu - mq)}
        for j, (lab, (m_, r_)) in enumerate(parts.items()):
            _bar(a2, j, m_, C['green'], method, label='queue-matched units' if j == 0 else None); _bar(a2, j, r_, C['grey'], method, bottom=m_, label='queue residual (unmatched)' if j == 0 else None)
            a2.add_patch(plt.Rectangle((j - 0.3, 0), 0.6, m_ + r_, fill=False, ec='k', lw=1.0)); a2.text(j, m_ + r_, f'{int(m_ + r_):,}', ha='center', va='bottom', fontsize=7); data += [['units', f'{lab}: queue-matched', m_, 'units', CLASS[method]], ['units', f'{lab}: queue residual', r_, 'units', CLASS[method]], ['units', f'{lab}: observed total', m_ + r_, 'units', 'OBSERVED']]
        a2.set_xticks([0, 1]); a2.set_xticklabels(list(parts))
    else:
        for j, (lab, items, m) in enumerate((('wing units', W, wmap), ('body units', Bd, bmap))):
            u, mu, z = split(items, m); tot = u + mu + z; b0 = 0
            for val, col, nm in ((u, C['green'], 'exactly 1 candidate'), (mu, C['orange'], '>=2 candidates (ambiguous)'), (z, C['grey'], 'no candidate (unmatched)')):
                _bar(a2, j, val, col, method, bottom=b0, label=nm if j == 0 else None); b0 += val; data.append(['units', f'{lab}: {nm}', val, 'units', CLASS[method]])
            a2.add_patch(plt.Rectangle((j - 0.3, 0), 0.6, tot, fill=False, ec='k', lw=1.0)); a2.text(j, tot, f'{tot:,}', ha='center', va='bottom', fontsize=7); data.append(['units', f'{lab}: observed total', tot, 'units', 'OBSERVED'])
        a2.set_xticks([0, 1]); a2.set_xticklabels(['wing units', 'body units'])
    a2.set_title('Units by candidate status (black outline = observed total)', fontsize=8); a2.set_ylim(0, a2.get_ylim()[1] * 1.3); a2.legend(fontsize=6.5, loc='upper right'); a2.set_ylabel('units (opening)')
    a3 = F_.fig.add_subplot(gs[2])
    if method in ('W1', 'W1_S60'):
        dts = [int(l['dt_s']) for l in L]; bins = range(-60, 62, 4) if method == 'W1_S60' else range(-120, 62, 6)
        a3.hist([max(min(d, bins[-1] - 1), bins[0]) for d in dts], bins=list(bins), facecolor=C['dark'] if method == 'W1' else 'none', edgecolor=C['dark'], hatch='////' if method == 'W1' else None, ls='-' if method == 'W1' else ':', alpha=0.6)
        a3.set_xlabel(f'first-fill time: wing - body (s); {sum(1 for d in dts if d < bins[0] or d >= bins[-1])} links beyond the axis are drawn in the end bins'); a3.set_ylabel('candidate links'); a3.set_title(f'{method} candidate links: n = {len(L):,}', fontsize=8)
        h, e = __import__('numpy').histogram([max(min(d, bins[-1] - 1), bins[0]) for d in dts], bins=list(bins)); data += [['dt_s_histogram', f'[{int(e[i])},{int(e[i + 1])})', int(h[i]), 'links', CLASS[method]] for i in range(len(h))]
        if method == 'W1_S60': inp = sum(int(l['in_primary_candidate_set']) for l in L); a3.text(0.02, 0.95, f'links also in the W1 primary set: {inp:,} of {len(L):,}', transform=a3.transAxes, fontsize=6.5, va='top'); data.append(['links_in_primary_set', 'W1_S60 links also W1', inp, 'links', CLASS[method]])
    elif method == 'W2':
        sw = defaultdict(float)
        for l in L: sw[l['body_item']] += float(l['weighted_wing_units'])
        xs = [int(r['qty']) for r in Bd if r['item_id'] in sw]; ys = [sw[r['item_id']] for r in Bd if r['item_id'] in sw]
        a3.scatter(xs, ys, s=8, facecolor='none', edgecolor=C['dark'], alpha=0.6); lim = max(xs + ys + [1]); a3.plot([0, lim], [0, lim], color=C['grey'], lw=0.8, ls='--'); a3.set_xlabel('body item units'); a3.set_ylabel('sum of weighted wing units (weights, NOT allocations)'); a3.set_title('W2 weights per body item (body items with a W1 candidate)', fontsize=8)
        data += [['w2_body_vs_weighted_units', r['item_id'], f'{sw[r["item_id"]]:.4f}', f'body_units={r["qty"]}', CLASS[method]] for r in Bd if r['item_id'] in sw]
    else:
        q = Counter(f"{float(l['queue_matched_units']):g}" for l in L); ks = sorted(q, key=float); a3.bar(range(len(ks)), [q[k] for k in ks], facecolor=C['dark'], alpha=0.25, edgecolor='#222', ls=':', lw=1.3); a3.set_xticks(range(len(ks))); a3.set_xticklabels(ks, fontsize=7)
        a3.set_xlabel('queue_matched_units per link (distinct values)'); a3.set_ylabel('links'); a3.set_title(f'W3 queue-matched links: n = {len(L):,} (queue arithmetic, not ownership)', fontsize=8)
        data += [['w3_queue_matched_units_by_value', k, q[k], 'links', CLASS[method]] for k in ks]
    F_.head(f"V5 {method} wing / body | {cycle.replace('_', ' ')}\n{EVID[method]}.  Solid bars/outlines = observed facts; hatched = inferred (weakly supported); dotted outline = unresolved.  Candidate multiplicity and unmatched units are shown, not resolved.", fontsize=8, x=0.01, y=0.985, ha='left')
    extra_w = {'W1': '', 'W1_S60': 'W1_S60 uses first-fill execution timestamps within the same IST session: not decision-time evidence. ', 'W2': 'W2 weights are arithmetic, never allocation. ', 'W3': 'W3 = opening-level FIFO queue arithmetic, not ownership. '}[method]
    return F_.finish(['panel', 'category', 'value', 'unit', 'evidence_class'], data, ['m2d_wing_body_items.tsv', f'm2d_wing_body_links_{method}.tsv'], warning=extra_w + SCOPE_WARNING, extra=dict(method=method, evidence_class=CLASS[method], wing_units_observed=wu, body_units_observed=bu))


# ------------------------------------------------------------------------------------------------------------------------ V6 coverage / uncertainty dashboard
def v6(cycle):
    D = K.load_data(os.path.join(DATA, cycle)); cov = json.load(open(os.path.join(DATA, cycle, 'coverage.json'))); sec = []
    W = [r for r in D['wb_items'].values() if r['level'] == 'OPENING' and r['role'] == 'WING']; Bd = [r for r in D['wb_items'].values() if r['level'] == 'OPENING' and r['role'] == 'BODY']
    cm = {m: _cand_maps(D, m) for m in ('W1', 'W1_S60', 'W3')}
    F_ = Fig(cycle, 'V6_coverage_uncertainty_dashboard', 'V6 coverage and uncertainty dashboard', (13, 9.2)); gs = F_.fig.add_gridspec(3, 3, hspace=0.7, wspace=0.34, top=0.86, bottom=0.16, left=0.2)
    def st(items, m): c = [len(m.get(i['item_id'], ())) for i in items]; q = [int(i['qty']) for i in items]; return (sum(x for x, k in zip(q, c) if k == 1), sum(x for x, k in zip(q, c) if k >= 2), sum(x for x, k in zip(q, c) if k == 0))
    for pi, (role, items, idx) in enumerate((('wing', W, 1), ('body', Bd, 0))):
        ax = F_.fig.add_subplot(gs[0, pi]); 
        for j, m in enumerate(('W1', 'W1_S60', 'W3')):
            u, mu, z = st(items, cm[m][idx]); b0 = 0
            for val, col, nm in ((u, C['green'], '1 candidate'), (mu, C['orange'], '>=2 candidates'), (z, C['grey'], 'none')):
                _bar(ax, j, val, col, m, bottom=b0, label=nm if j == 0 else None); b0 += val; sec.append(['A_units_by_candidate_status', f'{role} units, {m}: {nm}', val, 'cycle'])
            ax.text(j, b0, f'{b0:,}', ha='center', va='bottom', fontsize=6.5)
        ax.set_xticks(range(3)); ax.set_xticklabels(['W1\n(weak)', 'W1_S60\n(unresolved)', 'W3\n(unresolved)']); ax.set_title(f'Opening {role} units by candidate status', fontsize=8); ax.set_ylim(0, ax.get_ylim()[1] * 1.35); ax.legend(fontsize=6, loc='upper right')
    ax = F_.fig.add_subplot(gs[0, 2]); wm = {m: Counter(min(len(cm[m][1].get(i['item_id'], ())), 5) for i in W) for m in ('W1', 'W1_S60', 'W3')}
    for j, m in enumerate(('W1', 'W1_S60', 'W3')): _bar(ax, [k + (j - 1) * 0.27 for k in range(6)], [wm[m].get(k, 0) for k in range(6)], (C['dark'], C['orange'], C['purple'])[j], m, width=0.26, label=m); [sec.append(['B_wing_multiplicity', f'{m}: wing items with {k if k < 5 else "5+"} candidate bodies', wm[m].get(k, 0), 'cycle']) for k in range(6)]
    ax.set_xticks(range(6)); ax.set_xticklabels(['0', '1', '2', '3', '4', '5+']); ax.set_title('Wing candidate multiplicity (items)', fontsize=8); ax.legend(fontsize=6)
    ax = F_.fig.add_subplot(gs[1, 0]); ex = cov['role_classification']['m2d_tagged_scope_exclusions_units']; ks = sorted(ex, key=lambda k: -ex[k]); ax.barh(range(len(ks)), [ex[k] for k in ks], color=C['grey']); ax.set_yticks(range(len(ks))); ax.set_yticklabels([k.replace('_episode|closing_module|', ' ep, closed by ').replace('CLOSING_of_', 'CLOSING of ').replace('OPENING|', 'OPENING ') for k in ks], fontsize=5.5); ax.invert_yaxis()
    ax.set_title('Units outside tag-based roles (closing exclusions and non-wing/body openings)', fontsize=7.5); [sec.append(['C_role_exclusions_units', k, ex[k], 'cycle']) for k in ks]
    ax = F_.fig.add_subplot(gs[1, 1]); ax.axis('off'); ro = cov['role_classification']; mt = cov['order_metadata']; lines = [f"Opening units classified by tag: {ro['opening_units_classified_by_tag']:,} of {ro['opening_units_total']:,}", f"UNCLASSIFIED opening units: {ro['opening_units_unclassified']:,}"]
    for k, v in sorted(ro['opening_units_by_tag_role'].items()):
        if k.startswith('UNCLASSIFIED'): lines.append(f'   {k}: {v:,}')
    lines += ['', f"Missing order metadata (parents): {sum(mt['field_missing'].values())} of {mt['parents'] * len(mt['field_missing']):,} field values", 'Historical marks: MISSING (source absent) -> unrealized P&L = NA', f"Expired-unclosed positions: {cov['episodes']['expired_unclosed']}", f"MIXED-role parents: {cov['missing_or_ambiguous']['parents_with_mixed_role']}", f"Partially-filled fills: {cov['missing_or_ambiguous']['partially_filled_fills']}"]
    import textwrap; ax.text(0, 1, '\n'.join('\n'.join(textwrap.wrap(l, 46, subsequent_indent='   ')) if l.strip() else '' for l in lines), va='top', fontsize=6.8, family='monospace'); ax.set_title('Unclassified quantities and missing metadata', fontsize=8)
    for l in lines:
        if l.strip(): sec.append(['D_unclassified_and_missing', l.strip(), '', 'cycle'])
    ax = F_.fig.add_subplot(gs[1, 2]); cnt = {t: [sum(1 for b in D['batches'][m] if b['threshold_s'] == str(t)) for m in ('C1', 'C2')] for t in THR}
    for j, m in enumerate(('C1', 'C2')): _bar(ax, [i + (j - 0.5) * 0.35 for i in range(5)], [cnt[t][j] for t in THR], (C['dark'], C['orange'])[j], 'OBSERVED', width=0.33, label=m); [sec.append(['E_batch_count_sensitivity', f'{m} batches at {t} s', cnt[t][j], 'cycle']) for t in THR]
    ax.set_xticks(range(5)); ax.set_xticklabels([f'{t}s' for t in THR]); ax.set_title('Closing-batch count by threshold (C1 vs C2 separate views)', fontsize=8); ax.legend(fontsize=6)
    d1 = {i['item_id'] for i in Bd if cm['W1'][0].get(i['item_id'], set()) != cm['W1_S60'][0].get(i['item_id'], set())}; d1w = {i['item_id'] for i in W if cm['W1'][1].get(i['item_id'], set()) != cm['W1_S60'][1].get(i['item_id'], set())}
    mul = {m: sum(1 for i in W if len(cm[m][1].get(i['item_id'], ())) >= 2) for m in cm}
    ax = F_.fig.add_subplot(gs[2, :]); ax.axis('off'); tx = [f'UNRESOLVED / SENSITIVITY (cycle level): body items whose candidate-wing set differs between W1 and W1_S60: {len(d1)} of {len(Bd)}; wing items whose candidate-body set differs: {len(d1w)} of {len(W)}.',
          f'Wing items with >=2 candidate bodies: W1 {mul["W1"]}, W1_S60 {mul["W1_S60"]}, W3 {mul["W3"]} of {len(W)}. Unmatched wing units: W1 {st(W, cm["W1"][1])[2]:,}, W1_S60 {st(W, cm["W1_S60"][1])[2]:,}; W3 queue residual: wing {wu_res(D, "wing"):,}, body {wu_res(D, "body"):,} units.',
          'Evidence classes: W1 WEAKLY_SUPPORTED | W1_S60 UNRESOLVED | W3 UNRESOLVED | lot-level ownership and protective intent UNRESOLVED / NOT_TESTABLE (never upgraded here).']
    ax.text(0, 0.9, '\n'.join(tx), va='top', fontsize=7.2); [sec.append(['F_sensitivity_unresolved', t, '', 'cycle']) for t in tx]
    sec += [['F_sensitivity_unresolved', 'body items with differing W1 vs W1_S60 candidate set', len(d1), 'cycle'], ['F_sensitivity_unresolved', 'wing items with differing W1 vs W1_S60 candidate set', len(d1w), 'cycle']]
    for k, v in (('wing_items_full_ledger_W1', FULL_W1['wing_items']), ('wing_items_with_candidate_full_ledger_W1', FULL_W1['wing_items_with_candidate']), ('wing_items_unique_full_ledger_W1', FULL_W1['wing_items_unique_candidate']), ('wing_items_multiple_full_ledger_W1', FULL_W1['wing_items_multiple_candidates']), ('wing_items_none_full_ledger_W1', FULL_W1['wing_items_no_candidate']), ('wing_units_unmatched_full_ledger_W1', FULL_W1['wing_units_unmatched']), ('wing_items_with_candidate_full_ledger_W1_S60', FULL_S60['wing_items_with_candidate']), ('wing_items_none_full_ledger_W1_S60', FULL_S60['wing_items_no_candidate']), ('wing_units_unmatched_full_ledger_W1_S60', FULL_S60['wing_units_unmatched']), ('closing_units_excluded_by_tag_roles_full_ledger', EXCL_CLOSING_UNITS), ('closing_wing_units_in_mixed_module_episodes_full_ledger', FULL_CLOSING_WING_MIXED['opened_by_mixed_modules'])): sec.append(['G_scope_warning_numbers_full_ledger', k, v, 'full ledger (m2d_summary.json)'])
    F_.head(f"V6 coverage and uncertainty dashboard | {cycle.replace('_', ' ')} | what is matched, unmatched, excluded, missing or unresolved. Nothing here upgrades an inferred relation.", fontsize=8.5, x=0.01, y=0.985, ha='left')
    return F_.finish(['section', 'metric', 'value', 'scope'], sec, ['m2d_wing_body_items.tsv', 'm2d_wing_body_links_W1.tsv', 'm2d_wing_body_links_W1_S60.tsv', 'm2d_wing_body_links_W3.tsv', 'm2c_closing_batches_C1.tsv', 'm2c_closing_batches_C2.tsv', 'coverage.json'], warning=SCOPE_WARNING)


def wu_res(D, role):
    L = [l for l in D['links']['W3'] if l['level'] == 'OPENING']; mq = sum(float(l['queue_matched_units']) for l in L); tot = sum(int(r['qty']) for r in D['wb_items'].values() if r['level'] == 'OPENING' and r['role'] == role.upper())
    return int(round(tot - mq))


def build_all(cycle):
    man = [v1(cycle), v2(cycle), v3(cycle), v4(cycle, 'C1'), v4(cycle, 'C2')] + [v5(cycle, m) for m in ('W1', 'W1_S60', 'W2', 'W3')] + [v6(cycle)]
    return man


def main(argv):
    cyc = [a for a in argv if a.startswith('--cycle=')]; ep = [a for a in argv if a.startswith('--episode=')]
    cycles = [cyc[0].split('=', 1)[1]] if cyc else [F.cycle_key(*c) for c in F.CYCLES]
    for cy in cycles:
        if ep: print(json.dumps(v2(cy, {ep[0].split('=', 1)[1]}, 'V2_episode_filtered'))); continue
        man = build_all(cy); json.dump(dict(cycle=cy, version=F.VERSION, figures=man), open(os.path.join(FIG, cy, 'figure_manifest.json'), 'w'), indent=1); print(cy, [m['figure'] for m in man])


if __name__ == '__main__': main(sys.argv[1:])
