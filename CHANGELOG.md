# Changelog

## 1.0.0

First release. Requires Home Assistant 2025.12.2 or newer.

- Barcodes from phone sharing or a webhook are looked up in OpenFoodFacts (API v3.6) and stored locally.
- A shopping list of its own, for scanned products and plain text, with quantities and notes.
- Dashboard card with scanning, the list, product details, naming of unknown barcodes and editing. It installs itself to `www/shopping-assistant/` and matches either the Home cards or the Home Assistant theme.
- Price and expiry tracking, with an Expiring soon sensor.
- Contributions to OpenFoodFacts: product details, nutrition and photos, with a test server option.
- Backup, restore and reset of the stored data.
