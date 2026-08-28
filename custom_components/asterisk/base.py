"""Base entities for Asterisk."""

from __future__ import annotations

from asterisk.ami import AMIClient

from .const import CLIENT, DOMAIN


class AsteriskDeviceEntity:
    """Base mixin for an Asterisk endpoint entity."""

    def __init__(self, hass, entry, device):
        self._hass = hass
        self._device = device
        self._entry = entry
        self._unique_id_prefix = (
            f"{entry.entry_id}_{device['tech'].lower()}_{device['extension']}"
        )
        self._ami_client: AMIClient = hass.data[DOMAIN][entry.entry_id][CLIENT]
        self._name: str
        self._unique_id: str

    def _schedule_state_write(self) -> None:
        """Safely schedule a state write from an AMI callback thread."""
        self._hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._unique_id_prefix)},
            "name": f"{self._device['tech']}/{self._device['extension']}",
            "manufacturer": "Asterisk",
            "model": self._device["tech"],
            "via_device": (DOMAIN, f"{self._entry.entry_id}_server"),
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id
