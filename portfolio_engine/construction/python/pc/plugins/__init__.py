from .cut import BasketCutPlugin
from .reentry import BasketReentryPlugin
from .scripted import ScriptedActionsPlugin

BUILTIN = {p.name: p for p in (BasketCutPlugin, BasketReentryPlugin, ScriptedActionsPlugin)}
