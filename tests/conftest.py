"""Shared test configuration.

Mocks the homeassistant package so the integration's modules can be imported
without installing the full Home Assistant runtime.  Every ``homeassistant.*``
submodule that the integration touches at import time must be registered here.
"""
import sys
import json
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

_ha = MagicMock()
_pkce = MagicMock()
_pkce.generate_pkce_pair.return_value = ("test_verifier", "test_challenge")


class _ConfigFlow:
    """Minimal stand-in for Home Assistant ConfigFlow."""

    def __init_subclass__(cls, domain=None, **kwargs):
        """Allow class declarations with ``domain=...``."""
        super().__init_subclass__(**kwargs)
        cls.DOMAIN = domain


class _OptionsFlow:
    """Minimal stand-in for Home Assistant OptionsFlow."""

    @property
    def config_entry(self):
        """Mirror HA's read-only config_entry property."""
        return getattr(self, "_config_entry", None)


class _ConfigEntry:
    """Minimal stand-in for Home Assistant ConfigEntry."""

# Provide concrete values that const.py relies on at module scope
_ha.const.Platform.SENSOR = "sensor"
_ha.const.Platform.BUTTON = "button"
_ha.const.CONF_CLIENT_ID = "client_id"
_ha.config_entries.ConfigFlow = _ConfigFlow
_ha.config_entries.OptionsFlow = _OptionsFlow
_ha.config_entries.ConfigEntry = _ConfigEntry
_ha.core.callback = lambda method: method


class _StatisticMeanType(IntEnum):
    """Recorder mean types used by real metadata and the upstream reducer fixture."""
    NONE = 0
    ARITHMETIC = 1
    CIRCULAR = 2


_ha.components.recorder.models.StatisticMeanType = _StatisticMeanType
_ha.components.recorder.models.StatisticData = dict
_ha.components.recorder.models.StatisticMetaData = dict
_ha.components.recorder.statistics.async_import_statistics.return_value = None
_ha.components.recorder.statistics.async_add_external_statistics.return_value = None


def translation_resources(language="en"):
    """Read shipped labels for stand-ins; native fallback is tested separately."""
    directory = Path(__file__).parents[1] / "custom_components/mijnted/translations"
    path = directory / f"{language}.json"
    return json.loads((path if path.exists() else directory / "en.json").read_text(encoding="utf-8"))


def flattened_resources(category, language="en"):
    """Flatten test resources into the shape returned at the HA API boundary."""
    def flatten(value, prefix):
        if isinstance(value, dict):
            return {key: text for part, child in value.items()
                    for key, text in flatten(child, f"{prefix}.{part}").items()}
        return {prefix: value}
    return flatten(translation_resources(language)[category], f"component.mijnted.{category}")


async def get_translations(hass, language, category, integrations):
    """Stand in for translation I/O in logic tests, without contacting HA."""
    return flattened_resources(category, language if isinstance(language, str) else "en")


_ha.helpers.translation.async_get_translations = AsyncMock(side_effect=get_translations)

_SUBMODULES = {
    "homeassistant": _ha,
    "homeassistant.const": _ha.const,
    "homeassistant.config_entries": _ha.config_entries,
    "homeassistant.core": _ha.core,
    "homeassistant.helpers": _ha.helpers,
    "homeassistant.helpers.entity": _ha.helpers.entity,
    "homeassistant.helpers.event": _ha.helpers.event,
    "homeassistant.helpers.entity_registry": _ha.helpers.entity_registry,
    "homeassistant.helpers.storage": _ha.helpers.storage,
    "homeassistant.helpers.translation": _ha.helpers.translation,
    "homeassistant.helpers.update_coordinator": _ha.helpers.update_coordinator,
    "homeassistant.components": _ha.components,
    "homeassistant.components.button": _ha.components.button,
    "homeassistant.components.sensor": _ha.components.sensor,
    "homeassistant.components.recorder": _ha.components.recorder,
    "homeassistant.components.recorder.models": _ha.components.recorder.models,
    "homeassistant.components.recorder.statistics": _ha.components.recorder.statistics,
    "homeassistant.data_entry_flow": _ha.data_entry_flow,
    "homeassistant.exceptions": _ha.exceptions,
    "homeassistant.util": _ha.util,
    "homeassistant.util.dt": _ha.util.dt,
}

for name, mock in _SUBMODULES.items():
    sys.modules[name] = mock

_ha.util.dt.now.side_effect = lambda: datetime.now(timezone.utc)
_ha.util.dt.get_default_time_zone.return_value = timezone.utc

# Mock runtime dependency imported at module scope by oauth_util.
sys.modules["pkce"] = _pkce


# HA entity classes must be real classes so multiple-inheritance in sensor
# definitions doesn't cause a metaclass conflict between MagicMock instances.
class _CoordinatorEntity:
    def __init__(self, coordinator):
        """Store the coordinator like Home Assistant's base entity."""
        self.coordinator = coordinator
        from custom_components.mijnted.localization import MijnTedTranslations
        if not isinstance(getattr(coordinator, "mijnted_translations", None), MijnTedTranslations):
            coordinator.mijnted_translations = MijnTedTranslations(
                flattened_resources("entity"), flattened_resources("common"),
            )

    def _handle_coordinator_update(self):
        """Allow logic tests to exercise placeholder refreshes."""
        self.async_write_ha_state()


class _SensorEntity:
    @property
    def name(self):
        """Expose labels for recorder logic tests; this does not emulate HA lifecycle."""
        key = getattr(self, "_attr_translation_key", None)
        resources = getattr(self.coordinator, "mijnted_translations", None)
        if key and resources:
            return resources.sensor_name(key).format(**getattr(self, "_attr_translation_placeholders", {}))
        return None


class _ButtonEntity:
    @property
    def name(self):
        """Expose shipped button labels in logic tests."""
        return translation_resources()["entity"]["button"][self._attr_translation_key]["name"]


_ha.helpers.update_coordinator.CoordinatorEntity = _CoordinatorEntity
_ha.components.sensor.SensorEntity = _SensorEntity
_ha.components.button.ButtonEntity = _ButtonEntity
