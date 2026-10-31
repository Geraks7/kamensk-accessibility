"""Шаг 6: интерактивная веб-карта (GitHub Pages).

Собирает docs/index.html: граница округа, доступность школ и поликлиник,
объекты инфраструктуры и критичные объекты с всплывающими карточками.

Вход:
    data/processed/boundary.gpkg
    data/processed/accessibility.gpkg
    data/processed/poi_osm.gpkg
    data/processed/critical_objects.gpkg

Выход:
    docs/index.html

Запуск (из любой папки):
    python src/06_webmap.py
"""
import html
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
DOCS = ROOT / "docs"

CENTER = [56.4145, 61.9186]

BINS = [0, 5, 10, 15, 20, 60]
LABELS = ["≤ 5 мин", "5–10 мин", "10–15 мин", "15–20 мин", "> 20 мин"]
COLORS = ["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027"]

TYPE_COLORS = {"school": "#1f78b4", "kindergarten": "#33a02c", "clinic": "#e31a1c"}
TYPE_LABELS = {"school": "школа", "kindergarten": "детский сад", "clinic": "медицинское учреждение"}


def color_for(t):
    if pd.isna(t):
        return "#bdbdbd"
    for lo, hi, c in zip(BINS[:-1], BINS[1:], COLORS):
        if lo < t <= hi:
            return c
    return "#d73027"


def load(name, crs=4326):
    path = PROC / name
    return gpd.read_file(path).to_crs(crs) if path.exists() else None


def coverage_layer(acc, column, layer_name):
    fg = folium.FeatureGroup(name=layer_name, show=True)
    for _, row in acc.iterrows():
        t = row[column]
        label = "недостижимо" if pd.isna(t) else f"{t:.1f} мин"
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=3,
            weight=0,
            fill=True,
            fill_color=color_for(t),
            fill_opacity=0.8,
            tooltip=f"Пешком: {label}",
        ).add_to(fg)
    return fg


def facilities_layer(poi):
    fg = folium.FeatureGroup(name="Объекты инфраструктуры", show=True)
    for _, row in poi.iterrows():
        if row.geometry is None:
            continue
        pt = row.geometry.representative_point()
        what = row.get("amenity") if isinstance(row.get("amenity"), str) else row.get("leisure")
        type_name = TYPE_LABELS.get(what, what or "объект")
        name = row.get("name") if isinstance(row.get("name"), str) else ""
        folium.CircleMarker(
            location=[pt.y, pt.x],
            radius=4,
            weight=1,
            color="#111111",
            fill=True,
            fill_color="#111111",
            fill_opacity=0.9,
            popup=folium.Popup(html.escape(f"{type_name}. {name}"), max_width=260),
            tooltip=html.escape(name or type_name),
        ).add_to(fg)
    return fg


def critical_layer(crit):
    fg = folium.FeatureGroup(name="Критичные объекты", show=True)
    for _, row in crit.iterrows():
        share = float(row["loss_share"])
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=4 + 26 * share,
            weight=1,
            color="#7f0000",
            fill=True,
            fill_color=TYPE_COLORS.get(row["type"], "#7f0000"),
            fill_opacity=0.55,
            popup=folium.Popup(
                html.escape(
                    f"{row['name']} ({TYPE_LABELS.get(row['type'], row['type'])}). "
                    f"При закрытии без доступа останутся {share * 100:.1f} % жилой застройки "
                    f"({int(row['loss_buildings'])} зданий)."
                ),
                max_width=320,
            ),
            tooltip=f"{row['name']}: {share*100:.1f} %",
        ).add_to(fg)
    return fg


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    boundary = load("boundary.gpkg")
    acc = load("accessibility.gpkg")
    poi = load("poi_verified.gpkg")
    if poi is None:
        poi = load("poi_osm.gpkg")
    crit = load("critical_objects.gpkg")

    m = folium.Map(
        location=CENTER,
        zoom_start=11,
        tiles="OpenStreetMap",
        attr="© OpenStreetMap contributors",
        control_scale=True,
    )

    if boundary is not None:
        folium.GeoJson(
            boundary.__geo_interface__,
            name="Граница городского округа",
            style_function=lambda _: {"color": "#333333", "weight": 2, "fill": False},
        ).add_to(m)

    if acc is not None:
        coverage_layer(acc, "time_school_min", "Доступность школ").add_to(m)
        coverage_layer(acc, "time_clinic_min", "Доступность поликлиник").add_to(m)
    if poi is not None:
        facilities_layer(poi).add_to(m)
    if crit is not None:
        critical_layer(crit).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    legend = "".join(
        f'<div><span style="display:inline-block;width:12px;height:12px;background:{c};'
        f'margin-right:6px;"></span>{lab}</div>'
        for c, lab in zip(COLORS, LABELS)
    )
    legend += (
        '<div style="margin-top:6px;"><span style="display:inline-block;width:10px;height:10px;'
        'border-radius:50%;background:#111;margin-right:6px;"></span>объект</div>'
    )
    m.get_root().html.add_child(
        folium.Element(
            '<div style="position:fixed;left:16px;bottom:16px;z-index:9999;background:white;'
            'padding:10px 12px;border-radius:8px;font:12px/1.5 sans-serif;'
            'box-shadow:0 1px 6px rgba(0,0,0,.3);">'
            '<b>Пешеходная доступность</b><br>' + legend + "</div>"
        )
    )
    m.get_root().html.add_child(
        folium.Element(
            '<div style="position:fixed;left:50%;top:12px;transform:translateX(-50%);z-index:9999;'
            'background:white;padding:8px 14px;border-radius:8px;font:13px/1.4 sans-serif;'
            'box-shadow:0 1px 6px rgba(0,0,0,.3);text-align:center;">'
            "<b>Каменск-Уральский: доступность социальной инфраструктуры</b><br>"
            "15 минут пешком: школы — 67 %, детсады — 66 %, поликлиники — 46 % жилой застройки"
            "</div>"
        )
    )
    m.get_root().html.add_child(
        folium.Element(
            '<div style="position:fixed;right:16px;bottom:16px;z-index:9999;font:10px sans-serif;'
            'background:rgba(255,255,255,.85);padding:3px 6px;border-radius:4px;">'
            "Данные: © OpenStreetMap contributors (ODbL)</div>"
        )
    )

    out = DOCS / "index.html"
    m.save(str(out))
    print(f"Сохранено: {out}")


if __name__ == "__main__":
    main()
