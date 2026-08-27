# Архитектура daylyPlaner

## Frontend

Vanilla HTML/CSS/JavaScript и service worker. `app.js` — единственная активная точка входа. Клиент общается через `/api/v1`, хранит даты в UTC ISO 8601 и сохраняет путь к PWA и оболочкам Tauri. Следующий рефакторинг — выделение `api`, `auth`, `calendar`, `tasks`, `kanban`, `chat`, `integrations` и `ui` в ES modules.

## Backend и Database

FastAPI + SQLAlchemy 2; SQLite используется локально, PostgreSQL — целевая production БД. Alembic является источником изменений схемы. HTTP orchestration пока находится в `main.py`; recurrence, notifications и calendar sync вынесены в `services/`. Следующий этап — перенос endpoint-групп в `api/` routers.

## Task, Kanban и Calendar

`Task` — единая сущность для Kanban и собственного календаря. Источники истины: `start_at`, `due_at`, `duration_minutes`, `all_day`, `status`, `priority`, `project_id`, `column_id`, `location`, `mentions`, `recurrence_rule`. Legacy-поля удаляются migration `0003`. Kanban меняет `column_id`, календарь — scheduling fields; optimistic concurrency обеспечивается `sync_version`.

## Google integration

`CalendarConnection` хранит зашифрованные tokens, expiry, статус и время успешной синхронизации. `CalendarEventLink` связывает только события daylyPlaner. Цикл: pull → match → compare timestamps → apply inbound → push local → metadata. При конфликте побеждает наиболее свежий timestamp. Удаляется только Google Event с существующей связью; неизвестные события сохраняются как `ExternalCalendarEvent` и не попадают в Kanban.

## Recurrence и notifications

Recurrence основан на RFC 5545 через `python-dateutil`: `DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY`, `BYDAY`, `BYMONTHDAY`, `INTERVAL`, `UNTIL`, `COUNT`. Notification service отделяет определение due reminders от HTTP. Канал in-app работает сейчас; модель допускает будущие `web_push` и `email`. Успешная обработка устанавливает `sent_at`.

## Permissions и security

Проектные роли агрегируют permissions; endpoints проверяют membership. Сессия подписана, OAuth state ограничен сроком токена, cookie — `HttpOnly`/`SameSite=Lax`, production требует явный secret. Следующее усиление state-changing cookie endpoints — отдельный CSRF token или строгая Origin-проверка.

## Будущие платформы и финансы

Desktop/mobile клиенты должны использовать тот же versioned API; Tauri или native-клиенты не импортируют backend internals. Финансы — отдельный bounded context: `Account`, `Transaction`, `TransactionCategory`, `Budget`, `RecurringTransaction`, `FinancialGoal`. Допустимы optional-связи `Transaction → Project` и `Transaction → Task`; финансовые поля не добавляются в `Task`.
