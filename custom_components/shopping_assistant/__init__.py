"""Shopping Assistant integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import OpenFoodFactsClient
from .const import (
    DATA_APP_UUID,
    DOMAIN,
    LEGACY_DOMAIN,
    PLATFORMS,
    SHARE_EVENT,
)
from .ean import extract_ean
from .card import async_register_card
from .product_database import ProductDatabase
from .runtime import Settings, ShoppingAssistant
from .scanner_webhook import async_setup_webhook
from .services import async_setup_services
from .shopping import ShoppingList

_LOGGER = logging.getLogger(__name__)

type ShoppingAssistantConfigEntry = ConfigEntry[ShoppingAssistant]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services and the dashboard card once for the domain."""
    async_setup_services(hass)
    await async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ShoppingAssistantConfigEntry) -> bool:
    """Set up Shopping Assistant from a config entry."""
    settings = Settings.from_options(dict(entry.options))
    integration = await async_get_integration(hass, DOMAIN)

    db = ProductDatabase(hass)
    if await db.async_load():
        _LOGGER.info("Imported %d products from EAN Reader", len(db.products))

    client = OpenFoodFactsClient(
        hass,
        app_version=str(integration.version),
        contact_email=settings.contact_email,
        app_uuid=entry.data.get(DATA_APP_UUID, ""),
        test_mode=settings.off_test_mode,
    )
    assistant = ShoppingAssistant(
        hass=hass,
        entry=entry,
        settings=settings,
        db=db,
        client=client,
        shopping=ShoppingList(hass, db, settings.shopping_list_entity),
    )
    entry.runtime_data = assistant

    _async_update_issue(
        hass, "legacy_integration", bool(hass.config_entries.async_entries(LEGACY_DOMAIN))
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _handle_share(event: Event) -> None:
        ean = extract_ean(event.data.get("text")) or extract_ean(event.data.get("url"))
        if ean is None:
            _LOGGER.debug("Shared content has no valid barcode: %s", event.data)
            return
        entry.async_create_background_task(
            hass, assistant.async_process_scan(ean, origin="share"), f"{DOMAIN} scan {ean}"
        )

    entry.async_on_unload(hass.bus.async_listen(SHARE_EVENT, _handle_share))
    entry.async_on_unload(assistant.shopping.async_start())
    if settings.enable_webhook:
        async_setup_webhook(hass, entry)
    return True


@callback
def _async_update_issue(hass: HomeAssistant, issue_id: str, active: bool) -> None:
    """Create or clear a repair issue."""
    if active:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=issue_id,
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_unload_entry(hass: HomeAssistant, entry: ShoppingAssistantConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.async_shutdown()
    return unload_ok
