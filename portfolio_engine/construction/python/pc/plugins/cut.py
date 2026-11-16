"""basket_cut: transparent, configurable EXAMPLE cut policies. They are not Algo 8 rules and are not claimed to be good rules.

policy MARK_ADVERSE_MOVE  a short leg triggers when mark >= entry*(1+trigger_bp/10000); a long leg when mark <= entry*(1-trigger_bp/10000).
                          entry = the leg's integer volume-weighted average seed price, ROUNDED DOWN to a whole paise (so the threshold can differ from the exact one by < 1 paise x (1+bp/10000))
policy SCHEDULED          every selected leg triggers once ts >= cut_at_ts
scope  LEG                cut only the triggered legs        BASKET   cut every selected leg of the basket (one atomic group)
leg_side_filter / option_type_filter select which legs a policy looks at and cuts (side-aware cutting)
qty_mode UNITS            cut `units` (clamped to the leg only if clamp_to_available=1; otherwise an over-large request is proposed and the risk layer rejects it)
qty_mode FRACTION_BP      cut round-to-nearest-lot(current_lots * fraction_bp / 10000); 10000 = whole leg"""
from ..contract import Plugin, Spec, PluginResult, ProposedAction, Decision, OK, NO_ACTION


class BasketCutPlugin(Plugin):
    name = 'basket_cut'; version = '1.0.0'
    CONFIG_SPEC = {
        'policy': Spec('enum', 'MARK_ADVERSE_MOVE', ('MARK_ADVERSE_MOVE', 'SCHEDULED')),
        'trigger_bp': Spec('int', 2000, minimum=0, maximum=10 ** 6), 'cut_at_ts': Spec('int', 0, minimum=0, maximum=10 ** 11),
        'scope': Spec('enum', 'LEG', ('LEG', 'BASKET')),
        'leg_side_filter': Spec('enum', 'ANY', ('ANY', 'SHORT', 'LONG')), 'option_type_filter': Spec('enum', 'ANY', ('ANY', 'CE', 'PE')),
        'qty_mode': Spec('enum', 'UNITS', ('UNITS', 'FRACTION_BP')), 'units': Spec('int', 65, minimum=0, maximum=10 ** 9), 'fraction_bp': Spec('int', 10000, minimum=0, maximum=10000),
        'clamp_to_available': Spec('int', 0, minimum=0, maximum=1), 'max_cuts_per_leg': Spec('int', 1, minimum=1, maximum=10 ** 6), 'basket_filter': Spec('str', '*'),
    }

    def _qty(self, ctx, leg):
        c = self.config
        if c['qty_mode'] == 'UNITS':
            q = c['units']
            return min(q, leg.current) if c['clamp_to_available'] else q
        lot = ctx.lot_size(leg.instrument_id); lots = leg.current // lot
        return ((lots * c['fraction_bp'] + 5000) // 10000) * lot

    def evaluate(self, ctx):
        c = self.config; res = PluginResult(); ts = ctx.ts
        def dec(b, l, outcome, reason, detail, info): res.decisions.append(Decision(ts, self.name, self.version, b, l, outcome, reason, detail, info))
        for bk in ctx.baskets:
            if c['basket_filter'] not in ('*', bk.basket_id) or bk.status == 'FULLY_CUT': continue
            cand = [l for l in bk.legs if (c['leg_side_filter'] == 'ANY' or (c['leg_side_filter'] == 'SHORT') == (l.side < 0)) and (c['option_type_filter'] == 'ANY' or l.instrument_id.split('|')[2] == c['option_type_filter'])]
            elig = [l for l in cand if l.current > 0 and l.cuts_done < c['max_cuts_per_leg']]
            if not cand: dec(bk.basket_id, '*', 'NOT_PROPOSED', 'NO_MATCHING_LEG', 'filters select no leg', ts); continue
            trig, used = {}, []                       # trig: leg_id -> (detail, newest data timestamp used for that leg)
            for l in elig:
                if c['policy'] == 'SCHEDULED':
                    if ts >= c['cut_at_ts']: trig[l.leg_id] = (f'cut_at_ts={c["cut_at_ts"]}', ts)
                    continue
                m = ctx.mark(l.instrument_id)
                if m is None: dec(bk.basket_id, l.leg_id, 'NOT_PROPOSED', 'NO_MARK_AVAILABLE', 'no mark at or before ts', ts); continue
                px, mts = m; used.append(mts)
                hit = px * 10000 >= l.entry_price * (10000 + c['trigger_bp']) if l.side < 0 else px * 10000 <= l.entry_price * (10000 - c['trigger_bp'])
                if hit: trig[l.leg_id] = (f'mark={px} entry={l.entry_price} trigger_bp={c["trigger_bp"]}', mts)
            if not trig:
                if not elig: dec(bk.basket_id, '*', 'NOT_PROPOSED', 'NO_ELIGIBLE_LEG', 'no leg is eligible (no inventory or max_cuts_per_leg reached)', ts)
                else: dec(bk.basket_id, '*', 'NOT_PROPOSED', 'NO_TRIGGER', f'policy={c["policy"]}', max(used) if used else ts)
                continue
            targets = [l for l in elig if l.leg_id in trig] if c['scope'] == 'LEG' else list(elig)
            group = f'{self.name}|{ts}|{bk.basket_id}' if c['scope'] == 'BASKET' else ''
            for l in targets:
                q = self._qty(ctx, l); why, info = trig.get(l.leg_id, ('basket scope', max([v[1] for v in trig.values()])))
                if q == 0: dec(bk.basket_id, l.leg_id, 'NOT_PROPOSED', 'CUT_QTY_ZERO', f'{why}', ts); continue
                aid = f'{self.name}|{ts}|{bk.basket_id}|{l.leg_id}|CUT'
                res.actions.append(ProposedAction(aid, self.name, self.version, 'CUT', group, bk.basket_id, l.leg_id, q, '', ts, info, 'POLICY_TRIGGERED'))
                dec(bk.basket_id, l.leg_id, 'PROPOSED', 'POLICY_TRIGGERED', f'{why} qty={q}', info)
        res.status = OK if res.actions else NO_ACTION
        return res
