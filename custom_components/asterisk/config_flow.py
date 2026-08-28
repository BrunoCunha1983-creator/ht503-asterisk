"""Config flow for the Asterisk integration."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientSession, CookieJar
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .ami import (
    AMIAuthenticationError,
    AMIConnectionError,
    AMIEndpoint,
    AMIProbeResult,
    probe_ami,
    unique_id_for,
)
from .const import (
    CONF_DISCOVER_PJSIP,
    CONF_DISCOVER_SIP,
    CONF_ENABLE_CONNECTED_LINE,
    CONF_ENABLE_DEVICE_STATE,
    CONF_ENABLE_DTMF,
    CONF_ENABLE_HT503,
    CONF_ENABLE_REGISTERED,
    CONF_EXTRA_ENDPOINTS,
    CONF_HT503_HOST,
    CONF_HT503_PASSWORD,
    CONF_HT503_POLL_INTERVAL,
    CONF_HT503_PORT,
    CONF_SELECTED_ENDPOINTS,
    DEFAULT_DISCOVER_PJSIP,
    DEFAULT_DISCOVER_SIP,
    DEFAULT_ENABLE_CONNECTED_LINE,
    DEFAULT_ENABLE_DEVICE_STATE,
    DEFAULT_ENABLE_DTMF,
    DEFAULT_ENABLE_HT503,
    DEFAULT_ENABLE_REGISTERED,
    DEFAULT_EXTRA_ENDPOINTS,
    DEFAULT_HT503_POLL_INTERVAL,
    DEFAULT_HT503_PORT,
    DEFAULT_SELECTED_ENDPOINTS,
    DOMAIN,
    MAX_HT503_POLL_INTERVAL,
    MIN_HT503_POLL_INTERVAL,
)
from .ht503 import async_test_ht503


def _connection_schema(values: dict[str, Any] | None = None) -> vol.Schema:
    values = values or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                description={"suggested_value": values.get(CONF_HOST)},
            ): TextSelector(),
            vol.Required(
                CONF_PORT,
                default=values.get(CONF_PORT, 5038),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_USERNAME,
                default=values.get(CONF_USERNAME, "admin"),
            ): TextSelector(TextSelectorConfig(autocomplete="username")),
            vol.Optional(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.PASSWORD,
                    autocomplete="current-password",
                )
            ),
        }
    )


def _endpoint_selector_options(
    endpoints: tuple[AMIEndpoint, ...], selected: list[str] | None = None
) -> list[SelectOptionDict]:
    choices = [
        SelectOptionDict(
            value=endpoint.value,
            label=f"{endpoint.value} — {endpoint.status}",
        )
        for endpoint in endpoints
    ]
    known = {choice["value"] for choice in choices}
    for value in selected or []:
        if value not in known:
            choices.append(SelectOptionDict(value=value, label=f"{value} — saved"))
    return choices


def _options_schema(
    endpoints: tuple[AMIEndpoint, ...] = (),
    values: dict[str, Any] | None = None,
) -> vol.Schema:
    """Return discovery/entity options shown before optional HT503 setup."""
    values = values or {}
    selected = list(values.get(CONF_SELECTED_ENDPOINTS, DEFAULT_SELECTED_ENDPOINTS))
    choices = _endpoint_selector_options(endpoints, selected)

    return vol.Schema(
        {
            vol.Optional(
                CONF_DISCOVER_PJSIP,
                default=values.get(CONF_DISCOVER_PJSIP, DEFAULT_DISCOVER_PJSIP),
            ): bool,
            vol.Optional(
                CONF_DISCOVER_SIP,
                default=values.get(CONF_DISCOVER_SIP, DEFAULT_DISCOVER_SIP),
            ): bool,
            vol.Optional(
                CONF_SELECTED_ENDPOINTS,
                description={"suggested_value": selected},
            ): SelectSelector(
                SelectSelectorConfig(options=choices, multiple=True)
            ),
            vol.Optional(
                CONF_EXTRA_ENDPOINTS,
                description={
                    "suggested_value": values.get(
                        CONF_EXTRA_ENDPOINTS, DEFAULT_EXTRA_ENDPOINTS
                    )
                },
            ): TextSelector(),
            vol.Optional(
                CONF_ENABLE_DEVICE_STATE,
                default=values.get(
                    CONF_ENABLE_DEVICE_STATE, DEFAULT_ENABLE_DEVICE_STATE
                ),
            ): bool,
            vol.Optional(
                CONF_ENABLE_REGISTERED,
                default=values.get(CONF_ENABLE_REGISTERED, DEFAULT_ENABLE_REGISTERED),
            ): bool,
            vol.Optional(
                CONF_ENABLE_CONNECTED_LINE,
                default=values.get(
                    CONF_ENABLE_CONNECTED_LINE, DEFAULT_ENABLE_CONNECTED_LINE
                ),
            ): bool,
            vol.Optional(
                CONF_ENABLE_DTMF,
                default=values.get(CONF_ENABLE_DTMF, DEFAULT_ENABLE_DTMF),
            ): bool,
            vol.Optional(
                CONF_ENABLE_HT503,
                default=values.get(CONF_ENABLE_HT503, DEFAULT_ENABLE_HT503),
            ): bool,
        }
    )


def _ht503_schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Return the HT503-only GUI step."""
    values = values or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HT503_HOST,
                description={"suggested_value": values.get(CONF_HT503_HOST, "")},
            ): TextSelector(),
            vol.Optional(
                CONF_HT503_PORT,
                default=values.get(CONF_HT503_PORT, DEFAULT_HT503_PORT),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_HT503_PASSWORD): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.PASSWORD,
                    autocomplete="current-password",
                )
            ),
            vol.Optional(
                CONF_HT503_POLL_INTERVAL,
                default=values.get(
                    CONF_HT503_POLL_INTERVAL, DEFAULT_HT503_POLL_INTERVAL
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_HT503_POLL_INTERVAL,
                    max=MAX_HT503_POLL_INTERVAL,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
        }
    )


def _normalize_connection_input(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    data[CONF_PORT] = int(data[CONF_PORT])
    data.setdefault(CONF_PASSWORD, "")
    return data


def _probe_ami_blocking(
    data: dict[str, Any], discover: bool = True
) -> tuple[str | None, AMIProbeResult | None]:
    """Validate AMI and optionally discover endpoints in an executor thread."""
    try:
        result = probe_ami(
            data,
            discover_sip=discover,
            discover_pjsip=discover,
            discovery_timeout=5,
        )
    except AMIAuthenticationError:
        return "invalid_auth", None
    except (AMIConnectionError, OSError, TimeoutError):
        return "cannot_connect", None
    except Exception:
        return "cannot_connect", None
    return None, result


async def _validate_ht503_options(options: dict[str, Any]) -> str | None:
    if not options.get(CONF_ENABLE_HT503, False):
        return None

    host = str(options.get(CONF_HT503_HOST, "")).strip()
    if not host:
        return "ht503_missing_host"

    session = ClientSession(cookie_jar=CookieJar(unsafe=True))
    try:
        await async_test_ht503(
            session,
            host,
            int(options.get(CONF_HT503_PORT, DEFAULT_HT503_PORT)),
            str(options.get(CONF_HT503_PASSWORD, "")),
        )
    except Exception:
        return "ht503_cannot_connect"
    finally:
        await session.close()

    return None


def _normalize_options(options: dict[str, Any]) -> dict[str, Any]:
    """Normalize values submitted by the currently visible GUI step."""
    normalized = dict(options)
    normalized.setdefault(CONF_SELECTED_ENDPOINTS, [])
    normalized.setdefault(CONF_EXTRA_ENDPOINTS, "")
    if CONF_HT503_PORT in normalized:
        normalized[CONF_HT503_PORT] = int(normalized[CONF_HT503_PORT])
    if CONF_HT503_POLL_INTERVAL in normalized:
        normalized[CONF_HT503_POLL_INTERVAL] = int(
            normalized[CONF_HT503_POLL_INTERVAL]
        )
    return normalized


class AsteriskConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Asterisk setup through the Home Assistant UI."""

    VERSION = 2

    def __init__(self) -> None:
        self._connection_data: dict[str, Any] = {}
        self._endpoints: tuple[AMIEndpoint, ...] = ()
        self._entry_title = "Asterisk"
        self._pending_options: dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Configure, validate and probe the AMI connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _normalize_connection_input(user_input)
            error, probe = await self.hass.async_add_executor_job(
                _probe_ami_blocking, data
            )
            if error is None and probe is not None:
                self._async_abort_entries_match(
                    {CONF_HOST: data[CONF_HOST], CONF_PORT: data[CONF_PORT]}
                )
                await self.async_set_unique_id(unique_id_for(data, probe.server))
                self._abort_if_unique_id_configured()
                self._connection_data = data
                self._endpoints = probe.endpoints
                self._entry_title = (
                    f"Asterisk {probe.server.system_name}"
                    if probe.server.system_name
                    else f"Asterisk {data[CONF_HOST]}"
                )
                return await self.async_step_features()
            errors["base"] = error or "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input),
            errors=errors,
        )

    async def async_step_features(self, user_input=None) -> ConfigFlowResult:
        """Configure endpoint selection, entities and optional HT503 support."""
        errors: dict[str, str] = {}

        if user_input is not None:
            options = _normalize_options(user_input)
            self._pending_options = options
            if options.get(CONF_ENABLE_HT503, False):
                return await self.async_step_ht503()
            return self.async_create_entry(
                title=self._entry_title,
                data=self._connection_data,
                options=options,
            )

        return self.async_show_form(
            step_id="features",
            data_schema=_options_schema(self._endpoints),
            errors=errors,
        )

    async def async_step_ht503(self, user_input=None) -> ConfigFlowResult:
        """Configure and validate the optional Grandstream HT503."""
        errors: dict[str, str] = {}

        if user_input is not None:
            options = _normalize_options({**self._pending_options, **user_input})
            error = await _validate_ht503_options(options)
            if error is None:
                return self.async_create_entry(
                    title=self._entry_title,
                    data=self._connection_data,
                    options=options,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="ht503",
            data_schema=_ht503_schema(self._pending_options),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        """Reauthenticate AMI credentials and verify the server identity when possible."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            updates = dict(user_input)
            if not str(updates.get(CONF_PASSWORD, "")).strip():
                updates[CONF_PASSWORD] = entry.data.get(CONF_PASSWORD, "")
            new_data = {**entry.data, **updates}
            error, probe = await self.hass.async_add_executor_job(
                _probe_ami_blocking, new_data, False
            )
            if error is None and probe is not None:
                current_unique = entry.unique_id or ""
                if current_unique.startswith("entity:") and probe.server.entity_id:
                    probed_unique = unique_id_for(new_data, probe.server)
                    if probed_unique != current_unique:
                        return self.async_abort(reason="unique_id_mismatch")
                return self.async_update_reload_and_abort(
                    entry, data_updates=updates
                )
            errors["base"] = error or "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=entry.data.get(CONF_USERNAME, "admin"),
                    ): TextSelector(TextSelectorConfig(autocomplete="username")),
                    vol.Optional(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        """Reconfigure AMI host, port and credentials."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            submitted = dict(user_input)
            if not str(submitted.get(CONF_PASSWORD, "")).strip():
                submitted[CONF_PASSWORD] = entry.data.get(CONF_PASSWORD, "")
            data = _normalize_connection_input(submitted)
            error, probe = await self.hass.async_add_executor_job(
                _probe_ami_blocking, data, False
            )
            if error is None and probe is not None:
                current_unique = entry.unique_id or ""
                candidate_unique = unique_id_for(data, probe.server)

                if (
                    current_unique.startswith("entity:")
                    and probe.server.entity_id
                    and candidate_unique != current_unique
                ):
                    return self.async_abort(reason="unique_id_mismatch")

                if current_unique.startswith("entity:") and not probe.server.entity_id:
                    candidate_unique = current_unique

                other = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, candidate_unique
                )
                if other is not None and other.entry_id != entry.entry_id:
                    errors["base"] = "already_configured"
                else:
                    title = (
                        f"Asterisk {probe.server.system_name}"
                        if probe.server.system_name
                        else f"Asterisk {data[CONF_HOST]}"
                    )
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=candidate_unique,
                        title=title,
                        data=data,
                    )
            else:
                errors["base"] = error or "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(entry.data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithReload:
        """Return the options flow."""
        return AsteriskOptionsFlow()


class AsteriskOptionsFlow(OptionsFlowWithReload):
    """Manage mutable Asterisk integration options."""

    def __init__(self) -> None:
        self._endpoints: tuple[AMIEndpoint, ...] | None = None
        self._pending_options: dict[str, Any] = {}

    async def _async_discover_for_form(self) -> tuple[AMIEndpoint, ...]:
        if self._endpoints is not None:
            return self._endpoints
        _error, probe = await self.hass.async_add_executor_job(
            _probe_ami_blocking, dict(self.config_entry.data)
        )
        self._endpoints = probe.endpoints if probe is not None else ()
        return self._endpoints

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Update discovery, endpoint selection, sensors and HT503 settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            options = _normalize_options(user_input)
            if options.get(CONF_ENABLE_HT503, False):
                self._pending_options = {**dict(self.config_entry.options), **options}
                return await self.async_step_ht503()

            for key in (
                CONF_HT503_HOST,
                CONF_HT503_PORT,
                CONF_HT503_PASSWORD,
                CONF_HT503_POLL_INTERVAL,
            ):
                if key in self.config_entry.options:
                    options[key] = self.config_entry.options[key]
            return self.async_create_entry(data=options)

        endpoints = await self._async_discover_for_form()
        schema = _options_schema(endpoints, dict(self.config_entry.options))
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_ht503(self, user_input=None) -> ConfigFlowResult:
        """Update and validate the optional HT503 settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            submitted = dict(user_input)
            if not str(submitted.get(CONF_HT503_PASSWORD, "")).strip():
                submitted[CONF_HT503_PASSWORD] = self._pending_options.get(
                    CONF_HT503_PASSWORD, ""
                )
            options = _normalize_options({**self._pending_options, **submitted})
            error = await _validate_ht503_options(options)
            if error is None:
                return self.async_create_entry(data=options)
            errors["base"] = error

        return self.async_show_form(
            step_id="ht503",
            data_schema=_ht503_schema(self._pending_options),
            errors=errors,
        )
