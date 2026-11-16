"""Plugin registry: register / get / enable / disable / configure / list; rejects duplicate names and incompatible versions."""
import re
from .contract import Plugin
from . import API_VERSION


class RegistryError(Exception):
    def __init__(self, code, msg=''): super().__init__(f'{code}: {msg}'); self.code = code


_SEMVER = re.compile(r'[0-9]{1,40}\.[0-9]{1,40}\.[0-9]{1,40}\Z')


class Registry:
    def __init__(self, api_version=API_VERSION):
        self.api_version = api_version; self._items = {}; self._order = []

    def register(self, plugin, enabled=True):
        if not isinstance(plugin, Plugin): raise RegistryError('NOT_A_PLUGIN', type(plugin).__name__)
        if not isinstance(plugin.name, str) or not re.match(r'^[a-z][a-z0-9_]*\Z', plugin.name): raise RegistryError('INVALID_NAME', repr(plugin.name))
        if not isinstance(plugin.version, str) or not _SEMVER.match(plugin.version): raise RegistryError('INVALID_VERSION', repr(plugin.version))
        if plugin.api_version != self.api_version: raise RegistryError('INCOMPATIBLE_API_VERSION', f'{plugin.name} needs api {plugin.api_version}, registry is {self.api_version}')
        if plugin.name in self._items: raise RegistryError('DUPLICATE_NAME', plugin.name)
        self._items[plugin.name] = [plugin, bool(enabled)]; self._order.append(plugin.name)

    def get(self, name):
        if name not in self._items: raise RegistryError('UNKNOWN_PLUGIN', name)
        return self._items[name][0]

    def enable(self, name): self.get(name); self._items[name][1] = True
    def disable(self, name): self.get(name); self._items[name][1] = False

    def configure(self, name, config):
        old = self.get(name); new = type(old)(config)            # validates; the old instance stays if this raises
        self._items[name][0] = new; return new

    def require_version(self, name, wanted):
        """a scenario or caller asks for plugin `name` at version `wanted`: the major number must match"""
        have = self.get(name).version
        if have.split('.')[0] != wanted.split('.')[0]: raise RegistryError('INCOMPATIBLE_VERSION', f'{name}: have {have}, wanted {wanted}')

    def list(self): return [(n, self._items[n][0].version, self._items[n][1], self._items[n][0].config_hash) for n in self._order]
    def enabled(self): return [self._items[n][0] for n in self._order if self._items[n][1]]
