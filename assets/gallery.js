/*
 * Gallery pages: French is pre-rendered by scripts/pages.mjs; this script switches the language
 * (?lang=en, kept when following links), runs the hero map, the viewer and the ?open= deep link.
 */
const ROOT = document.body.dataset.root || "";
const PAGE = document.body.dataset.page;
const SECTION = document.body.dataset.section;
const NAMED = "[data-name], [data-above_m]";
const MAX_ZOOM = 24;
const coarse = matchMedia("(pointer: coarse)");

let strings = {};
let locale = new URLSearchParams(location.search).get("lang") === "en" ? "en" : "fr";

const t = (key, values = {}) =>
  (strings[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => values[name] ?? "");
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const countLabel = (n) => t(n === 1 ? "family.count.one" : "family.count.other", { n: n.toLocaleString(locale) });
const sizeLabel = (bytes) =>
  t("unit.kb", { size: (bytes / 1024).toLocaleString(locale, { maximumFractionDigits: bytes < 10240 ? 1 : 0 }) });
const fileName = (map) => map.path.split("/").pop();

const svgTexts = new Map();
function fetchSvg(path) {
  if (!svgTexts.has(path)) {
    const request = fetch(path).then((response) => {
      if (!response.ok) throw new Error(response.status);
      return response.text();
    });
    request.catch(() => svgTexts.delete(path));
    svgTexts.set(path, request);
  }
  return svgTexts.get(path);
}

/* Parses an SVG file into an inline element and gathers what the tooltips need. */
function inlineSvg(text, { keepIds = true } = {}) {
  const parsed = new DOMParser().parseFromString(text, "image/svg+xml").documentElement;
  const svg = document.importNode(parsed, true);
  svg.removeAttribute("width");
  svg.removeAttribute("height");
  svg.classList.add("map");
  svg.setAttribute("focusable", "false");
  const communes = new Map();
  svg.querySelectorAll("path[data-code][data-name]").forEach((path) => {
    if (path.id.startsWith("commune-")) communes.set(path.dataset.code, path.dataset.name);
  });
  const levels = [...svg.querySelectorAll("[data-above_m]")]
    .map((node) => Number(node.dataset.above_m)).sort((a, b) => a - b);
  if (!keepIds) svg.querySelectorAll("[id]").forEach((node) => node.removeAttribute("id"));
  return { svg, communes, levels, named: Boolean(svg.querySelector(NAMED)) };
}

function describe(node, info) {
  const data = node.dataset;
  if (data.above_m !== undefined) {
    const from = Number(data.above_m);
    const next = info.levels.find((level) => level > from);
    const name = next === undefined ? t("tip.relief.top", { from }) : t("tip.relief.band", { from, to: next });
    return { name, lines: [] };
  }
  const lines = [];
  if (data.kind) lines.push(t(`kind.${data.kind}`));
  if (data.commune && info.communes.has(data.commune)) lines.push(t("tip.commune", { name: info.communes.get(data.commune) }));
  const prefix = (node.id || "").split("-")[0];
  if (data.code && prefix === "commune") lines.push(t("tip.insee", { code: data.code }));
  if (data.code && prefix === "canton") lines.push(t("tip.canton", { code: data.code }));
  if (data.code && prefix === "epci") lines.push(t("tip.siren", { code: data.code }));
  return { name: data.name, lines };
}

/*
 * Map explorer: hover/tap tooltips with highlight, and, when zoomable, wheel / pinch /
 * drag / keyboard zoom and pan by rewriting the SVG viewBox (stays vector-sharp).
 */
function createExplorer(stage, holder, { zoomable }) {
  const tip = stage.querySelector(".tip");
  let info = null;
  let base = null;
  let box = null;
  let hot = null;
  let ring = null;
  const pointers = new Map();
  let start = null;
  let moved = false;

  function load(next) {
    clear();
    info = next;
    holder.replaceChildren(info.svg);
    const [x, y, w, h] = info.svg.getAttribute("viewBox").split(/[\s,]+/).map(Number);
    base = { x, y, w, h };
    box = { ...base };
    ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    ring.setAttribute("class", "ring");
    ring.style.display = "none";
    info.svg.append(ring);
    update();
  }

  function clear() {
    info = null;
    hot = null;
    tip.hidden = true;
    pointers.clear();
  }

  function update() {
    if (!info) return;
    info.svg.setAttribute("viewBox", `${box.x} ${box.y} ${box.w} ${box.h}`);
    const scale = base.w / box.w;
    stage.querySelectorAll("[data-zoom]").forEach((button) => {
      const kind = button.dataset.zoom;
      button.disabled = kind === "in" ? scale >= MAX_ZOOM - 0.01 : scale <= 1.001;
    });
  }

  function zoomAt(clientX, clientY, factor) {
    if (!info || !zoomable) return;
    const scale = base.w / box.w;
    const target = clamp(scale * factor, 1, MAX_ZOOM);
    const f = target / scale;
    if (Math.abs(f - 1) < 1e-4) return;
    const point = new DOMPoint(clientX, clientY).matrixTransform(info.svg.getScreenCTM().inverse());
    box = { x: point.x - (point.x - box.x) / f, y: point.y - (point.y - box.y) / f, w: box.w / f, h: box.h / f };
    if (target <= 1.001) box = { ...base };
    keepInside();
    update();
  }

  function zoomCentre(factor) {
    const rect = stage.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, factor);
  }

  function panBy(dx, dy) {
    if (!info || !zoomable) return;
    const matrix = info.svg.getScreenCTM();
    box.x -= dx / matrix.a;
    box.y -= dy / matrix.d;
    keepInside();
    update();
  }

  function keepInside() {
    const cx = clamp(box.x + box.w / 2, base.x, base.x + base.w);
    const cy = clamp(box.y + box.h / 2, base.y, base.y + base.h);
    box.x = cx - box.w / 2;
    box.y = cy - box.h / 2;
  }

  function reset() {
    if (!info) return;
    box = { ...base };
    update();
  }

  function shapeAt(clientX, clientY) {
    const node = document.elementFromPoint(clientX, clientY)?.closest?.(NAMED);
    return node && info && info.svg.contains(node) ? node : null;
  }

  function highlight(node) {
    if (node === hot) return;
    if (hot) hot.classList.remove("is-hot");
    ring.style.display = "none";
    hot = node;
    if (!node) return;
    if (node.tagName === "circle") {
      const r = Number(node.getAttribute("r")) || 2;
      ring.setAttribute("cx", node.getAttribute("cx"));
      ring.setAttribute("cy", node.getAttribute("cy"));
      const unitsPerPixel = 1 / (info.svg.getScreenCTM()?.a || 1);
      ring.setAttribute("r", String(Math.max(r * 1.9, 6 * unitsPerPixel)));
      ring.style.display = "";
    } else {
      node.classList.add("is-hot");
    }
  }

  function show(node, clientX, clientY, above) {
    highlight(node);
    if (!node) { tip.hidden = true; return; }
    const { name, lines } = describe(node, info);
    const title = document.createElement("strong");
    title.textContent = name;
    tip.replaceChildren(title, ...lines.map((line) => Object.assign(document.createElement("span"), { textContent: line })));
    tip.hidden = false;
    const rect = stage.getBoundingClientRect();
    const width = tip.offsetWidth;
    const height = tip.offsetHeight;
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    let x = px + 16;
    let y = above ? py - height - 22 : py + 18;
    if (above) x = px - width / 2;
    if (x + width > rect.width - 8) x = px - width - 16;
    if (y + height > rect.height - 8) y = py - height - 16;
    if (y < 8) y = py + 22;
    tip.style.transform = `translate(${clamp(x, 8, rect.width - width - 8)}px, ${clamp(y, 8, rect.height - height - 8)}px)`;
  }

  function hide() {
    highlight(null);
    tip.hidden = true;
  }

  stage.addEventListener("pointerdown", (event) => {
    if (!info || event.target.closest("button, a")) return;
    if (event.pointerType === "mouse" && event.button !== 0) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.size === 1) { start = { x: event.clientX, y: event.clientY }; moved = false; }
    if (zoomable) stage.setPointerCapture(event.pointerId);
  });

  stage.addEventListener("pointermove", (event) => {
    if (!info) return;
    if (!pointers.has(event.pointerId)) {
      if (event.pointerType === "mouse") show(shapeAt(event.clientX, event.clientY), event.clientX, event.clientY, false);
      return;
    }
    const before = [...pointers.values()];
    const previous = pointers.get(event.pointerId);
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (!zoomable) return;
    if (!moved && (pointers.size > 1 || Math.hypot(event.clientX - start.x, event.clientY - start.y) > 5)) {
      moved = true;
      hide();
      stage.classList.add("is-dragging");
    }
    if (!moved) return;
    if (pointers.size === 1) {
      panBy(event.clientX - previous.x, event.clientY - previous.y);
    } else if (pointers.size === 2 && before.length === 2) {
      const after = [...pointers.values()];
      const mid = (list) => ({ x: (list[0].x + list[1].x) / 2, y: (list[0].y + list[1].y) / 2 });
      const gap = (list) => Math.hypot(list[0].x - list[1].x, list[0].y - list[1].y) || 1;
      const a = mid(before);
      const b = mid(after);
      zoomAt(b.x, b.y, gap(after) / gap(before));
      panBy(b.x - a.x, b.y - a.y);
    }
  });

  function release(event) {
    if (!pointers.has(event.pointerId)) return;
    pointers.delete(event.pointerId);
    if (pointers.size > 0) return;
    stage.classList.remove("is-dragging");
    if (event.type === "pointercancel") return;
    if (!moved) {
      const node = shapeAt(event.clientX, event.clientY);
      show(node, event.clientX, event.clientY, event.pointerType !== "mouse");
    }
  }
  stage.addEventListener("pointerup", release);
  stage.addEventListener("pointercancel", release);
  stage.addEventListener("pointerleave", (event) => {
    if (event.pointerType === "mouse" && pointers.size === 0) hide();
  });

  if (zoomable) {
    stage.addEventListener("wheel", (event) => {
      if (!info) return;
      event.preventDefault();
      hide();
      const delta = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY;
      zoomAt(event.clientX, event.clientY, Math.exp(-clamp(delta, -120, 120) * 0.0022));
    }, { passive: false });
    stage.addEventListener("dblclick", (event) => {
      if (event.target.closest("button, a")) return;
      zoomAt(event.clientX, event.clientY, event.shiftKey ? 0.5 : 2);
    });
    stage.addEventListener("keydown", (event) => {
      if (event.target !== stage) return;
      const step = 60;
      const actions = {
        ArrowLeft: () => panBy(step, 0), ArrowRight: () => panBy(-step, 0),
        ArrowUp: () => panBy(0, step), ArrowDown: () => panBy(0, -step),
        "+": () => zoomCentre(1.5), "=": () => zoomCentre(1.5), "-": () => zoomCentre(1 / 1.5), "0": reset,
      };
      if (actions[event.key]) { event.preventDefault(); hide(); actions[event.key](); }
    });
    stage.querySelectorAll("[data-zoom]").forEach((button) => {
      button.addEventListener("click", () => {
        hide();
        const kind = button.dataset.zoom;
        if (kind === "reset") reset();
        else zoomCentre(kind === "in" ? 1.6 : 1 / 1.6);
      });
    });
  }

  return { load, clear, reset, hide };
}

/* Same attributes as the pre-rendering in scripts/pages.mjs */
function localize() {
  const vars = (node) => Object.fromEntries((node.dataset.i18nVars || "").split(/\s+/).filter(Boolean)
    .map((pair) => { const [name, key] = pair.split(":"); return [name, t(key)]; }));
  document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n, vars(node)); });
  const attributes = { i18nLabel: "aria-label", i18nTitle: "title", i18nContent: "content", i18nAlt: "alt" };
  for (const [source, target] of Object.entries(attributes)) {
    const selector = `[data-${source.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}]`;
    document.querySelectorAll(selector).forEach((node) => { node.setAttribute(target, t(node.dataset[source], vars(node))); });
  }
  document.querySelectorAll("[data-count]").forEach((node) => { node.textContent = countLabel(Number(node.dataset.count)); });
  document.querySelectorAll("[data-filesize]").forEach((node) => { node.textContent = sizeLabel(Number(node.dataset.filesize)); });
}

/* Links between pages keep the language */
function updateLinks() {
  document.querySelectorAll("a[data-nav]").forEach((link) => {
    link.dataset.href ??= link.getAttribute("href");
    link.setAttribute("href", locale === "en" ? `${link.dataset.href}?lang=en` : link.dataset.href);
  });
}

async function load() {
  strings = await fetch(`${ROOT}i18n/${locale}.json`).then((response) => response.json());
  document.documentElement.lang = locale;
  localize();
  document.querySelectorAll(".lang button").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.lang === locale));
  });
  renderCredit();
  renderHint();
  updateLinks();
  if (viewer?.open && current) fillViewerText(current);
}

function renderCredit() {
  const [before, after = ""] = t("page.credit", { author: "{author}" }).split("{author}");
  const link = document.createElement("a");
  link.href = "https://beeraw.yt";
  link.textContent = t("page.author");
  document.getElementById("credit").replaceChildren(before, link, after);
}

async function copySvg(map, button) {
  try {
    const code = await fetchSvg(map.path);
    await navigator.clipboard.writeText(code);
    button.textContent = t("action.copied");
    setTimeout(() => { button.textContent = t("action.copy"); }, 1600);
  } catch {
    window.open(map.path, "_blank", "noopener");
  }
}

/* Section navigation: on a narrow screen, scroll the current section into view */
const currentChip = document.querySelector(".chip[aria-current]");
if (currentChip) {
  const row = currentChip.closest(".chips");
  const offset = currentChip.getBoundingClientRect().left - row.getBoundingClientRect().left;
  row.scrollLeft += offset - (row.clientWidth - currentChip.offsetWidth) / 2;
}

/* Cards of a section page: the maps come from the pre-rendered markup */
const maps = [...document.querySelectorAll(".card")].map((article) => {
  const map = { id: article.dataset.id, path: ROOT + article.dataset.path, bytes: Number(article.dataset.bytes) };
  const preview = article.querySelector(".preview");
  preview.addEventListener("click", () => openViewer(map, preview));
  const copy = article.querySelector("[data-copy]");
  copy.addEventListener("click", () => copySvg(map, copy));
  return map;
});

/* Enlarged view (section pages) */
const viewer = document.getElementById("viewer");
const viewerStage = document.getElementById("viewer-stage");
const viewerHolder = document.getElementById("viewer-holder");
const explorer = viewer && createExplorer(viewerStage, viewerHolder, { zoomable: true });
let current = null;
let opener = null;

function fillViewerText(map) {
  const name = t(`map.${map.id}`);
  document.getElementById("viewer-title").textContent = name;
  document.getElementById("viewer-text").textContent = t(`map.${map.id}.text`);
  viewerStage.setAttribute("aria-label", t("viewer.stage", { name }));
  const download = document.getElementById("viewer-download");
  download.href = map.path;
  download.setAttribute("download", fileName(map));
  document.getElementById("viewer-copy").textContent = t("action.copy");
  const named = viewerHolder.querySelector("svg") && current?.named;
  const mode = coarse.matches ? "touch" : "mouse";
  document.getElementById("viewer-hint").textContent = t(named ? `viewer.hint.${mode}` : `viewer.hint.plain.${mode}`);
}

async function openViewer(map, trigger) {
  current = { ...map, named: false };
  opener = trigger || null;
  explorer.clear();
  const status = Object.assign(document.createElement("p"), { className: "status", textContent: t("viewer.loading") });
  viewerHolder.replaceChildren(status);
  fillViewerText(current);
  if (!viewer.open) viewer.showModal();
  // Deep link: ?open=<map id> reopens this view (also read on page load, see below).
  const url = new URL(location.href);
  url.searchParams.set("open", map.id);
  history.replaceState(null, "", url);
  try {
    const text = await fetchSvg(map.path);
    if (current?.id !== map.id || !viewer.open) return;
    const info = inlineSvg(text);
    info.svg.setAttribute("role", "img");
    info.svg.setAttribute("aria-label", t(`map.${map.id}`));
    current.named = info.named;
    explorer.load(info);
    fillViewerText(current);
  } catch {
    if (current?.id === map.id) status.textContent = t("viewer.error");
  }
}

if (viewer) {
  document.getElementById("viewer-close").addEventListener("click", () => viewer.close());
  document.getElementById("viewer-copy").addEventListener("click", (event) => { if (current) copySvg(current, event.currentTarget); });
  viewer.addEventListener("click", (event) => { if (event.target === viewer) viewer.close(); });
  viewer.addEventListener("close", () => {
    explorer.clear();
    viewerHolder.replaceChildren();
    current = null;
    const url = new URL(location.href);
    url.searchParams.delete("open");
    history.replaceState(null, "", url);
    if (opener?.isConnected) opener.focus();
    opener = null;
  });
}

/* Language switch */
document.querySelectorAll(".lang button").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.lang === locale) return;
    locale = button.dataset.lang;
    const url = new URL(location.href);
    url.searchParams.set("lang", locale);
    history.replaceState(null, "", url);
    load();
  });
});
coarse.addEventListener?.("change", () => { renderHint(); if (current) fillViewerText(current); });

/* Hero of the home page: the communes map, live (ids stripped to keep them unique in the page). */
const heroStage = document.getElementById("hero-stage");
const heroExplorer = heroStage && createExplorer(heroStage, document.getElementById("hero-holder"), { zoomable: false });

function renderHint() {
  if (!heroStage) return;
  document.getElementById("hero-hint").textContent = t(coarse.matches ? "page.hero.hint.touch" : "page.hero.hint.mouse");
  heroStage.querySelector("svg")?.setAttribute("aria-label", t(`map.${heroStage.dataset.id}`));
}

/*
 * Old single-page links: ?open=<map id> and #family-<id> lead to the section page that holds the map;
 * on a section page, ?open= opens the viewer.
 */
async function followRequest() {
  const id = new URLSearchParams(location.search).get("open");
  const anchor = PAGE === "home" && location.hash.match(/^#family-([\w-]+)$/)?.[1];
  if (!id) {
    if (anchor && document.querySelector(`.tile[data-family="${CSS.escape(anchor)}"]`)) location.replace(`${anchor}/${location.search}`);
    return false;
  }
  const local = maps.find((map) => map.id === id);
  if (local) { openViewer(local, null); return false; }
  try {
    const catalog = await fetch(`${ROOT}dist/catalog.json`).then((response) => response.json());
    const entry = catalog.find((map) => map.id === id);
    if (entry && entry.family !== SECTION) { location.replace(`${ROOT}${entry.family}/${location.search}`); return true; }
  } catch { /* unknown map: stay on this page */ }
  return false;
}

load().then(async () => {
  if (await followRequest() || !heroStage) return;
  try {
    const info = inlineSvg(await fetchSvg(ROOT + heroStage.dataset.path), { keepIds: false });
    info.svg.setAttribute("role", "img");
    heroExplorer.load(info);
    renderHint();
  } catch { /* the hero map is decorative: the sections below stay usable */ }
});
