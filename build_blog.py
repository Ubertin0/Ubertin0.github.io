import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- Конфигурация ---
CHANNEL_URL = "https://t.me/s/balandinatherapy"
TEMPLATE_FILE = "article-template.html"
BLOG_FILE = "blog.html"
MAX_POSTS = 15
# --------------------

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

    if not os.path.exists(TEMPLATE_FILE) or not os.path.exists(BLOG_FILE):
        print("Ошибка: Не найден article-template.html или blog.html!")
        return

    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        template = f.read()

    cards_html = ""

    for msg in messages:
        text_div = msg.find('div', class_='tgme_widget_message_text')
        if not text_div:
            continue
            
        # БРОНЯ: Удаляем все системные иконки, видео, картинки и кастомные эмодзи Телеграма
        for media in text_div.find_all(['img', 'video', 'svg', 'i']):
            media.decompose()
            
        time_tag = msg.find('time')
        post_date = time_tag.text if time_tag else datetime.now().strftime("%d.%m.%Y")
        
        post_link = msg.find('a', class_='tgme_widget_message_date')
        post_id = post_link['href'].split('/')[-1] if post_link else str(hash(text_div.text))
        
        # Лимитируем длину HTML на всякий случай
        content_html = str(text_div)[:50000]
        raw_text = text_div.get_text(separator=' ')
        
        sentences = raw_text.split('.')
        title = sentences[0][:70].strip() + ("..." if len(sentences[0]) > 70 else "")
        excerpt = raw_text[:140].strip() + ("..." if len(raw_text) > 140 else "")
        
        article_html = template.replace('{{TITLE}}', title)\
                               .replace('{{DATE}}', post_date)\
                               .replace('{{META_DESC}}', excerpt)\
                               .replace('{{CONTENT}}', content_html)
                               
        article_filename = f"post-{post_id}.html"
        
        with open(article_filename, 'w', encoding='utf-8') as f:
            f.write(article_html)
            
        cards_html += f'''
            <a href="{article_filename}" class="article-card">
                <div class="article-card__content">
                    <div class="article-card__date">{post_date}</div>
                    <h2 class="article-card__title">{title}</h2>
                    <p class="article-card__excerpt">{excerpt}</p>
                    <div class="article-card__readmore">Читать статью →</div>
                </div>
            </a>'''

    # Безопасная замена без использования regex
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_content = f.read()
        
    start_marker = ""
    end_marker = ""
    
    if start_marker in blog_content and end_marker in blog_content:
        parts1 = blog_content.split(start_marker, 1)
        parts2 = parts1[1].split(end_marker, 1)
        
        updated_blog = parts1[0] + start_marker + "\n" + cards_html + "\n            " + end_marker + parts2[1]
        
        # Предохранитель от раздувания файла
        if len(updated_blog) > 5000000:
            print("КРИТИЧЕСКАЯ ОШИБКА: Файл blog.html превысил 5МБ. Отмена записи.")
            return
            
        with open(BLOG_FILE, 'w', encoding='utf-8') as f:
            f.write(updated_blog)
        print("Успех: Статьи сгенерированы, блог обновлен!")
    else:
        print("Ошибка: Метки для вставки карточек не найдены в blog.html!")

if __name__ == "__main__":
    main()
