import pytest
from helpers import *
from pc.contract import Plugin, PluginResult, Spec, fnv1a64
from pc.registry import Registry, RegistryError
from pc.plugins import BasketCutPlugin, BasketReentryPlugin, BUILTIN
from pc.engine import build_registry
from pc.scenario import Scenario


class V2(Plugin):
    name = 'other'; version = '1.0.0'; api_version = 2
    def evaluate(self, ctx): return PluginResult()
class BadVersion(Plugin):
    name = 'bad_version'; version = 'one'
    def evaluate(self, ctx): return PluginResult()


def test_register_get_enable_disable_list_configure():
    r = Registry(); r.register(BasketCutPlugin()); r.register(BasketReentryPlugin(), enabled=False)
    assert [(n, v, e) for n, v, e, _ in r.list()] == [('basket_cut', '1.0.0', True), ('basket_reentry', '1.0.0', False)]
    assert len(r.enabled()) == 1; r.enable('basket_reentry'); assert len(r.enabled()) == 2; r.disable('basket_cut'); assert [p.name for p in r.enabled()] == ['basket_reentry']
    h = r.get('basket_cut').config_hash; r.configure('basket_cut', {'trigger_bp': 500}); assert r.get('basket_cut').config_hash != h and r.get('basket_cut').config['trigger_bp'] == 500
    from pc.contract import ConfigError
    with pytest.raises(ConfigError): r.configure('basket_cut', {'trigger_bp': -1})
    assert r.get('basket_cut').config['trigger_bp'] == 500                                   # failed configuration changes nothing
    with pytest.raises(RegistryError) as e: r.get('nope'); assert e.value.code == 'UNKNOWN_PLUGIN'


def test_duplicates_and_incompatible_versions_are_rejected():
    r = Registry(); r.register(BasketCutPlugin())
    for plug, code in ((BasketCutPlugin(), 'DUPLICATE_NAME'), (V2(), 'INCOMPATIBLE_API_VERSION'), (BadVersion(), 'INVALID_VERSION')):
        with pytest.raises(RegistryError) as e: r.register(plug)
        assert e.value.code == code
    with pytest.raises(RegistryError) as e: r.register(object()); assert e.value.code == 'NOT_A_PLUGIN'
    with pytest.raises(RegistryError) as e: r.require_version('basket_cut', '2.0.0'); assert e.value.code == 'INCOMPATIBLE_VERSION'
    r.require_version('basket_cut', '1.9.9')


def test_fnv1a64_known_vectors():
    assert fnv1a64('') == 'cbf29ce484222325' and fnv1a64('a') == 'af63dc4c8601ec8c'


class FlattenLeg(Plugin):
    """a drop-in plugin defined OUTSIDE the engine: cut the WPE leg completely at/after `at_ts`"""
    name = 'flatten_leg'; version = '1.0.0'; CONFIG_SPEC = {'at_ts': Spec('int', 0, minimum=0)}
    def evaluate(self, ctx):
        from pc.contract import ProposedAction, OK
        res = PluginResult()
        if ctx.ts < self.config['at_ts']: return res
        for b in ctx.baskets:
            for l in b.legs:
                if l.leg_id == 'WPE' and l.current > 0: res.actions.append(ProposedAction(f'flatten_leg|{ctx.ts}', self.name, self.version, 'CUT', '', b.basket_id, l.leg_id, l.current, '', ctx.ts, ctx.ts, 'FLATTEN')); res.status = OK
        return res


def test_a_new_plugin_runs_without_touching_the_core():
    text = scn(L('PLUGIN', 'flatten_leg', '1.0.0', 1) + cfg('flatten_leg', 'at_ts', T0 + 100) + mark(0, WPE, 250) + tick(0) + tick(200))
    _, f = run(text, extra={'flatten_leg': FlattenLeg}); a = table(f['actions.tsv'])
    assert len(a) == 1 and a[0]['plugin'] == 'flatten_leg' and a[0]['status'] == 'ACCEPTED' and a[0]['qty'] == '195' and a[0]['fill_side'] == '-1'
    assert 'flatten_leg' not in BUILTIN                                                      # nothing was added to the built-in catalogue
    from pc.contract import ConfigError
    with pytest.raises(ConfigError): build_registry(Scenario.parse(text))                    # without the drop-in the scenario is refused
    with pytest.raises(RegistryError): build_registry(Scenario.parse(scn(L('PLUGIN', 'basket_cut', '2.0.0', 1) + tick(0))))


def test_a_failing_plugin_fails_closed_and_the_run_continues():
    class Boom(Plugin):
        name = 'boom'; version = '1.0.0'
        def evaluate(self, ctx): raise RuntimeError('bug')
    _, f = run(scn(plugins() + L('PLUGIN', 'boom', '1.0.0', 1) + mark(0, SCE, 10000) + tick(0) + tick(1)), extra={'boom': Boom})
    d = [x for x in table(f['decisions.tsv']) if x['plugin'] == 'boom']; assert len(d) == 2 and all(x['reason'] == 'PLUGIN_ERROR' for x in d) and kv(f, 'plugin_errors') == '2'


def test_a_plugin_with_a_non_text_name_or_version_is_a_registry_error_not_a_crash():
    class NumName(Plugin):
        name = 123; version = '1.0.0'
        def evaluate(self, ctx): return PluginResult()
    class NumVersion(Plugin):
        name = 'numversion'; version = 1
        def evaluate(self, ctx): return PluginResult()
    class LongVersion(Plugin):
        name = 'longversion'; version = '1.0.' + '0' * 41
        def evaluate(self, ctx): return PluginResult()
    class NewlineName(Plugin):
        name = 'ok\n'; version = '1.0.0'
        def evaluate(self, ctx): return PluginResult()
    for cls, code in ((NumName, 'INVALID_NAME'), (NumVersion, 'INVALID_VERSION'), (LongVersion, 'INVALID_VERSION'), (NewlineName, 'INVALID_NAME')):
        with pytest.raises(RegistryError) as e: Registry().register(cls())
        assert e.value.code == code
