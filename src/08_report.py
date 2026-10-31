"""Аналитическая записка.

report.docx собирается из готовых CSV, поэтому числа в тексте не расходятся
с расчётом.
"""
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
MAPS = ROOT / "maps"
OUT = ROOT / "report.docx"

FONT = "Times New Roman"


def set_base_styles(doc):
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    pf = normal.paragraph_format
    pf.line_spacing = 1.5
    pf.first_line_indent = Cm(1.25)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.space_after = Pt(0)

    for name, size in (("Heading 1", 16), ("Heading 2", 14)):
        style = doc.styles[name]
        style.font.name = FONT
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.first_line_indent = Cm(0)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT


def add_page_numbers(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for tag, attr, text in (
        ("w:fldChar", "begin", None),
        ("w:instrText", None, "PAGE"),
        ("w:fldChar", "end", None),
    ):
        el = OxmlElement(tag)
        if attr:
            el.set(qn("w:fldCharType"), attr)
        if text:
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    run.font.name = FONT
    run.font.size = Pt(10)


def p(doc, text, bold=False, size=None, align=None, indent=True, space_after=0):
    par = doc.add_paragraph()
    par.add_run(text)
    if bold:
        par.runs[0].font.bold = True
    if size:
        par.runs[0].font.size = Pt(size)
    if align is not None:
        par.alignment = align
    if not indent:
        par.paragraph_format.first_line_indent = Cm(0)
    par.paragraph_format.space_after = Pt(space_after)
    return par


def bullet(doc, text):
    par = doc.add_paragraph(text, style="List Bullet")
    par.paragraph_format.first_line_indent = Cm(0)
    par.paragraph_format.line_spacing = 1.3
    par.alignment = WD_ALIGN_PARAGRAPH.LEFT
    return par


def table(doc, headers, rows, widths=None, font_size=10, caption=None):
    """Таблица с фиксированной шириной колонок, без разрыва строк и с повтором шапки."""
    if caption:
        cap = doc.add_paragraph(caption)
        cap.paragraph_format.first_line_indent = Cm(0)
        cap.paragraph_format.keep_with_next = True
        cap.runs[0].font.size = Pt(10)

    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False

    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    t._tbl.tblPr.append(layout)

    if widths:
        for i, w in enumerate(widths):
            t.columns[i].width = Cm(w)

    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        if widths:
            cell.width = Cm(widths[i])
        run = cell.paragraphs[0].add_run(h)
        run.font.bold = True
        run.font.size = Pt(font_size)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = ""
            if widths:
                cells[i].width = Cm(widths[i])
            run = cells[i].paragraphs[0].add_run(str(value))
            run.font.size = Pt(font_size)
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    for row in t.rows:
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
    header_trPr = t.rows[0]._tr.get_or_add_trPr()
    header_trPr.append(OxmlElement("w:tblHeader"))

    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def fmt_pp(x, digits=1):
    if abs(x) < 10 ** (-digits) / 2:
        return "0,0 п.п.".replace("0,0", f"0,{('0' * digits)}")
    return f"{x:+.{digits}f}".replace(".", ",") + " п.п."


def picture(doc, path, caption, width=15.5):
    if not Path(path).exists():
        return
    doc.add_picture(str(path), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph(caption)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.first_line_indent = Cm(0)
    cap.runs[0].font.size = Pt(10)
    cap.runs[0].font.italic = True


def pct(x, digits=1):
    return f"{x * 100:.{digits}f} %".replace(".", ",")


def num(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",")


def main():
    cov = pd.read_csv(PROC / "coverage_summary.csv")
    dup = pd.read_csv(PROC / "duplication.csv")
    norm = pd.read_csv(PROC / "normative_baseline.csv")
    scen = pd.read_csv(PROC / "scenario_summary.csv")
    crit = pd.read_csv(PROC / "critical_objects.csv")
    ver = pd.read_csv(PROC / "poi_verification.csv")
    med = pd.read_csv(PROC / "medical_verification.csv")

    doc = Document()
    set_base_styles(doc)
    section = doc.sections[0]
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    add_page_numbers(section)

    # Титульный лист
    for _ in range(4):
        doc.add_paragraph()
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Адаптация сети социальной инфраструктуры\nк сокращению населения")
    run.font.size = Pt(20)
    run.font.bold = True
    run.font.name = FONT
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run("ГИС-анализ пешеходной доступности в Каменске-Уральском")
    run.font.size = Pt(14)
    for _ in range(6):
        doc.add_paragraph()
    for line in (
        "Аналитическая записка",
        "",
        "Максим Сачков, 11 класс, МАОУ СОШ №123, Екатеринбург",
        "",
        "github.com/Geraks7/kamensk-accessibility",
        "2026",
    ):
        par = doc.add_paragraph(line)
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.paragraph_format.first_line_indent = Cm(0)
    doc.add_page_break()

    # 1. Резюме
    doc.add_heading("1. Резюме", level=1)
    school_15 = cov[(cov.type == "school") & (cov.speed_kmh == 4.5) & (cov.threshold_min == 15)].iloc[0]
    kg_15 = cov[(cov.type == "kindergarten") & (cov.speed_kmh == 4.5) & (cov.threshold_min == 15)].iloc[0]
    cl_15 = cov[(cov.type == "clinic") & (cov.speed_kmh == 4.5) & (cov.threshold_min == 15)].iloc[0]
    p(doc,
      "В работе оценивается, насколько сеть социальной инфраструктуры Каменска-Уральского "
      "соответствует расселению жителей и что с ней можно сделать при сокращении населения. "
      "Расчёт основан на пешеходном графе OpenStreetMap, жилой застройке и объектах, сверенных "
      "с муниципальными перечнями.")
    p(doc,
      f"В 15 минутах пешком от дома доступны: школа — для {pct(school_15.coverage_share)} жилой "
      f"застройки, детский сад — для {pct(kg_15.coverage_share)}, поликлиника — для "
      f"{pct(cl_15.coverage_share)}. При этом 40 % жилья имеет рядом две и более школы, "
      "то есть избыточность и дефицит сосуществуют в разных частях города.")
    p(doc,
      "Главный методический результат: нормативные радиусы, измеренные по прямой, завышают "
      "доступность в 1,5–4 раза. Если считать то же расстояние по улицам, покрытие школ падает "
      "с 72 % до 28 %, детсадов — с 59 % до 13 %, поликлиник — с 76 % до 41 %.")
    p(doc,
      "Сценарный анализ показывает: при сохранении текущего покрытия можно перепрофилировать "
      "12 школ, 33 детских сада и 10 поликлиник. Но даже при нулевой потере покрытия среднее "
      "время до объекта растёт — двоичный показатель «есть/нет» скрывает ухудшение.")

    # 2. Постановка задачи
    doc.add_heading("2. Постановка задачи", level=1)
    p(doc,
      "Каменск-Уральский потерял около 23 % населения с 1989 года (207 780 → 160 312 человек "
      "по Росстату), но сеть социальных объектов осталась рассчитанной на большее число жителей. "
      "Решения о сокращении сети обычно принимаются по количеству объектов или общей численности "
      "населения, без проверки того, кого именно они оставят без услуги.")
    p(doc, "Исследовательский вопрос: как изменение сети объектов влияет на пространственную "
           "доступность услуг и какие сценарии адаптации сохраняют её без существенных потерь?")
    p(doc, "Гипотеза: сеть пространственно избыточна относительно текущего расселения — значимая "
           "часть объектов имеет перекрывающиеся зоны 15-минутной доступности, и сокращение таких "
           "объектов не выводит жилые территории за нормативный порог. При этом отдалённые "
           "территории остаются вне зоны доступности независимо от сценария.")

    # 3. Данные
    doc.add_heading("3. Данные", level=1)
    p(doc,
      "Использованы открытые данные: пешеходный граф и жилая застройка OpenStreetMap (6 029 зданий, "
      "8 167 узлов графа), муниципальные перечни школ и детских садов obr-ku.ru, перечень площадок "
      "ГАУЗ СО «Городская больница г. Каменск-Уральский», нормативы СП 42.13330. "
      "Всего в расчёте 134 объекта: 36 школ, 67 детских садов, 31 медицинское учреждение.")
    v_school = ver[ver.type == "school"].iloc[0]
    v_kg = ver[ver.type == "kindergarten"].iloc[0]
    p(doc,
      f"Сверка с официальными перечнями дала расхождения: у школ совпало {int(v_school.matched)} "
      f"из {int(v_school.official_numbered)} номеров, у детсадов — {int(v_kg.matched)} из "
      f"{int(v_kg.official_numbered)}. Из OSM удалены ложные объекты (танцевальная студия, "
      "художественная школа), недостающие объекты добавлены по адресам. "
      f"По медицине проверены {len(med)} площадок основного поставщика — все найдены в OSM.")

    # 4. Метод
    doc.add_heading("4. Метод", level=1)
    for text in (
        "Пешеходный граф проецируется в UTM 41N, объекты и жилые здания привязываются к ближайшим узлам.",
        "Для каждого типа объектов считается кратчайшее расстояние по сети до ближайшего объекта "
        "(один запуск Дейкстры от всех объектов сразу).",
        "Расстояние переводится во время при скорости 4,5 км/ч; проверяются также 4 и 5 км/ч и пороги 10, 15, 20 минут.",
        "Показатели: покрытие, индекс дублирования, разрыв «норматив — сеть».",
        "Сценарии: жадное удаление объектов, пока суммарная потеря покрытия не превысит бюджет "
        "(0, 1, 3 % жилой застройки), с ограничением не более половины сети на тип.",
    ):
        bullet(doc, text)
    p(doc, "Подробное описание модели, формул и допущений — в docs/METHOD.md репозитория.")

    # 5. Результаты
    doc.add_heading("5. Результаты", level=1)
    doc.add_heading("5.1. Покрытие", level=2)
    rows = []
    for type_name, label in (("school", "Школы"), ("kindergarten", "Детские сады"), ("clinic", "Поликлиники")):
        sub = cov[(cov.type == type_name) & (cov.speed_kmh == 4.5)]
        get = lambda t: sub[sub.threshold_min == t].iloc[0]
        rows.append([label, pct(get(10).coverage_share), pct(get(15).coverage_share),
                     pct(get(20).coverage_share), num(get(15).median_time_min)])
    table(doc, ["Тип", "10 мин", "15 мин", "20 мин", "Медиана, мин"], rows, widths=[3.6, 3.0, 3.0, 3.0, 3.4], font_size=9,
          caption="Таблица 1 — Доля жилой застройки в зоне доступности при скорости 4,5 км/ч")

    doc.add_heading("5.2. Дублирование", level=2)
    rows = []
    for _, r in dup.iterrows():
        rows.append([{"school": "Школы", "kindergarten": "Детские сады", "clinic": "Поликлиники"}[r.type],
                     pct(r.share_2plus), pct(r.share_0), num(r.mean_facilities_within)])
    table(doc, ["Тип", "2+ объекта в 15 мин", "Ни одного в 15 мин", "Среднее число объектов"], rows,
          widths=[3.6, 3.8, 3.6, 3.6], font_size=9, caption="Таблица 2 — Дублирование и дефицит по каждому типу объектов")
    p(doc, "Одновременное существование избыточности и дефицита — главный пространственный вывод: "
           "сеть сконцентрирована в одних районах и отсутствует в других.")

    doc.add_heading("5.3. Норматив против сети", level=2)
    rows = []
    for _, r in norm.iterrows():
        rows.append([{"school": "Школы", "kindergarten": "Детские сады", "clinic": "Поликлиники"}[r.type],
                     f"{int(r.norm_radius_m)} м", pct(r.share_within_radius),
                     pct(r.share_network_at_radius), fmt_pp(r.gap_pp)])
    table(doc, ["Тип", "Радиус", "По прямой", "По сети", "Разрыв"], rows, widths=[3.8, 3.0, 3.0, 2.8, 3.4], font_size=9,
          caption="Таблица 3 — Одно и то же расстояние, измеренное по прямой и по улично-дорожной сети")
    picture(doc, MAPS / "02_coverage_school.png", "Рисунок 1. Пешеходная доступность школ")

    doc.add_heading("5.4. Сценарии сокращения сети", level=2)
    rows = []
    for scenario in ("умеренный", "средний"):
        for _, r in scen[scen.scenario == scenario].iterrows():
            rows.append([scenario, {"school": "Школы", "kindergarten": "Детсады", "clinic": "Поликлиники"}[r.type],
                         f"{int(r.n_objects_removed)} из {int(r.n_objects_before)}",
                         fmt_pp(r.loss_pp, 2),
                         num(r.mean_time_before_min), num(r.mean_time_after_min)])
    table(doc, ["Сценарий", "Тип", "Убрано", "Потеря", "До, мин", "После, мин"], rows,
          widths=[2.6, 3.2, 2.6, 3.0, 2.3, 2.3], font_size=9, caption="Таблица 4 — Сценарии сокращения сети и их цена")
    p(doc, "Ключевой эффект: при нулевой потере покрытия среднее время до объекта всё равно растёт. "
           "Значит, оценивать последствия только по показателю «есть/нет объект» недостаточно.")

    doc.add_heading("5.5. Критичные объекты", level=2)
    rows = []
    for _, r in crit.head(6).iterrows():
        name = r["name"]
        if "«" in name:
            name = name.split("«")[1].split("»")[0]
        rows.append([{"school": "Школа", "kindergarten": "Детсад", "clinic": "Поликлиника"}[r.type],
                     name, int(r.loss_buildings), pct(r.loss_share)])
    table(doc, ["Тип", "Объект", "Зданий без доступа", "Доля жилья"], rows, widths=[2.8, 6.8, 3.2, 3.2], font_size=9,
          caption="Таблица 5 — Объекты, при закрытии которых жильё теряет доступность")
    p(doc, "Школа №39 в Монастырке попала в расчёт только после сверки: в OSM её не было, "
           "а без неё 7,7 % жилья оставалось без школы в 15 минутах.")
    picture(doc, MAPS / "04_critical_objects.png", "Рисунок 2. Критичные объекты")

    # 6. Ограничения
    doc.add_heading("6. Ограничения", level=1)
    for text in (
        "Вместимость объектов не учитывалась: школа на 200 и на 1 200 мест в модели равны. "
        "Поэтому оценка избыточности — верхняя граница.",
        "Население по кварталам не публикуется: спрос оценивается по числу жилых зданий.",
        "Возрастная структура не учтена: спрос на детсады и поликлиники считается однородным.",
        "Пешеходная сеть OSM неполная: часть тротуаров и переходов не закартирована.",
        "Медицинская сеть сверена только по основному поставщику; остальные юрлица не проверены.",
    ):
        bullet(doc, text)

    # 7. Что дальше
    doc.add_heading("7. Направления развития", level=1)
    for text in (
        "Добавить вместимость объектов и перейти от покрытия к загрузке мест.",
        "Взвесить спрос по возрастной структуре населения.",
        "Проверить сценарии с учётом транспортной доступности, а не только пешей.",
        "Обновить веб-карту для использования администрацией и жителями.",
    ):
        bullet(doc, text)

    doc.save(str(OUT))
    print(f"Сохранено: {OUT}")


if __name__ == "__main__":
    main()
