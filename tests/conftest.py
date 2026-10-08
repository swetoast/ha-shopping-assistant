"""Shared fixtures for Shopping Assistant tests."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.shopping_assistant.const import (
    CONF_CONTACT_EMAIL,
    CONF_ENABLE_WEBHOOK,
    DATA_APP_UUID,
    DEFAULT_OPTIONS,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"

KNOWN_EAN = "3017620422003"
UNKNOWN_EAN = "7340083438684"

KNOWN_PRODUCT: dict[str, Any] = {
    "code": KNOWN_EAN,
    "product_name": "Nutella",
    "product_name_sv": "Nutella hasselnotskram",
    "brands": "Ferrero, Nutella",
    "quantity": "400 g",
    "nutrition": {
        "aggregated_set": {
            "preparation": "as_sold",
            "per": "100g",
            "nutrients": {
                "energy-kcal": {"value": 539, "unit": "kcal"},
                "fat": {"value": "30.9", "unit": "g"},
                "sugars": {"value": 56.3, "unit": "g"},
            },
        }
    },
    "categories_tags_sv": ["Spreads", "Cocoa spreads"],
    "ingredients_analysis_tags": ["en:palm-oil", "en:non-vegan", "en:vegetarian"],
    "labels_tags": ["en:green-dot"],
    "nova_group": 4,
    "environmental_score_grade": "d",
    "environmental_score_data": {"agribalyse": {"co2_total": 5.2}},
    "nutrition_grades": "e",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


@pytest.fixture(autouse=True)
def config_dir(hass: HomeAssistant, tmp_path) -> Any:
    """Give every test its own config folder, so the card copy lands there."""
    hass.config.config_dir = str(tmp_path)
    return tmp_path


@pytest.fixture
def frontend_urls(hass: HomeAssistant) -> Generator[set[str]]:
    """Pretend the frontend is loaded and capture the extra module URLs."""
    hass.config.components.add("frontend")
    urls: set[str] = set()
    with patch(
        "custom_components.shopping_assistant.card.add_extra_js_url",
        side_effect=lambda hass, url: urls.add(url),
    ):
        yield urls


@pytest.fixture
def off_lookup() -> Generator[AsyncMock]:
    """Fake OpenFoodFacts that only knows KNOWN_EAN."""

    async def _get(client: Any, ean: str, languages: Any) -> dict[str, Any] | None:
        return dict(KNOWN_PRODUCT) if ean == KNOWN_EAN else None

    with patch(
        "custom_components.shopping_assistant.api.OpenFoodFactsClient.async_get_product",
        autospec=True,
        side_effect=_get,
    ) as mock:
        yield mock


def make_entry(**options: Any) -> MockConfigEntry:
    """Return an Shopping Assistant config entry with the given option overrides."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Shopping Assistant",
        version=1,
        data={DATA_APP_UUID: "0" * 32},
        options={
            **DEFAULT_OPTIONS,
            CONF_CONTACT_EMAIL: "toast@example.org",
            CONF_ENABLE_WEBHOOK: False,
            **options,
        },
    )


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, off_lookup: AsyncMock
) -> MockConfigEntry:
    """Set up Shopping Assistant with default options."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
