# Верификация Google Search Console для balandinatherapy.ru

## Проблема
Google Search Console не находит верификационный токен в DNS TXT записях, потому что:
- **Мы добавили:** HTML meta-тег (это работает!)
- **Google ищет:** DNS TXT запись (вы выбрали неправильный метод верификации)

## ✅ Решение 1: Использовать HTML meta-тег (уже добавлен)

### Шаги в Google Search Console:

1. Откройте https://search.google.com/search-console/
2. Выберите ваш сайт `balandinatherapy.ru`
3. Перейдите в **Settings** (Настройки) → **Ownership verification** (Подтверждение прав)
4. Нажмите **Verify** (Подтвердить)
5. Выберите метод: **HTML tag** (HTML-тег)
6. Google покажет тег вида:
   ```html
   <meta name="google-site-verification" content="MAnfw5ZSvj67NOD2Ppsb7CFIjR3wfPdfwjQoCdZPiZg" />
   ```
7. ✅ **Этот тег уже добавлен на сайт!**
8. Нажмите **Verify** (Подтвердить)

**Готово!** Верификация пройдёт успешно.

---

## 🔧 Решение 2: Добавить DNS TXT запись (если хотите использовать DNS метод)

Если вы всё же хотите использовать DNS-верификацию, нужно добавить TXT запись в настройках вашего регистратора домена.

### Где домен зарегистрирован?
Проверьте на https://www.nic.ru/whois/?searchWord=balandinatherapy.ru

### Инструкция (общая):

1. Войдите в панель управления вашего регистратора домена (Reg.ru, Timeweb, REG.RU и т.д.)
2. Найдите раздел **DNS настройки** или **DNS записи**
3. Добавьте **TXT запись**:
   - **Имя/Host:** `@` или `balandinatherapy.ru` (или оставьте пустым)
   - **Тип:** `TXT`
   - **Значение/Value:** `google-site-verification=MAnfw5ZSvj67NOD2Ppsb7CFIjR3wfPdfwjQoCdZPiZg`
   - **TTL:** 3600 (или оставьте по умолчанию)
4. Сохраните
5. **Подождите 1-24 часа** (DNS изменения распространяются не мгновенно)
6. Вернитесь в Google Search Console и нажмите **Verify**

### Примеры для популярных регистраторов:

#### Reg.ru:
1. Личный кабинет → Домены → balandinatherapy.ru
2. DNS-серверы и зона → Добавить запись
3. Тип: TXT, Хост: @, Значение: `google-site-verification=MAnfw5ZSvj67NOD2Ppsb7CFIjR3wfPdfwjQoCdZPiZg`

#### Cloudflare:
1. Dashboard → Domain → DNS → Add record
2. Type: TXT, Name: @, Content: `google-site-verification=MAnfw5ZSvj67NOD2Ppsb7CFIjR3wfPdfwjQoCdZPiZg`

#### REG.RU:
1. Список услуг → Домены → balandinatherapy.ru → Управление зоной
2. Добавить запись → TXT
3. Поддомен: @ или пусто
4. Значение: `google-site-verification=MAnfw5ZSvj67NOD2Ppsb7CFIjR3wfPdfwjQoCdZPiZg`

---

## ⚡ Быстрое решение (рекомендую)

**Используйте HTML meta-тег метод** (Решение 1):
- ✅ Уже добавлен на сайт
- ✅ Работает сразу
- ✅ Не требует доступа к DNS

Просто выберите **HTML tag** метод в Google Search Console вместо **DNS TXT record**.

---

## 🔍 Проверка после добавления DNS записи

После добавления DNS TXT записи проверьте её появление:

### Онлайн-инструменты:
- https://mxtoolbox.com/TXTLookup.aspx
- https://toolbox.googleapps.com/apps/dig/#TXT/balandinatherapy.ru

### Через командную строку:
```bash
nslookup -type=TXT balandinatherapy.ru
# или
dig TXT balandinatherapy.ru
```

Должна появиться строка:
```
google-site-verification=MAnfw5ZSvj67NOD2Ppsb7CFIjR3wfPdfwjQoCdZPiZg
```

---

## 📋 Итог

**Самый простой способ:**
1. Откройте Google Search Console
2. Выберите метод верификации **HTML tag** (не DNS)
3. Нажмите Verify

Meta-тег уже на сайте — верификация пройдёт мгновенно! ✅
