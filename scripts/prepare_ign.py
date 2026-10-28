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
from rasterio.merge import merge
from shapely import force_2d, from_wkb
from shapely.geometry import mapping
from shapely.ops import unary_union

from derive_sentinel import contour_polygons, write

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "src"

RELIEF_STEP_M = 100
MIN_RELIEF_M2 = 20000


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


if __name__ == "__main__":
    administrative()
    topography()
    places()
    services()
    relief()
