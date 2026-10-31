"""Шаг 2c: сверка OSM с официальными перечнями.

Что делает:
    1) чистит OSM-слой от ложных объектов (танцевальные студии, художественные школы);
    2) сопоставляет объекты OSM с муниципальным перечнем по номеру;
    3) недостающие в OSM муниципальные объекты геокодирует по адресу (Nominatim);
    4) сохраняет сверенный слой и отчёт о расхождениях.

Вход:
    data/processed/poi_osm.gpkg
    data/raw/official_schools.csv
    data/raw/official_kindergartens.csv

Выход:
    data/processed/poi_verified.gpkg
    data/processed/poi_verification.csv
    data/raw/official_missing_geocoded.csv

Запуск:
    python src/02c_verify_poi.py
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

# Что не считаем школой/детсадом, хотя OSM так размечен.
FALSE_POSITIVE = re.compile(r"танц|художественн", re.I)

CITY_BBOX = (56.20, 61.60, 56.60, 62.15)  # south, west, north, east


def number_of(name):
    if not isinstance(name, str):
        return None
    m = re.search(r"№\s*(\d+)", name)
    return int(m.group(1)) if m else None


def load_osm():
    poi = gpd.read_file(PROC / "poi_osm.gpkg")
    if poi.crs is None:
        poi = poi.set_crs(4326)
    return poi.to_crs(4326)


def classify(poi):
    """Тип объекта и признак «мусора»."""
    def kind(row):
        if row.get("amenity") in ("school", "kindergarten"):
            return row["amenity"]
        if row.get("amenity") in ("clinic", "hospital", "doctors"):
            return "clinic"
        return None

    poi = poi.copy()
    poi["type"] = poi.apply(kind, axis=1)
    poi = poi[poi["type"].notna()].copy()
    poi["false_positive"] = poi["name"].fillna("").str.contains(FALSE_POSITIVE)
    poi = poi[~poi["false_positive"]].copy()
    poi["number"] = poi["name"].apply(number_of)
    return poi


ABBREV = [
    (r"\bул\.", "улица"),
    (r"\bпр\.", "проспект"),
    (r"\bпер\.", "переулок"),
    (r"\bб-р\b", "бульвар"),
    (r"\bд\.", ""),
    (r"\bш\.", "шоссе"),
]


def normalize_address(address):
    """Nominatim не понимает сокращения: 'ул. Кузнецова' -> 'улица Кузнецова'."""
    a = re.sub(r"\(.*?\)", "", address)
    a = a.replace("г. Каменск-Уральский", "")
    for pattern, repl in ABBREV:
        a = re.sub(pattern, repl, a)
    a = re.sub(r"\s+", " ", a).strip(" ,")
    return f"Каменск-Уральский, {a}"


def geocode(address):
    """Адрес -> координаты через Nominatim. Один запрос в секунду по правилам сервиса."""
    q = normalize_address(address)
    params = {"q": q, "format": "jsonv2", "limit": 1, "countrycodes": "ru"}
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
    lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
    s, w, n, e = CITY_BBOX
    if not (s <= lat <= n and w <= lon <= e):
        return None, "out of bbox"
    return (lon, lat), "ok"


def main():
    poi = classify(load_osm())
    official = {
        "school": pd.read_csv(RAW / "official_schools.csv"),
        "kindergarten": pd.read_csv(RAW / "official_kindergartens.csv"),
    }

    report, added, geocoded_log = [], [], []
    off_nums_by_type = {}

    for type_name, off in official.items():
        sub = poi[poi["type"] == type_name].copy()
        off = off.copy()
        off["number"] = pd.to_numeric(off["number"], errors="coerce")
        off_nums = set(int(x) for x in off["number"].dropna())
        off_nums_by_type[type_name] = off_nums
        osm_nums = set(int(x) for x in sub["number"].dropna())

        matched = sorted(off_nums & osm_nums)
        missing = sorted(off_nums - osm_nums)
        extra = sorted(osm_nums - off_nums)
        unnumbered = off[off["number"].isna()]

        report.append({
            "type": type_name,
            "official_total": len(off),
            "official_numbered": len(off_nums),
            "osm_total": len(sub),
            "matched": len(matched),
            "missing_in_osm": len(missing),
            "extra_in_osm": len(extra),
            "missing_numbers": ", ".join(map(str, missing)),
            "extra_numbers": ", ".join(map(str, extra)),
        })

        # Недостающие в OSM: геокодируем первый адрес
        rows = []
        for _, row in off[off["number"].isin(missing)].iterrows():
            addr = str(row["addresses"]).split(";")[0].strip()
            coords, status_geo = geocode(addr)
            geocoded_log.append({
                "type": type_name, "number": int(row["number"]), "name": row["name"],
                "address": addr, "geocode": status_geo,
                "lon": coords[0] if coords else None, "lat": coords[1] if coords else None,
            })
            if coords:
                rows.append({
                    "type": type_name, "amenity": type_name, "name": row["name"],
                    "number": int(row["number"]), "status": "municipal", "source": "official",
                    "geometry": gpd.points_from_xy([coords[0]], [coords[1]])[0],
                })

        # Объекты без номера (гимназия, центр образования): геокодируем и проверяем дубли
        for _, row in unnumbered.iterrows():
            addr = str(row["addresses"]).split(";")[0].strip()
            coords, status_geo = geocode(addr)
            geocoded_log.append({
                "type": type_name, "number": None, "name": row["name"],
                "address": addr, "geocode": status_geo,
                "lon": coords[0] if coords else None, "lat": coords[1] if coords else None,
            })
            if not coords:
                continue
            pt = gpd.GeoSeries(gpd.points_from_xy([coords[0]], [coords[1]]), crs=4326).to_crs(3857).iloc[0]
            near = sub.to_crs(3857).distance(pt)
            if len(near) and near.min() < 150:
                continue  # уже есть в OSM
            rows.append({
                "type": type_name, "amenity": type_name, "name": row["name"], "number": None,
                "status": "municipal", "source": "official",
                "geometry": gpd.points_from_xy([coords[0]], [coords[1]])[0],
            })

        if rows:
            added.append(gpd.GeoDataFrame(rows, crs=4326))

    poi["status"] = [
        "municipal"
        if (row["type"] in off_nums_by_type and row["number"] in off_nums_by_type[row["type"]])
        else "other"
        for _, row in poi.iterrows()
    ]
    poi["source"] = "osm"

    verified = pd.concat([poi[["type", "amenity", "name", "number", "status", "source", "geometry"]]] + added,
                         ignore_index=True)
    verified = gpd.GeoDataFrame(verified, geometry="geometry", crs=4326)
    verified.to_file(PROC / "poi_verified.gpkg", driver="GPKG")
    pd.DataFrame(report).to_csv(PROC / "poi_verification.csv", index=False, encoding="utf-8")
    pd.DataFrame(geocoded_log).to_csv(RAW / "official_missing_geocoded.csv", index=False, encoding="utf-8")

    print("=== СВЕРКА ===")
    print(pd.DataFrame(report).to_string(index=False))
    print(f"\nИтоговый слой: {len(verified)} объектов")
    print(verified.groupby(["type", "status"]).size().to_string())


if __name__ == "__main__":
    main()
