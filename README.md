# План — ежедневник

Клиент-серверное приложение для задач, календаря, проектов, Kanban, шаблонов и напоминаний.

## Локальный запуск

```powershell
python -m pip install -r backend/requirements.txt
python run.py
```

Приложение: `http://127.0.0.1:8000`  
OpenAPI: `http://127.0.0.1:8000/api/docs`

Существующая локальная база обновляется без удаления данных. Для новой установки сначала зарегистрируйте пользователя. Сохранённый демонстрационный аккаунт раннего прототипа: `demo@plan.local` / `demo12345` — используйте только локально.

## PostgreSQL

```powershell
docker compose up --build
```

Перед production-запуском задайте собственные `POSTGRES_PASSWORD`, `SECRET_KEY` и `COOKIE_SECURE=1`.

## Google Calendar

```text
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/v1/google/callback
```

После OAuth доступны зашифрованное хранение токенов и двусторонний endpoint `POST /api/v1/google/sync`. Samsung Calendar получает события через подключённый Google-аккаунт.

## Реализовано

- регистрация, вход, выход, HttpOnly-сессия и PBKDF2;
- CRUD задач и проектов с проверкой владельца;
- UTC `start_at`/`due_at`, all-day, длительность и timezone пользователя;
- optimistic concurrency через `sync_version`;
- soft delete и Activity Log;
- динамические Kanban-колонки и drag & drop;
- календарь День/Неделя/Месяц/Повестка и перенос событий;
- повторения и создание следующего экземпляра;
- напоминания и внутренний notification endpoint;
- шаблоны, поиск, приоритеты и фильтры;
- PWA/service worker;
- SQLite, PostgreSQL, Docker и Alembic;
- Google Calendar OAuth и двусторонняя синхронизация;
- pytest и GitHub Actions CI.

## Проверка

```powershell
$env:PYTHONPATH='backend'
python -m pytest -q tests/test_api.py -p no:cacheprovider
node --check app-clean.js
```
