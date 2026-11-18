"""capital_stop: transparent, configurable capital-loss stop (added for the historical backtest; documented extension of the engine).
STATED in Info.txt: a 4 % carry stop-loss and a 1 % stop on capital on expiry day. How those percentages are defined is UNRESOLVED, so this plugin takes explicit rupee-equivalent limits (in paise) and applies them
to the basket's OPEN-LEG mark-to-market loss measured from the leg seed prices (realised effects of earlier cuts are not counted).
  ts <  phase_switch_ts  -> carry_limit_paise   (0 = no stop in that phase)
  ts >= phase_switch_ts  -> expiry_limit_paise  (0 = no stop in that phase)
When the loss reaches the limit every open leg of the basket is cut completely, as ONE atomic group. Do not combine with basket_reentry (it would re-enter the stopped basket)."""
from ..contract import Plugin, Spec, PluginResult, ProposedAction, Decision, OK, NO_ACTION


class CapitalStopPlugin(Plugin):
    name = 'capital_stop'; version = '1.0.0'
    CONFIG_SPEC = {'phase_switch_ts': Spec('int', 0, minimum=0, maximum=10 ** 11), 'carry_limit_paise': Spec('int', 0, minimum=0, maximum=10 ** 15),
                   'expiry_limit_paise': Spec('int', 0, minimum=0, maximum=10 ** 15), 'basket_filter': Spec('str', '*')}

    def evaluate(self, ctx):
        c = self.config; res = PluginResult(); ts = ctx.ts
        def dec(b, outcome, reason, detail, info): res.decisions.append(Decision(ts, self.name, self.version, b, '*', outcome, reason, detail, info))
        for bk in ctx.baskets:
            if c['basket_filter'] not in ('*', bk.basket_id) or bk.status == 'FULLY_CUT': continue
            limit = c['carry_limit_paise'] if ts < c['phase_switch_ts'] else c['expiry_limit_paise']
            open_legs = [l for l in bk.legs if l.current > 0]
            if limit == 0: dec(bk.basket_id, 'NOT_PROPOSED', 'STOP_DISABLED_FOR_PHASE', f'phase={"carry" if ts < c["phase_switch_ts"] else "expiry"}', ts); continue
            loss = 0; used = []; missing = False
            for l in open_legs:
                m = ctx.mark(l.instrument_id)
                if m is None: missing = True; break
                px, mts = m; used.append(mts); loss += -l.side * (px - l.entry_price) * l.current
            if missing: dec(bk.basket_id, 'NOT_PROPOSED', 'NO_MARK_AVAILABLE', 'a leg has no mark at or before ts', ts); continue
            info = max(used) if used else ts
            if loss < limit: dec(bk.basket_id, 'NOT_PROPOSED', 'WITHIN_LIMIT', f'loss_paise={loss} limit_paise={limit}', info); continue
            group = f'{self.name}|{ts}|{bk.basket_id}'
            for l in open_legs:
                res.actions.append(ProposedAction(f'{self.name}|{ts}|{bk.basket_id}|{l.leg_id}|CUT', self.name, self.version, 'CUT', group, bk.basket_id, l.leg_id, l.current, '', ts, info, 'STOP_TRIGGERED'))
                dec(bk.basket_id, 'PROPOSED', 'STOP_TRIGGERED', f'loss_paise={loss} limit_paise={limit} qty={l.current}', info)
        res.status = OK if res.actions else NO_ACTION
        return res
