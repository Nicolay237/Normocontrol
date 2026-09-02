# Боевой снимок интеграции Study Platform

Эта папка содержит исходники нормоконтроля, которые работают в Study Platform.
Они скопированы без адаптации из ревизий, запущенных на сервере:

- backend: `d9de090ce931d8a2f80a872ceecf2aab65907608`;
- frontend: `19061caa9d46339c301e4a5234a353c63d406e3f`.

Корень этой ветки — внешний сервис проверки документов. Контрольные суммы его
основных файлов совпадают с файлами внутри боевого контейнера:

```text
5658425af7f58bf05dc7f20cb9c6d7b4429fd7d2f204d9be9fa508f3b964434d  app.py
95fced0d1393bf3f8e166e8be2908184546cc7590e0dc6d0fe85cbe5fe2c121d  normocontrol.py
```

## Состав

- `backend/src/app/normocontrol/` — очередь, кеш, права доступа, история и
  обработка сбоев;
- `backend/migrations/versions/0023_normocontrol.py` — схема базы данных;
- `backend/tests/unit/test_normocontrol_*.py` — тесты интеграции;
- `backend/compose.yaml` и `backend/scripts/normocontrol-source.sh` — подключение
  отдельного checker-контейнера;
- `frontend/src/pages/materials/components/normocontrol-panel/` — боевая панель,
  таблицы отчёта и анимации состояний;
- `frontend/src/pages/materials/use-normocontrol.ts` — запросы, загрузка файлов и
  обновления статусов в реальном времени.

Файлы в `backend/` и `frontend/` являются снимком частей двух приложений и
зависят от остального кода Study Platform. Они предназначены для переноса или
сравнения с полной платформой; самостоятельно эти две папки не собираются.
