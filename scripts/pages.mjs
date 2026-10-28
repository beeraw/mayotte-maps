// Generate the gallery pages (home and one page per section) from templates/, dist/catalog.json
// and the French strings. The browser script switches them to English (?lang=en).

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const read = (path) => readFile(`${root}${path}`, "utf8");
const json = async (path) => JSON.parse(await read(path));

const LOCALE = "fr";
const site = await json("templates/site.json");
const catalog = await json("dist/catalog.json");
const strings = await json(`i18n/${LOCALE}.json`);
const layout = await read("templates/layout.html");
const homeBody = await read("templates/home.html");
const sectionBody = await read("templates/section.html");
const fragments = Object.fromEntries(
  [...(await read("templates/fragments.html")).matchAll(/<template id="([\w-]+)">\n([\s\S]*?)\n<\/template>/g)]
    .map(([, id, html]) => [id, html]),
);

const escape = (text) =>
  String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function fill(template, values) {
  return template.replace(/\{\{(\w+)\}\}/g, (_, name) => {
    if (!(name in values)) throw new Error(`template slot without value: ${name}`);
    return values[name];
  });
}
const fragment = (id, values = {}) => fill(fragments[id], values);

function t(key, values = {}) {
  if (!(key in strings)) throw new Error(`i18n/${LOCALE}.json: missing key ${key}`);
  return strings[key].replace(/\{(\w+)\}/g, (_, name) => values[name] ?? "");
}
const number = (n, options) => n.toLocaleString(LOCALE, options);
const countLabel = (n) => t(n === 1 ? "family.count.one" : "family.count.other", { n: number(n) });
const sizeLabel = (bytes) => t("unit.kb", { size: number(bytes / 1024, { maximumFractionDigits: bytes < 10240 ? 1 : 0 }) });

/*
 * Pre-renders the data-i18n* attributes, as the browser script does at runtime: text of empty
 * elements (data-i18n, data-count, data-filesize) and translated attributes.
 */
const ATTRIBUTES = { "data-i18n-label": "aria-label", "data-i18n-title": "title", "data-i18n-content": "content", "data-i18n-alt": "alt" };

function localize(html) {
  return html.replace(/<([a-z][\w-]*)((?:\s+[\w-]+(?:="[^"]*")?)*)\s*>(<\/\1>)?/g, (tag, name, attrs, close) => {
    const list = Object.fromEntries([...attrs.matchAll(/([\w-]+)(?:="([^"]*)")?/g)].map(([, key, value]) => [key, value ?? ""]));
    if (!Object.keys(list).some((key) => key.startsWith("data-i18n") || key === "data-count" || key === "data-filesize")) return tag;
    const vars = Object.fromEntries((list["data-i18n-vars"] || "").split(/\s+/).filter(Boolean)
      .map((pair) => { const [variable, key] = pair.split(":"); return [variable, t(key)]; }));
    for (const [source, target] of Object.entries(ATTRIBUTES)) {
      if (!(source in list)) continue;
      const value = `${target}="${escape(t(list[source], vars))}"`;
      const existing = new RegExp(`\\s${target}="[^"]*"`);
      attrs = existing.test(attrs) ? attrs.replace(existing, ` ${value}`) : `${attrs} ${value}`;
    }
    let text = "";
    if ("data-i18n" in list) text = escape(t(list["data-i18n"], vars));
    else if ("data-count" in list) text = escape(countLabel(Number(list["data-count"])));
    else if ("data-filesize" in list) text = escape(sizeLabel(Number(list["data-filesize"])));
    return close ? `<${name}${attrs}>${text}${close}` : `<${name}${attrs}>`;
  });
}

const sections = site.sections.map(({ id, cover }) => {
  const maps = catalog.filter((entry) => entry.family === id);
  const chosen = maps.find((entry) => entry.id === cover);
  if (cover && !chosen) console.warn(`templates/site.json: cover ${cover} not in the catalog, using the first map of ${id}`);
  return { id, maps, cover: chosen ?? maps[0] };
});
for (const family of new Set(catalog.map((entry) => entry.family))) {
  if (!sections.some((section) => section.id === family)) console.warn(`family ${family} is in the catalog but not in templates/site.json: no page`);
}

const [creditBefore, creditAfter = ""] = t("page.credit", { author: "{author}" }).split("{author}");
const credit = fragment("credit", { before: escape(creditBefore), author: escape(t("page.author")), after: escape(creditAfter) });

async function write({ folder, page, section = "", titleKey, descriptionKey, metaVars = "", body }) {
  const base = folder ? "../" : "";
  const html = fill(layout, {
    title_key: titleKey,
    description_key: descriptionKey,
    meta_vars: metaVars,
    canonical: `${site.url}${folder ? `${folder}/` : ""}`,
    root: base,
    home: base || "./",
    page,
    section,
    body,
    credit,
  });
  if (folder) await mkdir(`${root}${folder}`, { recursive: true });
  await writeFile(`${root}${folder ? `${folder}/` : ""}index.html`, localize(html));
  console.log(`${folder ? `${folder}/` : ""}index.html`);
}

const filled = sections.filter((section) => section.maps.length);
const hero = catalog.find((entry) => entry.id === site.hero);
if (!hero) throw new Error(`templates/site.json: hero map ${site.hero} not in the catalog`);

await write({
  folder: "",
  page: "home",
  titleKey: "page.title",
  descriptionKey: "page.lead",
  body: fill(homeBody, {
    index: filled.map(({ id, maps }) => fragment("index-item", { id, href: `${id}/`, n: maps.length })).join("\n      "),
    hero_id: hero.id,
    hero_path: hero.path,
    tiles: filled.map(({ id, maps, cover }) =>
      fragment("tile", { id, href: `${id}/`, src: cover.path, cover: cover.id, n: maps.length })).join("\n    "),
  }),
});

for (const { id, maps } of sections) {
  const chips = sections.map((other) => fragment("chip", {
    id: other.id,
    href: `../${other.id}/`,
    class: other.maps.length ? "" : " is-empty",
    current: other.id === id ? ' aria-current="page"' : "",
    badge: other.maps.length ? fragment("chip-count", { n: other.maps.length }) : fragment("chip-soon"),
  })).join("\n    ");
  const cards = maps.map((map) => fragment("card", {
    id: map.id, path: map.path, src: `../${map.path}`, bytes: map.bytes, file: escape(map.path.split("/").pop()),
  })).join("\n      ");
  await write({
    folder: id,
    page: "section",
    section: id,
    titleKey: "section.meta.title",
    descriptionKey: "section.meta.description",
    metaVars: `name:family.${id} text:family.${id}.text`,
    body: fill(sectionBody, {
      id,
      chips,
      count: maps.length ? fragment("count", { n: maps.length }) : "",
      content: maps.length ? fragment("grid", { cards }) : fragment("empty"),
    }),
  });
}
