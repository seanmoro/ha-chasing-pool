from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ChasingPoolCoordinator
from .entity import ChasingPoolEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ChasingPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ChasingOutOfWaterBinarySensor(coordinator),
            ChasingFilterFullBinarySensor(coordinator),
            ChasingCloudOnlineBinarySensor(coordinator),
        ]
    )


class ChasingOutOfWaterBinarySensor(ChasingPoolEntity, BinarySensorEntity):
    _attr_name = "Out of Water"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_out_of_water"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.out_of_water


class ChasingFilterFullBinarySensor(ChasingPoolEntity, BinarySensorEntity):
    """True when CHASING reports error 0x42033C (filter basket fully loaded)."""

    _attr_name = "Filter Full"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_filter_full"

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.robot_available:
            return None
        return self.coordinator.filter_full

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        fault = self.coordinator.data.fault_alarm if self.coordinator.data else -1
        return {
            "fault_alarm": fault,
            "fault_alarm_hex": hex(fault) if fault >= 0 else None,
            "error_codes": [hex(code) for code in self.coordinator.error_codes],
            "errors": self.coordinator.error_details,
        }


class ChasingCloudOnlineBinarySensor(ChasingPoolEntity, BinarySensorEntity):
    """True when CHASING REST reports the robot online (not MQTT retained)."""

    _attr_name = "Cloud Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_cloud_online"

    @property
    def available(self) -> bool:
        # Show online/offline even when the robot itself is unreachable.
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        return self.coordinator.cloud_online

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        return {
            "mqtt_connected": self.coordinator.mqtt_connected,
            "wifi_name": self.coordinator.wifi_name,
            "sleeping": self.coordinator.sleeping,
        }
