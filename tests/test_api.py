"""Tests for the OpenFoodFacts v3.6 client against the documented contract."""
from __future__ import annotations

from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.shopping_assistant.api import (
    PRODUCTION_URL,
    STAGING_URL,
    Credentials,
    OFFAuthError,
    OFFError,
    OFFRateLimitError,
    OpenFoodFactsClient,
)
from custom_components.shopping_assistant.const import (
    CONF_ENABLE_OFF_SUBMISSION,
    CONF_OFF_PASSWORD,
    CONF_OFF_USERNAME,
    DOMAIN,
)

from .conftest import KNOWN_EAN, KNOWN_PRODUCT, UNKNOWN_EAN, make_entry

PRODUCT_URL = f"{PRODUCTION_URL}/api/v3.6/product/{KNOWN_EAN}"
CREDENTIALS = Credentials("toast", "secret")


def _client(hass: HomeAssistant, test_mode: bool = False) -> OpenFoodFactsClient:
    return OpenFoodFactsClient(
        hass,
        app_version="1.0.0",
        contact_email="toast@example.org",
        app_uuid="abc",
        test_mode=test_mode,
    )


async def test_read_product(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Reads use /api/v3.6 with unescaped field commas and a contact User-Agent."""
    aioclient_mock.get(
        PRODUCT_URL,
        json={"status": "success", "result": {"id": "product_found"}, "product": KNOWN_PRODUCT},
    )
    aioclient_mock.get(
        f"{PRODUCTION_URL}/api/v3.6/product/{UNKNOWN_EAN}",
        status=HTTPStatus.NOT_FOUND,
        json={"status": "failure", "result": {"id": "product_not_found"}},
    )
    client = _client(hass)

    assert await client.async_get_product(KNOWN_EAN, ["sv", "en"]) == KNOWN_PRODUCT
    assert await client.async_get_product(UNKNOWN_EAN, ["sv"]) is None

    _, url, _, headers = aioclient_mock.mock_calls[0]
    fields = url.query["fields"].split(",")
    assert {"nutrition", "product_name_sv", "categories_tags_sv"} <= set(fields)
    assert "fields=code,product_name," in url.raw_query_string
    assert headers["User-Agent"] == "HomeAssistant-ShoppingAssistant/1.0.0 (toast@example.org)"


async def test_read_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Throttling and server errors raise; they are never treated as not found."""
    aioclient_mock.get(PRODUCT_URL, status=HTTPStatus.SERVICE_UNAVAILABLE, text="busy")
    with pytest.raises(OFFRateLimitError):
        await _client(hass).async_get_product(KNOWN_EAN, ["sv"])

    aioclient_mock.clear_requests()
    aioclient_mock.get(PRODUCT_URL, status=HTTPStatus.INTERNAL_SERVER_ERROR, text="<html>")
    with pytest.raises(OFFError):
        await _client(hass).async_get_product(KNOWN_EAN, ["sv"])


async def test_write_product(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Writes PATCH JSON with credentials; bad logins raise OFFAuthError."""
    staging_url = f"{STAGING_URL}/api/v3.6/product/{KNOWN_EAN}"
    aioclient_mock.patch(
        staging_url,
        json={"status": "success", "result": {"id": "product_updated"}},
    )
    payload = await _client(hass, test_mode=True).async_write_product(
        KNOWN_EAN, {"product_name_sv": "X"}, tags_lc="sv", credentials=CREDENTIALS
    )
    assert payload["result"]["id"] == "product_updated"
    method, url, body, _ = aioclient_mock.mock_calls[0]
    assert method.upper() == "PATCH"
    assert url.query["app_name"] == "HomeAssistant-ShoppingAssistant"
    assert body["user_id"] == "toast"
    assert body["tags_lc"] == "sv"
    assert body["product"] == {"product_name_sv": "X"}

    aioclient_mock.clear_requests()
    aioclient_mock.patch(
        PRODUCT_URL,
        status=HTTPStatus.FORBIDDEN,
        json={
            "status": "failure",
            "errors": [{"message": {"id": "invalid_user_id_and_password"}}],
        },
    )
    with pytest.raises(OFFAuthError):
        await _client(hass).async_write_product(
            KNOWN_EAN, {"quantity": "1 l"}, tags_lc="sv", credentials=CREDENTIALS
        )


async def test_submit_service(
    hass: HomeAssistant,
    off_lookup: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """update_product submits only the entered details, marking new products' language."""
    entry: MockConfigEntry = make_entry(
        **{
            CONF_ENABLE_OFF_SUBMISSION: True,
            CONF_OFF_USERNAME: "toast",
            CONF_OFF_PASSWORD: "secret",
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    unknown_url = f"{PRODUCTION_URL}/api/v3.6/product/{UNKNOWN_EAN}"
    aioclient_mock.get(
        unknown_url,
        status=HTTPStatus.NOT_FOUND,
        json={"status": "failure", "result": {"id": "product_not_found"}},
    )
    aioclient_mock.patch(
        unknown_url,
        json={"status": "success_with_warnings", "result": {"id": "product_updated"}},
    )
    response = await hass.services.async_call(
        DOMAIN,
        "update_product",
        {
            "ean": UNKNOWN_EAN,
            "name": "Havredryck",
            "quantity": "1 l",
            "fat": 1.5,
            "notes": "private",
            "submit_to_openfoodfacts": True,
        },
        blocking=True,
        return_response=True,
    )
    submission = response["submission"]
    assert submission["ok"] is True
    assert submission["submitted_fields"] == ["nutrition", "product_name_sv", "quantity"]

    _, _, body, _ = aioclient_mock.mock_calls[-1]
    assert body["product"]["lang"] == "sv"
    assert body["product"]["product_name_sv"] == "Havredryck"
    assert "notes" not in body["product"]
    assert body["password"] == "secret"

    # A product with nothing entered locally has nothing to submit.
    await hass.services.async_call(
        DOMAIN, "lookup_product", {"ean": KNOWN_EAN}, blocking=True
    )
    with pytest.raises(HomeAssistantError, match="Nothing to submit"):
        await hass.services.async_call(
            DOMAIN, "submit_to_openfoodfacts", {"ean": KNOWN_EAN}, blocking=True
        )
