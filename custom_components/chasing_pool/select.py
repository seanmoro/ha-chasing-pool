from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CLEANING_MODES,
    CLEANING_ZONES,
    DOMAIN,
    LIGHT_STRIP_MODES,
    POOL_SHAPES,
)
from .coordinator import ChasingPoolCoordinator
from .entity import ChasingPoolEntity

_MODE_BY_LABEL = {label: value for value, label in CLEANING_MODES.items()}
_SHAPE_BY_LABEL = {label: value for value, label in POOL_SHAPES.items()}
_ZONE_BY_LABEL = {label: value for value, label in CLEANING_ZONES.items()}
_LIGHT_BY_LABEL = {label: value for value, label in LIGHT_STRIP_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ChasingPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ChasingCleaningProgramSelect(coordinator),
            ChasingPoolShapeSelect(coordinator),
            ChasingCleaningZoneSelect(coordinator),
            ChasingLightStripSelect(coordinator),
        ]
    )


class ChasingCleaningProgramSelect(ChasingPoolEntity, SelectEntity):
    _attr_name = "Cleaning Program"
    _attr_options = list(CLEANING_MODES.values())

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_cleaning_program"

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return CLEANING_MODES.get(self.coordinator.data.mode)

    async def async_select_option(self, option: str) -> None:
        mode = _MODE_BY_LABEL[option]
        await self.coordinator.async_publish_command({"mode": mode})


class ChasingPoolShapeSelect(ChasingPoolEntity, SelectEntity):
    _attr_name = "Pool Shape"
    _attr_options = list(POOL_SHAPES.values())

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_pool_shape"

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return POOL_SHAPES.get(self.coordinator.data.shape)

    async def async_select_option(self, option: str) -> None:
        shape = _SHAPE_BY_LABEL[option]
        await self.coordinator.async_publish_command({"shape": shape})


class ChasingCleaningZoneSelect(ChasingPoolEntity, SelectEntity):
    _attr_name = "Cleaning Zone"
    _attr_options = list(CLEANING_ZONES.values())

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_cleaning_zone"

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return CLEANING_ZONES.get(self.coordinator.data.zone)

    async def async_select_option(self, option: str) -> None:
        zone = _ZONE_BY_LABEL[option]
        await self.coordinator.async_publish_command({"zone": zone})


class ChasingLightStripSelect(ChasingPoolEntity, SelectEntity):
    _attr_name = "Light Strip"
    _attr_options = list(LIGHT_STRIP_MODES.values())

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_light_strip"

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return LIGHT_STRIP_MODES.get(self.coordinator.data.light_strip)

    async def async_select_option(self, option: str) -> None:
        light_strip = _LIGHT_BY_LABEL[option]
        await self.coordinator.async_publish_command({"lightStrip": light_strip})
