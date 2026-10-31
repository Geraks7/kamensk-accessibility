"""Общие пути и загрузчики для расчётных скриптов (03–06).

01 и 02 стоят отдельно: они готовят данные, от которых зависит всё остальное,
поэтому не должны зависеть от уже посчитанных слоёв.
"""
from pathlib import Path

import geopandas as gpd
import osmnx as ox

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
MAPS = ROOT / "maps"
CACHE = ROOT / "data" / "cache"

PLACE = "Каменск-Уральский, Свердловская область, Россия"
UTM = "EPSG:32641"  # 41N, подходит для 60–66° в.д.

# Тип объекта -> теги OSM. Медицина собрана из трёх тегов: поликлиники,
# больницы и врачебные кабинеты отдельно в OSM почти не различаются.
TYPES = {
    "school": {"amenity": ["school"]},
    "kindergarten": {"amenity": ["kindergarten"]},
    "clinic": {"amenity": ["clinic", "hospital", "doctors"]},
}


def load_graph():
    path = PROC / "kamensk_walk.graphml"
    if not path.exists():
        raise SystemExit(f"нет {path} — сначала запустите src/01_city_map.py")
    G = ox.load_graphml(path)
    print(f"граф: {G.number_of_nodes()} узлов, {G.number_of_edges()} рёбер")
    return G


def load_poi():
    """Верхний слой, если сверка уже была, иначе сырой OSM."""
    for name in ("poi_verified.gpkg", "poi_osm.gpkg"):
        path = PROC / name
        if path.exists():
            gdf = gpd.read_file(path)
            if gdf.crs is None:
                gdf = gdf.set_crs(4326)
            return gdf.to_crs(4326)
    raise SystemExit("нет poi_verified.gpkg или poi_osm.gpkg — запустите src/02_poi.py")


def subset(poi, tags):
    mask = False
    for col, values in tags.items():
        if col in poi.columns:
            mask = mask | poi[col].isin(values)
    return poi[mask]


def snap_to_nodes(points_wgs84, G):
    """Ближайший узел графа для точек.

    Считаем по спроецированному графу через sjoin_nearest — так не нужен
    scikit-learn, который osmnx требует для географических координат.
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
    return joined.groupby(level=0).first()["node"].reindex(pts.index)
