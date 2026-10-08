"""Service actions for Shopping Assistant."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
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
from homeassistant.util import dt as dt_util

from .api import IMAGE_FIELDS, clean_text
from .const import DOMAIN, EVENT_IMPORT_COMPLETE, EVENT_PRODUCT_SAVED, EVENT_PRODUCT_REMOVED
from .ean import parse_ean
from .product_database import EDITABLE_NUTRIENTS, ProductData
from .runtime import ShoppingAssistant
from .shopping import UPDATABLE_FIELDS, ListItem

ATTR_EAN = "ean"
ATTR_NAME = "name"
ATTR_ADD_TO_LIST = "add_to_shopping_list"
ATTR_QUANTITY = "quantity"
ATTR_ITEM = "item"
ATTR_NOTE = "note"
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

RESET_SECTIONS = ("products", "unknowns", "shopping_list", "statistics")

# Picks a list item by its id or by the barcode of its product.
ITEM_SCHEMA: dict[Any, Any] = {
    vol.Exclusive(ATTR_ITEM, "item"): cv.string,
    vol.Exclusive(ATTR_EAN, "item"): EAN,
}


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
    """Apply edits, dismiss the missing notification and fire product_saved."""
    product = assistant.db.update_fields(ean, values)
    if product.is_named:
        assistant.dismiss_missing(ean)
    assistant.hass.bus.async_fire(
        EVENT_PRODUCT_SAVED,
        {"ean": ean, "name": product.product_name, "source": product.source},
    )
    return product


@callback
def _list_product(assistant: ShoppingAssistant, product: ProductData) -> ListItem:
    """Put a named product on the shopping list."""
    if not product.is_named:
        raise ServiceValidationError(f"{product.ean} has no product name yet")
    return assistant.shopping.add(product.product_name, ean=product.ean)


def _item(assistant: ShoppingAssistant, data: dict[str, Any]) -> ListItem:
    """Return the list item a service call points at."""
    if ATTR_ITEM not in data and ATTR_EAN not in data:
        raise ServiceValidationError("Give the item id or the barcode of a listed product")
    item = assistant.shopping.find(item_id=data.get(ATTR_ITEM), ean=data.get(ATTR_EAN))
    if item is None:
        raise ServiceValidationError(
            f"{data.get(ATTR_ITEM) or data.get(ATTR_EAN)} is not on the shopping list"
        )
    return item


async def _name_product(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    product = _save_details(
        assistant, call.data[ATTR_EAN], {"product_name": call.data[ATTR_NAME]}
    )
    if call.data[ATTR_ADD_TO_LIST]:
        _list_product(assistant, product)


async def _name_last_unknown(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    if not (ean := assistant.db.last_missing_ean):
        raise ServiceValidationError("No unknown barcode has been scanned")
    product = _save_details(assistant, ean, {"product_name": call.data[ATTR_NAME]})
    if call.data[ATTR_ADD_TO_LIST]:
        _list_product(assistant, product)


async def _remove_product(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    ean = call.data[ATTR_EAN]
    if not assistant.db.delete(ean):
        raise ServiceValidationError(f"{ean} is not in the Shopping Assistant database")
    assistant.dismiss_missing(ean)
    call.hass.bus.async_fire(EVENT_PRODUCT_REMOVED, {"ean": ean})


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


async def _export_data(call: ServiceCall) -> ServiceResponse:
    return _assistant(call.hass).db.export()


async def _import_data(call: ServiceCall) -> ServiceResponse:
    try:
        count = _assistant(call.hass).db.import_data(call.data["data"], call.data["merge"])
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err
    call.hass.bus.async_fire(EVENT_IMPORT_COMPLETE, {"imported_count": count})
    return {"imported_count": count}


async def _reset_database(call: ServiceCall) -> ServiceResponse:
    if not call.data["confirm"]:
        raise ServiceValidationError("Set confirm to true to remove the data")
    before = None
    if days := call.data.get("older_than_days"):
        before = dt_util.utcnow() - timedelta(days=days)
    return _assistant(call.hass).db.reset(set(call.data["sections"]), before)


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


async def _add_to_shopping_list(call: ServiceCall) -> ServiceResponse:
    assistant = _assistant(call.hass)
    item = assistant.shopping.add(
        call.data[ATTR_NAME],
        quantity=call.data.get(ATTR_QUANTITY),
        note=call.data.get(ATTR_NOTE),
    )
    return assistant.describe(item)


async def _update_shopping_list_item(call: ServiceCall) -> ServiceResponse:
    assistant = _assistant(call.hass)
    item = _item(assistant, call.data)
    values = {key: clean_text(call.data[key]) for key in UPDATABLE_FIELDS if key in call.data}
    return assistant.describe(assistant.shopping.update(item, values))


async def _remove_from_shopping_list(call: ServiceCall) -> None:
    assistant = _assistant(call.hass)
    assistant.shopping.remove([_item(assistant, call.data)])


async def _clear_shopping_list(call: ServiceCall) -> ServiceResponse:
    shopping = _assistant(call.hass).shopping
    return {"removed": shopping.remove(list(shopping.items.values()))}


async def _get_shopping_list(call: ServiceCall) -> ServiceResponse:
    assistant = _assistant(call.hass)
    items = [assistant.describe(item) for item in assistant.shopping.items.values()]
    return {"items": items, "count": len(items)}


async def _update_product(call: ServiceCall) -> ServiceResponse:
    assistant = _assistant(call.hass)
    ean = call.data[ATTR_EAN]
    if values := _editable_values(call.data):
        product = _save_details(assistant, ean, values)
    elif (product := assistant.db.get(ean)) is None:
        raise ServiceValidationError("Give at least one product detail to save")
    response: dict[str, Any] = {"product": product.to_dict()}
    if call.data[ATTR_ADD_TO_LIST]:
        _list_product(assistant, product)
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
    "name_product": (
        _name_product,
        vol.Schema(
            {
                vol.Required(ATTR_EAN): EAN,
                vol.Required(ATTR_NAME): NAME,
                vol.Optional(ATTR_ADD_TO_LIST, default=False): cv.boolean,
            }
        ),
        SupportsResponse.NONE,
    ),
    "name_last_unknown": (
        _name_last_unknown,
        vol.Schema(
            {
                vol.Required(ATTR_NAME): NAME,
                vol.Optional(ATTR_ADD_TO_LIST, default=True): cv.boolean,
            }
        ),
        SupportsResponse.NONE,
    ),
    "remove_product": (
        _remove_product,
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
    "export_data": (_export_data, EMPTY_SCHEMA, SupportsResponse.ONLY),
    "import_data": (
        _import_data,
        vol.Schema(
            {
                vol.Required("data"): dict,
                vol.Optional("merge", default=True): cv.boolean,
            }
        ),
        SupportsResponse.OPTIONAL,
    ),
    "reset_database": (
        _reset_database,
        vol.Schema(
            {
                vol.Required("confirm"): cv.boolean,
                vol.Optional("sections", default=list(RESET_SECTIONS)): vol.All(
                    cv.ensure_list, [vol.In(RESET_SECTIONS)]
                ),
                vol.Optional("older_than_days"): vol.All(vol.Coerce(int), vol.Range(min=1)),
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
    "add_to_shopping_list": (
        _add_to_shopping_list,
        vol.Schema(
            {
                vol.Required(ATTR_NAME): NAME,
                vol.Optional(ATTR_QUANTITY): cv.string,
                vol.Optional(ATTR_NOTE): cv.string,
            }
        ),
        SupportsResponse.OPTIONAL,
    ),
    "update_shopping_list_item": (
        _update_shopping_list_item,
        vol.Schema(
            {
                **ITEM_SCHEMA,
                vol.Optional(ATTR_NAME): cv.string,
                vol.Optional(ATTR_QUANTITY): cv.string,
                vol.Optional(ATTR_NOTE): cv.string,
            }
        ),
        SupportsResponse.OPTIONAL,
    ),
    "remove_from_shopping_list": (
        _remove_from_shopping_list,
        vol.Schema(ITEM_SCHEMA),
        SupportsResponse.NONE,
    ),
    "clear_shopping_list": (_clear_shopping_list, EMPTY_SCHEMA, SupportsResponse.OPTIONAL),
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
