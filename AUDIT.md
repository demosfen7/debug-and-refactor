# Аудит `utility.py` и `api.py`

Дата: 15.10.2026. > После аудита код разнесён по пакету `app/` (см. [README.md](README.md#структура)): `api.py` → `app/routes`, `app/db.py`, `app/repositories/api_users.py`; `utility.py` → `app/repositories/profiles.py` и `app/utils/`. Тесты — в `tests/`. Номера строк и имена файлов ниже относятся к версии до разбиения.

Исходники обоих файлов — в приложениях в конце. Оригинал `api.py` есть ещё и в первом коммите, а `utility.py` закоммичен уже исправленным — его исходник только здесь.

Все тесты (`test_utility.py` — 21, `test_api.py` — 18):

```bash
python -m pytest -q
```

# Часть 1. `utility.py`

## Как проверялось

Оригинал запускался как есть (после очистки от HTML), каждый баг воспроизведён скриптом.
После рефакторинга — `test_utility.py`, 21 тест, все проходят:

```bash
python -m pytest -q
```

## Найденные проблемы

| # | Где | Проблема | Подтверждено | Исправление |
|---|-----|----------|--------------|-------------|
| 1 | весь файл | Код обёрнут в HTML-теги `<code …>`, `store_password` продублирована с лишним отступом — файл не импортируется вообще | `SyntaxError` / `IndentationError` | Чистый Python |
| 2 | `add_user` | `cur.lastrowid + ""` — `TypeError`. **Хуже:** строка уже закоммичена в БД до падения, вызывающий видит ошибку, а пользователь создан | `TypeError` | Возвращается `int` |
| 3 | `add_user`, `get_user_by_name` | Таблица `users` нигде не создаётся | `no such table: users` | `CREATE TABLE IF NOT EXISTS` при подключении |
| 4 | `add_user` | Мутируемый дефолт `tags=[]`: метка `"new"` копится между вызовами | дефолт стал `['new', 'new']` | `tags=None`, новый список |
| 5 | `add_user` | Изменяет список, переданный вызывающим | `['admin']` → `['admin', 'new']` | Копия, оригинал не трогается |
| 6 | `add_user` | SQL-инъекция через f-строку; имя `O'Brien` ломает запрос | `syntax error near "Brien"` | Параметры `?` |
| 7 | `get_user_by_name` | SQL-инъекция через `%` | `"nobody' OR '1'='1"` вернул alice | Параметры `?` |
| 8 | `get_user_by_name` | При отсутствии пользователя возвращает `{}` вместо `None` | `{}` | `None` |
| 9 | `get_user_by_name` | `tags` возвращается JSON-строкой, а не списком | `str` | `json.loads` |
| 10 | обе функции БД | Соединения не закрываются, при ошибке нет rollback | — | `closing()` + транзакция `with conn` |
| 11 | `store_password` | «Хеш» — это пароль задом наперёд, без соли | `1:terces` | scrypt + случайная соль |
| 12 | `store_password` | `"\\n"` пишет буквально `\n` — все записи в одну строку | `'1:terces\\n2:2retnuh\\n'` | — (файл больше не используется) |
| 13 | `store_password` | Файл не закрывается; повторный вызов дописывает дубль, а не обновляет | — | Хеш хранится в колонке `users.password_hash`, `UPDATE` |
| 14 | `set_active` | Проверка `len > 5` и `pop(0)` не атомарны: два потока могут оба сделать `pop` и сократить список до 4 | в прогоне не проявилось (GIL), но гонка реальна | `deque(maxlen=5)` + `Lock` |
| 15 | `set_active` | `time.sleep(0.1)` в рабочем коде; `pop(0)` — O(n); один пользователь может занять несколько мест | — | Убрано; повторная активация двигает id в конец |
| 16 | модуль | `CACHE` и `import threading` не используются; путь к БД захардкожен | — | Удалено; `USERS_DB` из окружения + `db_path=` |
| 17 | модуль | Нет типов, докстринг `add_user` противоречит коду | — | Аннотации, `TypedDict User` |

## Изменения контракта (важно для вызывающего кода)

- `add_user` возвращает `int`; пустое имя → `ValueError`.
- `get_user_by_name` возвращает `None`, если пользователя нет; `tags` — список. При неуникальных именах — самый ранний.
- Пароли хранятся в БД, а не в `passwords.txt`. `store_password` для несуществующего пользователя → `LookupError`, пустой пароль → `ValueError`.
- Добавлена `verify_password(user_id, password)` — без неё хеш бесполезен.
- Глобальный список `active_users` стал приватным `_active_users`; читать через `get_active_users()`.
- У всех функций БД есть keyword-аргумент `db_path` (удобно для тестов).

## Открытые вопросы

- **Уникальность имени.** Сейчас имена могут повторяться. Если имя — логин, стоит добавить `UNIQUE` на `users.name`.
- **Миграция.** Если где-то есть старый `users.db` без колонки `password_hash` или старый `passwords.txt`, нужна миграция; «перевёрнутые» пароли перенести нельзя — только сбросить.

# Часть 2. `api.py`

## Как проверялось

Оригинал не парсится, поэтому для воспроизведения в копии были исправлены только синтаксические ошибки (№ 1–2), логика осталась прежней. Запросы слались через тестовый клиент Flask.

## Найденные проблемы

| # | Где | Проблема | Подтверждено | Исправление |
|---|-----|----------|--------------|-------------|
| 1 | весь файл | HTML-обёртка `<code …>` | `SyntaxError` | Чистый Python |
| 2 | весь файл | Синтаксис: `sqlite3.conn@ct`, `methods=["POST"))`, `fINSERT …"` без кавычки, `jsonify({…))`, неверный отступ `return` | `SyntaxError` | Исправлено |
| 3 | `/adducer` | Опечатка в маршруте: клиент, обращающийся к `/adduser`, получает 404 | `404 Not Found` | Маршрут `/adduser` |
| 4 | `addUser` | SQL-инъекция через f-строку: `x'),('pwned` создаёт две строки, `O'Brien` роняет сервер | лишняя строка `pwned`; `500` | Параметры `?` |
| 5 | `GETUSER` | SQL-инъекция через конкатенацию `id=`+uid: `0 UNION SELECT …` читает произвольные данные БД | вернулась версия SQLite | `<int:uid>` + параметр `?` |
| 6 | `GETUSER` | Нечисловой id роняет сервер | `/user/abc` → `500` | `<int:uid>` → `404` |
| 7 | `GETUSER` | «Не найден» отдаётся со статусом 200 | `200 {"error":"notfound"}` | `404` |
| 8 | `GETUSER` | Найденный пользователь отдаётся с 201 Created | `201` | `200` |
| 9 | `addUser` | Нет валидации: пустое имя принимается, не-JSON тело даёт HTML-ошибку 415 | `200 ok` на `""`; `415` | `400` с JSON-ошибкой для любого кривого тела |
| 10 | `addUser` | Ответ `"ok"` со статусом 200: клиент не узнаёт id созданного пользователя | `200 ok` | `201`, `{"id", "name"}`, заголовок `Location` |
| 11 | модуль | Одно глобальное соединение и **один курсор** на все потоки с `check_same_thread=False`: при параллельных запросах `execute`/`fetchone` разных запросов перемешиваются | не воспроизводилось, гонка по устройству кода | Своё соединение на запрос (`flask.g`), закрытие в `teardown` |
| 12 | модуль | `try: CREATE TABLE … except: pass` глотает любые ошибки, включая отсутствие прав и битую БД | — | `CREATE TABLE IF NOT EXISTS` |
| 13 | модуль | Таблица создаётся и БД открывается при импорте; путь `test.db` захардкожен | — | Фабрика `create_app(database)`, путь из `API_DB` |
| 14 | модуль | Неиспользуемые `time`, `random`, `threading`; имена `addUser`, `GETUSER` вне PEP 8 | — | Удалено, переименовано |
| 15 | модуль | `active = []` — обрывок третьего эндпоинта («поток со сломанной логикой»): код после него в файле отсутствует | — | Удалено (см. открытые вопросы) |

## Найдено при тестировании исправленной версии

Переход на соединение-на-запрос открыл проблему, которой в оригинале не было (там все запросы шли через одно соединение): при 20 параллельных писателях SQLite отвечал `database is locked`. На Windows каждый коммит в режиме rollback journal — несколько fsync, очередь писателей не укладывалась в 5-секундный таймаут. Решение — `journal_mode=WAL` + `synchronous=NORMAL`: 200 параллельных вставок теперь проходят за ~1,8 с, без ошибок и с уникальными id (`test_concurrent_requests`).

## Изменения контракта

- Маршрут добавления — `/adduser` (было `/adducer`).
- `POST /adduser` → `201 {"id", "name"}` + `Location`; при неверном теле → `400 {"error"}`.
- `GET /user/<id>` → `200` при успехе, `404 {"error": "user not found"}` если нет; нечисловой id → `404`.
- Запуск: `flask --app api run` или `python api.py`. Импорт модуля больше не создаёт БД.

## Открытые вопросы

- **Третий эндпоинт.** В файле остался только комментарий «эндпоинт, где создаётся поток, но логика сломана» и `active = []` — сам код обрезан при копировании. Если есть полная версия, её нужно разобрать отдельно.
- **Общая БД с `utility.py`.** Оба модуля ведут свою таблицу `users` с разными схемами (`users.db` и `test.db`). Если это одно приложение, API стоит перевести на функции из `utility.py`.
- **REST-маршруты.** Привычнее `POST /users` и `GET /users/<id>`; оставлены старые пути, чтобы не ломать клиентов сильнее необходимого.

## Приложение A: исходный `utility.py`

````text
<code class="language-python" style="white-space:pre-wrap;word-break:break-all">import sqlite3
import threading
import time
import json
# Глобальная переменная — плохая идея
CACHE = {}
# Мутируемый дефолтный аргумент — плохая документация
def add_user(name, tags=[]):
    """
    Добавляет пользователя в локальную базу.
    Возвращает id (int) — но на деле возвращает строку.
    """
    tags.append("new")  # неожиданно модифицирует аргумент зовущего
    conn = sqlite3.connect('users.db')  # соединение не закрывается при ошибке
    cur = conn.cursor()
    # Небезопасная вставка — уязвимость SQL-инъекции
    query = f"INSERT INTO users (name, tags) VALUES ('{name}', '{json.dumps(tags)}')"
    cur.execute(query)
    conn.commit()
    # Возвращаем строку (ошибка типов)
    return cur.lastrowid + ""
# Неправильная обработка паролей — "хеширование" через простой срез
def store_password(user_id, password):
    # pretend hashing
    hashed = password[::-1]  # не-хеш!
    f = open('passwords.txt', 'a')  # файл не закрывается в случае ошибки
    f.write(f"{user_id}:{hashed}\\n")
    # забыли закрыть файл</code>

    <code class="language-python" style="white-space:pre-wrap;word-break:break-all">def store_password(user_id, password):
    # pretend hashing
    hashed = password[::-1]  # не-хеш!
    f = open('passwords.txt', 'a')  # файл не закрывается в случае ошибки
    f.write(f"{user_id}:{hashed}\\n")
    # забыли закрыть файл
# Функция с гонкой потоков (общий список без блокировок)
active_users = []
def set_active(user_id):
    # имитируем задержку, чтобы гонка проявилась
    active_users.append(user_id)
    time.sleep(0.1)
    # иногда удаляем первый элемент — логика странная
    if len(active_users) > 5:
        active_users.pop(0)
# Неверный пример запроса (SQL-инъекция + неправильный тип возврата)
def get_user_by_name(name):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    # опасный способ составления запроса
    cur.execute("SELECT id, name, tags FROM users WHERE name = '%s'" % name)
    row = cur.fetchone()
    # не закрываем соединение
    if not row:
        # возвращаем пустой dict вместо None — контракт не соблюдается
        return {}
    uid, uname, tags_json = row
    # забываем декодировать теги корректно — возможно выброс исключения
    return {"id": uid, "name": uname, "tags": tags_json}</code>
````

## Приложение B: исходный `api.py`

````text
<code class="language-python" style="white-space:pre-wrap;word-break:break-all">from flask import Flask,request,jsonify
import sqlite3,time,random, threading
app=Flask(__name__)
# глобальное соединение (плохая практика)
conn = sqlite3.conn@ct("test.db", check_same_thread=False)
cur=conn.cursor()
try:
    cur.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT)")
except:
    pass
# НЕ ПЕЛ8, плохие имена, нет валидации, SQL-инъекции
@app.route("/adducer", methods=["POST"))
def addUser():
    name = request.json.get("name","")
    q = fINSERT INTO users(name) VALUES('{name}')"
    cur.execute(q) # инъекция
    conn.commit()
    return "ok"
# Эндпомит с неверной логикой и неправильными статусами
@app.route("/user/<uid>")
def GETUSER(uid):
    cur.execute("select id,name from users where id="+uid) # тоже инъекция
    r = cur.fetchone()
    if not r:
    return jsonify({"error":"notfound")) # статус не возвращён
    return jsonify({"id":r[0],"name":r[1]}), 201 # неверный код 201 вместо 200
# Эндпомит, где создаётся поток, но логика сломана
active = []</code>
````
