import os
import re
import glob
import requests
import random
import html
import json
import time
from bs4 import BeautifulSoup
from datetime import datetime

# --- Конфигурация ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHANNEL_URL = "https://t.me/s/balandinatherapy"
TEMPLATE_FILE = os.path.join(BASE_DIR, "article-template.html")
BLOG_FILE = os.path.join(BASE_DIR, "blog.html")
SEO_CACHE_FILE = os.path.join(BASE_DIR, "seo_cache.json")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
POSTS_PER_PAGE = 15

# DevOps-трюк: прячем HTML-маркеры от автоформаттеров VS Code
MARKER_START = "<" + "!-- START ARTICLES --" + ">"
MARKER_END = "<" + "!-- END ARTICLES --" + ">"
# --------------------

def load_seo_cache() -> dict:
    if os.path.exists(SEO_CACHE_FILE):
        try:
            with open(SEO_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Предупреждение: ошибка чтения seo_cache.json: {e}")
    return {}

def save_seo_cache(cache: dict) -> None:
    try:
        with open(SEO_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Предупреждение: ошибка сохранения seo_cache.json: {e}")

_DISCOVERED_MODELS = None

def get_gemini_models_list() -> list:
    global _DISCOVERED_MODELS
    if _DISCOVERED_MODELS is not None:
        return _DISCOVERED_MODELS

    if not GEMINI_API_KEY:
        _DISCOVERED_MODELS = []
        return []

    print(f"  [AI SEO] Инициализация ключа GEMINI_API_KEY (длина: {len(GEMINI_API_KEY)}, префикс: {GEMINI_API_KEY[:4]}...)")

    # 1. Попытка динамически запросить список поддерживаемых моделей у Google API
    endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models?key={GEMINI_API_KEY}"
    ]
    for url in endpoints:
        try:
            resp = requests.get(
                url,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                found = []
                for item in data.get('models', []):
                    methods = item.get('supportedGenerationMethods', [])
                    if 'generateContent' in methods:
                        m_name = item.get('name', '').replace('models/', '')
                        if m_name:
                            found.append(m_name)
                if found:
                    print(f"  [AI SEO] Доступные модели Gemini для вашего ключа: {found}")
                    preferred = [
                        "gemini-3.5-flash",
                        "gemini-3.8-flash",
                        "gemini-3.5-flash-lite",
                        "gemini-flash-latest",
                        "gemini-3.1-flash-lite",
                        "gemini-pro-latest"
                    ]
                    ordered = [m for m in preferred if m in found]
                    ordered += [m for m in found if "flash" in m.lower() and m not in ordered]
                    ordered += [m for m in found if m not in ordered]
                    _DISCOVERED_MODELS = ordered
                    return _DISCOVERED_MODELS
            else:
                err_snippet = resp.text.strip().replace("\n", " ")[:250]
                api_name = "v1beta" if "v1beta" in url else "v1"
                print(f"  [AI SEO] Проверка моделей ({api_name}) вернула статус {resp.status_code}: {err_snippet}")
        except Exception as e:
            print(f"  [AI SEO] Ошибка проверки моделей: {e}")

    _DISCOVERED_MODELS = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]
    return _DISCOVERED_MODELS

def get_seo_for_post(post_id: str, title: str, text: str, cache: dict) -> dict:
    if post_id in cache:
        return cache[post_id]

    if not GEMINI_API_KEY:
        return {}

    prompt = f"""Ты — профессиональный SEO-редактор и психолог для сайта частнопрактикующего психотерапевта Натальи Баландиной (метод ЛОРП).
Автор часто формулирует свои мысли метафорично или академическим языком.

Заголовок статьи: {title}
Текст статьи:
{text[:3500]}

Твоя задача — извлечь практические смыслы для поисковых систем (Яндекс, Google) и читателя:
1. "meta_description": привлекательное, емкое описание (140-160 символов, без кавычек) с высокочастотными поисковыми фразами, понятными обычному человеку (как ищут в Яндексе).
2. "key_takeaway": ключевая мысль статьи простыми словами (1-2 емких предложения), объясняющая жизненную суть текста для читателя.
3. "keywords": список из 5-8 популярных поисковых запросов и терминов, релевантных теме (например: ["выгорание на работе", "хроническая тревога", "как перестать все контролировать", "психотерапия отношений"]).
4. "tags": список из 3-5 хэштегов темы на русском языке (например: ["#выгорание", "#тревожность", "#сверхконтроль", "#психология"]).

Верни СТРОГО чистый JSON:
{{
  "meta_description": "...",
  "key_takeaway": "...",
  "keywords": ["...", "..."],
  "tags": ["#...", "#..."]
}}"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

    models = get_gemini_models_list()
    if not models:
        models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest"]

    for model in models:
        for api_ver in ["v1beta", "v1"]:
            api_url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent?key={GEMINI_API_KEY}"
            try:
                resp = requests.post(
                    api_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=40
                )
                if resp.status_code == 200:
                    result = resp.json()
                    text_content = result['candidates'][0]['content']['parts'][0]['text']
                    seo_data = json.loads(text_content)
                    if isinstance(seo_data, dict) and 'keywords' in seo_data:
                        cache[post_id] = seo_data
                        save_seo_cache(cache)
                        print(f"  [AI SEO] Статья {post_id} успешно оптимизирована через {model} ({api_ver})")
                        return seo_data
                else:
                    err_msg = resp.text.strip().replace("\n", " ")[:250]
                    print(f"  [AI SEO] Gemini API ({model}, {api_ver}) статус {resp.status_code}: {err_msg}")
            except Exception as e:
                print(f"  [AI SEO] Ошибка вызова Gemini ({model}, {api_ver}): {e}")

    return {}

def build_seo_html_components(seo_data: dict, default_excerpt: str):
    meta_desc = seo_data.get('meta_description') if seo_data else None
    if not meta_desc or len(meta_desc.strip()) < 20:
        meta_desc = default_excerpt

    keywords = seo_data.get('keywords', ["психотерапия", "психолог онлайн", "ЛОРП-практик"]) if seo_data else ["психотерапия", "психолог онлайн", "ЛОРП-практик"]
    if not isinstance(keywords, list) or not keywords:
        keywords = ["психотерапия", "психолог онлайн", "ЛОРП-практик"]
    keywords_json = json.dumps(keywords, ensure_ascii=False)

    takeaway = seo_data.get('key_takeaway', '').strip() if seo_data else ''
    if takeaway:
        safe_takeaway = html.escape(takeaway)
        summary_block = f'''
        <div class="article-summary">
            <span class="article-summary__tag">Ключевая мысль</span>
            <p>{safe_takeaway}</p>
        </div>'''
    else:
        summary_block = ''

    tags = seo_data.get('tags', []) if seo_data else []
    if tags and isinstance(tags, list):
        tags_spans = " ".join(f'<span class="article-tag">{html.escape(t.strip())}</span>' for t in tags if t.strip())
        tags_block = f'''
        <div class="article-tags">
            <span class="article-tags__label">Темы:</span>
            {tags_spans}
        </div>'''
    else:
        tags_block = ''

    return meta_desc, keywords_json, summary_block, tags_block

def enrich_existing_post_html(post_path: str, seo_data: dict) -> bool:
    if not seo_data:
        return False
    try:
        with open(post_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return False

    if '<div class="article-tags">' in content:
        return False

    soup = BeautifulSoup(content, 'html.parser')
    h1 = soup.find('h1', class_='article-title')
    article_content = soup.find('div', class_='article-content')
    if not h1 or not article_content:
        return False

    meta_desc, keywords_json, summary_block, tags_block = build_seo_html_components(seo_data, "")

    if summary_block and not soup.find('div', class_='article-summary'):
        summary_soup = BeautifulSoup(summary_block, 'html.parser')
        h1.insert_after(summary_soup)

    if tags_block and not soup.find('div', class_='article-tags'):
        tags_soup = BeautifulSoup(tags_block, 'html.parser')
        article_content.insert_after(tags_soup)

    if meta_desc and len(meta_desc.strip()) > 20:
        safe_desc = html.escape(meta_desc, quote=True)
        for meta in soup.find_all('meta', attrs={'name': 'description'}):
            meta['content'] = safe_desc
        for meta in soup.find_all('meta', attrs={'property': 'og:description'}):
            meta['content'] = safe_desc
        for meta in soup.find_all('meta', attrs={'name': 'twitter:description'}):
            meta['content'] = safe_desc

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if data.get('@type') == 'Article':
                data['keywords'] = seo_data.get('keywords', [])
                if meta_desc:
                    data['description'] = meta_desc
                script.string = '\n' + json.dumps(data, ensure_ascii=False, indent=2) + '\n    '
        except Exception:
            pass

    try:
        with open(post_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        return True
    except Exception as e:
        print(f"Ошибка записи {post_path}: {e}")
        return False

def is_valid_image_url(url: str | None) -> bool:
    if not url or url.strip() in ('{{IMAGE}}', 'None', '', 'null'):
        return False
    if not url.strip().startswith('http'):
        return False
    return True

def optimize_and_save_image(image_url: str | None, post_id: str) -> str | None:
    if not image_url or not image_url.strip().startswith("http"):
        return image_url
    posts_dir = os.path.join(BASE_DIR, "images", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    local_rel = f"images/posts/{post_id}.webp"
    local_abs = os.path.join(BASE_DIR, local_rel)
    if os.path.exists(local_abs) and os.path.getsize(local_abs) > 0:
        return local_rel
    try:
        import io
        import requests
        from PIL import Image
        resp = requests.get(image_url, timeout=12)
        if resp.status_code == 200:
            img = Image.open(io.BytesIO(resp.content))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            if img.width > 1200:
                h = int((1200 / img.width) * img.height)
                img = img.resize((1200, h), Image.Resampling.LANCZOS)
            img.save(local_abs, "WEBP", quality=82, method=6)
            return local_rel
    except Exception as err:
        pass
    return image_url

def extract_image_url(msg) -> str | None:
    photo_wrap = msg.find('a', class_='tgme_widget_message_photo_wrap')
    if photo_wrap:
        style = photo_wrap.get('style', '')
        match = re.search(r"background-image:url\('?(.*?)'?\)", style)
        if match:
            return match.group(1)
    text_div = msg.find('div', class_='tgme_widget_message_text')
    if text_div:
        for img in text_div.find_all('img'):
            src = img.get('src', '')
            if 'emoji' not in img.get('class', []) and '/emoji/' not in src:
                return src
    return None

def clean_text_div(text_div) -> None:
    for tag in text_div.find_all(['i', 'svg', 'video']):
        tag.decompose()
    for img in text_div.find_all('img'):
        src = img.get('src', '')
        if 'emoji' in img.get('class', []) or '/emoji/' in src:
            img.decompose()
    for a in text_div.find_all('a'):
        href = a.get('href', '')
        # Удаляем относительные ссылки поиска/хэштегов (?q=...) и пустые ссылки
        if href.startswith('?') or not a.get_text(strip=True):
            a.decompose()

def strip_hashtags(text: str) -> str:
    text = re.sub(r'<a\s+[^>]*href=["\']\?[^"\']*["\'][^>]*>[\s\S]*?</a>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'#\w+', '', text)
    text = re.sub(r'(?:<br\s*/?>\s*)+$', '', text.rstrip(), flags=re.IGNORECASE)
    return text

def generate_sitemap(posts: list[str], total_pages: int) -> None:
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    # Главная страница - самый высокий приоритет
    sitemap += f'  <url>\n    <loc>https://balandinatherapy.ru/</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>1.0</priority>\n  </url>\n'

    # Важные статические страницы
    static_pages = [
        ('education.html', '0.8', 'monthly'),
        ('privacy.html', '0.7', 'yearly'),
    ]

    for page, priority, changefreq in static_pages:
        sitemap += f'  <url>\n    <loc>https://balandinatherapy.ru/{page}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>{changefreq}</changefreq>\n    <priority>{priority}</priority>\n  </url>\n'

    # Страницы блога
    blog_pages = ['blog.html'] + [f'blog-{i}.html' for i in range(2, total_pages + 1)]
    for page in blog_pages:
        sitemap += f'  <url>\n    <loc>https://balandinatherapy.ru/{page}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>\n'

    # Статьи блога
    for post in posts:
        sitemap += f'  <url>\n    <loc>https://balandinatherapy.ru/{post}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.6</priority>\n  </url>\n'

    sitemap += '</urlset>\n'
    with open(os.path.join(BASE_DIR, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(sitemap)

def remove_image_from_article(article_html: str) -> str:
    soup = BeautifulSoup(article_html, 'html.parser')
    for hero in soup.find_all('div', class_='article-hero-image'):
        hero.decompose()
    for meta in soup.find_all('meta', property='og:image'):
        meta.decompose()
    for meta in soup.find_all('meta', attrs={'name': 'twitter:image'}):
        meta.decompose()
    html_str = str(soup)
    html_str = re.sub(r'"image":\s*"[^"]*",?\s*', '', html_str, count=1)
    html_str = re.sub(r'<div[^>]*class="article-hero-image"[^>]*>.*?</div>\s*', '', html_str, flags=re.DOTALL)
    return html_str

def generate_blog_page(page_num: int, cards: list[str], total_pages: int, raw_template: str) -> str:
    parts1 = raw_template.split(MARKER_START, 1)
    if len(parts1) < 2:
        print("ВНИМАНИЕ: Маркер START ARTICLES не найден в шаблоне!")
        return raw_template
        
    parts2 = parts1[1].split(MARKER_END, 1)
    if len(parts2) < 2:
        print("ВНИМАНИЕ: Маркер END ARTICLES не найден в шаблоне!")
        return raw_template

    cards_html = "\n".join(cards)
    pagination = '<div class="blog-pagination">'
    
    if page_num > 1:
        prev_page = "blog.html" if page_num == 2 else f"blog-{page_num - 1}.html"
        pagination += f'<a href="{prev_page}" class="pagination__nav">&larr; Назад</a>'
        
    for i in range(1, total_pages + 1):
        if i == page_num:
            pagination += f'<span class="pagination__num pagination__num--active">{i}</span>'
        else:
            page_file = "blog.html" if i == 1 else f"blog-{i}.html"
            pagination += f'<a href="{page_file}" class="pagination__num">{i}</a>'
            
    if page_num < total_pages:
        next_page = f"blog-{page_num + 1}.html"
        pagination += f'<a href="{next_page}" class="pagination__nav">Вперёд &rarr;</a>'
        
    pagination += '</div>'
    
    page_title = ""
    if page_num > 1:
        page_title = f'<h2 style="text-align: center; margin-bottom: 2rem; font-family: var(--font-heading); color: var(--color-text-muted);">Страница {page_num}</h2>\n'
        
    content = (
        parts1[0]
        + MARKER_START + "\n"
        + page_title 
        + cards_html 
        + "\n" 
        + pagination 
        + "\n            " + MARKER_END
        + parts2[1]
    )

    cur_page_file = "blog.html" if page_num == 1 else f"blog-{page_num}.html"
    content = content.replace(
        'href="https://balandinatherapy.ru/blog.html"',
        f'href="https://balandinatherapy.ru/{cur_page_file}"'
    )
    return content

def clean_fallback_from_existing_post(post_path: str) -> bool:
    try:
        with open(post_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception:
        return False
    soup = BeautifulSoup(html, 'html.parser')
    changed = False
    for hero in soup.find_all('div', class_='article-hero-image'):
        style = hero.get('style', '')
        match = re.search(r"background-image:url\('?(.*?)'?\)", style)
        if match:
            url = match.group(1)
            if not is_valid_image_url(url):
                hero.decompose()
                changed = True
    for meta in soup.find_all('meta', property='og:image'):
        if not is_valid_image_url(meta.get('content')):
            meta.decompose()
            changed = True
    for meta in soup.find_all('meta', attrs={'name': 'twitter:image'}):
        if not is_valid_image_url(meta.get('content')):
            meta.decompose()
            changed = True
    if not changed:
        return False
    html_str = str(soup)
    html_str = re.sub(r'"image":\s*"[^"]*",?\s*', '', html_str, count=1)
    html_str = re.sub(r'<div[^>]*class="article-hero-image"[^>]*>.*?</div>\s*', '', html_str, flags=re.DOTALL)
    with open(post_path, 'w', encoding='utf-8') as f:
        f.write(html_str)
    return True

def extract_excerpt_from_html(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.find('div', class_='article-content') or soup.find('article') or soup.find('main') or soup.find('body')
    if content:
        text = content.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        excerpt = text[:140].strip()
        if len(text) > 140:
            excerpt += "..."
        return excerpt
    return ""

def extract_image_from_html(html: str) -> str | None:
    soup = BeautifulSoup(html, 'html.parser')
    og = soup.find('meta', property='og:image')
    if og and is_valid_image_url(og.get('content')):
        return og['content']
    tw = soup.find('meta', attrs={'name': 'twitter:image'})
    if tw and is_valid_image_url(tw.get('content')):
        return tw['content']
    hero = soup.find('div', class_='article-hero-image')
    if hero and hero.get('style'):
        match = re.search(r"background-image:url\('?(.*?)'?\)", hero['style'])
        if match and is_valid_image_url(match.group(1)):
            return match.group(1)
    article = soup.find('article') or soup.find('div', class_='article-content')
    if article:
        img = article.find('img')
        if img and is_valid_image_url(img.get('src')):
            return img['src']
    return None

def main() -> None:
    print("Запуск парсера Telegram-канала...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(CHANNEL_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Ошибка сети: {e}")
        return
        
    soup = BeautifulSoup(response.text, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_wrap', limit=100)
    
    if not messages:
        print("Внимание: В Telegram-канале не найдено сообщений.")
        return
        
    if not os.path.exists(TEMPLATE_FILE) or not os.path.exists(BLOG_FILE):
        print("Ошибка: Не найден article-template.html или blog.html!")
        return
        
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        article_template = f.read()
        
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_template = f.read()
        
    existing_posts = set(glob.glob(os.path.join(BASE_DIR, 'post-*.html')))
    new_posts_count = 0
    all_cards = []
    seo_cache = load_seo_cache()

    if GEMINI_API_KEY:
        print(f"AI SEO: Модуль Gemini активен. Загружено {len(seo_cache)} записей из кэша.")
    else:
        print("AI SEO: GEMINI_API_KEY не обнаружен, используется стандартный режим.")
    
    for msg in messages:
        text_div = msg.find('div', class_='tgme_widget_message_text')
        if not text_div:
            continue
            
        time_tag = msg.find('time')
        if time_tag and time_tag.get('datetime'):
            try:
                dt = datetime.fromisoformat(time_tag['datetime'])
                post_date = dt.strftime("%d.%m.%Y")
                post_date_iso = dt.strftime("%Y-%m-%d")
            except ValueError:
                post_date = time_tag.text.strip() if time_tag.text else datetime.now().strftime("%d.%m.%Y")
                post_date_iso = datetime.now().strftime("%Y-%m-%d")
        else:
            post_date = datetime.now().strftime("%d.%m.%Y")
            post_date_iso = datetime.now().strftime("%Y-%m-%d")
            
        bold_tag = text_div.find(['b', 'strong'])
        if bold_tag:
            title = bold_tag.get_text(strip=True)
            bold_tag.decompose()
        else:
            title = "Без названия"
            for element in text_div.descendants:
                if element.name is None and element.string and element.string.strip():
                    full_text = element.string.strip()
                    title = full_text.split('.')[0].strip()
                    if len(title) > 120:
                        title = title[:120] + "..."
                    
                    remaining_text = full_text.replace(title, '', 1).lstrip('. \n')
                    element.replace_with(remaining_text)
                    break
                    
        for child in list(text_div.children):
            if child.name == 'br' or (child.name is None and not child.string.strip()):
                child.extract()
            else:
                break
                
        clean_text_div(text_div)
        image_url = extract_image_url(msg)
        post_link = msg.find('a', class_='tgme_widget_message_date')
        post_id = post_link['href'].split('/')[-1] if post_link else str(hash(text_div.get_text()))
        image_url = optimize_and_save_image(image_url, post_id)
        article_filename = f"post-{post_id}.html"
        article_path = os.path.join(BASE_DIR, article_filename)
        
        raw_text = strip_hashtags(text_div.get_text(separator=' '))
        excerpt = raw_text[:140].strip() + ("..." if len(raw_text) > 140 else "")

        if article_path in existing_posts:
            # Если статья уже создана ранее, но еще не обогащена в кэше
            if GEMINI_API_KEY and post_id not in seo_cache and len(raw_text) > 40:
                seo_data = get_seo_for_post(post_id, title, raw_text, seo_cache)
                if seo_data:
                    enrich_existing_post_html(article_path, seo_data)
        else:
            content_html = strip_hashtags(str(text_div))
            seo_data = get_seo_for_post(post_id, title, raw_text, seo_cache)
            meta_desc, keywords_json, summary_block, tags_block = build_seo_html_components(seo_data, excerpt)

            safe_title_attr = html.escape(title, quote=True)
            safe_desc_attr = html.escape(meta_desc, quote=True)
            safe_title_json = json.dumps(title, ensure_ascii=False)[1:-1]
            safe_desc_json = json.dumps(meta_desc, ensure_ascii=False)[1:-1]

            article_html = article_template.replace('{{TITLE}}', title)\
                                           .replace('{{DATE}}', post_date)\
                                           .replace('{{DATE_ISO}}', post_date_iso)\
                                           .replace('{{POST_ID}}', post_id)\
                                           .replace('{{META_DESC}}', meta_desc)\
                                           .replace('{{KEYWORDS_JSON}}', keywords_json)\
                                           .replace('{{SUMMARY_BLOCK}}', summary_block)\
                                           .replace('{{TAGS_BLOCK}}', tags_block)\
                                           .replace('{{CONTENT}}', content_html)

            # Валидация JSON-LD и Open Graph при наличии кавычек в заголовке/описании
            article_html = re.sub(r'("headline":\s*)"(.*?)"(,\s*\n)', rf'\1"{safe_title_json}"\3', article_html)
            article_html = re.sub(r'("description":\s*)"(.*?)"(,\s*\n)', rf'\1"{safe_desc_json}"\3', article_html)
            article_html = re.sub(r'("name":\s*)"(.*?)"(,\s*\n\s*"item":\s*"https://balandinatherapy\.ru/post-)', rf'\1"{safe_title_json}"\3', article_html)
            article_html = article_html.replace(f'content="{title} | Наталья Баландина"', f'content="{safe_title_attr} | Наталья Баландина"')
            article_html = article_html.replace(f'content="{meta_desc}"', f'content="{safe_desc_attr}"')
            
            if image_url:
                article_html = article_html.replace('{{IMAGE}}', image_url)
            else:
                article_html = remove_image_from_article(article_html)
                
            with open(article_path, 'w', encoding='utf-8') as f:
                f.write(article_html)
            new_posts_count += 1
            
        card_desc = excerpt
        if post_id in seo_cache and seo_cache[post_id].get('meta_description'):
            card_desc = seo_cache[post_id]['meta_description']

        image_block = '<div class="article-card__image article-card__image--placeholder"></div>'
        if image_url:
            image_block = f'\n                <div class="article-card__image" role="img" aria-label="Иллюстрация к статье: {title}" style="background-image: url(\'{image_url}\')"></div>'
            
        card_html = f"""\n            <a href="{article_filename}" class="article-card">{image_block}\n                <div class="article-card__content">\n                    <div class="article-card__date">{post_date}</div>\n                    <h2 class="article-card__title">{title}</h2>\n                    <p class="article-card__excerpt">{card_desc}</p>\n                    <div class="article-card__readmore">Читать статью →</div>\n                </div>\n            </a>"""
        all_cards.append((post_date, article_filename, card_html))
        
    current_files = {c[1] for c in all_cards}
    
    for post_file in existing_posts:
        basename = os.path.basename(post_file)
        if basename in current_files:
            continue
            
        cleaned = clean_fallback_from_existing_post(post_file)
        try:
            with open(post_file, 'r', encoding='utf-8') as f:
                post_html = f.read()
            soup_post = BeautifulSoup(post_html, 'html.parser')
            time_tag = soup_post.find('time', datetime=True)
            
            if time_tag:
                try:
                    dt = datetime.fromisoformat(time_tag['datetime'])
                    post_date = dt.strftime("%d.%m.%Y")
                except ValueError:
                    post_date = time_tag.get_text(strip=True) or "01.01.2020"
            else:
                post_date = "01.01.2020"
                
            h1 = soup_post.find('h1', class_='article-title')
            title = h1.get_text(strip=True) if h1 else "Без названия"
            excerpt = extract_excerpt_from_html(post_html)

            # Если для архивной статьи есть кэш AI SEO — используем умное описание
            match_post_id = re.search(r'post-(\w+)\.html', basename)
            if match_post_id:
                p_id = match_post_id.group(1)
                if p_id in seo_cache and seo_cache[p_id].get('meta_description'):
                    excerpt = seo_cache[p_id]['meta_description']
            
            if not excerpt:
                excerpt = "..."
                
            existing_image = extract_image_from_html(post_html)
            image_block = '<div class="article-card__image article-card__image--placeholder"></div>'
            if existing_image:
                image_block = f'\n                <div class="article-card__image" style="background-image: url(\'{existing_image}\')"></div>'
                
            card_html = f"""\n            <a href="{basename}" class="article-card">{image_block}\n                <div class="article-card__content">\n                    <div class="article-card__date">{post_date}</div>\n                    <h2 class="article-card__title">{title}</h2>\n                    <p class="article-card__excerpt">{excerpt}</p>\n                    <div class="article-card__readmore">Читать статью →</div>\n                </div>\n            </a>"""
            all_cards.append((post_date, basename, card_html))
            
        except Exception as e:
            pass
            
    all_cards.sort(key=lambda x: datetime.strptime(x[0], "%d.%m.%Y") if len(x[0]) == 10 else datetime.now(), reverse=True)
    total_posts = len(all_cards)
    total_pages = max(1, (total_posts + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE)
    
    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * POSTS_PER_PAGE
        end_idx = start_idx + POSTS_PER_PAGE
        page_cards = [c[2] for c in all_cards[start_idx:end_idx]]
        page_html = generate_blog_page(page_num, page_cards, total_pages, blog_template)
        page_file = os.path.join(BASE_DIR, "blog.html" if page_num == 1 else f"blog-{page_num}.html")
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(page_html)
            
    # --- НОВЫЙ БЛОК: Внедрение случайных статей ---
    print("Генерация блока 'Возможно, вас заинтересует' для всех статей...")
    for date_str, filename, card_html in all_cards:
        post_path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(post_path):
            continue
            
        try:
            with open(post_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
            if '{{RANDOM_POSTS}}' in html_content:
                # Выбираем 3 случайные карточки, исключая текущую статью
                other_cards = [c for c in all_cards if c[1] != filename]
                random_selection = random.sample(other_cards, min(3, len(other_cards)))
                
                random_html = ""
                for c in random_selection:
                    random_html += c[2] + "\n"
                    
                html_content = html_content.replace('{{RANDOM_POSTS}}', random_html)
                
                with open(post_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
        except Exception as e:
            print(f"  Ошибка при добавлении рекомендаций в {filename}: {e}")
    # ----------------------------------------------

    # --- AI SEO: Фоновое постепенное обогащение архивных постов (до 5 за запуск) ---
    if GEMINI_API_KEY:
        archive_enriched = 0
        consecutive_failures = 0
        for post_file in sorted(existing_posts, reverse=True):
            if archive_enriched >= 5 or consecutive_failures >= 3:
                if consecutive_failures >= 3:
                    print("  [AI SEO] Приостановка обогащения архива: 3 неудачных запроса подряд. Проверьте ключ или настройки API.")
                break
            basename = os.path.basename(post_file)
            match_post_id = re.search(r'post-(\w+)\.html', basename)
            if not match_post_id:
                continue
            p_id = match_post_id.group(1)
            if p_id not in seo_cache:
                try:
                    with open(post_file, 'r', encoding='utf-8') as f:
                        old_html = f.read()
                    soup_old = BeautifulSoup(old_html, 'html.parser')
                    h1_tag = soup_old.find('h1', class_='article-title')
                    old_title = h1_tag.get_text(strip=True) if h1_tag else "Без названия"
                    content_div = soup_old.find('div', class_='article-content')
                    old_text = content_div.get_text(separator=' ', strip=True) if content_div else ""
                    if len(old_text) > 40:
                        print(f"  [AI SEO] Обогащение архивной статьи {basename}...")
                        seo_data = get_seo_for_post(p_id, old_title, old_text, seo_cache)
                        if seo_data:
                            enrich_existing_post_html(post_file, seo_data)
                            archive_enriched += 1
                            consecutive_failures = 0
                            time.sleep(2)
                        else:
                            consecutive_failures += 1
                except Exception as err:
                    print(f"  [AI SEO] Ошибка обработки {basename}: {err}")
                    consecutive_failures += 1
    # -----------------------------------------------------
        
    all_post_files = [c[1] for c in all_cards]
    generate_sitemap(all_post_files, total_pages)
    print(f"Успех: Сборка успешно завершена!")

if __name__ == "__main__":
    main()