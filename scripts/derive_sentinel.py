"""Derive land, reef and lagoon polygons from the Sentinel-2 mosaic.

Outputs GeoJSON files in RGM04 / UTM 38S (EPSG:4471) coordinates in data/work/.
"""

import json
from functools import reduce
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union
from skimage.measure import find_contours

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "data" / "work"

CLOUD_CLASSES = (3, 8, 9, 10)  # SCL: cloud shadow, medium and high probability cloud, cirrus
SHALLOW_GREEN = 450  # deep water stays around 270-350
MIN_ISLET_M2 = 3000
MIN_REEF_M2 = 20000
MIN_REEF_HOLE_M2 = 20000
MIN_STRUCTURE_M2 = 500000
MAX_REEF_DISTANCE_M = 13000
LAGOON_REACH_M = 2500
LAGOON_SMOOTHING_M = 3000


def contour_polygons(mask, transform, min_area):
    """Sub-pixel outline of a boolean mask, holes included."""
    field = ndimage.gaussian_filter(np.pad(mask, 2).astype(float), sigma=1.0)
    rings = []
    for contour in find_contours(field, 0.5):
        if len(contour) < 4:
            continue
        rows, cols = contour[:, 0] - 2, contour[:, 1] - 2
        xs, ys = transform * (cols + 0.5, rows + 0.5)
        ring = Polygon(zip(xs, ys)).buffer(0)
        if ring.area >= min_area:
            rings.append(ring)
    # Nested rings alternate between outer shells and holes
    return reduce(lambda a, b: a.symmetric_difference(b), sorted(rings, key=lambda p: -p.area), Polygon())


def write(name, features):
    collection = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4471"}},
        "features": [{"type": "Feature", "properties": props, "geometry": mapping(geom)} for geom, props in features],
    }
    (WORK / f"{name}.geojson").write_text(json.dumps(collection))
    print(f"{name}: {len(features)} features")


def main():
    with rasterio.open(WORK / "sentinel2.tif") as source:
        blue, green, red, nir, scl = source.read().astype(float)
        transform = source.transform
        pixel_area = source.res[0] * source.res[1]

    cloud = np.isin(scl, CLOUD_CLASSES)
    ndwi = (green - nir) / np.maximum(green + nir, 1)

    land = (ndwi < 0) & ~cloud
    land = ndimage.binary_opening(land, iterations=1)
    labels, count = ndimage.label(land)
    sizes = ndimage.sum(land, labels, range(1, count + 1)) * pixel_area
    land = np.isin(labels, np.flatnonzero(sizes >= MIN_ISLET_M2) + 1)
    land = ndimage.binary_fill_holes(land)

    shallow = (ndwi >= 0) & (green > SHALLOW_GREEN) & ~cloud & ~land
    shallow = ndimage.binary_closing(ndimage.binary_opening(shallow, iterations=1), iterations=2) & ~land

    land_shape = contour_polygons(land, transform, MIN_ISLET_M2)
    shallow_shape = contour_polygons(shallow, transform, MIN_REEF_M2).difference(land_shape)

    shallow_parts = [Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area > MIN_REEF_HOLE_M2])
                     for p in getattr(shallow_shape, "geoms", [shallow_shape])]

    # The lagoon is the convex hull of the reef system: the western barrier is too deep
    # to be seen, and the ring is nearly convex. Patches far offshore are surf, glint
    # or cloud edges.
    main_island = max(getattr(land_shape, "geoms", [land_shape]), key=lambda p: p.area)
    reach = main_island.buffer(MAX_REEF_DISTANCE_M)
    structures = [p for p in shallow_parts if p.area >= MIN_STRUCTURE_M2 and reach.contains(p)]
    near_land = [p for p in getattr(land_shape, "geoms", [land_shape]) if reach.contains(p)]
    hull = unary_union([*near_land, *structures]).convex_hull
    # Pull the hull back onto the outer reef where it runs straight across open sea
    neighbourhood = unary_union([*near_land, *(p for p in shallow_parts if hull.contains(p))]).buffer(LAGOON_REACH_M)
    enclosed = hull.intersection(neighbourhood).buffer(LAGOON_SMOOTHING_M).buffer(-LAGOON_SMOOTHING_M)
    enclosed = Polygon(max(getattr(enclosed, "geoms", [enclosed]), key=lambda p: p.area).exterior)
    inside = enclosed.buffer(200)
    # Every islet of Mayotte lies within the lagoon: specks outside are cloud edges
    islands = sorted((p for p in getattr(land_shape, "geoms", [land_shape]) if inside.contains(p)), key=lambda p: -p.area)
    land_shape = unary_union(islands)
    lagoon = enclosed.difference(land_shape)

    reefs = sorted((p.difference(land_shape) for p in shallow_parts if inside.contains(p)), key=lambda p: -p.area)
    write("land", [(p, {"area_m2": round(p.area)}) for p in islands])
    write("reef", [(p, {"area_m2": round(p.area)}) for p in reefs])
    write("lagoon", [(lagoon, {"area_m2": round(lagoon.area)})])


if __name__ == "__main__":
    main()
