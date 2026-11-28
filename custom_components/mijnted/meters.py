"""Stable identities and passive coordinator views for additional meters."""

from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UNIT_HEAT_ENERGY, UNIT_MIJNTED, UNIT_WATER


def canonical_unit(value: Any) -> str | None:
    """Normalize unit spellings used in MijnTed payloads."""
    return {
        "m³": UNIT_WATER, "m3": UNIT_WATER, "gj": UNIT_HEAT_ENERGY,
        "eenheid": UNIT_MIJNTED, "eenheden": UNIT_MIJNTED,
        "einheiten": UNIT_MIJNTED, "units": UNIT_MIJNTED,
    }.get(str(value).strip().casefold())


@dataclass(frozen=True)
class Meter:
    """A delivery/unit pair, with presentation kept out of its identity."""

    delivery_type: str
    unit: str
    kind: str

    @property
    def key(self) -> str:
        """Return a stable selector and payload key scoped to one entry."""
        return f"{self.delivery_type}_{'m3' if self.unit == UNIT_WATER else self.unit.lower()}"

    def scope(self, entry_id: str) -> str:
        """Namespace storage, entities and series by entry and meter."""
        return f"{entry_id}_meter_{self.key}"

    def label(self, translations: Any) -> str:
        """Return the translated delivery label with its canonical unit."""
        return f"{translations.common_label(f'delivery_{self.kind}')} ({self.unit})"


class MeterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Feed local entity listeners from one entry poll without owning API I/O."""

    def __init__(self, parent: DataUpdateCoordinator, meter: Meter) -> None:
        """Initialize an unscheduled view of the parent data."""
        super().__init__(parent.hass, parent.logger, name=f"{DOMAIN}_{meter.key}", config_entry=None)
        self.parent = parent
        self.mijnted_meter = meter

    @property
    def mijnted_translations(self) -> Any:
        """Share the entry's Home Assistant translation resources."""
        return self.parent.mijnted_translations

    def update_from_parent(self) -> None:
        """Publish the prepared snapshot or mark only this meter unavailable."""
        data = (self.parent.data or {}).get("meter_data", {}).get(self.mijnted_meter.key)
        if self.parent.last_update_success and data and data.get("meter_available", True):
            self.async_set_updated_data(data)
        else:
            self.async_set_update_error(UpdateFailed(f"No fresh data for {self.mijnted_meter.key}"))

    async def async_request_refresh(self) -> None:
        """Route entity refresh requests through the single entry poll."""
        await self.parent.async_request_refresh()


def meter_coordinators(parent: DataUpdateCoordinator) -> dict[str, MeterCoordinator]:
    """Return active meter views after the parent has published its snapshots."""
    views = getattr(parent, "mijnted_meter_coordinators", None)
    return views if isinstance(views, dict) else {}
