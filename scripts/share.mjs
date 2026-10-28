// Render the link-preview image of each page (1200 × 630 PNG): its cover map on the sea colour.

import { mkdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = fileURLToPath(new URL("..", import.meta.url));
const site = JSON.parse(await readFile(`${root}templates/site.json`, "utf8"));
const catalog = JSON.parse(await readFile(`${root}dist/catalog.json`, "utf8"));

const WIDTH = 1200;
const HEIGHT = 630;
const MARGIN = 30;
const SEA = "#bcd8da";

async function render(name, map) {
  const svg = await readFile(`${root}${map.path}`);
  const picture = await sharp(svg, { density: 300 })
    .resize(WIDTH - 2 * MARGIN, HEIGHT - 2 * MARGIN, { fit: "inside" })
    .png()
    .toBuffer();
  await sharp({ create: { width: WIDTH, height: HEIGHT, channels: 3, background: SEA } })
    .composite([{ input: picture, gravity: "centre" }])
    .png({ compressionLevel: 9 })
    .toFile(`${root}assets/share/${name}.png`);
  console.log(`assets/share/${name}.png`);
}

await mkdir(`${root}assets/share`, { recursive: true });
const byId = new Map(catalog.map((entry) => [entry.id, entry]));
await render("home", byId.get(site.share));
for (const { id, cover } of site.sections) {
  const map = byId.get(cover) ?? catalog.find((entry) => entry.family === id);
  if (map) await render(id, map);
}
