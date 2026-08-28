"""Grandstream HT503 local web status support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from html import unescape
import logging
import re
from typing import Any

from aiohttp import ClientSession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

_LOGIN_PATH = "/cgi-bin/dologin"
_STATUS_PATH = "/cgi-bin/index"


@dataclass(slots=True)
class HT503PortStatus:
    """Status for one HT503 analog port."""

    port: str
    state: str
    user_id: str
    registration: str

    @property
    def registered(self) -> bool:
        """Return whether the SIP account is registered."""
        value = self.registration.strip().lower()
        return bool(value) and "registered" in value and not value.startswith("not ")


class HT503Client:
    """Very small local client for the legacy HT503 web interface."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int,
        password: str,
    ) -> None:
        self._session = session
        self._host = host.strip()
        self._port = port
        self._password = password
        self._logged_in = False

    @property
    def base_url(self) -> str:
        """Return the local configuration URL."""
        return f"http://{self._host}:{self._port}"

    async def async_login(self) -> None:
        """Log in to the HT503 and retain its session cookie."""
        data = {
            "P2": self._password,
            "Login": "Login",
            "gnkey": "0b82",
        }
        try:
            async with self._session.post(
                f"{self.base_url}{_LOGIN_PATH}", data=data, timeout=10
            ) as response:
                if response.status >= 400:
                    raise UpdateFailed(f"HT503 login returned HTTP {response.status}")
                await response.read()
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Unable to log in to HT503: {err}") from err

        self._logged_in = True

    async def async_get_status(self) -> dict[str, HT503PortStatus]:
        """Read and parse the live HT503 status table."""
        if not self._logged_in:
            await self.async_login()

        try:
            async with self._session.get(
                f"{self.base_url}{_STATUS_PATH}", timeout=10
            ) as response:
                if response.status >= 400:
                    raise UpdateFailed(f"HT503 status returned HTTP {response.status}")
                text = await response.text(errors="ignore")
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Unable to read HT503 status: {err}") from err

        parsed = parse_ht503_status(text)
        if parsed:
            return parsed

        # Old firmware can silently send the login page when the cookie expired.
        self._logged_in = False
        await self.async_login()
        try:
            async with self._session.get(
                f"{self.base_url}{_STATUS_PATH}", timeout=10
            ) as response:
                text = await response.text(errors="ignore")
        except Exception as err:
            raise UpdateFailed(f"Unable to read HT503 status after login: {err}") from err

        parsed = parse_ht503_status(text)
        if not parsed:
            raise UpdateFailed("HT503 status page did not contain FXS/FXO status rows")
        return parsed


def _clean_html(value: str) -> str:
    value = re.sub(r"(?is)<[^>]+>", "", value)
    return unescape(value).replace("\xa0", " ").strip()


def parse_ht503_status(html: str) -> dict[str, HT503PortStatus]:
    """Parse FXS and FXO rows from the HT503 STATUS page."""
    result: dict[str, HT503PortStatus] = {}

    # Grandstream HT503 STATUS page layout:
    # Port | Hook/State | User ID | Registration
    for port in ("FXS", "FXO"):
        pattern = re.compile(
            rf"(?is)<td[^>]*>\s*{re.escape(port)}\s*</td>\s*"
            r"<td[^>]*>\s*<b>(.*?)</b>\s*</td>\s*"
            r"<td[^>]*>\s*<b>(.*?)</b>\s*</td>\s*"
            r"<td[^>]*>\s*<b>(.*?)</b>\s*</td>"
        )
        match = pattern.search(html)
        if not match:
            continue

        result[port] = HT503PortStatus(
            port=port,
            state=_clean_html(match.group(1)),
            user_id=_clean_html(match.group(2)),
            registration=_clean_html(match.group(3)),
        )

    return result


class HT503Coordinator(DataUpdateCoordinator[dict[str, HT503PortStatus]]):
    """Poll the HT503 legacy web status page."""

    def __init__(self, hass, client: HT503Client, update_interval: timedelta) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Grandstream HT503",
            update_interval=update_interval,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, HT503PortStatus]:
        return await self.client.async_get_status()


async def async_test_ht503(
    session: ClientSession,
    host: str,
    port: int,
    password: str,
) -> dict[str, Any]:
    """Validate HT503 access and return a small discovery result."""
    client = HT503Client(session, host, port, password)
    status = await client.async_get_status()
    return {
        key: {
            "state": value.state,
            "user_id": value.user_id,
            "registration": value.registration,
        }
        for key, value in status.items()
    }
