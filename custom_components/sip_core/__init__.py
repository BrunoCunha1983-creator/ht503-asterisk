import logging
import copy
from pathlib import Path
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig
from aiohttp.web import Request, Response
from homeassistant.components.hassio.const import DOMAIN as HASSIO_DOMAIN
from homeassistant.components.hassio.handler import HassIO, get_supervisor_client
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from .const import ASTERISK_ADDON_SLUG, DOMAIN, JS_FILENAME, JS_URL_PATH
from .resources import add_resources, remove_resources
from .defaults import sip_config

logger = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the SIP Core component."""

    logger.info("Registering SIP Core HTTP views")
    hass.http.register_view(SipCoreConfigView())
    hass.http.register_view(AsteriskIngressView())

    logger.info("Setting up SIP Core component")
    hass.data.setdefault(DOMAIN, {
        "data": config_entry.data,
        "options": {"sip_config": config_entry.options.get("sip_config", sip_config)},
        "entry_id": config_entry.entry_id,
    })
    # The options contain SIP passwords. Never write them to the Home Assistant log.
    logger.info("SIP Core entry loaded: %s", config_entry.entry_id)

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path=JS_URL_PATH,
                path=Path(__file__).parent / "www" / JS_FILENAME,
                cache_headers=True,
            ),
            StaticPathConfig(
                url_path="/sip_core_files/ringback-tone.mp3",
                path=Path(__file__).parent / "www" / "ringback-tone.mp3",
                cache_headers=True,
            ),
            StaticPathConfig(
                url_path="/sip_core_files/ring-tone.mp3",
                path=Path(__file__).parent / "www" / "ring-tone.mp3",
                cache_headers=True,
            ),
        ]
    )

    await add_resources(hass)

    config_entry.add_update_listener(update_listener)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    logger.info("Unloading SIP Core component")
    hass.data.pop(DOMAIN, None)
    await remove_resources(hass)
    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    logger.info("SIP Core configuration updated")
    hass.data[DOMAIN]["options"]["sip_config"] = config_entry.options.get("sip_config")


def deep_update(base_dict, overrides):
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            deep_update(base_dict[key], value)
        else:
            base_dict[key] = value
    return base_dict


class SipCoreConfigView(HomeAssistantView):
    """View to serve SIP Core configuration."""

    url = "/api/sip-core/config"
    name = "api:sip-core:config"
    requires_auth = True

    async def get(self, request: Request):
        """Handle GET request."""
        hass: HomeAssistant = request.app["hass"]
        user = request["hass_user"]

        try:
            sip_config = hass.data[DOMAIN]["options"]["sip_config"]
            
            # Replicate frontend matching logic
            matched_user = None
            users = sip_config.get("users", [])
            
            # 1. Match by User ID
            for u in users:
                if u.get("ha_username") == user.id:
                    matched_user = u
                    break
            
            # 2. Match by Name (if no ID match)
            if not matched_user:
                for u in users:
                    if u.get("ha_username") == user.name:
                        matched_user = u
                        break

            # Return credentials only for the authenticated Home Assistant user.
            # The upstream implementation returned the complete users list (including
            # every SIP password) to every authenticated browser.
            if matched_user and "overrides" in matched_user:
                overrides = matched_user["overrides"]
                config = copy.deepcopy(sip_config)
                deep_update(config, overrides)
            else:
                config = copy.deepcopy(sip_config)

            if matched_user:
                selected_user = copy.deepcopy(matched_user)
                selected_user.pop("overrides", None)
                config["users"] = [selected_user]
                config["backup_user"] = selected_user
                return self.json(config)

            if sip_config.get("allow_backup_user", False):
                config["users"] = []
                return self.json(config)

            return self.json(
                {"error": "No SIP account is assigned to this Home Assistant user"},
                status_code=403,
            )
        except KeyError:
            return self.json({"error": "No configuration found"}, status_code=500)


class AsteriskIngressView(HomeAssistantView):
    """View to handle Asterisk Add-on ingress."""

    url = "/api/sip-core/asterisk-ingress"
    name = "api:sip-core:asterisk-ingress"
    requires_auth = True

    async def get(self, request: Request) -> Response:
        hass: HomeAssistant = request.app["hass"]
        hassio: HassIO | None = hass.data.get(HASSIO_DOMAIN)
        if not hassio:
            return self.json({"error": "supervisor not available"}, status_code=503)

        supervisor_client = get_supervisor_client(hass)
        try:
            addon_info = await supervisor_client.addons.addon_info(ASTERISK_ADDON_SLUG)
            ingress_entry = addon_info.ingress_entry
            if not ingress_entry:
                raise ValueError("Ingress entry not found for Asterisk add-on")
            return self.json({"ingress_entry": ingress_entry})
        except Exception as err:
            logger.error(f"Error fetching Asterisk add-on info: {err}")
            return self.json({"error": "Failed to fetch add-on info"}, status_code=500)
