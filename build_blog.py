import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- Конфигурация ---
CHANNEL_URL = "https://t.me/s/balandinatherapy"
TEMPLATE_FILE = "article-template.html"
BLOG_FILE = "blog.html"
MAX_POSTS = 15
# --------------------

def extract_image_url(msg) -> str | None:
    """Извлекает URL обложки из фото-блока Telegram."""
    photo_wrap = msg.find('a', class_='tgme_widget_message_photo_wrap')
    if photo_wrap:
        style = photo_wrap.get('style', '')
        match = re.search(r"background-image:url\('?(.*?)'?\)", style)
        if match:
            return match.group(1)
    text_div = msg.find('div', class_='tgme_widget_message_text')
    if text_div:
        img = text_div.find('img')
        if img:
            return img.get('src')
    return None

def clean_text_div(text_div) -> None:
    """Удаляем системный мусор Telegram, но сохраняем контентные изображения."""
    for tag in text_div.find_all(['i', 'svg', 'video']):
        tag.decompose()
    for img in text_div.find_all('img'):
        src = img.get('src', '')
        if 'emoji' in img.get('class', []) or '/emoji/' in src:
            img.decompose()

def generate_sitemap(posts: list[str]) -> None:
    """Генерирует sitemap.xml со списком всех страниц."""
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '  <url><loc>https://balandinatherapy.ru/</loc><priority>1.0</priority></url>\n'
    sitemap += '  <url><loc>https://balandinatherapy.ru/blog.html</loc><priority>0.8</priority></url>\n'
    for post in posts:
        sitemap += f'  <url><loc>https://balandinatherapy.ru/{post}</loc><priority>0.6</priority></url>\n'
    sitemap += '</urlset>\n'
    with open('sitemap.xml', 'w', encoding='utf-8') as f:
        f.write(sitemap)
    print("Успех: sitemap.xml обновлён!")

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
    messages = soup.find_all('div', class_='tgme_widget_message_wrap', limit=MAX_POSTS)

    if not messages:
        print("Внимание: В Telegram-канале не найдено сообщений. Блог не будет обновлён.")
        return

    if not os.path.exists(TEMPLATE_FILE) or not os.path.exists(BLOG_FILE):
        print("Ошибка: Не найден article-template.html или blog.html!")
        return

    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        template = f.read()

    cards_html = ""
    posts = []

    for msg in messages:
        text_div = msg.find('div', class_='tgme_widget_message_text')
        if not text_div:
            continue

        # --- ДАТА: оба формата ---
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

        # --- ЗАГОЛОВОК ---
        bold_tag = text_div.find(['b', 'strong'])
        if bold_tag:
            title = bold_tag.get_text(strip=True)
            bold_tag.decompose()
        else:
            raw_text_full = text_div.get_text(separator=' ')
            sentences = raw_text_full.split('.')
            title = sentences[0].strip() if sentences else "Без названия"
            if len(title) > 150:
                title = title[:150] + "..."

        # --- ОЧИСТКА ---
        clean_text_div(text_div)

        # --- ИЗОБРАЖЕНИЯ ---
        image_url = extract_image_url(msg)

        post_link = msg.find('a', class_='tgme_widget_message_date')
        post_id = post_link['href'].split('/')[-1] if post_link else str(hash(text_div.get_text()))

        content_html = str(text_div)
        raw_text = text_div.get_text(separator=' ')

        excerpt = raw_text[:140].strip() + ("..." if len(raw_text) > 140 else "")

        # --- Генерация HTML статьи ---
        article_html = template.replace('{{TITLE}}', title)\
                               .replace('{{DATE}}', post_date)\
                               .replace('{{DATE_ISO}}', post_date_iso)\
                               .replace('{{POST_ID}}', post_id)\
                               .replace('{{META_DESC}}', excerpt)\
                               .replace('{{CONTENT}}', content_html)

        # --- ИЗОБРАЖЕНИЕ: подставляем URL или удаляем блок целиком ---
        if '{{IMAGE}}' in template:
            if image_url:
                article_html = article_html.replace('{{IMAGE}}', image_url)
            else:
                article_html = re.sub(
                    r'<div[^>]*class="article-hero-image"[^>]*>.*?</div>\s*',
                    '',
                    article_html,
                    count=1,
                    flags=re.DOTALL
                )
                # Удаляем og:image если нет фото
                article_html = re.sub(
                    r'<meta property="og:image" content="{{IMAGE}}">\n',
                    '',
                    article_html,
                    count=1
                )
                # Удаляем image из JSON-LD если нет фото
                article_html = re.sub(
                    r'"image": "{{IMAGE}}",\n',
                    '',
                    article_html,
                    count=1
                )

        article_filename = f"post-{post_id}.html"
        posts.append(article_filename)

        with open(article_filename, 'w', encoding='utf-8') as f:
            f.write(article_html)

        # --- Карточка для blog.html ---
        image_block = ""
        if image_url:
            image_block = f'\n                <div class="article-card__image" style="background-image: url(\'{image_url}\')"></div>'

        cards_html += f'''
            <a href="{article_filename}" class="article-card">{image_block}
                <div class="article-card__content">
                    <div class="article-card__date">{post_date}</div>
                    <h2 class="article-card__title">{title}</h2>
                    <p class="article-card__excerpt">{excerpt}</p>
                    <div class="article-card__readmore">Читать статью →</div>
                </div>
            </a>'''

    if not cards_html.strip():
        print("Внимание: Не удалось сгенерировать ни одной карточки.")
        return

    # --- Вставка в blog.html ---
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_content = f.read()

    start_marker = "<!-- START ARTICLES -->"
    end_marker = "<!-- END ARTICLES -->"

    if start_marker not in blog_content or end_marker not in blog_content:
        print(f"Ошибка: Метки {start_marker} / {end_marker} не найдены в blog.html!")
        return

    parts1 = blog_content.split(start_marker, 1)
    parts2 = parts1[1].split(end_marker, 1)

    updated_blog = (
        parts1[0]
        + start_marker + "\n"
        + cards_html + "\n            "
        + end_marker
        + parts2[1]
    )

    if len(updated_blog) > 5000000:
        print("КРИТИЧЕСКАЯ ОШИБКА: Файл blog.html превысил 5МБ. Отмена записи.")
        return

    with open(BLOG_FILE, 'w', encoding='utf-8') as f:
        f.write(updated_blog)

    # --- Генерация sitemap.xml ---
    generate_sitemap(posts)

    print(f"Успех: Сгенерировано {len(messages)} статей, блог и sitemap обновлены!")

if __name__ == "__main__":
    main()
