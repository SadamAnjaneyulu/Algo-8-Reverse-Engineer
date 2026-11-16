"""Simulation / execution layer.

At every evaluation time t:  seeds <= t are applied  ->  each enabled plugin (registration order) sees a read-only context (data <= t)  ->  its proposed
actions are validated (atomic groups)  ->  accepted actions become NEW explicit synthetic fills applied through the historical engine's ledger (PortfolioState.apply_fill).
Plugins never touch the ledger or the book. After every fill the book's claims are reconciled with the ledger's inventory."""
import os
from . import EVIDENCE
from ._hist import hist_ledger, hist_schema, hist_tsvio
from .contract import Plugin, PluginResult, Decision, ProposedAction, fnv1a64, ERROR, ConfigError
from .model import Book, MarkStore, EvalContext, LegView, BasketView, CutView, ScriptedAction
from .plugins import BUILTIN
from .registry import Registry
from . import risk as R


class EngineInvariantError(Exception): pass


def build_registry(sc, extra=None):
    """registry from the scenario's PLUGIN/CONFIG lines; `extra` = {name: PluginClass} for drop-in plugins that are not built in"""
    cat = dict(BUILTIN); cat.update(extra or {}); reg = Registry()
    for name, version, enabled in sc.plugins:
        if name not in cat: raise ConfigError(f'scenario names unknown plugin {name!r}')
        plug = cat[name](sc.configs.get(name, {})); reg.register(plug, enabled); reg.require_version(name, version)
    return reg


def _instrument(iid, lot):
    und, expiry, cp, strike = iid.split('|')
    return hist_schema.Instrument(iid, und, 'NSEFO', 'OPTION', cp, int(strike), expiry, lot, hist_schema.TICK_PAISE, 'SYNTHETIC')


def _tsv(header_note, cols, rows):
    return f'# {header_note}\n' + '\t'.join(cols) + '\n' + ''.join('\t'.join(str(x) for x in r) + '\n' for r in rows)


class Simulation:
    def __init__(self, scenario, registry=None):
        self.sc = scenario; self.registry = registry or build_registry(scenario)
        self.lots = dict(scenario.instruments); self.ins = {i: _instrument(i, l) for i, l in self.lots.items()}
        self.ledger = hist_ledger.PortfolioState(scenario.method, self.ins)           # THE position state (historical engine code)
        self.book = Book(); self.marks = MarkStore(scenario.marks); self.limits = R.parse_risk(scenario.risk)
        self.fills = []; self.dec_rows = []; self.act_rows = []; self.state_rows = []; self.lin_rows = []
        self._pc = 0; self._seed_i = 0; self.counts = {}; self._done = False

    # ------------------------------------------------------------------ helpers
    def _inv(self): return {i: self.ledger.signed_inventory(i) for i in self.ins}

    def _exposure(self): return R.exposure(self._inv(), {})

    def _bump(self, key): self.counts[key] = self.counts.get(key, 0) + 1

    def _reconcile(self):
        claims = {}
        for legs in self.book.baskets.values():
            for l in legs.values(): claims[l.instrument_id] = claims.get(l.instrument_id, 0) + l.side * l.current
        for iid in self.ins:
            if self.ledger.signed_inventory(iid) != claims.get(iid, 0): raise EngineInvariantError(f'ledger inventory {self.ledger.signed_inventory(iid)} != basket claims {claims.get(iid, 0)} for {iid}')

    def _fill(self, fid, iid, ts, side, qty, px, parent, module, source):
        f = hist_schema.Fill(fid, len(self.fills) + 1, parent, module, iid, ts, side, qty, px, qty, 'Filled', False, 'SYNTHETIC_TEST', source)
        self.ledger.apply_fill(f); self.fills.append(f); return f

    def _state(self, ts, event_id, action_id, bid, touched, before, after):
        g, s = self._exposure(); inv = self.ledger
        for lid in sorted(self.book.baskets[bid]):
            l = self.book.baskets[bid][lid]; b, a = (before, after) if lid == touched else (l.current, l.current)
            self.state_rows.append((len(self.state_rows) + 1, ts, event_id, action_id, bid, lid, l.instrument_id, l.side, l.initial, b, a, self.book.status(bid), inv.signed_inventory(l.instrument_id), g, s))

    def _context(self, ts):
        baskets = tuple(BasketView(bid, self.book.status(bid), tuple(LegView(bid, l.leg_id, l.instrument_id, l.side, l.initial, l.current, l.entry_price, l.cuts_done) for _, l in sorted(legs.items())))
                        for bid, legs in sorted(self.book.baskets.items()))
        cuts = tuple(CutView(c.cut_id, c.basket_id, c.leg_id, self.book.baskets[c.basket_id][c.leg_id].instrument_id, c.qty, c.ts, c.price, c.reentered, c.reentries) for _, c in sorted(self.book.cuts.items()))
        return EvalContext(ts, self.marks.view(ts), baskets, cuts, self.lots, tuple(ScriptedAction(**a) for a in self.sc.actions if a['ts'] == ts))

    # ------------------------------------------------------------------ seeds (basket creation)
    def _apply_seeds(self, upto):
        while self._seed_i < len(self.sc.seeds) and self.sc.seeds[self._seed_i]['ts'] <= upto:
            d = self.sc.seeds[self._seed_i]; self._seed_i += 1; leg = self.book.leg(d['basket_id'], d['leg_id']); before = leg.current if leg else 0
            f = self._fill(d['fill_id'], d['instrument_id'], d['ts'], d['side'], d['qty'], d['price'], f'seed:{d["basket_id"]}', 'pc', 'pc:SEED')
            self.book.seed(d['basket_id'], d['leg_id'], d['instrument_id'], d['side'], d['qty'], d['price'], d['fill_id']); self._reconcile(); self._bump('seed_fills')
            self._state(d['ts'], d['fill_id'], 'SEED', d['basket_id'], d['leg_id'], before, self.book.leg(d['basket_id'], d['leg_id']).current)
            self.lin_rows.append((d['fill_id'], 'SEED', '', d['basket_id'], d['leg_id'], d['instrument_id'], d['qty'], '', d['fill_id']))

    # ------------------------------------------------------------------ plugin evaluation and action handling
    def _run_plugin(self, plugin, ts):
        try:
            res = plugin.evaluate(self._context(ts))
            if not isinstance(res, PluginResult): raise TypeError('not a PluginResult')
        except Exception:
            self.dec_rows.append((len(self.dec_rows) + 1, ts, plugin.name, plugin.version, '*', '*', 'NOT_PROPOSED', 'PLUGIN_ERROR', 'plugin raised an exception', plugin.config_hash, ts)); self._bump('plugin_errors'); return
        bad = self._invalid_output(plugin, res, ts)
        if bad:
            self.dec_rows.append((len(self.dec_rows) + 1, ts, plugin.name, plugin.version, '*', '*', 'NOT_PROPOSED', 'PLUGIN_ERROR', 'invalid plugin output', plugin.config_hash, ts)); self._bump('plugin_errors'); return
        for d in res.decisions:
            self.dec_rows.append((len(self.dec_rows) + 1, d.ts, d.plugin, d.version, d.basket_id, d.leg_id, d.outcome, d.reason, d.detail, plugin.config_hash, d.info_ts)); self._bump('decision_' + d.outcome)
        groups = []                                           # proposals grouped by group_id, in order of first appearance; an empty group_id means a group of one
        for a in res.actions:
            if a.group_id:
                for g in groups:
                    if g[0] == a.group_id: g[1].append(a); break
                else: groups.append((a.group_id, [a]))
            else: groups.append(('', [a]))
        for _, acts in groups: self._handle_group(plugin, acts, ts)

    @staticmethod
    def _invalid_output(plugin, res, ts):
        """a plugin result must be plain data: exact types, printable ASCII text, honest decision stamps. Anything else drops the whole result (fail closed)."""
        def txt(x): return type(x) is str and all(32 <= ord(c) <= 126 for c in x)
        def num(x): return type(x) is int
        if res.status not in ('OK', 'NO_ACTION', 'ERROR') or not isinstance(res.actions, list) or not isinstance(res.decisions, list): return True
        for d in res.decisions:
            if not isinstance(d, Decision) or not all(txt(x) for x in (d.plugin, d.version, d.basket_id, d.leg_id, d.outcome, d.reason, d.detail)) or not num(d.ts) or not num(d.info_ts): return True
            if d.plugin != plugin.name or d.version != plugin.version or d.ts != ts or d.info_ts > d.ts or d.outcome not in ('PROPOSED', 'NOT_PROPOSED'): return True
        for a in res.actions:
            if not isinstance(a, ProposedAction) or not all(txt(x) for x in (a.action_id, a.plugin, a.version, a.type, a.group_id, a.basket_id, a.leg_id, a.parent_cut_id, a.reason)) or not all(num(x) for x in (a.qty, a.ts, a.info_ts)): return True
        return False

    def _handle_group(self, plugin, acts, ts):
        proj = R.Projection(self.book); inv = self._inv(); reasons = []; failed = None
        for a in acts:
            if failed is not None: reasons.append((R.GROUP_REJECTED, f'group member {failed[0]} failed')); continue
            r = R.check(a, ts, proj, inv, self.lots, self.limits, plugin)
            if r is None:
                leg = proj.book.leg(a.basket_id, a.leg_id); sign = -leg.side if a.type == 'CUT' else leg.side
                proj.delta[leg.instrument_id] = proj.delta.get(leg.instrument_id, 0) + sign * a.qty; proj.book.seen_ids.add(a.action_id)
                (proj.book.cut(a, ts, 0, '-') if a.type == 'CUT' else proj.book.reenter(a)); reasons.append(None)
            else: failed = (a.action_id, r); reasons.append(r)
        ok = failed is None
        for a, r in zip(acts, reasons):
            self.book.seen_ids.add(a.action_id); self._bump('proposed')
            if not ok:
                rr = r or (R.GROUP_REJECTED, f'group member {failed[0]} failed'); self._reject(a, ts, rr[0], rr[1]); continue
            self._execute(a, ts)

    def _reject(self, a, ts, reason, detail):
        self.act_rows.append((len(self.act_rows) + 1, ts, a.action_id, a.plugin, a.version, a.type, a.group_id, a.basket_id, a.leg_id, a.qty, a.parent_cut_id, a.info_ts, 'REJECTED', reason, detail, '', '', ''))
        self._bump('rejected'); self._bump('reason_' + reason)
        leg = self.book.leg(a.basket_id, a.leg_id)
        if leg is not None: self._state(ts, '-', a.action_id, a.basket_id, a.leg_id, leg.current, leg.current)

    def _execute(self, a, ts):
        leg = self.book.leg(a.basket_id, a.leg_id); before = leg.current; m = self.marks.at(leg.instrument_id, ts); px = m[0] if m else leg.last_price            # no mark yet: the leg's latest actual fill price (always a valid tick)
        side = -leg.side if a.type == 'CUT' else leg.side; self._pc += 1; fid = f'PC{self._pc:06d}'
        self._fill(fid, leg.instrument_id, ts, side, a.qty, px, a.action_id, 'pc', f'pc:{a.plugin}@{a.version}')
        (self.book.cut(a, ts, px, fid) if a.type == 'CUT' else self.book.reenter(a, px)); self._reconcile(); self._bump('accepted')
        self.act_rows.append((len(self.act_rows) + 1, ts, a.action_id, a.plugin, a.version, a.type, a.group_id, a.basket_id, a.leg_id, a.qty, a.parent_cut_id, a.info_ts, 'ACCEPTED', 'OK', '', fid, side, px))
        self._state(ts, fid, a.action_id, a.basket_id, a.leg_id, before, leg.current)
        self.lin_rows.append((fid, a.type, a.action_id, a.basket_id, a.leg_id, leg.instrument_id, a.qty, a.parent_cut_id, ','.join(leg.seed_fills)))

    # ------------------------------------------------------------------ run and outputs
    def run(self):
        if self._done: return self
        times = sorted(set(self.sc.ticks))
        for t in times:
            self._apply_seeds(t)
            for plugin in self.registry.enabled(): self._run_plugin(plugin, t)
        self._apply_seeds(1 << 62); self._done = True
        return self

    def files(self):
        self.run(); note = f'{EVIDENCE}; scenario={self.sc.name}; not Algo 8 data'
        ev = f'# {note}\n' + '\t'.join(hist_schema.EVENT_COLUMNS) + '\n' + ''.join('\t'.join([hist_schema.SCHEMA_FILL, x.execution_mode, x.fill_id, str(x.source_row_id), x.parent_order_id, x.module_tag, x.instrument_id, str(x.timestamp_s), str(x.side), str(x.quantity),
                                                                                         str(x.price_paise), str(x.requested_quantity), x.order_status, '0', x.evidence_source]) + '\n' for x in self.fills)
        ins = f'# {note}\n' + '\t'.join(hist_schema.INSTRUMENT_COLUMNS) + '\n' + ''.join('\t'.join([i.instrument_id, i.underlying, i.exchange_segment, i.instrument_type, i.option_type, str(i.strike), i.expiry, str(i.lot_size), str(i.tick_size_paise), i.lot_size_source]) + '\n' for _, i in sorted(self.ins.items()))
        g, s = self._exposure(); digest = fnv1a64(';'.join(f'{i}:{self.ledger.signed_inventory(i)}' for i in sorted(self.ins)))
        summ = [('scenario', self.sc.name), ('evidence', EVIDENCE), ('method', self.sc.method), ('plugins', ','.join(f'{n}@{v}:{int(e)}:{h}' for n, v, e, h in self.registry.list())), ('seed_fills_applied', self.counts.get('seed_fills', 0)), ('duplicate_seed_events_ignored', self.sc.duplicate_seeds),
                ('actions_proposed', self.counts.get('proposed', 0)), ('actions_accepted', self.counts.get('accepted', 0)), ('actions_rejected', self.counts.get('rejected', 0)), ('plugin_errors', self.counts.get('plugin_errors', 0))]
        summ += [('rejected_' + k[7:], v) for k, v in sorted(self.counts.items()) if k.startswith('reason_')]
        summ += [('fills_total', len(self.fills)), ('final_gross_units', g), ('final_short_units', s), ('final_realized_pnl_paise', f'{self.ledger.realized_total():.6f}' if self.ledger.avg else self.ledger.realized_total()), ('final_inventory_digest', digest)]
        return {
            'decisions.tsv': _tsv(note, ['seq', 'ts', 'plugin', 'plugin_version', 'basket_id', 'leg_id', 'outcome', 'reason', 'detail', 'config_hash', 'info_ts'], self.dec_rows),
            'actions.tsv': _tsv(note, ['seq', 'ts', 'action_id', 'plugin', 'plugin_version', 'type', 'group_id', 'basket_id', 'leg_id', 'qty', 'parent_cut_id', 'info_ts', 'status', 'reason', 'detail', 'fill_id', 'fill_side', 'fill_price_paise'], self.act_rows),
            'states.tsv': _tsv(note, ['seq', 'ts', 'event_id', 'action_id', 'basket_id', 'leg_id', 'instrument_id', 'leg_side', 'initial_qty', 'qty_before', 'qty_after', 'basket_status', 'instrument_inventory', 'gross_units', 'short_units'], self.state_rows),
            'lineage.tsv': _tsv(note, ['fill_id', 'kind', 'action_id', 'basket_id', 'leg_id', 'instrument_id', 'qty', 'parent_cut_id', 'origin_seed_fills'], self.lin_rows),
            'events.tsv': ev, 'instruments.tsv': ins, 'summary.tsv': _tsv(note, ['key', 'value'], summ)}

    def write(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        for name, text in self.files().items():
            with open(os.path.join(out_dir, name), 'w', encoding='utf-8', newline='\n') as f: f.write(text)
