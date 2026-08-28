"""Asterisk integration setup."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientSession, CookieJar
from asterisk.ami import AMIClient, AutoReconnect, SimpleAction
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)

from .ami import (
    AMIAuthenticationError,
    AMIConnectionError,
    AMIEndpoint,
    AMIServerInfo,
    connect_ami,
    discover_endpoints,
)
from .const import (
    AUTO_RECONNECT,
    CLIENT,
    CONF_DISCOVER_PJSIP,
    CONF_DISCOVER_SIP,
    CONF_ENABLE_HT503,
    CONF_EXTENSION_FILTER,
    CONF_EXTRA_ENDPOINTS,
    CONF_HT503_HOST,
    CONF_HT503_PASSWORD,
    CONF_HT503_POLL_INTERVAL,
    CONF_HT503_PORT,
    CONF_SELECTED_ENDPOINTS,
    DEFAULT_DISCOVER_PJSIP,
    DEFAULT_DISCOVER_SIP,
    DEFAULT_ENABLE_HT503,
    DEFAULT_EXTENSION_FILTER,
    DEFAULT_EXTRA_ENDPOINTS,
    DEFAULT_HT503_POLL_INTERVAL,
    DEFAULT_HT503_PORT,
    DEFAULT_SELECTED_ENDPOINTS,
    DOMAIN,
    HT503_COORDINATOR,
    HT503_SESSION,
    PLATFORMS,
    SERVER_INFO,
)
from .ht503 import HT503Client, HT503Coordinator

_LOGGER = logging.getLogger(__name__)

SEND_ACTION_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
        vol.Required("action"): str,
        vol.Optional("parameters", default={}): dict,
    }
)


def _send_action_blocking(client: AMIClient, action_name: str, parameters: dict[str, Any]):
    """Send an AMI action and wait for its direct response off the event loop."""
    action = SimpleAction(action_name, **parameters)
    future = client.send_action(action)
    return future.response


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration-wide actions."""
    hass.data.setdefault(DOMAIN, {})

    async def send_action_service(call: ServiceCall) -> ServiceResponse:
        action_name = str(call.data["action"]).strip()
        parameters = dict(call.data.get("parameters") or {})
        requested_entry = call.data.get("entry_id")

        if not action_name:
            raise ServiceValidationError("AMI action name is required")

        candidates = [
            (entry_id, data)
            for entry_id, data in hass.data.get(DOMAIN, {}).items()
            if isinstance(data, dict) and CLIENT in data
        ]
        if requested_entry:
            candidates = [item for item in candidates if item[0] == requested_entry]
        if not candidates:
            raise ServiceValidationError("No loaded Asterisk config entry is available")

        entry_id, selected = candidates[0]
        try:
            response = await hass.async_add_executor_job(
                _send_action_blocking, selected[CLIENT], action_name, parameters
            )
        except Exception as err:
            raise ServiceValidationError(f"AMI action failed: {err}") from err

        if response is None:
            raise ServiceValidationError("Asterisk did not return an AMI response")

        result: ServiceResponse = {
            "entry_id": entry_id,
            "action": action_name,
            "status": getattr(response, "status", None),
            "success": not response.is_error(),
            "response": dict(getattr(response, "keys", {}) or {}),
        }
        follows = getattr(response, "follows", None)
        if follows:
            result["follows"] = list(follows)
        return result

    hass.services.async_register(
        DOMAIN,
        "send_action",
        send_action_service,
        schema=SEND_ACTION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


def _option(entry: ConfigEntry, key: str, default: Any) -> Any:
    return entry.options.get(key, default)


def _tokens(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _configured_endpoint_filters(entry: ConfigEntry) -> tuple[set[str], set[str]]:
    """Return explicit full endpoint filters and extension-only filters."""
    full: set[str] = set()
    extension_only: set[str] = set()

    selected = entry.options.get(CONF_SELECTED_ENDPOINTS)
    extra = str(_option(entry, CONF_EXTRA_ENDPOINTS, DEFAULT_EXTRA_ENDPOINTS))

    if selected is not None or CONF_EXTRA_ENDPOINTS in entry.options:
        for value in list(selected or []) + _tokens(extra):
            cleaned = str(value).strip()
            if not cleaned:
                continue
            if "/" in cleaned:
                tech, extension = cleaned.split("/", 1)
                full.add(f"{tech.strip().upper()}/{extension.strip()}".casefold())
            else:
                extension_only.add(cleaned.casefold())
        return full, extension_only

    legacy = str(_option(entry, CONF_EXTENSION_FILTER, DEFAULT_EXTENSION_FILTER)).strip()
    if not legacy or legacy == "*":
        return full, extension_only
    for value in _tokens(legacy):
        if "/" in value:
            tech, extension = value.split("/", 1)
            full.add(f"{tech.strip().upper()}/{extension.strip()}".casefold())
        else:
            extension_only.add(value.casefold())
    return full, extension_only


def _endpoint_allowed(entry: ConfigEntry, tech: str, extension: str) -> bool:
    full_filters, extension_filters = _configured_endpoint_filters(entry)
    if not full_filters and not extension_filters:
        return True
    return (
        f"{tech.upper()}/{extension}".casefold() in full_filters
        or extension.casefold() in extension_filters
    )


def _normalize_initial_status(value: str | None) -> str:
    if not value:
        return "Unknown"
    cleaned = value.strip()
    upper = cleaned.upper().replace(" ", "_")
    mapping = {
        "NOT_INUSE": "Not in use",
        "INUSE": "In use",
        "BUSY": "Busy",
        "UNAVAILABLE": "Unavailable",
        "RINGING": "Ringing",
        "RINGINUSE": "Ringing in use",
        "ONHOLD": "On hold",
        "UNKNOWN": "Unknown",
    }
    if upper in mapping:
        return mapping[upper]
    if cleaned.lower().startswith("ok"):
        return "Not in use"
    if "unavailable" in cleaned.lower() or "unreachable" in cleaned.lower():
        return "Unavailable"
    return cleaned


def _device_from_endpoint(endpoint: AMIEndpoint) -> dict[str, Any]:
    return {
        "extension": endpoint.extension,
        "tech": endpoint.tech,
        "status": _normalize_initial_status(endpoint.status),
    }


def _manual_endpoint(value: str) -> tuple[str, str] | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if "/" in cleaned:
        tech, extension = cleaned.split("/", 1)
        tech = tech.strip().upper()
        extension = extension.strip()
        if tech not in {"PJSIP", "SIP"} or not extension:
            return None
        return tech, extension
    return "PJSIP", cleaned


def _ensure_saved_endpoints(
    entry: ConfigEntry, devices_by_key: dict[tuple[str, str], dict[str, Any]]
) -> None:
    """Keep selected/manual endpoints even if they are temporarily absent."""
    discover_pjsip = bool(_option(entry, CONF_DISCOVER_PJSIP, DEFAULT_DISCOVER_PJSIP))
    discover_sip = bool(_option(entry, CONF_DISCOVER_SIP, DEFAULT_DISCOVER_SIP))

    selected = entry.options.get(CONF_SELECTED_ENDPOINTS, DEFAULT_SELECTED_ENDPOINTS)
    for value in selected:
        parsed = _manual_endpoint(str(value))
        if parsed is None:
            continue
        tech, extension = parsed
        if tech == "PJSIP" and not discover_pjsip:
            continue
        if tech == "SIP" and not discover_sip:
            continue
        key = (tech, extension)
        if key not in devices_by_key and _endpoint_allowed(entry, tech, extension):
            devices_by_key[key] = {
                "extension": extension,
                "tech": tech,
                "status": "Unknown",
            }

    for value in _tokens(str(_option(entry, CONF_EXTRA_ENDPOINTS, DEFAULT_EXTRA_ENDPOINTS))):
        parsed = _manual_endpoint(value)
        if parsed is None:
            continue
        tech, extension = parsed
        key = (tech, extension)
        if key not in devices_by_key and _endpoint_allowed(entry, tech, extension):
            devices_by_key[key] = {
                "extension": extension,
                "tech": tech,
                "status": "Unknown",
            }


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate entries created by earlier/original integration versions."""
    if entry.version > 2:
        return False
    if entry.version < 2:
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Asterisk config entry."""
    try:
        client, auto_reconnect, server_info = await hass.async_add_executor_job(
            connect_ami, dict(entry.data)
        )
    except AMIAuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except (AMIConnectionError, OSError, TimeoutError) as err:
        raise ConfigEntryNotReady(str(err)) from err
    except Exception as err:
        raise ConfigEntryNotReady(str(err)) from err

    root = hass.data.setdefault(DOMAIN, {})
    entry_data: dict[str, Any] = {
        CLIENT: client,
        AUTO_RECONNECT: auto_reconnect,
        SERVER_INFO: server_info,
        CONF_DEVICES: [],
        HT503_COORDINATOR: None,
        HT503_SESSION: None,
    }
    root[entry.entry_id] = entry_data

    discover_sip = bool(_option(entry, CONF_DISCOVER_SIP, DEFAULT_DISCOVER_SIP))
    discover_pjsip = bool(_option(entry, CONF_DISCOVER_PJSIP, DEFAULT_DISCOVER_PJSIP))

    devices_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        endpoints = await hass.async_add_executor_job(
            discover_endpoints,
            client,
            discover_sip,
            discover_pjsip,
            8,
        )
        for endpoint in endpoints:
            if _endpoint_allowed(entry, endpoint.tech, endpoint.extension):
                devices_by_key[(endpoint.tech, endpoint.extension)] = _device_from_endpoint(
                    endpoint
                )
    except Exception as err:
        _LOGGER.warning("Asterisk endpoint discovery failed: %s", err)

    _ensure_saved_endpoints(entry, devices_by_key)
    entry_data[CONF_DEVICES] = list(devices_by_key.values())

    if bool(_option(entry, CONF_ENABLE_HT503, DEFAULT_ENABLE_HT503)):
        host = str(_option(entry, CONF_HT503_HOST, "")).strip()
        if host:
            session = ClientSession(cookie_jar=CookieJar(unsafe=True))
            ht503_client = HT503Client(
                session,
                host,
                int(_option(entry, CONF_HT503_PORT, DEFAULT_HT503_PORT)),
                str(_option(entry, CONF_HT503_PASSWORD, "")),
            )
            coordinator = HT503Coordinator(
                hass,
                ht503_client,
                timedelta(
                    seconds=int(
                        _option(
                            entry,
                            CONF_HT503_POLL_INTERVAL,
                            DEFAULT_HT503_POLL_INTERVAL,
                        )
                    )
                ),
            )
            entry_data[HT503_SESSION] = session
            entry_data[HT503_COORDINATOR] = coordinator
            try:
                await coordinator.async_refresh()
            except Exception as err:
                _LOGGER.warning("HT503 initial refresh failed: %s", err)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Asterisk config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    session: ClientSession | None = data.get(HT503_SESSION)
    if session is not None and not session.closed:
        await session.close()

    client: AMIClient = data[CLIENT]
    try:
        await hass.async_add_executor_job(client.logoff)
    except Exception:
        pass
    try:
        await hass.async_add_executor_job(client.disconnect)
    except Exception:
        pass

    hass.data[DOMAIN].pop(entry.entry_id, None)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an Asterisk config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
