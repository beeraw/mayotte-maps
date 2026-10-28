"""Download the IGN, Natural Earth and INSEE sources into data/raw/ and extract them into data/src/."""

import csv
import urllib.request
import zipfile
from pathlib import Path

import py7zr
import xlrd

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

# INSEE, census 2017, detailed tables by commune: dwellings (LOG) and main residences (PRINC)
INSEE = "https://www.insee.fr/fr/statistiques/fichier/4199326"
INSEE_TABLES = ["rp-mayotte-2017-communes-log.xls", "rp-mayotte-2017-communes-princ.xls"]


def insee():
    """Download the INSEE workbooks and write each sheet as a CSV file in data/src/insee/<workbook>/."""
    (RAW / "insee").mkdir(parents=True, exist_ok=True)
    for name in INSEE_TABLES:
        workbook = RAW / "insee" / name
        if not workbook.exists():
            print(f"downloading {name}")
            request = urllib.request.Request(f"{INSEE}/{name}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request) as response:
                workbook.write_bytes(response.read())
        target = SRC / "insee" / workbook.stem
        if target.exists():
            continue
        target.mkdir(parents=True)
        for sheet in xlrd.open_workbook(workbook).sheets():
            with open(target / f"{sheet.name}.csv", "w", newline="", encoding="utf-8") as output:
                csv.writer(output).writerows([cell.value for cell in row] for row in sheet.get_rows())
        print(f"extracted {target.name}")


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
    insee()


if __name__ == "__main__":
    main()
