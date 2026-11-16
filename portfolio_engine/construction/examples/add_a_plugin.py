"""Adds a new plugin to the simulation WITHOUT touching any file of the framework.
Run from 02_Portfolio_Construction_Skeleton:   PYTHONPATH=python python3 examples/add_a_plugin.py
The new plugin (flatten_leg) cuts the whole long put wing of a basket once a configured time is reached. It is registered by name, listed in the scenario with a PLUGIN line,
configured with a CONFIG line, and its proposals go through the same risk validation as the built-in plugins."""
import os, sys
from pc.contract import Plugin, PluginResult, ProposedAction, Spec, OK
from pc.engine import Simulation, build_registry
from pc.scenario import Scenario

HERE = os.path.dirname(os.path.abspath(__file__))


class FlattenLeg(Plugin):
    name = 'flatten_leg'; version = '1.0.0'; CONFIG_SPEC = {'at_ts': Spec('int', 0, minimum=0, maximum=10 ** 11)}

    def evaluate(self, ctx):                                   # ctx holds only data with timestamp <= ctx.ts, as read-only copies
        res = PluginResult()
        for b in ctx.baskets:
            for leg in b.legs:
                if leg.leg_id == 'WPE' and leg.current > 0 and ctx.ts >= self.config['at_ts']:
                    res.actions.append(ProposedAction(f'flatten_leg|{ctx.ts}|{b.basket_id}', self.name, self.version, 'CUT', '', b.basket_id, leg.leg_id, leg.current, '', ctx.ts, ctx.ts, 'FLATTEN'))
                    res.status = OK
        return res


if __name__ == '__main__':
    text = open(os.path.join(HERE, '..', 'scenarios', 's05_reentry_success.scn'), encoding='ascii').read()
    first_tick = min(int(l.split('\t')[1]) for l in text.split('\n') if l.startswith('TICK\t'))
    text += f'PLUGIN\tflatten_leg\t1.0.0\t1\nCONFIG\tflatten_leg\tat_ts\t{first_tick + 600}\n'
    sc = Scenario.parse(text); sim = Simulation(sc, build_registry(sc, extra={'flatten_leg': FlattenLeg})).run()
    for a in [r for r in sim.act_rows if r[3] == 'flatten_leg']: print(f't+{a[1] - first_tick}s  flatten_leg proposed {a[5]} {a[7]}:{a[8]} qty {a[9]} -> {a[12]}')
