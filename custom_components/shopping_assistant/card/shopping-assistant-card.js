/* Shopping Assistant card for Home Assistant
 * Companion card for the shopping_assistant integration.
 * https://github.com/swetoast/ha-shopping-assistant
 */

const CARD_VERSION = "4.0.0";
const DOMAIN = "shopping_assistant";
const OFF_PRODUCT_URL = "https://world.openfoodfacts.org/product/";

const nothing = "";

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
        show_scanner: true,
        show_filters: true,
        show_totals: true,
        show_stats: true,
        scan_action: "add",
        ...config,
      };
    }

    static getStubConfig() {
      return { type: "custom:shopping-assistant-card" };
    }

    static getConfigForm() {
      return {
        schema: [
          { name: "title", selector: { text: {} } },
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
      if (!old || old.locale !== this.hass.locale || old.themes !== this.hass.themes) return true;
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
          <div class="header-icon"><ha-icon icon="mdi:cart-outline"></ha-icon></div>
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
      return html`<span class="score-pill" style="background:${bg};color:${fg}" title="${kind} ${gradeLabel(grade)}">
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
                ${p.nova_group ? html`<span class="nova" style="background:${NOVA_COLORS[p.nova_group] || "#888"}" title="NOVA group ${p.nova_group}">NOVA ${p.nova_group}</span>` : nothing}
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
        ["mdi:barcode-scan", "Scans", stats.state],
        ["mdi:database-outline", "Products", a.total_mappings],
        ["mdi:web", "Online", a.openfoodfacts_hits],
        ["mdi:home-outline", "Local", a.local_hits],
      ];
      const tips = {
        Online: "Products found in OpenFoodFacts",
        Local: "Scans answered from your own product list",
      };
      return html`<div class="stats">
        ${items.map(([icon, label, value]) => html`<div class="stat" title=${tips[label] || label}>
          <ha-icon icon=${icon}></ha-icon><strong>${value ?? 0}</strong><span>${label}</span>
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
          <div class="score-tile" style="background:${bg};color:${fg}"><span>${label}</span><strong>${value}</strong></div>`)}</div>` : nothing}
        ${diet.length ? html`<div class="diet-row">${diet.map(([label, value, icon]) => html`
          <span class="diet-chip ${value}"><ha-icon icon=${value === "yes" ? icon : value === "no" ? "mdi:close" : "mdi:help"}></ha-icon>
            ${value === "no" ? `Not ${label.toLowerCase()}` : value === "maybe" ? `${label}?` : label}</span>`)}</div>` : nothing}
      </section>`;
    }

    _renderNutrition(p) {
      const rows = NUTRITION_ROWS.filter(([key]) => typeof p[key] === "number");
      if (!rows.length) return nothing;
      const liquid = p.nutrition_per === "100ml";
      const level = (key, value) => {
        const limits = TRAFFIC_LIGHTS[key]?.[liquid ? "ml" : "g"];
        if (!limits) return null;
        return value <= limits[0] ? "low" : value > limits[1] ? "high" : "medium";
      };
      const per = liquid ? "100 ml" : "100 g";
      return html`<section>
        <h3>Nutrition <span class="muted">per ${per}${p.nutrition_preparation === "prepared" ? ", prepared" : ""}</span></h3>
        <div class="nutrition">
          ${rows.map(([key, label, unit, indent]) => {
            const value = p[key];
            const lvl = level(key, value);
            return html`<div class="nutri-row ${indent ? "sub" : ""}">
              <span>${label}</span>
              ${lvl ? html`<span class="level ${lvl}">${lvl}</span>` : html`<span></span>`}
              <strong>${this._num(value, unit === "kcal" ? 0 : 1)} ${unit}</strong>
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
        :host {
          --sa-radius: var(--ha-card-border-radius, 12px);
          --sa-surface: var(--card-background-color, var(--ha-card-background, #fff));
          --sa-surface-2: var(--secondary-background-color, #f2f2f2);
          --sa-accent: var(--primary-color, #03a9f4);
          --sa-on-accent: var(--text-primary-color, #fff);
          --sa-text: var(--primary-text-color, #212121);
          --sa-muted: var(--secondary-text-color, #727272);
          --sa-line: var(--divider-color, rgba(0, 0, 0, 0.12));
          --sa-good: var(--success-color, #43a047);
          --sa-warn: var(--warning-color, #ffa600);
          --sa-bad: var(--error-color, #db4437);
          --sa-hover: rgba(127, 127, 127, 0.12);
          display: block;
        }
        ha-card { overflow: hidden; color: var(--sa-text); }
        button { font: inherit; color: inherit; cursor: pointer; }
        button:disabled { cursor: default; opacity: 0.45; }
        button:focus-visible, input:focus-visible, textarea:focus-visible, a:focus-visible {
          outline: 2px solid var(--sa-accent); outline-offset: 2px;
        }
        ha-icon { --mdc-icon-size: 20px; display: inline-flex; }
        code { font-family: var(--code-font-family, monospace); font-size: 0.92em; }
        .muted { color: var(--sa-muted); font-weight: 400; }
        .small { font-size: 12px; }
        .spacer { width: 40px; }

        /* Header */
        .header { display: flex; align-items: center; gap: 12px; padding: 16px 12px 8px 16px; }
        .header-icon {
          width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center;
          background: color-mix(in srgb, var(--sa-accent) 16%, transparent); color: var(--sa-accent);
        }
        .header-text { flex: 1; min-width: 0; }
        .title { font-size: 18px; font-weight: 600; line-height: 1.25; }
        .subtitle { font-size: 13px; color: var(--sa-muted); }
        .subtitle { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .status-chip {
          display: inline-flex; align-items: center; gap: 4px; height: 28px; padding: 0 10px; border-radius: 14px;
          border: none; background: color-mix(in srgb, var(--sa-warn) 18%, transparent); color: var(--sa-text); font-size: 12px; font-weight: 500;
        }
        .status-chip ha-icon { --mdc-icon-size: 16px; color: var(--sa-warn); }

        /* Buttons */
        .icon-button {
          width: 40px; height: 40px; border: none; border-radius: 50%; background: transparent;
          display: inline-grid; place-items: center; flex-shrink: 0; color: var(--sa-muted);
        }
        .icon-button:hover:not(:disabled) { background: var(--sa-hover); color: var(--sa-text); }
        .icon-button.small { width: 32px; height: 32px; }
        .icon-button.small ha-icon { --mdc-icon-size: 18px; }
        .icon-button.accent { color: var(--sa-accent); }
        .icon-button.light { color: #fff; }
        .filled-button, .tonal-button, .text-button {
          display: inline-flex; align-items: center; justify-content: center; gap: 6px; height: 40px; padding: 0 16px;
          border: none; border-radius: 20px; font-weight: 500; font-size: 14px; white-space: nowrap; flex-shrink: 0;
        }
        .filled-button { background: var(--sa-accent); color: var(--sa-on-accent); }
        .tonal-button { background: color-mix(in srgb, var(--sa-accent) 16%, transparent); color: var(--sa-text); height: 36px; padding: 0 14px; }
        .text-button { background: transparent; color: var(--sa-accent); }
        .filled-button:hover:not(:disabled), .tonal-button:hover:not(:disabled) { filter: brightness(1.08); }
        .spinner {
          width: 16px; height: 16px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Input */
        .input-row { display: flex; gap: 8px; padding: 8px 16px; }
        .search-field {
          flex: 1; min-width: 0; display: flex; align-items: center; gap: 4px; height: 48px; padding: 0 4px 0 14px;
          border-radius: 24px; background: var(--sa-surface-2); border: 1px solid transparent; transition: border-color 0.15s;
        }
        .search-field:focus-within { border-color: var(--sa-accent); }
        .search-field.busy { opacity: 0.7; }
        .field-icon { color: var(--sa-muted); }
        .search-field input {
          flex: 1; min-width: 0; height: 100%; border: none; background: transparent; outline: none;
          font-size: 16px; color: var(--sa-text); letter-spacing: 0.5px;
        }
        .input-row > .filled-button { height: 48px; border-radius: 24px; }
        input, textarea {
          font: inherit; color: var(--sa-text); background: var(--sa-surface-2); border: 1px solid var(--sa-line);
          border-radius: 8px; padding: 0 12px; min-width: 0;
        }
        input { height: 40px; }
        textarea { padding: 8px 12px; resize: vertical; }
        input:focus, textarea:focus { border-color: var(--sa-accent); outline: none; }
        .search-field input, .mini-search input { border: none; padding: 0; }

        /* Result banner */
        .result {
          margin: 4px 16px 8px; padding: 10px 6px 10px 12px; border-radius: var(--sa-radius);
          display: flex; flex-direction: column; gap: 8px; font-size: 14px; animation: rise 0.2s ease-out;
        }
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
        .tabs { display: flex; gap: 4px; padding: 4px 16px 0; border-bottom: 1px solid var(--sa-line); }
        .tab {
          position: relative; display: inline-flex; align-items: center; gap: 6px; height: 44px; padding: 0 12px;
          border: none; background: transparent; color: var(--sa-muted); font-weight: 500; font-size: 14px;
        }
        .tab.active { color: var(--sa-accent); }
        .tab.active::after {
          content: ""; position: absolute; left: 8px; right: 8px; bottom: -1px; height: 3px; border-radius: 3px 3px 0 0; background: var(--sa-accent);
        }
        .count {
          min-width: 20px; height: 20px; padding: 0 6px; border-radius: 10px; display: inline-grid; place-items: center;
          font-size: 11px; font-weight: 600; background: var(--sa-surface-2); color: var(--sa-text);
        }
        .count.alert { background: var(--sa-accent); color: var(--sa-on-accent); }
        .tab-body { padding: 8px 0; }

        /* Toolbar */
        .toolbar { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 8px; padding: 4px 16px 8px; }
        .toolbar .mini-search { grid-column: 1 / -1; }
        .sort-button {
          width: 32px; height: 32px; border-radius: 8px; border: 1px solid var(--sa-line); background: transparent;
          display: grid; place-items: center; color: var(--sa-muted);
        }
        .sort-button ha-icon { --mdc-icon-size: 18px; }
        .mini-search { display: flex; align-items: center; gap: 8px; height: 36px; padding: 0 12px; border-radius: 18px; background: var(--sa-surface-2); }
        .mini-search ha-icon { --mdc-icon-size: 18px; color: var(--sa-muted); }
        .mini-search input { flex: 1; height: 100%; background: transparent; outline: none; }
        .chips { display: flex; gap: 8px; overflow-x: auto; scrollbar-width: none; min-width: 0; mask-image: linear-gradient(90deg, #000 90%, transparent); }
        .chips::-webkit-scrollbar { display: none; }
        .chip {
          display: inline-flex; align-items: center; gap: 4px; height: 32px; padding: 0 12px; border-radius: 8px;
          border: 1px solid var(--sa-line); background: transparent; font-size: 13px; font-weight: 500; white-space: nowrap;
        }
        .chip ha-icon { --mdc-icon-size: 16px; }
        .chip.selected { background: color-mix(in srgb, var(--sa-accent) 18%, transparent); border-color: transparent; }

        /* Rows */
        .list { display: flex; flex-direction: column; }
        .row-wrap { position: relative; overflow: hidden; }
        .swipe-bg {
          position: absolute; inset: 0; display: flex; align-items: center; justify-content: flex-end; gap: 6px; padding-right: 24px;
          background: var(--sa-surface-2); color: var(--sa-muted); font-weight: 600; font-size: 13px; transition: background 0.15s, color 0.15s;
        }
        .row-wrap.armed .swipe-bg { background: var(--sa-good); color: #fff; }
        .row {
          position: relative; display: flex; align-items: center; gap: 12px; padding: 8px 16px; min-height: 64px;
          background: var(--sa-surface); transition: transform 0.2s ease, opacity 0.2s;
        }
        .row:hover { background: color-mix(in srgb, var(--sa-surface) 92%, var(--sa-text)); }
        .row.pending { opacity: 0.5; }
        .row-wrap + .row-wrap .row { border-top: 1px solid var(--sa-line); }
        .thumb {
          width: 48px; height: 48px; flex-shrink: 0; border-radius: 10px; border: none; padding: 0; overflow: hidden;
          background: #fff; display: grid; place-items: center; color: #9e9e9e;
          box-shadow: inset 0 0 0 1px var(--sa-line);
        }
        .thumb img { width: 100%; height: 100%; object-fit: contain; }
        .row-main {
          flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; align-items: flex-start; text-align: left;
          border: none; background: transparent; padding: 4px 0;
        }
        .row-title {
          font-size: 15px; font-weight: 500; line-height: 1.3; max-width: 100%; overflow: hidden;
          display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow-wrap: anywhere;
        }
        .row-meta { font-size: 13px; color: var(--sa-muted); max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .row-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-top: 2px; }
        .row-tags:empty { display: none; }
        .score-pill, .nova {
          display: inline-flex; align-items: center; gap: 3px; height: 20px; padding: 0 6px; border-radius: 6px;
          font-size: 11px; font-weight: 700; color: #fff; line-height: 1;
        }
        .score-kind { font-weight: 500; opacity: 0.85; }
        .diet { display: inline-grid; place-items: center; width: 22px; height: 20px; border-radius: 6px; background: color-mix(in srgb, var(--sa-good) 18%, transparent); color: var(--sa-good); }
        .diet ha-icon { --mdc-icon-size: 14px; }
        .expiry { height: 20px; padding: 0 6px; border-radius: 6px; font-size: 11px; font-weight: 600; display: inline-flex; align-items: center; background: var(--sa-surface-2); }
        .expiry.warn { background: color-mix(in srgb, var(--sa-warn) 22%, transparent); }
        .expiry.bad { background: color-mix(in srgb, var(--sa-bad) 20%, transparent); color: var(--sa-bad); }
        .stepper { display: flex; align-items: center; gap: 2px; flex-shrink: 0; background: var(--sa-surface-2); border-radius: 18px; padding: 2px; }
        .step { width: 32px; height: 32px; border-radius: 50%; border: none; background: transparent; display: grid; place-items: center; }
        .step:hover:not(:disabled) { background: var(--sa-hover); }
        .step ha-icon { --mdc-icon-size: 18px; }
        .qty { min-width: 20px; text-align: center; font-weight: 600; font-size: 14px; font-variant-numeric: tabular-nums; }
        .qty-text { padding: 0 10px; font-size: 13px; font-weight: 600; line-height: 32px; }
        .check {
          width: 40px; height: 40px; flex-shrink: 0; border-radius: 50%; border: 2px solid var(--sa-line); background: transparent;
          display: grid; place-items: center; color: var(--sa-muted); transition: all 0.15s;
        }
        .check:hover:not(:disabled) { border-color: var(--sa-good); background: var(--sa-good); color: #fff; }
        .total {
          display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin: 8px 16px 0; padding: 12px 0 4px;
          border-top: 1px dashed var(--sa-line); font-size: 14px;
        }
        .total strong { font-size: 18px; font-variant-numeric: tabular-nums; }

        /* Unknown and expiring rows */
        .unknown-row { display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; }
        .unknown-row + .unknown-row { border-top: 1px solid var(--sa-line); }
        .unknown-head { display: flex; align-items: center; gap: 10px; }
        .unknown-head code { font-size: 15px; font-weight: 600; }
        .unknown-head .muted { flex: 1; font-size: 13px; }
        .expiring-row { display: flex; align-items: center; gap: 12px; padding: 8px 16px; min-height: 60px; }
        .expiring-row + .expiring-row { border-top: 1px solid var(--sa-line); }
        .days {
          width: 48px; height: 48px; border-radius: 12px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
          background: var(--sa-surface-2); line-height: 1;
        }
        .days strong { font-size: 18px; }
        .days small { font-size: 10px; color: var(--sa-muted); margin-top: 2px; }
        .days.warn { background: color-mix(in srgb, var(--sa-warn) 22%, transparent); }
        .days.bad { background: color-mix(in srgb, var(--sa-bad) 20%, transparent); color: var(--sa-bad); }

        /* Empty */
        .empty-state { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 6px; padding: 32px 24px; }
        .empty-state ha-icon { --mdc-icon-size: 40px; color: var(--sa-muted); opacity: 0.6; margin-bottom: 4px; }
        .empty-title { font-weight: 600; font-size: 15px; }
        .empty-text { color: var(--sa-muted); font-size: 13px; max-width: 320px; }
        .empty-inline { padding: 24px 16px; text-align: center; color: var(--sa-muted); font-size: 13px; }

        /* Stats */
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--sa-line); }
        .stat { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 10px 4px; min-width: 0; }
        .stat ha-icon { --mdc-icon-size: 16px; color: var(--sa-muted); }
        .stat strong { font-size: 15px; font-variant-numeric: tabular-nums; }
        .stat span { font-size: 10px; color: var(--sa-muted); text-transform: uppercase; letter-spacing: 0.4px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }

        /* Overlays */
        .scrim {
          position: fixed; inset: 0; z-index: 9; background: rgba(0, 0, 0, 0.45); display: flex; align-items: flex-end; justify-content: center;
          animation: fade 0.15s ease-out;
        }
        .scrim.dark { background: rgba(0, 0, 0, 0.85); align-items: center; }
        @keyframes fade { from { opacity: 0; } }
        @keyframes slide { from { transform: translateY(24px); opacity: 0.6; } }
        .sheet {
          width: 100%; max-width: 560px; background: var(--sa-surface); border-radius: 28px 28px 0 0; padding: 8px 0 calc(16px + env(safe-area-inset-bottom));
          animation: slide 0.2s ease-out; color: var(--sa-text);
        }
        .handle { width: 32px; height: 4px; border-radius: 2px; background: var(--sa-line); margin: 8px auto 12px; }
        .sheet-item {
          width: 100%; display: flex; align-items: center; gap: 16px; padding: 12px 24px; border: none; background: transparent; text-align: left;
        }
        .sheet-item:hover:not(:disabled) { background: var(--sa-hover); }
        .sheet-item span { display: flex; flex-direction: column; gap: 2px; }
        .sheet-item small { color: var(--sa-muted); font-size: 13px; }
        .sheet-item ha-icon { --mdc-icon-size: 24px; color: var(--sa-muted); }
        .sheet-item.danger strong, .sheet-item.danger ha-icon { color: var(--sa-bad); }
        .sheet-divider { height: 1px; background: var(--sa-line); margin: 8px 0; }

        .dialog {
          width: 100%; max-width: 640px; max-height: 92vh; display: flex; flex-direction: column; background: var(--sa-surface);
          border-radius: 28px 28px 0 0; overflow: hidden; animation: slide 0.2s ease-out; color: var(--sa-text);
        }
        @media (min-width: 700px) {
          .scrim:not(.dark) { align-items: center; }
          .dialog { border-radius: 28px; max-height: 86vh; }
        }
        .dialog-bar { display: flex; align-items: center; gap: 4px; padding: 8px; border-bottom: 1px solid var(--sa-line); }
        .dialog-title { flex: 1; font-size: 16px; font-weight: 600; padding-left: 4px; }
        .progress { height: 3px; background: linear-gradient(90deg, transparent, var(--sa-accent), transparent); background-size: 50% 100%; animation: load 1s linear infinite; }
        @keyframes load { from { background-position: -50% 0; } to { background-position: 150% 0; } }
        .dialog-body { overflow-y: auto; padding: 16px 20px calc(24px + env(safe-area-inset-bottom)); display: flex; flex-direction: column; gap: 20px; }
        section { display: flex; flex-direction: column; gap: 8px; }
        h3 { margin: 0; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; }
        h3 .muted { text-transform: none; letter-spacing: 0; font-size: 12px; margin-left: 4px; }

        .hero { display: flex; gap: 16px; align-items: flex-start; }
        .hero-img {
          width: 104px; height: 104px; flex-shrink: 0; border-radius: 16px; background: #fff; overflow: hidden; display: grid; place-items: center;
          box-shadow: inset 0 0 0 1px var(--sa-line); color: #9e9e9e;
        }
        .hero-img ha-icon { --mdc-icon-size: 40px; }
        .hero-img img { width: 100%; height: 100%; object-fit: contain; }
        .hero-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
        .hero-name { font-size: 20px; font-weight: 600; line-height: 1.25; }
        .hero-actions { margin-top: 10px; display: flex; gap: 8px; }

        .score-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 8px; }
        .score-tile { border-radius: 14px; padding: 10px 12px; display: flex; flex-direction: column; gap: 2px; }
        .score-tile span { font-size: 11px; font-weight: 600; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.4px; }
        .score-tile strong { font-size: 26px; line-height: 1; }
        .diet-row { display: flex; flex-wrap: wrap; gap: 6px; }
        .diet-chip { display: inline-flex; align-items: center; gap: 4px; height: 28px; padding: 0 10px; border-radius: 14px; font-size: 13px; background: var(--sa-surface-2); }
        .diet-chip ha-icon { --mdc-icon-size: 16px; }
        .diet-chip.yes { background: color-mix(in srgb, var(--sa-good) 16%, transparent); }
        .diet-chip.yes ha-icon { color: var(--sa-good); }
        .diet-chip.no ha-icon { color: var(--sa-bad); }

        .nutrition { border: 1px solid var(--sa-line); border-radius: 12px; overflow: hidden; }
        .nutri-row { display: grid; grid-template-columns: 1fr auto 96px; align-items: center; gap: 8px; padding: 8px 12px; font-size: 14px; }
        .nutri-row + .nutri-row { border-top: 1px solid var(--sa-line); }
        .nutri-row.sub { padding-left: 28px; color: var(--sa-muted); font-size: 13px; }
        .nutri-row strong { text-align: right; font-variant-numeric: tabular-nums; color: var(--sa-text); }
        .level { font-size: 11px; font-weight: 600; text-transform: uppercase; padding: 2px 8px; border-radius: 10px; color: #fff; }
        .level.low { background: #2e7d32; }
        .level.medium { background: #f9a825; color: #1f1f1f; }
        .level.high { background: #c62828; }
        .micro-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; }
        .micro { display: flex; flex-direction: column; gap: 2px; padding: 8px 12px; border-radius: 10px; background: var(--sa-surface-2); }
        .micro span { font-size: 12px; color: var(--sa-muted); }
        .micro strong { font-variant-numeric: tabular-nums; }
        .note { display: flex; gap: 8px; align-items: flex-start; font-size: 14px; padding: 8px 12px; border-radius: 10px; background: var(--sa-surface-2); }
        .note ha-icon { --mdc-icon-size: 18px; color: var(--sa-muted); margin-top: 1px; }
        .note.warn { background: color-mix(in srgb, var(--sa-warn) 16%, transparent); }
        .note.warn ha-icon { color: var(--sa-warn); }
        .text { margin: 0; font-size: 14px; line-height: 1.5; color: var(--sa-text); }
        .labels { display: flex; flex-wrap: wrap; gap: 6px; }
        .label-chip { padding: 4px 10px; border-radius: 8px; font-size: 12px; border: 1px solid var(--sa-line); }
        .info-row { display: grid; grid-template-columns: 24px 120px 1fr; gap: 8px; align-items: center; font-size: 14px; padding: 4px 0; }
        .info-row ha-icon { --mdc-icon-size: 18px; color: var(--sa-muted); }

        .your-data { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
        .data-block { border: 1px solid var(--sa-line); border-radius: 14px; padding: 12px; display: flex; flex-direction: column; gap: 6px; }
        .data-head { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: var(--sa-muted); }
        .data-head ha-icon { --mdc-icon-size: 18px; }
        .big { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
        .history { list-style: none; margin: 4px 0 0; padding: 0; font-size: 12px; }
        .history li { display: flex; justify-content: space-between; padding: 3px 0; color: var(--sa-muted); }
        .inline-form { display: flex; gap: 6px; margin-top: 6px; }
        .inline-form input { flex: 1; height: 36px; }
        .inline-form input[name="price"] { max-width: 90px; }
        .warn-text { color: var(--sa-warn); }
        .bad-text { color: var(--sa-bad); }
        .off-link { display: inline-flex; align-items: center; gap: 6px; color: var(--sa-accent); font-size: 14px; text-decoration: none; align-self: flex-start; }
        .off-link ha-icon { --mdc-icon-size: 16px; }

        .edit { display: flex; flex-direction: column; gap: 14px; }
        .fields { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
        .field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--sa-muted); }
        .field.wide { grid-column: 1 / -1; }
        .field input, .field textarea { font-size: 15px; }
        .switch-row { display: flex; align-items: center; gap: 10px; font-size: 14px; }
        .switch-row input { width: 18px; height: 18px; accent-color: var(--sa-accent); }
        .edit-actions { display: flex; justify-content: flex-end; gap: 8px; }

        /* Scanner */
        .scanner { width: 100%; max-width: 520px; display: flex; flex-direction: column; color: #fff; }
        .scanner-bar { display: flex; align-items: center; padding: 8px; }
        .scanner-title { flex: 1; text-align: center; font-weight: 600; }
        .viewfinder { position: relative; aspect-ratio: 4 / 3; background: #000; overflow: hidden; border-radius: 20px; margin: 0 12px; }
        .viewfinder video { width: 100%; height: 100%; object-fit: cover; }
        .frame {
          position: absolute; left: 12%; right: 12%; top: 30%; bottom: 30%; border-radius: 14px;
          box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.45); border: 2px solid rgba(255, 255, 255, 0.85);
        }
        .laser { position: absolute; left: 6%; right: 6%; top: 50%; height: 2px; background: var(--sa-bad); box-shadow: 0 0 8px var(--sa-bad); animation: sweep 1.6s ease-in-out infinite alternate; }
        @keyframes sweep { from { top: 15%; } to { top: 85%; } }
        .scanner-error { position: absolute; inset: auto 16px 16px; padding: 10px 14px; border-radius: 12px; background: rgba(0, 0, 0, 0.75); text-align: center; }
        .scanner-footer { display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; }
        .scanner-footer .switch-row { color: #fff; }
        .hint { color: rgba(255, 255, 255, 0.7); font-size: 13px; text-align: center; }
        .scanned { display: flex; flex-wrap: wrap; gap: 6px; }
        .scanned code { padding: 4px 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.15); }

        @media (max-width: 420px) {
          .status-chip span { display: none; }
          .status-chip { width: 32px; padding: 0; justify-content: center; }
          .step { width: 28px; height: 28px; }
          .check { width: 36px; height: 36px; }
          .input-row > .filled-button .label { display: none; }
          .input-row > .filled-button { width: 48px; padding: 0; }
          .row { gap: 10px; padding-left: 12px; }
          .thumb { width: 42px; height: 42px; }
          .info-row { grid-template-columns: 24px 1fr; }
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
