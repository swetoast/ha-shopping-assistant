"""Install the Shopping Assistant dashboard card and load it in the frontend."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "shopping-assistant-card.js"
CARD_SOURCE = Path(__file__).parent / CARD_FILENAME
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
WWW_FOLDER = "shopping-assistant"
LOCAL_URL = f"/local/{WWW_FOLDER}/{CARD_FILENAME}"


def _install_card(www: Path) -> bool:
    """Copy the card to www/shopping-assistant when it is missing or outdated.

    Returns whether /local serves it now. The frontend only serves /local when
    the www folder existed when it started, so a folder created here is served
    from the next restart.
    """
    served = www.is_dir()
    target = www / WWW_FOLDER / CARD_FILENAME
    data = CARD_SOURCE.read_bytes()
    if not target.is_file() or target.read_bytes() != data:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return served


async def async_register_card(hass: HomeAssistant) -> None:
    """Install the card in www and add it to every dashboard.

    The card is also served from the integration folder, which is used until
    /local is available. The version query string makes browsers fetch the
    new file after an update.
    """
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_SOURCE), True)]
    )
    www = Path(hass.config.path("www"))
    try:
        served = await hass.async_add_executor_job(_install_card, www)
    except OSError as err:
        _LOGGER.warning("Could not copy the dashboard card to %s: %s", www, err)
        served = False
    if "frontend" in hass.config.components:
        url = LOCAL_URL if served else CARD_URL
        add_extra_js_url(hass, f"{url}?v={integration.version}")
