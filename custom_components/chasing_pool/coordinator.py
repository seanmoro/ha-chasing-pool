"""Data update coordinator for CHASING Pool Robot."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ChasingApiError,
    ChasingAuthError,
    ChasingMqttClient,
    ChasingRestClient,
    DeviceStatus,
)
from .const import (
    CONF_DEVICE_ID,
    CONF_EMAIL,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_USERNAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    DOMAIN,
    PRESENCE_UPDATE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class ChasingPoolCoordinator(DataUpdateCoordinator[DeviceStatus | None]):
    """MQTT push for status + REST poll for true cloud online presence."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=PRESENCE_UPDATE_SECONDS),
        )
        self.entry = entry
        self.device_id: str = entry.data[CONF_DEVICE_ID]
        self.client: ChasingMqttClient | None = None
        self.rest = ChasingRestClient(
            async_get_clientsession(hass), entry.data.get(CONF_TOKEN)
        )
        self.mqtt_connected = False
        self.cloud_online = False
        self.device_name: str | None = entry.title
        self.wifi_name: str | None = None
        self.sleeping: bool | None = None
        self._reauth_started = False

    @property
    def robot_available(self) -> bool:
        """True only when broker is up AND cloud says the robot is online."""
        return bool(self.mqtt_connected and self.cloud_online and self.data is not None)

    @callback
    def handle_status(self, status: DeviceStatus) -> None:
        """MQTT status callback (already marshaled onto the HA loop)."""
        # Retained MQTT can claim connected=True while REST onLine=0.
        # Keep the payload for when the robot returns, but don't pretend it's live.
        self.async_set_updated_data(status)

    @callback
    def handle_mqtt_connection(self, connected: bool) -> None:
        self.mqtt_connected = connected
        # Force entity availability refresh even if DeviceStatus unchanged.
        self.async_update_listeners()

    async def async_setup(self) -> None:
        await self.async_ensure_mqtt()
        await self.async_config_entry_first_refresh()

    async def async_ensure_mqtt(self) -> None:
        if self.client is not None:
            return

        def _create_and_connect() -> ChasingMqttClient:
            client = ChasingMqttClient(
                loop=self.hass.loop,
                device_id=self.device_id,
                mqtt_username=str(self.entry.data[CONF_MQTT_USERNAME]),
                mqtt_password=str(self.entry.data[CONF_MQTT_PASSWORD]),
                on_status=self.handle_status,
                on_connection_change=self.handle_mqtt_connection,
            )
            client.connect()
            return client

        self.client = await self.hass.async_add_executor_job(_create_and_connect)

    async def async_shutdown_mqtt(self) -> None:
        client = self.client
        self.client = None
        self.mqtt_connected = False
        if client is not None:
            await self.hass.async_add_executor_job(client.disconnect)

    async def async_reconnect_mqtt(self) -> None:
        await self.async_shutdown_mqtt()
        await self.async_ensure_mqtt()

    async def _async_refresh_credentials(self) -> bool:
        """Re-login using stored password. Returns True if creds updated."""
        email = self.entry.data.get(CONF_EMAIL)
        password = self.entry.data.get(CONF_PASSWORD)
        if not email or not password:
            return False

        _LOGGER.info("CHASING token expired; refreshing login for %s", email)
        creds = await self.rest.async_login(email, password)
        new_data = {
            **self.entry.data,
            CONF_TOKEN: creds.token,
            CONF_MQTT_USERNAME: creds.mqtt_username,
            CONF_MQTT_PASSWORD: creds.mqtt_password,
        }
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        self.rest.set_token(creds.token)
        await self.async_reconnect_mqtt()
        self._reauth_started = False
        return True

    async def _async_handle_auth_failure(self, err: Exception) -> None:
        if await self._async_refresh_credentials():
            return
        if not self._reauth_started:
            self._reauth_started = True
            self.entry.async_start_reauth(self.hass)
        raise ConfigEntryAuthFailed(str(err)) from err

    async def _async_update_data(self) -> DeviceStatus | None:
        try:
            await self.rest.async_check_token()
            presence = await self.rest.async_get_presence(self.device_id)
        except ChasingAuthError as err:
            await self._async_handle_auth_failure(err)
            # If refresh succeeded, retry once.
            await self.rest.async_check_token()
            presence = await self.rest.async_get_presence(self.device_id)
        except ChasingApiError as err:
            raise UpdateFailed(str(err)) from err

        self.cloud_online = presence.online
        if presence.device_name:
            self.device_name = presence.device_name
        self.wifi_name = presence.wifi_name
        self.sleeping = presence.sleeping

        if self.cloud_online and self.client is not None and self.client.is_connected:
            await self.hass.async_add_executor_job(self.client.request_status)

        if not self.cloud_online:
            _LOGGER.debug(
                "CHASING device %s cloud offline (wifi=%s)",
                self.device_id,
                self.wifi_name,
            )

        # Keep last MQTT status payload (may be retained/stale when offline).
        return self.data

    async def async_publish_command(self, data: dict[str, Any]) -> None:
        if not self.robot_available or self.client is None:
            raise HomeAssistantError(
                "Pool robot is offline from CHASING cloud. "
                "Wake it / reconnect Wi-Fi, then try again."
            )
        try:
            await self.hass.async_add_executor_job(self.client.publish_command, data)
        except ChasingApiError as err:
            raise HomeAssistantError(str(err)) from err
