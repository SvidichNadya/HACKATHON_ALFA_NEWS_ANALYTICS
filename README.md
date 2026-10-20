# Alfa News Intelligence — корпоративный бизнес-радар

Интерактивный конкурсный прототип: выбор синтетической компании → отбор новостей → объяснимое ранжирование → инсайт с фактами, гипотезами и неизвестными данными → источники → уточняющий диалог → обратная связь → трасса агентного процесса.

> **Не путать с production банковской системой.** В репозитории нет реальных клиентских CSV, оригинальных аналитических материалов кейса, банковской аутентификации или параметров корпоративной инфраструктуры. Демоданные явно помечены как синтетические и не являются официальной позицией Альфа-Банка. Перед промышленным внедрением обязательны корпоративная аутентификация/авторизация и изоляция tenant, импорт/проверка реальных данных, security review, нагрузочные испытания и согласование источников/моделей.

## Windows / Docker
1. Установите Docker Desktop с Compose v2.
2. Запустите `run.bat`.
3. Откройте http://localhost:8000.
4. Выберите одну из трёх синтетических компаний → «Запустить анализ» → откройте обоснование → задайте вопрос → оцените инсайт → просмотрите трассу агента.

Миграции, заполнение демоданных и сбор статики выполняются при старте контейнера. PostgreSQL доступен только внутри Docker-сети, веб-приложение привязано к localhost.

## Локальный запуск
Python 3.12+:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py test
python manage.py runserver
```
Без `POSTGRES_HOST` используется SQLite; Compose запускает PostgreSQL.

## Реализованные компоненты
- Профили: отрасль, ОКВЭД, выручка, география, группа, продукты, внешнеторговые признаки и происхождение полей.
- Новостная база: классификация, тональность, URL, дата, хеш заголовка и дедупликация.
- Импорт RSS/Atom из операторского `RSS_FEEDS`; произвольные URL из браузера не принимаются.
- Импорт аналитики TXT/MD/CSV/PDF/DOCX с извлечением текста и типом `BANK_ANALYSIS`.
- Объяснимое rule-based ранжирование; коэффициенты — стартовая эвристика, не обученная модель.
- Интерпретация: факты, экспозиция, сценарии, риски/возможности, неизвестные данные и проверки.
- Собственный ограниченный оркестратор: план, поиск, интерпретация, самопроверка, трасса AgentRun. Готовый автономный агентный фреймворк не используется.
- Опциональный OpenAI-compatible endpoint для моделей из allowlist: `Gemma 4 26B A4B`, `GLM-5.3-Flash`, `Qwen3.6 35B A3B`, `DeepSeek-V4.1-Flash`, `Qwen3-VL-30B-A3B-Instruct`, `Kimi-K2.6`. Без ключа/endpoint работает rule-based fallback; лимит расходов настраивается на gateway.
- Контекстный диалог, обратная связь, фильтры и API.
- CSRF для POST, HttpOnly session cookie, базовые security headers, лимит загрузки документа 15 МБ.

## Конфигурация
Скопируйте `.env.example` в `.env`. Настройки: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `WEB_PORT`, параметры PostgreSQL, `RSS_FEEDS`, `LLM_API_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`. Не коммитьте секреты. LLM endpoint должен поддерживать OpenAI-compatible Chat Completions и имя разрешённой модели.

## API
- `GET /api/companies/`
- `POST /api/companies/{id}/analyze/`
- `GET /api/insights/{id}/`
- `POST /api/insights/{id}/chat/`
- `POST /api/insights/{id}/feedback/`
- `POST /api/import/news/`
- `POST /api/import/bank-analysis/`
- `GET /api/agent-runs/`
- `GET /api/overview/`

## Проверка
`python manage.py test`. Перед сдачей также запустите чистый Docker volume, импортируйте оригинальные материалы кейса и пройдите end-to-end сценарий. Точные версии зависимостей закреплены; notices — в `THIRD_PARTY_NOTICES`.
