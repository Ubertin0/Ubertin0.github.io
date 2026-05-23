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

def is_valid_image_url(url: str | None) -> bool:
    if not url or url.strip() in ('{{IMAGE}}', 'None', '', 'null'):
        return False
    if not url.strip().startswith('http'):
        return False
    return True

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

def strip_hashtags(text: str) -> str:
    return re.sub(r'#\w+', '', text)

def generate_sitemap(posts: list[str], total_pages: int) -> None:
    pages = ['index.html', 'blog.html'] + [f'blog-{i}.html' for i in range(2, total_pages + 1)]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        sitemap += f'  <url><loc>https://balandinatherapy.ru/{page}</loc><priority>0.8</priority></url>\n'
    for post in posts:
        sitemap += f'  <url><loc>https://balandinatherapy.ru/{post}</loc><priority>0.6</priority></url>\n'
    sitemap += '</urlset>\n'
    with open(os.path.join(BASE_DIR, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(sitemap)
    print(f"Успех: sitemap.xml обновлён! ({len(posts)} постов, {len(pages)} страниц)")

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
    """Безопасная генерация страницы (без регулярных выражений)."""
    parts1 = raw_template.split("", 1)
    if len(parts1) < 2:
        print("КРИТИЧЕСКАЯ ОШИБКА: Маркер не найден!")
        return raw_template
        
    parts2 = parts1[1].split("", 1)
    if len(parts2) < 2:
        print("КРИТИЧЕСКАЯ ОШИБКА: Маркер не найден!")
        return raw_template

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
        page_title = f'<h2 style="text-align: center; margin-bottom: 2rem; font-family: var(--font-heading); color: var(--color-text-muted);">Страница {page_num}</h2>\n'
        
    # Вставляем пагинацию ВНУТРЬ маркеров. Это решает проблему дублей навсегда.
    content = (
        parts1[0]
        + "\n"
        + page_title 
        + cards_html 
        + "\n" 
        + pagination 
        + "\n            "
        + parts2[1]
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
        
    # Читаем шаблон блога ОДИН РАЗ, до цикла!
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_template = f.read()
        
    existing_posts = set(glob.glob(os.path.join(BASE_DIR, 'post-*.html')))
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
        article_filename = f"post-{post_id}.html"
        article_path = os.path.join(BASE_DIR, article_filename)
        
        if article_path in existing_posts:
            pass
        else:
            content_html = strip_hashtags(str(text_div))
            raw_text = strip_hashtags(text_div.get_text(separator=' '))
            excerpt = raw_text[:140].strip() + ("..." if len(raw_text) > 140 else "")
            
            article_html = article_template.replace('{{TITLE}}', title)\
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
    
    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * POSTS_PER_PAGE
        end_idx = start_idx + POSTS_PER_PAGE
        page_cards = [c[2] for c in all_cards[start_idx:end_idx]]
        
        # Передаем blog_template, прочитанный из памяти!
        page_html = generate_blog_page(page_num, page_cards, total_pages, blog_template)
        
        page_file = os.path.join(BASE_DIR, "blog.html" if page_num == 1 else f"blog-{page_num}.html")
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(page_html)
        
    all_post_files = [c[1] for c in all_cards]
    generate_sitemap(all_post_files, total_pages)
    print(f"Успех: Сборка успешно завершена!")

if __name__ == "__main__":
    main()