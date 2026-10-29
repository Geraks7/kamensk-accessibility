"""Шаг 1: граница городского округа, пешеходный граф и первая карта.

Запуск:
    python src/01_city_map.py

Что делает:
    1) скачивает границу Каменск-Уральского городского округа (Nominatim/OSM);
    2) строит пешеходный граф улиц (OSMnx);
    3) рисует граф с границей и сохраняет карту.

Результат:
    data/processed/boundary.gpkg
    data/processed/kamensk_walk.graphml
    maps/01_walk_graph.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import osmnx as ox

PLACE = "Каменск-Уральский, Свердловская область, Россия"

# Запасной вариант, если геокодер не найдёт город по названию.
CENTER = (56.4145, 61.9186)
DIST_M = 11_000

ROOT = Path(__file__).resolve().parents[1]
OUT_PROC = ROOT / "data" / "processed"
OUT_MAPS = ROOT / "maps"
OUT_PROC.mkdir(parents=True, exist_ok=True)
OUT_MAPS.mkdir(parents=True, exist_ok=True)

ox.settings.use_cache = True
ox.settings.log_console = True


def load_boundary():
    """Граница городского округа из OSM."""
    gdf = ox.geocode_to_gdf(PLACE)
    gdf.to_file(OUT_PROC / "boundary.gpkg", driver="GPKG")
    area_km2 = gdf.to_crs(32641).area.sum() / 1e6  # UTM 41N подходит для 60-66° в.д.
    print(f"Граница: {len(gdf)} объект(ов), площадь ≈ {area_km2:.0f} км²")
    return gdf


def load_graph():
    """Пешеходный граф улиц."""
    try:
        G = ox.graph_from_place(PLACE, network_type="walk", simplify=True)
    except Exception as exc:  # геокодер иногда не находит кириллические названия
        print(f"graph_from_place не сработал ({exc}); берём по координатам центра")
        G = ox.graph_from_point(CENTER, dist=DIST_M, network_type="walk", simplify=True)

    print(f"Узлов: {G.number_of_nodes()}, рёбер: {G.number_of_edges()}")
    if G.number_of_nodes() == 0:
        raise SystemExit("Граф пустой — проверьте название города или радиус.")
    return G


def main():
    boundary = load_boundary()
    G = load_graph()

    fig, ax = ox.plot_graph(
        G,
        show=False,
        close=False,
        node_size=0,
        edge_linewidth=0.4,
        edge_color="#444444",
        bgcolor="white",
    )
    boundary.boundary.plot(ax=ax, color="#c0392b", linewidth=1.6)
    ax.set_title("Пешеходный граф, Каменск-Уральский", fontsize=14)
    fig.savefig(OUT_MAPS / "01_walk_graph.png", dpi=200, bbox_inches="tight")

    ox.save_graphml(G, OUT_PROC / "kamensk_walk.graphml")
    print(f"Готово: {OUT_MAPS / '01_walk_graph.png'}")


if __name__ == "__main__":
    main()
