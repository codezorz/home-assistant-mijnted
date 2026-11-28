"""Bind existing primary entity and recorder identities to the right delivery."""

import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .sensors.water import delivery_devices


def legacy_identity(hass: HomeAssistant, entry: ConfigEntry, residential_unit: Any) -> tuple[bool, set[str], str | None]:
    """Find entry-owned legacy entities, physical meter numbers and the old device model."""
    prefix = f"{DOMAIN}_{entry.entry_id}_"
    legacy = False
    numbers = set()
    for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        if entity.platform != DOMAIN or not entity.unique_id.startswith(f"{DOMAIN}_"):
            continue
        scoped = entity.unique_id.startswith(prefix)
        key = entity.unique_id.removeprefix(prefix if scoped else f"{DOMAIN}_")
        if key.startswith(("water_", "meter_")):
            continue
        legacy = True
        if entity.entity_id.startswith("sensor.") and key.startswith("device_"):
            number = key.removeprefix("device_")
            if not scoped:
                number = number.rsplit("_", 1)[-1]
            if re.fullmatch(r"[0-9]+", number):
                numbers.add(number)
    old_device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, residential_unit)})
    model = old_device.model if old_device and entry.entry_id in old_device.config_entries else None
    model = _known_model(model)
    return legacy or bool(model), numbers, model


def _known_model(value: Any) -> str | None:
    """Ignore placeholder models and accept only normalized API model codes."""
    if not isinstance(value, str):
        return None
    value = value.strip().casefold()
    return value if value not in {"", "unknown", "none"} else None


def match_legacy_delivery(
    deliveries: dict[str, dict[str, Any]], numbers: set[str], model: str | None,
) -> str | None:
    """Use positive identity evidence; conflicting or ambiguous evidence cannot bind history."""
    number_matches = {
        key for key, payload in deliveries.items()
        if any(str(row.get("deviceNumber")) in numbers for row in delivery_devices(payload))
    }
    models = {key: _known_model(payload.get("active_model")) for key, payload in deliveries.items()}
    model_matches = {key for key, candidate in models.items() if model and candidate == model}
    matches = number_matches & model_matches
    if len(matches) == 1:
        return next(iter(matches))
    if not number_matches and len(model_matches) == 1 and all(models.values()):
        return next(iter(model_matches))
    if len(number_matches) == 1 and not model_matches and all(delivery_devices(payload) for payload in deliveries.values()):
        return next(iter(number_matches))
    return None
