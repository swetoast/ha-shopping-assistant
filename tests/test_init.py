"""Integration tests for setup, scanning, services and the webhook."""
from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.shopping_assistant.api import OFFRateLimitError
from custom_components.shopping_assistant.const import (
    CONF_AUTO_ADD_TO_SHOPPING_LIST,
    CONF_ENABLE_WEBHOOK,
    DATA_WEBHOOK_ID,
    DOMAIN,
    EVENT_PRODUCT_SCANNED,
    SHARE_EVENT,
    STORAGE_KEY,
)

from .conftest import KNOWN_EAN, UNKNOWN_EAN, make_entry

NUTELLA = "Ferrero - Nutella hasselnotskram (400 g)"


async def _list(hass: HomeAssistant) -> list[dict]:
    result = await hass.services.async_call(
        DOMAIN, "get_shopping_list", {}, blocking=True, return_response=True
    )
    return result["items"]


async def _call(hass: HomeAssistant, service: str, data: dict) -> dict | None:
    response = service not in ("remove_from_shopping_list", "name_product")
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=response
    )


async def _share(hass: HomeAssistant, text: str) -> None:
    hass.bus.async_fire(SHARE_EVENT, {"text": text})
    await hass.async_block_till_done()


async def test_scan_adds_to_own_list(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, off_lookup: AsyncMock
) -> None:
    """A shared barcode is looked up once and listed once, without any to-do list."""
    scanned = async_capture_events(hass, EVENT_PRODUCT_SCANNED)

    await _share(hass, KNOWN_EAN)
    await _share(hass, KNOWN_EAN)  # repeated share within seconds is ignored

    assert off_lookup.call_count == 1
    assert [e.data["source"] for e in scanned] == ["openfoodfacts"]
    [item] = await _list(hass)
    assert item["name"] == NUTELLA
    assert item["ean"] == KNOWN_EAN
    assert item["net_quantity"] == "400 g"
    assert item["nutrition_grades"] == "e"
    assert "quantity" not in item
    assert hass.states.get("sensor.shopping_assistant_shopping_list").state == "1"
    assert "todo" not in hass.config.components

    # Scanning again raises the count; an explicit quantity replaces it.
    response = await _call(hass, "add_scanned_to_shopping_list", {"ean": KNOWN_EAN})
    assert response["source"] == "local"
    assert response["item"]["quantity"] == "2"
    await _call(hass, "add_scanned_to_shopping_list", {"ean": KNOWN_EAN, "quantity": "500 g"})
    assert [i["quantity"] for i in await _list(hass)] == ["500 g"]
    assert off_lookup.call_count == 1

    attrs = hass.states.get("sensor.shopping_assistant_statistics").attributes
    assert attrs["total_scans"] == 3
    assert attrs["local_hits"] == 2

    await _call(hass, "remove_from_shopping_list", {"ean": KNOWN_EAN})
    assert await _list(hass) == []


async def test_free_text_items(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_storage
) -> None:
    """Things without a barcode can be listed, edited and removed, and are stored."""
    item = await _call(hass, "add_to_shopping_list", {"name": "Bananas", "note": "Ripe"})
    assert item["name"] == "Bananas"
    again = await _call(hass, "add_to_shopping_list", {"name": "bananas"})
    assert again["id"] == item["id"]
    assert again["quantity"] == "2"

    edited = await _call(
        hass, "update_shopping_list_item", {"item": item["id"], "quantity": "6", "note": ""}
    )
    assert edited["quantity"] == "6"
    assert "note" not in edited
    state = hass.states.get("sensor.shopping_assistant_shopping_list")
    assert state.state == "1"
    assert state.attributes["items"][0]["quantity"] == "6"

    await hass.config_entries.async_unload(loaded_entry.entry_id)
    assert hass_storage[STORAGE_KEY]["data"]["shopping_list"][0]["name"] == "Bananas"
    assert await hass.config_entries.async_setup(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert [i["id"] for i in await _list(hass)] == [item["id"]]

    with pytest.raises(ServiceValidationError):
        await _call(hass, "remove_from_shopping_list", {"item": "missing"})
    assert await _call(hass, "clear_shopping_list", {}) == {"removed": 1}
    assert await _list(hass) == []


async def test_reset_database(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, freezer
) -> None:
    """Reset removes old data only when asked, and everything when asked to."""
    await _share(hass, KNOWN_EAN)  # on the list
    await _share(hass, UNKNOWN_EAN)
    await _call(hass, "name_product", {"ean": "036000291452", "name": "Tea"})
    freezer.tick(timedelta(days=40))
    await _call(hass, "add_to_shopping_list", {"name": "Bananas"})

    with pytest.raises(ServiceValidationError):
        await _call(hass, "reset_database", {"confirm": False})

    removed = await _call(
        hass,
        "reset_database",
        {"confirm": True, "sections": ["products", "unknowns"], "older_than_days": 30},
    )
    assert removed == {"products": 1, "unknowns": 1}
    db = loaded_entry.runtime_data.db
    assert set(db.products) == {KNOWN_EAN}  # kept: still on the list

    removed = await _call(hass, "reset_database", {"confirm": True, "older_than_days": 30})
    assert removed == {"shopping_list": 1, "products": 1, "unknowns": 0}
    assert [i["name"] for i in await _list(hass)] == ["Bananas"]
    assert db.statistics["total_scans"] == 2

    removed = await _call(hass, "reset_database", {"confirm": True})
    assert removed == {"shopping_list": 1, "products": 0, "unknowns": 0, "statistics": True}
    assert not db.products and not db.shopping.items
    assert hass.states.get("sensor.shopping_assistant_statistics").state == "0"


async def test_unknown_then_naming_keeps_data(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Unknown barcodes are cached; naming them or a known product keeps its data."""
    await _share(hass, UNKNOWN_EAN)
    assert hass.states.get("sensor.shopping_assistant_unknown_products").state == "1"

    await hass.services.async_call(
        DOMAIN, "name_last_unknown", {"name": "Store milk"}, blocking=True
    )
    assert hass.states.get("sensor.shopping_assistant_unknown_products").state == "0"
    assert [i["name"] for i in await _list(hass)] == ["Store milk"]

    await _share(hass, KNOWN_EAN)
    await hass.services.async_call(
        DOMAIN, "name_product", {"ean": KNOWN_EAN, "name": "My Nutella"}, blocking=True
    )
    product = loaded_entry.runtime_data.db.get(KNOWN_EAN)
    assert product.product_name == "My Nutella"
    assert product.fat == 30.9
    assert loaded_entry.runtime_data.shopping.find(ean=KNOWN_EAN)
    assert product.source == "openfoodfacts+manual"


async def test_api_problem_and_service_responses(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, off_lookup: AsyncMock
) -> None:
    """The problem sensor follows the latest request; data services return responses."""
    off_lookup.side_effect = OFFRateLimitError("HTTP 503")
    response = await hass.services.async_call(
        DOMAIN, "lookup_product", {"ean": KNOWN_EAN}, blocking=True, return_response=True
    )
    assert response["source"] == "rate_limited"
    assert hass.states.get("binary_sensor.shopping_assistant_api_problem").state == "on"
    assert not loaded_entry.runtime_data.db.unknowns  # throttling is not "missing"

    off_lookup.side_effect = None
    off_lookup.return_value = None
    response = await hass.services.async_call(
        DOMAIN, "lookup_product", {"ean": UNKNOWN_EAN}, blocking=True, return_response=True
    )
    assert response == {"ean": UNKNOWN_EAN, "found": False, "source": "missing", "product": None}
    assert hass.states.get("binary_sensor.shopping_assistant_api_problem").state == "off"

    await hass.services.async_call(
        DOMAIN, "name_product", {"ean": "036000291452", "name": "Tea"}, blocking=True
    )
    export = await hass.services.async_call(
        DOMAIN, "export_data", {}, blocking=True, return_response=True
    )
    assert set(export["products"]) == {"0036000291452"}

    result = await hass.services.async_call(
        DOMAIN,
        "import_data",
        {"data": {"products": {KNOWN_EAN: {"product_name": "Imported"}}}, "merge": False},
        blocking=True,
        return_response=True,
    )
    assert result == {"imported_count": 1}
    assert set(loaded_entry.runtime_data.db.products) == {KNOWN_EAN}


async def test_webhook_is_stable_and_returns_json(
    hass: HomeAssistant, off_lookup: AsyncMock, hass_client_no_auth
) -> None:
    """The webhook keeps its id across reloads and answers with JSON."""
    entry = make_entry(**{CONF_ENABLE_WEBHOOK: True, CONF_AUTO_ADD_TO_SHOPPING_LIST: False})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    webhook_id = entry.data[DATA_WEBHOOK_ID]

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data[DATA_WEBHOOK_ID] == webhook_id

    client = await hass_client_no_auth()
    resp = await client.post(f"/api/webhook/{webhook_id}", json={"barcode": KNOWN_EAN})
    assert resp.status == HTTPStatus.OK
    body = await resp.json()
    assert body["status"] == "ok"
    assert body["name"] == NUTELLA
    assert body["added_to_shopping_list"] is False

    resp = await client.get(f"/api/webhook/{webhook_id}?code=2026-10-08")
    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_card_is_installed_and_loaded(
    hass: HomeAssistant,
    frontend_urls: set[str],
    off_lookup: AsyncMock,
    hass_client_no_auth,
    config_dir: Path,
) -> None:
    """Without a www folder the card is copied there and served from the integration."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    installed = config_dir / "www" / "shopping-assistant" / "shopping-assistant-card.js"
    assert "shopping-assistant-card" in installed.read_text()
    assert frontend_urls == {"/shopping_assistant/shopping-assistant-card.js?v=1.0.0"}
    client = await hass_client_no_auth()
    resp = await client.get("/shopping_assistant/shopping-assistant-card.js")
    assert resp.status == HTTPStatus.OK
    assert await resp.text() == installed.read_text()


async def test_card_loads_from_www(
    hass: HomeAssistant,
    frontend_urls: set[str],
    off_lookup: AsyncMock,
    config_dir: Path,
) -> None:
    """With a www folder the card loads from /local and an old copy is replaced."""
    installed = config_dir / "www" / "shopping-assistant" / "shopping-assistant-card.js"
    installed.parent.mkdir(parents=True)
    installed.write_text("old")
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert frontend_urls == {"/local/shopping-assistant/shopping-assistant-card.js?v=1.0.0"}
    assert "shopping-assistant-card" in installed.read_text()
