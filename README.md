# Debug and Refactor

Учебный проект: аудит, дебаг и рефакторинг двух Python-файлов с намеренно сломанным кодом, плюс порт HTTP-сервера на Go.

- `utility.py` — функции для работы с пользователями: SQLite, хеширование паролей, список активных.
- `api.py` — HTTP API на Flask: создать пользователя и получить его по id.
- `go-server/` — тот же API на Go, см. [go-server/README.md](go-server/README.md).

Что было сломано и как исправлено — в [AUDIT.md](AUDIT.md), там же исходники до правок.

## Структура

| Файл | Назначение |
|------|------------|
| `api.py` | Flask-сервер |
| `utility.py` | Модуль работы с пользователями |
| `test_api.py`, `test_utility.py` | Тесты (pytest) |
| `requirements.txt` | Зависимости для запуска |
| `requirements-dev.txt` | Зависимости для разработки (запуск + тесты) |
| `AUDIT.md` | Отчёт аудита |
| `go-server/` | Порт сервера на Go |

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
flask --app api run
```

Сервер слушает `http://127.0.0.1:5000`. Другой порт — `flask --app api run --port 8000`. Можно и без CLI Flask: `python api.py`.

База — файл SQLite `test.db` в текущей папке; создаётся автоматически при старте. Путь задаётся переменной окружения `API_DB`.

Встроенный сервер Flask — для разработки. Для продакшена нужен WSGI-сервер (например, waitress или gunicorn) с фабрикой `api:create_app()`.

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

## Модуль `utility.py`

```python
import utility

uid = utility.add_user("alice", ["admin"])     # -> 1; к тегам добавится "new"
utility.get_user_by_name("alice")              # -> {"id": 1, "name": "alice", "tags": ["admin", "new"]}
utility.get_user_by_name("ghost")              # -> None

utility.store_password(uid, "s3cret")          # хеш scrypt с солью, хранится в БД
utility.verify_password(uid, "s3cret")         # -> True

utility.set_active(uid)
utility.get_active_users()                     # -> [1]; хранятся последние 5, без повторов
```

База — `users.db` в текущей папке, путь задаётся переменной `USERS_DB` или аргументом `db_path=` у каждой функции. Это отдельная база от `api.py`: схемы таблиц `users` у модулей разные.

## Тесты

```bash
python -m pytest -q
```

Тесты работают во временных папках и не трогают `test.db` и `users.db`.

## Переменные окружения

| Переменная | Кто читает | По умолчанию |
|------------|------------|--------------|
| `API_DB` | `api.py`, `go-server` | `test.db` |
| `USERS_DB` | `utility.py` | `users.db` |
| `API_ADDR` | `go-server` | `127.0.0.1:5000` |
