"""GLIO-NONCODE research workbench.

The package exposes a small, deterministic vertical slice for turning a case
manifest into inspectable regulatory hypotheses. It is intentionally local
first and research-use only.
"""

from __future__ import annotations

from importlib import import_module as _import_module
from sys import modules as _modules
from types import ModuleType as _ModuleType

from . import _public_surface as _surface

__all__ = list(_surface.ALL)
__version__ = _surface.CONSTANTS["__version__"]

_EXPORTS = _surface.EXPORTS
_CONSTANTS = _surface.CONSTANTS
_CHILD_MODULES = _surface.CHILD_MODULES
_EXPORT_CACHE: dict[str, object] = {}
_CHILD_CACHE: dict[str, _ModuleType] = {}
_USER_OVERRIDES: dict[str, object] = {}


def _missing_attribute(name: str) -> AttributeError:
    return AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _resolve_export(name: str) -> object:
    cached = _EXPORT_CACHE.get(name)
    if cached is not None or name in _EXPORT_CACHE:
        return cached

    module_name, attribute = _EXPORTS[name]
    module = _import_module(module_name)
    value = module if attribute is None else getattr(module, attribute)
    _EXPORT_CACHE[name] = value
    return value


def _resolve_public(name: str) -> object:
    if name in _USER_OVERRIDES:
        return _USER_OVERRIDES[name]
    if name in _CONSTANTS:
        return _CONSTANTS[name]
    if name in _EXPORTS:
        return _resolve_export(name)
    child_name = _CHILD_MODULES.get(name)
    if child_name is not None:
        module = _import_module(child_name)
        _CHILD_CACHE[name] = module
        return module
    raise _missing_attribute(name)


def __getattr__(name: str) -> object:
    """Resolve a declared root export or direct child module on first use."""

    return _resolve_public(name)


def __dir__() -> list[str]:
    """Return the complete discoverable surface without resolving exports."""

    return sorted(
        set(globals())
        | set(_EXPORTS)
        | set(_CONSTANTS)
        | set(_CHILD_MODULES)
    )


class _LazyPackage(_ModuleType):
    """Module type that protects canonical exports from child insertion."""

    def __getattribute__(self, name: str) -> object:
        if name in _USER_OVERRIDES:
            return _USER_OVERRIDES[name]
        if name in _CONSTANTS:
            return _CONSTANTS[name]
        if name in _EXPORTS:
            return _resolve_export(name)
        return _ModuleType.__getattribute__(self, name)

    def __setattr__(self, name: str, value: object) -> None:
        canonical = name in _EXPORTS or name in _CONSTANTS
        child_name = _CHILD_MODULES.get(name)
        inserted_child = (
            canonical
            and isinstance(value, _ModuleType)
            and value.__name__ == child_name
        )
        if inserted_child:
            _CHILD_CACHE[name] = value
            return
        if canonical:
            _USER_OVERRIDES[name] = value
        _ModuleType.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in _EXPORTS or name in _CONSTANTS:
            _USER_OVERRIDES.pop(name, None)
            _EXPORT_CACHE.pop(name, None)
            namespace = _ModuleType.__getattribute__(self, "__dict__")
            namespace.pop(name, None)
            return
        _ModuleType.__delattr__(self, name)


_package = _modules[__name__]
_package.__class__ = _LazyPackage
del _package
