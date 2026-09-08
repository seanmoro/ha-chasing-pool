from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ChasingApiError, ChasingAuthError, ChasingRestClient
from .const import (
    CONF_DEVICE_ID,
    CONF_EMAIL,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_USERNAME,
    CONF_TOKEN,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _device_label(device: dict) -> str:
    name = device.get("clientName") or "CHASING Pool Robot"
    device_id = device.get("clientId") or "?"
    return f"{name} ({device_id})"


async def _async_login_and_devices(
    hass: HomeAssistant, email: str, password: str
) -> tuple[dict[str, str], list[dict]]:
    session = async_get_clientsession(hass)
    client = ChasingRestClient(session)
    creds = await client.async_login(email.strip(), password)
    devices = await client.async_list_devices()
    return (
        {
            CONF_EMAIL: email.strip(),
            # Stored so the integration can refresh MQTT creds after the app
            # steals the session — without forcing a manual reconfigure.
            CONF_PASSWORD: password,
            CONF_TOKEN: creds.token,
            CONF_MQTT_USERNAME: creds.mqtt_username,
            CONF_MQTT_PASSWORD: creds.mqtt_password,
        },
        devices,
    )


class ChasingPoolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._login_data: dict[str, str] = {}
        self._devices: list[dict] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data, devices = await _async_login_and_devices(
                    self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except ChasingAuthError:
                errors["base"] = "invalid_auth"
            except (ChasingApiError, aiohttp.ClientError, OSError):
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices_found"
                else:
                    self._login_data = data
                    self._devices = devices
                    if len(devices) == 1:
                        return await self._async_create_for_device(devices[0])
                    return await self.async_step_device()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        choices = {
            str(d["clientId"]): _device_label(d)
            for d in self._devices
            if d.get("clientId")
        }
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            device = next(
                (d for d in self._devices if str(d.get("clientId")) == device_id),
                None,
            )
            if device is None:
                errors["base"] = "no_devices_found"
            else:
                return await self._async_create_for_device(device)

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE_ID): vol.In(choices)}
            ),
            errors=errors,
        )

    async def _async_create_for_device(self, device: dict) -> FlowResult:
        device_id = str(device["clientId"])
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=device.get("clientName") or "CHASING Pool Robot",
            data={**self._login_data, CONF_DEVICE_ID: device_id},
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                data, devices = await _async_login_and_devices(
                    self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except ChasingAuthError:
                errors["base"] = "invalid_auth"
            except (ChasingApiError, aiohttp.ClientError, OSError):
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices_found"
                else:
                    current_id = entry.data.get(CONF_DEVICE_ID)
                    device = next(
                        (d for d in devices if d.get("clientId") == current_id),
                        devices[0],
                    )
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={
                            **data,
                            CONF_DEVICE_ID: device["clientId"],
                        },
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL, default=entry.data.get(CONF_EMAIL, "")
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return ChasingPoolOptionsFlow()


class ChasingPoolOptionsFlow(config_entries.OptionsFlow):
    """Re-login to refresh REST/MQTT credentials after the app takes the session."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self.config_entry
        if user_input is not None:
            try:
                data, devices = await _async_login_and_devices(
                    self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except ChasingAuthError:
                errors["base"] = "invalid_auth"
            except (ChasingApiError, aiohttp.ClientError, OSError):
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices_found"
                else:
                    current_id = entry.data.get(CONF_DEVICE_ID)
                    device = next(
                        (d for d in devices if d.get("clientId") == current_id),
                        devices[0],
                    )
                    new_data = {
                        **entry.data,
                        **data,
                        CONF_DEVICE_ID: device["clientId"],
                    }
                    self.hass.config_entries.async_update_entry(entry, data=new_data)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL, default=entry.data.get(CONF_EMAIL, "")
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
