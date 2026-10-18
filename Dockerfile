# --- сборка React-фронтенда ---
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Python-сервер ---
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py auth.py normocontrol.py ./
COPY checker ./checker
COPY --from=frontend /build/dist ./frontend/dist

# Один процесс + потоки: отчёты и исправленные файлы для скачивания хранятся в памяти процесса,
# с несколькими процессами запрос на скачивание мог бы попасть в другой процесс (404).
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 120"]
