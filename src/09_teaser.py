"""Тизер на одну страницу A4.

Три числа, карта, список сделанного и контакты. Собирается сразу в PDF —
его и прикладывают к заявке.
"""
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import qrcode
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "maps"
PROC = ROOT / "data" / "processed"
OUT = ROOT / "teaser.pdf"

W_MM, H_MM = 210.0, 297.0

PRIMARY = "#1F3864"
ACCENT = "#C0392B"
TEXT = "#222222"
GRAY = "#5F6B7A"
LIGHT = "#F2F4F8"

MAP_URL = "https://geraks7.github.io/kamensk-accessibility/"
GH_URL = "github.com/Geraks7/kamensk-accessibility"
EMAIL = "shackovmaxim@gmail.com"

TITLE = "Доступность социальной инфраструктуры\nсжимающегося города"
CITY = "Каменск-Уральский, Свердловская область · ~160 тыс. человек"

LEAD = (
    "Город теряет население с 1989 года (207 780 → 160 312 человек), а сеть школ, "
    "детских садов и поликлиник осталась рассчитанной на большее число жителей. "
    "Я построил пешеходные изохроны по 6 029 жилым зданиям и 134 объектам, сверил "
    "данные по муниципальным перечням и посчитал, какие объекты избыточны, а где "
    "доступность проваливается."
)

CARDS = [
    ("75 %", "жилой застройки\nв 15 минутах от школы"),
    ("−43 п.п.", "разрыв между нормативом\nи пешеходной сетью"),
    ("45", "объектов можно\nперепрофилировать\nбез потери покрытия"),
]

DONE = [
    "Сверил данные: OSM + перечни obr-ku.ru, 31 школа и 51 детсад, "
    "добавил 5 объектов, которых не было в OSM",
    "Построил пешеходный граф (8 167 узлов) и изохроны 10 / 15 / 20 минут",
    "Посчитал покрытие, дублирование и разрыв с нормативами СП 42.13330",
    "Построил три сценария сокращения сети с ценой каждого решения",
    "Сделал веб-карту, презентацию и аналитическую записку",
]

STEPS = ["Данные", "Граф", "Изохроны", "Показатели", "Сценарии"]
STACK = "Python · geopandas · osmnx · networkx · QGIS · folium · Overpass API"


def fig_text(fig, x_mm, y_mm, s, size=10, color=TEXT, weight="normal", ha="left",
             va="top", linespacing=1.25):
    fig.text(x_mm / W_MM, 1 - y_mm / H_MM, s, fontsize=size, color=color,
             weight=weight, ha=ha, va=va, linespacing=linespacing)


def fig_rect(fig, x_mm, y_mm, w_mm, h_mm, color, alpha=1.0, radius=0.006,
             edgecolor="none", linewidth=0.0):
    box = FancyBboxPatch(
        (x_mm / W_MM, 1 - (y_mm + h_mm) / H_MM),
        w_mm / W_MM, h_mm / H_MM,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        transform=fig.transFigure,
        facecolor=color, edgecolor=edgecolor, linewidth=linewidth,
        alpha=alpha, mutation_aspect=1,
    )
    fig.patches.append(box)


def wrap(text, width):
    return "\n".join(textwrap.wrap(text, width))


def main():
    MAPS.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(W_MM / 25.4, H_MM / 25.4), dpi=300)
    fig.patch.set_facecolor("white")

    # Верхняя полоса и акцент
    fig_rect(fig, 0, 0, W_MM, 4.5, PRIMARY, radius=0)
    fig_rect(fig, 0, 4.5, 30, 1.0, ACCENT, radius=0)

    # Шапка
    fig_text(fig, 14, 15, TITLE, size=14, color=PRIMARY, weight="bold", linespacing=1.2)
    fig_text(fig, 14, 31, CITY, size=8.2, color=GRAY)

    # Три числа
    card_w, card_h, gap = 55.0, 34.0, 6.0
    for i, (number, caption) in enumerate(CARDS):
        x = 14 + i * (card_w + gap)
        fig_rect(fig, x, 39, card_w, card_h, LIGHT, radius=0.008)
        fig_rect(fig, x, 39, 1.5, card_h, ACCENT, radius=0.004)
        fig_text(fig, x + 5.5, 44, number, size=27, color=PRIMARY, weight="bold")
        fig_text(fig, x + 5.5, 57, caption, size=7.8, color=TEXT, linespacing=1.3)

    # Правая колонка: карта
    map_path = MAPS / "02_coverage_school.png"
    map_bottom = 82.0
    if map_path.exists():
        img = mpimg.imread(map_path)
        map_w = 76.0
        map_h = map_w * img.shape[0] / img.shape[1]
        fig.add_axes([
            122 / W_MM,
            1 - (map_bottom + map_h) / H_MM,
            map_w / W_MM,
            map_h / H_MM,
        ]).imshow(img)
        fig.axes[-1].axis("off")
        fig_text(fig, 122, map_bottom + map_h + 2.5,
                 "Время пешком до ближайшей школы", size=7.4, color=GRAY)

    # Левая колонка: что сделано
    fig_text(fig, 14, 82, "ЧТО СДЕЛАНО", size=7.8, color=ACCENT, weight="bold")
    y = 88.5
    for item in DONE:
        fig_text(fig, 14, y, "•", size=9, color=ACCENT, weight="bold")
        lines = wrap(item, 60)
        fig_text(fig, 18, y, lines, size=8.5, color=TEXT, linespacing=1.35)
        y += 7.4 + 3.5 * (len(lines.split("\n")) - 1)

    # Левая колонка: лид под списком
    lead_y = max(y + 8, 150)
    lead_lines = wrap(LEAD, 60)
    lead_h = 8 + 3.6 * len(lead_lines.split("\n"))
    fig_rect(fig, 14, lead_y, 100, lead_h, LIGHT, radius=0.006)
    fig_text(fig, 17, lead_y + 4, lead_lines, size=8.0, color=TEXT, linespacing=1.35)

    # Ключевой вывод
    call_y = lead_y + lead_h + 7
    fig_rect(fig, 14, call_y, 100, 22, "#FFF7F6", radius=0.006, edgecolor=ACCENT, linewidth=0.8)
    fig_rect(fig, 14, call_y, 1.6, 22, ACCENT, radius=0.003)
    fig_text(fig, 18, call_y + 3.5,
             "40 % жилья — две школы рядом,\n25 % — ни одной.",
             size=11.5, color=PRIMARY, weight="bold", linespacing=1.25)
    fig_text(fig, 18, call_y + 14.5,
             "Избыточность и дефицит сосуществуют в разных частях города.",
             size=7.8, color=TEXT)

    # Полоса метода
    strip_y = 232.0
    fig_rect(fig, 14, strip_y, 182, 11, PRIMARY, radius=0.005)
    fig_text(fig, 18, strip_y + 2.4, "МЕТОД", size=6.4, color="#A9BCD6", weight="bold")
    for i, step in enumerate(STEPS):
        fig_text(fig, 36 + i * 30, strip_y + 2.4, step, size=7.8, color="white", weight="bold")
        if i < len(STEPS) - 1:
            fig_text(fig, 36 + i * 30 + 21.5, strip_y + 2.4, "→", size=7.8, color="#A9BCD6")

    # Стек
    fig_text(fig, 14, strip_y + 15, STACK, size=7.9, color=GRAY)

    # Контакты + QR
    qr_path = PROC / "teaser_qr.png"
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(MAP_URL)
    qr.make(fit=True)
    qr.make_image(fill_color=PRIMARY, back_color="white").save(qr_path)

    contact_y = strip_y + 23
    fig_text(fig, 14, contact_y, "ССЫЛКИ И КОНТАКТЫ", size=7.8, color=ACCENT, weight="bold")
    fig_text(fig, 14, contact_y + 6.5, f"Почта: {EMAIL}", size=9.2, color=TEXT, weight="bold")
    fig_text(fig, 14, contact_y + 13, f"GitHub: {GH_URL}", size=8.4, color=TEXT)
    fig_text(fig, 14, contact_y + 19, f"Веб-карта: {MAP_URL}", size=8.4, color=TEXT)

    if qr_path.exists():
        qr_img = mpimg.imread(qr_path)
        qr_mm = 24.0
        ax_qr = fig.add_axes([162 / W_MM, 1 - (contact_y + qr_mm) / H_MM, qr_mm / W_MM, qr_mm / H_MM])
        ax_qr.imshow(qr_img)
        ax_qr.axis("off")
        fig_text(fig, 162, contact_y + qr_mm + 2, "Открыть карту", size=6.4, color=GRAY)

    # Подвал
    fig_text(fig, 14, 287, "Данные: © OpenStreetMap contributors (ODbL) · 2026",
             size=6.6, color=GRAY)

    fig.savefig(OUT, format="pdf", facecolor="white")
    plt.close(fig)
    print(f"Сохранено: {OUT}")


if __name__ == "__main__":
    main()
