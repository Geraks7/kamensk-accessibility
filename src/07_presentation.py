"""Шаг 7: презентация проекта (PPTX).

Собирает presentation.pptx: 8 слайдов с ключевыми числами и картами.

Вход:
    maps/01_walk_graph.png
    maps/02_coverage_school.png
    maps/04_critical_objects.png

Выход:
    presentation.pptx

Запуск:
    python src/07_presentation.py
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "maps"
OUT = ROOT / "presentation.pptx"

W, H = Inches(13.333), Inches(7.5)
PRIMARY = RGBColor(0x1F, 0x38, 0x64)
ACCENT = RGBColor(0xC0, 0x39, 0x2B)
DARK = RGBColor(0x22, 0x22, 0x22)
GRAY = RGBColor(0x66, 0x66, 0x66)
LIGHT = RGBColor(0xF2, 0xF4, 0xF8)

TITLE = "Адаптация сети социальной инфраструктуры к сокращению населения"
SUBTITLE = "ГИС-анализ пешеходной доступности в Каменске-Уральском"
AUTHOR = "Максим Сачков · 11 класс · МАОУ СОШ №123, Екатеринбург"


def add_text(slide, left, top, width, height, text, size=16, bold=False, color=DARK,
             align=PP_ALIGN.LEFT, spacing=1.15):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.alignment = align
        p.space_after = Pt(4)
        p.line_spacing = spacing
        for run in p.runs:
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = "Calibri"
    return box


def add_bullets(slide, left, top, width, height, items, size=15):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = "•  " + item
        p.space_after = Pt(10)
        p.line_spacing = 1.2
        for run in p.runs:
            run.font.size = Pt(size)
            run.font.color.rgb = DARK
            run.font.name = "Calibri"
    return box


def new_slide(prs, title, subtitle=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), W, Inches(0.12))
    bar.fill.solid()
    bar.fill.fore_color.rgb = PRIMARY
    bar.line.fill.background()
    add_text(slide, Inches(0.6), Inches(0.45), Inches(12.1), Inches(0.7), title, size=28, bold=True, color=PRIMARY)
    if subtitle:
        add_text(slide, Inches(0.6), Inches(1.1), Inches(12.1), Inches(0.5), subtitle, size=14, color=GRAY)
    return slide


def add_picture(slide, path, left, top, max_width, max_height):
    """Вставляет картинку, вписывая её в рамку с сохранением пропорций."""
    path = Path(path)
    if not path.exists():
        return None
    from PIL import Image

    with Image.open(path) as im:
        iw, ih = im.size
    ratio = iw / ih
    w = int(max_width)
    h = int(w / ratio)
    if h > max_height:
        h = int(max_height)
        w = int(h * ratio)
    return slide.shapes.add_picture(str(path), left, top, width=Emu(w), height=Emu(h))


def main():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # 1. Титул
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(1, Inches(0), Inches(0), W, H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = PRIMARY
    bg.line.fill.background()
    add_text(s, Inches(0.9), Inches(2.0), Inches(11.5), Inches(1.8), TITLE, size=32, bold=True,
             color=RGBColor(0xFF, 0xFF, 0xFF))
    add_text(s, Inches(0.9), Inches(3.9), Inches(11.5), Inches(0.8), SUBTITLE, size=20,
             color=RGBColor(0xD6, 0xE0, 0xF0))
    line = s.shapes.add_shape(1, Inches(0.9), Inches(4.75), Inches(2.2), Inches(0.05))
    line.fill.solid()
    line.fill.fore_color.rgb = ACCENT
    line.line.fill.background()
    add_text(s, Inches(0.9), Inches(5.1), Inches(11.5), Inches(0.5), AUTHOR, size=14,
             color=RGBColor(0xD6, 0xE0, 0xF0))
    add_text(s, Inches(0.9), Inches(6.4), Inches(11.5), Inches(0.4),
             "github.com/Geraks7/kamensk-accessibility", size=12, color=RGBColor(0xA9, 0xBC, 0xD6))

    # 2. Проблема
    s = new_slide(prs, "Проблема", "Город теряет население, сеть осталась прежней")
    add_bullets(s, Inches(0.7), Inches(1.9), Inches(6.4), Inches(4.6), [
        "Население: 207 780 (1989) → 160 312 (2025), −23 %",
        "Сеть школ, детсадов и поликлиник рассчитана на большее число жителей",
        "Решения о сокращении принимаются по количеству объектов, а не по тому, "
        "кого они оставят без услуги",
        "Нормативные радиусы считаются по прямой и не учитывают улично-дорожную сеть",
    ])
    card = s.shapes.add_shape(1, Inches(7.5), Inches(2.1), Inches(5.2), Inches(2.4))
    card.fill.solid()
    card.fill.fore_color.rgb = LIGHT
    card.line.fill.background()
    add_text(s, Inches(7.8), Inches(2.35), Inches(4.6), Inches(0.5), "Исследовательский вопрос", size=13, bold=True, color=PRIMARY)
    add_text(s, Inches(7.8), Inches(2.75), Inches(4.6), Inches(1.6),
             "Как изменение сети объектов влияет на доступность услуг и какие сценарии "
             "адаптации сохраняют её без существенных потерь?", size=15, color=DARK)

    # 3. Данные и метод
    s = new_slide(prs, "Данные и метод", "OpenStreetMap + официальные перечни + нормативы СП 42.13330")
    add_bullets(s, Inches(0.7), Inches(1.9), Inches(5.6), Inches(4.8), [
        "6 029 жилых зданий, 1 752 узла спроса",
        "36 школ, 64 детсада, 31 медучреждение",
        "Пешеходный граф: 8 167 узлов, 23 452 ребра",
        "Кратчайшие пути по сети → изохроны 10/15/20 мин",
        "Показатели: покрытие, дублирование, разрыв с нормативом",
        "Сценарии: жадное удаление с бюджетом потери покрытия",
    ], size=15)
    add_picture(s, MAPS / "01_walk_graph.png", Inches(6.6), Inches(1.9), Inches(5.9), Inches(5.2))

    # 4. Покрытие
    s = new_slide(prs, "Покрытие 15 минут", "Доля жилой застройки в зоне пешеходной доступности")
    add_text(s, Inches(0.8), Inches(1.85), Inches(3.0), Inches(0.4), "Тип объекта", size=12, color=GRAY)
    add_text(s, Inches(4.2), Inches(1.85), Inches(1.3), Inches(0.4), "15 мин", size=12, bold=True, color=GRAY)
    add_text(s, Inches(5.5), Inches(1.85), Inches(1.3), Inches(0.4), "20 мин", size=12, bold=True, color=GRAY)
    rows = [("Школы", "67 %", "89 %"), ("Детские сады", "66 %", "80 %"), ("Поликлиники", "46 %", "61 %")]
    y = 2.35
    for name, v15, v20 in rows:
        add_text(s, Inches(0.8), Inches(y), Inches(3.2), Inches(0.5), name, size=18, bold=True)
        add_text(s, Inches(4.2), Inches(y), Inches(1.3), Inches(0.6), v15, size=26, bold=True, color=PRIMARY)
        add_text(s, Inches(5.5), Inches(y + 0.1), Inches(1.3), Inches(0.5), v20, size=20, color=DARK)
        y += 0.95
    add_text(s, Inches(0.8), Inches(5.6), Inches(6.0), Inches(1.2),
             "Одновременно 33–54 % жилья не имеет ни одного объекта в пределах 15 минут — "
             "избыточность и дефицит сосуществуют в разных частях города.", size=13, color=GRAY)
    add_picture(s, MAPS / "02_coverage_school.png", Inches(7.2), Inches(1.7), Inches(5.4), Inches(5.3))

    # 5. Норматив против сети
    s = new_slide(prs, "Норматив против сети", "Одно и то же расстояние: по прямой и по улицам")
    data = [("Школы", "500 м", "71 %", "23 %", "−48 п.п."),
            ("Детсады", "300 м", "59 %", "13 %", "−45 п.п."),
            ("Поликлиники", "1 000 м", "76 %", "41 %", "−35 п.п.")]
    headers = ["Тип", "Радиус", "По прямой", "По сети", "Разрыв"]
    xs = [0.9, 3.6, 5.4, 7.4, 9.3]
    for x, h in zip(xs, headers):
        add_text(s, Inches(x), Inches(1.9), Inches(1.9), Inches(0.4), h, size=13, bold=True, color=GRAY)
    y = 2.4
    for r in data:
        for x, val, sz, bold, col in zip(xs, r, [16, 16, 16, 16, 18], [True, False, False, False, True],
                                         [DARK, DARK, GRAY, DARK, ACCENT]):
            add_text(s, Inches(x), Inches(y), Inches(1.9), Inches(0.4), val, size=sz, bold=bold, color=col)
        y += 0.75
    add_text(s, Inches(0.9), Inches(5.0), Inches(11.4), Inches(1.4),
             "Нормативные радиусы, измеренные по прямой, завышают доступность в 1,5–4 раза. "
             "Уличная сеть и барьеры «съедают» от 35 до 48 процентных пунктов норматива — "
             "это главный методический результат работы.", size=15, color=DARK)

    # 6. Сценарии
    s = new_slide(prs, "Сценарии сокращения сети", "Жадный алгоритм, бюджет потери покрытия 0–3 %")
    add_bullets(s, Inches(0.7), Inches(1.9), Inches(6.2), Inches(4.6), [
        "Умеренный (0 %): −12 школ, −32 детсада, −10 поликлиник при неизменном покрытии",
        "Средний (1 %): −18 школ, −15 поликлиник, потеря 0,4–0,8 п.п.",
        "Даже при нулевой потере покрытия среднее время до объекта растёт на 0,3–0,6 мин",
        "Критичные объекты: Школа №32 (10,9 % жилья), Детсад №34 (7,7 %)",
        "Ограничение: не более половины сети — модель не учитывает вместимость",
    ], size=14)
    add_picture(s, MAPS / "04_critical_objects.png", Inches(7.1), Inches(1.7), Inches(5.5), Inches(5.3))

    # 7. Ограничения
    s = new_slide(prs, "Ограничения и что дальше", "Честные ограничения — часть результата")
    add_bullets(s, Inches(0.7), Inches(1.9), Inches(6.2), Inches(4.6), [
        "Вместимость объектов не учтена: школа на 200 и на 1200 мест равны",
        "Нет возрастной структуры: спрос считается однородным",
        "Пешеходная сеть OSM неполная — часть тротуаров не закартирована",
        "Промышленные зоны влияют только через геометрию сети",
    ], size=15)
    add_bullets(s, Inches(7.2), Inches(1.9), Inches(5.4), Inches(4.6), [
        "Сверка объектов с перечнями obr-ku.ru и miacso.ru",
        "Веса спроса по возрастной структуре",
        "Сценарии с учётом вместимости",
        "Веб-карта для администрации и жителей",
    ], size=15)

    # 8. Итог
    s = new_slide(prs, "Что сделано", None)
    add_bullets(s, Inches(0.7), Inches(1.6), Inches(6.3), Inches(4.8), [
        "Воспроизводимый пайплайн: данные → доступность → сценарии → карты",
        "Методика с оценкой чувствительности и ограничениями",
        "Реестр объектов «избыточен / критичен»",
        "Три сценария адаптации сети с числами",
        "4 карты и интерактивная веб-карта",
    ], size=16)
    add_text(s, Inches(7.3), Inches(1.8), Inches(5.2), Inches(0.5), "Ссылки", size=14, bold=True, color=PRIMARY)
    add_text(s, Inches(7.3), Inches(2.3), Inches(5.2), Inches(2.4),
             "github.com/Geraks7/kamensk-accessibility\ngeraks7.github.io/kamensk-accessibility",
             size=13, color=DARK)
    add_text(s, Inches(7.3), Inches(5.0), Inches(5.2), Inches(1.0),
             "Данные: © OpenStreetMap contributors (ODbL)", size=11, color=GRAY)

    prs.save(str(OUT))
    print(f"Сохранено: {OUT}")


if __name__ == "__main__":
    main()
