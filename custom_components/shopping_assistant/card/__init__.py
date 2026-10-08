"""Serve the Shopping Assistant dashboard card and load it in the frontend."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from ..const import DOMAIN

CARD_FILENAME = "shopping-assistant-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card and add it to every dashboard.

    The version query string makes browsers fetch the new file after an update.
    """
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / CARD_FILENAME), True)]
    )
    if "frontend" in hass.config.components:
        add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
