"""Shared entity base for CHASING Pool Robot."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChasingPoolCoordinator


class ChasingPoolEntity(CoordinatorEntity[ChasingPoolCoordinator]):
    """Base entity with shared device info and availability."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        return self.coordinator.robot_available

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            name=self.coordinator.device_name or "CHASING Pool Robot",
            manufacturer="CHASING",
            model="HYDRO4",
            sw_version=data.fw_version if data else None,
        )
