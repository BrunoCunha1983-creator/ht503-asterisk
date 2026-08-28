"""Sensor entities for Asterisk and Grandstream HT503."""

from __future__ import annotations

from asterisk.ami import Event
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import now

from .base import AsteriskDeviceEntity
from .const import (
    CONF_ENABLE_CONNECTED_LINE,
    CONF_ENABLE_DEVICE_STATE,
    CONF_ENABLE_DTMF,
    DEFAULT_ENABLE_CONNECTED_LINE,
    DEFAULT_ENABLE_DEVICE_STATE,
    DEFAULT_ENABLE_DTMF,
    DOMAIN,
    HT503_COORDINATOR,
    STATE_ICONS,
    STATES,
)
from .ht503 import HT503Coordinator


def _event_value(event: Event, key: str, default=""):
    return event.keys.get(key, default)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Asterisk sensor entities."""
    devices = hass.data[DOMAIN][entry.entry_id][CONF_DEVICES]
    entities = []

    for device in devices:
        if entry.options.get(CONF_ENABLE_DEVICE_STATE, DEFAULT_ENABLE_DEVICE_STATE):
            entities.append(DeviceStateSensor(hass, entry, device))
        if entry.options.get(
            CONF_ENABLE_CONNECTED_LINE, DEFAULT_ENABLE_CONNECTED_LINE
        ):
            entities.append(ConnectedLineSensor(hass, entry, device))
        if entry.options.get(CONF_ENABLE_DTMF, DEFAULT_ENABLE_DTMF):
            entities.append(DTMFSentSensor(hass, entry, device))
            entities.append(DTMFReceivedSensor(hass, entry, device))

    coordinator: HT503Coordinator | None = hass.data[DOMAIN][entry.entry_id].get(
        HT503_COORDINATOR
    )
    if coordinator is not None:
        for port in ("FXS", "FXO"):
            entities.append(HT503PortStateSensor(entry, coordinator, port))
            entities.append(HT503PortUserIDSensor(entry, coordinator, port))

    async_add_entities(entities)


class DeviceStateSensor(AsteriskDeviceEntity, SensorEntity):
    """Current Asterisk device state."""

    def __init__(self, hass, entry, device):
        super().__init__(hass, entry, device)
        self._unique_id = f"{self._unique_id_prefix}_state"
        self._name = f"{device['extension']} State"
        self._state = device["status"]
        self._ami_client.add_event_listener(
            self.handle_event,
            white_list=["DeviceStateChange"],
            Device=f"{device['tech']}/{device['extension']}",
        )

    def handle_event(self, event: Event, **kwargs):
        state = str(_event_value(event, "State", "UNKNOWN"))
        self._state = STATES.get(state, STATES["UNKNOWN"])
        self._schedule_state_write()

    @property
    def native_value(self):
        return self._state

    @property
    def icon(self) -> str:
        return STATE_ICONS.get(self._state, STATE_ICONS["Unknown"])


class ConnectedLineSensor(AsteriskDeviceEntity, SensorEntity):
    """Current/last connected line for an endpoint."""

    def __init__(self, hass, entry, device):
        super().__init__(hass, entry, device)
        self._unique_id = f"{self._unique_id_prefix}_connected_line"
        self._name = f"{device['extension']} Connected Line"
        self._state = "None"
        self._extra_attributes = {}
        self._ami_client.add_event_listener(
            self.handle_new_connected_line,
            white_list=["NewConnectedLine"],
            CallerIDNum=device["extension"],
        )
        self._ami_client.add_event_listener(
            self.handle_new_connected_line,
            white_list=["NewConnectedLine"],
            ConnectedLineNum=device["extension"],
        )
        self._ami_client.add_event_listener(
            self.handle_hangup,
            white_list=["Hangup"],
            CallerIDNum=device["extension"],
        )
        self._ami_client.add_event_listener(
            self.handle_new_channel,
            white_list=["Newchannel"],
            CallerIDNum=device["extension"],
        )

    def _attributes(self, event: Event) -> dict:
        keys = (
            "Channel",
            "ChannelState",
            "ChannelStateDesc",
            "CallerIDNum",
            "CallerIDName",
            "ConnectedLineNum",
            "ConnectedLineName",
            "Exten",
            "Context",
        )
        return {key: _event_value(event, key) for key in keys}

    def handle_new_connected_line(self, event: Event, **kwargs):
        connected = str(_event_value(event, "ConnectedLineNum"))
        caller = str(_event_value(event, "CallerIDNum"))
        self._state = caller if connected == self._device["extension"] else connected
        self._state = self._state or "None"
        self._extra_attributes = self._attributes(event)
        self._schedule_state_write()

    def handle_hangup(self, event: Event, **kwargs):
        if str(_event_value(event, "Cause")) == "26":
            return
        self._state = "None"
        self._extra_attributes = self._attributes(event)
        self._extra_attributes["Cause"] = _event_value(event, "Cause")
        self._extra_attributes["Cause-txt"] = _event_value(event, "Cause-txt")
        self._schedule_state_write()

    def handle_new_channel(self, event: Event, **kwargs):
        self._state = "None"
        self._extra_attributes = self._attributes(event)
        self._schedule_state_write()

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_attributes

    @property
    def icon(self) -> str:
        return "mdi:phone-remove" if self._state == "None" else "mdi:phone-incoming-outgoing"


class DTMFSentSensor(AsteriskDeviceEntity, SensorEntity):
    """Timestamp and digit for latest sent DTMF."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, hass, entry, device):
        super().__init__(hass, entry, device)
        self._unique_id = f"{self._unique_id_prefix}_dtmf_sent"
        self._name = f"{device['extension']} DTMF Sent"
        self._state = None
        self._extra_attributes = {}
        self._ami_client.add_event_listener(
            self.handle_dtmf,
            white_list=["DTMFBegin"],
            ConnectedLineNum=device["extension"],
            Direction="Sent",
        )

    def handle_dtmf(self, event: Event, **kwargs):
        self._state = now()
        self._extra_attributes = {
            key: _event_value(event, key)
            for key in (
                "Channel",
                "Digit",
                "CallerIDNum",
                "CallerIDName",
                "ConnectedLineNum",
                "ConnectedLineName",
                "Context",
            )
        }
        self._schedule_state_write()

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_attributes


class DTMFReceivedSensor(AsteriskDeviceEntity, SensorEntity):
    """Timestamp and digit for latest received DTMF."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, hass, entry, device):
        super().__init__(hass, entry, device)
        self._unique_id = f"{self._unique_id_prefix}_dtmf_received"
        self._name = f"{device['extension']} DTMF Received"
        self._state = None
        self._extra_attributes = {}
        self._ami_client.add_event_listener(
            self.handle_dtmf,
            white_list=["DTMFBegin"],
            ConnectedLineNum=device["extension"],
            Direction="Received",
        )

    def handle_dtmf(self, event: Event, **kwargs):
        self._state = now()
        self._extra_attributes = {
            key: _event_value(event, key)
            for key in (
                "Channel",
                "Digit",
                "ConnectedLineNum",
                "ConnectedLineName",
                "Context",
            )
        }
        self._schedule_state_write()

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_attributes


class HT503BaseSensor(CoordinatorEntity[HT503Coordinator], SensorEntity):
    """Base HT503 sensor."""

    def __init__(self, entry, coordinator: HT503Coordinator, port: str, suffix: str, name: str):
        super().__init__(coordinator)
        self._entry = entry
        self._port = port
        self._attr_unique_id = f"{entry.entry_id}_ht503_{port.lower()}_{suffix}"
        self._attr_name = f"HT503 {port} {name}"

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

    @property
    def _port_data(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._port)


class HT503PortStateSensor(HT503BaseSensor):
    def __init__(self, entry, coordinator, port):
        super().__init__(entry, coordinator, port, "state", "State")

    @property
    def native_value(self):
        port_data = self._port_data
        return port_data.state if port_data else None

    @property
    def icon(self):
        if self._port == "FXS":
            return "mdi:phone-classic"
        return "mdi:phone-incoming-outgoing"


class HT503PortUserIDSensor(HT503BaseSensor):
    def __init__(self, entry, coordinator, port):
        super().__init__(entry, coordinator, port, "user_id", "User ID")

    @property
    def native_value(self):
        port_data = self._port_data
        return port_data.user_id if port_data else None

    @property
    def extra_state_attributes(self):
        port_data = self._port_data
        return {"registration": port_data.registration} if port_data else {}

    @property
    def icon(self):
        return "mdi:account-voice"
