from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ChasingPoolCoordinator
from .entity import ChasingPoolEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ChasingPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ChasingCleaningDurationNumber(coordinator)])


class ChasingCleaningDurationNumber(ChasingPoolEntity, NumberEntity):
    _attr_name = "Cleaning Duration"
    _attr_native_min_value = 5
    _attr_native_max_value = 300
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_cleaning_duration"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.minutes

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_publish_command({"minutes": int(value)})
