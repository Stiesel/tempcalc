DOMAIN = "tempcalc"

# Keywords to detect plant sensors (to exclude them)
PLANT_KEYWORDS = [
    "plant",
    "pflanze",
    "flora",
    "flower",
    "soil",
    "moisture",
    "boden",
    "erde"
]

# Keywords to detect outdoor sensors (Option C)
OUTDOOR_KEYWORDS = [
    "outdoor",
    "outside",
    "aussen",
    "außen",
    "balkon",
    "garten",
    "terrasse",
    "yard",
    "porch",
    "veranda"
]

# Mold index boundaries
MOLD_INDEX_MIN = 0.0
MOLD_INDEX_MAX = 6.0

# Default option values
DEFAULT_ENABLE_ABSOLUTE_HUMIDITY = True
DEFAULT_ENABLE_MOLD_INDEX = True
DEFAULT_ENABLE_DEW_POINT = True
DEFAULT_ENABLE_ENTHALPY = False
DEFAULT_ENABLE_VENTILATION_RECOMMENDATION = True
DEFAULT_ENABLE_VENTILATION_DURATION = True

# Temperature safety thresholds (winter protection)
MIN_INDOOR_TEMP = 18.0
MAX_TEMP_DROP = 1.5

# HA 2025.12 compatibility
MIN_REQUIRED_HA_VERSION = "2025.12.0"
