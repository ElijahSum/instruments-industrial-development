# Мини-дашборд рынка электроэнергии

Контейнеризованная версия сервиса для задания `task_03_docker`.

Приложение состоит из двух сервисов:

- `backend` на `FastAPI` хранит данные в CSV и предоставляет CRUD API
- `frontend` на `Streamlit` получает данные только через API и отображает
  таблицу и графики

Данные основаны на файле
`RU_Electricity_Market_PZ_dayahead_price_volume.csv`.
При первом запуске backend нормализует исходный CSV, добавляет столбец
`id` и сохраняет рабочую копию данных.

## Структура папки

```text
task_03_docker/
├── backend/
│   ├── main.py
│   ├── data.csv
│   └── RU_Electricity_Market_PZ_dayahead_price_volume.csv
├── frontend/
│   └── app.py
├── tests/
│   ├── conftest.py
│   └── test_backend.py
├── dashboard_shared.py
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── pycodestyle.py
├── requirements.txt
└── README.md
```

## Что реализовано

### Backend API

- `GET /records` — получить все записи
- `POST /records` — добавить новую запись
- `DELETE /records/{id}` — удалить запись по `id`
- `GET /ping` — healthcheck backend

### Frontend UI

- отображение таблицы с данными, включая `id`
- график потребления
- график цен
- форма добавления записи
- форма удаления записи по `id`

## Переменные окружения

### Backend

- `DATA_PATH` — путь к рабочему CSV-файлу
- `SEED_DATA_PATH` — путь к исходному CSV-файлу
- `CORS_ORIGINS` — разрешенные origin через запятую

### Frontend

- `API_URL` — адрес backend API
- `API_TIMEOUT` — таймаут запросов в секундах

## Запуск через Docker Compose

Все команды ниже выполняются из папки `task_03_docker/`.

### 0. Переход в папку задания

```bash
cd task_03_docker
```

## Как собрать Docker-образы вручную

Если требуется отдельно показать именно сборку Docker-образов, а не только
`docker compose`, можно собрать оба образа вручную.

### Сборка backend-образа

```bash
docker build -f Dockerfile.backend -t electricity-backend .
```

### Сборка frontend-образа

```bash
docker build -f Dockerfile.frontend -t electricity-frontend .
```

## Как запускать контейнеры вручную

Перед ручным запуском backend-контейнера удобно создать volume для данных:

```bash
docker volume create backend_data
```

### Запуск backend-контейнера

```bash
docker run --rm -p 8888:8888 \
  -e DATA_PATH=/data/data.csv \
  -e SEED_DATA_PATH=/app/backend/RU_Electricity_Market_PZ_dayahead_price_volume.csv \
  -v backend_data:/data \
  electricity-backend
```

### Запуск frontend-контейнера

Frontend нужно запускать после backend. Если backend запущен через Compose
или внутри одной Docker-сети с именем `backend`, можно использовать такой
запуск:

```bash
docker run --rm -p 8889:8889 \
  -e API_URL=http://host.docker.internal:8888 \
  -e API_TIMEOUT=15 \
  electricity-frontend
```

На macOS `host.docker.internal` позволяет frontend-контейнеру обратиться
к backend, опубликованному на хосте.

### 1. Сборка и запуск

```bash
docker compose up --build
```

Или в фоне:

```bash
docker compose up --build -d
```

После запуска сервисы будут доступны по адресам:

- backend API: `http://localhost:8888`
- Swagger UI: `http://localhost:8888/docs`
- Streamlit UI: `http://localhost:8889`

### 2. Остановка контейнеров

```bash
docker compose down
```

### 3. Полный сброс данных контейнеров

Если нужно удалить контейнеры вместе с volume:

```bash
docker compose down -v
```

## Как пользоваться приложением

### Просмотр данных

1. Откройте `http://localhost:8889`.
2. На странице будут доступны:
   - таблица всех записей
   - график потребления
   - график цен
3. Кнопка `Обновить данные` повторно загружает данные из backend API.

### Добавление записи

В блоке `Добавление записи`:

1. Выберите дату.
2. Выберите время.
3. Введите значения:
   - `Потребление EUR`
   - `Потребление SIB`
   - `Цена EUR`
   - `Цена SIB`
4. Нажмите `Добавить запись`.

После этого frontend отправляет `POST /records`, а backend:

- валидирует данные через `Pydantic`
- сохраняет запись в CSV
- возвращает созданный объект

При ошибке на экране отображается текст ошибки.

Пример валидного JSON для API:

```json
{
  "timestep": "2011-11-23 00:00",
  "consumption_eur": 72100,
  "consumption_sib": 21450,
  "price_eur": 980.35,
  "price_sib": 615.2
}
```

### Удаление записи

В блоке `Удаление записи`:

1. Укажите `id` записи.
2. Нажмите `Удалить запись`.

После этого frontend отправляет `DELETE /records/{id}`.

Если запись существует:

- запись удаляется из CSV
- таблица и графики обновляются

Если `id` не найден:

- отображается сообщение об ошибке

Удаление выполняется только по `id`, а не по номеру строки.

## API

### `GET /records`

Возвращает все записи из CSV вместе с `id`.

### `POST /records`

Добавляет новую запись и возвращает созданный объект.

### `DELETE /records/{id}`

Удаляет запись по `id`.

Ответ:

```json
{
  "deleted_id": 123
}
```

### `GET /ping`

Служебный endpoint для проверки доступности backend.

## Примеры API-запросов

### Проверка backend

```bash
curl http://localhost:8888/ping
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

### Получение всех записей

```bash
curl http://localhost:8888/records
```

### Добавление записи

```bash
curl -X POST http://localhost:8888/records \
  -H 'Content-Type: application/json' \
  -d '{
    "timestep": "2099-12-31 22:00",
    "consumption_eur": 71000,
    "consumption_sib": 22100,
    "price_eur": 951.1,
    "price_sib": 611.5
  }'
```

### Удаление записи

```bash
curl -X DELETE http://localhost:8888/records/45817
```

## Хранение данных

В `docker-compose.yml` backend использует named volume `backend_data`.

Это означает:

- данные не теряются после обычного `docker compose down`
- изменения после `POST` и `DELETE` сохраняются
- данные удаляются только при `docker compose down -v`

Рабочий CSV внутри контейнера backend хранится по пути:

```text
/data/data.csv
```

## Проверка, что Docker работает корректно

### Быстрая проверка

```bash
docker compose up --build -d
docker compose ps
curl -sSf http://127.0.0.1:8888/ping
curl -sSf http://127.0.0.1:8889/_stcore/health
docker compose down
```

### Что должно получиться

- оба контейнера должны иметь статус `healthy`
- `GET /ping` должен вернуть `{"status":"ok"}`
- `/_stcore/health` должен вернуть `ok`

## Проверка кода и линтеры

Если используется виртуальное окружение:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pycodestyle flake8 "pylint>=4,<5"
```

### Тесты

```bash
python -m pytest -q tests
```

### Проверка кодстайла

Скрипт из задания:

```bash
python pycodestyle.py dashboard_shared.py
python pycodestyle.py backend/main.py
python pycodestyle.py frontend/app.py
python pycodestyle.py tests/conftest.py
python pycodestyle.py tests/test_backend.py
```

### Flake8

```bash
python -m flake8 \
  dashboard_shared.py \
  backend/main.py \
  frontend/app.py \
  tests/conftest.py \
  tests/test_backend.py \
  --max-line-length=120
```

### Pylint

Рекомендуется запускать через виртуальное окружение, а не через Anaconda base:

```bash
PYLINTHOME=/tmp/pylint python -m pylint \
  dashboard_shared.py \
  backend/main.py \
  frontend/app.py \
  tests/conftest.py \
  tests/test_backend.py \
  --max-line-length=120 \
  --disable="C0103,C0114,C0115"
```

### Hadolint для Dockerfile

```bash
cat Dockerfile.backend | docker run --rm -i hadolint/hadolint
cat Dockerfile.frontend | docker run --rm -i hadolint/hadolint
```

### ShellCheck

В текущей версии проекта `.sh` файлов нет, поэтому `shellcheck` не применяется.

## Примечание по окружению

Если `pylint` запускается из `Anaconda base`, возможен сбой из-за
несовместимой версии `astroid`. Поэтому для проверки проекта нужно
использовать команды вида:

```bash
python -m pylint ...
```

из активированного `.venv`.
