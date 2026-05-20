import os
import re
import glob
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- Конфигурация ---
CHANNEL_URL = "https://t.me/s/balandinatherapy"
TEMPLATE_FILE = "article-template.html"
BLOG_FILE = "blog.html"
POSTS_PER_PAGE = 15
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

def strip_hashtags(text: str) -> str:
    """Удаляет хештеги вида #слово из текста."""
    return re.sub(r'#\w+', '', text)

def generate_sitemap(posts: list[str]) -> None:
    """Генерирует sitemap.xml со списком всех страниц."""
    pages = ['index.html', 'blog.html'] + [f'blog-{i}.html' for i in range(2, (len(posts) // POSTS_PER_PAGE) + 2)]

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        sitemap += f'  <url><loc>https://balandinatherapy.ru/{page}</loc><priority>0.8</priority></url>\n'
    for post in posts:
        sitemap += f'  <url><loc>https://balandinatherapy.ru/{post}</loc><priority>0.6</priority></url>\n'
    sitemap += '</urlset>\n'
    with open('sitemap.xml', 'w', encoding='utf-8') as f:
        f.write(sitemap)
    print(f"Успех: sitemap.xml обновлён! ({len(posts)} постов, {len(pages)} страниц)")

def generate_blog_page(page_num: int, cards: list[str], total_pages: int) -> str:
    """Генерирует HTML одной страницы блога с пагинацией."""

    # Читаем шаблон blog.html для структуры
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        template = f.read()

    start_marker = "<!-- START ARTICLES -->"
    end_marker = "<!-- END ARTICLES -->"

    if start_marker not in template or end_marker not in template:
        raise ValueError("Маркеры не найдены в blog.html")

    parts1 = template.split(start_marker, 1)
    parts2 = parts1[1].split(end_marker, 1)

    # Собираем карточки
    cards_html = "\n".join(cards)

    # Пагинация
    pagination = '<div class="blog-pagination" style="display: flex; justify-content: center; gap: 0.5rem; margin-top: 3rem; flex-wrap: wrap;">'

    if page_num > 1:
        prev_page = "blog.html" if page_num == 2 else f"blog-{page_num - 1}.html"
        pagination += f'<a href="{prev_page}" class="btn btn--outline" style="font-size: 0.8rem;">← Назад</a>'

    for i in range(1, total_pages + 1):
        if i == page_num:
            pagination += f'<span style="padding: 0.5rem 1rem; background: var(--color-accent); color: white; border-radius: 100px; font-size: 0.8rem;">{i}</span>'
        else:
            page_file = "blog.html" if i == 1 else f"blog-{i}.html"
            pagination += f'<a href="{page_file}" style="padding: 0.5rem 1rem; text-decoration: none; color: var(--color-text); font-size: 0.8rem; border-radius: 100px; border: 1px solid var(--color-bg-dark);">{i}</a>'

    if page_num < total_pages:
        next_page = f"blog-{page_num + 1}.html"
        pagination += f'<a href="{next_page}" class="btn btn--outline" style="font-size: 0.8rem;">Вперёд →</a>'

    pagination += '</div>'

    # Заголовок страницы (для blog-2, blog-3 и т.д.)
    page_title = ""
    if page_num > 1:
        page_title = f'<h2 style="text-align: center; margin-bottom: 2rem; font-family: var(--font-heading); color: var(--color-text-muted);">Страница {page_num}</h2>'

    content = (
        parts1[0]
        + start_marker + "\n"
        + page_title + cards_html + "\n            "
        + end_marker
        + pagination + "\n"
        + parts2[1]
    )

    return content

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
    messages = soup.find_all('div', class_='tgme_widget_message_wrap', limit=100)  # Парсим больше для накопления

    if not messages:
        print("Внимание: В Telegram-канале не найдено сообщений.")
        return

    if not os.path.exists(TEMPLATE_FILE) or not os.path.exists(BLOG_FILE):
        print("Ошибка: Не найден article-template.html или blog.html!")
        return

    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        template = f.read()

    # --- НАКОПЛЕНИЕ: собираем существующие посты ---
    existing_posts = set(glob.glob('post-*.html'))
    print(f"Найдено существующих постов: {len(existing_posts)}")

    new_posts_count = 0
    all_cards = []  # Все карточки для пагинации

    for msg in messages:
        text_div = msg.find('div', class_='tgme_widget_message_text')
        if not text_div:
            continue

        # --- ДАТА ---
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
        article_filename = f"post-{post_id}.html"

        # --- НАКОПЛЕНИЕ: пропускаем существующие ---
        if article_filename in existing_posts:
            print(f"  Пропуск (уже существует): {article_filename}")
        else:
            # --- УДАЛЯЕМ ХЕШТЕГИ ---
            content_html = strip_hashtags(str(text_div))
            raw_text = strip_hashtags(text_div.get_text(separator=' '))
            excerpt = raw_text[:140].strip() + ("..." if len(raw_text) > 140 else "")

            # --- Генерация HTML статьи ---
            article_html = template.replace('{{TITLE}}', title)\
                                   .replace('{{DATE}}', post_date)\
                                   .replace('{{DATE_ISO}}', post_date_iso)\
                                   .replace('{{POST_ID}}', post_id)\
                                   .replace('{{META_DESC}}', excerpt)\
                                   .replace('{{CONTENT}}', content_html)

            # --- ИЗОБРАЖЕНИЕ ---
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
                    article_html = re.sub(
                        r'<meta property="og:image" content="{{IMAGE}}">\n',
                        '',
                        article_html,
                        count=1
                    )
                    article_html = re.sub(
                        r'"image": "{{IMAGE}}",\n',
                        '',
                        article_html,
                        count=1
                    )

            with open(article_filename, 'w', encoding='utf-8') as f:
                f.write(article_html)

            new_posts_count += 1
            print(f"  Создан: {article_filename}")

        # --- Карточка (всегда добавляем в список для пагинации) ---
        image_block = ""
        if image_url:
            image_block = f'\n                <div class="article-card__image" style="background-image: url(\'{image_url}\')"></div>'

        card_html = f'''
            <a href="{article_filename}" class="article-card">{image_block}
                <div class="article-card__content">
                    <div class="article-card__date">{post_date}</div>
                    <h2 class="article-card__title">{title}</h2>
                    <p class="article-card__excerpt">{excerpt if not article_filename in existing_posts else "..."}</p>
                    <div class="article-card__readmore">Читать статью →</div>
                </div>
            </a>'''
        all_cards.append((post_date, article_filename, card_html))

    # --- СОРТИРОВКА: новые сверху ---
    # Собираем карточки из ВСЕХ существующих постов (не только из Telegram)
    for post_file in existing_posts:
        if post_file not in [c[1] for c in all_cards]:
            # Извлекаем дату из HTML файла для сортировки
            try:
                with open(post_file, 'r', encoding='utf-8') as f:
                    post_html = f.read()
                date_match = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})"[^>]*>(.*?)</time>', post_html)
                if date_match:
                    post_date = date_match.group(2)
                    post_date_iso = date_match.group(1)
                else:
                    post_date = "01.01.2020"
                    post_date_iso = "2020-01-01"

                title_match = re.search(r'<h1[^>]*class="article-title"[^>]*>(.*?)</h1>', post_html)
                title = title_match.group(1) if title_match else "Без названия"

                # Простая карточка без изображения (уже существующий пост)
                card_html = f'''
            <a href="{post_file}" class="article-card">
                <div class="article-card__content">
                    <div class="article-card__date">{post_date}</div>
                    <h2 class="article-card__title">{title}</h2>
                    <p class="article-card__excerpt">Ранее опубликованная статья...</p>
                    <div class="article-card__readmore">Читать статью →</div>
                </div>
            </a>'''
                all_cards.append((post_date, post_file, card_html))
            except Exception as e:
                print(f"  Ошибка чтения {post_file}: {e}")

    # Сортируем по дате (новые сверху)
    all_cards.sort(key=lambda x: datetime.strptime(x[0], "%d.%m.%Y") if len(x[0]) == 10 else datetime.now(), reverse=True)

    total_posts = len(all_cards)
    total_pages = max(1, (total_posts + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE)

    print(f"Всего постов: {total_posts}, страниц: {total_pages}, новых: {new_posts_count}")

    # --- ГЕНЕРАЦИЯ СТРАНИЦ БЛОГА ---
    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * POSTS_PER_PAGE
        end_idx = start_idx + POSTS_PER_PAGE
        page_cards = [c[2] for c in all_cards[start_idx:end_idx]]

        page_html = generate_blog_page(page_num, page_cards, total_pages)

        page_file = "blog.html" if page_num == 1 else f"blog-{page_num}.html"
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(page_html)
        print(f"  Сгенерирована: {page_file} ({len(page_cards)} карточек)")

    # --- Генерация sitemap.xml ---
    all_post_files = [c[1] for c in all_cards]
    generate_sitemap(all_post_files)

    print(f"Успех: Обработано {total_posts} статей, создано {new_posts_count} новых!")

if __name__ == "__main__":
    main()
