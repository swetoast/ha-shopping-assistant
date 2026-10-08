"""Tests for barcode handling, OpenFoodFacts parsing and the storage format."""
from __future__ import annotations

import pytest

from custom_components.shopping_assistant.api import (
    build_submission,
    display_name,
    parse_product,
)
from custom_components.shopping_assistant.ean import extract_ean, gtin_checksum_valid, parse_ean
from custom_components.shopping_assistant import storage
from custom_components.shopping_assistant.product_database import ProductData
from custom_components.shopping_assistant.shopping import ListItem

from .conftest import KNOWN_EAN, KNOWN_PRODUCT


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (KNOWN_EAN, KNOWN_EAN),
        (f"https://world.openfoodfacts.org/product/{KNOWN_EAN}/nutella", KNOWN_EAN),
        ("036000291452", "0036000291452"),  # UPC-A becomes EAN-13
        ("96385074", "96385074"),  # EAN-8
        ("Meeting 2026-10-08 16:19", None),
        ("https://example.com/news/2026/10/08/12345", None),
        ("Call 070-123 45 67", None),
        ("3017620422004", None),  # wrong check digit
        ("123456789", None),  # not a GTIN length
    ],
)
def test_extract_ean(text: str, expected: str | None) -> None:
    """Only real, check-digit valid barcodes are found in shared text."""
    assert extract_ean(text) == expected


def test_parse_ean_for_services() -> None:
    """Typed barcodes accept separators and any 8-14 digit code."""
    assert parse_ean("301 7620-422003") == KNOWN_EAN
    assert parse_ean("1234567890") == "1234567890"
    assert gtin_checksum_valid("00036000291452")
    with pytest.raises(ValueError):
        parse_ean("12345")


def test_parse_product() -> None:
    """OpenFoodFacts data is mapped with exact ingredient-analysis tags."""
    product = parse_product(KNOWN_EAN, KNOWN_PRODUCT, ["sv", "en"])
    assert product is not None
    assert product.product_name == "Ferrero - Nutella hasselnotskram (400 g)"
    assert product.localized_names == {"sv": "Nutella hasselnotskram"}
    assert product.fat == 30.9
    assert product.energy_kcal == 539
    assert product.nutrition_per == "100g"
    assert product.categories == "Spreads, Cocoa spreads"
    assert product.carbon_footprint == 5.2
    assert product.nova_group == 4
    assert product.eco_score_grade == "d"
    assert product.ingredients_analysis_palm_oil_free == "no"
    assert product.ingredients_analysis_vegan == "no"
    assert product.ingredients_analysis_vegetarian == "yes"

    unknown = parse_product(
        KNOWN_EAN,
        {
            "product_name": "X",
            "ingredients_analysis_tags": [
                "en:palm-oil-free",
                "en:vegan-status-unknown",
                "en:maybe-vegetarian",
            ],
        },
        [],
    )
    assert unknown is not None
    assert unknown.ingredients_analysis_palm_oil_free == "yes"
    assert unknown.ingredients_analysis_vegan == "maybe"
    assert unknown.ingredients_analysis_vegetarian == "maybe"
    assert display_name({"brands": "Arla"}, ["sv"]) is None


def test_build_submission() -> None:
    """Only edited fields are sent, in the v3 write format."""
    product = ProductData(
        ean=KNOWN_EAN,
        product_name="Havredryck",
        source="manual",
        brands="Not edited",
        quantity="1 l",
        categories="Oat drinks, Plant milks",
        labels=["en:organic"],
        fat=1.5,
        notes="private",
        edited_fields=["product_name", "quantity", "categories", "labels", "fat"],
    )
    assert build_submission(product, language="sv", new_product=True) == {
        "product_name_sv": "Havredryck",
        "quantity": "1 l",
        "categories_tags": ["Oat drinks", "Plant milks"],
        "labels_tags": ["en:organic"],
        "nutrition": {
            "input_sets": [
                {
                    "preparation": "as_sold",
                    "per": "100ml",
                    "per_quantity": 100,
                    "per_unit": "ml",
                    "source": "packaging",
                    "source_description": "",
                    "nutrients": {"fat": {"value_string": "1.5", "unit": "g"}},
                }
            ]
        },
        "lang": "sv",
    }
    product.edited_fields = []
    assert build_submission(product, language="sv", new_product=True) == {}


def test_records_keep_unknown_fields() -> None:
    """Fields a newer version added survive loading and saving."""
    raw = {"ean": KNOWN_EAN, "product_name": "Nutella", "fat": 30.9, "future_field": {"a": 1}}
    product = ProductData.from_dict(raw)
    assert product.fat == 30.9
    assert product.extra == {"future_field": {"a": 1}}
    assert {k: v for k, v in product.to_dict().items() if k in raw} == raw

    item = ListItem.from_dict({"name": "Bananas", "aisle": 4})
    assert item.to_dict()["aisle"] == 4
    assert ProductData.from_dict({"ean": KNOWN_EAN}).product_name == "Unknown Product"


def test_migrations_run_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Steps from the stored version onwards run in version order."""
    steps = {
        (1, 2): lambda data: data | {"order": [*data["order"], "1.2"]},
        (1, 1): lambda data: data | {"order": [*data["order"], "1.1"]},
    }
    monkeypatch.setattr(storage, "MIGRATIONS", steps)
    assert storage.migrate({"order": []}, 1, 1)["order"] == ["1.1", "1.2"]
    assert storage.migrate({"order": []}, 1, 2)["order"] == ["1.2"]
