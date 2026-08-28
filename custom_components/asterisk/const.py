"""Constants for the Asterisk integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "asterisk"

CLIENT = "client"
AUTO_RECONNECT = "auto_reconnect"
SERVER_INFO = "server_info"
HT503_COORDINATOR = "ht503_coordinator"
HT503_SESSION = "ht503_session"

PLATFORMS = ["binary_sensor", "sensor"]

CONF_DISCOVER_SIP = "discover_sip"
CONF_DISCOVER_PJSIP = "discover_pjsip"
CONF_SELECTED_ENDPOINTS = "selected_endpoints"
CONF_EXTRA_ENDPOINTS = "extra_endpoints"
# Legacy beta/original compatibility key. New UI uses selected_endpoints/extra_endpoints.
CONF_EXTENSION_FILTER = "extension_filter"
CONF_ENABLE_DEVICE_STATE = "enable_device_state"
CONF_ENABLE_REGISTERED = "enable_registered"
CONF_ENABLE_CONNECTED_LINE = "enable_connected_line"
CONF_ENABLE_DTMF = "enable_dtmf"

CONF_ENABLE_HT503 = "enable_ht503"
CONF_HT503_HOST = "ht503_host"
CONF_HT503_PORT = "ht503_port"
CONF_HT503_PASSWORD = "ht503_password"
CONF_HT503_POLL_INTERVAL = "ht503_poll_interval"

DEFAULT_DISCOVER_SIP = True
DEFAULT_DISCOVER_PJSIP = True
DEFAULT_SELECTED_ENDPOINTS: list[str] = []
DEFAULT_EXTRA_ENDPOINTS = ""
DEFAULT_EXTENSION_FILTER = "*"
DEFAULT_ENABLE_DEVICE_STATE = True
DEFAULT_ENABLE_REGISTERED = True
DEFAULT_ENABLE_CONNECTED_LINE = True
DEFAULT_ENABLE_DTMF = True

DEFAULT_ENABLE_HT503 = False
DEFAULT_HT503_PORT = 80
DEFAULT_HT503_POLL_INTERVAL = 30
MIN_HT503_POLL_INTERVAL = 10
MAX_HT503_POLL_INTERVAL = 3600
DEFAULT_HT503_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_HT503_POLL_INTERVAL)

STATES = {
    "NOT_INUSE": "Not in use",
    "INUSE": "In use",
    "BUSY": "Busy",
    "UNAVAILABLE": "Unavailable",
    "RINGING": "Ringing",
    "RINGINUSE": "Ringing in use",
    "ONHOLD": "On hold",
    "UNKNOWN": "Unknown",
}

STATE_ICONS = {
    "Not in use": "mdi:phone-hangup",
    "In use": "mdi:phone-in-talk",
    "Busy": "mdi:phone-in-talk",
    "Unavailable": "mdi:phone-off",
    "Ringing": "mdi:phone-ring",
    "Ringing in use": "mdi:phone-ring",
    "On hold": "mdi:phone-paused",
    "Unknown": "mdi:phone-off",
}
