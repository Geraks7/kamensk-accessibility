"""Шаг 2: объекты социальной инфраструктуры из OpenStreetMap.

Запуск:
    python src/02_poi.py

Почему из OSM, а не сразу из официальных списков:
    OSM даёт координаты, официальные перечни (obr-ku.ru, miacso.ru) — точные адреса
    и состав. Рабочий порядок: взять OSM как основу, затем сверить с перечнями
    и дописать недостающее. Это описано в docs/DATA.md.

Результат:
    data/processed/poi_osm.gpkg
"""
from pathlib import Path

import osmnx as ox

PLACE = "Каменск-Уральский, Свердловская область, Россия"
CENTER = (56.4145, 61.9186)
DIST_M = 11_000

TAGS = {
    "amenity": [
        "school",
        "kindergarten",
        "hospital",
        "clinic",
        "library",
        "community_centre",
    ],
    "leisure": ["sports_centre", "swimming_pool"],
}

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
ox.settings.use_cache = True


def load_poi():
    try:
        return ox.features_from_place(PLACE, tags=TAGS)          # osmnx >= 2.0
    except Exception as exc:
        print(f"features_from_place не сработал ({exc}); пробуем по точке")
        return ox.geometries_from_point(CENTER, tags=TAGS, dist=DIST_M)  # osmnx 1.x


def main():
    gdf = load_poi().reset_index()

    keep = [
        c
        for c in (
            "element",
            "id",
            "amenity",
            "leisure",
            "name",
            "addr:street",
            "addr:housenumber",
            "geometry",
        )
        if c in gdf.columns
    ]
    gdf = gdf[keep]
    gdf.to_file(OUT / "poi_osm.gpkg", driver="GPKG")

    print(f"Всего объектов: {len(gdf)}")
    for col in ("amenity", "leisure"):
        if col in gdf.columns:
            print(f"\n{col}:")
            print(gdf[col].value_counts())


if __name__ == "__main__":
    main()
