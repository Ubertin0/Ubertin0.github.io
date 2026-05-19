import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- Конфигурация ---
CHANNEL_URL = "https://t.me/s/balandinatherapy" # Публичная ссылка на канал
TEMPLATE_FILE = "article-template.html"
BLOG_FILE = "blog.html"
MAX_POSTS = 15  # Сколько последних постов проверяем за один раз
# --------------------

def main() -> None:
    print("Запуск парсера Telegram-канала...")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(CHANNEL_URL, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Ошибка сети: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_wrap', limit=MAX_POSTS)

    if not os.path.exists(TEMPLATE_FILE) or not os.path.exists(BLOG_FILE):
        print("Ошибка: Не найден article-template.html или blog.html!")
        return

    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        template = f.read()

    cards_html = ""

    for msg in messages:
        text_div = msg.find('div', class_='tgme_widget_message_text')
        if not text_div:
            continue # Пропускаем посты без текста (например, просто фото)
            
        time_tag = msg.find('time')
        post_date = time_tag.text if time_tag else datetime.now().strftime("%d.%m.%Y")
        
        # Берем ID поста для красивой ссылки (например: post-142.html)
        post_link = msg.find('a', class_='tgme_widget_message_date')
        post_id = post_link['href'].split('/')[-1] if post_link else str(hash(text_div.text))
        
        content_html = str(text_div)
        raw_text = text_div.get_text(separator=' ')
        
        # Автоматически генерируем заголовок (первое предложение) и описание для SEO
        sentences = raw_text.split('.')
        title = sentences[0][:70] + ("..." if len(sentences[0]) > 70 else "")
        excerpt = raw_text[:140] + ("..." if len(raw_text) > 140 else "")
        
        # Подставляем данные в шаблон
        article_html = template.replace('{{TITLE}}', title)\
                               .replace('{{DATE}}', post_date)\
                               .replace('{{META_DESC}}', excerpt)\
                               .replace('{{CONTENT}}', content_html)
                               
        article_filename = f"post-{post_id}.html"
        
        # Сохраняем готовую статью
        with open(article_filename, 'w', encoding='utf-8') as f:
            f.write(article_html)
            
        # Готовим карточку для главной страницы блога
        cards_html += f'''
            <a href="{article_filename}" class="article-card">
                <div class="article-card__content">
                    <div class="article-card__date">{post_date}</div>
                    <h2 class="article-card__title">{title}</h2>
                    <p class="article-card__excerpt">{excerpt}</p>
                    <div class="article-card__readmore">Читать статью →</div>
                </div>
            </a>'''

    # Вставляем карточки в blog.html
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_content = f.read()
        
    pattern = re.compile(r'.*?', re.DOTALL)
    replacement = f'\n{cards_html}\n            '
    
    updated_blog = pattern.sub(replacement, blog_content)
    
    with open(BLOG_FILE, 'w', encoding='utf-8') as f:
        f.write(updated_blog)
        
    print("Успех: Статьи сгенерированы, блог обновлен!")

if __name__ == "__main__":
    main()