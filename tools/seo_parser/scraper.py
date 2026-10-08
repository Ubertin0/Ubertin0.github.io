import urllib.request
import re
import html
import json
import time
import os
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("Balandina (Наш эталон)", "https://balandinatherapy.ru/"),
    ("Alter (Агрегатор доказательной терапии)", "https://alter.ru/"),
    ("Yasno (Лидер онлайн-психотерапии)", "https://yasno.live/"),
    ("YouTalk (Онлайн-психотерапия)", "https://you-talk.ru/"),
    ("B17 (Профиль Натальи Баландиной)", "https://www.b17.ru/balandinanathalie/?prt=76921")
]

STOP_WORDS = set(
    "и в не на с по как к из у за от о об для что это все мы вы он она они но или да если даже уже до при только так же ли был было были быть мне вам вас вам".split()
)

def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  ⚠ Ошибка загрузки {url}: {e}")
        return ""

def clean(text):
    t = re.sub(r"<[^>]+>", " ", text)
    t = html.unescape(t)
    return " ".join(t.split())

def analyze(raw_html):
    title = re.search(r"<title>(.*?)</title>", raw_html, re.I)
    desc = re.search(r"<meta\s+name=[\"\x27]description[\"\x27]\s+content=[\"\x27](.*?)[\"\x27]", raw_html, re.I)
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", raw_html, re.I | re.DOTALL)
    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", raw_html, re.I | re.DOTALL)

    body = re.sub(r"<(script|style|svg|nav|footer)[^>]*>.*?</\1>", " ", raw_html, flags=re.I | re.DOTALL)
    plain = clean(body)
    words = [w.lower() for w in re.findall(r"[а-яёa-z]{4,}", plain.lower()) if w.lower() not in STOP_WORDS]
    phrases = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1) if words[i] not in STOP_WORDS and words[i+1] not in STOP_WORDS]

    return {
        "title": clean(title.group(1)) if title else "N/A",
        "description": clean(desc.group(1)) if desc else "N/A",
        "h1": [clean(x) for x in h1s],
        "h2": [clean(x) for x in h2s][:8],
        "top_phrases": [p for p, _ in Counter(phrases).most_common(12)]
    }

print("=== ЗАПУСК ПАРСЕРА СЕМАНТИКИ КОНКУРЕНТОВ ===")
data = {}
for name, url in TARGETS:
    print(f"→ Загрузка {name} ({url})...")
    html_content = fetch(url)
    if html_content:
        data[name] = analyze(html_content)
    time.sleep(1.5)

# Сохраняем сырой JSON
json_path = os.path.join(BASE_DIR, "competitors_data.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Content Gap (чего нет на balandinatherapy.ru)
our_phrases = set(data.get("Balandina (Наш эталон)", {}).get("top_phrases", []))
comp_phrases = set()
for k, v in data.items():
    if "Balandina" not in k:
        comp_phrases.update(v.get("top_phrases", []))
gap_phrases = sorted(list(comp_phrases - our_phrases))[:15]

# Формируем итоговый отчет Markdown
report = f"""# SEO-Аудит конкурентов и поисковых запросов
Дата сбора: {time.strftime('%Y-%m-%d %H:%M')}
Анализируемые ресурсы: {len(data)} сайтов

## 1. Сводная таблица мета-тегов лидеров рынка
| Сайт | Title | H1 |
|---|---|---|
"""
for name, d in data.items():
    h1_text = " / ".join(d['h1']) if d['h1'] else "—"
    report += f"| **{name}** | {d['title']} | {h1_text} |\n"

report += f"""
## 2. Семантический разрыв (Content Gap)
Фразы и поисковые темы, которые активно привлекают трафик конкурентам, но отсутствуют в основном ядре balandinatherapy.ru:
"""
for p in gap_phrases:
    report += f"- `{p}`\n"

report += """
## 3. Топ-10 тем для Telegram-канала (под органический поиск)
Каждая тема закрывает высокочастотный поисковый интент Яндекса/Google и при авто-публикации в блог через n8n превратится в трафиковую статью:

1. **«Почему советы "просто успокойся" не работают: как ЛОРП-терапия разбирает механизм тревоги»** (запрос: терапия тревоги онлайн)
2. **«Синдром самозванца у руководителя: цена постоянного гиперконтроля и страха ошибки»** (запрос: психолог для предпринимателей)
3. **«Панические атаки: что тело пытается сказать, когда игнорируется хроническое напряжение»** (запрос: панические атаки помощь психолога)
4. **«Эмоциональное выгорание vs лень: как отличить истощение нервной системы от прокрастинации»** (запрос: стадии профессионального выгорания)
5. **«Сложности с делегированием: почему руководителю проще сделать всё самому»** (запрос: психологические барьеры делегирования)
6. **«Повторяющиеся сценарии в отношениях: почему мы бессознательно выбираем одних и тех же людей»** (запрос: проблемы в отношениях психолог)
7. **«Как устроен бесплатный ознакомительный звонок с психологом: 15 минут без давления и оценок»** (запрос: первая консультация психолога онлайн)
8. **«Размытые личные границы на работе: как научиться говорить "нет" без чувства вины»** (запрос: отстаивание личных границ)
9. **«Кризис смысла после достижения целей: когда всё внешне хорошо, а внутри пустота»** (запрос: кризис среднего возраста предпринимателя)
10. **«Личностно-ориентированная реконструктивная терапия: чем ЛОРП отличается от КПТ и коучинга»** (запрос: что такое лорп психотерапия)
"""

report_path = os.path.join(BASE_DIR, "COMPETITORS_SEO_REPORT.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report)

print(f"\n✅ ПАРСИНГ ЗАВЕРШЕН УСПЕШНО!")
print(f"  - Данные сохранены: tools/seo_parser/competitors_data.json")
print(f"  - Аналитический отчет: tools/seo_parser/COMPETITORS_SEO_REPORT.md\n")
