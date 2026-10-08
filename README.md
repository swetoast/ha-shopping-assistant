# Shopping Assistant for Home Assistant

Scan a barcode, get the product from [OpenFoodFacts](https://world.openfoodfacts.org/), and have it land on your shopping list.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

## What it does

- Takes barcodes shared from your phone or sent by a hardware scanner.
- Looks products up in OpenFoodFacts: name, brand, quantity, nutrition, Nutri-Score, Green-Score, NOVA group, allergens, and whether a product is vegan, vegetarian or palm oil free.
- Keeps its own shopping list of scanned products and anything else you type in, with quantities and notes. No to-do list or other integration is needed.
- Stores every product it has seen, so repeat scans need no lookup. You can name products OpenFoodFacts does not know, edit any product and send your additions to OpenFoodFacts.
- Optionally tracks prices and expiry dates.
- Comes with a dashboard card for scanning, the list, product details and naming unknown barcodes.

## Requirements

- Home Assistant 2025.12.2 or newer.
- A contact email address. OpenFoodFacts asks every app for one.

Please also fill in the [OpenFoodFacts API usage form](https://docs.google.com/forms/d/e/1FAIpQLSdIE3D8qvjC_zRJw1W8OmuHhsWJ_NSckiiniAHlfaVwUZCziQ/viewform) and read their [terms of use](https://world.openfoodfacts.org/terms-of-use).

## Installation

**HACS:** add `https://github.com/swetoast/ha-shopping-assistant` as a custom repository of type Integration, install **Shopping Assistant** and restart Home Assistant.

**Manual:** copy `custom_components/shopping_assistant` into your `config/custom_components/` folder and restart Home Assistant.

Then go to **Settings > Devices & services > Add integration** and choose **Shopping Assistant**.

## Setup

Setup asks for your contact email and whether scanned products should go on the shopping list automatically.

Everything else is under **Configure** on the integration:

| Option | Default | |
| --- | --- | --- |
| Name languages | `sv, en, de, fr, es` | Two-letter codes, in order of preference, for product names and categories. |
| Show notifications | on | When a product is added or a barcode is unknown. |
| Price tracking | off | Enables the `add_price` action. |
| Expiry tracking | off | Enables the `set_expiry` action and the Expiring soon sensor. |
| Webhook for barcode scanners | off | Its address is shown at the top of the options dialog. |
| Only accept webhook calls from the local network | on | Turn off to accept calls through Home Assistant Cloud or your external URL. |
| Allow submitting to OpenFoodFacts | off | Needs your OpenFoodFacts username and password. |
| Use the OpenFoodFacts test server | off | Contributions go to openfoodfacts.net and never reach the real database. |

## Scanning

**From your phone:** scan with any barcode app, tap Share and pick Home Assistant.

**From a scanner or script:** turn on the webhook and send the barcode to its address.

The [barcode scanning guide](BARCODE_SCANNING_GUIDE.md) covers both, with examples for USB scanners, a Raspberry Pi and an ESP32.

Only real barcodes count. A shared link, date or phone number is ignored. If the same barcode arrives twice within a few seconds, which many scanners do, it is handled once.

Products you have scanned before come from the local list. Everything else is looked up in OpenFoodFacts. A barcode OpenFoodFacts does not know is not looked up again for 24 hours, and you get a notification so you can name it:

```yaml
action: shopping_assistant.name_last_unknown
data:
  name: "Store brand milk 1 l"
```

## Dashboard card

The card comes with the integration. On every start Shopping Assistant copies it to `config/www/shopping-assistant/shopping-assistant-card.js` and adds it to all dashboards, so there is no resource to add. Home Assistant only serves the `www` folder if it existed when Home Assistant started, so on a system without one the card loads from the integration folder until the next restart.

Add it from the card picker (search for Shopping Assistant) or with:

```yaml
type: custom:shopping-assistant-card
```

It has three tabs:

- **List:** what to buy, with quantity buttons, Nutri-Score, NOVA and expiry badges, filters, sorting and an estimated total. Tick a product or swipe it left when it is in the basket; the notification lets you undo.
- **To name:** barcodes OpenFoodFacts did not know, each with a field for its name.
- **Expiring:** products expiring within a week, when expiry tracking is on.

Type or scan a barcode at the top, or type anything else, like "bananas", to put it on the list as it is. If a barcode is unknown you can name it right there. Tap a product for scores, nutrition with low, medium and high levels, vitamins and minerals, ingredients and allergens, price history and expiry. From there you can also edit it and send your changes to OpenFoodFacts.

The camera scanner needs a browser with barcode detection, such as Chrome and the Home Assistant app on Android. Elsewhere the scan button is hidden and you can type the barcode. In the scanner you can turn on the torch and keep scanning to add several products in a row.

Options, all available in the visual editor:

| Option | Default | |
| --- | --- | --- |
| `title` | `Shopping` | Card title. |
| `entity` | found automatically | The shopping list sensor, if you have more than one. |
| `scan_action` | `add` | `add` puts scanned products on the list, `lookup` only shows them. |
| `show_scanner` | `true` | Camera scan button. |
| `show_filters` | `true` | Filters, search and sorting. |
| `show_totals` | `true` | Estimated total from recorded prices. |
| `show_stats` | `true` | Scan statistics at the bottom. |
| `style` | `auto` | `home` uses the `--home-*` tokens of the Home cards: their font, type scale, panels and radii. `default` follows your Home Assistant theme. `auto` picks `home` when those tokens or Home cards are on the dashboard. |
| `surface` | `auto` | `flat` drops the card background so the card sits on the page like the Home cards. `card` keeps it. `auto` is flat with the Home style. |
| `icon` | `mdi:cart-outline` | Header icon. Empty for none, which is the default with the Home style. |
| `accent` | theme colour | Any CSS colour for buttons, tabs and highlights. |

Both styles take their colours from your theme, so they work in light and dark mode. The Home style also reads `--home-accent`, `--home-panel`, `--home-press`, `--home-line`, `--home-radius` and `--home-radius-lg` when your theme sets them.

The copy in `www` is overwritten whenever it differs from the card that comes with the integration, so changes made there do not last. If you added the card as a dashboard resource before, remove that resource.

## Shopping list

Shopping Assistant keeps the list itself, stored with your products in `.storage/shopping_assistant`. It does not use the Shopping List integration or any to-do list.

An item is either a scanned product or plain text. Adding something that is already listed raises its count by one, so scanning two cartons of milk gives you milk times two. Products are matched by barcode and plain text by name. Each item has an id, a name, and optionally a quantity, a note and the barcode of its product.

```yaml
action: shopping_assistant.add_to_shopping_list
data:
  name: Bananas
  quantity: "6"
  note: Ripe ones
```

Actions that change an item take its `item` id (from `get_shopping_list` or the sensor) or, for a product, its `ean`.

## Entities

| Entity | State |
| --- | --- |
| `sensor.shopping_assistant_shopping_list` | Items on the list. The `items` attribute has each item with the details of its product. The product's own size is `net_quantity`, so `quantity` is always how many to buy. |
| `sensor.shopping_assistant_statistics` | Total scans, with hit counts and the last scan as attributes. |
| `sensor.shopping_assistant_unknown_products` | Barcodes OpenFoodFacts did not know. |
| `sensor.shopping_assistant_expiring_soon` | Products expiring within 7 days. Only with expiry tracking. |
| `binary_sensor.shopping_assistant_api_problem` | On while OpenFoodFacts cannot be reached or is limiting requests. |

Nutrition values are per 100 g or 100 ml, as given by `nutrition_per`. `carbon_footprint` is kg CO2e per kg of product.

## Actions

Barcodes can be typed with spaces or dashes. Actions marked with a response return data you can use with `response_variable` in scripts.

**Products**

| Action | |
| --- | --- |
| `name_product` | Give a barcode a name. Other details are kept. |
| `name_last_unknown` | Name the last barcode OpenFoodFacts did not know. |
| `update_product` | Add or change details, including nutrition. Response. |
| `remove_product` | Delete a barcode and everything stored for it. |
| `lookup_product` | Look a barcode up without counting a scan. Use `force_refresh: true` to fetch it from OpenFoodFacts again. Response. |
| `list_unknowns` | Return the unknown barcodes. Response. |

**Shopping list**

| Action | |
| --- | --- |
| `add_scanned_to_shopping_list` | Handle a barcode like a scan and add it to the list, with an optional `quantity`. Response. |
| `add_to_shopping_list` | Add something without a barcode, with an optional `quantity` and `note`. Response. |
| `update_shopping_list_item` | Change the name, quantity or note of an item. An empty value clears the quantity or note. Response. |
| `remove_from_shopping_list` | Take an item off the list. |
| `clear_shopping_list` | Empty the list. Response. |
| `get_shopping_list` | Return the list with product details. Response. |

**Prices, expiry and backups**

| Action | |
| --- | --- |
| `add_price` | Record a price. The currency defaults to your Home Assistant currency. |
| `set_expiry` | Set an expiry date. |
| `export_data` | Return everything stored as a backup. Response. |
| `import_data` | Restore a backup. By default only products that are not stored yet are added; `merge: false` replaces all products and the shopping list. Response. |
| `reset_database` | Remove stored data. Response. See [Starting over](#starting-over). |

All actions are in the `shopping_assistant` domain, for example `shopping_assistant.name_product`.

## Events

| Event | Fired when |
| --- | --- |
| `shopping_assistant_product_scanned` | A barcode is scanned. Data: `ean`, `name`, `source`, `origin`. |
| `shopping_assistant_missing_product` | OpenFoodFacts does not know a barcode. Data: `ean`, `seen_count`. |
| `shopping_assistant_lookup_completed` | An OpenFoodFacts lookup finished. Data: `ean`, `found`, `name`. |
| `shopping_assistant_product_saved` | A product is named or edited. |
| `shopping_assistant_product_removed` | A product is deleted. |
| `shopping_assistant_import_complete` | A backup was imported. |
| `shopping_assistant_off_submitted` | A contribution to OpenFoodFacts finished. Data includes `ok`. |

`source` is `local`, `openfoodfacts`, `cached_missing`, `missing`, `rate_limited` or `error`. `origin` is `share`, `webhook` or `service`.

Get a phone notification for unknown products:

```yaml
triggers:
  - trigger: event
    event_type: shopping_assistant_missing_product
actions:
  - action: notify.mobile_app_phone
    data:
      title: Unknown product
      message: "Barcode {{ trigger.event.data.ean }} needs a name"
```

## Contributing to OpenFoodFacts

Turn on **Allow submitting to OpenFoodFacts**, enter your OpenFoodFacts account in the options, and try it with the test server first. Then add details and submit:

```yaml
action: shopping_assistant.update_product
data:
  ean: "7340083438684"
  name: "Havredryck"
  brands: "Store brand"
  quantity: "1 l"
  categories: "Oat drinks"
  energy_kcal: 46
  fat: 1.5
  submit_to_openfoodfacts: true
```

Only what you entered yourself is sent, in your first name language. Notes stay in Home Assistant. Photos can be uploaded with `upload_image_to_openfoodfacts` from a folder listed in `allowlist_external_dirs`.

The actions also accept `username` and `password`, but those show up in automation traces, so keeping the account in the options is safer.

## Troubleshooting

- **Nothing happens when sharing:** share the barcode as text. Enable debug logging for `custom_components.shopping_assistant` to see what arrived.
- **Scanned products are not added to the list:** check that adding scanned products is on in the options. Barcodes OpenFoodFacts does not know are added once you name them.
- **API problem sensor is on:** the `last_error` attribute says why. It turns off after the next successful lookup.

## Data, privacy and limits

Everything is stored in one file, `.storage/shopping_assistant`, which is part of your Home Assistant backups. OpenFoodFacts receives the barcode and your contact email, plus the details you submit if you contribute. Diagnostics hide your email, account and webhook address.

OpenFoodFacts allows 15 lookups per minute per address. Shopping Assistant stays at 12 and makes extra scans wait instead of failing.

### Starting over

`reset_database` removes stored data. `confirm: true` is required. Without other fields it removes products, unknown barcodes, the shopping list and statistics.

Clear out products and unknown barcodes that have not been scanned for a year, keeping everything on the shopping list:

```yaml
action: shopping_assistant.reset_database
data:
  confirm: true
  sections: [products, unknowns]
  older_than_days: 365
```

`sections` can be any of `products`, `unknowns`, `shopping_list` and `statistics`. With `older_than_days`, statistics are left alone. Products removed this way are looked up in OpenFoodFacts again the next time they are scanned.

## License

Shopping Assistant is MIT licensed, see [LICENSE](LICENSE). It is not affiliated with OpenFoodFacts.

OpenFoodFacts data is under the [Open Database License](https://opendatacommons.org/licenses/odbl/1.0/), its contents under the [Database Contents License](https://opendatacommons.org/licenses/dbcl/1.0/) and images under [CC BY-SA](https://creativecommons.org/licenses/by-sa/3.0/deed.en). If you publish product data, credit OpenFoodFacts and link to https://openfoodfacts.org. Product data is entered by volunteers and can be wrong, so check the package for allergens. You can support the project by [donating](https://world.openfoodfacts.org/donate) or adding products.
