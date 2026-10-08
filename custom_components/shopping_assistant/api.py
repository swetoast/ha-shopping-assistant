"""OpenFoodFacts API v3 client and response parsing."""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
import logging
import re
import time
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import APP_NAME
from .product_database import SOURCE_OFF, ProductData

_LOGGER = logging.getLogger(__name__)

# The API version is pinned because each v3.x changes the product schema.
# v3.6: nutrition in nutrition.aggregated_set, taxonomy fields only as *_tags.
API_VERSION = "v3.6"
PRODUCTION_URL = "https://world.openfoodfacts.org"
STAGING_URL = "https://world.openfoodfacts.net"
STAGING_AUTH = aiohttp.BasicAuth("off", "off")  # staging is behind basic auth

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)
RATE_LIMIT_STATUSES = frozenset({429, 503})
NOT_FOUND_STATUSES = frozenset({400, 404})  # invalid_code / product_not_found
IMAGE_FIELDS = ("front", "ingredients", "nutrition", "packaging")

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_LIQUID_RE = re.compile(r"\d\s*(ml|cl|dl|l)\b", re.IGNORECASE)

PRODUCT_FIELDS: tuple[str, ...] = (
    "code",
    "product_name",
    "generic_name",
    "brands",
    "quantity",
    "ingredients_text",
    "packaging_text",
    "recycling_instructions_to_recycle",
    "serving_size",
    "serving_quantity",
    "nutrition",
    "nutrition_grades",
    "nova_group",
    "environmental_score_grade",
    "environmental_score_data",
    "additives_tags",
    "labels_tags",
    "packaging_tags",
    "ingredients_analysis_tags",
    "ingredients_from_palm_oil_tags",
    "image_url",
    "image_small_url",
    "image_front_url",
    "image_ingredients_url",
    "image_nutrition_url",
    "completeness",
    "last_modified_t",
)

# Taxonomy fields read as display names in the first preferred language
# (v3.6 no longer returns plain text versions of these).
DISPLAY_TAG_FIELDS: tuple[str, ...] = (
    "categories",
    "allergens",
    "traces",
    "origins",
    "manufacturing_places",
    "countries",
    "stores",
)

# Plain text fields: ProductData attribute -> OFF key.
TEXT_FIELDS: dict[str, str] = {
    "brands": "brands",
    "quantity": "quantity",
    "generic_name": "generic_name",
    "ingredients_text": "ingredients_text",
    "serving_size": "serving_size",
    "recycling_instructions": "recycling_instructions_to_recycle",
    "image_url": "image_url",
    "image_small_url": "image_small_url",
    "image_front_url": "image_front_url",
    "image_ingredients_url": "image_ingredients_url",
    "image_nutrition_url": "image_nutrition_url",
}

# ProductData attribute -> nutrient id in the OFF nutrients taxonomy.
NUTRIENT_IDS: dict[str, str] = {
    "energy_kcal": "energy-kcal",
    "energy_kj": "energy-kj",
    "fat": "fat",
    "saturated_fat": "saturated-fat",
    "carbohydrates": "carbohydrates",
    "sugars": "sugars",
    "fiber": "fiber",
    "proteins": "proteins",
    "salt": "salt",
    "sodium": "sodium",
    "monounsaturated_fat": "monounsaturated-fat",
    "polyunsaturated_fat": "polyunsaturated-fat",
    "trans_fat": "trans-fat",
    "cholesterol": "cholesterol",
    "omega_3_fat": "omega-3-fat",
    "omega_6_fat": "omega-6-fat",
    "vitamin_a": "vitamin-a",
    "vitamin_c": "vitamin-c",
    "vitamin_d": "vitamin-d",
    "vitamin_e": "vitamin-e",
    "vitamin_k": "vitamin-k",
    "vitamin_b1": "vitamin-b1",
    "vitamin_b2": "vitamin-b2",
    "vitamin_b6": "vitamin-b6",
    "vitamin_b9": "vitamin-b9",
    "vitamin_b12": "vitamin-b12",
    "calcium": "calcium",
    "iron": "iron",
    "magnesium": "magnesium",
    "phosphorus": "phosphorus",
    "potassium": "potassium",
    "zinc": "zinc",
    "alcohol": "alcohol",
    "caffeine": "caffeine",
}

# ingredients_analysis_tags values. Anything else (status-unknown) is "maybe".
ANALYSIS_TAGS: dict[str, dict[str, str]] = {
    "ingredients_analysis_vegan": {
        "en:vegan": "yes",
        "en:non-vegan": "no",
        "en:maybe-vegan": "maybe",
    },
    "ingredients_analysis_vegetarian": {
        "en:vegetarian": "yes",
        "en:non-vegetarian": "no",
        "en:maybe-vegetarian": "maybe",
    },
    "ingredients_analysis_palm_oil_free": {
        "en:palm-oil-free": "yes",
        "en:palm-oil": "no",
        "en:may-contain-palm-oil": "maybe",
    },
}

# Writing: ProductData attribute -> OFF language field (sent as <field>_<lc>).
SUBMIT_LANGUAGE_FIELDS: dict[str, str] = {
    "product_name": "product_name",
    "ingredients_text": "ingredients_text",
    "packaging": "packaging_text",
}
SUBMIT_TAG_FIELDS = frozenset(
    {"brands", "categories", "labels", "stores", "origins", "allergens", "traces"}
)
# Nutrients that can be entered and submitted: attribute -> (nutrient id, unit).
SUBMIT_NUTRIENTS: dict[str, tuple[str, str]] = {
    "energy_kcal": ("energy-kcal", "kcal"),
    "energy_kj": ("energy-kj", "kJ"),
    "fat": ("fat", "g"),
    "saturated_fat": ("saturated-fat", "g"),
    "carbohydrates": ("carbohydrates", "g"),
    "sugars": ("sugars", "g"),
    "fiber": ("fiber", "g"),
    "proteins": ("proteins", "g"),
    "salt": ("salt", "g"),
    "sodium": ("sodium", "g"),
}


class OFFError(Exception):
    """OpenFoodFacts request failed."""


class OFFRateLimitError(OFFError):
    """OpenFoodFacts is throttling us."""


class OFFAuthError(OFFError):
    """OpenFoodFacts rejected the credentials."""


@dataclass(frozen=True, slots=True)
class Credentials:
    """OpenFoodFacts account (user name, not email)."""

    username: str
    password: str


class RateLimiter:
    """Sliding window limiter shared by every request of one kind."""

    def __init__(self, max_requests: int, window: float) -> None:
        """Initialize."""
        self._max = max_requests
        self._window = window
        self._stamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request may be sent."""
        async with self._lock:
            while True:
                now = time.monotonic()
                while self._stamps and self._stamps[0] <= now - self._window:
                    self._stamps.popleft()
                if len(self._stamps) < self._max:
                    break
                delay = self._stamps[0] + self._window - now
                _LOGGER.debug("OpenFoodFacts rate limit reached, waiting %.1fs", delay)
                await asyncio.sleep(delay)
            self._stamps.append(time.monotonic())


# OFF allows 15 product reads per minute per IP; stay below it. Writes are not
# limited by OFF but are paced anyway. Module level so limits survive reloads.
READ_LIMITER = RateLimiter(12, 60)
WRITE_LIMITER = RateLimiter(30, 60)


def clean_text(value: Any) -> str | None:
    """Strip control characters and collapse whitespace."""
    if not isinstance(value, str):
        return None
    return " ".join(_CONTROL_CHARS_RE.sub("", value).split()) or None


def _as_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return int(number) if number is not None else None


def _as_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _join(values: Any) -> str | None:
    return ", ".join(item for v in _as_list(values) if (item := clean_text(v))) or None


def _split(value: Any) -> list[str]:
    items = value if isinstance(value, list) else str(value).split(",")
    return [text for item in items if (text := clean_text(str(item)))]


def _analysis(tags: list[str], mapping: dict[str, str]) -> str:
    for tag in tags:
        if tag in mapping:
            return mapping[tag]
    return "maybe"


def _dig(data: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def product_fields(languages: Iterable[str]) -> list[str]:
    """Return the fields to request for the given name languages."""
    languages = list(languages)
    fields = [*PRODUCT_FIELDS, *(f"product_name_{lang}" for lang in languages)]
    if languages:
        fields += [f"{tag}_tags_{languages[0]}" for tag in DISPLAY_TAG_FIELDS]
    return fields


def display_name(raw: dict[str, Any], languages: Iterable[str]) -> str | None:
    """Build "Brand - Name (Quantity)" using the preferred languages."""
    candidates = [raw.get(f"product_name_{lang}") for lang in languages]
    candidates += [raw.get("product_name"), raw.get("generic_name")]
    name = next((text for value in candidates if (text := clean_text(value))), None)
    if not name:
        return None
    brand = clean_text((raw.get("brands") or "").split(",")[0])
    quantity = clean_text(raw.get("quantity"))
    if brand and brand.casefold() not in name.casefold():
        name = f"{brand} - {name}"
    if quantity and quantity.casefold() not in name.casefold():
        name = f"{name} ({quantity})"
    return name


def parse_product(
    ean: str, raw: dict[str, Any], languages: Iterable[str]
) -> ProductData | None:
    """Convert a v3.6 product into ProductData, or None if it has no name."""
    languages = list(languages)
    if not (name := display_name(raw, languages)):
        return None

    aggregated = _dig(raw, "nutrition", "aggregated_set") or {}
    nutrients = aggregated.get("nutrients") or {}
    analysis_tags = _as_list(raw.get("ingredients_analysis_tags"))
    display_lc = languages[0] if languages else "en"
    co2_per_kg = _as_float(_dig(raw, "environmental_score_data", "agribalyse", "co2_total"))

    values: dict[str, Any] = {
        attr: clean_text(raw.get(key)) for attr, key in TEXT_FIELDS.items()
    }
    values |= {
        attr: _as_float(_dig(nutrients, nid, "value")) for attr, nid in NUTRIENT_IDS.items()
    }
    values |= {attr: _analysis(analysis_tags, tags) for attr, tags in ANALYSIS_TAGS.items()}
    values |= {tag: _join(raw.get(f"{tag}_tags_{display_lc}")) for tag in DISPLAY_TAG_FIELDS}

    return ProductData(
        ean=ean,
        product_name=name,
        source=SOURCE_OFF,
        localized_names={
            lang: text
            for lang in languages
            if (text := clean_text(raw.get(f"product_name_{lang}")))
        },
        packaging=clean_text(raw.get("packaging_text")),
        nutrition_preparation=clean_text(aggregated.get("preparation")),
        nutrition_per=clean_text(aggregated.get("per")),
        additives=_as_list(raw.get("additives_tags")),
        packaging_tags=_as_list(raw.get("packaging_tags")),
        ingredients_from_palm_oil=_as_list(raw.get("ingredients_from_palm_oil_tags")),
        labels=_as_list(raw.get("labels_tags")),
        nutrition_grades=clean_text(raw.get("nutrition_grades")),
        eco_score_grade=clean_text(raw.get("environmental_score_grade")),
        nova_group=_as_int(raw.get("nova_group")),
        serving_quantity=_as_float(raw.get("serving_quantity")),
        carbon_footprint=co2_per_kg,
        completeness=_as_float(raw.get("completeness")),
        last_modified_t=_as_int(raw.get("last_modified_t")),
        fetched_at=dt_util.utcnow().isoformat(),
        **values,
    )


def _nutrition_per(quantity: str | None) -> tuple[str, str]:
    """Return (per, unit) for nutrition values: 100ml for liquids, else 100g."""
    return ("100ml", "ml") if quantity and _LIQUID_RE.search(quantity) else ("100g", "g")


def build_submission(
    product: ProductData, *, language: str, new_product: bool
) -> dict[str, Any]:
    """Build the v3 "product" object with the fields the user edited."""
    body: dict[str, Any] = {}
    nutrients: dict[str, dict[str, str]] = {}
    for attr in product.edited_fields:
        value = getattr(product, attr, None)
        if value is None or value in ("", []):
            continue
        if attr in SUBMIT_LANGUAGE_FIELDS:
            body[f"{SUBMIT_LANGUAGE_FIELDS[attr]}_{language}"] = value
        elif attr in SUBMIT_TAG_FIELDS:
            body[f"{attr}_tags"] = _split(value)
        elif attr == "quantity":
            body["quantity"] = value
        elif attr in SUBMIT_NUTRIENTS:
            nid, unit = SUBMIT_NUTRIENTS[attr]
            nutrients[nid] = {"value_string": f"{value:g}", "unit": unit}
    if nutrients:
        per, per_unit = _nutrition_per(product.quantity)
        body["nutrition"] = {
            "input_sets": [
                {
                    "preparation": "as_sold",
                    "per": per,
                    "per_quantity": 100,
                    "per_unit": per_unit,
                    "source": "packaging",
                    "source_description": "",
                    "nutrients": nutrients,
                }
            ]
        }
    if body and new_product:
        body["lang"] = language
    return body


def message_ids(payload: dict[str, Any], key: str) -> list[str]:
    return [
        str(_dig(item, "message", "id"))
        for item in payload.get(key) or []
        if _dig(item, "message", "id")
    ]


class OpenFoodFactsClient:
    """Minimal async client for the OpenFoodFacts v3 product API."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        app_version: str,
        contact_email: str,
        app_uuid: str,
        test_mode: bool,
    ) -> None:
        """Initialize."""
        self._session = async_get_clientsession(hass)
        self._test_mode = test_mode
        self.user_agent = f"{APP_NAME}/{app_version} ({contact_email})"
        self._app_params = {
            "app_name": APP_NAME,
            "app_version": app_version,
            "app_uuid": app_uuid,
        }

    def _write_target(self) -> tuple[str, aiohttp.BasicAuth | None]:
        if self._test_mode:
            return STAGING_URL, STAGING_AUTH
        return PRODUCTION_URL, None

    async def _request(
        self,
        method: str,
        url: str,
        limiter: RateLimiter,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        auth: aiohttp.BasicAuth | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Send a request and return (HTTP status, JSON body)."""
        await limiter.acquire()
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json,
                auth=auth,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status in RATE_LIMIT_STATUSES:
                    raise OFFRateLimitError(
                        f"Rate limited by OpenFoodFacts (HTTP {response.status})"
                    )
                try:
                    payload = await response.json(content_type=None)
                except ValueError:
                    payload = None
                status = response.status
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OFFError(f"Cannot reach OpenFoodFacts: {err or type(err).__name__}") from err
        if not isinstance(payload, dict):
            raise OFFError(f"Unexpected response from OpenFoodFacts (HTTP {status})")
        return status, payload

    def _check_write(self, status: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Raise for a failed v3 write, otherwise return the payload."""
        errors = message_ids(payload, "errors")
        if status in (401, 403) and "invalid_user_id_and_password" in errors:
            raise OFFAuthError("OpenFoodFacts rejected the username or password")
        if status >= 400 or payload.get("status") == "failure":
            raise OFFError(
                "OpenFoodFacts rejected the request: "
                + (", ".join(errors) or f"HTTP {status}")
            )
        return payload

    async def async_get_product(
        self, ean: str, languages: Iterable[str]
    ) -> dict[str, Any] | None:
        """Fetch a product; None if OpenFoodFacts does not know it."""
        status, payload = await self._request(
            "GET",
            f"{PRODUCTION_URL}/api/{API_VERSION}/product/{ean}",
            READ_LIMITER,
            params={"fields": ",".join(product_fields(languages))},
        )
        if status in NOT_FOUND_STATUSES:
            return None
        if status >= 400 or payload.get("status") == "failure":
            raise OFFError(
                "OpenFoodFacts lookup failed: "
                + (", ".join(message_ids(payload, "errors")) or f"HTTP {status}")
            )
        product = payload.get("product")
        return product if isinstance(product, dict) and product else None

    async def async_product_exists(self, ean: str) -> bool:
        """Return True if the server that receives writes has the product."""
        base, auth = self._write_target()
        status, _ = await self._request(
            "GET",
            f"{base}/api/{API_VERSION}/product/{ean}",
            READ_LIMITER,
            params={"fields": "code"},
            auth=auth,
        )
        return status < 400

    async def async_write_product(
        self,
        ean: str,
        product: dict[str, Any],
        *,
        tags_lc: str,
        credentials: Credentials,
    ) -> dict[str, Any]:
        """Create or update a product with PATCH /api/v3.6/product/<code>."""
        base, auth = self._write_target()
        status, payload = await self._request(
            "PATCH",
            f"{base}/api/{API_VERSION}/product/{ean}",
            WRITE_LIMITER,
            params=self._app_params,
            json={
                "user_id": credentials.username,
                "password": credentials.password,
                "tags_lc": tags_lc,
                "fields": "updated",
                "comment": f"Edited with {APP_NAME}",
                "product": product,
            },
            auth=auth,
        )
        return self._check_write(status, payload)

    async def async_upload_image(
        self,
        ean: str,
        image_base64: str,
        *,
        credentials: Credentials,
        image_field: str | None,
        language: str,
    ) -> dict[str, Any]:
        """Upload an image with POST /api/v3.6/product/<code>/images."""
        base, auth = self._write_target()
        body: dict[str, Any] = {
            "user_id": credentials.username,
            "password": credentials.password,
            "image_data_base64": image_base64,
        }
        if image_field:
            body["selected"] = {image_field: {language: {}}}
        status, payload = await self._request(
            "POST",
            f"{base}/api/{API_VERSION}/product/{ean}/images",
            WRITE_LIMITER,
            params=self._app_params,
            json=body,
            auth=auth,
        )
        return self._check_write(status, payload)
