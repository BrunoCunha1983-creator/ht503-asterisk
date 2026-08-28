"""Diagnostics for the Asterisk integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, HT503_COORDINATOR


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return safe diagnostics without passwords."""
    runtime = hass.data[DOMAIN][config_entry.entry_id]
    options = dict(config_entry.options)
    if "ht503_password" in options:
        options["ht503_password"] = "REDACTED"

    coordinator = runtime.get(HT503_COORDINATOR)
    ht503 = None
    if coordinator is not None:
        ht503 = {
            "last_update_success": coordinator.last_update_success,
            "ports": {
                port: {
                    "state": data.state,
                    "user_id": data.user_id,
                    "registration": data.registration,
                }
                for port, data in (coordinator.data or {}).items()
            },
        }

    return {
        "connection": {
            "host": config_entry.data.get(CONF_HOST),
            "port": config_entry.data.get(CONF_PORT),
            "username": config_entry.data.get(CONF_USERNAME),
        },
        "options": options,
        "devices": runtime.get(CONF_DEVICES, []),
        "ht503": ht503,
    }
