# Email → Telegram Bot (IMAP)

Telegram-бот, который пересылает новые письма в Telegram. Работает по чистому
IMAP — подходит для почты с любым доменом (Gmail, Mail.ru, Yandex, корпоративная
почта и т.д.), не только Gmail. Поддерживает несколько пользователей одновременно:
каждый подключает свой ящик через веб-форму и получает письма в свой чат с ботом.

## Архитектура

```
main.py            — точка входа бота: Bot + Dispatcher + мультипользовательский mail_loop
bot/
  handlers.py      — /start с inline-кнопкой "Подключить почту"
  mail_loop.py     — опрос IMAP всех пользователей из БД, отправка писем в Telegram
auth/
  credentials.py   — абстракция способа авторизации (Credentials / PasswordCredentials)
  crypto.py        — шифрование пароля (Fernet)
imap/
  service.py       — подключение и логин на IMAP-сервере (aioimaplib)
  fetch.py         — получение новых писем по UID
  adapter.py       — приведение email.message к dict для format_msg
database/
  models.py        — модель User (SQLAlchemy)
  db.py            — async-движок/сессии (SQLite локально, PostgreSQL в проде)
  crud.py          — операции с пользователями
alembic/           — миграции БД
web/
  app.py           — FastAPI-приложение
  routes.py        — форма подключения IMAP (/connect)
  templates/       — HTML-шаблоны формы
message/
  parser.py, cleaner.py, formater.py — разбор и форматирование письма для Telegram
```

### Как это работает

1. Пользователь пишет боту `/start` → получает inline-кнопку "🔗 Подключить почту"
   со ссылкой вида `https://<домен>/connect?telegram_id=<id>` (пароль никогда не
   передаётся в URL).
2. На веб-странице вводит IMAP-сервер (подбирается автоматически по домену почты,
   можно поправить руками), email и пароль.
3. Сервер делает тестовый IMAP-логин; при успехе шифрует пароль и сохраняет
   пользователя в БД, бот присылает подтверждение в чат.
4. `mail_loop` каждые несколько секунд обходит всех пользователей из БД,
   подключается к их IMAP, забирает новые письма (по UID, с дедупликацией и
   пропуском писем самому себе) и пересылает их в чат пользователя в исходном
   Telegram-формате (эмодзи-шаблон в `message/formater.py` не менялся).

### Точка расширения: OAuth

Способ авторизации спроектирован как абстракция (`auth/credentials.py`):
IMAP-движок (`imap/service.py`) ничего не знает о паролях — он вызывает
`await credentials.login(client)`. Сейчас есть только `PasswordCredentials`.
Когда понадобится OAuth для Gmail/Mail.ru (SASL XOAUTH2), достаточно будет:

- добавить класс `OAuthCredentials` (заготовка с примером уже есть в файле, закомментирована);
- научить `database/crud.build_credentials` собирать его при `auth_method == "oauth"`
  (поле `auth_method` уже есть в таблице `users`).

Менять `imap/`, `bot/mail_loop.py` и остальной код не придётся.

## Настройка `.env`

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

| Переменная     | Назначение                                                                 |
|----------------|----------------------------------------------------------------------------|
| `TOKEN`        | Токен бота от [@BotFather](https://t.me/BotFather)                        |
| `DATABASE_URL` | Строка подключения к БД (см. ниже — разная для локали и прода)            |
| `FERNET_KEY`   | Ключ шифрования паролей пользователей                                      |
| `WEB_BASE_URL` | Публичный HTTPS-адрес веб-формы, **без слэша на конце**                   |

Сгенерировать `FERNET_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

⚠️ Если поменять `FERNET_KEY` на проде, расшифровать уже сохранённые пароли
будет невозможно — пользователям придётся переподключать почту.

Старые переменные `CHAT_ID` и `THREAD_ID` из однопользовательской версии бота
больше не используются — каждый пользователь получает письма в свой личный чат.

## Локальный запуск (SQLite)

Для разработки достаточно SQLite — поднимать PostgreSQL не нужно.

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

В `.env`:

```
DATABASE_URL=sqlite+aiosqlite:///./local.db
```

Применить миграции (создаст файл `local.db` со схемой из `alembic/versions/`):

```bash
alembic upgrade head
```

### HTTPS-форма локально — через ngrok

Веб-форма обязана открываться по HTTPS (иначе Telegram не даст использовать
ссылку как нормальную, да и пароль нельзя слать по HTTP). Для локальных тестов
проще всего поднять туннель через [ngrok](https://ngrok.com/):

```bash
ngrok http 8000
```

Скопируйте выданный адрес (вида `https://xxxx.ngrok-free.app`) в `.env`:

```
WEB_BASE_URL=https://xxxx.ngrok-free.app
```

Запустите оба процесса (в разных терминалах):

```bash
python main.py                                  # бот + опрос почты
uvicorn web.app:app --host 0.0.0.0 --port 8000  # веб-форма
```

Откройте бота в Telegram, нажмите `/start` → "🔗 Подключить почту".

## Прод (Docker Compose: bot + web + PostgreSQL)

В `.env`:

```
DATABASE_URL=postgresql+asyncpg://email_bot:email_bot@db:5432/email_bot
WEB_BASE_URL=https://your-domain.com
```

Поднять всё разом:

```bash
docker compose up -d --build
```

Применить миграции (один раз при первом разворачивании и после каждого
обновления, добавляющего новые ревизии в `alembic/versions/`):

```bash
docker compose run --rm web alembic upgrade head
```

`docker-compose.yml` поднимает три сервиса:
- `db` — PostgreSQL с volume для данных;
- `bot` — `python main.py` (Telegram-бот + опрос почты);
- `web` — `uvicorn web.app:app` на порту `8000` (форма подключения).

### SSL и домен

Сервис `web` сам по себе отдаёт обычный HTTP на порту 8000 — TLS нужно
терминировать снаружи. Проще всего поставить перед ним реверс-прокси с
автоматическим HTTPS:

- **Caddy** — достаточно `Caddyfile` вида:
  ```
  your-domain.com {
      reverse_proxy web:8000
  }
  ```
  и Caddy сам выпустит и обновит сертификат Let's Encrypt;
- либо ваш существующий nginx + certbot, если он уже настроен для других проектов.

После настройки укажите итоговый публичный адрес в `WEB_BASE_URL` — именно он
попадёт в кнопку бота.

## Миграции Alembic

Если меняете модели в `database/models.py`, создавайте новую миграцию:

```bash
alembic revision --autogenerate -m "описание изменения"
alembic upgrade head
```

`alembic/env.py` берёт `DATABASE_URL` из `.env` — один и тот же конфиг работает
и с локальным SQLite, и с продовым PostgreSQL.

## Что нужно сделать вручную

- [ ] Завести бота у @BotFather, получить `TOKEN`
- [ ] Сгенерировать и сохранить `FERNET_KEY` (без него нельзя расшифровать пароли!)
- [ ] Локально: поднять `ngrok http 8000`, прописать выданный адрес в `WEB_BASE_URL`
- [ ] В проде: завести домен, настроить SSL (Caddy/nginx+certbot), прописать домен в `WEB_BASE_URL`
- [ ] Применить миграции (`alembic upgrade head` локально или через `docker compose run --rm web alembic upgrade head`)
- [ ] Убедиться, что `.env` не попадает в git (уже добавлен в `.gitignore`)
