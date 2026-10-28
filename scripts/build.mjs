// Build the SVG, GeoJSON and TopoJSON maps from the layers in data/work/.

import { mkdir, readdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { basename } from "node:path";
import { fileURLToPath } from "node:url";
import mapshaper from "mapshaper";

const root = fileURLToPath(new URL("..", import.meta.url));
const work = `${root}data/work`;
const dist = `${root}dist`;
const naturalEarth = `${root}data/src`;

const CRS = "EPSG:4471";
const WIDTH = 1000;

// Shared frames, so that maps of the same frame overlay exactly
const FRAMES = {
  island: `-i ${work}/land.geojson name=frame -proj init=${CRS} -dissolve -rectangle offset=1500`,
  lagoon: `-i ${work}/lagoon.geojson name=frame -proj init=${CRS} -rectangle offset=1500`,
};

const STYLE = {
  land: "fill='#e4dccb' stroke='none'",
  landOutline: "fill='#e4dccb' stroke='#8c8270' stroke-width=1.5",
  lagoon: "fill='#cfe9ec' stroke='none'",
  reef: "fill='#8fd3cb' stroke='none'",
  division: "fill='#e4dccb' stroke='#ffffff' stroke-width=0.8",
  rivers: "stroke='#3d8fc1' stroke-width=0.6 fill='none'",
  mangroves: "fill='#4f8a5b' stroke='none'",
  villages: "fill='#5a4f3f' r=1.6",
};

// Named places: colour and radius by kind, the settlements first
const PLACE_STYLES = {
  village: ["#4a3b2a", 2.6],
  neighbourhood: ["#8a7d6b", 1.6],
  locality: ["#d17a22", 1.8],
  wood: ["#4f8a5b", 1.8],
  tree: ["#4f8a5b", 1.8],
  beach: ["#c9a227", 1.6],
  summit: ["#8b5a3c", 1.8],
  pass: ["#8b5a3c", 1.6],
  escarpment: ["#8b5a3c", 1.6],
  rocks: ["#8b5a3c", 1.6],
  isthmus: ["#8b5a3c", 1.6],
  islet: ["#2b7a78", 1.8],
  cape: ["#2b7a78", 1.6],
  reef: ["#2b7a78", 1.6],
};

function byKind(index) {
  const value = (style) => (typeof style[index] === "string" ? `'${style[index]}'` : style[index]);
  return Object.entries(PLACE_STYLES).map(([kind, style]) => `kind == '${kind}' ? ${value(style)}`).join(" : ");
}

// Buildings by usage: muted tones that stay legible on the land background
const BUILDING_COLORS = {
  residential: "#7d5f4b",
  commercial: "#c4553d",
  industrial: "#5d6875",
  agricultural: "#7a8c46",
  religious: "#2b7a78",
  sports: "#d19a2a",
  other: "#a39478",
};

const RELIEF_COLORS =["#dfe6c6", "#c9d8a6", "#b6c98e", "#c8b98a", "#b39c72", "#9a8060", "#86705a"];

const SIMPLIFY = { detailed: 5, standard: 25, simple: 150 };

function layer(name, options = "") {
  return `-i ${work}/${name}.geojson name=${name} -proj init=${CRS} ${options}`;
}

function idField(prefix) {
  return `-each 'svg_id = "${prefix}-" + code'`;
}

async function svg(file, frame, layers, svgData = "") {
  const output = `${dist}/svg/${file}`;
  const names = ["frame", ...layers.map((entry) => entry.split(" ")[2].replace("name=", ""))];
  const commands = [
    FRAMES[frame],
    ...layers,
    `-o ${output} target=${names.slice(1).join(",")} fit-extent=frame width=${WIDTH} id-field=svg_id ${svgData}`,
  ];
  await mapshaper.runCommands(commands.join(" "));
  console.log(`svg/${file}`);
}

async function silhouettes() {
  for (const [level, interval] of Object.entries(SIMPLIFY)) {
    const minArea = level === "simple" ? "-filter-islands min-area=100000" : "";
    const suffix = level === "standard" ? "" : `-${level}`;
    await svg(`silhouette/mayotte${suffix}.svg`, "island", [
      `${layer("land")} -dissolve -simplify interval=${interval} ${minArea} -style ${STYLE.land}`,
    ]);
  }
  await svg("silhouette/mayotte-outline.svg", "island", [
    `${layer("land")} -dissolve -simplify interval=${SIMPLIFY.standard} -style ${STYLE.landOutline} fill=none`,
  ]);
  await svg("silhouette/mayotte-lagoon.svg", "lagoon", [
    `${layer("lagoon")} -simplify interval=${SIMPLIFY.standard} -style ${STYLE.lagoon}`,
    `${layer("reef")} -simplify interval=${SIMPLIFY.standard} -style ${STYLE.reef}`,
    `${layer("land")} -dissolve -simplify interval=${SIMPLIFY.standard} -style ${STYLE.land}`,
  ]);
}

async function administrative() {
  const data = "svg-data=code,name";
  await svg("administrative/communes.svg", "island", [
    `${layer("communes")} -simplify interval=20 keep-shapes ${idField("commune")} -style ${STYLE.division}`,
  ], data);
  await svg("administrative/cantons.svg", "island", [
    `${layer("cantons")} -simplify interval=20 keep-shapes ${idField("canton")} -style ${STYLE.division}`,
  ], data);
  await svg("administrative/epci.svg", "island", [
    `${layer("epci")} -simplify interval=20 keep-shapes ${idField("epci")} -style ${STYLE.division}`,
  ], data);
  await svg("administrative/villages.svg", "island", [
    `${layer("communes")} -simplify interval=20 keep-shapes ${idField("commune")} -style ${STYLE.division}`,
    `${layer("villages")} -each 'svg_id = "village-" + slug' -style ${STYLE.villages}`,
  ], "svg-data=code,name,commune");
  await svg("administrative/places.svg", "island", [
    `${layer("communes")} -simplify interval=20 keep-shapes ${idField("commune")} -style ${STYLE.division}`,
    `${layer("places")} -each 'svg_id = "place-" + slug' -style fill="${byKind(0)} : '#000'" r="${byKind(1)} : 1.6"`,
  ], "svg-data=code,name,kind,commune");
}

async function physical() {
  const relief = RELIEF_COLORS.map((color, index) => `above_m == ${index * 100} ? '${color}'`).join(" : ");
  await svg("physical/relief.svg", "island", [
    `${layer("relief")} -simplify interval=20 -each 'svg_id = "relief-" + above_m' -style fill="${relief} : 'none'" stroke=none`,
  ], "svg-data=above_m");
  await svg("physical/hydrography.svg", "island", [
    `${layer("land")} -dissolve -simplify interval=${SIMPLIFY.standard} -style ${STYLE.land}`,
    `${layer("mangroves")} -simplify interval=10 -style ${STYLE.mangroves}`,
    `${layer("rivers")} -simplify interval=10 -style ${STYLE.rivers}`,
  ]);
  await svg("physical/lagoon.svg", "lagoon", [
    `${layer("lagoon")} -simplify interval=${SIMPLIFY.detailed} -style ${STYLE.lagoon}`,
    `${layer("reef")} -simplify interval=${SIMPLIFY.detailed} -style ${STYLE.reef}`,
    `${layer("land")} -dissolve -simplify interval=${SIMPLIFY.detailed} -style ${STYLE.land}`,
  ]);
}

// Rewrites path data as relative moves in hundredths: same shapes, far fewer bytes
function compactPathData(d) {
  const number = (value) => (value / 100).toString().replace(/^(-?)0\./, "$1.");
  // A separator is needed only where the next number could be read as part of the previous one
  const join = (values) => values.map(number).map((value, index, all) => {
    const glued = value.startsWith("-") || (value.startsWith(".") && all[index - 1]?.includes("."));
    return (index && !glued ? " " : "") + value;
  }).join("");
  let x = 0;
  let y = 0;
  return d.split("Z").filter((ring) => ring.trim()).map((ring) => {
    const values = ring.replace("M", "").trim().split(/\s+/).map((value) => Math.round(Number(value) * 100));
    const points = [];
    for (let i = 0; i < values.length; i += 2) points.push([values[i], values[i + 1]]);
    const [first, last] = [points[0], points.at(-1)];
    if (points.length > 1 && first[0] === last[0] && first[1] === last[1]) points.pop();
    const move = `m${join([first[0] - x, first[1] - y])}`;
    [x, y] = first;
    const steps = points.slice(1).map(([px, py], i) => [px - points[i][0], py - points[i][1]]);
    return `${move}${steps.length ? `l${join(steps.flat())}` : ""}z`;
  }).join("");
}

async function compactSvg(file) {
  const path = `${dist}/svg/${file}`;
  const text = await readFile(path, "utf8");
  await writeFile(path, text.replace(/ d="([^"]*)"/g, (_, d) => ` d="${compactPathData(d)}"`));
}

async function built() {
  const fill = Object.entries(BUILDING_COLORS).map(([kind, color]) => `kind == '${kind}' ? '${color}'`).join(" : ");
  await svg("built/buildings.svg", "island", [
    `${layer("land")} -dissolve -simplify interval=${SIMPLIFY.standard} -style ${STYLE.land}`,
    `${layer("buildings")} -each 'svg_id = "buildings-" + kind' -style fill="${fill} : '#000'" stroke=none`,
  ], "svg-data=kind,count,area_ha");
  await compactSvg("built/buildings.svg");
}

async function situation() {
  const regions = {
    "mozambique-channel": { bbox: "30,-27,52,-8", projection: "+proj=laea +lat_0=-17 +lon_0=41", locator: true },
    "comoros-archipelago": { bbox: "43,-13.2,45.5,-11.2", projection: "+proj=laea +lat_0=-12.3 +lon_0=44.3", locator: false },
  };
  for (const [name, { bbox, projection, locator }] of Object.entries(regions)) {
    // At small scale the island is a dot: circle it
    const locatorLayer = locator
      ? [
          `-i ${work}/land.geojson name=locator -proj init=${CRS} -dissolve -points centroid`,
          `-each 'svg_id = "mayotte-locator"' -proj ${projection} -style r=14 fill=none stroke='#c4553d' stroke-width=1.5`,
        ]
      : [];
    const targets = locator ? "countries,mayotte,locator" : "countries,mayotte";
    const commands = [
      `-rectangle bbox=${bbox} name=frame -densify interval=5000 -proj ${projection}`,
      `-i ${naturalEarth}/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp name=countries`,
      `-clip bbox=${bbox} -filter 'ADM0_A3 != "FRA"' -each 'svg_id = "country-" + ADM0_A3.toLowerCase()'`,
      `-proj ${projection} -style fill='#e4dccb' stroke='#ffffff' stroke-width=0.6`,
      `-i ${work}/land.geojson name=mayotte -proj init=${CRS} -dissolve -simplify interval=${SIMPLIFY.standard}`,
      `-each 'svg_id = "mayotte"' -proj ${projection} -style fill='#c4553d' stroke='none'`,
      ...locatorLayer,
      `-o ${dist}/svg/situation/${name}.svg target=${targets} fit-extent=frame width=${WIDTH} id-field=svg_id`,
    ];
    await mapshaper.runCommands(commands.join(" "));
    console.log(`svg/situation/${name}.svg`);
  }
}

async function geodata() {
  const layers = ["land", "lagoon", "reef", "communes", "cantons", "epci", "villages", "places", "rivers", "mangroves", "relief"];
  for (const name of layers) {
    await mapshaper.runCommands(
      `${layer(name)} -simplify interval=5 keep-shapes -proj wgs84 -o ${dist}/geojson/mayotte-${name}.geojson precision=0.000001`,
    );
  }
  // Already generalised in prepare_ign.py: a 5 m simplification would flatten the footprints
  await mapshaper.runCommands(
    `${layer("buildings")} -proj wgs84 -o ${dist}/geojson/mayotte-buildings.geojson precision=0.000001`,
  );
  const inputs = layers.map((name) => `${work}/${name}.geojson`).join(" ");
  await mapshaper.runCommands(
    `-i ${inputs} combine-files -proj init=${CRS} target=* -simplify interval=20 keep-shapes target=* ` +
      `-proj wgs84 target=* -o ${dist}/topojson/mayotte.json format=topojson target=* quantization=100000`,
  );
  console.log("geojson/, topojson/mayotte.json");
}

// Gallery order: the most common map of each family first
const CATALOG_ORDER = {
  silhouette: ["mayotte", "mayotte-detailed", "mayotte-simple", "mayotte-outline", "mayotte-lagoon"],
  administrative: ["communes", "cantons", "epci", "villages", "places"],
  physical: ["relief", "hydrography", "lagoon"],
  built: ["buildings"],
  situation: ["mozambique-channel", "comoros-archipelago"],
};

async function catalog() {
  const entries = [];
  for (const [family, order] of Object.entries(CATALOG_ORDER)) {
    const rank = (file) => order.indexOf(basename(file, ".svg")) >>> 0;
    for (const file of (await readdir(`${dist}/svg/${family}`)).sort((a, b) => rank(a) - rank(b))) {
      const { size } = await stat(`${dist}/svg/${family}/${file}`);
      entries.push({ id: `${family}.${basename(file, ".svg")}`, family, path: `dist/svg/${family}/${file}`, bytes: size });
    }
  }
  await writeFile(`${dist}/catalog.json`, JSON.stringify(entries, null, 2));
  console.log(`catalog.json: ${entries.length} maps`);
}

await rm(dist, { recursive: true, force: true });
for (const folder of ["svg/silhouette", "svg/administrative", "svg/physical", "svg/built", "svg/situation", "geojson", "topojson"]) {
  await mkdir(`${dist}/${folder}`, { recursive: true });
}
await silhouettes();
await administrative();
await physical();
await built();
await situation();
await geodata();
await catalog();
