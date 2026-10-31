"""Шаг 2d: проверка медицинских объектов по данным основного поставщика.

Полного машиночитаемого реестра городских медучреждений нет: сеть разбита между
несколькими юрлицами, а PDF МИАЦ содержит только сельские ОВП и ФАП. Поэтому
сверяем то, что можно проверить: структурные подразделения ГАУЗ СО «Городская
больница г. Каменск-Уральский» (7 площадок с адресами).

Что делает:
    1) геокодирует адреса площадок;
    2) ищет ближайший объект OSM среди clinic/hospital;
    3) пишет отчёт: что найдено, что нет, расстояние привязки.

Вход:
    data/raw/official_medical.csv
    data/processed/poi_verified.gpkg (или poi_osm.gpkg)

Выход:
    data/processed/medical_verification.csv

Запуск:
    python src/02d_medical_check.py
"""
import re
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

UA = "kamensk-accessibility/0.1 (student GIS project)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
MATCH_RADIUS_M = 200

ABBREV = [
    (r"\bул\.", "улица"),
    (r"\bпр\.", "проспект"),
    (r"\bпер\.", "переулок"),
    (r"\bд\.", ""),
]


def normalize_address(address):
    a = re.sub(r"\(.*?\)", "", address)
    a = a.replace("г. Каменск-Уральский", "")
    for pattern, repl in ABBREV:
        a = re.sub(pattern, repl, a)
    a = re.sub(r"\s+", " ", a).strip(" ,")
    return f"Каменск-Уральский, {a}"


def geocode(address):
    params = {"q": normalize_address(address), "format": "jsonv2", "limit": 1, "countrycodes": "ru"}
    try:
        r = requests.get(NOMINATIM, params=params, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        return None, f"error: {type(exc).__name__}"
    finally:
        time.sleep(1.1)
    if not data:
        return None, "not found"
    return (float(data[0]["lon"]), float(data[0]["lat"])), "ok"


def main():
    official = pd.read_csv(RAW / "official_medical.csv")

    poi_file = PROC / "poi_verified.gpkg"
    if not poi_file.exists():
        poi_file = PROC / "poi_osm.gpkg"
    poi = gpd.read_file(poi_file).to_crs(4326)
    med = poi[poi["amenity"].isin(["clinic", "hospital", "doctors"])].to_crs(3857)

    rows = []
    for _, row in official.iterrows():
        coords, status = geocode(row["address"])
        if coords is None:
            rows.append({
                "name": row["name"], "address": row["address"], "geocode": status,
                "nearest_osm": None, "distance_m": None, "matched": False,
            })
            continue
        pt = gpd.GeoSeries(gpd.points_from_xy([coords[0]], [coords[1]]), crs=4326).to_crs(3857).iloc[0]
        distances = med.distance(pt)
        idx = distances.idxmin() if len(distances) else None
        best = float(distances.min()) if idx is not None else None
        rows.append({
            "name": row["name"],
            "address": row["address"],
            "geocode": status,
            "nearest_osm": med.loc[idx, "name"] if idx is not None else None,
            "distance_m": round(best, 1) if best is not None else None,
            "matched": bool(best is not None and best <= MATCH_RADIUS_M),
        })

    report = pd.DataFrame(rows)
    report.to_csv(PROC / "medical_verification.csv", index=False, encoding="utf-8")

    matched = int(report["matched"].sum())
    print(f"Площадок ГАУЗ «Городская больница»: {len(report)}")
    print(f"Найдено в OSM в радиусе {MATCH_RADIUS_M} м: {matched}")
    print(report[["name", "nearest_osm", "distance_m", "matched"]].to_string(index=False))


if __name__ == "__main__":
    main()
