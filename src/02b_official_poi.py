"""Шаг 2b: официальные перечни школ и детских садов Каменска-Уральского.

Скачивает карточки с obr-ku.ru, вытаскивает название, номер и адреса,
сохраняет в data/raw/. Геокодирование — отдельным шагом (02c), чтобы не
дёргать Nominatim при каждом пересчёте.

Выход:
    data/raw/official_schools.csv
    data/raw/official_kindergartens.csv

Запуск:
    python src/02b_official_poi.py
"""
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

BASE = "https://obr-ku.ru"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kamensk-accessibility/0.1"}

LISTS = {
    "school": {
        "url": "/munitsipalnye-uchrezhdeniya/obshcheobrazovatelnye-uchrezhdeniya",
        "pages": 4,
        "out": "official_schools.csv",
    },
    "kindergarten": {
        "url": "/munitsipalnye-uchrezhdeniya/doshkolnye-obrazovatelnye-uchrezhdeniya",
        "pages": 6,
        "out": "official_kindergartens.csv",
    },
}

CARD_RE = re.compile(r"/obshcheobrazovatelnye-uchrezhdeniya/(\d+)-|/doshkolnye-obrazovatelnye-uchrezhdeniya/(\d+)-")


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def list_cards(category):
    """Ссылки на карточки учреждений со всех страниц списка."""
    seen, cards = set(), []
    for page in range(LISTS[category]["pages"]):
        url = BASE + LISTS[category]["url"] + (f"?start={page * 10}" if page else "")
        soup = BeautifulSoup(get(url), "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if CARD_RE.search(href):
                name = a.get_text(" ", strip=True)
                if not name or "Информация" in name:
                    continue
                key = href.split("?")[0]
                if key in seen:
                    continue
                seen.add(key)
                cards.append({"name": name, "url": BASE + key})
        time.sleep(0.3)
    return cards


STOP_RE = re.compile(
    r"\n\s*(?:Телефон|Директор|И\.О\.|Заведующий|E-mail|Сайт|ВКонтакте|Адрес:)", re.I
)


def parse_addresses(text):
    """Все блоки после 'Адрес:' — у детсадов может быть несколько корпусов."""
    chunks = []
    for m in re.finditer(r"Адрес:", text):
        rest = text[m.end():]
        stop = STOP_RE.search(rest)
        block = rest[: stop.start()] if stop else rest[:400]
        block = re.sub(r"\s+", " ", block).strip(" ,")
        if block:
            chunks.append(block)
    return chunks


def split_addresses(chunks):
    """Один блок может содержать несколько адресов корпусов."""
    out = []
    for address in chunks:
        if "(корпус" not in address.lower():
            out.append(address)
            continue
        parts = re.split(r"(?<=\))\s*,\s*", address)
        for p in parts:
            p = p.strip(" ,")
            if not p:
                continue
            p = re.sub(r"\s*\(корпус\s*\d+\)", "", p, flags=re.I).strip(" ,")
            if not p.lower().startswith("г."):
                p = "г. Каменск-Уральский, " + p
            out.append(p)
    return out


def parse_card(card, category):
    soup = BeautifulSoup(get(card["url"]), "lxml")
    text = soup.get_text("\n", strip=True)
    name = card["name"]
    num = re.search(r"№\s*(\d+)", name)
    addresses = split_addresses(parse_addresses(text))
    bus = re.search(r"bus\.gov\.ru/agency/(\d+)", str(soup))
    return {
        "type": category,
        "name": name,
        "number": int(num.group(1)) if num else None,
        "addresses": "; ".join(addresses) if addresses else "",
        "n_addresses": len(addresses),
        "bus_id": bus.group(1) if bus else "",
        "url": card["url"],
    }


def main():
    for category, cfg in LISTS.items():
        print(f"\n{category}: сбор карточек")
        cards = list_cards(category)
        print(f"  найдено карточек: {len(cards)}")
        rows = []
        for i, card in enumerate(cards, 1):
            try:
                rows.append(parse_card(card, category))
            except Exception as exc:
                print(f"  ошибка на {card['url']}: {exc}")
            if i % 10 == 0:
                print(f"  обработано {i}/{len(cards)}")
            time.sleep(0.3)
        df = pd.DataFrame(rows)
        out = RAW / cfg["out"]
        df.to_csv(out, index=False, encoding="utf-8")
        print(f"  сохранено: {out} ({len(df)} строк, адресов: {int(df['n_addresses'].sum())})")


if __name__ == "__main__":
    main()
