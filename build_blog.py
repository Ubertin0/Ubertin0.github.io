import os
import re
import glob
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- Конфигурация ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHANNEL_URL = "https://t.me/s/balandinatherapy"
TEMPLATE_FILE = os.path.join(BASE_DIR, "article-template.html")
BLOG_FILE = os.path.join(BASE_DIR, "blog.html")
POSTS_PER_PAGE = 15
# --------------------

def extract_image_url(msg) -> str | None:
    """Извлекает URL обложки из сообщения Telegram."""
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

    any_img = msg.find('img')
    if any_img:
        return any_img.get('src')

    return None

def clean_text_div(text_div) -> None:
    """Удаляем системный мусор Telegram, но сохраняем контентные изображения."""
    for tag in text_div.find_all(['i', 'svg', 'video']):
        tag.decompose()
    for img in text_div.find_all('img'):
        src = img.get('src', '')
        if 'emoji' in img.get('class', []) or '/emoji/' in src:
            img.decompose()

def strip_hashtags(text: str) -> str:
    """Удаляет хештеги вида #слово из текста."""
    return re.sub(r'#\w+', '', text)

def generate_sitemap(posts: list[str], total_pages: int) -> None:
    """Генерирует sitemap.xml со списком всех страниц."""
    pages = ['index.html', 'blog.html'] + [f'blog-{i}.html' for i in range(2, total_pages + 1)]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        sitemap += f'  <url><loc>https://balandinatherapy.ru/{page}</loc><priority>0.8</priority></url>\n'
    for post in posts:
        sitemap += f'  <url><loc>https://balandinatherapy.ru/{post}</loc><priority>0.6</priority></url>\n'
    sitemap += '</urlset>\n'
    with open(os.path.join(BASE_DIR, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(sitemap)
    print(f"Успех: sitemap.xml обновлён! ({len(posts)} постов, {len(pages)} страниц)")

def remove_image_from_article(article_html: str) -> str:
    """Удаляет hero-image, og:image и JSON-LD image из HTML статьи."""
    soup = BeautifulSoup(article_html, 'html.parser')
    hero = soup.find('div', class_='article-hero-image')
    if hero:
        hero.decompose()
    og_meta = soup.find('meta', property='og:image')
    if og_meta:
        og_meta.decompose()
    tw_meta = soup.find('meta', attrs={'name': 'twitter:image'})
    if tw_meta:
        tw_meta.decompose()
    html_str = str(soup)
    html_str = re.sub(r'"image":\s*"[^"]*",?\s*', '', html_str, count=1)
    return html_str

def generate_blog_page(page_num: int, cards: list[str], total_pages: int) -> str:
    """Генерирует HTML одной страницы блога с пагинацией."""
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        raw_template = f.read()
    template = re.sub(
        r'<div class="blog-pagination".*?</div>\s*',
        '',
        raw_template,
        flags=re.DOTALL
    )
    start_marker = "<!-- START ARTICLES -->"
    end_marker = "<!-- END ARTICLES -->"
    if start_marker not in template or end_marker not in template:
        raise ValueError("Маркеры не найдены в blog.html")
    parts1 = template.split(start_marker, 1)
    parts2 = parts1[1].split(end_marker, 1)
    cards_html = "\n".join(cards)
    pagination = '<div class="blog-pagination">'
    if page_num > 1:
        prev_page = "blog.html" if page_num == 2 else f"blog-{page_num - 1}.html"
        pagination += f'<a href="{prev_page}" class="btn btn--outline">← Назад</a>'
    for i in range(1, total_pages + 1):
        if i == page_num:
            pagination += f'<span>{i}</span>'
        else:
            page_file = "blog.html" if i == 1 else f"blog-{i}.html"
            pagination += f'<a href="{page_file}">{i}</a>'
    if page_num < total_pages:
        next_page = f"blog-{page_num + 1}.html"
        pagination += f'<a href="{next_page}" class="btn btn--outline">Вперёд →</a>'
    pagination += '</div>'
    page_title = ""
    if page_num > 1:
        page_title = f'<h2 style="text-align: center; margin-bottom: 2rem; font-family: var(--font-heading); color: var(--color-text-muted);">Страница {page_num}</h2>'
    content = (
        parts1[0]
        + start_marker + "\n"
        + page_title + cards_html + "\n            "
        + end_marker + "\n"
        + pagination + "\n"
        + parts2[1]
    )
    return content

def extract_excerpt_from_html(html: str) -> str:
    """Извлекает первые ~140 символов текста из HTML статьи."""
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
    """Извлекает URL изображения из уже сохранённой статьи."""
    soup = BeautifulSoup(html, 'html.parser')
    og = soup.find('meta', property='og:image')
    if og and og.get('content') and og['content'] != '{{IMAGE}}':
        return og['content']
    tw = soup.find('meta', attrs={'name': 'twitter:image'})
    if tw and tw.get('content') and tw['content'] != '{{IMAGE}}':
        return tw['content']
    hero = soup.find('div', class_='article-hero-image')
    if hero and hero.get('style'):
        match = re.search(r"background-image:url\('?(.*?)'?\)", hero['style'])
        if match and match.group(1) != '{{IMAGE}}':
            return match.group(1)
    article = soup.find('article') or soup.find('div', class_='article-content')
    if article:
        img = article.find('img')
        if img and img.get('src') and img['src'] != '{{IMAGE}}':
            return img['src']
    return None

def main() -> None:
    print("Запуск парсера Telegram-канала...")
    print(f"DEBUG: BASE_DIR = {BASE_DIR}")
    print(f"DEBUG: TEMPLATE_FILE = {TEMPLATE_FILE}")
    print(f"DEBUG: BLOG_FILE = {BLOG_FILE}")
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
        print(f"DEBUG: Проверьте, что файлы находятся в: {BASE_DIR}")
        return
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        template = f.read()
    existing_posts = set(glob.glob(os.path.join(BASE_DIR, 'post-*.html')))
    print(f"Найдено существующих постов: {len(existing_posts)}")
    new_posts_count = 0
    all_cards = []
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
            raw_text_full = text_div.get_text(separator=' ')
            sentences = raw_text_full.split('.')
            title = sentences[0].strip() if sentences else "Без названия"
            if len(title) > 150:
                title = title[:150] + "..."
        clean_text_div(text_div)
        image_url = extract_image_url(msg)
        post_link = msg.find('a', class_='tgme_widget_message_date')
        post_id = post_link['href'].split('/')[-1] if post_link else str(hash(text_div.get_text()))
        article_filename = f"post-{post_id}.html"
        article_path = os.path.join(BASE_DIR, article_filename)
        if article_path in existing_posts:
            print(f"  Пропуск (уже существует): {article_filename}")
        else:
            content_html = strip_hashtags(str(text_div))
            raw_text = strip_hashtags(text_div.get_text(separator=' '))
            excerpt = raw_text[:140].strip() + ("..." if len(raw_text) > 140 else "")
            article_html = template.replace('{{TITLE}}', title)\
                                   .replace('{{DATE}}', post_date)\
                                   .replace('{{DATE_ISO}}', post_date_iso)\
                                   .replace('{{POST_ID}}', post_id)\
                                   .replace('{{META_DESC}}', excerpt)\
                                   .replace('{{CONTENT}}', content_html)
            if image_url:
                article_html = article_html.replace('{{IMAGE}}', image_url)
            else:
                article_html = remove_image_from_article(article_html)
            with open(article_path, 'w', encoding='utf-8') as f:
                f.write(article_html)
            new_posts_count += 1
            print(f"  Создан: {article_filename}")
        image_block = ""
        if image_url:
            image_block = f'\n                <div class="article-card__image" style="background-image: url(\'{image_url}\')"></div>'
        card_html = f"""\n            <a href="{article_filename}" class="article-card">{image_block}\n                <div class="article-card__content">\n                    <div class="article-card__date">{post_date}</div>\n                    <h2 class="article-card__title">{title}</h2>\n                    <p class="article-card__excerpt">...</p>\n                    <div class="article-card__readmore">Читать статью →</div>\n                </div>\n            </a>"""
        all_cards.append((post_date, article_filename, card_html))
    current_files = {c[1] for c in all_cards}
    for post_file in existing_posts:
        basename = os.path.basename(post_file)
        if basename in current_files:
            continue
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
            if not excerpt:
                excerpt = "..."
            existing_image = extract_image_from_html(post_html)
            image_block = ""
            if existing_image:
                image_block = f'\n                <div class="article-card__image" style="background-image: url(\'{existing_image}\')"></div>'
            card_html = f"""\n            <a href="{basename}" class="article-card">{image_block}\n                <div class="article-card__content">\n                    <div class="article-card__date">{post_date}</div>\n                    <h2 class="article-card__title">{title}</h2>\n                    <p class="article-card__excerpt">{excerpt}</p>\n                    <div class="article-card__readmore">Читать статью →</div>\n                </div>\n            </a>"""
            all_cards.append((post_date, basename, card_html))
        except Exception as e:
            print(f"  Ошибка чтения {post_file}: {e}")
    all_cards.sort(key=lambda x: datetime.strptime(x[0], "%d.%m.%Y") if len(x[0]) == 10 else datetime.now(), reverse=True)
    total_posts = len(all_cards)
    total_pages = max(1, (total_posts + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE)
    print(f"Всего постов: {total_posts}, страниц: {total_pages}, новых: {new_posts_count}")
    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * POSTS_PER_PAGE
        end_idx = start_idx + POSTS_PER_PAGE
        page_cards = [c[2] for c in all_cards[start_idx:end_idx]]
        page_html = generate_blog_page(page_num, page_cards, total_pages)
        page_file = os.path.join(BASE_DIR, "blog.html" if page_num == 1 else f"blog-{page_num}.html")
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(page_html)
        print(f"  Сгенерирована: {os.path.basename(page_file)} ({len(page_cards)} карточек)")
    all_post_files = [c[1] for c in all_cards]
    generate_sitemap(all_post_files, total_pages)
    print(f"Успех: Обработано {total_posts} статей, создано {new_posts_count} новых!")

if __name__ == "__main__":
    main()
