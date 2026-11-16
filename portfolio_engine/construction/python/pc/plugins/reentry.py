"""basket_reentry: transparent, configurable EXAMPLE re-entry policy. A re-entry is only ever proposed for an accepted cut (its lineage) and becomes a NEW synthetic fill.
Order of checks per outstanding cut: limits -> cooldown -> window -> mark available -> price band -> propose. Each outcome is logged with a reason."""
from ..contract import Plugin, Spec, PluginResult, ProposedAction, Decision, OK, NO_ACTION


class BasketReentryPlugin(Plugin):
    name = 'basket_reentry'; version = '1.0.0'
    CONFIG_SPEC = {
        'cooldown_s': Spec('int', 600, minimum=0), 'max_wait_s': Spec('int', 0, minimum=0, doc='0 = no limit'),
        'max_reentries_per_cut': Spec('int', 1, minimum=1), 'max_reentry_fraction_bp': Spec('int', 10000, minimum=0, maximum=10000),
        'qty_mode': Spec('enum', 'RESTORE', ('RESTORE', 'UNITS')), 'units': Spec('int', 0, minimum=0),
        'price_condition': Spec('enum', 'NONE', ('NONE', 'WITHIN_BAND')), 'band_bp': Spec('int', 1000, minimum=0), 'basket_filter': Spec('str', '*'),
    }

    def evaluate(self, ctx):
        c = self.config; res = PluginResult(); ts = ctx.ts
        legs = {(b.basket_id, l.leg_id): l for b in ctx.baskets for l in b.legs}
        def dec(cut, outcome, reason, detail, info): res.decisions.append(Decision(ts, self.name, self.version, cut.basket_id, cut.leg_id, outcome, reason, detail, info))
        for cut in sorted(ctx.cuts, key=lambda x: x.cut_id):
            if c['basket_filter'] not in ('*', cut.basket_id): continue
            leg = legs[(cut.basket_id, cut.leg_id)]; lot = ctx.lot_size(cut.instrument_id)
            allowed = ((cut.qty // lot) * c['max_reentry_fraction_bp'] // 10000) * lot - cut.reentered; room = leg.initial - leg.current
            qty = min(allowed, room)
            if cut.reentries >= c['max_reentries_per_cut'] or qty <= 0: dec(cut, 'NOT_PROPOSED', 'REENTRY_LIMIT_REACHED', f'reentries={cut.reentries} reentered={cut.reentered} cut_qty={cut.qty}', ts); continue
            if ts < cut.ts + c['cooldown_s']: dec(cut, 'NOT_PROPOSED', 'COOLDOWN_ACTIVE', f'cut_ts={cut.ts} cooldown_s={c["cooldown_s"]} eligible_ts={cut.ts + c["cooldown_s"]}', ts); continue
            if c['max_wait_s'] and ts > cut.ts + c['max_wait_s']: dec(cut, 'NOT_PROPOSED', 'WINDOW_EXPIRED', f'cut_ts={cut.ts} max_wait_s={c["max_wait_s"]}', ts); continue
            m = ctx.mark(cut.instrument_id)
            if m is None: dec(cut, 'NOT_PROPOSED', 'NO_MARK_AVAILABLE', 'no mark at or before ts', ts); continue
            px, mts = m
            if c['price_condition'] == 'WITHIN_BAND' and abs(px - cut.price) * 10000 > c['band_bp'] * cut.price:
                dec(cut, 'NOT_PROPOSED', 'PRICE_CONDITION_NOT_MET', f'mark={px} cut_price={cut.price} band_bp={c["band_bp"]}', mts); continue
            q = qty if c['qty_mode'] == 'RESTORE' else min(c['units'], qty)
            if q <= 0: dec(cut, 'NOT_PROPOSED', 'REENTRY_LIMIT_REACHED', 'configured units give zero quantity', ts); continue
            aid = f'{self.name}|{ts}|{cut.basket_id}|{cut.leg_id}|REENTRY'
            res.actions.append(ProposedAction(aid, self.name, self.version, 'REENTRY', '', cut.basket_id, cut.leg_id, q, cut.cut_id, ts, mts, 'REENTRY_ELIGIBLE'))
            dec(cut, 'PROPOSED', 'REENTRY_ELIGIBLE', f'mark={px} cut_price={cut.price} qty={q}', mts)
        res.status = OK if res.actions else NO_ACTION
        return res
