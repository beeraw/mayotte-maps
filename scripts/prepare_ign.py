"""Extract the IGN layers used by the maps into GeoJSON files in data/work/.

Coordinates stay in RGM04 / UTM 38S (EPSG:4471), like the sources.
"""

import glob
import re
import unicodedata
from pathlib import Path

import numpy as np
import pyogrio
import rasterio
import shapely
from rasterio.merge import merge
from shapely import force_2d, from_wkb
from shapely.geometry import mapping
from shapely.ops import linemerge, unary_union

from derive_sentinel import contour_polygons, write

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "src"

RELIEF_STEP_M = 100
MIN_RELIEF_M2 = 20000

# Building classes by main usage, mapped from the BD TOPO "usage_1" field
BUILDING_KINDS = {
    "Résidentiel": "residential",
    "Commercial et services": "commercial",
    "Industriel": "industrial",
    "Agricole": "agricultural",
    "Religieux": "religious",
    "Sportif": "sports",
    "Annexe": "other",
    "Indifférencié": "other",
}
MIN_BUILDING_M2 = 20
BUILDING_GAP_M = 2
BUILDING_TOLERANCE_M = 1.5


def slugify(text):
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def source(pattern):
    return glob.glob(str(SRC / pattern), recursive=True)[0]


def read(path, layer, columns, where=None):
    meta, _, geometry, fields = pyogrio.raw.read(path, layer=layer, columns=columns, where=where)
    rows = [dict(zip(meta["fields"], values)) for values in zip(*fields)] if fields else [{}] * len(geometry)
    return [(from_wkb(wkb), row) for wkb, row in zip(geometry, rows)]


def administrative():
    path = source("ADMIN-EXPRESS-COG*/**/*.gpkg")
    write("communes", [
        (geom, {"code": row["code_insee"], "name": row["nom_officiel"], "epci": row["codes_siren_des_epci"]})
        for geom, row in sorted(read(path, "commune", ["code_insee", "nom_officiel", "codes_siren_des_epci"]),
                                key=lambda item: item[1]["code_insee"])
    ])
    write("cantons", [
        (geom, {"code": row["code_insee"], "name": row["nom_officiel"]})
        for geom, row in sorted(read(path, "canton", ["code_insee", "nom_officiel"]), key=lambda item: item[1]["code_insee"])
    ])
    write("epci", [
        (geom, {"code": row["code_siren"], "name": row["nom_officiel"], "nature": row["nature"]})
        for geom, row in sorted(read(path, "epci", ["code_siren", "nom_officiel", "nature"]), key=lambda item: item[1]["code_siren"])
    ])


def topography():
    path = source("BDTOPO*/**/*.gpkg")
    villages = read(path, "zone_d_habitation", ["toponyme", "importance", "insee_commune"],
                    where="nature = 'Lieu-dit habité' AND toponyme IS NOT NULL")
    features = []
    for geom, row in sorted(villages, key=lambda item: (item[1]["importance"], item[1]["toponyme"])):
        slug = f"{row['insee_commune']}-{slugify(row['toponyme'])}"
        features.append((geom.representative_point(), {
            "slug": slug, "name": row["toponyme"], "commune": row["insee_commune"], "rank": int(row["importance"]),
        }))
    duplicates = {props["slug"] for _, props in features if sum(p["slug"] == props["slug"] for _, p in features) > 1}
    if duplicates:
        raise SystemExit(f"duplicate village identifiers: {sorted(duplicates)}")
    write("villages", features)

    rivers = read(path, "troncon_hydrographique", [], where="persistance = 'Permanent'")
    merged = unary_union([geom for geom, _ in rivers])
    write("rivers", [(merged, {})])

    mangroves = read(path, "zone_de_vegetation", [], where="nature = 'Mangrove'")
    merged = unary_union([geom.buffer(0) for geom, _ in mangroves])
    write("mangroves", [(part, {"area_m2": round(part.area)}) for part in getattr(merged, "geoms", [merged])])


PLACE_KINDS = {
    ("zone_d_habitation", "Lieu-dit habité"): "village",
    ("zone_d_habitation", "Quartier"): "neighbourhood",
    ("lieu_dit_non_habite", "Lieu-dit non habité"): "locality",
    ("lieu_dit_non_habite", "Bois"): "wood",
    ("lieu_dit_non_habite", "Arbre"): "tree",
    ("detail_orographique", "Plage"): "beach",
    ("detail_orographique", "Sommet"): "summit",
    ("detail_orographique", "Ile"): "islet",
    ("detail_orographique", "Cap"): "cape",
    ("detail_orographique", "Récif"): "reef",
    ("detail_orographique", "Col"): "pass",
    ("detail_orographique", "Rochers"): "rocks",
    ("detail_orographique", "Isthme"): "isthmus",
    ("detail_orographique", "Escarpement"): "escarpment",
}


def places():
    """Every named place: villages, neighbourhoods, localities and natural features."""
    communes = read(source("ADMIN-EXPRESS-COG*/**/*.gpkg"), "commune", ["code_insee"])
    path = source("BDTOPO*/**/*.gpkg")
    features = []
    for (layer, nature), kind in PLACE_KINDS.items():
        rows = read(path, layer, ["toponyme", "insee_commune"],
                    where=f"nature = '{nature.replace(chr(39), chr(39) * 2)}' AND toponyme IS NOT NULL")
        for geom, row in rows:
            point = geom.representative_point()
            # Islets and reefs lie offshore: fall back on the nearest commune
            commune = row["insee_commune"] or min(communes, key=lambda c: c[0].distance(point))[1]["code_insee"]
            features.append((point, {"name": row["toponyme"], "kind": kind, "commune": commune[:5]}))

    # Identifiers: commune and name, then the kind for homonyms, then a north-to-south rank
    features.sort(key=lambda item: (item[1]["commune"], item[1]["name"], -item[0].y))
    groups = {}
    for point, props in features:
        groups.setdefault(f"{props['commune']}-{slugify(props['name'])}", []).append(props)
    for base, members in groups.items():
        kinds = [props["kind"] for props in members]
        for props in members:
            slug = base if len(members) == 1 else f"{base}-{props['kind']}"
            if kinds.count(props["kind"]) > 1:
                rank = [p for p in members if p["kind"] == props["kind"]].index(props) + 1
                slug = f"{slug}-{rank}"
            props["slug"] = slug
    if len({props["slug"] for _, props in features}) != len(features):
        raise SystemExit("duplicate place identifiers")
    write("places", features)


SECURITY_NATURES = {
    "Caserne", "Caserne de pompiers", "Enceinte militaire", "Etablissement pénitentiaire",
    "Gendarmerie", "Police", "Surveillance maritime",
}
CULTURE_NATURES = {
    "Centre de documentation", "Ecomusée", "Monument", "Musée", "Salle de danse ou de jeux",
    "Salle de spectacle ou conférence", "Vestige archéologique",
}
TOURISM_NATURES = {
    "Construction", "Hébergement de loisirs", "Maison du parc", "Office de tourisme",
    "Point de vue", "Sentier de découverte",
}


def facility_kind(category, nature):
    if category == "Science et enseignement":
        return "health" if nature.startswith("Structure d'accueil") else "education"
    if category == "Santé":
        return "health"
    if category == "Administratif ou militaire":
        return "security" if nature in SECURITY_NATURES else "administration"
    if category == "Religieux":
        return "worship"
    if category == "Sport":
        return "sport"
    if category in ("Industriel et commercial", "Gestion des eaux"):
        return "economy"
    if nature == "Espace public":
        return "public-space"
    if nature in CULTURE_NATURES:
        return "culture"
    if nature in TOURISM_NATURES:
        return "tourism"
    raise SystemExit(f"unclassified facility: {category} / {nature}")


def services():
    """Named facilities and services as points, plus the airport and port areas."""
    communes = read(source("ADMIN-EXPRESS-COG*/**/*.gpkg"), "commune", ["code_insee"])
    path = source("BDTOPO*/**/*.gpkg")
    sources = [
        (geom, row["toponyme"], facility_kind(row["categorie"], row["nature"]), row["insee_commune"])
        for geom, row in read(path, "zone_d_activite_ou_d_interet", ["categorie", "nature", "toponyme", "insee_commune"],
                              where="toponyme IS NOT NULL AND etat_de_l_objet != 'En projet'")
    ]
    sources += [
        (geom, row["toponyme"], "transport", row["insee_commune"])
        for geom, row in read(path, "equipement_de_transport", ["toponyme", "insee_commune"],
                              where="toponyme IS NOT NULL AND (nature IN ('Port', 'Gare maritime', 'Gare routière') "
                                    "OR nature_detaillee = 'Parking relais')")
    ]
    airports = read(path, "aerodrome", ["toponyme"], where="toponyme IS NOT NULL")
    sources += [(geom, row["toponyme"], "transport", None) for geom, row in airports]

    features = []
    for geom, name, kind, commune in sources:
        point = force_2d(geom.representative_point())
        commune = commune or min(communes, key=lambda c: c[0].distance(point))[1]["code_insee"]
        features.append((point, {"name": name, "kind": kind, "commune": commune[:5]}))

    # Identifiers as in places(): commune and name, then the kind for homonyms, then a north-to-south rank
    features.sort(key=lambda item: (item[1]["commune"], item[1]["name"], -item[0].y))
    groups = {}
    for point, props in features:
        groups.setdefault(f"{props['commune']}-{slugify(props['name'])}", []).append(props)
    for base, members in groups.items():
        kinds = [props["kind"] for props in members]
        for props in members:
            slug = base if len(members) == 1 else f"{base}-{props['kind']}"
            if kinds.count(props["kind"]) > 1:
                rank = [p for p in members if p["kind"] == props["kind"]].index(props) + 1
                slug = f"{slug}-{rank}"
            props["slug"] = slug
    if len({props["slug"] for _, props in features}) != len(features):
        raise SystemExit("duplicate facility identifiers")
    write("services", features)

    # Areas large enough to read at island scale: airport grounds, runway, commercial port
    runway = read(path, "piste_d_aerodrome", [])
    port = read(path, "equipement_de_transport", [], where="nature_detaillee = 'Port de commerce'")
    write("services-areas", [
        *((force_2d(geom), {"area": "airport"}) for geom, _ in airports),
        *((force_2d(geom), {"area": "runway"}) for geom, _ in runway),
        *((force_2d(geom), {"area": "port"}) for geom, _ in port),
    ])


VEGETATION_KINDS = {
    "Forêt fermée de feuillus": "broadleaf-forest",
    "Bois": "woodlot",
    "Lande ligneuse": "shrubland",
    "Bananeraie": "banana-plantation",
    "Verger": "orchard",
    "Mangrove": "mangrove",
}

# Drawing order, the widest areas first. The marine park covers the whole exclusive economic zone: left out
PROTECTED_KINDS = {
    ("foret_publique", "Autre forêt publique"): "departmental-forest",
    ("foret_publique", "Forêt domaniale"): "state-forest",
    ("parc_ou_reserve", "Réserve naturelle"): "nature-reserve",
    ("parc_ou_reserve", "Terrain du Conservatoire du Littoral"): "coastal-conservancy",
    ("parc_ou_reserve", "Site Ramsar"): "ramsar-site",
    ("parc_ou_reserve", "Arrêté de protection"): "biotope-protection",
}

WATER_KINDS = {"Lac": "lake", "Retenue-barrage": "reservoir", "Retenue": "reservoir", "Lagune": "coastal-lagoon"}


def hectares(geom):
    return round(geom.area / 10000, 1)


def nature():
    """Vegetation cover, protected areas, intertidal zone and lakes."""
    path = source("BDTOPO*/**/*.gpkg")
    vegetation = read(path, "zone_de_vegetation", ["nature"])
    features = []
    for nature_name, kind in VEGETATION_KINDS.items():
        merged = unary_union([geom.buffer(0) for geom, row in vegetation if row["nature"] == nature_name])
        features.append((merged, {"kind": kind, "area_ha": hectares(merged)}))
    write("vegetation", features)

    features = []
    for (layer, nature_name), kind in PROTECTED_KINDS.items():
        rows = read(path, layer, ["toponyme"], where=f"nature = '{nature_name}'")
        for geom, row in sorted(rows, key=lambda item: -item[0].area):
            geom = geom.buffer(0)
            features.append((geom, {"slug": slugify(row["toponyme"]), "name": row["toponyme"], "kind": kind,
                                    "area_ha": hectares(geom)}))
    slugs = [props["slug"] for _, props in features]
    for _, props in features:
        if slugs.count(props["slug"]) > 1:
            props["slug"] = f"{props['slug']}-{props['kind']}"
    if len({props["slug"] for _, props in features}) != len(features):
        raise SystemExit("duplicate protected area identifiers")
    write("protected_areas", features)

    estran = unary_union([geom.buffer(0) for geom, _ in read(path, "zone_d_estran", [])])
    write("intertidal", [(estran, {"kind": "intertidal", "area_ha": hectares(estran)})])

    features = []
    for geom, row in sorted(read(path, "plan_d_eau", ["nature", "toponyme"]), key=lambda item: -item[0].area):
        kind = WATER_KINDS[row["nature"]]
        props = {"slug": slugify(row["toponyme"]) if row["toponyme"] else kind, "kind": kind, "area_ha": hectares(geom)}
        if row["toponyme"]:
            props["name"] = row["toponyme"]
        features.append((geom, props))
    write("lakes", features)


def buildings():
    """Footprints merged by class: neighbours closer than the gap become one block, sheds are dropped."""
    rows = read(source("BDTOPO*/**/*.gpkg"), "batiment", ["usage_1"])
    groups = {}
    for geom, row in rows:
        groups.setdefault(BUILDING_KINDS[row["usage_1"]], []).append(shapely.force_2d(geom))
    features = []
    for kind in dict.fromkeys(BUILDING_KINDS.values()):
        footprints = np.array(groups[kind])
        kept = footprints[shapely.area(footprints) >= MIN_BUILDING_M2]
        grown = shapely.buffer(kept, BUILDING_GAP_M, join_style="mitre", quad_segs=1)
        merged = shapely.union_all(grown).buffer(-BUILDING_GAP_M, join_style="mitre")
        shape = shapely.simplify(merged, BUILDING_TOLERANCE_M)
        area_ha = round(shapely.area(footprints).sum() / 10000, 1)
        features.append((shape, {"kind": kind, "count": len(footprints), "area_ha": area_ha}))
    write("buildings", features)


def relief():
    tiles = [rasterio.open(path) for path in glob.glob(str(SRC / "BDALTI*/**/*_MNT_*.asc"), recursive=True)]
    # The tiles carry no CRS: passing nodata to merge() blanks them, their own -99999 is kept instead
    elevation, transform = merge(tiles)
    elevation = elevation[0]
    for tile in tiles:
        tile.close()
    top = int(elevation.max())
    print(f"highest point in the elevation model: {top} m")

    # Each feature is the area above a level, meant to be stacked bottom to top
    features = []
    for floor in range(0, top, RELIEF_STEP_M):
        shape = contour_polygons(elevation > max(floor, 0.5), transform, MIN_RELIEF_M2)
        if not shape.is_empty:
            features.append((shape, {"above_m": floor}))
    write("relief", features)


ROAD_COLUMNS = ["nature", "importance", "cpx_numero", "cpx_classement_administratif", "cpx_toponyme_route_nommee",
                "nom_voie_ban_gauche", "nom_voie_ban_droite", "insee_commune_gauche", "insee_commune_droite"]
ROUTE_KINDS = {"Nationale": "national", "Départementale": "departmental"}
TRACK_NATURES = ("Chemin", "Route empierrée")
TRAIL_KINDS = {"Sentier": "trail", "Escalier": "steps"}


def merged(geoms):
    """One line geometry per group: segments joined end to end, without the Z values."""
    union = unary_union([force_2d(geom) for geom in geoms])
    return linemerge(union) if union.geom_type == "MultiLineString" else union


def complete(props):
    """Same fields on every feature, null when absent, so that no attribute reads "undefined"."""
    return {key: props.get(key) for key in ("slug", "ref", "kind", "name", "commune")}


def named_groups(segments, kind):
    """Segments grouped by street name and commune; unnamed ones dissolved together."""
    groups = {}
    for geom, row in segments:
        name = row["nom_voie_ban_gauche"] or row["nom_voie_ban_droite"]
        commune = row["insee_commune_gauche"] or row["insee_commune_droite"]
        key = (name, commune) if name and commune else (None, None)
        groups.setdefault(key, []).append(geom)
    features = []
    for (name, commune), geoms in sorted(groups.items(), key=lambda item: (item[0][1] or "", item[0][0] or "")):
        props = {"kind": kind}
        if name:
            props.update(name=name, commune=commune)
        features.append((merged(geoms), props))
    return features


def roads():
    """Road network: numbered roads one feature per number, sea links, then the local network by class."""
    path = source("BDTOPO*/**/*.gpkg")
    segments = read(path, "troncon_de_route", ROAD_COLUMNS, where="etat_de_l_objet = 'En service'")
    features = []

    numbered = {}
    for geom, row in segments:
        if row["cpx_numero"]:
            numbered.setdefault(row["cpx_numero"], []).append((geom, row))
    # Nationals last, so that they are drawn (and hovered) on top
    order = sorted(numbered, key=lambda ref: (ref[0] != "D", int(re.sub(r"\D", "", ref) or 0), ref))
    for ref in order:
        rows = numbered[ref]
        kind = "national" if ref.startswith("N") else "departmental"
        props = {"slug": slugify(ref), "ref": ref, "kind": kind}
        # A street name is kept only when it covers the whole road (Route de Moya = D9)
        names = {row["cpx_toponyme_route_nommee"] for _, row in rows}
        if len(names) == 1 and None not in names:
            props["name"] = names.pop()
        features.append((merged([geom for geom, _ in rows]), props))

    for geom, row in segments:
        if row["nature"] == "Bac ou liaison maritime":
            name = row["cpx_toponyme_route_nommee"]
            features.append((force_2d(geom), {"slug": slugify(name), "kind": "ferry", "name": name}))

    unnumbered = [(geom, row) for geom, row in segments if not row["cpx_numero"]]
    roads_only = [(geom, row) for geom, row in unnumbered
                  if row["nature"] in ("Route à 1 chaussée", "Route à 2 chaussées", "Rond-point")]
    local_classes = [
        ("secondary", [item for item in roads_only if item[1]["importance"] in ("2", "3", "4")]),
        ("local", [item for item in roads_only if item[1]["importance"] not in ("2", "3", "4")]),
        ("track", [item for item in unnumbered if item[1]["nature"] in TRACK_NATURES]),
    ]
    # Local classes are drawn first, under the numbered roads
    network = [feature for kind, items in local_classes for feature in named_groups(items, kind)]
    write("roads", [(geom, complete(props)) for geom, props in network + features])


def trails():
    """Footpaths and steps, grouped by street name where the BAN gives one."""
    path = source("BDTOPO*/**/*.gpkg")
    features = []
    for nature, kind in TRAIL_KINDS.items():
        segments = read(path, "troncon_de_route", ROAD_COLUMNS,
                        where=f"etat_de_l_objet = 'En service' AND nature = '{nature}'")
        features += named_groups(segments, kind)
    write("trails", [(geom, complete(props)) for geom, props in features])


if __name__ == "__main__":
    administrative()
    topography()
    places()
    services()
    nature()
    buildings()
    relief()
    roads()
    trails()
