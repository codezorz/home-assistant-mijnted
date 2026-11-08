"""Persist language-independent numbering for duplicate device display contexts."""

from copy import deepcopy
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .sensors.water import delivery_devices, delivery_payloads, get_water_kind, is_water_delivery

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1


def _identity_order(entity_key: str) -> Tuple[Any, ...]:
    """Use natural device-number ordering, with an exact-string tie breaker."""
    def parts(value: str) -> Tuple[Any, ...]:
        """Compare numeric chunks numerically and preserve arbitrary identifiers."""
        return tuple((0, int(part)) if part.isdecimal() else (1, part)
                     for part in re.split(r"([0-9]+)", value))
    number = entity_key.split("_device_", 1)[-1] if entity_key.startswith("water_") else entity_key.removeprefix("device_")
    return parts(number), parts(entity_key), entity_key


def _context(family: str, device_number: str, room: Any, kind: Optional[str] = None) -> Dict[str, Any]:
    """Identify equal generated contexts without translating or altering API names."""
    room = room if isinstance(room, str) and room else None
    group = json.dumps([family, room or device_number, kind], ensure_ascii=False)
    return {"group": group, "room": room, "kind": kind}


def _observed_contexts(data: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Collect primary and water contexts using the same discovery/classification rules."""
    contexts: Dict[str, Dict[str, Any]] = {}
    for device in delivery_devices(data):
        number = device.get("deviceNumber")
        if number is not None:
            key = f"device_{number}"
            contexts.setdefault(key, _context("device", str(number), device.get("room")))
    for delivery_type, delivery in delivery_payloads(data).items():
        if not is_water_delivery(delivery):
            continue
        kind = get_water_kind(delivery_type, delivery.get("active_model"))
        for device in delivery_devices(delivery):
            number = device.get("deviceNumber")
            if number is None:
                continue
            key = f"water_{delivery_type}_device_{number}"
            device_kind = kind
            if kind is None and not delivery.get("active_model"):
                device_kind = previous.get(key, {}).get("kind")
            contexts.setdefault(key, _context("water", str(number), device.get("room"), device_kind))
    return contexts


def _valid_state(stored: Any) -> bool:
    """Reject inconsistent assignments rather than reusing a reserved number."""
    if not isinstance(stored, dict):
        return False
    groups, devices = stored.get("groups"), stored.get("devices")
    if not isinstance(groups, dict) or not isinstance(devices, dict):
        return False
    for group, members in groups.items():
        if not isinstance(group, str) or not isinstance(members, dict) or not members:
            return False
        if any(not isinstance(key, str) or not key or type(number) is not int or number < 1
               for key, number in members.items()):
            return False
        if len(set(members.values())) != len(members):
            return False
    for key, context in devices.items():
        if not isinstance(key, str) or not isinstance(context, dict):
            return False
        if not {"group", "room", "kind"} <= context.keys():
            return False
        group = context.get("group")
        if not isinstance(group, str) or key not in groups.get(group, {}):
            return False
        if context.get("room") is not None and not isinstance(context["room"], str):
            return False
        if context.get("kind") not in (None, "warm", "cold"):
            return False
    return True


class DeviceNameTracker:
    """Reserve per-context ordinals independently of monthly consumption caches.

    A singleton reserves its first ordinal but shows no suffix. Once another
    identity joins that context, all members are numbered. Reservations and last
    observed contexts survive absent readings, room changes, and reloads.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Scope assignments to one installation without changing entity identity."""
        self._store = Store(hass, _STORAGE_VERSION, f"{DOMAIN}_device_names_{entry_id}")
        self._groups: Dict[str, Dict[str, int]] = {}
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        self._dirty = False

    async def _async_load(self) -> bool:
        """Retry failed reads without overwriting existing durable assignments."""
        if self._loaded:
            return True
        try:
            stored = await self._store.async_load()
            if stored is not None:
                if not _valid_state(stored):
                    raise ValueError("invalid device-name assignments")
                self._groups = deepcopy(stored["groups"])
                self._devices = deepcopy(stored["devices"])
            self._loaded = True
            return True
        except Exception as err:
            _LOGGER.warning("Could not restore device-name numbering (%s)", type(err).__name__)
            return False

    def _apply_contexts(self, contexts: Dict[str, Dict[str, Any]]) -> None:
        """Append new identities without reordering or reclaiming existing slots."""
        for key in sorted(contexts, key=_identity_order):
            context = contexts[key]
            members = self._groups.setdefault(context["group"], {})
            if key not in members:
                members[key] = max(members.values(), default=0) + 1
                self._dirty = True
            if self._devices.get(key) != context:
                self._devices[key] = context
                self._dirty = True

    def _projection(self) -> Dict[str, Dict[str, Any]]:
        """Expose detached name context and suffixes for entity properties to read."""
        return {
            key: {
                "room": context["room"], "kind": context["kind"],
                "number": self._groups[context["group"]][key]
                if len(self._groups[context["group"]]) > 1 else None,
            }
            for key, context in self._devices.items()
        }

    async def async_update(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Prepare naming before coordinator listeners run, persisting only changes."""
        if not await self._async_load():
            return {}
        self._apply_contexts(_observed_contexts(data, self._devices))
        if self._dirty:
            try:
                await self._store.async_save(deepcopy({"groups": self._groups, "devices": self._devices}))
                self._dirty = False
            except Exception as err:
                _LOGGER.warning("Could not persist device-name numbering (%s)", type(err).__name__)
        return self._projection()
