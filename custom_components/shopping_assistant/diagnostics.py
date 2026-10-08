"""Diagnostics for Shopping Assistant."""
from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONTACT_EMAIL,
    CONF_OFF_PASSWORD,
    CONF_OFF_USERNAME,
    DATA_APP_UUID,
    DATA_WEBHOOK_ID,
)

if TYPE_CHECKING:
    from . import ShoppingAssistantConfigEntry

TO_REDACT = {
    CONF_CONTACT_EMAIL,
    CONF_OFF_PASSWORD,
    CONF_OFF_USERNAME,
    DATA_APP_UUID,
    DATA_WEBHOOK_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ShoppingAssistantConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    assistant = entry.runtime_data
    db = assistant.db
    return {
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "api_health": asdict(assistant.health),
        "statistics": dict(db.statistics),
        "products": len(db.products),
        "named_products": sum(1 for p in db.products.values() if p.is_named),
        "products_by_source": {
            source: sum(1 for p in db.products.values() if p.source == source)
            for source in sorted({p.source for p in db.products.values()})
        },
        "unknowns": len(db.unknowns),
        "shopping_list_items": len(db.shopping.items),
    }
