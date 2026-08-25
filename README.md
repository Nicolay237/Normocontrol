# Нормоконтроль

Веб-сервис автоматической проверки .docx/.pdf на соответствие ГОСТ 7.32-2017.

## Локальный запуск

```bash
pip install -r requirements.txt
python app.py
```

Откройте http://127.0.0.1:5000

## Продакшн-запуск (без Docker)

```bash
pip install -r requirements.txt
gunicorn app:app --bind 0.0.0.0:8080 --workers 2 --timeout 60
```

## Запуск в Docker

```bash
docker build -t normocontrol .
docker run -p 8080:8080 normocontrol
```

## Структура проекта

```
app.py                 — Flask-сервер (страница + API /api/check)
normocontrol.py         — логика проверки docx/pdf (без изменений в поведении)
templates/index.html    — лендинг
static/css/style.css    — стили сайта
static/js/main.js       — загрузка файла и вывод результата без перезагрузки страницы
requirements.txt
Procfile                 — для Render/Railway/Heroku-подобных платформ
Dockerfile               — для контейнерного хостинга
```
