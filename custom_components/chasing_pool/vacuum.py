from __future__ import annotations

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import DeviceStatus
from .const import DOMAIN, STATUS_CLEANING, STATUS_IDLE, STATUS_PAUSED, MODE_RETRIEVE
from .coordinator import ChasingPoolCoordinator
from .entity import ChasingPoolEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ChasingPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ChasingPoolVacuum(coordinator)])


def _activity(status: DeviceStatus) -> VacuumActivity:
    if status.is_returning:
        return VacuumActivity.RETURNING
    return {
        STATUS_IDLE: VacuumActivity.IDLE,
        STATUS_CLEANING: VacuumActivity.CLEANING,
        STATUS_PAUSED: VacuumActivity.PAUSED,
    }.get(status.status, VacuumActivity.IDLE)


class ChasingPoolVacuum(ChasingPoolEntity, StateVacuumEntity):
    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.STATE
    )
    _attr_name = None

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device_id

    @property
    def activity(self) -> VacuumActivity | None:
        if self.coordinator.data is None:
            return None
        return _activity(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        return {
            "cloud_online": self.coordinator.cloud_online,
            "mqtt_connected": self.coordinator.mqtt_connected,
            "wifi_name": self.coordinator.wifi_name,
            "sleeping": self.coordinator.sleeping,
        }

    async def async_start(self) -> None:
        await self.coordinator.async_publish_command({"status": STATUS_CLEANING})

    async def async_stop(self, **kwargs) -> None:
        await self.coordinator.async_publish_command({"status": STATUS_IDLE})

    async def async_pause(self) -> None:
        await self.coordinator.async_publish_command({"status": STATUS_PAUSED})

    async def async_return_to_base(self, **kwargs) -> None:
        await self.coordinator.async_publish_command({"mode": MODE_RETRIEVE})
