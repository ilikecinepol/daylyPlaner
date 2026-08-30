# Архитектура daylyPlaner

## Профиль пользователя

Миграция `0013` добавляет фамилию, должность, ручной статус, контакты и встроенный аватар. `PUT /api/v1/auth/profile` обновляет только профиль текущей сессии; email, nickname, пароль и права через него менять нельзя. IANA-часовой пояс валидируется. Аватары принимаются только как base64 PNG/JPEG/WebP до 512 КБ; внешние URL и SVG запрещены. Существующие имена и часовые пояса при миграции не меняются. Статус не определяет онлайн-присутствие и не отключает уведомления автоматически.

## Frontend

Vanilla HTML/CSS/JavaScript и service worker. `app.js` — единственная активная точка входа. Клиент общается через `/api/v1`, хранит даты в UTC ISO 8601 и сохраняет путь к PWA и оболочкам Tauri. Следующий рефакторинг — выделение `api`, `auth`, `calendar`, `tasks`, `kanban`, `chat`, `integrations` и `ui` в ES modules.

## Backend и Database

FastAPI + SQLAlchemy 2; SQLite используется локально, PostgreSQL — целевая production БД. Alembic является источником изменений схемы. Bootstrap и бизнес-алгоритмы находятся в `services/`, общие HTTP dependencies и integrations — в `api/`. Следующий этап — последовательный перенос оставшихся endpoint-групп из `main.py` в routers.

Клиент держит авторизованное SSE-подключение к `/api/v1/events`. Сервис `services/realtime.py` вычисляет пользовательскую ревизию доступных задач, проектов, сообщений и уведомлений; при её изменении браузер без перезагрузки страницы обновляет локальное состояние. Heartbeat поддерживает соединение через reverse proxy, а `X-Accel-Buffering: no` запрещает буферизацию потока.

## Task, Kanban и Calendar

`Task` — единая сущность для Kanban и собственного календаря. Календарный блок задают `start_at`, `end_at`, `duration_minutes` и `all_day`; независимый срок выполнения хранится в `deadline_at`, а `is_overdue` вычисляется на backend. `deadline_action` выбирает идемпотентное поведение worker: ничего не делать, отметить просрочку или автоматически завершить; `deadline_processed_at` защищает от повторной обработки. Поле `due_at` временно остаётся только как legacy-псевдоним `end_at` в API. Workflow-статусы: `idea`, `planned`, `in_progress`, `completed`, `cancelled`. Остальные источники истины: `priority`, `project_id`, `column_id`, `location`, `mentions`, `recurrence_rule`. Legacy-поля удаляются migration `0003`, разделение окончания и дедлайна выполняется migration `0008`, политики дедлайна добавляются migration `0009`. Kanban меняет `column_id`, календарь — scheduling fields; optimistic concurrency обеспечивается `sync_version`.

`TaskTemplate.task_data` хранит полный API-параметр карточки задачи. Выбор и создание шаблона находятся непосредственно в форме задачи; отдельного экрана шаблонов нет. Для старых записей API формирует совместимый `task_data` из legacy-полей.

Свободную проектную задачу участник с разрешением `edit_tasks` может назначить себе через `/tasks/{id}/assign-self`. Операция идемпотентна и не позволяет перехватить задачу другого исполнителя. Уведомления владельцу и администраторам проекта сохраняются как адресные записи `ActivityLog`.

## Google integration

`CalendarConnection` хранит зашифрованные tokens, expiry, статус и время успешной синхронизации. `CalendarEventLink` связывает только события daylyPlaner. Цикл: pull → match → compare timestamps → apply inbound → push local → metadata. При конфликте побеждает наиболее свежий timestamp. Удаляется только Google Event с существующей связью; неизвестные события сохраняются как `ExternalCalendarEvent` и не попадают в Kanban.

## Recurrence и notifications

Recurrence основан на RFC 5545 через `python-dateutil`: `DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY`, `BYDAY`, `BYMONTHDAY`, `INTERVAL`, `UNTIL`, `COUNT`. Notification service отделяет определение due reminders от HTTP. Канал in-app работает сейчас; модель допускает будущие `web_push` и `email`. Успешная обработка устанавливает `sent_at`.

## Permissions и security

Проектные роли агрегируют permissions; endpoints проверяют membership. Сессия подписана, OAuth state ограничен сроком токена, cookie — `HttpOnly`/`SameSite=Lax`, production требует явный secret. Следующее усиление state-changing cookie endpoints — отдельный CSRF token или строгая Origin-проверка.

## Будущие платформы и финансы

Desktop/mobile клиенты должны использовать тот же versioned API; Tauri или native-клиенты не импортируют backend internals. Финансы — отдельный bounded context: `Account`, `Transaction`, `TransactionCategory`, `Budget`, `RecurringTransaction`, `FinancialGoal`. Допустимы optional-связи `Transaction → Project` и `Transaction → Task`; финансовые поля не добавляются в `Task`.
## Личные цели

`Goal` хранит цель дня, недели (понедельник—воскресенье) или календарного месяца и пояснение «Зачем это важно». `Task.goal_id` связывает обычную задачу с одной личной целью без копирования. Связь меняет только автор задачи. Иерархия необязательна: родитель имеет более длительный период; прогресс считается по непосредственно связанным задачам, включая архивные, исключая отменённые и удалённые. Удаление цели отвязывает задачи и дочерние цели, сохраняя их. API `/api/v1/goals`, миграция `0014`, интерфейс `frontend/js/goals.js`.
