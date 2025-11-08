"""Utilities for providing stub modules referenced by example configurations."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Dict, Mapping


EXAMPLE_STUB_MODULES: Dict[str, Mapping[str, object]] = {
    "my_module": {"__doc__": "Example package for loguru-config demonstrations."},
    "my_module.secret": {"ENABLED": False},
    "another_library": {},
    "another_library.module": {"VERSION": "0.0"},
    "third_party": {},
    "third_party.module": {"ACTIVE": True},
    "api": {},
    "api.client": {"NAME": "example-client"},
    "secret": {},
    "secret.payment": {"ENABLED": False},
    "payments": {},
    "payments.core": {"ENABLED": True},
    "service": {},
    "service.api": {"__all__": []},
    "service.metrics": {"ENABLED": True},
    "service.debug": {"ENABLED": False},
}

_PACKAGE_NAMES = {
    part
    for name in EXAMPLE_STUB_MODULES
    for part in (".".join(name.split(".")[:i]) for i in range(1, len(name.split("."))))
    if part
}


def _ensure_module(name: str, attrs: Mapping[str, object]) -> ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = ModuleType(name)
        if name in _PACKAGE_NAMES:
            module.__path__ = []  # type: ignore[attr-defined]
        sys.modules[name] = module
    if attrs:
        for key, value in attrs.items():
            setattr(module, key, value)
    if "." in name:
        parent_name, _, child = name.rpartition(".")
        parent = _ensure_module(parent_name, EXAMPLE_STUB_MODULES.get(parent_name, {}))
        setattr(parent, child, module)
        if parent_name in _PACKAGE_NAMES and not hasattr(parent, "__path__"):
            parent.__path__ = []  # type: ignore[attr-defined]
    return module


def ensure_example_stubs() -> None:
    """Ensure stub modules referenced by bundled examples are importable."""

    for name, attrs in EXAMPLE_STUB_MODULES.items():
        _ensure_module(name, attrs)
