from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

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
    name = entity_id.lower()
    return any(keyword in name for keyword in PLANT_KEYWORDS)


def _is_outdoor_sensor(entity_id: str) -> bool:
    name = entity_id.lower()
    return any(keyword in name for keyword in OUTDOOR_KEYWORDS)


def _is_temperature_sensor(state):
    entity_id = state.entity_id.lower()
    attrs = state.attributes

    if _is_plant_sensor(entity_id):
        return False

    try:
        val = float(state.state)
    except:
        return False

    unit = attrs.get("unit_of_measurement", "").lower()
    if unit not in ["°c", "c", "°f", "f"]:
        return False

    if not (-40 <= val <= 80):
        return False

    if not any(x in entity_id for x in ["temp", "temperatur", "temperature"]):
        return False

    return True


def _is_humidity_sensor(state):
    entity_id = state.entity_id.lower()
    attrs = state.attributes

    if _is_plant_sensor(entity_id):
        return False

    try:
        val = float(state.state)
    except:
        return False

    unit = attrs.get("unit_of_measurement", "").lower()
    if unit not in ["%", "percent"]:
        return False

    if not (0 <= val <= 100):
        return False

    if not any(x in entity_id for x in ["hum", "humidity", "feuchte"]):
        return False

    return True


def _get_temperature_sensors(hass: HomeAssistant):
    sensors = []
    for state in hass.states.async_all("sensor"):
        if _is_temperature_sensor(state):
            sensors.append(state.entity_id)
    return sensors


def _get_humidity_sensors(hass: HomeAssistant):
    sensors = []
    for state in hass.states.async_all("sensor"):
        if _is_humidity_sensor(state):
            sensors.append(state.entity_id)
    return sensors


# ---------------------------------------------------------
# Config Flow
# ---------------------------------------------------------

class TempCalcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="TempCalc",
                data={},
                options=user_input,
            )

        temp_sensors = _get_temperature_sensors(self.hass)
        hum_sensors = _get_humidity_sensors(self.hass)

        outdoor_temp = [s for s in temp_sensors if _is_outdoor_sensor(s)]
        outdoor_hum = [s for s in hum_sensors if _is_outdoor_sensor(s)]

        schema = vol.Schema(
            {
                vol.Required("indoor_temperature_sensor"): vol.In(temp_sensors),
                vol.Required("indoor_humidity_sensor"): vol.In(hum_sensors),

                vol.Optional("outdoor_temperature_sensor", default=outdoor_temp[0] if outdoor_temp else ""): str,
                vol.Optional("outdoor_humidity_sensor", default=outdoor_hum[0] if outdoor_hum else ""): str,

                vol.Optional("enable_absolute_humidity", default=DEFAULT_ENABLE_ABSOLUTE_HUMIDITY): bool,
                vol.Optional("enable_mold_index", default=DEFAULT_ENABLE_MOLD_INDEX): bool,
                vol.Optional("enable_dew_point", default=DEFAULT_ENABLE_DEW_POINT): bool,
                vol.Optional("enable_enthalpy", default=DEFAULT_ENABLE_ENTHALPY): bool,
                vol.Optional("enable_ventilation_recommendation", default=DEFAULT_ENABLE_VENTILATION_RECOMMENDATION): bool,
                vol.Optional("enable_ventilation_duration", default=DEFAULT_ENABLE_VENTILATION_DURATION): bool,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_options(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        temp_sensors = _get_temperature_sensors(self.hass)
        hum_sensors = _get_humidity_sensors(self.hass)

        outdoor_temp = [s for s in temp_sensors if _is_outdoor_sensor(s)]
        outdoor_hum = [s for s in hum_sensors if _is_outdoor_sensor(s)]

        entry = self.config_entry

        schema = vol.Schema(
            {
                vol.Required("indoor_temperature_sensor", default=entry.options.get("indoor_temperature_sensor")): vol.In(temp_sensors),
                vol.Required("indoor_humidity_sensor", default=entry.options.get("indoor_humidity_sensor")): vol.In(hum_sensors),

                vol.Optional("outdoor_temperature_sensor", default=entry.options.get("outdoor_temperature_sensor", outdoor_temp[0] if outdoor_temp else "")): str,
                vol.Optional("outdoor_humidity_sensor", default=entry.options.get("outdoor_humidity_sensor", outdoor_hum[0] if outdoor_hum else "")): str,

                vol.Optional("enable_absolute_humidity", default=entry.options.get("enable_absolute_humidity", DEFAULT_ENABLE_ABSOLUTE_HUMIDITY)): bool,
                vol.Optional("enable_mold_index", default=entry.options.get("enable_mold_index", DEFAULT_ENABLE_MOLD_INDEX)): bool,
                vol.Optional("enable_dew_point", default=entry.options.get("enable_dew_point", DEFAULT_ENABLE_DEW_POINT)): bool,
                vol.Optional("enable_enthalpy", default=entry.options.get("enable_enthalpy", DEFAULT_ENABLE_ENTHALPY)): bool,
                vol.Optional("enable_ventilation_recommendation", default=entry.options.get("enable_ventilation_recommendation", DEFAULT_ENABLE_VENTILATION_RECOMMENDATION)): bool,
                vol.Optional("enable_ventilation_duration", default=entry.options.get("enable_ventilation_duration", DEFAULT_ENABLE_VENTILATION_DURATION)): bool,
            }
        )

        return self.async_show_form(step_id="options", data_schema=schema)
