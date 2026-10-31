"""Шаг 4: сценарии сокращения сети и реестр объектов.

Логика:
    1) для каждого объекта считаем зону 15-минутной пешеходной доступности;
    2) базовое покрытие — доля жилой застройки, от которой доступен хотя бы один объект;
    3) жадный алгоритм убирает объекты, если суммарная потеря покрытия не превышает
       допустимую (умеренный сценарий — 0 %, средний — 1 %, радикальный — 3 %);
    4) отдельно считаем «критичность» каждого объекта: сколько жилья потеряет
       доступность, если убрать только его.

Вход:
    data/processed/kamensk_walk.graphml
    data/processed/poi_osm.gpkg
    data/processed/accessibility.gpkg   (результат шага 3)

Выход:
    data/processed/scenario_summary.csv
    data/processed/scenario_objects.csv
    data/processed/critical_objects.csv
    data/processed/scenario_removed.gpkg

Запуск (из любой папки):
    python src/04_scenario.py
"""
from collections import Counter
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
CACHE = ROOT / "data" / "cache"

PLACE = "Каменск-Уральский, Свердловская область, Россия"

TYPES = {
    "school": {"amenity": ["school"]},
    "kindergarten": {"amenity": ["kindergarten"]},
    "clinic": {"amenity": ["clinic", "hospital", "doctors"]},
}

THRESHOLD_MIN = 15
SPEED_KMH = 4.5
CUTOFF_M = THRESHOLD_MIN * SPEED_KMH * 1000 / 60

# Сценарий -> допустимая потеря покрытия (доля жилой застройки).
SCENARIOS = {
    "умеренный": 0.0,
    "средний": 0.01,
    "радикальный": 0.03,
}

# Не даём алгоритму закрыть больше половины сети: модель оценивает доступность,
# а не вместимость, поэтому формально «без потерь» можно убрать почти всё.
MAX_REMOVE_SHARE = 0.5


def load_graph():
    path = PROC / "kamensk_walk.graphml"
    if not path.exists():
        raise SystemExit(f"Нет {path}. Сначала запустите src/01_city_map.py")
    return ox.project_graph(ox.load_graphml(path))


def load_poi():
    for name in ("poi_verified.gpkg", "poi_osm.gpkg"):
        path = PROC / name
        if path.exists():
            gdf = gpd.read_file(path)
            if gdf.crs is None:
                gdf = gdf.set_crs(4326)
            return gdf.to_crs(4326)
    raise SystemExit("Нет poi_verified.gpkg или poi_osm.gpkg")


def load_demand():
    path = PROC / "accessibility.gpkg"
    if not path.exists():
        raise SystemExit(f"Нет {path}. Сначала запустите src/03_accessibility.py")
    gdf = gpd.read_file(path)
    return gdf[["node", "buildings", "geometry"]].copy()


def subset_by_tags(poi, tags):
    mask = pd.Series(False, index=poi.index)
    for col, values in tags.items():
        if col in poi.columns:
            mask |= poi[col].isin(values)
    return poi[mask]


def snap_to_nodes(points_wgs84, G):
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
    return joined.groupby(level=0).first()["node"].reindex(pts.index)


def service_nodes(poi, G, tags):
    """Уникальные узлы обслуживания с числом объектов и названием."""
    sub = subset_by_tags(poi, tags)
    if sub.empty:
        return gpd.GeoDataFrame()
    pts = sub.geometry.representative_point()
    nodes = snap_to_nodes(pts, G)
    df = gpd.GeoDataFrame(
        {
            "node": nodes.values,
            "name": sub["name"].values if "name" in sub.columns else "",
        },
        geometry=list(pts),
        crs="EPSG:4326",
    ).dropna(subset=["node"])
    agg = (
        df.groupby("node")
        .agg(n_objects=("node", "size"), name=("name", "first"), geometry=("geometry", "first"))
        .reset_index()
    )
    return gpd.GeoDataFrame(agg, geometry="geometry", crs="EPSG:4326")


def coverage_sets(G, services, demand_nodes):
    """Для каждого узла обслуживания — какие узлы спроса доступны за порог."""
    covers = {}
    for node in services["node"].astype(int):
        reach = nx.single_source_dijkstra_path_length(G, node, cutoff=CUTOFF_M, weight="length")
        covers[node] = set(reach).intersection(demand_nodes)
    return covers


def covered_weight(counts, weights):
    return sum(weights[n] for n, c in counts.items() if c > 0)


def run_greedy(services, covers, weights, allowed_share):
    """Жадно убирает объекты, пока потеря покрытия не превысит допустимую."""
    total = sum(weights.values())
    baseline = covered_weight({n: 1 for n in set().union(*covers.values())}, weights)
    allowed = allowed_share * total
    max_remove = int(len(services) * MAX_REMOVE_SHARE)

    active = list(services["node"].astype(int))
    counts = Counter()
    for s in active:
        for d in covers[s]:
            counts[d] += 1

    current = covered_weight(counts, weights)
    removed = []
    while active and len(removed) < max_remove:
        remaining = allowed - (baseline - current)
        if remaining < 0:
            break
        best, best_loss = None, None
        for s in active:
            loss = sum(weights[d] for d in covers[s] if counts[d] == 1)
            if best_loss is None or loss < best_loss:
                best, best_loss = s, loss
        if best is None or best_loss > remaining:
            break
        for d in covers[best]:
            counts[d] -= 1
        current = covered_weight(counts, weights)
        row = services.loc[services["node"] == best].iloc[0]
        removed.append(
            {
                "node": best,
                "name": row["name"],
                "n_objects": int(row["n_objects"]),
                "loss_buildings": int(best_loss),
                "loss_share": round(best_loss / total, 4),
                "geometry": row["geometry"],
            }
        )
        active.remove(best)

    return removed, baseline, current, total, active


def mean_time(G, service_nodes_list, weights):
    """Средневзвешенное время до ближайшего объекта; недостижимые — 60 минут."""
    if service_nodes_list is None or len(service_nodes_list) == 0:
        return float("nan")
    dist = nx.multi_source_dijkstra_path_length(
        G, set(int(s) for s in service_nodes_list), weight="length"
    )
    km_per_min = SPEED_KMH / 60
    total = sum(weights.values())
    acc = 0.0
    for node, w in weights.items():
        d = dist.get(node)
        acc += w * (d / 1000 / km_per_min if d is not None else 60.0)
    return acc / total


def critical_objects(services, covers, weights):
    """Потеря покрытия, если убрать только этот объект (маргинальная, а не полная).

    Считаем, сколько жилья останется без объекта именно из-за этого удаления:
    только те узлы спроса, которые покрыты этим и больше никем.
    """
    total = sum(weights.values())
    counts = Counter()
    for s in services["node"].astype(int):
        for d in covers[s]:
            counts[d] += 1

    rows = []
    for _, row in services.iterrows():
        node = int(row["node"])
        loss = sum(weights[d] for d in covers[node] if counts[d] == 1)
        rows.append(
            {
                "node": node,
                "name": row["name"],
                "n_objects": int(row["n_objects"]),
                "loss_buildings": int(loss),
                "loss_share": round(loss / total, 4),
                "geometry": row["geometry"],
            }
        )
    return pd.DataFrame(rows).sort_values("loss_buildings", ascending=False)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(CACHE)

    print("1. Загрузка данных")
    G = load_graph()
    poi = load_poi()
    demand = load_demand()
    weights = dict(zip(demand["node"].astype(int), demand["buildings"].astype(int)))
    demand_nodes = set(weights)
    print(f"Граф: {G.number_of_nodes()} узлов; спрос: {len(weights)} узлов, {sum(weights.values())} зданий")

    summary_rows, object_rows, critical_frames = [], [], []

    for type_name, tags in TYPES.items():
        services = service_nodes(poi, G, tags)
        if services.empty:
            print(f"  {type_name}: объектов нет — пропуск")
            continue
        print(f"\n2. {type_name}: объектов {len(services)}")

        covers = coverage_sets(G, services, demand_nodes)
        crit = critical_objects(services, covers, weights)
        crit.insert(0, "type", type_name)
        critical_frames.append(crit)

        for scenario, allowed in SCENARIOS.items():
            removed, baseline, current, total, remaining = run_greedy(
                services, covers, weights, allowed
            )
            summary_rows.append(
                {
                    "scenario": scenario,
                    "type": type_name,
                    "n_objects_before": int(services["n_objects"].sum()),
                    "n_objects_removed": int(sum(r["n_objects"] for r in removed)),
                    "coverage_before": round(baseline / total, 4),
                    "coverage_after": round(current / total, 4),
                    "loss_pp": round((baseline - current) / total * 100, 2),
                    "allowed_loss_pp": round(allowed * 100, 2),
                    "mean_time_before_min": round(mean_time(G, services["node"], weights), 2),
                    "mean_time_after_min": round(mean_time(G, remaining, weights), 2),
                    "cap_binding": len(removed) >= int(len(services) * MAX_REMOVE_SHARE),
                }
            )
            for r in removed:
                r["scenario"] = scenario
                r["type"] = type_name
                object_rows.append(r)
            print(f"   {scenario}: убрано {sum(r['n_objects'] for r in removed)} объектов, "
                  f"потеря {round((baseline - current) / total * 100, 2)} п.п.")

        crit_top = crit.head(3)[["name", "loss_buildings", "loss_share"]]
        print(f"   критичные: {crit_top.to_dict('records')}")

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(PROC / "scenario_summary.csv", index=False, encoding="utf-8")

    objects = pd.DataFrame(object_rows)
    if not objects.empty:
        objects["geometry"] = objects["geometry"].astype(str)
    objects.to_csv(PROC / "scenario_objects.csv", index=False, encoding="utf-8")

    critical = pd.concat(critical_frames, ignore_index=True) if critical_frames else pd.DataFrame()
    critical_out = critical.drop(columns=["geometry"])
    critical_out.to_csv(PROC / "critical_objects.csv", index=False, encoding="utf-8")

    if not critical.empty:
        gpd.GeoDataFrame(critical, geometry="geometry", crs="EPSG:4326").to_file(
            PROC / "critical_objects.gpkg", driver="GPKG"
        )

    print("\n=== ИТОГИ ПО СЦЕНАРИЯМ ===")
    print(summary.to_string(index=False))
    print("\n=== САМЫЕ КРИТИЧНЫЕ ОБЪЕКТЫ ===")
    print(critical_out.head(10).to_string(index=False))
    print(f"\nГотово: {PROC / 'scenario_summary.csv'}")


if __name__ == "__main__":
    main()
