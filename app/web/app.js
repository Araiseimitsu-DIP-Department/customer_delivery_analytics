const state = {
  customers: [],
  products: [],
  allProducts: [],
  choicesLoaded: false,
  choicesLoading: null,
};

const el = {
  brandLogo: document.getElementById("brandLogo"),
  dateFrom: document.getElementById("dateFrom"),
  dateTo: document.getElementById("dateTo"),
  aggregateMode: document.getElementById("aggregateMode"),
  customerInput: document.getElementById("customerInput"),
  productInput: document.getElementById("productInput"),
  customerDropdown: document.getElementById("customerDropdown"),
  productDropdown: document.getElementById("productDropdown"),
  searchButton: document.getElementById("searchButton"),
  exportActualButton: document.getElementById("exportActualButton"),
  yearChartButton: document.getElementById("yearChartButton"),
  monthChartButton: document.getElementById("monthChartButton"),
  forecastYears: document.getElementById("forecastYears"),
  forecastButton: document.getElementById("forecastButton"),
  forecastChartButton: document.getElementById("forecastChartButton"),
  exportForecastButton: document.getElementById("exportForecastButton"),
  forecastDetailButton: document.getElementById("forecastDetailButton"),
  forecastNote: document.getElementById("forecastNote"),
  statusLine: document.getElementById("statusLine"),
  actualTable: document.getElementById("actualTable"),
  forecastTable: document.getElementById("forecastTable"),
  chartDialog: document.getElementById("chartDialog"),
  chartTitle: document.getElementById("chartTitle"),
  chartImage: document.getElementById("chartImage"),
  detailDialog: document.getElementById("detailDialog"),
  detailBody: document.getElementById("detailBody"),
};

function setBusy(isBusy, text = "") {
  document.body.style.cursor = isBusy ? "wait" : "";
  for (const button of document.querySelectorAll("button")) {
    button.disabled = Boolean(isBusy);
  }
  if (!isBusy) {
    refreshFieldState();
  }
  if (text) {
    setStatus(text);
  }
}

function setStatus(text, isError = false) {
  el.statusLine.textContent = text;
  el.statusLine.classList.toggle("is-visible", Boolean(text));
  el.statusLine.classList.toggle("error", isError);
}

function apiError(result) {
  setStatus(result.message || "処理に失敗しました。", true);
}

function renderSelectOptions(options, selected) {
  el.aggregateMode.replaceChildren();
  for (const item of options) {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    option.selected = item.value === selected;
    el.aggregateMode.appendChild(option);
  }
}

function filteredItems(items, keyword) {
  const query = String(keyword || "").trim().toLowerCase();
  const source = query
    ? items.filter((item) => item.toLowerCase().includes(query))
    : items;
  return source.slice(0, 80);
}

function renderSuggestions(dropdown, input, items) {
  dropdown.replaceChildren();
  if (input.disabled) {
    dropdown.classList.remove("is-open");
    return;
  }
  const matches = filteredItems(items, input.value);
  if (!matches.length) {
    const empty = document.createElement("div");
    empty.className = "suggestion-empty";
    empty.textContent = "候補がありません";
    dropdown.appendChild(empty);
    dropdown.classList.add("is-open");
    return;
  }
  for (const item of matches) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "suggestion-item";
    button.textContent = item;
    button.addEventListener("mousedown", (event) => {
      event.preventDefault();
      input.value = item;
      dropdown.classList.remove("is-open");
      if (input === el.customerInput) {
        refreshProductsForCustomer();
      }
    });
    dropdown.appendChild(button);
  }
  dropdown.classList.add("is-open");
}

function closeSuggestions() {
  el.customerDropdown.classList.remove("is-open");
  el.productDropdown.classList.remove("is-open");
}

function refreshFieldState() {
  const mode = el.aggregateMode.value;
  const byCustomer = mode === "BY_CUSTOMER";
  const byProduct = mode === "BY_PRODUCT";
  el.customerInput.disabled = byProduct;
  el.productInput.disabled = byCustomer;
  if (byProduct) {
    el.customerInput.value = "";
  }
  if (byCustomer) {
    el.productInput.value = "";
  }
}

function formatCell(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? value.toLocaleString("ja-JP")
      : value.toLocaleString("ja-JP", { maximumFractionDigits: 2 });
  }
  return String(value);
}

function isNumericColumn(column) {
  return /年|月|数|金額|予測|実績|直線|回帰|要因/.test(column);
}

function renderTable(table, columns, rows) {
  table.replaceChildren();
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const column of columns) {
    const th = document.createElement("th");
    th.textContent = column;
    if (isNumericColumn(column)) {
      th.classList.add("numeric");
    }
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  if (!rows.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.className = "empty-cell";
    cell.colSpan = Math.max(columns.length, 1);
    cell.textContent = "該当データがありません";
    row.appendChild(cell);
    tbody.appendChild(row);
    table.appendChild(tbody);
    return;
  }

  for (const item of rows) {
    const row = document.createElement("tr");
    for (const column of columns) {
      const cell = document.createElement("td");
      cell.textContent = formatCell(item[column]);
      if (isNumericColumn(column)) {
        cell.classList.add("numeric");
      }
      row.appendChild(cell);
    }
    tbody.appendChild(row);
  }
  table.appendChild(tbody);
}

function searchParams() {
  return {
    dateFrom: el.dateFrom.value,
    dateTo: el.dateTo.value,
    aggregateMode: el.aggregateMode.value,
    customer: el.customerInput.value,
    product: el.productInput.value,
  };
}

async function onSearch() {
  setBusy(true, "検索中...");
  const result = await window.pywebview.api.search(searchParams());
  setBusy(false);
  if (!result.ok) {
    apiError(result);
    return;
  }
  renderTable(el.actualTable, result.columns, result.rows);
  renderTable(el.forecastTable, ["年", "実績", "予測"], []);
  setStatus(result.status);
}

async function onForecast() {
  setBusy(true, "予測を計算中...");
  const result = await window.pywebview.api.forecast(Number(el.forecastYears.value || 3));
  setBusy(false);
  if (!result.ok) {
    apiError(result);
    return;
  }
  renderTable(el.forecastTable, result.columns, result.rows);
  el.forecastNote.innerHTML = result.summaryLines
    .slice(0, 4)
    .map((line) => `・${escapeHtml(line)}`)
    .join("<br>");
  setStatus(result.status);
}

async function exportActual() {
  setBusy(true, "Excel を保存中...");
  const result = await window.pywebview.api.export_actual();
  setBusy(false);
  if (result.cancelled) {
    setStatus("Excel 出力をキャンセルしました。");
    return;
  }
  result.ok ? setStatus(result.status) : apiError(result);
}

async function exportForecast() {
  setBusy(true, "予測 Excel を保存中...");
  const result = await window.pywebview.api.export_forecast();
  setBusy(false);
  if (result.cancelled) {
    setStatus("Excel 出力をキャンセルしました。");
    return;
  }
  result.ok ? setStatus(result.status) : apiError(result);
}

async function openChart(kind) {
  setBusy(true, "グラフを準備中...");
  const result = await window.pywebview.api.chart(kind);
  setBusy(false);
  if (!result.ok) {
    apiError(result);
    return;
  }
  el.chartTitle.textContent = result.title;
  el.chartImage.src = result.image;
  el.chartDialog.showModal();
}

async function openDetails() {
  const result = await window.pywebview.api.forecast_details();
  if (!result.ok) {
    apiError(result);
    return;
  }
  el.detailBody.replaceChildren();
  for (const section of result.sections) {
    const block = document.createElement("section");
    block.className = "detail-section";
    const title = document.createElement("h3");
    title.textContent = section.title;
    const body = document.createElement("p");
    body.textContent = section.body;
    block.append(title, body);
    el.detailBody.appendChild(block);
  }
  el.detailDialog.showModal();
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function refreshProductsForCustomer() {
  if (el.aggregateMode.value !== "BY_CUSTOMER_PRODUCT" || !el.customerInput.value.trim()) {
    state.products = state.allProducts;
    renderSuggestions(el.productDropdown, el.productInput, state.products);
    return;
  }
  const result = await window.pywebview.api.get_products(el.customerInput.value);
  if (result.ok) {
    state.products = result.products;
    renderSuggestions(el.productDropdown, el.productInput, state.products);
  }
}

async function ensureChoicesLoaded() {
  if (state.choicesLoaded) {
    return true;
  }
  if (!state.choicesLoading) {
    setStatus("");
    state.choicesLoading = window.pywebview.api.load_master_choices();
  }
  const result = await state.choicesLoading;
  state.choicesLoading = null;
  if (!result.ok) {
    apiError(result);
    return false;
  }
  state.customers = result.customers;
  state.products = result.products;
  state.allProducts = result.products;
  state.choicesLoaded = true;
  setStatus("");
  return true;
}

async function showCustomerSuggestions() {
  if (await ensureChoicesLoaded()) {
    renderSuggestions(el.customerDropdown, el.customerInput, state.customers);
  }
}

async function showProductSuggestions() {
  if (await ensureChoicesLoaded()) {
    renderSuggestions(el.productDropdown, el.productInput, state.products);
  }
}

async function bootstrap() {
  renderTable(el.actualTable, ["顧客", "品番", "年", "月", "納品数", "金額"], []);
  renderTable(el.forecastTable, ["年", "実績", "予測"], []);
  const result = await window.pywebview.api.bootstrap();
  if (!result.ok) {
    apiError(result);
    return;
  }
  if (result.logoDataUri) {
    el.brandLogo.src = result.logoDataUri;
  }
  renderSelectOptions(result.aggregateOptions, result.defaults.aggregateMode);
  el.dateFrom.value = result.defaults.dateFrom;
  el.dateTo.value = result.defaults.dateTo;
  refreshFieldState();
  setStatus("");
}

el.aggregateMode.addEventListener("change", () => {
  refreshFieldState();
  refreshProductsForCustomer();
});
el.customerInput.addEventListener("focus", showCustomerSuggestions);
el.customerInput.addEventListener("input", showCustomerSuggestions);
el.customerInput.addEventListener("change", refreshProductsForCustomer);
el.customerInput.addEventListener("blur", () => setTimeout(closeSuggestions, 120));
el.productInput.addEventListener("focus", showProductSuggestions);
el.productInput.addEventListener("input", showProductSuggestions);
el.productInput.addEventListener("blur", () => setTimeout(closeSuggestions, 120));
el.searchButton.addEventListener("click", onSearch);
el.forecastButton.addEventListener("click", onForecast);
el.exportActualButton.addEventListener("click", exportActual);
el.exportForecastButton.addEventListener("click", exportForecast);
el.yearChartButton.addEventListener("click", () => openChart("yearly"));
el.monthChartButton.addEventListener("click", () => openChart("monthly"));
el.forecastChartButton.addEventListener("click", () => openChart("forecast"));
el.forecastDetailButton.addEventListener("click", openDetails);

for (const button of document.querySelectorAll("[data-close-dialog]")) {
  button.addEventListener("click", () => {
    document.getElementById(button.dataset.closeDialog).close();
  });
}

window.addEventListener("pywebviewready", bootstrap);
