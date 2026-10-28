"""Download the IGN and Natural Earth sources into data/raw/ and extract them into data/src/."""

import urllib.request
import zipfile
from pathlib import Path

import py7zr

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SRC = ROOT / "data" / "src"

IGN = "https://data.geopf.fr/telechargement/download"
SOURCES = [
    f"{IGN}/ADMIN-EXPRESS-COG/ADMIN-EXPRESS-COG_4-0__GPKG_RGM04UTM38S_MYT_2026-01-01/ADMIN-EXPRESS-COG_4-0__GPKG_RGM04UTM38S_MYT_2026-01-01.7z",
    f"{IGN}/BDTOPO/BDTOPO_3-5_TOUSTHEMES_GPKG_RGM04UTM38S_D976_2026-09-15/BDTOPO_3-5_TOUSTHEMES_GPKG_RGM04UTM38S_D976_2026-09-15.7z",
    f"{IGN}/BDALTI/BDALTIV2_2-0_25M_ASC_RGM04UTM38S-MAYO53_D976_2013-12-19/BDALTIV2_2-0_25M_ASC_RGM04UTM38S-MAYO53_D976_2013-12-19.7z",
    "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
    "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip",
]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for url in SOURCES:
        archive = RAW / url.rsplit("/", 1)[1]
        if not archive.exists():
            print(f"downloading {archive.name}")
            urllib.request.urlretrieve(url, archive)
        target = SRC / archive.name.rsplit(".", 1)[0]
        if target.exists():
            continue
        target.mkdir(parents=True)
        if archive.suffix == ".7z":
            with py7zr.SevenZipFile(archive) as content:
                content.extractall(target)
        else:
            with zipfile.ZipFile(archive) as content:
                content.extractall(target)
        print(f"extracted {target.name}")


if __name__ == "__main__":
    main()
