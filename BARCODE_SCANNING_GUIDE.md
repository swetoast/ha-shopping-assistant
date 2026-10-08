# Barcode scanning guide

Shopping Assistant accepts barcodes in two ways:

- **Sharing from a phone** to the Home Assistant companion app. Nothing to set up.
- **A webhook** for hardware scanners, scripts and microcontrollers.

Either way the barcode must be a standalone EAN-8, UPC-A (12 digits), EAN-13 or GTIN-14 with a valid check digit. Anything else in the shared text, such as a product name or link, is ignored.

## Sharing from a phone

1. Scan the barcode with any scanner app that can share the result as text.
2. Tap **Share** and pick **Home Assistant**.

The companion app fires a [`mobile_app.share`](https://companion.home-assistant.io/docs/integrations/sharing) event, and Shopping Assistant reads the barcode from its `text` or `url` field. Sharing a product page link such as `https://world.openfoodfacts.org/product/3017620422003` works too.

If nothing happens, enable debug logging and share again:

```yaml
logger:
  logs:
    custom_components.shopping_assistant: debug
```

A log line saying the shared content has no valid barcode shows what the app actually sent.

## Webhook

### Enable it

1. Open **Settings > Devices & services > Shopping Assistant > Configure**.
2. Turn on **Webhook for barcode scanners** and save.
3. Open **Configure** again. The webhook URL is shown at the top of the dialog. A notification with the URL also appears the first time.

The URL stays the same across restarts and option changes. By default only devices on your local network can use it. Turn off **Only accept webhook calls from the local network** to allow calls through Home Assistant Cloud or your external URL.

Anyone who knows the URL can send barcodes, so treat it like a password.

### Request

`POST`, `PUT` or `GET` to `/api/webhook/<id>`. The barcode is read from the first of these keys that is present: `ean`, `barcode`, `code`, `text`.

```bash
# JSON
curl -X POST http://homeassistant.local:8123/api/webhook/<id> \
  -H "Content-Type: application/json" -d '{"ean": "3017620422003"}'

# Form
curl -X POST http://homeassistant.local:8123/api/webhook/<id> -d "ean=3017620422003"

# Query string
curl "http://homeassistant.local:8123/api/webhook/<id>?ean=3017620422003"

# Plain text body
curl -X POST http://homeassistant.local:8123/api/webhook/<id> \
  -H "Content-Type: text/plain" --data "3017620422003"
```

### Response

HTTP 200 with the scan result:

```json
{
  "status": "ok",
  "ean": "3017620422003",
  "name": "Ferrero - Nutella (400 g)",
  "source": "openfoodfacts",
  "added_to_shopping_list": true
}
```

`source` is `local`, `openfoodfacts`, `cached_missing`, `missing`, `rate_limited` or `error`. `name` is `null` when the product is unknown. A barcode sent again within 3 seconds returns `{"status": "ok", "ean": "...", "duplicate": true}` and is not processed twice.

HTTP 400 means no valid barcode was found in the request.

The response is sent after the lookup finishes. When more than 12 lookups have been made in the last minute, it waits for the OpenFoodFacts rate limit, so allow a timeout of at least 60 seconds.

## Scanner examples

### USB scanner on a computer

Most USB scanners type the digits followed by Enter, like a keyboard. This script sends each scanned line:

```python
#!/usr/bin/env python3
"""Send every scanned barcode to Shopping Assistant."""
import requests

WEBHOOK = "http://homeassistant.local:8123/api/webhook/<id>"

while True:
    barcode = input("Scan: ").strip()
    if not barcode:
        continue
    reply = requests.post(WEBHOOK, json={"ean": barcode}, timeout=90)
    print(reply.json() if reply.ok else f"HTTP {reply.status_code}")
```

### USB scanner on a Raspberry Pi without a keyboard session

Reads the scanner directly with [python-evdev](https://python-evdev.readthedocs.io/). Run it as a user with access to `/dev/input`.

```python
#!/usr/bin/env python3
"""Forward scans from a USB barcode scanner to Shopping Assistant."""
import evdev
import requests

WEBHOOK = "http://homeassistant.local:8123/api/webhook/<id>"
DIGITS = {f"KEY_{n}": str(n) for n in range(10)}

scanner = next(
    device
    for device in map(evdev.InputDevice, evdev.list_devices())
    if "barcode" in device.name.lower() or "scanner" in device.name.lower()
)
scanner.grab()  # keep the digits from reaching the console
barcode = ""
for event in scanner.read_loop():
    if event.type != evdev.ecodes.EV_KEY or event.value != 1:  # key down only
        continue
    key = evdev.ecodes.KEY.get(event.code, "")
    if isinstance(key, list):  # some codes have several names
        key = key[0]
    if key == "KEY_ENTER" and barcode:
        requests.post(WEBHOOK, json={"ean": barcode}, timeout=90)
        barcode = ""
    elif key in DIGITS:
        barcode += DIGITS[key]
```

### ESP32 (Arduino)

```cpp
#include <HTTPClient.h>

const char *WEBHOOK = "http://192.168.1.10:8123/api/webhook/<id>";

bool sendBarcode(const String &barcode) {
  HTTPClient http;
  http.begin(WEBHOOK);
  http.setTimeout(90000);
  http.addHeader("Content-Type", "application/json");
  int status = http.POST("{\"ean\":\"" + barcode + "\"}");
  http.end();
  return status == 200;
}
```

## Testing without a scanner

Use the action directly from **Developer tools > Actions**:

```yaml
action: shopping_assistant.add_scanned_to_shopping_list
data:
  ean: "3017620422003"
```

Or fire a share event the way the phone app would:

```yaml
event_type: mobile_app.share
event_data:
  text: "3017620422003"
```
