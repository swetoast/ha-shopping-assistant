# Contributing to Shopping Assistant

Bug reports and pull requests are welcome. For larger changes, open an issue first so we can agree on the approach.

## Development setup

Requires Python 3.13.

```bash
git clone https://github.com/YOUR_USERNAME/ha-shopping-assistant.git
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

The tests in `tests/` cover barcode parsing, OpenFoodFacts parsing, storage migration, the scan flow, services, the webhook and the config flow. OpenFoodFacts is mocked; never call the real API from tests.

## Code layout

| File | Purpose |
| --- | --- |
| `__init__.py` | Entry setup, share event listener, entry migration |
| `runtime.py` | Runtime object: settings, lookup, scan handling, notifications, contributions |
| `api.py` | OpenFoodFacts API v3.6 client (aiohttp), rate limiters, response parsing, submission payload |
| `product_database.py` | Product model, storage and storage migration |
| `shopping.py` | To-do list sync |
| `services.py` | Service actions and their schemas |
| `scanner_webhook.py` | Webhook handler |
| `ean.py` | Barcode validation and normalization |
| `config_flow.py` | Setup and options |
| `card/` | Dashboard card (`shopping-assistant-card.js`, plain JavaScript, no build step) and the code that serves it |

## OpenFoodFacts rules

- The API version is pinned (`API_VERSION` in `api.py`) because every v3.x changes the product schema. Read the [schema change log](https://openfoodfacts.github.io/openfoodfacts-server/api/ref-api-and-product-schema-change-log/) before bumping it and update the parser and tests together.
- Check request and response formats against the [v3 reference](https://openfoodfacts.github.io/openfoodfacts-server/api/ref-v3/) and the server's `tests/integration/api_v3_*.t` files.
- Keep the User-Agent format `AppName/Version (email)`.
- Stay under the read limit of 15 requests per minute per IP. The integration uses 12.
- Never store a throttled (HTTP 429 or 503) or failed lookup as an unknown product.
- Send `app_name`, `app_version` and `app_uuid` with write requests.
- Test contributions against the test server (`off_test_mode`).

## Style

- Plain ASCII in source files.
- Type hints and docstrings on public functions and classes.
- User-facing strings for config, entities and services live in `translations/en.json`.

## Commit messages

Use conventional commits, for example `fix(webhook): return JSON responses` or `feat(services): add force_refresh to lookup_product`.

## License

Contributions are licensed under the MIT License.
