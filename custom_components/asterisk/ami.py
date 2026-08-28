"""Helpers for the Asterisk Manager Interface (AMI)."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any

from asterisk.ami import AMIClient, AutoReconnect, Event, SimpleAction


class AMIError(Exception):
    """Base AMI integration error."""


class AMIAuthenticationError(AMIError):
    """AMI authentication failed."""


class AMIConnectionError(AMIError):
    """AMI connection or response failed."""


@dataclass(slots=True, frozen=True)
class AMIEndpoint:
    """Discovered AMI endpoint."""

    tech: str
    extension: str
    status: str

    @property
    def value(self) -> str:
        """Return stable selector value."""
        return f"{self.tech}/{self.extension}"


@dataclass(slots=True, frozen=True)
class AMIServerInfo:
    """Small set of server metadata exposed by AMI."""

    version: str | None = None
    system_name: str | None = None
    entity_id: str | None = None


@dataclass(slots=True, frozen=True)
class AMIProbeResult:
    """Result of validating and probing an AMI server."""

    server: AMIServerInfo
    endpoints: tuple[AMIEndpoint, ...]


def _response(future):
    """Return an AMI response or raise a useful timeout error."""
    response = future.response
    if response is None:
        raise AMIConnectionError("Timed out waiting for an AMI response")
    return response


def _action_response(client: AMIClient, action: str, **parameters: Any):
    """Send one AMI action and wait for its direct response."""
    return _response(client.send_action(SimpleAction(action, **parameters)))


def _clean_global_value(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned.lower() in {"", "(null)", "null", "none", "unknown", "<unknown>"}:
        return None
    return cleaned


def read_server_info(client: AMIClient) -> AMIServerInfo:
    """Read non-sensitive server identity/version information.

    These actions are deliberately best-effort: a restricted manager account can
    still be used even if one of them is not permitted.
    """
    version = None
    system_name = None
    entity_id = None

    try:
        response = _action_response(client, "CoreSettings")
        if not response.is_error():
            version = _clean_global_value(response.keys.get("AsteriskVersion"))
            system_name = _clean_global_value(response.keys.get("SystemName"))
    except Exception:
        pass

    for variable, target in (("ENTITYID", "entity_id"), ("SYSTEMNAME", "system_name")):
        try:
            response = _action_response(client, "Getvar", Variable=variable)
            value = None if response.is_error() else _clean_global_value(response.keys.get("Value"))
        except Exception:
            value = None
        if target == "entity_id" and value:
            entity_id = value
        elif target == "system_name" and value:
            system_name = value

    return AMIServerInfo(
        version=version,
        system_name=system_name,
        entity_id=entity_id,
    )


def unique_id_for(data: dict[str, Any], server: AMIServerInfo) -> str:
    """Return the best available config-entry unique ID.

    Asterisk exposes a global ENTITYID which is designed to be unique between
    servers. If the manager account cannot read it, use the AMI endpoint as a
    compatibility fallback.
    """
    if server.entity_id:
        return f"entity:{server.entity_id.lower()}"
    return f"ami:{str(data['host']).lower()}:{int(data['port'])}"


def _login(client: AMIClient, username: str, password: str) -> None:
    try:
        response = _response(client.login(username=username, secret=password))
    except AMIConnectionError:
        raise
    except Exception as err:
        raise AMIConnectionError(str(err)) from err

    if response.is_error():
        message = str(response.keys.get("Message", "AMI authentication failed"))
        raise AMIAuthenticationError(message)


def connect_ami(
    data: dict[str, Any], *, auto_reconnect_delay: float = 5
) -> tuple[AMIClient, AutoReconnect, AMIServerInfo]:
    """Connect a long-lived AMI client for Home Assistant runtime use."""
    client = AMIClient(
        address=data["host"],
        port=int(data["port"]),
        timeout=10,
    )
    auto_reconnect = AutoReconnect(client, delay=auto_reconnect_delay)
    try:
        _login(client, str(data["username"]), str(data.get("password", "")))
        server = read_server_info(client)
    except Exception:
        try:
            client.disconnect()
        except Exception:
            pass
        raise
    return client, auto_reconnect, server


def discover_endpoints(
    client: AMIClient,
    discover_sip: bool = True,
    discover_pjsip: bool = True,
    timeout: float = 8,
) -> tuple[AMIEndpoint, ...]:
    endpoints: dict[tuple[str, str], AMIEndpoint] = {}
    sip_done = threading.Event()
    pjsip_done = threading.Event()

    def add_pjsip(event: Event, **kwargs) -> None:
        extension = str(event.keys.get("ObjectName", "")).strip()
        if extension:
            endpoints[("PJSIP", extension)] = AMIEndpoint(
                "PJSIP",
                extension,
                str(event.keys.get("DeviceState", "Unknown")),
            )

    def add_sip(event: Event, **kwargs) -> None:
        extension = str(event.keys.get("ObjectName", "")).strip()
        if extension:
            endpoints[("SIP", extension)] = AMIEndpoint(
                "SIP",
                extension,
                str(event.keys.get("Status", "Unknown")),
            )

    def end_sip(event: Event, **kwargs) -> None:
        sip_done.set()

    def end_pjsip(event: Event, **kwargs) -> None:
        pjsip_done.set()

    listeners = []
    try:
        if discover_sip:
            listeners.append(client.add_event_listener(add_sip, white_list=["PeerEntry"]))
            listeners.append(
                client.add_event_listener(end_sip, white_list=["PeerlistComplete"])
            )
            try:
                if _action_response(client, "SIPpeers").is_error():
                    sip_done.set()
            except Exception:
                sip_done.set()
        else:
            sip_done.set()

        if discover_pjsip:
            listeners.append(
                client.add_event_listener(add_pjsip, white_list=["EndpointList"])
            )
            listeners.append(
                client.add_event_listener(end_pjsip, white_list=["EndpointListComplete"])
            )
            try:
                if _action_response(client, "PJSIPShowEndpoints").is_error():
                    pjsip_done.set()
            except Exception:
                pjsip_done.set()
        else:
            pjsip_done.set()

        deadline = time.monotonic() + timeout
        for completed in (sip_done, pjsip_done):
            remaining = max(0.0, deadline - time.monotonic())
            completed.wait(remaining)
    finally:
        for listener in listeners:
            try:
                client.remove_event_listener(listener)
            except (ValueError, AttributeError):
                pass

    return tuple(
        sorted(endpoints.values(), key=lambda item: (item.tech, item.extension.casefold()))
    )


def probe_ami(
    data: dict[str, Any],
    *,
    discover_sip: bool = True,
    discover_pjsip: bool = True,
    discovery_timeout: float = 5,
) -> AMIProbeResult:
    """Validate AMI and discover server metadata/endpoints, then disconnect."""
    client = AMIClient(
        address=data["host"],
        port=int(data["port"]),
        timeout=10,
    )
    try:
        _login(client, str(data["username"]), str(data.get("password", "")))
        server = read_server_info(client)
        endpoints = discover_endpoints(
            client,
            discover_sip,
            discover_pjsip,
            discovery_timeout,
        )
        return AMIProbeResult(server=server, endpoints=endpoints)
    finally:
        try:
            client.logoff()
        except Exception:
            pass
        try:
            client.disconnect()
        except Exception:
            pass
