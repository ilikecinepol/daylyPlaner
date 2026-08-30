# daylyPlaner

FastAPI-приложение для задач, календаря, Kanban, проектов, команд, шаблонов и напоминаний. Одна `Task` используется календарём и Kanban; импортированные внешние события хранятся отдельно.

Шаблоны выбираются внизу формы задачи и сохраняют полный набор заполненных полей карточки. Отдельный раздел шаблонов в навигации не используется.

Участники проекта могут взять свободную задачу кнопкой «Назначить себе». Владелец и администраторы проекта получают постоянное уведомление в ленте; повторное нажатие не создаёт дубликаты.

## Требования и запуск

- Python 3.12+
- SQLite для разработки или PostgreSQL 16+
- Node.js для проверки синтаксиса frontend

```powershell
python -m pip install -r backend/requirements.txt
Copy-Item .env.example .env
$env:PYTHONPATH='backend'
alembic upgrade head
python run.py
```

Приложение доступно на `http://127.0.0.1:8000`, OpenAPI — `/api/docs`. Первый пользователь создаётся через регистрацию; реальные базы и demo credentials в Git не хранятся. PostgreSQL-вариант запускается через `docker compose up --build` после замены секретов.

После входа браузер подключается к `GET /api/v1/events` через Server-Sent Events. Изменения задач, Kanban, проектов, сообщений, контактов и уведомлений появляются в открытом приложении автоматически; ручное обновление страницы не требуется.

## Конфигурация

См. `.env.example`. Основные переменные: `APP_ENV`, `SECRET_KEY`, `DATABASE_URL`, `COOKIE_SECURE`, `ALLOWED_ORIGINS`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`. При `APP_ENV=production` приложение не запускается без `SECRET_KEY`, а cookie автоматически получает `Secure`. Auth cookie имеет `HttpOnly`, `SameSite=Lax` и срок 7 дней. OAuth callback проверяет подписанный и ограниченный по времени `state`; cross-origin изменяющие запросы отклоняются, кроме явно разрешённых origins.

## Миграции

```powershell
$env:PYTHONPATH='backend'
alembic upgrade head
alembic revision -m "describe change"
```

`0003` сначала переносит legacy-данные, затем удаляет конфликтующие поля Task. Не обновляйте production-схему через `create_all`.

## Google Calendar

Создайте OAuth Web Client, разрешите Calendar Events scope и добавьте redirect URI из конфигурации. `POST /api/v1/google/sync` выполняет pull перед push, сравнивает timestamps, обновляет истёкший access token один раз, синхронизирует удаления только для связанных событий daylyPlaner и хранит чужие события как `ExternalCalendarEvent`. Отозванный refresh token переводит подключение в `reauthorization_required`.

## Render deployment

Репозиторий содержит `render.yaml`: Blueprint создаёт Docker web service и managed PostgreSQL, генерирует production secret, запускает Alembic перед приложением и проверяет `/api/v1/health`. В Render выберите **New → Blueprint**, подключите GitHub-репозиторий `ilikecinepol/daylyPlaner` и примените Blueprint. После получения публичного URL добавьте Google OAuth variables и используйте `https://<ваш-домен>/api/v1/google/callback` как redirect URI.

## Напоминания

`GET /api/v1/notifications` выдаёт наступившие in-app reminders и ставит `sent_at`, поэтому повторная выдача исключена. Для фоновой обработки напоминаний и политик дедлайна запускайте `python -m app.worker` по расписанию cron/systemd/Kubernetes CronJob; worker одноразовый, идемпотентный и не держит цикл внутри web process.

## Проверки и CI

```powershell
$env:PYTHONPATH='backend'
python -m pytest -q tests -p no:cacheprovider
python -m compileall -q backend
node --check app.js
node --check frontend/js/api.js
node --check sw.js
```

GitHub Actions запускает те же проверки на `push` и `pull_request` и падает при ошибке тестов. Архитектурные границы описаны в [ARCHITECTURE.md](ARCHITECTURE.md).

## Ограничения

- синхронизация запускается вручную, а её scheduler можно вынести в отдельный worker;
- разрешение конфликтов — `latest updated_at wins`, ручного UI пока нет;
- внешние события доступны на уровне модели и sync, отдельный календарный UI ещё не добавлен;
- frontend остаётся vanilla JS/PWA; канонический файл один, постепенное деление на ES modules ещё не завершено;
- desktop/mobile и финансовый модуль не реализованы.
