"""Binary sensors for Asterisk and Grandstream HT503."""

from __future__ import annotations

import logging

from asterisk.ami import AMIClient, AutoReconnect, Event
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .base import AsteriskDeviceEntity
from .const import (
    AUTO_RECONNECT,
    CLIENT,
    CONF_ENABLE_REGISTERED,
    DEFAULT_ENABLE_REGISTERED,
    DOMAIN,
    HT503_COORDINATOR,
    SERVER_INFO,
)
from .ht503 import HT503Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Asterisk binary sensors."""
    devices = hass.data[DOMAIN][entry.entry_id][CONF_DEVICES]
    entities = [AMIConnected(hass, entry)]

    if entry.options.get(CONF_ENABLE_REGISTERED, DEFAULT_ENABLE_REGISTERED):
        entities.extend(RegisteredSensor(hass, entry, device) for device in devices)

    coordinator: HT503Coordinator | None = hass.data[DOMAIN][entry.entry_id].get(
        HT503_COORDINATOR
    )
    if coordinator is not None:
        entities.append(HT503Connected(entry, coordinator))
        entities.append(HT503PortRegistered(entry, coordinator, "FXS"))
        entities.append(HT503PortRegistered(entry, coordinator, "FXO"))

    async_add_entities(entities)


class RegisteredSensor(AsteriskDeviceEntity, BinarySensorEntity):
    """Whether an Asterisk SIP/PJSIP endpoint is available/registered."""

    def __init__(self, hass, entry, device):
        super().__init__(hass, entry, device)
        self._unique_id = f"{self._unique_id_prefix}_registered"
        self._name = f"{device['extension']} Registered"
        initial = str(device["status"]).lower()
        self._state = initial not in ("unavailable", "unknown")
        self._ami_client.add_event_listener(
            self.handle_state_change,
            white_list=["DeviceStateChange"],
            Device=f"{device['tech']}/{device['extension']}",
        )

    def handle_state_change(self, event: Event, **kwargs):
        state = str(event.keys.get("State", "UNKNOWN")).upper()
        self._state = state not in ("UNAVAILABLE", "UNKNOWN", "INVALID")
        self._schedule_state_write()

    @property
    def is_on(self) -> bool:
        return self._state

    @property
    def icon(self) -> str:
        return "mdi:phone-check" if self._state else "mdi:phone-off"


class AMIConnected(BinarySensorEntity):
    """AMI connection state and Asterisk server device."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_connected"
        self._attr_name = "AMI Connected"
        self._state = True
        self._ami_client: AMIClient = hass.data[DOMAIN][entry.entry_id][CLIENT]
        self._auto_reconnect: AutoReconnect = hass.data[DOMAIN][entry.entry_id][AUTO_RECONNECT]
        self._auto_reconnect.on_disconnect = self.on_disconnect
        self._auto_reconnect.on_reconnect = self.on_reconnect
        self._server_info = hass.data[DOMAIN][entry.entry_id].get(SERVER_INFO)

    def _schedule(self):
        self._hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    def on_disconnect(self, client, response):
        _LOGGER.debug("Disconnected from AMI: %s", response)
        try:
            client.disconnect()
        except Exception:
            pass
        self._state = False
        self._schedule()

    def on_reconnect(self, client, response):
        _LOGGER.debug("Reconnected to AMI: %s", response)
        self._state = True
        self._schedule()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_server")},
            "name": "Asterisk Server",
            "manufacturer": "Asterisk",
            "model": "PBX / AMI",
            "sw_version": getattr(self._server_info, "version", None),
        }

    @property
    def is_on(self) -> bool:
        return self._state


class HT503Connected(CoordinatorEntity[HT503Coordinator], BinarySensorEntity):
    """HT503 web-interface connectivity."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "HT503 Connected"

    def __init__(self, entry, coordinator):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_ht503_connected"

    @property
    def is_on(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_ht503")},
            "name": "Grandstream HT503",
            "manufacturer": "Grandstream",
            "model": "HT503",
            "configuration_url": self.coordinator.client.base_url,
            "via_device": (DOMAIN, f"{self._entry.entry_id}_server"),
        }


class HT503PortRegistered(CoordinatorEntity[HT503Coordinator], BinarySensorEntity):
    """HT503 FXS/FXO registration state from its STATUS page."""

    def __init__(self, entry, coordinator, port):
        super().__init__(coordinator)
        self._entry = entry
        self._port = port
        self._attr_unique_id = f"{entry.entry_id}_ht503_{port.lower()}_registered"
        self._attr_name = f"HT503 {port} Registered"

    @property
    def is_on(self):
        if not self.coordinator.data:
            return False
        data = self.coordinator.data.get(self._port)
        return data.registered if data else False

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        data = self.coordinator.data.get(self._port)
        return {"registration_text": data.registration} if data else {}

    @property
    def icon(self):
        return "mdi:phone-check" if self.is_on else "mdi:phone-off"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_ht503")},
            "name": "Grandstream HT503",
            "manufacturer": "Grandstream",
            "model": "HT503",
            "configuration_url": self.coordinator.client.base_url,
            "via_device": (DOMAIN, f"{self._entry.entry_id}_server"),
        }
