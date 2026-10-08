"""Shopping Assistant integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import OpenFoodFactsClient
from .const import (
    DATA_APP_UUID,
    DOMAIN,
    PLATFORMS,
    SHARE_EVENT,
)
from .ean import extract_ean
from .card import async_register_card
from .product_database import ProductDatabase
from .runtime import Settings, ShoppingAssistant
from .scanner_webhook import async_setup_webhook
from .services import async_setup_services

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
    await db.async_load()

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
    )
    entry.runtime_data = assistant

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
    if settings.enable_webhook:
        async_setup_webhook(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ShoppingAssistantConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.async_shutdown()
    return unload_ok
