DOMAIN = "chasing_pool"
PLATFORMS = ["vacuum", "select", "number", "sensor", "binary_sensor"]

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_DEVICE_ID = "device_id"

REST_BASE_URL = "https://na-mqtt-api.chasing.com"
MQTT_HOST = "mqtt-na.chasing.com"
MQTT_PORT = 8883
TOPIC_PREFIX = "Hydro4"

# REST presence / token health poll. MQTT remains push for live status.
PRESENCE_UPDATE_SECONDS = 60

STATUS_IDLE = 0
STATUS_CLEANING = 1
STATUS_PAUSED = 2
MODE_RETRIEVE = 6

# Cleaning program names as shown in the CHASING app, in mode-value order (0-5).
# Durations match the modesDuration preset list captured from the app
# ([120, 60, 180, 120, 120, 5] minutes) for the first five; "Custom" duration
# is user-adjustable via the minutes number entity instead of fixed.
CLEANING_MODES = {
    0: "Regular (2H)",
    1: "Regular (1H)",
    2: "Regular (3H)",
    3: "Floor (2H)",
    4: "Wall (2H)",
    5: "Custom (4H)",
}

# Pool shape as reported/sent on the wire (app UI uses 3 for "Other", remapped to 2).
POOL_SHAPES = {
    0: "Rectangle",
    1: "Round",
    2: "Other",
}

# Zone is a bitmask: Floor=1, Wall=2, Water line=4.
CLEANING_ZONES = {
    1: "Floor",
    2: "Wall",
    4: "Water line",
    3: "Floor + Wall",
    5: "Floor + Water line",
    6: "Wall + Water line",
    7: "Floor + Wall + Water line",
}

LIGHT_STRIP_MODES = {
    0: "Default",
    1: "Dynamic",
    2: "Lighting",
}
