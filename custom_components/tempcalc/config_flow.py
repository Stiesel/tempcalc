from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er

from .const import (
    DOMAIN,
    OUTDOOR_KEYWORDS,
    PLANT_KEYWORDS,
    DEFAULT_ENABLE_ABSOLUTE_HUMIDITY,
    DEFAULT_ENABLE_MOLD_INDEX,
    DEFAULT_ENABLE_DEW_POINT,
    DEFAULT_ENABLE_ENTHALPY,
    DEFAULT_ENABLE_VENTILATION_RECOMMENDATION,
    DEFAULT_ENABLE_VENTILATION_DURATION,
)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def _is_plant_sensor(entity_id: str) -> bool:
    """Exclude plant sensors by name."""
    name = entity_id.lower()
    return any(keyword in name for keyword in PLANT_KEYWORDS)


def _is_outdoor_sensor(entity_id: str) -> bool:
    """Detect outdoor sensors by name."""
    name = entity_id.lower()
    return any(keyword in name for keyword in OUTDOOR_KEYWORDS)


def _is_temperature_sensor(state) -> bool:
    """Detect real temperature sensors using robust heuristics."""
    entity_id = state.entity_id.lower()
    attrs = state.attributes

    # Exclude obvious non-climate sensors early
    if _is_plant_sensor(entity_id):
        return False
    if any(x in entity_id for x in ["energy_", "power", "voltage", "current", "wifi", "mqtt", "connect_count"]):
        return False
    if any(x in entity_id for x in ["backup", "uptime", "runtime"]):
        return False

    # Must be numeric
    try:
        val = float(str(state.state).replace(",", "."))
    except Exception:
        return False

    # Plausible range
    if not (-40.0 <= val <= 80.0):
        return False

    # Unit check
    unit = str(attrs.get("unit_of_measurement", "")).lower().strip()
    if unit in ["°c", "c", "℃", "celsius", "°f", "f", "fahrenheit"]:
        return True

    # Name heuristics – only if unit missing
    if any(x in entity_id for x in ["temp", "temperatur", "temperature", "t_"]):
        return True

    return False


def _is_humidity_sensor(state) -> bool:
    """Detect real humidity sensors using robust heuristics."""
    entity_id = state.entity_id.lower()
    attrs = state.attributes

    if _is_plant_sensor(entity_id):
        return False
    if any(x in entity_id for x in ["energy_", "power", "voltage", "current", "wifi", "mqtt", "connect_count"]):
        return False
    if any(x in entity_id for x in ["backup", "uptime", "runtime"]):
        return False

    # Must be numeric
    try:
        val = float(str(state.state).replace(",", "."))
    except Exception:
        return False

    # Plausible range
    if not (0.0 <= val <= 100.0):
        return False

    # Unit check
    unit = str(attrs.get("unit_of_measurement", "")).lower().strip()
    if unit in ["%", "percent", "rel. %", "rh"]:
        return True

    # Name heuristics – only wenn Einheit fehlt
    if any(x in entity_id for x in ["hum", "humidity", "feuchte", "r_h", "rh"]):
        return True

    return False


def _filter_by_area_and_text(
    hass: HomeAssistant,
    entity_ids: list[str],
    area_name: str | None,
    text_filter: str | None,
) -> list[str]:
    """Optional filter by area name and free text."""
    if not entity_ids:
        return []

    area_name = (area_name or "").strip().lower()
    text_filter = (text_filter or "").strip().lower()

    if not area_name and not text_filter:
        return entity_ids

    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)

    # Resolve area name -> area_id
    area_id = None
    if area_name:
        for area in area_reg.areas.values():
            if area.name.lower() == area_name:
                area_id = area.id
                break

    result: list[str] = []

    for eid in entity_ids:
        eid_l = eid.lower()

        # Text filter
        if text_filter and text_filter not in eid_l:
            # Try friendly name
            state = hass.states.get(eid)
            friendly = (state and str(state.attributes.get("friendly_name", "")).lower()) or ""
            if text_filter not in friendly:
                continue

        # Area filter
        if area_id:
            ent_entry = ent_reg.async_get(eid)
            if not ent_entry:
                continue
            if ent_entry.area_id != area_id:
                continue

        result.append(eid)

    return result


def _get_temperature_sensors(
    hass: HomeAssistant,
    area_name: str | None = None,
    text_filter: str | None = None,
) -> list[str]:
    """Return temperature sensors, optionally filtered by area/text."""
    sensors: list[str] = []
    for state in hass.states.async_all("sensor"):
        if _is_temperature_sensor(state):
            sensors.append(state.entity_id)

    return _filter_by_area_and_text(hass, sensors, area_name, text_filter)


def _get_humidity_sensors(
    hass: HomeAssistant,
    area_name: str | None = None,
    text_filter: str | None = None,
) -> list[str]:
    """Return humidity sensors, optionally filtered by area/text."""
    sensors: list[str] = []
    for state in hass.states.async_all("sensor"):
        if _is_humidity_sensor(state):
            sensors.append(state.entity_id)

    return _filter_by_area_and_text(hass, sensors, area_name, text_filter)


def _guess_best_outdoor(
    hass: HomeAssistant,
    candidates: list[str],
) -> str | None:
    """Guess the best outdoor sensor among candidates."""
    if not candidates:
        return None

    # 1. Name heuristics (balkon, garten, outdoor, terrace, etc.)
    outdoor_like = [eid for eid in candidates if _is_outdoor_sensor(eid)]
    if outdoor_like:
        return outdoor_like[0]

    # 2. Area heuristics (areas mit typischen Namen)
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)

    outdoor_area_ids = {
        area.id
        for area in area_reg.areas.values()
        if any(x in area.name.lower() for x in ["balkon", "balkony", "garten", "garden", "terrasse", "terrace", "outdoor"])
    }

    if outdoor_area_ids:
        for eid in candidates:
            ent = ent_reg.async_get(eid)
            if ent and ent.area_id in outdoor_area_ids:
                return eid

    # 3. Fallback: first candidate
    return candidates[0]


def _get_area_names(hass: HomeAssistant) -> list[str]:
    """Return sorted list of all area names."""
    area_reg = ar.async_get(hass)
    names = sorted(area.name for area in area_reg.areas.values() if area.name)
    return names


# ---------------------------------------------------------
# Config Flow
# ---------------------------------------------------------

class TempCalcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle TempCalc config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial setup step."""
        errors: dict[str, str] = {}

        # First call: no input yet -> just show form
        if user_input is None:
            return await self._show_user_form()

        # On submit: basic validation – if something fundamental fehlt, zeig das Formular erneut
        required_keys = ["indoor_temperature_sensor", "indoor_humidity_sensor"]
        for key in required_keys:
            if not user_input.get(key):
                errors[key] = "required"

        if errors:
            return await self._show_user_form(user_input=user_input, errors=errors)

        # Create entry, title optional per Raumname
        title = user_input.get("room_name") or "TempCalc"
        return self.async_create_entry(
            title=title,
            data={},
            options=user_input,
        )

    async def _show_user_form(self, user_input=None, errors=None):
        """Build and show the main setup form."""
        user_input = user_input or {}
        errors = errors or {}

        room_area = user_input.get("room_area", "")
        room_filter = user_input.get("room_filter", "")

        # Get sensors with optional filter (area/text)
        temp_sensors = _get_temperature_sensors(self.hass, area_name=room_area or None, text_filter=room_filter or None)
        hum_sensors = _get_humidity_sensors(self.hass, area_name=room_area or None, text_filter=room_filter or None)

        # Fallback: if filter zu streng, nimm alle
        if not temp_sensors:
            temp_sensors = _get_temperature_sensors(self.hass)
        if not hum_sensors:
            hum_sensors = _get_humidity_sensors(self.hass)

        # Auto-detect outdoor sensors
        outdoor_temp_candidates = [s for s in temp_sensors if _is_outdoor_sensor(s)]
        outdoor_hum_candidates = [s for s in hum_sensors if _is_outdoor_sensor(s)]

        best_outdoor_temp = _guess_best_outdoor(self.hass, outdoor_temp_candidates) if outdoor_temp_candidates else None
        best_outdoor_hum = _guess_best_outdoor(self.hass, outdoor_hum_candidates) if outdoor_hum_candidates else None

        # Area list for dropdown
        areas = _get_area_names(self.hass)
        area_options = [""] + areas  # "" = keine Auswahl

        schema = vol.Schema(
            {
                # Raum / Filter / Name
                vol.Optional("room_name", default=user_input.get("room_name", "")): str,
                vol.Optional("room_area", default=user_input.get("room_area", "")): vol.In(area_options),
                vol.Optional("room_filter", default=user_input.get("room_filter", "")): str,

                # Innensensoren
                vol.Required(
                    "indoor_temperature_sensor",
                    default=user_input.get("indoor_temperature_sensor", temp_sensors[0] if temp_sensors else ""),
                ): vol.In(temp_sensors),
                vol.Required(
                    "indoor_humidity_sensor",
                    default=user_input.get("indoor_humidity_sensor", hum_sensors[0] if hum_sensors else ""),
                ): vol.In(hum_sensors),

                # Außensensoren – manuell überschreibbar
                vol.Optional(
                    "outdoor_temperature_sensor",
                    default=user_input.get(
                        "outdoor_temperature_sensor",
                        best_outdoor_temp or "",
                    ),
                ): str,
                vol.Optional(
                    "outdoor_humidity_sensor",
                    default=user_input.get(
                        "outdoor_humidity_sensor",
                        best_outdoor_hum or "",
                    ),
                ): str,

                # Berechnungen
                vol.Optional(
                    "enable_absolute_humidity",
                    default=user_input.get("enable_absolute_humidity", DEFAULT_ENABLE_ABSOLUTE_HUMIDITY),
                ): bool,
                vol.Optional(
                    "enable_mold_index",
                    default=user_input.get("enable_mold_index", DEFAULT_ENABLE_MOLD_INDEX),
                ): bool,
                vol.Optional(
                    "enable_dew_point",
                    default=user_input.get("enable_dew_point", DEFAULT_ENABLE_DEW_POINT),
                ): bool,
                vol.Optional(
                    "enable_enthalpy",
                    default=user_input.get("enable_enthalpy", DEFAULT_ENABLE_ENTHALPY),
                ): bool,
                vol.Optional(
                    "enable_ventilation_recommendation",
                    default=user_input.get(
                        "enable_ventilation_recommendation",
                        DEFAULT_ENABLE_VENTILATION_RECOMMENDATION,
                    ),
                ): bool,
                vol.Optional(
                    "enable_ventilation_duration",
                    default=user_input.get(
                        "enable_ventilation_duration",
                        DEFAULT_ENABLE_VENTILATION_DURATION,
                    ),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_options(self, user_input=None):
        """Options flow to adjust sensors and calculations later."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Minimal validation
            if not user_input.get("indoor_temperature_sensor"):
                errors["indoor_temperature_sensor"] = "required"
            if not user_input.get("indoor_humidity_sensor"):
                errors["indoor_humidity_sensor"] = "required"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Erste Anzeige oder Fehler -> Formular zeigen
        return await self._show_options_form(user_input=user_input, errors=errors)

    async def _show_options_form(self, user_input=None, errors=None):
        """Build options form based on existing config entry."""
        errors = errors or {}
        entry = self.config_entry
        current = dict(entry.options)
        if user_input:
            current.update(user_input)

        room_area = current.get("room_area", "")
        room_filter = current.get("room_filter", "")

        temp_sensors = _get_temperature_sensors(self.hass, area_name=room_area or None, text_filter=room_filter or None)
        hum_sensors = _get_humidity_sensors(self.hass, area_name=room_area or None, text_filter=room_filter or None)

        if not temp_sensors:
            temp_sensors = _get_temperature_sensors(self.hass)
        if not hum_sensors:
            hum_sensors = _get_humidity_sensors(self.hass)

        outdoor_temp_candidates = [s for s in temp_sensors if _is_outdoor_sensor(s)]
        outdoor_hum_candidates = [s for s in hum_sensors if _is_outdoor_sensor(s)]

        best_outdoor_temp = _guess_best_outdoor(self.hass, outdoor_temp_candidates) if outdoor_temp_candidates else None
        best_outdoor_hum = _guess_best_outdoor(self.hass, outdoor_hum_candidates) if outdoor_hum_candidates else None

        areas = _get_area_names(self.hass)
        area_options = [""] + areas

        schema = vol.Schema(
            {
                vol.Optional("room_name", default=current.get("room_name", "")): str,
                vol.Optional("room_area", default=current.get("room_area", "")): vol.In(area_options),
                vol.Optional("room_filter", default=current.get("room_filter", "")): str,

                vol.Required(
                    "indoor_temperature_sensor",
                    default=current.get(
                        "indoor_temperature_sensor",
                        temp_sensors[0] if temp_sensors else "",
                    ),
                ): vol.In(temp_sensors),
                vol.Required(
                    "indoor_humidity_sensor",
                    default=current.get(
                        "indoor_humidity_sensor",
                        hum_sensors[0] if hum_sensors else "",
                    ),
                ): vol.In(hum_sensors),

                vol.Optional(
                    "outdoor_temperature_sensor",
                    default=current.get(
                        "outdoor_temperature_sensor",
                        best_outdoor_temp or "",
                    ),
                ): str,
                vol.Optional(
                    "outdoor_humidity_sensor",
                    default=current.get(
                        "outdoor_humidity_sensor",
                        best_outdoor_hum or "",
                    ),
                ): str,

                vol.Optional(
                    "enable_absolute_humidity",
                    default=current.get("enable_absolute_humidity", DEFAULT_ENABLE_ABSOLUTE_HUMIDITY),
                ): bool,
                vol.Optional(
                    "enable_mold_index",
                    default=current.get("enable_mold_index", DEFAULT_ENABLE_MOLD_INDEX),
                ): bool,
                vol.Optional(
                    "enable_dew_point",
                    default=current.get("enable_dew_point", DEFAULT_ENABLE_DEW_POINT),
                ): bool,
                vol.Optional(
                    "enable_enthalpy",
                    default=current.get("enable_enthalpy", DEFAULT_ENABLE_ENTHALPY),
                ): bool,
                vol.Optional(
                    "enable_ventilation_recommendation",
                    default=current.get(
                        "enable_ventilation_recommendation",
                        DEFAULT_ENABLE_VENTILATION_RECOMMENDATION,
                    ),
                ): bool,
                vol.Optional(
                    "enable_ventilation_duration",
                    default=current.get(
                        "enable_ventilation_duration",
                        DEFAULT_ENABLE_VENTILATION_DURATION,
                    ),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
            errors=errors,
        )
