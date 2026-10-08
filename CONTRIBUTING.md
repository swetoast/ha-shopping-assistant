# Contributing

## Development setup

Requires Python 3.13.

```bash
git clone https://github.com/swetoast/ha-shopping-assistant.git
cd ha-shopping-assistant
python3.13 -m venv .venv
. .venv/bin/activate
pip install -r requirements_test.txt
```

`requirements_test.txt` pins `pytest-homeassistant-custom-component` to the release matching the minimum supported Home Assistant version (2025.12.2).

To try changes in a real instance, link or copy `custom_components/shopping_assistant` into your `config/custom_components/` and restart Home Assistant. Config flow and option changes need a full restart, not a reload.

## Checks

Run these before opening a pull request. CI runs the same checks.

```bash
python -m pyflakes custom_components tests
pytest
```

CI also runs hassfest and the HACS validator.

OpenFoodFacts is mocked in the tests. Never call the real API from tests.

## Code layout

| File | Purpose |
| --- | --- |
| `__init__.py` | Entry setup and the share event listener |
| `runtime.py` | Runtime object: settings, lookup, scan handling, notifications, contributions |
| `api.py` | OpenFoodFacts API v3.6 client (aiohttp), rate limiters, response parsing, submission payload |
| `storage.py` | Storage format, record base class and migrations |
| `product_database.py` | Products, unknown barcodes, statistics, backup, restore and reset |
| `shopping.py` | The shopping list |
| `services.py` | Service actions and their schemas |
| `scanner_webhook.py` | Webhook handler |
| `ean.py` | Barcode validation and normalization |
| `config_flow.py` | Setup and options |
| `card/` | Dashboard card (`shopping-assistant-card.js`, plain JavaScript, no build step) and the code that copies it to `www` and loads it |

## OpenFoodFacts rules

- The API version is pinned (`API_VERSION` in `api.py`) because every v3.x changes the product schema. Read the [schema change log](https://openfoodfacts.github.io/openfoodfacts-server/api/ref-api-and-product-schema-change-log/) before bumping it and update the parser and tests together.
- Check request and response formats against the [v3 reference](https://openfoodfacts.github.io/openfoodfacts-server/api/ref-v3/) and the server's `tests/integration/api_v3_*.t` files.
- Keep the User-Agent format `AppName/Version (email)`.
- Stay under the read limit of 15 requests per minute per IP. The integration uses 12.
- Never store a throttled (HTTP 429 or 503) or failed lookup as an unknown product.
- Send `app_name`, `app_version` and `app_uuid` with write requests.
- Test contributions against the test server (`off_test_mode`).

## Storage

All data is one document in `.storage/shopping_assistant`. `storage.py` describes it.

- New fields need no migration. Add the field with a default to `ProductData`, `UnknownProduct` or `ListItem`. Stored data without it gets the default, and fields an older version does not know are kept.
- A new kind of data gets its own top-level section. Add it to `SECTIONS` in `product_database.py` and to `_apply` and `_data_to_save`.
- Renaming, moving or reshaping stored data needs a step in `MIGRATIONS` in `storage.py`, keyed by the version it upgrades from, and a bump of `STORAGE_MINOR_VERSION` in `const.py`. Bump `STORAGE_VERSION` only when older versions can no longer read the data.
- A new `ListItem` field shows up in the sensor and in `get_shopping_list` by itself. Add it to `UPDATABLE_FIELDS` and the `update_shopping_list_item` schema to make it editable.

## Style

- Plain ASCII in source files.
- Type hints and docstrings on public functions and classes.
- User-facing strings for config, entities and services live in `translations/en.json`.
