# Нормоконтроль

Веб-сервис автоматической проверки .docx/.pdf на соответствие ГОСТ 7.32-2017.
Два раздела: **ВКР** (`/vkr`) и **курсовая** (`/coursework`) — у каждого свой профиль норм.

## Запуск для разработки

```bash
pip install -r requirements.txt
python app.py                       # API на http://127.0.0.1:5000

cd frontend && npm install
npm run dev                         # React на http://localhost:5173 (проксирует /api на Flask)
```

## Продакшн (без Docker)

```bash
cd frontend && npm install && npm run build && cd ..
pip install -r requirements.txt
gunicorn app:app --bind 0.0.0.0:8080 --workers 2 --timeout 60
```

Flask раздаёт собранный фронтенд из `frontend/dist`.

## Docker

```bash
docker build -t normocontrol .
docker run -p 8080:8080 normocontrol
```

## CLI

```bash
python normocontrol.py работа.docx --type vkr
python normocontrol.py курсовая.pdf --type coursework
```

## Тесты

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

Тесты генерируют .docx/.pdf: эталон не должен давать замечаний, а каждое намеренное
нарушение — замечание в своей категории.

## Структура

```
app.py                  Flask: /api/profiles, /api/check, /api/report/<id>, раздача React
normocontrol.py         CLI
checker/norms.py        профили норм (ВКР, курсовая) — ЗДЕСЬ меняются числа под требования вуза
checker/docx_checks.py  проверки .docx
checker/docx_utils.py   вычисление фактического форматирования (стили → docDefaults)
checker/pdf_checks.py   проверки .pdf (по координатам, оценочно)
checker/typography.py   пробелы, пустые строки
checker/report.py       модель отчёта, HTML для скачивания
frontend/               React + Vite (react-router)
tests/                  pytest
```

## Нормы

Источник — ГОСТ 7.32-2017, раздел 6. Что ГОСТ требует прямо, а что — типовая практика вузов:

| Параметр | ГОСТ 7.32-2017 | В профиле |
|---|---|---|
| Поля | лев. 30, прав. 15, верх./нижн. 20 мм | правое допускается 10–15 мм |
| Шрифт | Times New Roman (рекомендуется), ≥ 12 пт, чёрный | ВКР — ровно 14 пт; курсовая — 12–14 пт |
| Интервал | полуторный | 1,5 |
| Абзацный отступ | 1,25 см | 1,25 см |
| Нумерация страниц | внизу по центру, без точки | проверяется |
| Заголовки структурных элементов | по центру, ПРОПИСНЫМИ, без точки, с новой страницы | проверяется |
| Заголовки разделов | полужирный, без точки, с новой страницы | проверяется |
| Подписи | «Рисунок N – Название» по центру под рисунком; «Таблица N – Название» слева над таблицей | проверяется |

Правило «в оглавлении жирным только заголовки верхнего уровня» в ГОСТ отсутствует —
это требование вуза, оставлено из прежней версии (`check_toc` в `docx_checks.py`).
