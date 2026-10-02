# Инструкция по оптимизации изображений

## Текущая ситуация
- photo.jpeg: 2.0MB (слишком большой!)
- photo.jpg: 473KB (нужно оптимизировать)

## Что нужно сделать

### Вариант 1: Онлайн сервисы (быстро)
1. Зайти на https://squoosh.app/
2. Загрузить photo.jpg
3. Выбрать WebP, качество 80%
4. Скачать как photo.webp
5. Загрузить в репозиторий

### Вариант 2: Локально через команду (если установлен ImageMagick)
```bash
# Конвертация в WebP
magick photo.jpg -quality 80 -resize 800x1000 photo.webp

# Или через cwebp (если установлен libwebp)
cwebp -q 80 photo.jpg -o photo.webp
```

### Вариант 3: Использовать встроенные инструменты Windows
1. Открыть photo.jpg в Paint
2. Изменить размер: 800x1000px (сейчас вероятно больше)
3. Сохранить как PNG с качеством 90%
4. Затем конвертировать через Squoosh.app в WebP

## Целевые размеры
- **Hero section**: 800x1000px, WebP, ~80-100KB
- **About section**: 600x750px, WebP, ~50-70KB
- **Thumbnail** (если нужно): 400x500px, WebP, ~30KB

## После оптимизации
Обновить HTML для использования WebP с fallback:
```html
<picture>
  <source srcset="photo.webp" type="image/webp">
  <img src="photo.jpg" alt="Наталья Баландина, психолог-консультант">
</picture>
```
