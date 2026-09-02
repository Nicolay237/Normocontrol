# Нормоконтроль

Веб-сервис автоматической проверки .docx/.pdf на соответствие ГОСТ 7.32-2017.

Бэкенд (Flask) отвечает за разбор документа и отдаёт результат в виде JSON;
весь интерфейс — отдельное production-приложение на React + TypeScript (Vite).

## Локальная разработка

Нужны два процесса: API-сервер и dev-сервер фронтенда с горячей перезагрузкой.

```bash
# терминал 1 — API
pip install -r requirements.txt
python app.py                 # http://127.0.0.1:5000

# терминал 2 — фронтенд (проксирует /api на 5000, см. frontend/vite.config.ts)
cd frontend
npm install
npm run dev                   # http://127.0.0.1:5173
```

Откройте http://127.0.0.1:5173 — это адрес для разработки.

## Продакшн-сборка

Фронтенд собирается один раз в статику, после чего Flask раздаёт её сам —
отдельный Node-процесс в проде не нужен.

```bash
cd frontend && npm install && npm run build && cd ..
pip install -r requirements.txt
gunicorn app:app --bind 0.0.0.0:8080 --workers 2 --timeout 60
```

Flask ищет собранный фронтенд в `frontend/dist`. Если запустить `app.py` без
предварительной сборки — API продолжит работать, но `/` вернёт 404.

## Запуск в Docker

`Dockerfile` собирает фронтенд в отдельном стейдже и упаковывает его вместе с
Flask-приложением в один образ — снаружи не видно, что это два разных стека.

```bash
docker build -t normocontrol .
docker run -p 8080:8080 normocontrol
```

## Структура проекта

```
app.py                    — Flask-сервер: API /api/check (JSON) + раздача frontend/dist
normocontrol.py           — логика проверки docx/pdf (не изменялась) + CLI (main())
frontend/                 — React + TypeScript (Vite) SPA
  src/api/                — типы и клиент для /api/check (XHR с прогрессом загрузки)
  src/hooks/               — useDocumentCheck: состояние проверки (idle/uploading/processing/success/error)
  src/components/          — NavBar, Hero, Uploader, FeatureGrid, LoadingState, ReportView, Footer
  src/lib/                 — валидация файла, форматирование дат/чисел
requirements.txt
Procfile                  — для Render/Railway/Heroku-подобных платформ (нужен build-шаг для frontend, см. ниже)
Dockerfile                — многостейдж-сборка: Node (frontend) → Python (сервис)
```

## API

`POST /api/check` — multipart-форма с полем `file` (`.docx` или `.pdf`, до 20 МБ).

Успешный ответ:

```json
{
  "filename": "diplom.docx",
  "generatedAt": "2026-09-02T08:16:15.234441+00:00",
  "isClean": false,
  "totalIssues": 5,
  "notes": ["..."],
  "categories": [
    { "name": "Поля страницы", "issues": [{ "location": "Раздел документа №1", "message": "..." }] }
  ]
}
```

Ошибка (400/413/422/500): `{"error": "..."}`.

## Деплой на платформах без Docker (Render/Railway)

Если хостинг не использует `Dockerfile`, добавьте сборку фронтенда в build-команду
платформы перед запуском `Procfile`, например:

```
cd frontend && npm ci && npm run build && cd .. && pip install -r requirements.txt
```
