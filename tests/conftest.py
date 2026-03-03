"""Shared test configuration.

Mocks the homeassistant package so the integration's modules can be imported
without installing the full Home Assistant runtime.  Every ``homeassistant.*``
submodule that the integration touches at import time must be registered here.
"""
import sys
from unittest.mock import MagicMock

_ha = MagicMock()

# Provide concrete values that const.py relies on at module scope
_ha.const.Platform.SENSOR = "sensor"
_ha.const.Platform.BUTTON = "button"

_SUBMODULES = {
    "homeassistant": _ha,
    "homeassistant.const": _ha.const,
    "homeassistant.config_entries": _ha.config_entries,
    "homeassistant.core": _ha.core,
    "homeassistant.helpers": _ha.helpers,
    "homeassistant.helpers.entity": _ha.helpers.entity,
    "homeassistant.helpers.storage": _ha.helpers.storage,
    "homeassistant.helpers.update_coordinator": _ha.helpers.update_coordinator,
    "homeassistant.components": _ha.components,
    "homeassistant.components.button": _ha.components.button,
    "homeassistant.components.sensor": _ha.components.sensor,
    "homeassistant.components.recorder": _ha.components.recorder,
    "homeassistant.components.recorder.models": _ha.components.recorder.models,
    "homeassistant.components.recorder.statistics": _ha.components.recorder.statistics,
    "homeassistant.data_entry_flow": _ha.data_entry_flow,
    "homeassistant.exceptions": _ha.exceptions,
}

for name, mock in _SUBMODULES.items():
    sys.modules[name] = mock


# HA entity classes must be real classes so multiple-inheritance in sensor
# definitions doesn't cause a metaclass conflict between MagicMock instances.
class _CoordinatorEntity:
    pass


class _SensorEntity:
    pass


class _ButtonEntity:
    pass


_ha.helpers.update_coordinator.CoordinatorEntity = _CoordinatorEntity
_ha.components.sensor.SensorEntity = _SensorEntity
_ha.components.button.ButtonEntity = _ButtonEntity
