"""Шаг 5: тематические карты по результатам расчётов.

Карты:
    02_coverage_school.png    — время до ближайшей школы
    03_coverage_clinic.png    — время до ближайшей поликлиники
    04_critical_objects.png   — критичные объекты и их вклад в доступность

Вход:
    data/processed/boundary.gpkg
    data/processed/accessibility.gpkg
    data/processed/poi_osm.gpkg
    data/processed/critical_objects.gpkg

Выход:
    maps/02_coverage_school.png
    maps/03_coverage_clinic.png
    maps/04_critical_objects.png

Запуск (из любой папки):
    python src/05_maps.py
"""
import re
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
MAPS = ROOT / "maps"

UTM = "EPSG:32641"
ATTR = "Данные: © OpenStreetMap contributors (ODbL)"

BINS = [0, 5, 10, 15, 20, 60]
LABELS = ["≤ 5 мин", "5–10 мин", "10–15 мин", "15–20 мин", "> 20 мин"]
COLORS = ["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027"]

TYPE_COLORS = {"school": "#1f78b4", "kindergarten": "#33a02c", "clinic": "#e31a1c"}
TYPE_LABELS = {"school": "школы", "kindergarten": "детсады", "clinic": "поликлиники"}


def scalebar(ax, length_km=2):
    """Масштабная линейка в правом нижнем углу (в долях осей)."""
    x0, x1 = ax.get_xlim()
    frac = length_km * 1000 / (x1 - x0)
    left = 0.78 - frac
    ax.plot(
        [left, left + frac], [0.07, 0.07],
        transform=ax.transAxes, color="#111", lw=3, clip_on=False, zorder=10,
    )
    ax.text(
        left + frac / 2, 0.09, f"{length_km} км",
        transform=ax.transAxes, ha="center", va="bottom", fontsize=8, zorder=10,
    )


def short_name(name):
    """Длинное официальное название -> «Школа №39», «Детский сад №34»."""
    if not isinstance(name, str):
        return ""
    m = re.search(r"«([^»]+)»", name)
    s = m.group(1) if m else name
    s = re.sub(r"^(?:средняя|основная)\s+общеобразовательная\s+школа", "Школа", s, flags=re.I)
    s = re.sub(r"^муниципаль\w*\s+[\w\s]+?\s+учреждение\s+", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" ,")


def subset(poi, tags):
    mask = False
    for col, values in tags.items():
        if col in poi.columns:
            mask = mask | poi[col].isin(values)
    return poi[mask]


def coverage_map(acc, boundary, poi, column, tags, title, subtitle, outfile):
    mask_in = acc.within(boundary.geometry.union_all())
    acc = acc[mask_in]

    fig, ax = plt.subplots(figsize=(9, 9))
    boundary.boundary.plot(ax=ax, color="#444444", linewidth=1.0, zorder=2)

    times = acc[column]
    for lo, hi, color, label in zip(BINS[:-1], BINS[1:], COLORS, LABELS):
        m = (times > lo) & (times <= hi)
        if m.any():
            ax.scatter(
                acc.loc[m].geometry.x, acc.loc[m].geometry.y,
                s=5, c=color, linewidths=0, label=label, zorder=3,
            )
    if times.isna().any():
        ax.scatter(
            acc.loc[times.isna()].geometry.x, acc.loc[times.isna()].geometry.y,
            s=5, c="#bdbdbd", linewidths=0, label="недостижимо", zorder=3,
        )

    fac = subset(poi, tags)
    if not fac.empty:
        # школы и больницы в OSM часто площадные — берём точку-представитель
        fac = fac.copy()
        fac["geometry"] = fac.geometry.representative_point()
        ax.scatter(
            fac.geometry.x, fac.geometry.y,
            s=34, marker="^", c="#111111", edgecolors="white", linewidths=0.5,
            label="объекты", zorder=5,
        )

    ax.set_title(title, fontsize=14, pad=12)
    ax.text(0.5, 1.005, subtitle, transform=ax.transAxes, ha="center", va="bottom", fontsize=9, color="#555")
    ax.set_aspect("equal")
    ax.legend(loc="lower left", fontsize=8, frameon=True, markerscale=2.2)
    scalebar(ax)
    ax.text(0.995, 0.005, ATTR, transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color="#666")
    ax.set_axis_off()
    fig.savefig(outfile, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"  сохранено: {outfile}")


def critical_map(outfile):
    path = PROC / "critical_objects.gpkg"
    if not path.exists():
        print("  критичные объекты не найдены — пропуск карты")
        return
    crit = gpd.read_file(path).to_crs(UTM)
    boundary = gpd.read_file(PROC / "boundary.gpkg").to_crs(UTM)
    # Не обрезаем по границе: школа №39 стоит в Монастырке за пределами города,
    # но обслуживает жилую застройку внутри него.
    crit = crit[crit.geometry.notna()]

    fig, ax = plt.subplots(figsize=(9, 9))
    boundary.boundary.plot(ax=ax, color="#444444", linewidth=1.0, zorder=2)

    max_loss = max(crit["loss_buildings"].max(), 1)
    for type_name, color in TYPE_COLORS.items():
        part = crit[crit["type"] == type_name]
        if part.empty:
            continue
        sizes = 20 + 420 * (part["loss_buildings"] / max_loss)
        ax.scatter(
            part.geometry.x, part.geometry.y, s=sizes, c=color, alpha=0.75,
            edgecolors="white", linewidths=0.6, label=TYPE_LABELS[type_name], zorder=4,
        )

    for _, row in crit.head(5).iterrows():
        ax.annotate(
            f"{short_name(row['name'])}\n{row['loss_share'] * 100:.1f} % жилья",
            (row.geometry.x, row.geometry.y),
            textcoords="offset points", xytext=(8, 8), fontsize=7,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#999", alpha=0.85),
            zorder=6,
        )

    ax.set_title("Критичные объекты: потеря доступности при закрытии", fontsize=14, pad=12)
    ax.text(0.5, 1.005, "размер точки — доля жилой застройки, которая потеряет доступность",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=9, color="#555")
    ax.set_aspect("equal")
    ax.legend(loc="lower left", fontsize=8, frameon=True)
    scalebar(ax)
    ax.text(0.995, 0.005, ATTR, transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color="#666")
    ax.set_axis_off()
    fig.savefig(outfile, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"  сохранено: {outfile}")


def main():
    MAPS.mkdir(parents=True, exist_ok=True)
    print("1. Загрузка данных")
    boundary = gpd.read_file(PROC / "boundary.gpkg").to_crs(UTM)
    acc = gpd.read_file(PROC / "accessibility.gpkg").to_crs(UTM)
    poi_file = PROC / "poi_verified.gpkg"
    if not poi_file.exists():
        poi_file = PROC / "poi_osm.gpkg"
    poi = gpd.read_file(poi_file).to_crs(UTM)

    print("2. Карты доступности")
    coverage_map(
        acc, boundary, poi, "time_school_min", {"amenity": ["school"]},
        "Пешеходная доступность школ",
        "время по улично-дорожной сети, скорость 4,5 км/ч",
        MAPS / "02_coverage_school.png",
    )
    coverage_map(
        acc, boundary, poi, "time_clinic_min", {"amenity": ["clinic", "hospital", "doctors"]},
        "Пешеходная доступность медицинских учреждений",
        "время по улично-дорожной сети, скорость 4,5 км/ч",
        MAPS / "03_coverage_clinic.png",
    )

    print("3. Карта критичных объектов")
    critical_map(MAPS / "04_critical_objects.png")

    print("Готово")


if __name__ == "__main__":
    main()
