# CHASING Pool Robot (Home Assistant)

Unofficial Home Assistant integration for **CHASING Hydro4** pool robots (PoolMate / CHASING GO3 cloud account).

> Not affiliated with CHASING. The cloud protocol is reverse-engineered and may break if CHASING changes their API.

## Features

- Vacuum entity: start / pause / stop / retrieve
- Cleaning program, zone, pool shape, and light-strip selects
- Cleaning duration number entity
- Water temperature, task time remaining, firmware, Wi-Fi name
- **Cloud Online** diagnostic binary sensor (REST presence — not stale MQTT)
- Automatic session refresh when the mobile app steals the login
- Multi-device picker when the account has more than one robot

## Requirements

- Home Assistant 2024.6+
- Robot already set up in the CHASING / PoolMate app (Wi-Fi + cloud account)
- Outbound access to:
  - `https://na-mqtt-api.chasing.com` (HTTPS)
  - `mqtt-na.chasing.com:8883` (MQTT over TLS)
- DNS for those hosts must resolve to CHASING / AWS — do **not** rewrite them to a local machine (common leftover from MQTT debugging)

**Region note:** this release uses **North America** cloud endpoints only.

## Install (HACS custom repository)

1. HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/seanmoro/ha-chasing-pool` as category **Integration**
3. Search for **CHASING Pool Robot** and install
4. Restart Home Assistant
5. Settings → Devices & services → Add integration → **CHASING Pool Robot**
6. Sign in with your CHASING / PoolMate email and password

## Install (manual)

1. Copy `custom_components/chasing_pool` into your HA `config/custom_components/` folder
2. Restart Home Assistant
3. Add the integration as above

## Important behavior

- CHASING allows **one cloud session** per account. Logging in from HA may sign the phone app out (and vice versa). Prefer leaving the app closed while HA controls the robot.
- The account password is stored in the HA config entry so the integration can refresh MQTT credentials automatically.
- Entities are only fully available when the robot is **cloud online** (MQTT connected **and** REST `onLine`). Wi-Fi association alone is not enough.
- Local cleaning from the app / BLE can still work while cloud is offline; HA will not see or control that session.

## Entities

| Entity | Purpose |
|--------|---------|
| Vacuum | Start / pause / stop / retrieve |
| Cleaning Program | Regular / Floor / Wall / Custom modes |
| Cleaning Zone | Floor / wall / water-line bitmask |
| Pool Shape | Rectangle / Round / Other |
| Cleaning Duration | Minutes (especially for Custom) |
| Cloud Online | True cloud presence |
| Out of Water | Problem binary sensor |

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Entities `unavailable` | Cloud Online off? Robot Wi-Fi? Power box online? |
| MQTT queries rewritten in AdGuard | Remove DNS rewrite for `mqtt-na.chasing.com` |
| Login works then dies after opening the app | Expected single-session behavior — reauth or use Configure → refresh login |
| EU / other region | Not supported yet (NA hosts hardcoded) |

## Disclaimer

Use at your own risk. This project is unofficial and may stop working without notice.

## License

MIT
