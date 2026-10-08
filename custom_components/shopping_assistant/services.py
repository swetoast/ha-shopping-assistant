"""Service actions for Shopping Assistant."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import re
from typing import Any

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import IMAGE_FIELDS, clean_text
from .const import DOMAIN, EVENT_IMPORT_COMPLETE, EVENT_MAPPING_ADDED, EVENT_MAPPING_REMOVED
from .ean import parse_ean
from .product_database import EDITABLE_NUTRIENTS, ProductData
from .runtime import ShoppingAssistant

ATTR_EAN = "ean"
ATTR_NAME = "name"
ATTR_ADD_TO_LIST = "add_to_shopping_list"
ATTR_QUANTITY = "quantity"
ATTR_USERNAME = "username"
ATTR_PASSWORD = "password"

# Service field -> ProductData attribute for editable product details.
EDIT_FIELDS: dict[str, str] = {
    "name": "product_name",
    "brands": "brands",
    "quantity": "quantity",
    "categories": "categories",
    "ingredients_text": "ingredients_text",
    "allergens": "allergens",
    "traces": "traces",
    "labels": "labels",
    "stores": "stores",
    "origins": "origins",
    "packaging": "packaging",
    "notes": "notes",
}
# Nutrient fields use the ProductData attribute name (values per 100 g/ml).
EDIT_FIELDS |= {name: name for name in sorted(EDITABLE_NUTRIENTS)}


def _ean(value: Any) -> str:
    try:
        return parse_ean(value)
    except ValueError as err:
        raise vol.Invalid(str(err)) from err


def _required_text(value: Any) -> str:
    if not (text := clean_text(cv.string(value))):
        raise vol.Invalid("must not be empty")
    return text


EAN = vol.All(cv.string, _ean)
NAME = vol.All(cv.string, _required_text)

EDIT_SCHEMA: dict[Any, Any] = (
    {
        vol.Optional(key): cv.string
        for key in EDIT_FIELDS
        if key != "labels" and key not in EDITABLE_NUTRIENTS
    }
    | {vol.Optional("labels"): vol.Any(cv.string, [cv.string])}
    | {
        vol.Optional(key): vol.All(vol.Coerce(float), vol.Range(min=0))
        for key in EDITABLE_NUTRIENTS
    }
)

CREDENTIALS_SCHEMA: dict[Any, Any] = {
    vol.Optional(ATTR_USERNAME): cv.string,
    vol.Optional(ATTR_PASSWORD): cv.string,
}

EMPTY_SCHEMA = vol.Schema({})


def _assistant(hass: HomeAssistant) -> ShoppingAssistant:
    if not (entries := hass.config_entries.async_loaded_entries(DOMAIN)):
        raise ServiceValidationError("Shopping Assistant is not loaded")
    return entries[0].runtime_data


def _editable_values(data: dict[str, Any]) -> dict[str, Any]:
    """Map service fields to product attributes, dropping empty values."""
    values: dict[str, Any] = {}
    for key, attr in EDIT_FIELDS.items():
        if (value := data.get(key)) is None:
            continue
        if attr in EDITABLE_NUTRIENTS:
            values[attr] = value
            continue
        if attr == "labels":
            items = value.split(",") if isinstance(value, str) else value
            value = [text for item in items if (text := clean_text(str(item)))]
        else:
            value = clean_text(value)
        if value:
            values[attr] = value
    return values


@callback
def _save_details(assistant: ShoppingAssistant, ean: str, values: dict[str, Any]) -> ProductData:
    """Apply edits, dismiss the missing notification and fire mapping_added."""
    product = assistant.db.update_fields(ean, values)
    if product.is_named:
        assistant.dismiss_missing(ean)
    assistant.hass.bus.async_fire(
        EVENT_MAPPING_ADDED,
        {"ean": ean, "name": product.product_name, "source": product.source},
    )
    return product


def _require_named(product: ProductData) -> ProductData:
    if not product.is_named:
        raise ServiceValidationError(f"{product.ean} has no product name yet")
    return product


async def _add_mapping(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    product = _save_details(
        assistant, call.data[ATTR_EAN], {"product_name": call.data[ATTR_NAME]}
    )
    if call.data[ATTR_ADD_TO_LIST]:
        await assistant.shopping.async_add(product)


async def _add_last_missing_mapping(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    if not (ean := assistant.db.last_missing_ean):
        raise ServiceValidationError("No unknown barcode has been scanned")
    product = _save_details(assistant, ean, {"product_name": call.data[ATTR_NAME]})
    if call.data[ATTR_ADD_TO_LIST]:
        await assistant.shopping.async_add(product)


async def _remove_mapping(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    ean = call.data[ATTR_EAN]
    if not assistant.db.delete(ean):
        raise ServiceValidationError(f"{ean} is not in the Shopping Assistant database")
    assistant.dismiss_missing(ean)
    call.hass.bus.async_fire(EVENT_MAPPING_REMOVED, {"ean": ean})


async def _lookup_product(call: ServiceCall) -> ServiceResponse:
    assistant = _assistant(call.hass)
    ean = call.data[ATTR_EAN]
    product, source = await assistant.async_lookup(
        ean, force_refresh=call.data["force_refresh"]
    )
    return {
        "ean": ean,
        "found": product is not None,
        "source": source,
        "product": product.to_dict() if product else None,
    }


async def _add_scanned_to_shopping_list(call: ServiceCall) -> ServiceResponse:
    return await _assistant(call.hass).async_process_scan(
        call.data[ATTR_EAN],
        origin="service",
        add_to_list=True,
        quantity=call.data.get(ATTR_QUANTITY),
    )


async def _list_unknowns(call: ServiceCall) -> ServiceResponse:
    db = _assistant(call.hass).db
    unknowns = sorted(db.unknowns.values(), key=lambda u: u.seen_count, reverse=True)
    return {
        "unknowns": [u.to_dict() for u in unknowns],
        "count": len(unknowns),
        "last_missing_ean": db.last_missing_ean,
    }


async def _export_mappings(call: ServiceCall) -> ServiceResponse:
    return _assistant(call.hass).db.export()


async def _import_mappings(call: ServiceCall) -> ServiceResponse:
    try:
        count = _assistant(call.hass).db.import_data(call.data["data"], call.data["merge"])
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err
    call.hass.bus.async_fire(EVENT_IMPORT_COMPLETE, {"imported_count": count})
    return {"imported_count": count}


async def _add_price(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    if not assistant.settings.track_prices:
        raise ServiceValidationError("Price tracking is disabled in the Shopping Assistant options")
    assistant.db.add_price(
        call.data[ATTR_EAN],
        call.data["price"],
        call.data.get("currency") or call.hass.config.currency,
        call.data.get("store"),
    )


async def _set_expiry(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    if not assistant.settings.track_expiry:
        raise ServiceValidationError("Expiry tracking is disabled in the Shopping Assistant options")
    assistant.db.set_expiry(call.data[ATTR_EAN], call.data["expiry_date"])


async def _remove_from_shopping_list(call: ServiceCall) -> None:
    await _assistant(call.hass).shopping.async_remove([call.data[ATTR_EAN]])


async def _update_shopping_list_quantity(call: ServiceCall) -> None:
    ean = call.data[ATTR_EAN]
    if not _assistant(call.hass).db.set_shopping_list_quantity(ean, call.data[ATTR_QUANTITY]):
        raise ServiceValidationError(f"{ean} is not on the shopping list")


async def _clear_shopping_list(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    await assistant.shopping.async_remove([p.ean for p in assistant.db.shopping_list()])


async def _get_shopping_list(call: ServiceCall) -> ServiceResponse:
    items = _assistant(call.hass).db.shopping_list()
    return {"items": [p.to_dict() for p in items], "count": len(items)}


async def _update_product(call: ServiceCall) -> ServiceResponse:
    assistant = _assistant(call.hass)
    ean = call.data[ATTR_EAN]
    if values := _editable_values(call.data):
        product = _save_details(assistant, ean, values)
    elif (product := assistant.db.get(ean)) is None:
        raise ServiceValidationError("Give at least one product detail to save")
    response: dict[str, Any] = {"product": product.to_dict()}
    if call.data[ATTR_ADD_TO_LIST]:
        await assistant.shopping.async_add(_require_named(product))
    if call.data["submit_to_openfoodfacts"]:
        response["submission"] = await assistant.async_submit(
            ean,
            username=call.data.get(ATTR_USERNAME),
            password=call.data.get(ATTR_PASSWORD),
        )
    return response


async def _submit_to_openfoodfacts(call: ServiceCall) -> ServiceResponse:
    assistant = _assistant(call.hass)
    ean = call.data[ATTR_EAN]
    if values := _editable_values(call.data):
        _save_details(assistant, ean, values)
    return await assistant.async_submit(
        ean,
        username=call.data.get(ATTR_USERNAME),
        password=call.data.get(ATTR_PASSWORD),
    )


async def _upload_image_to_openfoodfacts(call: ServiceCall) -> ServiceResponse:
    return await _assistant(call.hass).async_upload_image(
        call.data[ATTR_EAN],
        call.data["image_path"],
        image_field=call.data.get("image_field"),
        language=call.data["language"],
        username=call.data.get(ATTR_USERNAME),
        password=call.data.get(ATTR_PASSWORD),
    )


type _Handler = Callable[[ServiceCall], Awaitable[ServiceResponse | None]]

SERVICES: dict[str, tuple[_Handler, vol.Schema, SupportsResponse]] = {
    "add_mapping": (
        _add_mapping,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                vol.Required(ATTR_NAME): NAME,
                vol.Optional(ATTR_ADD_TO_LIST, default=False): cv.boolean,
            }
        ),
        SupportsResponse.NONE,
    ),
    "add_last_missing_mapping": (
        _add_last_missing_mapping,
        vol.Schema(
            {
                vol.Required(ATTR_NAME): NAME,
                vol.Optional(ATTR_ADD_TO_LIST, default=True): cv.boolean,
            }
        ),
        SupportsResponse.NONE,
    ),
    "remove_mapping": (
        _remove_mapping,
        vol.Schema({vol.Required(ATTR_EAN): EAN}),
        SupportsResponse.NONE,
    ),
    "lookup_product": (
        _lookup_product,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                vol.Optional("force_refresh", default=False): cv.boolean,
            }
        ),
        SupportsResponse.OPTIONAL,
    ),
    "add_scanned_to_shopping_list": (
        _add_scanned_to_shopping_list,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                vol.Optional(ATTR_QUANTITY): cv.string,
            }
        ),
        SupportsResponse.OPTIONAL,
    ),
    "list_unknowns": (_list_unknowns, EMPTY_SCHEMA, SupportsResponse.ONLY),
    "export_mappings": (_export_mappings, EMPTY_SCHEMA, SupportsResponse.ONLY),
    "import_mappings": (
        _import_mappings,
        vol.Schema(
            {
                vol.Required("data"): dict,
                vol.Optional("merge", default=True): cv.boolean,
            }
        ),
        SupportsResponse.OPTIONAL,
    ),
    "add_price": (
        _add_price,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                vol.Required("price"): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Optional("currency"): vol.All(cv.string, vol.Upper, vol.Length(3, 3)),
                vol.Optional("store"): cv.string,
            }
        ),
        SupportsResponse.NONE,
    ),
    "set_expiry": (
        _set_expiry,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                vol.Required("expiry_date"): cv.date,
            }
        ),
        SupportsResponse.NONE,
    ),
    "remove_from_shopping_list": (
        _remove_from_shopping_list,
        vol.Schema({vol.Required(ATTR_EAN): EAN}),
        SupportsResponse.NONE,
    ),
    "update_shopping_list_quantity": (
        _update_shopping_list_quantity,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                vol.Required(ATTR_QUANTITY): cv.string,
            }
        ),
        SupportsResponse.NONE,
    ),
    "clear_shopping_list": (_clear_shopping_list, EMPTY_SCHEMA, SupportsResponse.NONE),
    "get_shopping_list": (_get_shopping_list, EMPTY_SCHEMA, SupportsResponse.ONLY),
    "update_product": (
        _update_product,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                **EDIT_SCHEMA,
                vol.Optional(ATTR_ADD_TO_LIST, default=False): cv.boolean,
                vol.Optional("submit_to_openfoodfacts", default=False): cv.boolean,
                **CREDENTIALS_SCHEMA,
            }
        ),
        SupportsResponse.OPTIONAL,
    ),
    "submit_to_openfoodfacts": (
        _submit_to_openfoodfacts,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                **EDIT_SCHEMA,
                **CREDENTIALS_SCHEMA,
            }
        ),
        SupportsResponse.OPTIONAL,
    ),
    "upload_image_to_openfoodfacts": (
        _upload_image_to_openfoodfacts,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                vol.Required("image_path"): cv.string,
                vol.Optional("image_field"): vol.In(IMAGE_FIELDS),
                vol.Optional("language", default="en"): vol.All(
                    cv.string, vol.Lower, vol.Match(re.compile(r"^[a-z]{2}$"))
                ),
                **CREDENTIALS_SCHEMA,
            }
        ),
        SupportsResponse.OPTIONAL,
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register all service actions."""
    for name, (handler, schema, supports_response) in SERVICES.items():
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=supports_response
        )
