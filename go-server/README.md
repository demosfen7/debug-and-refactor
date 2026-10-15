# go-server

HTTP API пользователей на Go — порт HTTP API из Python-пакета [`app`](../app) с тем же контрактом: те же маршруты, статусы, формат JSON и схема базы.

> **Статус: код не компилировался и тесты не запускались.** Он писался на машине без Go. Перед использованием выполните шаги из раздела «Первый запуск» — `go test` покажет, всё ли в порядке.

## Требования

- Go 1.22 или новее (нужны маршруты с методами в `net/http`).
- Компилятор C и cgo **не нужны**: драйвер SQLite [`modernc.org/sqlite`](https://pkg.go.dev/modernc.org/sqlite) написан на чистом Go.

Установить Go на Windows:

```powershell
winget install GoLang.Go
```

Или скачать установщик с [go.dev/dl](https://go.dev/dl/). После установки откройте новый терминал и проверьте:

```bash
go version
```

## Первый запуск

Все команды — из папки `go-server`:

```bash
cd go-server
```

Скачать зависимости и создать `go.sum` (нужно один раз; `go.sum` стоит закоммитить):

```bash
go mod tidy
```

Прогнать тесты:

```bash
go test ./...
```

Запустить сервер:

```bash
go run ./cmd/server
```

В логе появится `listening on http://127.0.0.1:5000 (db: test.db)`.

## Настройка

| Флаг | Переменная окружения | По умолчанию | Что задаёт |
|------|----------------------|--------------|------------|
| `-addr` | `API_ADDR` | `127.0.0.1:5000` | Адрес и порт |
| `-db` | `API_DB` | `test.db` | Путь к файлу SQLite |

Флаг важнее переменной окружения. Пример:

```bash
go run ./cmd/server -addr 127.0.0.1:8080 -db users.db
```

Чтобы сервер был доступен с других машин, слушайте все интерфейсы: `-addr 0.0.0.0:8080`.

## Сборка бинарника

Windows:

```bash
go build -o go-server.exe ./cmd/server
```

```bash
./go-server.exe -addr 127.0.0.1:8080
```

Под Linux — например, для сервера — собирается прямо с Windows, cgo не нужен. В Git Bash:

```bash
GOOS=linux GOARCH=amd64 go build -o go-server ./cmd/server
```

В PowerShell:

```powershell
$env:GOOS='linux'; $env:GOARCH='amd64'; go build -o go-server ./cmd/server
```

Бинарник самодостаточный: копируете один файл и запускаете.

## API

| Метод и путь | Тело запроса | Ответ |
|--------------|--------------|-------|
| `POST /adduser` | JSON `{"name": "..."}`, заголовок `Content-Type: application/json` | `201 {"id": 1, "name": "..."}` и заголовок `Location: /user/1` |
| `GET /user/{id}` | — | `200 {"id": 1, "name": "..."}` |

Ошибки — JSON `{"error": "..."}`:

| Статус | Когда |
|--------|-------|
| `400` | Нет JSON-заголовка `Content-Type`, тело не JSON или больше 1 МБ, нет поля `name`, `name` не строка или пустая |
| `404` | Пользователя нет или id не целое число |
| `405` | Неверный метод, например `GET /adduser` (текстовый ответ от `net/http`) |
| `500` | Ошибка базы; подробности — в логе сервера, клиенту только `internal error` |

### Примеры

Git Bash, Linux, macOS:

```bash
curl -i -X POST http://127.0.0.1:5000/adduser -H "Content-Type: application/json" -d '{"name": "alice"}'
```

```bash
curl -i http://127.0.0.1:5000/user/1
```

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/adduser -ContentType 'application/json' -Body '{"name": "alice"}'
```

```powershell
Invoke-RestMethod http://127.0.0.1:5000/user/1
```

## Остановка

`Ctrl+C` (или `SIGTERM` на Linux). Сервер перестаёт принимать новые соединения, до 10 секунд ждёт завершения текущих запросов и закрывает базу.

## Устройство

```
cmd/server/main.go           точка входа: флаги, запуск, корректная остановка
internal/
├── model/user.go            модель User и ошибка ErrNotFound
├── store/store.go           хранилище в SQLite: открытие, схема, запросы
└── httpapi/                 HTTP-слой
    ├── routes.go            маршруты и интерфейс UserStore
    ├── handlers.go          обработчики запросов
    ├── request.go           разбор и проверка тела запроса
    ├── response.go          JSON-ответы
    └── handlers_test.go     тесты — зеркало tests/test_routes_users.py
```

Слои те же, что в Python-пакете: `httpapi` ≈ `app/routes` + `app/utils/validation`, `store` ≈ `app/repositories/api_users`, `model` ≈ `app/models`. Пакет `httpapi` зависит не от `store`, а от интерфейса `UserStore` — хранилище можно подменить, например, заглушкой в тестах. Каталог `internal/` закрывает пакеты от импорта извне модуля.

База работает в режиме WAL — как и в Python-версии, иначе параллельные запросы на запись упираются в `database is locked`. Поэтому рядом с файлом базы во время работы лежат `test.db-wal` и `test.db-shm`; это нормально, в git они не попадают.

Схема таблицы та же, что у HTTP API в Python-пакете, поэтому обе версии могут работать с одним файлом — укажите им одинаковый `API_DB`.

## Отличия от Python-версии

- Нечисловой id (`/user/abc`) — JSON `404 {"error": "user not found"}`; во Flask это HTML-страница 404.
- Неизвестный маршрут и неверный метод — текстовый ответ `net/http`; во Flask — HTML.
- Тело запроса ограничено 1 МБ; у Flask по умолчанию лимита нет.
- Заданы таймауты чтения и записи (10 с) — защита от медленных клиентов; встроенный сервер Flask их не ставит.

## Тесты

```bash
go test ./...
```

Подробный вывод — `go test -v ./...`. Детектор гонок `go test -race ./...` на Windows требует cgo и компилятор C (например, MinGW-w64), без них он не запустится; на Linux и macOS работает из коробки.
