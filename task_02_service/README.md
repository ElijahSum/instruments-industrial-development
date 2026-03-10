# Мини-дашборд рынка электроэнергии

Приложение состоит из двух частей:

- `backend/main.py` — FastAPI API для чтения, добавления и удаления записей в CSV.
- `frontend/app.py` — Streamlit UI, который работает только через API.

Исходный датасет лежит в `backend/RU_Electricity_Market_PZ_dayahead_price_volume.csv` (изначально лежал). При первом запуске backend нормализует его в `backend/data.csv`, добавляет столбец `id` и сохраняет изменения обратно в CSV. Поэтому в засабмиченной версии лежит файл `data.csv`. Возможно чтобы перезапустить код вам потребуется переименовать файл обратно.

## Структура проекта - прям как в структуре в презентации описано :)

```text
instruments_homework2/
├── backend/
│   ├── main.py
│   ├── data.csv
│   └── RU_Electricity_Market_PZ_dayahead_price_volume.csv
├── frontend/
│   └── app.py
├── tests/
│   └── test_backend.py
├── README.md
├── render.yaml
└── requirements.txt
```

## ВАЖНО: ЧТОБЫ ПРОВЕРИТЬ ЛОКАЛЬНО, НУЖНО ИЗМЕНИТЬ 23 СТРОЧКУ В ФАЙЛЕ С БЕКЭНДОМ!

## Установка (не все из этого обязательно)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Локальный запуск

1. Запустите backend:

```bash
uvicorn backend.main:app --reload
```

2. В отдельном терминале запустите Streamlit (я не смог придумать как все параллельно запустить, приходится два терминала включать):

```bash
streamlit run frontend/app.py
```

По умолчанию UI использует путь `http://127.0.0.1:8000`, но это можно изменить в коде.

## Переменные окружения

- `DATA_PATH` — путь к рабочему CSV-файлу. По умолчанию `backend/data.csv`.
- `SEED_DATA_PATH` — путь к исходному CSV. По умолчанию `backend/RU_Electricity_Market_PZ_dayahead_price_volume.csv`.
- `API_URL` — адрес backend API для Streamlit. По умолчанию `http://127.0.0.1:8000`.
- `CORS_ORIGINS` — список разрешённых origin через запятую для frontend. По умолчанию локальные Streamlit origin.
- `API_TIMEOUT` — таймаут запросов из Streamlit в секундах.

## API

### `GET /records`

Возвращает все записи из CSV вместе с `id`.

### `POST /records`

Добавляет новую запись.

Пример тела запроса:

```json
{
  "timestep": "2011-11-23 00:00",
  "consumption_eur": 72100,
  "consumption_sib": 21450,
  "price_eur": 980.35,
  "price_sib": 615.2
}
```

### `DELETE /records/{id}`

Удаляет запись по `id`.

## Проверка

```bash
pytest
```

## Деплой

### Backend НЕ НА RENDER, использовал модный Railway

Ссылка на Streamlit Cloud: https://instruments-industrial-development-uvomhkwavuqeyw6t7psy3n.streamlit.app
Ссылка на деплой бека: instruments-industrial-development-production.up.railway.app



После этого UI будет работать с удалённым backend через API.
