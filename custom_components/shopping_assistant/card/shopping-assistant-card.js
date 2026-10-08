/* Shopping Assistant card for Home Assistant
 * Companion card for the shopping_assistant integration.
 * https://github.com/swetoast/ha-shopping-assistant
 */

const CARD_VERSION = "4.0.0";
const DOMAIN = "shopping_assistant";
const OFF_PRODUCT_URL = "https://world.openfoodfacts.org/product/";

const nothing = "";

/* Cards of the Home suite. When one of them (or its --home-* theme tokens) is
 * present, style "auto" picks the Home look so this card sits in with them. */
const HOME_SUITE = [
  "home-summary-card", "home-climate-summary", "home-energy-summery", "home-plant-summery",
  "home-quick-control-card", "home-spacer-card", "home-vacuum-summary", "home-work-summary",
  "home-you-summery", "home-weather-summary",
];
const HOME_TOKENS = ["--home-font", "--home-panel", "--home-title-size", "--metro-font-family"];

/* ------------------------------------------------------------------ */
/* Pure helpers                                                        */
/* ------------------------------------------------------------------ */

const GTIN_LENGTHS = [8, 12, 13, 14];

function gtinValid(code) {
  if (!/^\d+$/.test(code) || !GTIN_LENGTHS.includes(code.length)) return false;
  const digits = [...code].map(Number);
  const check = digits.pop();
  const sum = digits
    .reverse()
    .reduce((acc, d, i) => acc + d * (i % 2 === 0 ? 3 : 1), 0);
  return (10 - (sum % 10)) % 10 === check;
}

const cleanEan = (value) => String(value || "").replace(/\D/g, "").slice(0, 14);

const SCORE_COLORS = {
  "a-plus": ["#00602f", "#fff"],
  a: ["#038141", "#fff"],
  b: ["#85bb2f", "#fff"],
  c: ["#fecb02", "#1f1f1f"],
  d: ["#ee8100", "#fff"],
  e: ["#e63e11", "#fff"],
  f: ["#b0170c", "#fff"],
};
const NOVA_COLORS = { 1: "#038141", 2: "#85bb2f", 3: "#ee8100", 4: "#e63e11" };
const validGrade = (g) => typeof g === "string" && g.toLowerCase() in SCORE_COLORS;
const gradeLabel = (g) => (g.toLowerCase() === "a-plus" ? "A+" : g.toUpperCase());

/* UK FSA front-of-pack thresholds (low <=, high >) per 100 g and per 100 ml. */
const TRAFFIC_LIGHTS = {
  fat: { g: [3, 17.5], ml: [1.5, 8.75] },
  saturated_fat: { g: [1.5, 5], ml: [0.75, 2.5] },
  sugars: { g: [5, 22.5], ml: [2.5, 11.25] },
  salt: { g: [0.3, 1.5], ml: [0.3, 0.75] },
};

/* Main nutrition rows: [key, label, unit, indent]. Values come per 100 g/ml. */
const NUTRITION_ROWS = [
  ["energy_kcal", "Energy", "kcal", false],
  ["fat", "Fat", "g", false],
  ["saturated_fat", "of which saturates", "g", true],
  ["carbohydrates", "Carbohydrates", "g", false],
  ["sugars", "of which sugars", "g", true],
  ["fiber", "Fibre", "g", false],
  ["proteins", "Protein", "g", false],
  ["salt", "Salt", "g", false],
];

/* Micronutrients arrive in grams; show them in the unit people expect. */
const MICRONUTRIENTS = [
  ["vitamin_a", "Vitamin A", "\u00b5g", 1e6],
  ["vitamin_d", "Vitamin D", "\u00b5g", 1e6],
  ["vitamin_e", "Vitamin E", "mg", 1e3],
  ["vitamin_k", "Vitamin K", "\u00b5g", 1e6],
  ["vitamin_c", "Vitamin C", "mg", 1e3],
  ["vitamin_b1", "Thiamin (B1)", "mg", 1e3],
  ["vitamin_b2", "Riboflavin (B2)", "mg", 1e3],
  ["vitamin_b6", "Vitamin B6", "mg", 1e3],
  ["vitamin_b9", "Folate (B9)", "\u00b5g", 1e6],
  ["vitamin_b12", "Vitamin B12", "\u00b5g", 1e6],
  ["calcium", "Calcium", "mg", 1e3],
  ["iron", "Iron", "mg", 1e3],
  ["magnesium", "Magnesium", "mg", 1e3],
  ["phosphorus", "Phosphorus", "mg", 1e3],
  ["potassium", "Potassium", "mg", 1e3],
  ["zinc", "Zinc", "mg", 1e3],
  ["caffeine", "Caffeine", "mg", 1e3],
];

const EDIT_FIELDS = [
  ["product_name", "name", "Name", "text"],
  ["brands", "brands", "Brand", "text"],
  ["quantity", "quantity", "Net quantity", "text"],
  ["categories", "categories", "Categories", "text"],
  ["ingredients_text", "ingredients_text", "Ingredients", "textarea"],
  ["energy_kcal", "energy_kcal", "Energy (kcal)", "number"],
  ["fat", "fat", "Fat (g)", "number"],
  ["saturated_fat", "saturated_fat", "Saturates (g)", "number"],
  ["carbohydrates", "carbohydrates", "Carbohydrates (g)", "number"],
  ["sugars", "sugars", "Sugars (g)", "number"],
  ["fiber", "fiber", "Fibre (g)", "number"],
  ["proteins", "proteins", "Protein (g)", "number"],
  ["salt", "salt", "Salt (g)", "number"],
  ["notes", "notes", "Notes (private)", "textarea"],
];

const FILTERS = [
  { id: "all", label: "All" },
  { id: "vegan", label: "Vegan", icon: "mdi:sprout" },
  { id: "vegetarian", label: "Vegetarian", icon: "mdi:leaf" },
  { id: "green", label: "Green-Score A-B", icon: "mdi:earth" },
  { id: "unhealthy", label: "Nutri-Score D-E", icon: "mdi:alert-outline" },
];

const SORTS = [
  { id: "added", label: "Recently added", icon: "mdi:sort-clock-descending-outline" },
  { id: "name", label: "Name", icon: "mdi:sort-alphabetical-ascending" },
  { id: "nutri", label: "Nutri-Score", icon: "mdi:sort-ascending" },
];

const tagLabel = (tag) => {
  const text = String(tag).replace(/^[a-z]{2}:/, "").replace(/-/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};

const daysUntil = (isoDate) => {
  if (!isoDate) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const date = new Date(`${String(isoDate).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return null;
  return Math.round((date - today) / 86400000);
};

const expiryText = (days) => {
  if (days === null) return "";
  if (days < 0) return days === -1 ? "Expired yesterday" : `Expired ${-days} days ago`;
  if (days === 0) return "Expires today";
  if (days === 1) return "Expires tomorrow";
  return `Expires in ${days} days`;
};

const qtyNumber = (value) => {
  const n = parseInt(value, 10);
  return Number.isFinite(n) && n > 0 ? n : 1;
};

/* ------------------------------------------------------------------ */
/* Card                                                                */
/* ------------------------------------------------------------------ */

function defineCard(LitElement) {
  const { html, css } = LitElement.prototype;

  class ShoppingAssistantCard extends LitElement {
    static get properties() {
      return {
        hass: { attribute: false },
        _config: { state: true },
        _tab: { state: true },
        _input: { state: true },
        _busy: { state: true },
        _result: { state: true },
        _filter: { state: true },
        _sort: { state: true },
        _query: { state: true },
        _details: { state: true },
        _editing: { state: true },
        _menuOpen: { state: true },
        _confirmClear: { state: true },
        _scanner: { state: true },
        _pending: { state: true },
        _names: { state: true },
      };
    }

    constructor() {
      super();
      this._tab = "list";
      this._input = "";
      this._busy = false;
      this._result = null;
      this._filter = "all";
      this._sort = "added";
      this._query = "";
      this._details = null;
      this._editing = null;
      this._menuOpen = false;
      this._confirmClear = false;
      this._scanner = null;
      this._pending = new Set();
      this._names = {};
      this._idCache = null;
      this._swipe = null;
      this._stream = null;
      this._scanTimer = null;
    }

    /* ---------- Lovelace API ---------- */

    setConfig(config) {
      if (!config) throw new Error("Invalid configuration");
      this._config = {
        title: "Shopping",
        style: "auto",
        surface: "auto",
        show_scanner: true,
        show_filters: true,
        show_totals: true,
        show_stats: true,
        scan_action: "add",
        ...config,
      };
      if (this.isConnected) this._applyLook();
    }

    connectedCallback() {
      super.connectedCallback();
      this._applyLook();
    }

    /** Resolve style and surface into host attributes the stylesheet keys off. */
    _applyLook() {
      if (!this._config) return;
      let style = this._config.style;
      if (style !== "home" && style !== "default") {
        const computed = getComputedStyle(this);
        const tokens = HOME_TOKENS.some((name) => computed.getPropertyValue(name).trim());
        style = tokens || HOME_SUITE.some((tag) => customElements.get(tag)) ? "home" : "default";
      }
      const surface = this._config.surface === "card" || this._config.surface === "flat"
        ? this._config.surface
        : style === "home" ? "flat" : "card";
      this.setAttribute("sa-style", style);
      this.setAttribute("sa-surface", surface);
      if (this._config.accent) this.style.setProperty("--sa-accent", this._config.accent);
      else this.style.removeProperty("--sa-accent");
    }

    get _icon() {
      if (this._config.icon !== undefined) return this._config.icon || null;
      return this.getAttribute("sa-style") === "home" ? null : "mdi:cart-outline";
    }

    static getStubConfig() {
      return { type: "custom:shopping-assistant-card" };
    }

    static getConfigForm() {
      return {
        schema: [
          { name: "title", selector: { text: {} } },
          {
            type: "grid",
            name: "",
            schema: [
              {
                name: "style",
                selector: {
                  select: {
                    mode: "dropdown",
                    options: [
                      { value: "auto", label: "Automatic" },
                      { value: "home", label: "Home" },
                      { value: "default", label: "Home Assistant" },
                    ],
                  },
                },
              },
              {
                name: "surface",
                selector: {
                  select: {
                    mode: "dropdown",
                    options: [
                      { value: "auto", label: "Automatic" },
                      { value: "card", label: "Card background" },
                      { value: "flat", label: "Flat, blends into the page" },
                    ],
                  },
                },
              },
              { name: "icon", selector: { icon: {} } },
              { name: "accent", selector: { text: {} } },
            ],
          },
          {
            name: "entity",
            selector: {
              entity: { filter: { integration: DOMAIN, domain: "sensor" } },
            },
          },
          {
            name: "scan_action",
            selector: {
              select: {
                mode: "dropdown",
                options: [
                  { value: "add", label: "Add to the shopping list" },
                  { value: "lookup", label: "Only show the product" },
                ],
              },
            },
          },
          {
            type: "grid",
            name: "",
            schema: [
              { name: "show_scanner", selector: { boolean: {} } },
              { name: "show_filters", selector: { boolean: {} } },
              { name: "show_totals", selector: { boolean: {} } },
              { name: "show_stats", selector: { boolean: {} } },
            ],
          },
        ],
        computeLabel: (schema) =>
          ({
            title: "Title",
            style: "Style",
            surface: "Background",
            icon: "Icon (empty for none)",
            accent: "Accent colour (CSS, optional)",
            entity: "Shopping list sensor (optional)",
            scan_action: "When a barcode is scanned",
            show_scanner: "Camera scanner",
            show_filters: "Filters and sorting",
            show_totals: "Estimated total",
            show_stats: "Statistics",
          })[schema.name],
      };
    }

    getCardSize() {
      return 3 + Math.min(this._products().length, 8);
    }

    getGridOptions() {
      return { columns: 12, min_columns: 6, rows: "auto", min_rows: 4 };
    }

    disconnectedCallback() {
      super.disconnectedCallback();
      this._stopScanner();
    }

    /* ---------- Data ---------- */

    /** Map translation_key -> entity_id for this integration's entities. */
    _ids() {
      const registry = this.hass?.entities;
      if (!this._idCache || this._idCache.registry !== registry || this._idCache.config !== this._config) {
        const ids = {};
        for (const [entityId, entry] of Object.entries(registry || {})) {
          if (entry.platform === DOMAIN && entry.translation_key) {
            ids[entry.translation_key] = entityId;
          }
        }
        ids.shopping_list = this._config?.entity || ids.shopping_list || `sensor.${DOMAIN}_shopping_list`;
        ids.statistics ||= `sensor.${DOMAIN}_statistics`;
        ids.unknown_products ||= `sensor.${DOMAIN}_unknown_products`;
        ids.api_problem ||= `binary_sensor.${DOMAIN}_api_problem`;
        ids.expiring_soon ||= `sensor.${DOMAIN}_expiring_soon`;
        this._idCache = { registry, config: this._config, ids };
      }
      return this._idCache.ids;
    }

    _stateOf(key) {
      return this.hass?.states?.[this._ids()[key]];
    }

    _products() {
      return this._stateOf("shopping_list")?.attributes?.products || [];
    }

    _unknowns() {
      return this._stateOf("unknown_products")?.attributes?.unknowns || [];
    }

    _expiring() {
      return this._stateOf("expiring_soon")?.attributes?.products || [];
    }

    shouldUpdate(changed) {
      if (!changed.has("hass") || changed.size > 1) return true;
      const old = changed.get("hass");
      if (!old || old.locale !== this.hass.locale) return true;
      if (old.themes !== this.hass.themes) {
        this._applyLook();
        return true;
      }
      if (old.entities !== this.hass.entities) return true;
      return Object.values(this._ids()).some((id) => old.states[id] !== this.hass.states[id]);
    }

    /* ---------- Formatting ---------- */

    get _lang() {
      return this.hass?.locale?.language || navigator.language || "en";
    }

    _num(value, digits = 1) {
      return new Intl.NumberFormat(this._lang, { maximumFractionDigits: digits }).format(value);
    }

    _money(value, currency) {
      try {
        return new Intl.NumberFormat(this._lang, {
          style: "currency",
          currency: currency || this.hass?.config?.currency || "EUR",
        }).format(value);
      } catch (_err) {
        return `${this._num(value, 2)} ${currency || ""}`.trim();
      }
    }

    /* ---------- Service calls ---------- */

    async _call(service, data = {}, { response = false, quiet = false } = {}) {
      try {
        const result = await this.hass.callService(DOMAIN, service, data, undefined, false, response);
        return response ? result?.response : true;
      } catch (err) {
        if (!quiet) this._toast(err?.message || String(err));
        return null;
      }
    }

    _toast(message, action) {
      this.dispatchEvent(
        new CustomEvent("hass-notification", {
          bubbles: true,
          composed: true,
          detail: action ? { message, action } : { message },
        })
      );
    }

    _haptic(type = "light") {
      this.dispatchEvent(new CustomEvent("haptic", { bubbles: true, composed: true, detail: type }));
    }

    async _withPending(ean, fn) {
      this._pending = new Set(this._pending).add(ean);
      try {
        return await fn();
      } finally {
        const next = new Set(this._pending);
        next.delete(ean);
        this._pending = next;
      }
    }

    /* ---------- Actions ---------- */

    async _submitInput(mode = this._config.scan_action) {
      const ean = cleanEan(this._input);
      if (ean.length < 8) {
        this._toast("Enter a barcode with 8 to 14 digits");
        return;
      }
      await this._handleBarcode(ean, mode);
    }

    async _handleBarcode(ean, mode) {
      this._busy = true;
      try {
        if (mode === "lookup") {
          const res = await this._call("lookup_product", { ean }, { response: true });
          if (!res) return;
          this._input = "";
          if (res.found) {
            this._openDetails(res.product);
            this._result = null;
          } else {
            this._result = { ean, status: res.source === "missing" || res.source === "cached_missing" ? "unknown" : "error", source: res.source };
          }
          return;
        }
        const res = await this._call("add_scanned_to_shopping_list", { ean }, { response: true });
        if (!res) return;
        this._input = "";
        if (res.name) {
          this._result = { ean, status: "added", name: res.name };
          this._haptic("success");
          this._tab = "list";
        } else {
          this._result = {
            ean,
            status: res.source === "rate_limited" || res.source === "error" ? "error" : "unknown",
            source: res.source,
          };
          this._haptic("warning");
        }
      } finally {
        this._busy = false;
      }
    }

    async _nameBarcode(ean, name, addToList = true) {
      const clean = String(name || "").trim();
      if (!clean) {
        this._toast("Type a product name first");
        return false;
      }
      const ok = await this._withPending(ean, () =>
        this._call("add_mapping", { ean, name: clean, add_to_shopping_list: addToList })
      );
      if (ok) {
        const names = { ...this._names };
        delete names[ean];
        this._names = names;
        if (this._result?.ean === ean) this._result = { ean, status: "added", name: clean };
        this._haptic("success");
      }
      return Boolean(ok);
    }

    async _dismissUnknown(ean) {
      await this._withPending(ean, () => this._call("remove_mapping", { ean }));
    }

    async _setQuantity(product, delta) {
      const next = Math.max(1, qtyNumber(product.shopping_list_quantity) + delta);
      await this._withPending(product.ean, () =>
        this._call("update_shopping_list_quantity", { ean: product.ean, quantity: String(next) })
      );
    }

    async _markBought(product) {
      this._haptic("light");
      const ok = await this._withPending(product.ean, () =>
        this._call("remove_from_shopping_list", { ean: product.ean })
      );
      if (!ok) return;
      const quantity = product.shopping_list_quantity;
      this._toast(`${product.product_name} removed`, {
        text: "Undo",
        action: () =>
          this._call("add_scanned_to_shopping_list", {
            ean: product.ean,
            ...(quantity ? { quantity } : {}),
          }),
      });
    }

    async _addToList(ean) {
      const res = await this._withPending(ean, () =>
        this._call("add_scanned_to_shopping_list", { ean }, { response: true })
      );
      if (res?.name) this._toast(`Added ${res.name}`);
    }

    async _clearList() {
      if (!this._confirmClear) {
        this._confirmClear = true;
        clearTimeout(this._confirmTimer);
        this._confirmTimer = setTimeout(() => (this._confirmClear = false), 4000);
        return;
      }
      this._confirmClear = false;
      this._menuOpen = false;
      if (await this._call("clear_shopping_list")) this._toast("Shopping list cleared");
    }

    /* ---------- Details ---------- */

    async _openDetails(product) {
      this._editing = null;
      this._details = { product, full: null, loading: true };
      const res = await this._call("lookup_product", { ean: product.ean }, { response: true, quiet: true });
      if (this._details?.product?.ean !== product.ean) return;
      this._details = { product, full: res?.product || null, loading: false };
    }

    async _refreshDetails() {
      const ean = this._details?.product?.ean;
      if (!ean) return;
      this._details = { ...this._details, loading: true };
      const res = await this._call("lookup_product", { ean, force_refresh: true }, { response: true });
      if (this._details?.product?.ean !== ean) return;
      this._details = { ...this._details, full: res?.product || this._details.full, loading: false };
      if (res?.product) this._toast("Updated from OpenFoodFacts");
    }

    _closeDetails() {
      this._details = null;
      this._editing = null;
    }

    _startEdit() {
      const p = this._detailProduct();
      const values = {};
      for (const [attr] of EDIT_FIELDS) values[attr] = p[attr] ?? "";
      this._editing = { values, original: { ...values }, submit: false };
      this.updateComplete.then(() => {
        const body = this.renderRoot.querySelector(".dialog-body");
        if (body) body.scrollTop = 0;
      });
    }

    async _saveEdit() {
      const { values, original, submit } = this._editing;
      const ean = this._detailProduct().ean;
      const data = { ean };
      for (const [attr, field, , type] of EDIT_FIELDS) {
        const value = values[attr];
        if (value === original[attr] || value === "" || value === null) continue;
        data[field] = type === "number" ? Number(value) : value;
      }
      if (Object.keys(data).length === 1 && !submit) {
        this._editing = null;
        return;
      }
      if (submit) data.submit_to_openfoodfacts = true;
      this._busy = true;
      const res = await this._call("update_product", data, { response: true });
      this._busy = false;
      if (!res) return;
      this._editing = null;
      this._details = { ...this._details, full: res.product };
      this._toast(res.submission?.ok ? "Saved and sent to OpenFoodFacts" : "Product saved");
    }

    async _addPrice(form) {
      const ean = this._detailProduct().ean;
      const price = Number(form.price.value);
      if (!Number.isFinite(price) || price < 0) return this._toast("Enter a price");
      const data = { ean, price };
      if (form.store.value.trim()) data.store = form.store.value.trim();
      if (await this._call("add_price", data)) {
        form.reset();
        this._reloadFull(ean);
      }
    }

    async _setExpiry(input) {
      const ean = this._detailProduct().ean;
      if (!input.value) return;
      if (await this._call("set_expiry", { ean, expiry_date: input.value })) this._reloadFull(ean);
    }

    async _reloadFull(ean) {
      const res = await this._call("lookup_product", { ean }, { response: true, quiet: true });
      if (res?.product && this._details?.product?.ean === ean) {
        this._details = { ...this._details, full: res.product };
      }
    }

    _detailProduct() {
      const d = this._details;
      if (!d) return null;
      const listed = this._products().find((p) => p.ean === d.product.ean);
      return { ...d.product, ...(d.full || {}), ...(listed ? { shopping_list_quantity: listed.shopping_list_quantity, in_shopping_list: true } : {}) };
    }

    /* ---------- Scanner ---------- */

    get _scannerSupported() {
      return "BarcodeDetector" in window && Boolean(navigator.mediaDevices?.getUserMedia);
    }

    async _openScanner() {
      this._scanner = { continuous: false, torch: false, torchAvailable: false, last: [], error: "" };
      await this.updateComplete;
      try {
        this._stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } },
          audio: false,
        });
        const video = this.renderRoot.querySelector("#scanner-video");
        if (!video || !this._scanner) return this._stopScanner();
        video.srcObject = this._stream;
        await video.play();
        const track = this._stream.getVideoTracks()[0];
        const caps = track?.getCapabilities ? track.getCapabilities() : {};
        this._scanner = { ...this._scanner, torchAvailable: Boolean(caps.torch) };
        this._detector = new window.BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a"] });
        this._detectLoop(video);
      } catch (err) {
        this._scanner = {
          ...this._scanner,
          error: err?.name === "NotAllowedError" ? "Camera access was denied" : "The camera could not be started",
        };
      }
    }

    _detectLoop(video) {
      this._scanTimer = setTimeout(async () => {
        if (!this._scanner || !this._stream) return;
        try {
          const codes = await this._detector.detect(video);
          const hit = codes.map((c) => cleanEan(c.rawValue)).find(gtinValid);
          if (hit && !this._scanner.last.some((l) => l.ean === hit && Date.now() - l.at < 3000)) {
            this._haptic("success");
            if (this._scanner.continuous) {
              this._scanner = { ...this._scanner, last: [{ ean: hit, at: Date.now() }, ...this._scanner.last].slice(0, 5) };
              this._handleBarcode(hit, "add");
            } else {
              this._stopScanner();
              this._handleBarcode(hit, this._config.scan_action);
              return;
            }
          }
        } catch (_err) {
          /* a frame that cannot be decoded; keep scanning */
        }
        this._detectLoop(video);
      }, 180);
    }

    async _toggleTorch() {
      const track = this._stream?.getVideoTracks()[0];
      if (!track) return;
      const torch = !this._scanner.torch;
      try {
        await track.applyConstraints({ advanced: [{ torch }] });
        this._scanner = { ...this._scanner, torch };
      } catch (_err) {
        this._scanner = { ...this._scanner, torchAvailable: false };
      }
    }

    _stopScanner() {
      clearTimeout(this._scanTimer);
      this._stream?.getTracks().forEach((t) => t.stop());
      this._stream = null;
      this._scanner = null;
    }

    /* ---------- Swipe to remove ---------- */

    _touchStart(e, product) {
      const t = e.touches[0];
      this._swipe = { product, x: t.clientX, y: t.clientY, dx: 0, active: false, el: e.currentTarget };
    }

    _touchMove(e) {
      const s = this._swipe;
      if (!s) return;
      const t = e.touches[0];
      const dx = t.clientX - s.x;
      const dy = t.clientY - s.y;
      if (!s.active) {
        if (Math.abs(dy) > Math.abs(dx) || Math.abs(dx) < 12) return;
        s.active = true;
      }
      s.dx = Math.min(0, dx);
      s.el.style.transform = `translateX(${s.dx}px)`;
      s.el.parentElement.classList.toggle("armed", -s.dx > s.el.offsetWidth * 0.35);
    }

    _touchEnd() {
      const s = this._swipe;
      this._swipe = null;
      if (!s?.active) return;
      const remove = -s.dx > s.el.offsetWidth * 0.35;
      s.el.style.transform = "";
      s.el.parentElement.classList.remove("armed");
      if (remove) this._markBought(s.product);
    }

    /* ---------- Derived list ---------- */

    _visibleProducts() {
      let list = [...this._products()];
      const q = this._query.trim().toLowerCase();
      if (q) list = list.filter((p) => `${p.product_name} ${p.brands || ""} ${p.ean}`.toLowerCase().includes(q));
      const grade = (g) => String(g || "").toLowerCase();
      if (this._filter === "vegan") list = list.filter((p) => p.ingredients_analysis_vegan === "yes");
      if (this._filter === "vegetarian") list = list.filter((p) => p.ingredients_analysis_vegetarian === "yes");
      if (this._filter === "green") list = list.filter((p) => ["a-plus", "a", "b"].includes(grade(p.eco_score_grade)));
      if (this._filter === "unhealthy") list = list.filter((p) => ["d", "e"].includes(grade(p.nutrition_grades)));
      if (this._sort === "name") list.sort((a, b) => a.product_name.localeCompare(b.product_name, this._lang));
      if (this._sort === "nutri") {
        const rank = (p) => (validGrade(p.nutrition_grades) ? "abcde".indexOf(grade(p.nutrition_grades)) : 9);
        list.sort((a, b) => rank(a) - rank(b));
      }
      if (this._sort === "added") list.sort((a, b) => String(b.added_to_list_at || "").localeCompare(String(a.added_to_list_at || "")));
      return list;
    }

    _total(products) {
      let total = 0;
      let priced = 0;
      let currency = null;
      for (const p of products) {
        if (typeof p.current_price !== "number") continue;
        if (currency && p.price_currency && p.price_currency !== currency) continue;
        currency = currency || p.price_currency;
        total += p.current_price * qtyNumber(p.shopping_list_quantity);
        priced += 1;
      }
      return { total, priced, currency };
    }

    /* ------------------------------------------------------------------ */
    /* Rendering                                                           */
    /* ------------------------------------------------------------------ */

    render() {
      if (!this.hass || !this._config) return nothing;
      const listState = this._stateOf("shopping_list");
      if (!listState) {
        return html`<ha-card>
          <div class="empty-state">
            <ha-icon icon="mdi:cart-off"></ha-icon>
            <div class="empty-title">Shopping Assistant not found</div>
            <div class="empty-text">Add the Shopping Assistant integration, or pick its shopping list sensor in the card settings.</div>
          </div>
        </ha-card>`;
      }
      const products = this._products();
      const unknowns = this._unknowns();
      const hasExpiry = Boolean(this._stateOf("expiring_soon"));
      const expiring = this._expiring();

      return html`
        <ha-card>
          ${this._renderHeader(products, unknowns)}
          ${this._renderInput()}
          ${this._renderResult()}
          ${this._renderTabs(products.length, unknowns.length, hasExpiry ? expiring.length : null)}
          <div class="tab-body">
            ${this._tab === "unknown"
              ? this._renderUnknowns(unknowns)
              : this._tab === "expiring" && hasExpiry
                ? this._renderExpiring(expiring)
                : this._renderList(products)}
          </div>
          ${this._config.show_stats ? this._renderStats() : nothing}
        </ha-card>
        ${this._details ? this._renderDetails() : nothing}
        ${this._menuOpen ? this._renderMenu(products.length) : nothing}
        ${this._scanner ? this._renderScanner() : nothing}
      `;
    }

    _renderHeader(products, unknowns) {
      const api = this._stateOf("api_problem");
      const problem = api?.state === "on";
      const count = products.length;
      return html`
        <div class="header">
          ${this._icon ? html`<div class="header-icon"><ha-icon icon=${this._icon}></ha-icon></div>` : nothing}
          <div class="header-text">
            <div class="title">${this._config.title}</div>
            <div class="subtitle">${[
              count === 0 ? "Nothing to buy" : `${count} ${count === 1 ? "item" : "items"} to buy`,
              unknowns.length ? `${unknowns.length} to name` : null,
            ].filter(Boolean).join(" \u00b7 ")}</div>
          </div>
          ${problem
            ? html`<button class="status-chip" title=${api.attributes.last_error || ""}
                @click=${() => this._toast(`OpenFoodFacts: ${api.attributes.last_error || "not reachable"}`)}>
                <ha-icon icon="mdi:cloud-alert-outline"></ha-icon><span>Offline</span>
              </button>`
            : nothing}
          <button class="icon-button" aria-label="More actions" @click=${() => (this._menuOpen = true)}>
            <ha-icon icon="mdi:dots-vertical"></ha-icon>
          </button>
        </div>
      `;
    }

    _renderInput() {
      const showScanner = this._config.show_scanner && this._scannerSupported;
      const valid = cleanEan(this._input).length >= 8;
      const lookupOnly = this._config.scan_action === "lookup";
      return html`
        <div class="input-row">
          <div class="search-field ${this._busy ? "busy" : ""}">
            <ha-icon class="field-icon" icon="mdi:barcode"></ha-icon>
            <input
              type="text"
              inputmode="numeric"
              autocomplete="off"
              enterkeyhint="go"
              aria-label="Barcode"
              placeholder=${showScanner ? "Scan or type a barcode" : "Type a barcode"}
              .value=${this._input}
              @input=${(e) => (this._input = cleanEan(e.target.value))}
              @keydown=${(e) => e.key === "Enter" && this._submitInput()}
            />
            ${this._input
              ? html`<button class="icon-button small" aria-label="Clear" @click=${() => (this._input = "")}>
                  <ha-icon icon="mdi:close"></ha-icon>
                </button>`
              : nothing}
            ${showScanner
              ? html`<button class="icon-button accent" aria-label="Scan with camera" ?disabled=${this._busy}
                  @click=${this._openScanner}>
                  <ha-icon icon="mdi:barcode-scan"></ha-icon>
                </button>`
              : nothing}
          </div>
          <button class="filled-button" ?disabled=${this._busy || !valid} @click=${() => this._submitInput()}>
            ${this._busy
              ? html`<span class="spinner"></span>`
              : html`<ha-icon icon=${lookupOnly ? "mdi:magnify" : "mdi:cart-plus"}></ha-icon>`}
            <span class="label">${lookupOnly ? "Look up" : "Add"}</span>
          </button>
        </div>
      `;
    }

    _renderResult() {
      const r = this._result;
      if (!r) return nothing;
      const close = html`<button class="icon-button small" aria-label="Dismiss" @click=${() => (this._result = null)}>
        <ha-icon icon="mdi:close"></ha-icon>
      </button>`;
      if (r.status === "added") {
        return html`<div class="result success">
          <ha-icon icon="mdi:check-circle"></ha-icon>
          <div class="result-text"><strong>${r.name}</strong> is on the list</div>
          ${close}
        </div>`;
      }
      if (r.status === "error") {
        return html`<div class="result warning">
          <ha-icon icon="mdi:cloud-alert-outline"></ha-icon>
          <div class="result-text">OpenFoodFacts could not be reached for <code>${r.ean}</code>. Try again in a minute.</div>
          ${close}
        </div>`;
      }
      const value = this._names[r.ean] || "";
      return html`<div class="result unknown">
        <div class="result-head">
          <ha-icon icon="mdi:help-circle-outline"></ha-icon>
          <div class="result-text">OpenFoodFacts does not know <code>${r.ean}</code>. What is it?</div>
          ${close}
        </div>
        <form class="name-form" @submit=${(e) => { e.preventDefault(); this._nameBarcode(r.ean, value); }}>
          <input type="text" placeholder="Product name" aria-label="Product name" .value=${value}
            @input=${(e) => (this._names = { ...this._names, [r.ean]: e.target.value })} />
          <button class="filled-button" type="submit" ?disabled=${!value.trim() || this._pending.has(r.ean)}>
            <ha-icon icon="mdi:cart-plus"></ha-icon><span class="label">Save and add</span>
          </button>
        </form>
      </div>`;
    }

    _renderTabs(listCount, unknownCount, expiringCount) {
      const tabs = [
        { id: "list", label: "List", count: listCount },
        { id: "unknown", label: "To name", count: unknownCount, alert: unknownCount > 0 },
      ];
      if (expiringCount !== null) tabs.push({ id: "expiring", label: "Expiring", count: expiringCount, alert: expiringCount > 0 });
      return html`<div class="tabs" role="tablist">
        ${tabs.map(
          (t) => html`<button role="tab" aria-selected=${this._tab === t.id} class="tab ${this._tab === t.id ? "active" : ""}"
            @click=${() => (this._tab = t.id)}>
            ${t.label}
            ${t.count ? html`<span class="count ${t.alert ? "alert" : ""}">${t.count}</span>` : nothing}
          </button>`
        )}
      </div>`;
    }

    _renderList(products) {
      if (!products.length) {
        return html`<div class="empty-state">
          <ha-icon icon="mdi:cart-check"></ha-icon>
          <div class="empty-title">Your list is empty</div>
          <div class="empty-text">Scan or type a barcode above to add something.</div>
        </div>`;
      }
      const visible = this._visibleProducts();
      const { total, priced, currency } = this._total(products);
      return html`
        ${this._config.show_filters ? this._renderFilters(products.length) : nothing}
        ${visible.length
          ? html`<div class="list">${visible.map((p) => this._renderRow(p))}</div>`
          : html`<div class="empty-inline">Nothing matches this filter.</div>`}
        ${this._config.show_totals && priced
          ? html`<div class="total">
              <span>Estimated total${priced < products.length ? html` <span class="muted">(${priced} of ${products.length} priced)</span>` : nothing}</span>
              <strong>${this._money(total, currency)}</strong>
            </div>`
          : nothing}
      `;
    }

    _renderFilters(count) {
      const sort = SORTS.find((s) => s.id === this._sort);
      return html`<div class="toolbar">
        ${count > 6
          ? html`<div class="mini-search">
              <ha-icon icon="mdi:magnify"></ha-icon>
              <input type="search" placeholder="Search the list" aria-label="Search the list" .value=${this._query}
                @input=${(e) => (this._query = e.target.value)} />
            </div>`
          : nothing}
        <div class="chips">
          ${FILTERS.map(
            (f) => html`<button class="chip ${this._filter === f.id ? "selected" : ""}" aria-pressed=${this._filter === f.id}
              @click=${() => (this._filter = f.id)}>
              ${this._filter === f.id && f.id !== "all" ? html`<ha-icon icon="mdi:check"></ha-icon>` : f.icon ? html`<ha-icon icon=${f.icon}></ha-icon>` : nothing}
              ${f.label}
            </button>`
          )}
        </div>
        <button class="sort-button" title="Sort: ${sort.label}" aria-label="Sort: ${sort.label}" @click=${() => {
          const i = SORTS.findIndex((s) => s.id === this._sort);
          this._sort = SORTS[(i + 1) % SORTS.length].id;
          this._toast(`Sorted by ${SORTS[(i + 1) % SORTS.length].label.toLowerCase()}`);
        }}>
          <ha-icon icon=${sort.icon}></ha-icon>
        </button>
      </div>`;
    }

    _renderScorePill(grade, kind) {
      if (!validGrade(grade)) return nothing;
      const [bg, fg] = SCORE_COLORS[grade.toLowerCase()];
      return html`<span class="score-pill" style="--score:${bg};--score-fg:${fg}" title="${kind} ${gradeLabel(grade)}">
        <span class="score-kind">Nutri</span>${gradeLabel(grade)}
      </span>`;
    }

    _renderRow(p) {
      const pending = this._pending.has(p.ean);
      const qty = qtyNumber(p.shopping_list_quantity);
      const qtyText = p.shopping_list_quantity && !/^\d+$/.test(p.shopping_list_quantity) ? p.shopping_list_quantity : null;
      const img = p.image_small_url || p.image_url;
      const brandShown = p.brands && !p.product_name.toLowerCase().includes(String(p.brands).split(",")[0].toLowerCase());
      const days = daysUntil(p.expiry_date);
      const meta = [brandShown ? p.brands : null, typeof p.current_price === "number" ? this._money(p.current_price, p.price_currency) : null].filter(Boolean);

      return html`
        <div class="row-wrap">
          <div class="swipe-bg"><ha-icon icon="mdi:check"></ha-icon><span>Bought</span></div>
          <div class="row ${pending ? "pending" : ""}"
            @touchstart=${(e) => this._touchStart(e, p)}
            @touchmove=${this._touchMove}
            @touchend=${this._touchEnd}
            @touchcancel=${this._touchEnd}>
            <button class="thumb" aria-label="Details for ${p.product_name}" @click=${() => this._openDetails(p)}>
              ${img ? html`<img src=${img} alt="" loading="lazy" />` : html`<ha-icon icon="mdi:package-variant-closed"></ha-icon>`}
            </button>
            <button class="row-main" @click=${() => this._openDetails(p)}>
              <span class="row-title">${p.product_name}</span>
              ${meta.length ? html`<span class="row-meta">${meta.join(" \u00b7 ")}</span>` : nothing}
              <span class="row-tags">
                ${this._renderScorePill(p.nutrition_grades, "Nutri-Score")}
                ${p.nova_group ? html`<span class="nova" style="--score:${NOVA_COLORS[p.nova_group] || "#888"}" title="NOVA group ${p.nova_group}">NOVA ${p.nova_group}</span>` : nothing}
                ${p.ingredients_analysis_vegan === "yes"
                  ? html`<span class="diet" title="Vegan"><ha-icon icon="mdi:sprout"></ha-icon></span>`
                  : p.ingredients_analysis_vegetarian === "yes"
                    ? html`<span class="diet" title="Vegetarian"><ha-icon icon="mdi:leaf"></ha-icon></span>`
                    : nothing}
                ${days !== null && days <= 7 ? html`<span class="expiry ${days < 0 ? "bad" : days <= 2 ? "warn" : ""}">${expiryText(days)}</span>` : nothing}
              </span>
            </button>
            <div class="stepper" aria-label="Quantity">
              ${qtyText
                ? html`<span class="qty-text" title="Quantity">${qtyText}</span>`
                : html`
                    <button class="step" aria-label="Fewer" ?disabled=${qty <= 1 || pending} @click=${() => this._setQuantity(p, -1)}>
                      <ha-icon icon="mdi:minus"></ha-icon>
                    </button>
                    <span class="qty">${qty}</span>
                    <button class="step" aria-label="More" ?disabled=${pending} @click=${() => this._setQuantity(p, 1)}>
                      <ha-icon icon="mdi:plus"></ha-icon>
                    </button>
                  `}
            </div>
            <button class="check" aria-label="Mark ${p.product_name} as bought" ?disabled=${pending} @click=${() => this._markBought(p)}>
              <ha-icon icon="mdi:check"></ha-icon>
            </button>
          </div>
        </div>
      `;
    }

    _renderUnknowns(unknowns) {
      if (!unknowns.length) {
        return html`<div class="empty-state">
          <ha-icon icon="mdi:check-decagram-outline"></ha-icon>
          <div class="empty-title">All barcodes are named</div>
          <div class="empty-text">Barcodes OpenFoodFacts does not know show up here so you can name them.</div>
        </div>`;
      }
      return html`<div class="list">
        ${unknowns.map((u) => {
          const value = this._names[u.ean] || "";
          const pending = this._pending.has(u.ean);
          return html`<form class="unknown-row" @submit=${(e) => { e.preventDefault(); this._nameBarcode(u.ean, value); }}>
            <div class="unknown-head">
              <code>${u.ean}</code>
              <span class="muted">Scanned ${u.seen_count} ${u.seen_count === 1 ? "time" : "times"}</span>
              <button type="button" class="icon-button small" aria-label="Forget ${u.ean}" ?disabled=${pending}
                @click=${() => this._dismissUnknown(u.ean)}>
                <ha-icon icon="mdi:delete-outline"></ha-icon>
              </button>
            </div>
            <div class="name-form">
              <input type="text" placeholder="Product name" aria-label="Name for ${u.ean}" .value=${value}
                @input=${(e) => (this._names = { ...this._names, [u.ean]: e.target.value })} />
              <button class="tonal-button" type="submit" ?disabled=${!value.trim() || pending}>
                <ha-icon icon="mdi:cart-plus"></ha-icon><span class="label">Save</span>
              </button>
            </div>
          </form>`;
        })}
      </div>`;
    }

    _renderExpiring(items) {
      if (!items.length) {
        return html`<div class="empty-state">
          <ha-icon icon="mdi:calendar-check-outline"></ha-icon>
          <div class="empty-title">Nothing expires this week</div>
          <div class="empty-text">Set expiry dates from a product's details.</div>
        </div>`;
      }
      const listed = new Set(this._products().map((p) => p.ean));
      return html`<div class="list">
        ${items.map((item) => {
          const days = item.days_left;
          return html`<div class="expiring-row">
            <span class="days ${days < 0 ? "bad" : days <= 2 ? "warn" : ""}">
              <strong>${Math.abs(days)}</strong><small>${Math.abs(days) === 1 ? "day" : "days"}${days < 0 ? " ago" : ""}</small>
            </span>
            <button class="row-main" @click=${() => this._openDetails({ ean: item.ean, product_name: item.product_name })}>
              <span class="row-title">${item.product_name}</span>
              <span class="row-meta">${expiryText(days)}</span>
            </button>
            ${listed.has(item.ean)
              ? html`<span class="muted small">On list</span>`
              : html`<button class="tonal-button" ?disabled=${this._pending.has(item.ean)} @click=${() => this._addToList(item.ean)}>
                  <ha-icon icon="mdi:cart-plus"></ha-icon><span class="label">Buy</span>
                </button>`}
          </div>`;
        })}
      </div>`;
    }

    _renderStats() {
      const stats = this._stateOf("statistics");
      if (!stats) return nothing;
      const a = stats.attributes || {};
      const items = [
        ["accent", "Scans", stats.state, "Barcodes scanned"],
        ["violet", "Products", a.total_mappings, "Products you have named or looked up"],
        ["cyan", "Online", a.openfoodfacts_hits, "Products found in OpenFoodFacts"],
        ["green", "Local", a.local_hits, "Scans answered from your own product list"],
      ];
      return html`<div class="stats">
        ${items.map(([hue, label, value, tip]) => html`<div class="stat" title=${tip}>
          <span class="stat-value"><i class="dot ${hue}"></i>${value ?? 0}</span>
          <span class="stat-label">${label}</span>
        </div>`)}
      </div>`;
    }

    _renderMenu(count) {
      const valid = cleanEan(this._input).length >= 8;
      return html`<div class="scrim" @click=${() => { this._menuOpen = false; this._confirmClear = false; }}>
        <div class="sheet" role="dialog" aria-label="Actions" @click=${(e) => e.stopPropagation()}>
          <div class="handle"></div>
          <button class="sheet-item" ?disabled=${!valid}
            @click=${() => { this._menuOpen = false; this._submitInput("lookup"); }}>
            <ha-icon icon="mdi:magnify"></ha-icon>
            <span><strong>Look up the typed barcode</strong><small>Show the product without adding it</small></span>
          </button>
          <button class="sheet-item" @click=${() => { this._menuOpen = false; this._tab = "unknown"; }}>
            <ha-icon icon="mdi:help-circle-outline"></ha-icon>
            <span><strong>Name unknown barcodes</strong><small>${this._unknowns().length} waiting</small></span>
          </button>
          <div class="sheet-divider"></div>
          <button class="sheet-item danger" ?disabled=${!count} @click=${this._clearList}>
            <ha-icon icon="mdi:cart-remove"></ha-icon>
            <span><strong>${this._confirmClear ? `Tap again to remove all ${count} items` : "Clear the list"}</strong>
              <small>Removes everything Shopping Assistant added</small></span>
          </button>
        </div>
      </div>`;
    }

    _renderScanner() {
      const s = this._scanner;
      return html`<div class="scrim dark" @click=${this._stopScanner}>
        <div class="scanner" role="dialog" aria-label="Barcode scanner" @click=${(e) => e.stopPropagation()}>
          <div class="scanner-bar">
            <button class="icon-button light" aria-label="Close scanner" @click=${this._stopScanner}>
              <ha-icon icon="mdi:close"></ha-icon>
            </button>
            <span class="scanner-title">Scan a barcode</span>
            ${s.torchAvailable
              ? html`<button class="icon-button light" aria-label="Torch" @click=${this._toggleTorch}>
                  <ha-icon icon=${s.torch ? "mdi:flashlight-off" : "mdi:flashlight"}></ha-icon>
                </button>`
              : html`<span class="spacer"></span>`}
          </div>
          <div class="viewfinder">
            <video id="scanner-video" muted playsinline></video>
            <div class="frame"><div class="laser"></div></div>
            ${s.error ? html`<div class="scanner-error">${s.error}</div>` : nothing}
          </div>
          <div class="scanner-footer">
            <label class="switch-row">
              <input type="checkbox" .checked=${s.continuous}
                @change=${(e) => (this._scanner = { ...this._scanner, continuous: e.target.checked })} />
              <span>Keep scanning and add every product</span>
            </label>
            ${s.continuous && s.last.length
              ? html`<div class="scanned">${s.last.map((l) => html`<code>${l.ean}</code>`)}</div>`
              : html`<div class="hint">Hold the barcode inside the frame</div>`}
          </div>
        </div>
      </div>`;
    }

    /* ---------- Details sheet ---------- */

    _renderDetails() {
      const p = this._detailProduct();
      const loading = this._details.loading;
      const img = p.image_front_url || p.image_url || p.image_small_url;
      return html`<div class="scrim" @click=${this._closeDetails}>
        <div class="dialog" role="dialog" aria-label=${p.product_name || p.ean} @click=${(e) => e.stopPropagation()}>
          <div class="dialog-bar">
            <button class="icon-button" aria-label="Close" @click=${this._closeDetails}><ha-icon icon="mdi:close"></ha-icon></button>
            <span class="dialog-title">${this._editing ? "Edit product" : "Product"}</span>
            ${this._editing
              ? html`<span class="spacer"></span>`
              : html`<button class="icon-button" aria-label="Refresh from OpenFoodFacts" ?disabled=${loading} @click=${this._refreshDetails}>
                    <ha-icon icon="mdi:refresh"></ha-icon>
                  </button>
                  <button class="icon-button" aria-label="Edit" ?disabled=${loading} @click=${this._startEdit}>
                    <ha-icon icon="mdi:pencil-outline"></ha-icon>
                  </button>`}
          </div>
          ${loading && !this._details.full ? html`<div class="progress"></div>` : nothing}
          <div class="dialog-body">
            ${this._editing ? this._renderEdit() : html`
              <div class="hero">
                <div class="hero-img">${img ? html`<img src=${img} alt="" />` : html`<ha-icon icon="mdi:package-variant-closed"></ha-icon>`}</div>
                <div class="hero-text">
                  <div class="hero-name">${p.product_name || "Unnamed product"}</div>
                  ${p.brands ? html`<div class="muted">${p.brands}</div>` : nothing}
                  <div class="muted small">${[p.quantity, p.ean].filter(Boolean).join(" \u00b7 ")}</div>
                  ${this._renderHeroActions(p)}
                </div>
              </div>
              ${this._renderScores(p)}
              ${this._renderNutrition(p)}
              ${this._renderMicros(p)}
              ${this._renderIngredients(p)}
              ${this._renderSustainability(p)}
              ${this._renderYourData(p)}
              <a class="off-link" href="${OFF_PRODUCT_URL}${p.ean}" target="_blank" rel="noreferrer">
                <ha-icon icon="mdi:open-in-new"></ha-icon> View on OpenFoodFacts
              </a>
            `}
          </div>
        </div>
      </div>`;
    }

    _renderHeroActions(p) {
      const listed = p.in_shopping_list;
      const pending = this._pending.has(p.ean);
      return html`<div class="hero-actions">
        ${listed
          ? html`<button class="tonal-button" ?disabled=${pending}
              @click=${() => { this._markBought(p); this._closeDetails(); }}>
              <ha-icon icon="mdi:check"></ha-icon><span class="label">Bought</span>
            </button>`
          : html`<button class="filled-button" ?disabled=${pending} @click=${() => this._addToList(p.ean)}>
              <ha-icon icon="mdi:cart-plus"></ha-icon><span class="label">Add to list</span>
            </button>`}
      </div>`;
    }

    _renderScores(p) {
      const tiles = [];
      if (validGrade(p.nutrition_grades)) tiles.push(["Nutri-Score", gradeLabel(p.nutrition_grades), ...SCORE_COLORS[p.nutrition_grades.toLowerCase()]]);
      if (validGrade(p.eco_score_grade)) tiles.push(["Green-Score", gradeLabel(p.eco_score_grade), ...SCORE_COLORS[p.eco_score_grade.toLowerCase()]]);
      if (p.nova_group) tiles.push(["NOVA", String(p.nova_group), NOVA_COLORS[p.nova_group] || "#888", "#fff"]);
      const diet = [
        ["Vegan", p.ingredients_analysis_vegan, "mdi:sprout"],
        ["Vegetarian", p.ingredients_analysis_vegetarian, "mdi:leaf"],
        ["Palm oil free", p.ingredients_analysis_palm_oil_free, "mdi:palm-tree"],
      ].filter(([, v]) => v);
      if (!tiles.length && !diet.length) return nothing;
      return html`<section>
        ${tiles.length ? html`<div class="score-tiles">${tiles.map(([label, value, bg, fg]) => html`
          <div class="score-tile" style="--score:${bg};--score-fg:${fg}"><span>${label}</span><strong>${value}</strong></div>`)}</div>` : nothing}
        ${diet.length ? html`<div class="diet-row">${diet.map(([label, value, icon]) => html`
          <span class="diet-chip ${value}"><ha-icon icon=${value === "yes" ? icon : value === "no" ? "mdi:close" : "mdi:help"}></ha-icon>
            ${value === "no" ? `Not ${label.toLowerCase()}` : value === "maybe" ? `${label}?` : label}</span>`)}</div>` : nothing}
      </section>`;
    }

    _renderNutrition(p) {
      const rows = NUTRITION_ROWS.filter(([key]) => typeof p[key] === "number");
      if (!rows.length) return nothing;
      const liquid = p.nutrition_per === "100ml";
      const per = liquid ? "100 ml" : "100 g";
      return html`<section>
        <h3>Nutrition <span class="muted">per ${per}${p.nutrition_preparation === "prepared" ? ", prepared" : ""}</span></h3>
        <div class="meters">
          ${rows.map(([key, label, unit, indent]) => {
            const value = p[key];
            const limits = TRAFFIC_LIGHTS[key]?.[liquid ? "ml" : "g"];
            const level = limits ? (value <= limits[0] ? "low" : value > limits[1] ? "high" : "medium") : null;
            // Bars share a scale per kind: energy against 900 kcal, traffic-light
            // nutrients against 1.5x their "high" limit, the rest against 100 g.
            const scale = unit === "kcal" ? 900 : limits ? limits[1] * 1.5 : 100;
            const width = Math.max(2, Math.min(100, (value / scale) * 100));
            return html`<div class="meter ${indent ? "sub" : ""} ${level || "plain"}">
              <div class="meter-head">
                <span class="meter-name">${label}</span>
                ${level ? html`<span class="meter-level">${level}</span>` : nothing}
                <span class="meter-value">${this._num(value, unit === "kcal" ? 0 : 1)} ${unit}</span>
              </div>
              <div class="track"><div class="fill" style="width:${width}%"></div></div>
            </div>`;
          })}
        </div>
        ${typeof p.alcohol === "number" && p.alcohol > 0 ? html`<div class="note"><ha-icon icon="mdi:glass-wine"></ha-icon>Contains ${this._num(p.alcohol)}% alcohol</div>` : nothing}
      </section>`;
    }

    _renderMicros(p) {
      const items = MICRONUTRIENTS.filter(([key]) => typeof p[key] === "number" && p[key] > 0);
      if (!items.length) return nothing;
      return html`<section>
        <h3>Vitamins and minerals <span class="muted">per ${p.nutrition_per === "100ml" ? "100 ml" : "100 g"}</span></h3>
        <div class="micro-grid">
          ${items.map(([key, label, unit, factor]) => html`<div class="micro">
            <span>${label}</span><strong>${this._num(p[key] * factor, p[key] * factor < 10 ? 1 : 0)} ${unit}</strong>
          </div>`)}
        </div>
      </section>`;
    }

    _renderIngredients(p) {
      if (!p.ingredients_text && !p.allergens && !p.traces && !(p.labels || []).length) return nothing;
      return html`<section>
        <h3>Ingredients</h3>
        ${p.allergens ? html`<div class="note warn"><ha-icon icon="mdi:alert-circle-outline"></ha-icon><span><strong>Allergens:</strong> ${p.allergens}</span></div>` : nothing}
        ${p.traces ? html`<div class="note"><ha-icon icon="mdi:information-outline"></ha-icon><span><strong>May contain:</strong> ${p.traces}</span></div>` : nothing}
        ${p.ingredients_text ? html`<p class="text">${p.ingredients_text}</p>` : nothing}
        ${(p.labels || []).length ? html`<div class="labels">${p.labels.map((l) => html`<span class="label-chip">${tagLabel(l)}</span>`)}</div>` : nothing}
      </section>`;
    }

    _renderSustainability(p) {
      const rows = [
        ["mdi:package-variant", "Packaging", p.packaging],
        ["mdi:recycle", "Recycling", p.recycling_instructions],
        ["mdi:molecule-co2", "Carbon footprint", typeof p.carbon_footprint === "number" ? `${this._num(p.carbon_footprint, 2)} kg CO2e per kg` : null],
        ["mdi:map-marker-outline", "Origin", p.origins],
      ].filter(([, , v]) => v);
      if (!rows.length) return nothing;
      return html`<section>
        <h3>Environment</h3>
        ${rows.map(([icon, label, value]) => html`<div class="info-row"><ha-icon icon=${icon}></ha-icon><span class="muted">${label}</span><span>${value}</span></div>`)}
      </section>`;
    }

    _renderYourData(p) {
      const prices = (p.prices || []).slice(-5).reverse();
      const lowest = (p.prices || []).reduce((min, e) => (min && min.price <= e.price ? min : e), null);
      const days = daysUntil(p.expiry_date);
      return html`<section>
        <h3>Your data</h3>
        <div class="your-data">
          <div class="data-block">
            <div class="data-head"><ha-icon icon="mdi:cash"></ha-icon>Price</div>
            ${typeof p.current_price === "number"
              ? html`<div class="big">${this._money(p.current_price, p.price_currency)}</div>
                  ${lowest && prices.length > 1 ? html`<div class="muted small">Lowest ${this._money(lowest.price, lowest.currency)}${lowest.store ? ` at ${lowest.store}` : ""}</div>` : nothing}
                  ${prices.length > 1 ? html`<ul class="history">${prices.map((e) => html`<li>
                    <span>${new Date(e.timestamp).toLocaleDateString(this._lang)}${e.store ? ` \u00b7 ${e.store}` : ""}</span>
                    <span>${this._money(e.price, e.currency)}</span></li>`)}</ul>` : nothing}`
              : html`<div class="muted small">No price recorded</div>`}
            <form class="inline-form" @submit=${(e) => { e.preventDefault(); this._addPrice(e.target); }}>
              <input name="price" type="number" step="0.01" min="0" inputmode="decimal" placeholder="Price" aria-label="Price" />
              <input name="store" type="text" placeholder="Store" aria-label="Store" />
              <button class="tonal-button" type="submit"><span class="label">Add</span></button>
            </form>
          </div>
          <div class="data-block">
            <div class="data-head"><ha-icon icon="mdi:calendar-clock"></ha-icon>Expiry</div>
            ${p.expiry_date
              ? html`<div class="big">${new Date(`${p.expiry_date.slice(0, 10)}T00:00:00`).toLocaleDateString(this._lang)}</div>
                  <div class="small ${days < 0 ? "bad-text" : days <= 2 ? "warn-text" : "muted"}">${expiryText(days)}</div>`
              : html`<div class="muted small">No date set</div>`}
            <div class="inline-form">
              <input type="date" aria-label="Expiry date" .value=${p.expiry_date ? p.expiry_date.slice(0, 10) : ""}
                @change=${(e) => this._setExpiry(e.target)} />
            </div>
          </div>
        </div>
        ${p.notes ? html`<div class="note"><ha-icon icon="mdi:note-text-outline"></ha-icon><span>${p.notes}</span></div>` : nothing}
      </section>`;
    }

    _renderEdit() {
      const e = this._editing;
      const set = (attr, value) => (this._editing = { ...e, values: { ...e.values, [attr]: value } });
      const field = ([attr, , label, type]) =>
        type === "textarea"
          ? html`<label class="field wide"><span>${label}</span>
              <textarea rows="3" .value=${String(e.values[attr] ?? "")} @input=${(ev) => set(attr, ev.target.value)}></textarea></label>`
          : html`<label class="field ${type === "number" ? "" : "wide"}"><span>${label}</span>
              <input type=${type} step="any" min="0" .value=${String(e.values[attr] ?? "")} @input=${(ev) => set(attr, ev.target.value)} /></label>`;
      const [basics, nutrition] = [EDIT_FIELDS.slice(0, 5), EDIT_FIELDS.slice(5, 13)];
      return html`<form class="edit" @submit=${(ev) => { ev.preventDefault(); this._saveEdit(); }}>
        <div class="fields">${basics.map(field)}</div>
        <h3>Nutrition <span class="muted">per 100 g or 100 ml</span></h3>
        <div class="fields">${nutrition.map(field)}</div>
        <div class="fields">${field(EDIT_FIELDS[13])}</div>
        <label class="switch-row">
          <input type="checkbox" .checked=${e.submit} @change=${(ev) => (this._editing = { ...e, submit: ev.target.checked })} />
          <span>Also send what I entered to OpenFoodFacts</span>
        </label>
        <div class="edit-actions">
          <button type="button" class="text-button" @click=${() => (this._editing = null)}>Cancel</button>
          <button type="submit" class="filled-button" ?disabled=${this._busy}>
            ${this._busy ? html`<span class="spinner"></span>` : html`<ha-icon icon="mdi:content-save-outline"></ha-icon>`}
            <span class="label">Save</span>
          </button>
        </div>
      </form>`;
    }

    /* ------------------------------------------------------------------ */
    /* Styles                                                              */
    /* ------------------------------------------------------------------ */

    static get styles() {
      return css`
        /* ---------------------------------------------------------------- *
         * Tokens. Two looks share every rule below:
         *   default  Home Assistant: theme font, card surface, regular weights
         *   home     the Home suite: --home-* tokens, light type, flat panels
         * Anything set as --home-* in a theme flows through to the Home look.
         * ---------------------------------------------------------------- */
        :host {
          --sa-font: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, "Noto Sans", sans-serif));
          --sa-accent: var(--primary-color, #03a9f4);
          --sa-on-accent: var(--text-primary-color, #fff);
          --sa-text: var(--primary-text-color, #212121);
          --sa-muted: var(--secondary-text-color, #727272);
          --sa-line: var(--divider-color, rgba(0, 0, 0, 0.12));
          --sa-panel: var(--secondary-background-color, rgba(127, 140, 158, 0.12));
          --sa-press: rgba(127, 140, 158, 0.18);
          --sa-radius: 12px;
          --sa-radius-lg: var(--ha-card-border-radius, 12px);
          --sa-pad: 16px;
          --sa-good: var(--success-color, #43a047);
          --sa-warn: var(--warning-color, #ffa600);
          --sa-bad: var(--error-color, #db4437);
          --sa-violet: #7c5cf0;
          --sa-cyan: #22c4ee;
          --sa-green: #34c98e;

          --sa-title-size: 1.25rem;    --sa-title-weight: 400;  --sa-title-line: 1.3;  --sa-title-track: 0;
          --sa-subtitle-size: 0.875rem; --sa-subtitle-weight: 400; --sa-subtitle-line: 1.35;
          --sa-heading-size: 1.05rem;  --sa-heading-weight: 500; --sa-heading-line: 1.3;
          --sa-metric-size: 1.25rem;   --sa-metric-weight: 400;  --sa-metric-line: 1.2;
          --sa-body-size: 0.875rem;    --sa-body-weight: 400;    --sa-body-line: 1.5;
          --sa-label-size: 0.9rem;     --sa-label-weight: 500;   --sa-label-line: 1.3;
          --sa-caption-size: 0.78rem;  --sa-caption-weight: 400; --sa-caption-line: 1.3;
          --sa-overline-size: 0.72rem; --sa-overline-weight: 500; --sa-overline-line: 1.2; --sa-overline-track: 0.04em;
          --sa-emphasis-weight: 600;
          --sa-button-bg: var(--sa-accent);
          --sa-button-fg: var(--sa-on-accent);

          display: block;
          font-family: var(--sa-font);
          color: var(--sa-text);
        }

        :host([sa-style="home"]) {
          --sa-font: var(--home-font, var(--metro-font-family, "Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", Roboto, system-ui, sans-serif));
          --sa-accent: var(--home-accent, var(--primary-color, #22c4ee));
          --sa-panel: var(--home-panel, rgba(127, 140, 158, 0.09));
          --sa-press: var(--home-press, rgba(127, 140, 158, 0.16));
          --sa-line: var(--home-line, rgba(127, 140, 158, 0.16));
          --sa-radius: var(--home-radius, 12px);
          --sa-radius-lg: var(--home-radius-lg, 18px);

          --sa-title-size: var(--home-title-size, 1.45rem);
          --sa-title-weight: var(--home-title-weight, 300);
          --sa-title-line: var(--home-title-line, 1.25);
          --sa-title-track: var(--home-title-track, -0.02em);
          --sa-subtitle-size: var(--home-subtitle-size, 0.8rem);
          --sa-subtitle-weight: var(--home-subtitle-weight, 300);
          --sa-subtitle-line: var(--home-subtitle-line, 1.35);
          --sa-heading-size: var(--home-heading-size, 1.08rem);
          --sa-heading-weight: var(--home-heading-weight, 500);
          --sa-heading-line: var(--home-heading-line, 1.25);
          --sa-metric-size: var(--home-metric-size, 1.25rem);
          --sa-metric-weight: var(--home-metric-weight, 300);
          --sa-metric-line: var(--home-metric-line, 1.2);
          --sa-body-size: var(--home-body-size, 0.875rem);
          --sa-body-weight: var(--home-body-weight, 300);
          --sa-body-line: var(--home-body-line, 1.5);
          --sa-label-size: var(--home-label-size, 0.82rem);
          --sa-label-weight: var(--home-label-weight, 500);
          --sa-label-line: var(--home-label-line, 1.25);
          --sa-caption-size: var(--home-caption-size, 0.75rem);
          --sa-caption-weight: var(--home-caption-weight, 300);
          --sa-caption-line: var(--home-caption-line, 1.25);
          --sa-overline-size: var(--home-overline-size, 0.7rem);
          --sa-overline-weight: var(--home-overline-weight, 400);
          --sa-overline-line: var(--home-overline-line, 1.2);
          --sa-overline-track: var(--home-overline-track, 0.06em);
          --sa-emphasis-weight: var(--home-emphasis-weight, 600);
          --sa-button-bg: color-mix(in srgb, var(--sa-accent) 22%, transparent);
          --sa-button-fg: var(--sa-text);
        }

        /* Surface */
        ha-card { overflow: hidden; color: var(--sa-text); font-family: var(--sa-font); }
        :host([sa-surface="flat"]) ha-card {
          --ha-card-background: transparent;
          --ha-card-box-shadow: none;
          --ha-card-border-width: 0;
          background: none;
          box-shadow: none;
          border: none;
          border-radius: 0;
        }

        /* Base */
        button { font: inherit; color: inherit; cursor: pointer; -webkit-tap-highlight-color: transparent; }
        button:disabled { cursor: default; opacity: 0.45; }
        button:focus-visible, input:focus-visible, textarea:focus-visible, a:focus-visible {
          outline: 2px solid var(--sa-accent); outline-offset: 2px;
        }
        ha-icon { --mdc-icon-size: var(--home-icon-size, 20px); display: inline-flex; }
        code { font-family: var(--code-font-family, ui-monospace, monospace); font-size: 0.92em; }
        .muted { color: var(--sa-muted); font-weight: var(--sa-caption-weight); }
        .small { font-size: var(--sa-caption-size); }
        .spacer { width: 40px; }
        .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--sa-accent); flex: 0 0 auto; }
        .dot.violet { background: var(--sa-violet); }
        .dot.cyan { background: var(--sa-cyan); }
        .dot.green { background: var(--sa-green); }

        /* Header */
        .header { display: flex; align-items: center; gap: 12px; padding: var(--sa-pad) calc(var(--sa-pad) - 4px) 8px var(--sa-pad); }
        .header-icon {
          width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; flex: 0 0 auto;
          background: color-mix(in srgb, var(--sa-accent) 16%, transparent); color: var(--sa-accent);
        }
        .header-text { flex: 1; min-width: 0; }
        .title {
          font-size: var(--sa-title-size); font-weight: var(--sa-title-weight);
          line-height: var(--sa-title-line); letter-spacing: var(--sa-title-track);
        }
        .subtitle {
          margin-top: 2px; font-size: var(--sa-subtitle-size); font-weight: var(--sa-subtitle-weight);
          line-height: var(--sa-subtitle-line); color: var(--sa-muted);
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .status-chip {
          display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border-radius: 999px; border: none;
          background: color-mix(in srgb, var(--sa-warn) 18%, transparent); color: var(--sa-text);
          font-size: var(--sa-caption-size); font-weight: var(--sa-label-weight);
        }
        .status-chip ha-icon { --mdc-icon-size: 16px; color: var(--sa-warn); }

        /* Buttons */
        .icon-button {
          width: 40px; height: 40px; border: none; border-radius: 50%; background: transparent;
          display: inline-grid; place-items: center; flex-shrink: 0; color: var(--sa-muted);
        }
        .icon-button:hover:not(:disabled) { background: var(--sa-press); color: var(--sa-text); }
        .icon-button.small { width: 32px; height: 32px; }
        .icon-button.small ha-icon { --mdc-icon-size: 18px; }
        .icon-button.accent { color: var(--sa-accent); }
        .icon-button.light { color: #fff; }
        .filled-button, .tonal-button, .text-button {
          display: inline-flex; align-items: center; justify-content: center; gap: 6px; height: 40px; padding: 0 16px;
          border: none; border-radius: 999px; white-space: nowrap; flex-shrink: 0;
          font-size: var(--sa-label-size); font-weight: var(--sa-label-weight);
        }
        .filled-button { background: var(--sa-button-bg); color: var(--sa-button-fg); }
        .filled-button ha-icon { color: inherit; }
        :host([sa-style="home"]) .filled-button ha-icon { color: var(--sa-accent); }
        .tonal-button { background: var(--sa-panel); color: var(--sa-text); height: 36px; padding: 0 14px; }
        .tonal-button ha-icon { color: var(--sa-accent); }
        .text-button { background: transparent; color: var(--sa-accent); }
        .filled-button:hover:not(:disabled), .tonal-button:hover:not(:disabled) { filter: brightness(1.1); }
        .spinner {
          width: 16px; height: 16px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Input */
        .input-row { display: flex; gap: 8px; padding: 8px var(--sa-pad); }
        .search-field {
          flex: 1; min-width: 0; display: flex; align-items: center; gap: 4px; height: 48px; padding: 0 4px 0 14px;
          border-radius: 999px; background: var(--sa-panel); border: 1px solid transparent; transition: border-color 0.15s;
        }
        .search-field:focus-within { border-color: var(--sa-accent); }
        .search-field.busy { opacity: 0.7; }
        .field-icon { color: var(--sa-muted); }
        .search-field input {
          flex: 1; min-width: 0; height: 100%; border: none; background: transparent; outline: none; padding: 0;
          font-size: var(--sa-body-size); font-weight: var(--sa-body-weight); color: var(--sa-text); letter-spacing: 0.02em;
        }
        .input-row > .filled-button { height: 48px; }
        input, textarea {
          font: inherit; font-size: var(--sa-body-size); font-weight: var(--sa-body-weight); color: var(--sa-text);
          background: var(--sa-panel); border: 1px solid transparent; border-radius: var(--sa-radius); padding: 0 12px; min-width: 0;
        }
        input { height: 40px; }
        textarea { padding: 8px 12px; resize: vertical; line-height: var(--sa-body-line); }
        input:focus, textarea:focus { border-color: var(--sa-accent); outline: none; }
        input::placeholder, textarea::placeholder { color: var(--sa-muted); opacity: 0.8; }
        .mini-search input { border: none; padding: 0; background: transparent; }

        /* Result banner */
        .result {
          margin: 4px var(--sa-pad) 8px; padding: 10px 6px 10px 12px; border-radius: var(--sa-radius);
          display: flex; flex-direction: column; gap: 8px; animation: rise 0.2s ease-out;
          font-size: var(--sa-body-size); font-weight: var(--sa-body-weight); line-height: var(--sa-body-line);
        }
        .result strong { font-weight: var(--sa-label-weight); }
        .result.success, .result.warning { flex-direction: row; align-items: center; }
        .result-head { display: flex; align-items: center; gap: 8px; }
        .result-text { flex: 1; min-width: 0; }
        .result.success { background: color-mix(in srgb, var(--sa-good) 14%, transparent); }
        .result.success > ha-icon { color: var(--sa-good); }
        .result.warning { background: color-mix(in srgb, var(--sa-warn) 16%, transparent); }
        .result.warning > ha-icon { color: var(--sa-warn); }
        .result.unknown { background: color-mix(in srgb, var(--sa-accent) 10%, transparent); padding-right: 12px; }
        .result.unknown .result-head > ha-icon { color: var(--sa-accent); }
        .name-form { display: flex; gap: 8px; }
        .name-form input { flex: 1; }
        @keyframes rise { from { opacity: 0; transform: translateY(-4px); } }

        /* Tabs */
        .tabs { display: flex; gap: 4px; padding: 4px var(--sa-pad) 0; border-bottom: 1px solid var(--sa-line); }
        .tab {
          position: relative; display: inline-flex; align-items: center; gap: 6px; height: 42px; padding: 0 10px;
          border: none; background: transparent; color: var(--sa-muted);
          font-size: var(--sa-label-size); font-weight: var(--sa-label-weight);
        }
        .tab.active { color: var(--sa-text); }
        .tab.active::after {
          content: ""; position: absolute; left: 6px; right: 6px; bottom: -1px; height: 2px; border-radius: 2px; background: var(--sa-accent);
        }
        .count {
          min-width: 18px; height: 18px; padding: 0 6px; border-radius: 9px; display: inline-grid; place-items: center;
          font-size: var(--sa-overline-size); font-weight: var(--sa-label-weight); background: var(--sa-panel); color: var(--sa-text);
        }
        .count.alert { background: var(--sa-accent); color: var(--sa-on-accent); }
        .tab-body { padding: 8px 0; }

        /* Toolbar */
        .toolbar { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 8px; padding: 4px var(--sa-pad) 8px; }
        .toolbar .mini-search { grid-column: 1 / -1; }
        .mini-search { display: flex; align-items: center; gap: 8px; height: 36px; padding: 0 12px; border-radius: 999px; background: var(--sa-panel); }
        .mini-search ha-icon { --mdc-icon-size: 18px; color: var(--sa-muted); }
        .mini-search input { flex: 1; height: 100%; outline: none; }
        .chips { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; min-width: 0; mask-image: linear-gradient(90deg, #000 90%, transparent); }
        .chips::-webkit-scrollbar { display: none; }
        .chip {
          display: inline-flex; align-items: center; gap: 4px; height: 30px; padding: 0 12px; border-radius: 999px;
          border: none; background: var(--sa-panel); white-space: nowrap;
          font-size: var(--sa-caption-size); font-weight: var(--sa-label-weight); color: var(--sa-muted);
        }
        .chip ha-icon { --mdc-icon-size: 15px; }
        .chip.selected { background: color-mix(in srgb, var(--sa-accent) 20%, transparent); color: var(--sa-text); }
        .sort-button {
          width: 30px; height: 30px; border-radius: 50%; border: none; background: var(--sa-panel);
          display: grid; place-items: center; color: var(--sa-muted);
        }
        .sort-button ha-icon { --mdc-icon-size: 17px; }

        /* Rows */
        .list { display: flex; flex-direction: column; }
        .row-wrap { position: relative; overflow: hidden; }
        .swipe-bg {
          position: absolute; inset: 0; display: flex; align-items: center; justify-content: flex-end; gap: 6px; padding-right: 24px;
          background: var(--sa-panel); color: var(--sa-muted); font-size: var(--sa-caption-size); font-weight: var(--sa-label-weight);
          transition: background 0.15s, color 0.15s;
        }
        .row-wrap.armed .swipe-bg { background: var(--sa-good); color: #fff; }
        .row {
          position: relative; display: flex; align-items: center; gap: 12px; padding: 10px var(--sa-pad); min-height: 64px;
          background: var(--ha-card-background, var(--card-background-color, transparent)); transition: transform 0.2s ease, opacity 0.2s;
        }
        :host([sa-surface="flat"]) .row { background: var(--primary-background-color, var(--lovelace-background, transparent)); }
        .row.pending { opacity: 0.5; }
        .row-wrap + .row-wrap .row { border-top: 1px solid var(--sa-line); }
        .thumb {
          width: 48px; height: 48px; flex-shrink: 0; border-radius: var(--sa-radius); border: none; padding: 0; overflow: hidden;
          background: #fff; display: grid; place-items: center; color: #9e9e9e;
        }
        :host([sa-style="home"]) .thumb { background: var(--sa-panel); color: var(--sa-muted); }
        .thumb img { width: 100%; height: 100%; object-fit: contain; background: #fff; }
        .row-main {
          flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; align-items: flex-start; text-align: left;
          border: none; background: transparent; padding: 2px 0;
        }
        .row-title {
          font-size: var(--sa-label-size); font-weight: var(--sa-label-weight); line-height: var(--sa-label-line);
          max-width: 100%; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow-wrap: anywhere;
        }
        .row-meta {
          font-size: var(--sa-caption-size); font-weight: var(--sa-caption-weight); line-height: var(--sa-caption-line); color: var(--sa-muted);
          max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .row-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-top: 3px; }
        .row-tags:empty { display: none; }
        .score-pill, .nova {
          display: inline-flex; align-items: center; gap: 3px; height: 18px; padding: 0 6px; border-radius: 6px;
          font-size: var(--sa-overline-size); font-weight: var(--sa-emphasis-weight); line-height: 1;
          background: var(--score); color: var(--score-fg, #fff);
        }
        :host([sa-style="home"]) .score-pill, :host([sa-style="home"]) .nova {
          gap: 5px; background: var(--sa-panel); color: var(--sa-text); font-weight: var(--sa-label-weight);
        }
        :host([sa-style="home"]) .score-pill::before, :host([sa-style="home"]) .nova::before {
          content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--score);
        }
        .score-kind { font-weight: var(--sa-caption-weight); opacity: 0.9; }
        .diet { display: inline-grid; place-items: center; width: 20px; height: 18px; border-radius: 6px; background: color-mix(in srgb, var(--sa-good) 18%, transparent); color: var(--sa-good); }
        .diet ha-icon { --mdc-icon-size: 13px; }
        .expiry {
          height: 18px; padding: 0 6px; border-radius: 6px; display: inline-flex; align-items: center; background: var(--sa-panel);
          font-size: var(--sa-overline-size); font-weight: var(--sa-label-weight);
        }
        .expiry.warn { background: color-mix(in srgb, var(--sa-warn) 22%, transparent); }
        .expiry.bad { background: color-mix(in srgb, var(--sa-bad) 20%, transparent); color: var(--sa-bad); }
        .stepper { display: flex; align-items: center; gap: 2px; flex-shrink: 0; background: var(--sa-panel); border-radius: 999px; padding: 2px; }
        .step { width: 30px; height: 30px; border-radius: 50%; border: none; background: transparent; display: grid; place-items: center; color: var(--sa-muted); }
        .step:hover:not(:disabled) { background: var(--sa-press); color: var(--sa-text); }
        .step ha-icon { --mdc-icon-size: 17px; }
        .qty { min-width: 18px; text-align: center; font-size: var(--sa-label-size); font-weight: var(--sa-label-weight); font-variant-numeric: tabular-nums; }
        .qty-text { padding: 0 10px; font-size: var(--sa-caption-size); font-weight: var(--sa-label-weight); line-height: 30px; }
        .check {
          width: 38px; height: 38px; flex-shrink: 0; border-radius: 50%; border: 1.5px solid var(--sa-line); background: transparent;
          display: grid; place-items: center; color: var(--sa-muted); transition: all 0.15s;
        }
        .check ha-icon { --mdc-icon-size: 18px; }
        .check:hover:not(:disabled) { border-color: var(--sa-good); background: var(--sa-good); color: #fff; }
        .total {
          display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin: 8px var(--sa-pad) 0; padding: 12px 0 4px;
          border-top: 1px solid var(--sa-line); font-size: var(--sa-body-size); font-weight: var(--sa-body-weight);
        }
        .total strong { font-size: var(--sa-metric-size); font-weight: var(--sa-metric-weight); font-variant-numeric: tabular-nums; }

        /* Unknown and expiring rows */
        .unknown-row { display: flex; flex-direction: column; gap: 8px; padding: 12px var(--sa-pad); }
        .unknown-row + .unknown-row { border-top: 1px solid var(--sa-line); }
        .unknown-head { display: flex; align-items: center; gap: 10px; }
        .unknown-head code { font-size: var(--sa-label-size); font-weight: var(--sa-label-weight); }
        .unknown-head .muted { flex: 1; font-size: var(--sa-caption-size); }
        .expiring-row { display: flex; align-items: center; gap: 12px; padding: 10px var(--sa-pad); min-height: 60px; }
        .expiring-row + .expiring-row { border-top: 1px solid var(--sa-line); }
        .days {
          width: 48px; height: 48px; border-radius: var(--sa-radius); flex-shrink: 0; display: flex; flex-direction: column;
          align-items: center; justify-content: center; background: var(--sa-panel); line-height: 1;
        }
        .days strong { font-size: var(--sa-metric-size); font-weight: var(--sa-metric-weight); }
        .days small { font-size: var(--sa-overline-size); color: var(--sa-muted); margin-top: 3px; }
        .days.warn { background: color-mix(in srgb, var(--sa-warn) 22%, transparent); }
        .days.bad { background: color-mix(in srgb, var(--sa-bad) 20%, transparent); color: var(--sa-bad); }

        /* Empty */
        .empty-state { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 6px; padding: 32px 24px; }
        .empty-state ha-icon { --mdc-icon-size: 36px; color: var(--sa-muted); opacity: 0.6; margin-bottom: 4px; }
        .empty-title { font-size: var(--sa-heading-size); font-weight: var(--sa-heading-weight); line-height: var(--sa-heading-line); }
        .empty-text { color: var(--sa-muted); font-size: var(--sa-body-size); font-weight: var(--sa-body-weight); line-height: var(--sa-body-line); max-width: 320px; }
        .empty-inline { padding: 24px var(--sa-pad); text-align: center; color: var(--sa-muted); font-size: var(--sa-caption-size); }

        /* Stats, laid out like a readout row: dot and figure, label under */
        .stats {
          display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px;
          margin: 4px var(--sa-pad) 0; padding: 14px 0 var(--sa-pad); border-top: 1px solid var(--sa-line);
        }
        .stat { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
        .stat:nth-child(2), .stat:nth-child(3) { justify-self: center; }
        .stat:last-child { justify-self: end; }
        .stat-value { display: inline-flex; align-items: center; gap: 7px; font-size: var(--sa-label-size); font-weight: var(--sa-label-weight); line-height: var(--sa-label-line); font-variant-numeric: tabular-nums; }
        .stat-label {
          display: block; max-width: 100%; padding-left: 14px; color: var(--sa-muted);
          font-size: var(--sa-overline-size); font-weight: var(--sa-overline-weight); letter-spacing: var(--sa-overline-track);
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }

        /* Overlays */
        .scrim {
          position: fixed; inset: 0; z-index: 9; background: rgba(6, 10, 16, 0.55); display: flex; align-items: flex-end; justify-content: center;
          animation: fade 0.15s ease-out; font-family: var(--sa-font);
        }
        .scrim.dark { background: rgba(0, 0, 0, 0.88); align-items: center; }
        @keyframes fade { from { opacity: 0; } }
        @keyframes slide { from { transform: translateY(24px); opacity: 0.6; } }
        .sheet, .dialog {
          --sa-surface: var(--ha-card-background, var(--card-background-color, #fff));
          background: var(--sa-surface); color: var(--sa-text);
        }
        :host([sa-style="home"]) .sheet, :host([sa-style="home"]) .dialog {
          --sa-surface: var(--home-surface, var(--ha-card-background, var(--card-background-color, #141b26)));
        }
        .sheet {
          width: 100%; max-width: 560px; border-radius: 28px 28px 0 0; padding: 8px 0 calc(16px + env(safe-area-inset-bottom));
          animation: slide 0.2s ease-out;
        }
        .handle { width: 32px; height: 4px; border-radius: 2px; background: var(--sa-line); margin: 8px auto 12px; }
        .sheet-item { width: 100%; display: flex; align-items: center; gap: 16px; padding: 12px 24px; border: none; background: transparent; text-align: left; }
        .sheet-item:hover:not(:disabled) { background: var(--sa-press); }
        .sheet-item span { display: flex; flex-direction: column; gap: 2px; }
        .sheet-item strong { font-size: var(--sa-label-size); font-weight: var(--sa-label-weight); }
        .sheet-item small { color: var(--sa-muted); font-size: var(--sa-caption-size); font-weight: var(--sa-caption-weight); }
        .sheet-item ha-icon { --mdc-icon-size: 22px; color: var(--sa-muted); }
        .sheet-item.danger strong, .sheet-item.danger ha-icon { color: var(--sa-bad); }
        .sheet-divider { height: 1px; background: var(--sa-line); margin: 8px 0; }

        .dialog {
          width: 100%; max-width: 640px; max-height: 92vh; display: flex; flex-direction: column;
          border-radius: var(--sa-radius-lg) var(--sa-radius-lg) 0 0; overflow: hidden; animation: slide 0.2s ease-out;
        }
        @media (min-width: 700px) {
          .scrim:not(.dark) { align-items: center; }
          .dialog { border-radius: var(--sa-radius-lg); max-height: 86vh; }
        }
        .dialog-bar { display: flex; align-items: center; gap: 4px; padding: 8px; border-bottom: 1px solid var(--sa-line); }
        .dialog-title { flex: 1; padding-left: 4px; font-size: var(--sa-heading-size); font-weight: var(--sa-heading-weight); }
        .progress { height: 2px; background: linear-gradient(90deg, transparent, var(--sa-accent), transparent); background-size: 50% 100%; animation: load 1s linear infinite; }
        @keyframes load { from { background-position: -50% 0; } to { background-position: 150% 0; } }
        .dialog-body { overflow-y: auto; padding: 18px 20px calc(24px + env(safe-area-inset-bottom)); display: flex; flex-direction: column; gap: 22px; }
        section { display: flex; flex-direction: column; gap: 10px; }
        h3 {
          margin: 0; display: flex; align-items: center; gap: 12px; color: var(--sa-muted);
          font-size: var(--sa-overline-size); font-weight: var(--sa-overline-weight); line-height: var(--sa-overline-line);
          letter-spacing: var(--sa-overline-track);
        }
        h3::after { content: ""; flex: 1 1 auto; height: 1px; background: var(--sa-line); }
        h3 .muted { font-size: var(--sa-overline-size); margin-left: -6px; opacity: 0.8; }

        .hero { display: flex; gap: 16px; align-items: flex-start; }
        .hero-img {
          width: 104px; height: 104px; flex-shrink: 0; border-radius: var(--sa-radius-lg); background: #fff; overflow: hidden;
          display: grid; place-items: center; color: #9e9e9e;
        }
        :host([sa-style="home"]) .hero-img { background: var(--sa-panel); color: var(--sa-muted); }
        .hero-img ha-icon { --mdc-icon-size: 40px; }
        .hero-img img { width: 100%; height: 100%; object-fit: contain; background: #fff; }
        .hero-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
        .hero-name {
          font-size: var(--sa-title-size); font-weight: var(--sa-title-weight); line-height: var(--sa-title-line);
          letter-spacing: var(--sa-title-track);
        }
        .hero-text .muted { font-size: var(--sa-body-size); }
        .hero-actions { margin-top: 10px; display: flex; gap: 8px; }

        .score-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 8px; }
        .score-tile {
          border-radius: var(--sa-radius); padding: 10px 12px; display: flex; flex-direction: column; gap: 4px;
          background: var(--score); color: var(--score-fg, #fff);
        }
        :host([sa-style="home"]) .score-tile { background: var(--sa-panel); color: var(--sa-text); position: relative; overflow: hidden; padding-bottom: 14px; }
        :host([sa-style="home"]) .score-tile span { color: var(--sa-muted); opacity: 1; }
        :host([sa-style="home"]) .score-tile strong { font-weight: var(--sa-metric-weight); }
        :host([sa-style="home"]) .score-tile::after {
          content: ""; position: absolute; left: 12px; right: 12px; bottom: 8px; height: 4px; border-radius: 999px; background: var(--score);
        }
        .score-tile span { font-size: var(--sa-overline-size); font-weight: var(--sa-label-weight); letter-spacing: var(--sa-overline-track); opacity: 0.9; }
        .score-tile strong { font-size: calc(var(--sa-metric-size) * 1.45); font-weight: var(--sa-emphasis-weight); line-height: 1; }
        .diet-row { display: flex; flex-wrap: wrap; gap: 6px; }
        .diet-chip {
          display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; border-radius: 999px; background: var(--sa-panel);
          font-size: var(--sa-caption-size); font-weight: var(--sa-label-weight);
        }
        .diet-chip ha-icon { --mdc-icon-size: 15px; }
        .diet-chip.yes { background: color-mix(in srgb, var(--sa-good) 16%, transparent); }
        .diet-chip.yes ha-icon { color: var(--sa-good); }
        .diet-chip.no ha-icon { color: var(--sa-bad); }

        /* Nutrition bars, the same build as the readout bars elsewhere on the dashboard */
        .meters { display: flex; flex-direction: column; gap: 10px; }
        .meter { --hue: var(--sa-violet); }
        .meter.low { --hue: var(--sa-green); }
        .meter.medium { --hue: var(--sa-warn); }
        .meter.high { --hue: var(--sa-bad); }
        .meter.sub { padding-left: 16px; }
        .meter-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 5px; }
        .meter-name { flex: 1; font-size: var(--sa-label-size); font-weight: var(--sa-label-weight); line-height: var(--sa-label-line); }
        .meter.sub .meter-name { font-weight: var(--sa-caption-weight); color: var(--sa-muted); }
        .meter-level {
          font-size: var(--sa-overline-size); font-weight: var(--sa-overline-weight); letter-spacing: var(--sa-overline-track);
          color: var(--hue);
        }
        .meter-value { font-size: var(--sa-label-size); font-weight: var(--sa-label-weight); font-variant-numeric: tabular-nums; min-width: 4.5em; text-align: right; }
        .track { height: 6px; border-radius: 999px; background: var(--sa-panel); overflow: hidden; }
        .fill { height: 100%; border-radius: 999px; background: var(--hue); transition: width 760ms cubic-bezier(0.2, 0, 0, 1); }

        .micro-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; }
        .micro { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px; border-radius: var(--sa-radius); background: var(--sa-panel); }
        .micro span { font-size: var(--sa-caption-size); font-weight: var(--sa-caption-weight); color: var(--sa-muted); }
        .micro strong { font-size: var(--sa-label-size); font-weight: var(--sa-label-weight); font-variant-numeric: tabular-nums; }
        .note {
          display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border-radius: var(--sa-radius); background: var(--sa-panel);
          font-size: var(--sa-body-size); font-weight: var(--sa-body-weight); line-height: var(--sa-body-line);
        }
        .note strong { font-weight: var(--sa-label-weight); }
        .note ha-icon { --mdc-icon-size: 18px; color: var(--sa-muted); margin-top: 2px; }
        .note.warn { background: color-mix(in srgb, var(--sa-warn) 16%, transparent); }
        .note.warn ha-icon { color: var(--sa-warn); }
        .text { margin: 0; font-size: var(--sa-body-size); font-weight: var(--sa-body-weight); line-height: var(--sa-body-line); max-width: var(--home-measure, 70ch); }
        .labels { display: flex; flex-wrap: wrap; gap: 6px; }
        .label-chip { padding: 4px 10px; border-radius: 999px; background: var(--sa-panel); font-size: var(--sa-caption-size); font-weight: var(--sa-caption-weight); }
        .info-row {
          display: grid; grid-template-columns: 22px 130px 1fr; gap: 8px; align-items: center; padding: 3px 0;
          font-size: var(--sa-body-size); font-weight: var(--sa-body-weight);
        }
        .info-row ha-icon { --mdc-icon-size: 18px; color: var(--sa-muted); }

        .your-data { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
        .data-block { border-radius: var(--sa-radius); padding: 12px; display: flex; flex-direction: column; gap: 6px; background: var(--sa-panel); }
        .data-block input { background: var(--ha-card-background, var(--card-background-color, transparent)); }
        :host([sa-style="home"]) .data-block input { background: rgba(127, 140, 158, 0.1); }
        .data-head { display: flex; align-items: center; gap: 6px; color: var(--sa-muted); font-size: var(--sa-overline-size); font-weight: var(--sa-overline-weight); letter-spacing: var(--sa-overline-track); }
        .data-head ha-icon { --mdc-icon-size: 16px; }
        .big { font-size: var(--sa-metric-size); font-weight: var(--sa-metric-weight); line-height: var(--sa-metric-line); font-variant-numeric: tabular-nums; }
        .history { list-style: none; margin: 4px 0 0; padding: 0; font-size: var(--sa-caption-size); font-weight: var(--sa-caption-weight); }
        .history li { display: flex; justify-content: space-between; padding: 3px 0; color: var(--sa-muted); }
        .inline-form { display: flex; gap: 6px; margin-top: 6px; }
        .inline-form input { flex: 1; height: 36px; }
        .inline-form input[name="price"] { max-width: 90px; }
        .warn-text { color: var(--sa-warn); }
        .bad-text { color: var(--sa-bad); }
        .off-link {
          display: inline-flex; align-items: center; gap: 6px; color: var(--sa-accent); text-decoration: none; align-self: flex-start;
          font-size: var(--sa-label-size); font-weight: var(--sa-label-weight);
        }
        .off-link ha-icon { --mdc-icon-size: 16px; }

        .edit { display: flex; flex-direction: column; gap: 14px; }
        .fields { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
        .field {
          display: flex; flex-direction: column; gap: 5px; color: var(--sa-muted);
          font-size: var(--sa-overline-size); font-weight: var(--sa-overline-weight); letter-spacing: var(--sa-overline-track);
        }
        .field.wide { grid-column: 1 / -1; }
        .field input, .field textarea { letter-spacing: normal; }
        .switch-row { display: flex; align-items: center; gap: 10px; font-size: var(--sa-body-size); font-weight: var(--sa-body-weight); }
        .switch-row input { width: 18px; height: 18px; accent-color: var(--sa-accent); }
        .edit-actions { display: flex; justify-content: flex-end; gap: 8px; }

        /* Scanner */
        .scanner { width: 100%; max-width: 520px; display: flex; flex-direction: column; color: #fff; }
        .scanner-bar { display: flex; align-items: center; padding: 8px; }
        .scanner-title { flex: 1; text-align: center; font-size: var(--sa-heading-size); font-weight: var(--sa-heading-weight); }
        .viewfinder { position: relative; aspect-ratio: 4 / 3; background: #000; overflow: hidden; border-radius: var(--sa-radius-lg); margin: 0 12px; }
        .viewfinder video { width: 100%; height: 100%; object-fit: cover; }
        .frame {
          position: absolute; left: 12%; right: 12%; top: 30%; bottom: 30%; border-radius: 14px;
          box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.45); border: 2px solid rgba(255, 255, 255, 0.85);
        }
        .laser { position: absolute; left: 6%; right: 6%; top: 50%; height: 2px; background: var(--sa-accent); box-shadow: 0 0 8px var(--sa-accent); animation: sweep 1.6s ease-in-out infinite alternate; }
        @keyframes sweep { from { top: 15%; } to { top: 85%; } }
        .scanner-error { position: absolute; inset: auto 16px 16px; padding: 10px 14px; border-radius: 12px; background: rgba(0, 0, 0, 0.75); text-align: center; }
        .scanner-footer { display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; }
        .scanner-footer .switch-row { color: #fff; }
        .hint { color: rgba(255, 255, 255, 0.7); font-size: var(--sa-caption-size); text-align: center; }
        .scanned { display: flex; flex-wrap: wrap; gap: 6px; }
        .scanned code { padding: 4px 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.15); }

        /* Narrow placements are measured against the card, not the window */
        :host { container-type: inline-size; container-name: shopping; }
        @container shopping (max-width: 420px) {
          .status-chip span { display: none; }
          .status-chip { width: 30px; padding: 0; justify-content: center; }
          .step { width: 26px; height: 26px; }
          .check { width: 34px; height: 34px; }
          .input-row > .filled-button .label { display: none; }
          .input-row > .filled-button { width: 48px; padding: 0; }
          .row { gap: 10px; }
          .thumb { width: 42px; height: 42px; }
          .info-row { grid-template-columns: 22px 1fr; }
          .info-row span:last-child { grid-column: 2; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; transition: none !important; }
        }
      `;
    }
  }

  customElements.define("shopping-assistant-card", ShoppingAssistantCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "shopping-assistant-card",
    name: "Shopping Assistant",
    preview: true,
    description: "Scan barcodes, manage the shopping list and see product details from OpenFoodFacts.",
    documentationURL: "https://github.com/swetoast/ha-shopping-assistant",
  });
  console.info(`%c SHOPPING-ASSISTANT-CARD %c ${CARD_VERSION} `, "color:#fff;background:#03a9f4;font-weight:700", "color:#03a9f4");
}

// Lit comes from Home Assistant's dashboard code. The integration loads this
// file when the app starts, possibly before that code exists, so wait for it.
// The extra checks skip a second copy added as a dashboard resource.
customElements.whenDefined("ha-panel-lovelace").then(() => {
  if (!customElements.get("shopping-assistant-card")) {
    defineCard(Object.getPrototypeOf(customElements.get("ha-panel-lovelace")));
  }
});
