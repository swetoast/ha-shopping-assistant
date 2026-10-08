# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-10-08

Requires Home Assistant 2025.12.2 or newer.

### Renamed
- EAN Reader is now **Shopping Assistant** (domain `shopping_assistant`, repository `ha-shopping-assistant`). Entities, actions and events start with `shopping_assistant` instead of `ean_reader`.
- On first start, products, unknown barcodes, prices, expiry dates and statistics are imported from EAN Reader, and the setup form is pre-filled with its options. A repair notice asks you to remove the old EAN Reader entry.
- The User-Agent is now `HomeAssistant-ShoppingAssistant/<version> (email)`.

### Dashboard card
- The card is now part of the integration as `custom:shopping-assistant-card` and loads automatically; no dashboard resource needed.
- New layout: scan or type at the top with inline naming of unknown barcodes, tabs for the list, barcodes to name and expiring products, and a product sheet with scores, nutrition levels, vitamins and minerals in mg or micrograms, ingredients, price history, expiry and editing.
- Continuous scanning with torch, swipe to remove with undo, filters, search, sorting, estimated total and a visual editor.
- Fixed: editing called a non-existent action, "Remove from list" deleted the product from the database, the card subscribed to every event on the bus, micronutrient units were wrong, the add button floated over the whole dashboard, and reordering was lost on the next update.
- The shopping list sensor now also has `image_small_url` and `added_to_list_at` per product.

### Fixed
- Options dialog crashed on current Home Assistant (the options flow assigned `config_entry`).
- Saving options added another share listener and update listener each time, so scans were processed several times and two database copies overwrote each other.
- The webhook always answered HTTP 500 because the handler returned a dict.
- The webhook id changed on every restart; it is now created once and kept.
- `add_mapping` replaced an existing product with a bare entry, losing OpenFoodFacts data and shopping list state.
- Any shared text with 8 to 14 digits in total (dates, phone numbers, links) was treated as a barcode. Barcodes now need a valid GS1 check digit.
- Vegan, vegetarian and palm oil analysis was parsed with substring matching, so "palm oil free" read as "contains palm oil" and "status unknown" as "yes".
- A stored product with an unexpected key was reduced to its name on load.
- Storage in the older `mappings` layout loaded as empty and was then overwritten.
- Translations were missing for custom integrations, so forms showed raw keys.
- The API problem sensor stayed on forever after a single error.
- A product found in OpenFoodFacts without a name produced no event or notification.
- Scan statistics skipped unknown scans, counted `lookup_product` calls as scans and never increased per-product scan counts.
- Products created by price or expiry tracking were added to the shopping list as "Unknown Product".
- HTTP 429 was not treated as rate limiting; the rate limit logged a warning on most requests.
- `import_mappings` with `merge: false` did not replace existing products, and the documented example used the wrong key.

### Added
- Products are added to a selectable to-do entity, duplicates are skipped and ticked-off items are removed from the EAN Reader list.
- `lookup_product` accepts `force_refresh`. OpenFoodFacts data older than 30 days is refreshed in the background on scan.
- Action responses for `lookup_product`, `add_scanned_to_shopping_list`, `import_mappings`, `update_product` and the OpenFoodFacts actions.
- Expiring soon sensor when expiry tracking is on.
- Webhook accepts JSON, form data, query string or plain text, shows its URL in the options dialog and can be limited to the local network.
- Repeated scans of the same barcode within 3 seconds are ignored.
- Diagnostics download with sensitive values redacted.
- Action and entity icons, `add_price` `store` field, `traces` and other editable fields on `submit_to_openfoodfacts`.
- Foundation tests and CI with hassfest, HACS validation and pytest.

### Changed
- All OpenFoodFacts requests use API v3.6: product reads (`GET /api/v3.6/product/<code>`), writes (`PATCH`, JSON body) and image uploads (`POST .../images`). Nutrition is read from the aggregated nutrition set and written as a v3 nutrition input set; taxonomy fields are read as translated tags.
- The `openfoodfacts` Python package was replaced by a small async client on Home Assistant's HTTP session, so the integration installs no requirements.
- Submissions send only the details entered in Home Assistant, in the first name language; `include_nutrition` was replaced by nutrient fields on `update_product` and `submit_to_openfoodfacts`.
- `carbon_footprint` is now kg CO2e per kg from Agribalyse; new `nutrition_per` and `nutrition_preparation` attributes.
- `list_unknowns`, `export_mappings` and `get_shopping_list` return an action response instead of firing an event (large events were dropped by the recorder).
- Removed the `ean_reader_stats_updated` event; entities update internally.
- Removed the unused Show product images option.
- `ingredients_analysis_palm_oil` is now `ingredients_analysis_palm_oil_free`.
- 12-digit UPC-A codes are stored as 13-digit EAN, matching OpenFoodFacts.
- Storage is written at most every 10 seconds instead of twice per scan.
- Write requests include `app_name`, `app_version` and `app_uuid`.
- The setup step requires a real contact email.

## [1.0.1] - 2026-05-22

### Added
- **Shopping List Sensor**: New `sensor.ean_reader_shopping_list` that exposes shopping list items with full product data
- **Comprehensive Product Fields**: Added 43 new API fields from OpenFoodFacts (95+ total fields)
  - Serving information (serving_size, serving_quantity)
  - Detailed fats (monounsaturated, polyunsaturated, trans fat, cholesterol, omega-3, omega-6)
  - Complete vitamin profile (A, C, D, E, K, B1, B2, B6, B9, B12)
  - Complete mineral profile (calcium, iron, magnesium, phosphorus, potassium, zinc)
  - Special content (alcohol, caffeine)
  - Packaging & sustainability (packaging, recycling instructions, carbon footprint)
  - Ingredients analysis (vegan, vegetarian, palm oil detection)
  - Additional metadata (generic_name, labels, additives)

### Changed
- Shopping list data now accessible via dedicated sensor with `products` attribute array
- Product database now stores 95+ fields per product (up from 52)
- Enhanced product data extraction from OpenFoodFacts API

### Fixed
- Shopping list sensor properly updates when items added/removed
- Card reactivity fixed with proper LitElement state updates
- Binary sensor (API Problem) now properly updates with event listeners

## [1.0.0] - 2025-01-XX

### Added
- Initial release of EAN Reader integration
- OpenFoodFacts API integration using official openfoodfacts-python library
- Barcode scanning via mobile_app.share events
- Local product database with manual mappings
- Shopping list auto-add functionality
- Two sensor entities: statistics and unknown products
- **Binary diagnostic sensor**: API health monitoring (error tracking, rate limit detection)
- Rate limiting (12 req/min) to comply with OpenFoodFacts API limits
- Configurable contact email for User-Agent compliance
- Multi-language product name support (sv, en, de, fr, es)
- Optional price tracking feature
- Optional expiry date tracking feature
- Optional webhook support for external scanners
- Config flow with options for all features
- 10 services for product management
- 9 events for automation triggers
- Comprehensive error handling and logging
- HTTP 503 rate limit detection
- 24-hour caching of unknown products
- Export/import functionality for backups

### Services
- `add_mapping` - Add or update EAN to product name mapping
- `add_last_missing_mapping` - Map the last unknown scanned EAN
- `remove_mapping` - Remove an EAN from the database
- `lookup_product` - Force a lookup in OpenFoodFacts
- `add_scanned_to_shopping_list` - Add scanned EAN to shopping list
- `list_unknowns` - List all unknown products
- `export_mappings` - Export database to JSON
- `import_mappings` - Import mappings from JSON
- `add_price` - Add price tracking entry
- `set_expiry` - Set expiry date for product

### Events
- `ean_reader_product_scanned` - Fired on every scan
- `ean_reader_lookup_completed` - Fired after API lookup
- `ean_reader_missing_product` - Fired when product not found
- `ean_reader_mapping_added` - Fired when mapping created
- `ean_reader_mapping_removed` - Fired when mapping deleted
- `ean_reader_stats_updated` - Fired when statistics change
- `ean_reader_unknowns_list` - Response from list_unknowns service
- `ean_reader_export_complete` - Response from export_mappings service
- `ean_reader_import_complete` - Response from import_mappings service

### Technical
- Synchronous openfoodfacts library wrapped in executor jobs
- Conservative rate limiting to prevent IP bans
- Proper User-Agent format: `HomeAssistant-EANReader/1.0.0 (email)`
- Storage migration support from older versions
- Robust error handling for network issues
- Input sanitization for security
- Field selection for efficient API calls

### Documentation
- Comprehensive README with OpenFoodFacts legal requirements
- CONTRIBUTING.md with development guidelines
- LICENSE file with third-party license information
- GitHub issue templates for bugs and feature requests
- Pull request template
- HACS integration support

### Requirements
- Home Assistant 2024.1.0+
- openfoodfacts>=0.2.0 library
- Shopping List integration (optional)
