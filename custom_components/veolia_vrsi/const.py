"""Constante pentru integrarea Veolia VRSI."""

from __future__ import annotations

DOMAIN = "veolia_vrsi"
MANUFACTURER = "Veolia România Soluții Integrate"
PORTAL_URL = "https://clienti-vrsi.veolia.ro"

# --- Config entry ---
CONF_BRIDGE_URL = "bridge_url"
CONF_BRIDGE_TOKEN = "bridge_token"
CONF_LOCATIONS = "locations"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL_HOURS = 6
MIN_SCAN_INTERVAL_HOURS = 2
MAX_SCAN_INTERVAL_HOURS = 24

# --- Acțiune ---
SERVICE_SUBMIT_INDEX = "trimite_index"
ATTR_METER = "contor"
ATTR_INDEX = "index"

# --- Limite atribute ---
HISTORY_LIMIT = 24
PAID_LIMIT = 12

# Toleranța pentru sume (lei)
AMOUNT_EPSILON = 0.005
