"""Read the Sentinel-2 L2A scenes covering Mayotte and mosaic them on a 10 m grid.

Only the window around the island is read from the cloud-optimised GeoTIFFs
published on AWS Open Data (Element 84 Earth Search), no account needed.
"""

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

DATE = "2025-09-02"
TARGET_CRS = "EPSG:4471"  # RGM04 / UTM zone 38S
# Island, reef barrier and a margin, in RGM04 / UTM 38S metres
BOUNDS = (488000, 8550000, 538000, 8618000)
RESOLUTION = 10
BANDS = {"blue": "blue", "green": "green", "red": "red", "nir": "nir", "scl": "scl"}

OUT = Path(__file__).resolve().parent.parent / "data" / "work" / "sentinel2.tif"


def search_items():
    body = {
        "collections": ["sentinel-2-l2a"],
        "intersects": {
            "type": "Polygon",
            "coordinates": [[[44.91, -13.06], [45.35, -13.06], [45.35, -12.49], [44.91, -12.49], [44.91, -13.06]]],
        },
        "datetime": f"{DATE}T00:00:00Z/{DATE}T23:59:59Z",
        "limit": 50,
    }
    request = urllib.request.Request(
        "https://earth-search.aws.element84.com/v1/search",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        features = json.load(response)["features"]
    # Several processing baselines may exist for one tile: keep the latest
    latest = {}
    for feature in features:
        tile = feature["id"].split("_")[1]
        if tile not in latest or feature["id"] > latest[tile]["id"]:
            latest[tile] = feature
    return list(latest.values())


def main():
    items = search_items()
    print(f"{len(items)} tiles: {', '.join(sorted(i['id'] for i in items))}")

    width = (BOUNDS[2] - BOUNDS[0]) // RESOLUTION
    height = (BOUNDS[3] - BOUNDS[1]) // RESOLUTION
    transform = from_origin(BOUNDS[0], BOUNDS[3], RESOLUTION, RESOLUTION)
    mosaic = np.zeros((len(BANDS), height, width), dtype=np.uint16)

    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        for index, asset in enumerate(BANDS.values()):
            for item in items:
                href = item["assets"][asset]["href"]
                with rasterio.open(href) as source:
                    layer = np.zeros((height, width), dtype=np.uint16)
                    reproject(
                        rasterio.band(source, 1),
                        layer,
                        dst_transform=transform,
                        dst_crs=TARGET_CRS,
                        dst_nodata=0,
                        resampling=Resampling.nearest,
                    )
                empty = mosaic[index] == 0
                mosaic[index][empty] = layer[empty]
            print(f"  {asset} done", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": "uint16",
        "count": len(BANDS),
        "width": width,
        "height": height,
        "crs": TARGET_CRS,
        "transform": transform,
        "nodata": 0,
        "compress": "deflate",
        "tiled": True,
    }
    with rasterio.open(OUT, "w", **profile) as target:
        target.write(mosaic)
        for index, name in enumerate(BANDS, start=1):
            target.set_band_description(index, name)
    print(f"written {OUT}")


if __name__ == "__main__":
    sys.exit(main())
