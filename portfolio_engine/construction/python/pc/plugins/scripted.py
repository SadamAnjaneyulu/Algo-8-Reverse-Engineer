"""scripted_actions: proposes exactly the ACTION lines of the scenario that carry the current timestamp. It exists so tests and users can push
arbitrary (including invalid or hostile) actions through the same validation path as real plugins."""
from ..contract import Plugin, PluginResult, ProposedAction, Decision, OK, NO_ACTION


class ScriptedActionsPlugin(Plugin):
    name = 'scripted_actions'; version = '1.0.0'
    CONFIG_SPEC = {}

    def evaluate(self, ctx):
        res = PluginResult()
        for a in ctx.scripted:
            res.actions.append(ProposedAction(a.action_id, a.plugin or self.name, a.version or self.version, a.type, a.group_id, a.basket_id, a.leg_id, a.qty, a.parent_cut_id, a.ts, a.info_ts, 'SCRIPTED'))
            res.decisions.append(Decision(ctx.ts, self.name, self.version, a.basket_id, a.leg_id, 'PROPOSED', 'SCRIPTED', f'type={a.type} qty={a.qty}', ctx.ts))       # the claimed info_ts is on the action row, where the validator checks it
        res.status = OK if res.actions else NO_ACTION
        return res
