# Аудит `utility.py`

Дата: 15.10.2026. Исходник — в приложении в конце (папка не под git, копии больше нет).

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

## Приложение: исходный `utility.py`

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
