from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, MIN_REQUIRED_HA_VERSION


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """YAML setup is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TempCalc from a config entry."""

    # Version check for HA 2025.12+
    current_version = hass.config.as_dict().get("version")
    if current_version and current_version < MIN_REQUIRED_HA_VERSION:
        raise HomeAssistantError(
            f"TempCalc requires Home Assistant {MIN_REQUIRED_HA_VERSION} or newer."
        )

    hass.data.setdefault(DOMAIN, {})

    # Forward to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    # Enable auto-reload when options change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload TempCalc config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload TempCalc when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
