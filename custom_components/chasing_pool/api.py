"""Client for the CHASING Hydro-Cloud protocol.

Reverse-engineered from the PoolMate Bot / CHASING GO3 app (undocumented,
no public API). Account login returns an AES-encrypted blob that yields the
REST token plus MQTT username/password; live status travels over MQTT.
REST /clients exposes onLine — required because MQTT often returns a retained
stale host/report while the robot is actually offline.
"""
from __future__ import annotations

from dataclasses import dataclass
import asyncio
import base64
import json
import logging
import ssl
import time
import uuid
from collections.abc import Callable

import aiohttp
import paho.mqtt.client as mqtt
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import MQTT_HOST, MQTT_PORT, MODE_RETRIEVE, REST_BASE_URL, TOPIC_PREFIX

_LOGGER = logging.getLogger(__name__)

# Hardcoded in com.chasing.poolrobot.utils.AESEncryption (CHASING GO3).
_AES_KEY = b"RpbWUiOjE2OTI3MR"
_AES_IV = b"a55384cbb8318e6a"


def decrypt_chasing_blob(ciphertext_b64: str) -> str:
    """Decrypt app AES/CBC/PKCS5 payloads (login token, appHost, etc.)."""
    raw = base64.b64decode(ciphertext_b64)
    decryptor = Cipher(algorithms.AES(_AES_KEY), modes.CBC(_AES_IV)).decryptor()
    padded = decryptor.update(raw) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")


def _connect_ok(rc) -> bool:
    """paho-mqtt v2 passes ReasonCode; v1 passed int."""
    if rc == 0:
        return True
    value = getattr(rc, "value", None)
    if value == 0:
        return True
    return str(rc) in {"Success", "0"}


def _clean_wifi_name(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.split("\x00", 1)[0].strip()
    return cleaned or None


class ChasingApiError(Exception):
    pass


class ChasingAuthError(ChasingApiError):
    pass


@dataclass
class ChasingCredentials:
    token: str
    mqtt_username: str
    mqtt_password: str


@dataclass
class DevicePresence:
    """Cloud presence from REST /clients (not MQTT retained status)."""

    online: bool
    device_name: str | None
    wifi_name: str | None
    sleeping: bool | None


@dataclass
class DeviceStatus:
    connected: bool
    status: int
    mode: int
    shape: int
    zone: int
    minutes: int
    task_duration: int
    task_remain: int
    out_of_water: bool
    water_temperature: int
    fw_version: str
    light_strip: int

    @classmethod
    def from_payload(cls, data: dict) -> "DeviceStatus":
        return cls(
            connected=bool(data.get("connected", False)),
            status=data.get("status", 0),
            mode=data.get("mode", 0),
            shape=data.get("shape", 0),
            zone=data.get("zone", 0),
            minutes=data.get("minutes", 0),
            task_duration=data.get("taskDuration", 0),
            task_remain=data.get("taskRemain", 0),
            out_of_water=bool(data.get("outOfWater", False)),
            water_temperature=data.get("waterTemprature", 0),
            fw_version=data.get("fwVer", ""),
            light_strip=int(data.get("lightStrip", 0) or 0),
        )

    @property
    def is_returning(self) -> bool:
        return self.mode == MODE_RETRIEVE and self.status == 1


class ChasingRestClient:
    """REST helpers for login, token check, and device discovery."""

    def __init__(self, session: aiohttp.ClientSession, token: str | None = None) -> None:
        self._session = session
        self._token = token

    @property
    def token(self) -> str | None:
        return self._token

    def set_token(self, token: str) -> None:
        self._token = token

    @property
    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise ChasingAuthError("No token configured")
        return {"Authorization": self._token, "Accept": "*/*"}

    async def async_login(self, account: str, password: str) -> ChasingCredentials:
        """Log in with CHASING account email/password and decrypt MQTT creds.

        Note: logging in can invalidate other app sessions on the same account.
        """
        payload = {"account": account, "password": password}
        async with self._session.post(
            f"{REST_BASE_URL}/v1/login",
            json=payload,
            headers={"Accept": "*/*", "Content-Type": "application/json"},
        ) as resp:
            if resp.status != 200:
                raise ChasingAuthError(f"login returned HTTP {resp.status}")
            body = await resp.json()

        if body.get("code") != 0:
            raise ChasingAuthError(body.get("msg", "login failed"))

        data = body.get("data") or {}
        encrypted = data.get("token")
        if not encrypted:
            raise ChasingAuthError("login response missing encrypted token")

        try:
            decoded = json.loads(decrypt_chasing_blob(encrypted))
        except Exception as err:  # noqa: BLE001
            raise ChasingAuthError(f"failed to decrypt login token: {err}") from err

        token = decoded.get("token")
        username = decoded.get("username")
        mqtt_password = decoded.get("password")
        if not token or username is None or not mqtt_password:
            raise ChasingAuthError("decrypted login token missing fields")

        self._token = str(token)
        return ChasingCredentials(
            token=str(token),
            mqtt_username=str(username),
            mqtt_password=str(mqtt_password),
        )

    async def async_check_token(self) -> None:
        async with self._session.get(
            f"{REST_BASE_URL}/v1/users/check-token", headers=self._headers
        ) as resp:
            if resp.status == 401:
                raise ChasingAuthError("check-token returned HTTP 401")
            if resp.status != 200:
                raise ChasingApiError(f"check-token returned HTTP {resp.status}")
            body = await resp.json()
            if body.get("code") != 0:
                raise ChasingAuthError(body.get("msg", "check-token failed"))

    async def async_list_devices(self) -> list[dict]:
        async with self._session.get(
            f"{REST_BASE_URL}/v1/users/clients?type=1", headers=self._headers
        ) as resp:
            if resp.status == 401:
                raise ChasingAuthError("clients returned HTTP 401")
            if resp.status != 200:
                raise ChasingApiError(f"clients returned HTTP {resp.status}")
            body = await resp.json()
            if body.get("code") != 0:
                # Auth-ish failures often come as code != 0 with HTTP 200.
                msg = str(body.get("msg", "clients failed"))
                if "token" in msg.lower() or "auth" in msg.lower() or "login" in msg.lower():
                    raise ChasingAuthError(msg)
                raise ChasingApiError(msg)
            return body.get("data", [])

    async def async_get_presence(self, device_id: str) -> DevicePresence:
        devices = await self.async_list_devices()
        match = next((d for d in devices if d.get("clientId") == device_id), None)
        if match is None:
            return DevicePresence(
                online=False, device_name=None, wifi_name=None, sleeping=None
            )

        sleep_raw = match.get("sleep")
        sleeping: bool | None
        if sleep_raw in (None, "undefined", ""):
            sleeping = None
        else:
            sleeping = bool(sleep_raw) and str(sleep_raw).lower() not in {"0", "false"}

        return DevicePresence(
            online=bool(match.get("onLine")),
            device_name=match.get("clientName"),
            wifi_name=_clean_wifi_name(match.get("wifiName")),
            sleeping=sleeping,
        )


class ChasingMqttClient:
    """Wraps paho-mqtt for one robot's Hydro4/<device_id> topics.

    Broker ACL only allows the exact host/report subscribe (wildcards denied).
    paho runs its own network thread; callbacks marshal onto the HA loop.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        device_id: str,
        mqtt_username: str,
        mqtt_password: str,
        on_status: Callable[[DeviceStatus], None],
        on_connection_change: Callable[[bool], None] | None = None,
    ) -> None:
        self._loop = loop
        self._device_id = device_id
        self._on_status = on_status
        self._on_connection_change = on_connection_change
        self._connected = False

        self._client = mqtt.Client(
            client_id=f"ha-chasing-{device_id[-8:]}-{uuid.uuid4().hex[:8]}",
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._client.username_pw_set(mqtt_username, mqtt_password)
        self._client.tls_set(cert_reqs=ssl.CERT_NONE)
        self._client.tls_insecure_set(True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=120)
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message

    @property
    def is_connected(self) -> bool:
        return self._connected and bool(self._client.is_connected())

    @property
    def _topic_host_report(self) -> str:
        return f"{TOPIC_PREFIX}/{self._device_id}/property/host/report"

    @property
    def _topic_set(self) -> str:
        return f"{TOPIC_PREFIX}/{self._device_id}/property/set"

    @property
    def _topic_get(self) -> str:
        return f"{TOPIC_PREFIX}/{self._device_id}/property/get"

    def _notify_connection(self, connected: bool) -> None:
        self._connected = connected
        if self._on_connection_change is None:
            return
        self._loop.call_soon_threadsafe(self._on_connection_change, connected)

    def _handle_connect(self, client, userdata, flags, rc, properties=None) -> None:
        if not _connect_ok(rc):
            _LOGGER.error("CHASING MQTT connect failed, rc=%s", rc)
            self._notify_connection(False)
            return

        # Exact topic only — Hydro4/<id>/# is ACL-denied.
        client.subscribe(self._topic_host_report, qos=1)
        _LOGGER.info("CHASING MQTT connected; subscribed to %s", self._topic_host_report)
        self._notify_connection(True)
        self.request_status()

    def _handle_disconnect(self, client, userdata, flags, rc, properties=None) -> None:
        _LOGGER.warning("CHASING MQTT disconnected, rc=%s", rc)
        self._notify_connection(False)

    def _handle_message(self, client, userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except ValueError:
            _LOGGER.warning("CHASING MQTT non-JSON on %s", msg.topic)
            return

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or "status" not in data:
            return
        self._loop.call_soon_threadsafe(self._on_status, DeviceStatus.from_payload(data))

    def connect(self) -> None:
        """Blocking; call via hass.async_add_executor_job."""
        self._client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self._client.loop_start()

    def disconnect(self) -> None:
        try:
            self._client.loop_stop()
            self._client.disconnect()
        finally:
            self._connected = False

    def update_credentials(self, mqtt_username: str, mqtt_password: str) -> None:
        """Update broker auth (caller should disconnect/reconnect around this)."""
        self._client.username_pw_set(mqtt_username, mqtt_password)

    def request_status(self) -> None:
        """Ask the cloud/device for a fresh host/report."""
        get_payload = {
            "msgId": f"{self._device_id}{int(time.time())}",
            "time": int(time.time()),
            "data": {"status": True},
        }
        try:
            info = self._client.publish(self._topic_get, json.dumps(get_payload), qos=1)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                _LOGGER.warning("CHASING MQTT get publish rc=%s", info.rc)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("CHASING MQTT get publish failed")

    def publish_command(self, data: dict) -> None:
        if not self.is_connected:
            raise ChasingApiError("MQTT broker not connected")
        msg_id = f"{self._device_id}{int(time.time())}"
        payload = {"msgId": msg_id, "time": int(time.time()), "data": data}
        info = self._client.publish(self._topic_set, json.dumps(payload), qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ChasingApiError(f"MQTT publish failed, rc={info.rc}")
        # Nudge a status refresh so entities catch the new state quickly.
        self.request_status()
