"""Шаг 3: пешеходная доступность, дублирование и нормативный baseline.

Что считает:
    1) время по пешеходной сети от каждой жилой застройки до ближайшего объекта
       каждого типа (школа, детский сад, медицинское учреждение);
    2) покрытие при порогах 10 / 15 / 20 минут и скоростях 4 / 4.5 / 5 км/ч;
    3) индекс дублирования — сколько объектов доступно в пределах порога;
    4) разрыв «нормативный радиус — фактическая пешеходная доступность».

Вход:
    data/processed/kamensk_walk.graphml
    data/processed/poi_osm.gpkg

Выход:
    data/processed/accessibility.gpkg
    data/processed/buildings_residential.gpkg  (кэш жилой застройки)
    data/processed/coverage_summary.csv
    data/processed/duplication.csv
    data/processed/normative_baseline.csv

Запуск (из любой папки):
    python src/03_accessibility.py
"""
import time
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
CACHE = ROOT / "data" / "cache"

PLACE = "Каменск-Уральский, Свердловская область, Россия"

UTM = "EPSG:32641"  # UTM 41N — подходит для 60-66° в.д.

# Публичные серверы Overpass: если один перегружен, пробуем следующий.
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Overpass без User-Agent отвечает 406/429 — заголовок обязателен.
OVERPASS_HEADERS = {
    "User-Agent": "kamensk-accessibility/0.1 (student GIS project)",
    "Accept": "application/json",
}

# Тип объекта -> теги OSM.
TYPES = {
    "school": {"amenity": ["school"]},
    "kindergarten": {"amenity": ["kindergarten"]},
    "clinic": {"amenity": ["clinic", "hospital", "doctors"]},
}

# Нормативные радиусы обслуживания, м (СП 42.13330; проверить по актуальной редакции).
NORM_RADIUS_M = {"school": 500, "kindergarten": 300, "clinic": 1000}

THRESHOLDS_MIN = (10, 15, 20)
SPEEDS_KMH = (4.0, 4.5, 5.0)
BASE_SPEED_KMH = 4.5
DUP_THRESHOLD_MIN = 15

RESIDENTIAL_BUILDING = [
    "residential",
    "apartments",
    "house",
    "dormitory",
    "detached",
    "terrace",
]


def load_graph():
    path = PROC / "kamensk_walk.graphml"
    if not path.exists():
        raise SystemExit(f"Нет {path}. Сначала запустите src/01_city_map.py")
    G = ox.load_graphml(path)
    print(f"Граф: узлов {G.number_of_nodes()}, рёбер {G.number_of_edges()}")
    return G


def load_poi():
    path = PROC / "poi_osm.gpkg"
    if not path.exists():
        raise SystemExit(f"Нет {path}. Сначала запустите src/02_poi.py")
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    return gdf.to_crs(4326)


def _subset_by_tags(poi, tags):
    mask = pd.Series(False, index=poi.index)
    for col, values in tags.items():
        if col in poi.columns:
            mask |= poi[col].isin(values)
    return poi[mask]


def snap_to_nodes(points_wgs84, G):
    """Ближайший узел графа для каждой точки.

    Работает без scikit-learn: граф уже спроецирован, привязка идёт через
    пространственный индекс geopandas (sjoin_nearest).
    """
    nodes = gpd.GeoDataFrame(
        {"node": list(G.nodes())},
        geometry=gpd.points_from_xy(
            [d["x"] for _, d in G.nodes(data=True)],
            [d["y"] for _, d in G.nodes(data=True)],
        ),
        crs=G.graph["crs"],
    )
    pts = points_wgs84.to_crs(nodes.crs).reset_index(drop=True)
    pts = gpd.GeoDataFrame({"geometry": list(pts)}, crs=nodes.crs)
    joined = gpd.sjoin_nearest(pts, nodes, how="left", distance_col="snap_m")
    joined = joined.groupby(level=0).first()
    return joined["node"].reindex(pts.index)


def facilities_by_type(poi, G):
    """Узлы графа, соответствующие объектам каждого типа."""
    out = {}
    for name, tags in TYPES.items():
        sub = _subset_by_tags(poi, tags)
        if sub.empty:
            print(f"  {name}: объектов не найдено — тип пропускается")
            continue
        pts = sub.geometry.representative_point()
        nodes = snap_to_nodes(pts, G)
        uniq = sorted(set(nodes.dropna().astype(int).tolist()))
        out[name] = {"nodes": uniq, "n_facilities": len(sub)}
        print(f"  {name}: объектов {len(sub)}, узлов {len(uniq)}")
    return out


def fetch_buildings():
    """Жилая застройка из OSM: прямой запрос Overpass по bbox города.

    Возвращает точки-центроиды зданий. Прямой запрос вместо ox.features_from_place
    потому, что тот сначала геокодирует площадь и тянет полные геометрии —
    на перегруженном Overpass это чаще падает по таймауту.
    """
    boundary = gpd.read_file(PROC / "boundary.gpkg").to_crs(4326)
    minx, miny, maxx, maxy = boundary.total_bounds
    bbox = f"{miny:.6f},{minx:.6f},{maxy:.6f},{maxx:.6f}"
    query = (
        "[out:json][timeout:120];\n"
        'way["building"~"^(residential|apartments|house|dormitory|detached|terrace)$"]'
        f"({bbox});\n"
        "out center;"
    )
    last = None
    for url in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(url, data={"data": query}, headers=OVERPASS_HEADERS, timeout=240)
            r.raise_for_status()
            elements = r.json().get("elements", [])
            rows = [
                {"lat": el["center"]["lat"], "lon": el["center"]["lon"],
                 "building": (el.get("tags") or {}).get("building")}
                for el in elements
                if el.get("center")
            ]
            if rows:
                print(f"  здания получены с {url}: {len(rows)}")
                return gpd.GeoDataFrame(
                    rows,
                    geometry=gpd.points_from_xy([x["lon"] for x in rows], [x["lat"] for x in rows]),
                    crs="EPSG:4326",
                )
            print(f"  {url}: пустой ответ")
        except Exception as exc:
            last = exc
            print(f"  {url} не ответил ({type(exc).__name__})")
            time.sleep(2)
    raise last if last else RuntimeError("Overpass не вернул данные")


def load_demand(G):
    """Жилая застройка: одна строка на узел, вес — число зданий."""
    cache = PROC / "buildings_residential.gpkg"
    try:
        if cache.exists():
            b = gpd.read_file(cache)
            print("  здания взяты из кэша")
        else:
            b = fetch_buildings()
            b.to_file(cache, driver="GPKG")
        b = b.to_crs(4326)
        pts = b.geometry.representative_point()
        nodes = snap_to_nodes(pts, G)
        tmp = gpd.GeoDataFrame({"node": nodes.values}, geometry=list(pts), crs="EPSG:4326")
        counts = tmp.groupby("node").size()
        first = tmp.groupby("node").first()["geometry"]
        demand = gpd.GeoDataFrame(
            {"node": counts.index, "buildings": counts.to_numpy()},
            geometry=list(first),
            crs="EPSG:4326",
        )
        print(f"Жилая застройка: {len(b)} зданий, {len(demand)} узлов")
        return demand
    except Exception as exc:
        print(f"Здания получить не удалось ({exc}); используем узлы графа как спрос")
        nodes = list(G.nodes())
        return gpd.GeoDataFrame(
            {"node": nodes, "buildings": 1},
            geometry=gpd.points_from_xy(
                [G.nodes[n]["x"] for n in nodes],
                [G.nodes[n]["y"] for n in nodes],
            ),
            crs=G.graph["crs"],
        )


def coverage_table(demand, dist_by_type):
    rows = []
    total = demand["buildings"].sum()
    for name, dist in dist_by_type.items():
        for speed in SPEEDS_KMH:
            km_per_min = speed / 60.0
            times = demand["node"].map(dist) / 1000.0 / km_per_min
            for thr in THRESHOLDS_MIN:
                covered = times <= thr
                rows.append(
                    {
                        "type": name,
                        "speed_kmh": speed,
                        "threshold_min": thr,
                        "demand_total": int(total),
                        "demand_covered": int(demand.loc[covered, "buildings"].sum()),
                        "coverage_share": round(demand.loc[covered, "buildings"].sum() / total, 4),
                        "mean_time_min": round(float(times.mean()), 2),
                        "median_time_min": round(float(times.median()), 2),
                        "share_unreachable": round(float(times.isna().mean()), 4),
                    }
                )
    return pd.DataFrame(rows)


def duplication_table(G, demand, facilities):
    rows = []
    cutoff_m = DUP_THRESHOLD_MIN * BASE_SPEED_KMH * 1000 / 60
    total = demand["buildings"].sum()
    for name, info in facilities.items():
        counts = np.zeros(len(demand))
        for src in info["nodes"]:
            reach = nx.single_source_dijkstra_path_length(G, src, cutoff=cutoff_m, weight="length")
            counts += demand["node"].isin(set(reach)).to_numpy()
        local = demand.copy()
        local["n_within"] = counts
        rows.append(
            {
                "type": name,
                "n_facilities": info["n_facilities"],
                "threshold_min": DUP_THRESHOLD_MIN,
                "speed_kmh": BASE_SPEED_KMH,
                "share_2plus": round(local.loc[local["n_within"] >= 2, "buildings"].sum() / total, 4),
                "share_0": round(local.loc[local["n_within"] == 0, "buildings"].sum() / total, 4),
                "mean_facilities_within": round(float(local["n_within"].mean()), 2),
            }
        )
    return pd.DataFrame(rows)


def normative_table(demand, poi, dist_by_type):
    """Норматив против факта: одинаковое расстояние, два способа измерения.

    Для каждого типа берём нормативный радиус и считаем долю жилья:
      - в пределах радиуса по прямой (как в нормативе);
      - в пределах того же расстояния по пешеходной сети.
    Разница показывает, насколько уличная сеть и барьеры «съедают» норматив.
    """
    demand_m = demand.to_crs(UTM)
    total = demand["buildings"].sum()
    rows = []
    for name, tags in TYPES.items():
        sub = _subset_by_tags(poi, tags)
        if sub.empty or name not in dist_by_type:
            continue
        fac_m = sub.to_crs(UTM)
        nearest = gpd.sjoin_nearest(
            demand_m, fac_m[["geometry"]], how="left", distance_col="d_m"
        ).groupby(level=0)["d_m"].min()
        d = np.asarray(demand_m.index.map(nearest), float)
        radius = NORM_RADIUS_M[name]

        dist_net = demand["node"].map(dist_by_type[name])
        within_radius = float((d <= radius).mean())
        network_at_radius = float(
            (dist_net <= radius).mul(demand["buildings"]).sum() / total
        )
        times = dist_net / 1000.0 / (BASE_SPEED_KMH / 60)
        network_15 = float((times <= 15).mul(demand["buildings"]).sum() / total)

        rows.append(
            {
                "type": name,
                "norm_radius_m": radius,
                "share_within_radius": round(within_radius, 4),
                "share_network_at_radius": round(network_at_radius, 4),
                "gap_pp": round((within_radius - network_at_radius) * 100, 1),
                "share_network_15min": round(network_15, 4),
                "n_facilities": int(len(sub)),
            }
        )
    return pd.DataFrame(rows)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(CACHE)

    print("1. Загрузка данных")
    G_raw = load_graph()
    G = ox.project_graph(G_raw)
    poi = load_poi()

    print("2. Объекты инфраструктуры")
    facilities = facilities_by_type(poi, G)
    if not facilities:
        raise SystemExit("Не найдено ни одного объекта — проверьте src/02_poi.py")

    print("3. Жилая застройка")
    demand = load_demand(G)

    print("4. Кратчайшие расстояния по сети")
    dist_by_type = {}
    for name, info in facilities.items():
        d = nx.multi_source_dijkstra_path_length(G, set(info["nodes"]), weight="length")
        dist_by_type[name] = d
        print(f"  {name}: достижимо узлов {len(d)}")

    print("5. Покрытие")
    cov = coverage_table(demand, dist_by_type)
    cov.to_csv(PROC / "coverage_summary.csv", index=False)

    print("6. Дублирование")
    dup = duplication_table(G, demand, facilities)
    dup.to_csv(PROC / "duplication.csv", index=False)

    print("7. Нормативный baseline")
    norm = normative_table(demand, poi, dist_by_type)
    norm.to_csv(PROC / "normative_baseline.csv", index=False)

    print("8. Сохранение слоя")
    out = demand.copy()
    for name, dist in dist_by_type.items():
        out[f"dist_{name}_m"] = out["node"].map(dist).round(1)
        out[f"time_{name}_min"] = (out[f"dist_{name}_m"] / 1000 / (BASE_SPEED_KMH / 60)).round(2)
    out.to_file(PROC / "accessibility.gpkg", driver="GPKG")

    print("\n=== ПОКРЫТИЕ (4.5 км/ч) ===")
    print(cov[cov["speed_kmh"] == BASE_SPEED_KMH].to_string(index=False))
    print("\n=== ДУБЛИРОВАНИЕ ===")
    print(dup.to_string(index=False))
    print("\n=== НОРМАТИВ vs ФАКТ ===")
    print(norm.to_string(index=False))
    print(f"\nГотово: {PROC / 'accessibility.gpkg'}")


if __name__ == "__main__":
    main()
