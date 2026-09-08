from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
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
            ChasingWaterTemperatureSensor(coordinator),
            ChasingTaskRemainingSensor(coordinator),
            ChasingFirmwareVersionSensor(coordinator),
            ChasingWifiNameSensor(coordinator),
        ]
    )


class ChasingWaterTemperatureSensor(ChasingPoolEntity, SensorEntity):
    _attr_name = "Water Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_water_temperature"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        # Raw value observed in the 2500-3300 range; /100 as Celsius lines up
        # with plausible pool temps (25-33C).
        return self.coordinator.data.water_temperature / 100


class ChasingTaskRemainingSensor(ChasingPoolEntity, SensorEntity):
    _attr_name = "Task Time Remaining"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_task_remain"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.task_remain


class ChasingFirmwareVersionSensor(ChasingPoolEntity, SensorEntity):
    _attr_name = "Firmware Version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_fw_version"

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.fw_version


class ChasingWifiNameSensor(ChasingPoolEntity, SensorEntity):
    _attr_name = "Wi-Fi Network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ChasingPoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_wifi_name"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str | None:
        return self.coordinator.wifi_name
