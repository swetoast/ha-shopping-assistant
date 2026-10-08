"""Constants for the Shopping Assistant integration."""
from __future__ import annotations

from typing import Any, Final

DOMAIN: Final = "shopping_assistant"

# Earlier name of this integration. Its data and options are imported once.
LEGACY_DOMAIN: Final = "ean_reader"
LEGACY_STORAGE_KEY: Final = "ean_reader_mappings"
APP_NAME: Final = "HomeAssistant-ShoppingAssistant"

# Storage
STORAGE_KEY: Final = "shopping_assistant"
STORAGE_VERSION: Final = 3
STORAGE_MINOR_VERSION: Final = 2
SAVE_DELAY: Final = 10

# Dispatcher signal used to refresh entities after any data change
SIGNAL_UPDATE: Final = f"{DOMAIN}_update"

# Event fired by the companion apps when something is shared to Home Assistant
SHARE_EVENT: Final = "mobile_app.share"

# Behaviour tuning
UNKNOWN_RETRY_SECONDS: Final = 86400  # retry products missing from OFF after 24h
DUPLICATE_SCAN_SECONDS: Final = 3.0  # ignore repeated share/webhook scans
REFRESH_AFTER_DAYS: Final = 30  # refresh OFF data in the background when older
EXPIRY_WARNING_DAYS: Final = 7
MAX_PRICE_HISTORY: Final = 50
MAX_UNKNOWNS_IN_ATTRIBUTES: Final = 20
UNKNOWN_PRODUCT_NAME: Final = "Unknown Product"

# Events
EVENT_PRODUCT_SCANNED: Final = "shopping_assistant_product_scanned"
EVENT_LOOKUP_COMPLETED: Final = "shopping_assistant_lookup_completed"
EVENT_MISSING_PRODUCT: Final = "shopping_assistant_missing_product"
EVENT_MAPPING_ADDED: Final = "shopping_assistant_mapping_added"
EVENT_MAPPING_REMOVED: Final = "shopping_assistant_mapping_removed"
EVENT_IMPORT_COMPLETE: Final = "shopping_assistant_import_complete"
EVENT_OFF_SUBMITTED: Final = "shopping_assistant_off_submitted"

# Config entry data (not user editable)
DATA_WEBHOOK_ID: Final = "webhook_id"
DATA_APP_UUID: Final = "app_uuid"

# Options
CONF_CONTACT_EMAIL: Final = "contact_email"
CONF_LANGUAGE_PRIORITY: Final = "language_priority"
CONF_AUTO_ADD_TO_SHOPPING_LIST: Final = "auto_add_to_shopping_list"
CONF_SHOPPING_LIST_ENTITY: Final = "shopping_list_entity"
CONF_SHOW_NOTIFICATIONS: Final = "show_notifications"
CONF_TRACK_PRICES: Final = "track_prices"
CONF_TRACK_EXPIRY: Final = "track_expiry"
CONF_ENABLE_WEBHOOK: Final = "enable_webhook"
CONF_WEBHOOK_LOCAL_ONLY: Final = "webhook_local_only"
CONF_ENABLE_OFF_SUBMISSION: Final = "enable_off_submission"
CONF_OFF_USERNAME: Final = "off_username"
CONF_OFF_PASSWORD: Final = "off_password"
CONF_OFF_TEST_MODE: Final = "off_test_mode"

DEFAULT_LANGUAGE_PRIORITY: Final = ("sv", "en", "de", "fr", "es")

DEFAULT_OPTIONS: Final[dict[str, Any]] = {
    CONF_CONTACT_EMAIL: "",
    CONF_LANGUAGE_PRIORITY: list(DEFAULT_LANGUAGE_PRIORITY),
    CONF_AUTO_ADD_TO_SHOPPING_LIST: True,
    CONF_SHOPPING_LIST_ENTITY: "todo.shopping_list",
    CONF_SHOW_NOTIFICATIONS: True,
    CONF_TRACK_PRICES: False,
    CONF_TRACK_EXPIRY: False,
    CONF_ENABLE_WEBHOOK: False,
    CONF_WEBHOOK_LOCAL_ONLY: True,
    CONF_ENABLE_OFF_SUBMISSION: False,
    CONF_OFF_USERNAME: "",
    CONF_OFF_PASSWORD: "",
    CONF_OFF_TEST_MODE: False,
}

PLATFORMS: Final = ["binary_sensor", "sensor"]
