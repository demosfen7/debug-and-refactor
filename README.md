# Debug and Refactor

Учебный проект: аудит, дебаг и рефакторинг Python-кода с намеренными ошибками, разбиение на модули и порт HTTP-сервера на Go.

- `app/` — Python-пакет: HTTP API на Flask и хранилище профилей пользователей (теги, пароли).
- `go-server/` — тот же HTTP API на Go, см. [go-server/README.md](go-server/README.md).

Что было сломано в исходных `api.py` и `utility.py` и как исправлено — в [AUDIT.md](AUDIT.md), там же исходники до правок.

## Структура

```
app/
├── __init__.py          create_app() — фабрика Flask-приложения
├── __main__.py          запуск: python -m app
├── config.py            настройки из переменных окружения
├── models.py            модели данных (User, UserProfile) и схемы таблиц
├── db.py                подключения к SQLite
├── routes/
│   └── users.py         маршруты /adduser и /user/<id>
├── repositories/        SQL-запросы
│   ├── api_users.py     пользователи HTTP API
│   └── profiles.py      профили: теги, пароли
└── utils/               логика без HTTP и SQL
    ├── validation.py    проверка имени и тела запроса
    ├── passwords.py     хеширование паролей (scrypt)
    └── active_users.py  список недавно активных пользователей
tests/                   тесты, по файлу на слой
go-server/               порт HTTP API на Go
```

Зависимости между слоями идут в одну сторону: `routes` → `repositories` → `db`/`models`, и все могут пользоваться `utils`. Маршруты не пишут SQL, репозитории ничего не знают об HTTP.

В пакете два независимых хранилища пользователей, каждое в своём файле SQLite:

| Хранилище | Модель | Файл БД | Кто пользуется |
|-----------|--------|---------|----------------|
| `repositories/api_users.py` | `User`: id, имя | `API_DB` (`test.db`) | HTTP API |
| `repositories/profiles.py` | `UserProfile`: id, имя, теги + хеш пароля | `USERS_DB` (`users.db`) | Код на Python напрямую |

## Требования

- Python 3.10+ (проверено на 3.14)
- Flask 3.1

## Установка

```bash
python -m venv .venv
```

Активировать окружение — в PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

В Git Bash:

```bash
source .venv/Scripts/activate
```

Установить зависимости (для разработки, вместе с pytest):

```bash
pip install -r requirements-dev.txt
```

Только для запуска сервера достаточно `requirements.txt`.

## Запуск сервера

```bash
flask --app app run
```

Сервер слушает `http://127.0.0.1:5000`. Другой порт — `flask --app app run --port 8000`. Без CLI Flask: `python -m app`.

База — файл SQLite `test.db` в текущей папке; создаётся автоматически при старте. Путь задаётся переменной окружения `API_DB`.

Встроенный сервер Flask — для разработки. Для продакшена нужен WSGI-сервер (например, waitress или gunicorn) с фабрикой `app:create_app()`.

## API

| Метод и путь | Тело запроса | Ответ |
|--------------|--------------|-------|
| `POST /adduser` | JSON `{"name": "..."}`, заголовок `Content-Type: application/json` | `201 {"id": 1, "name": "..."}` и заголовок `Location: /user/1` |
| `GET /user/<id>` | — | `200 {"id": 1, "name": "..."}` |

Ошибки возвращаются JSON-объектом `{"error": "..."}`:

| Статус | Когда |
|--------|-------|
| `400` | Тело не JSON, нет поля `name`, `name` не строка или пустая строка |
| `404` | Пользователя нет или id не целое число |
| `405` | Неверный метод, например `GET /adduser` (ответ HTML от Flask) |

### Примеры

Git Bash, Linux, macOS:

```bash
curl -i -X POST http://127.0.0.1:5000/adduser -H "Content-Type: application/json" -d '{"name": "alice"}'
```

```bash
curl -i http://127.0.0.1:5000/user/1
```

PowerShell (у `curl.exe` в Windows PowerShell 5.1 ломаются кавычки в JSON, поэтому здесь `Invoke-RestMethod`):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/adduser -ContentType 'application/json' -Body '{"name": "alice"}'
```

```powershell
Invoke-RestMethod http://127.0.0.1:5000/user/1
```

## Профили и утилиты из Python

```python
from app.repositories import profiles
from app.utils.active_users import get_active_users, set_active

uid = profiles.add_user("alice", ["admin"])    # -> 1; к тегам добавится "new"
profiles.get_user_by_name("alice")             # -> {"id": 1, "name": "alice", "tags": ["admin", "new"]}
profiles.get_user_by_name("ghost")             # -> None

profiles.store_password(uid, "s3cret")         # хеш scrypt с солью, хранится в БД
profiles.verify_password(uid, "s3cret")        # -> True

set_active(uid)
get_active_users()                             # -> [1]; хранятся последние 5, без повторов
```

База профилей — `users.db` в текущей папке, путь задаётся переменной `USERS_DB` или аргументом `db_path=` у каждой функции.

Для своего списка активных с другим лимитом есть класс `ActiveUsers(limit=...)` с методами `mark`, `snapshot`, `clear`.

## Тесты

```bash
python -m pytest -q
```

| Файл | Что проверяет |
|------|---------------|
| `tests/test_routes_users.py` | HTTP API: статусы, валидация, инъекции, параллельные запросы |
| `tests/test_profiles.py` | Хранилище профилей |
| `tests/test_utils.py` | Пароли, валидация, список активных |

Тесты работают во временных папках и не трогают `test.db` и `users.db`. Настройки pytest — в `pyproject.toml`, поэтому запускать можно из любой папки проекта.

## Переменные окружения

| Переменная | Кто читает | По умолчанию |
|------------|------------|--------------|
| `API_DB` | HTTP API (`app`, `go-server`) | `test.db` |
| `USERS_DB` | `app.repositories.profiles` | `users.db` |
| `API_ADDR` | `go-server` | `127.0.0.1:5000` |
