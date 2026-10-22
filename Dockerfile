# --- сборка React-фронтенда ---
FROM node:22-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# тексты статей общие для фронтенда и сервера (frontend/src импортирует ../../../content)
COPY content /build/content
RUN npm run build

# --- Python-сервер ---
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py auth.py seo.py legal.py mailer.py normocontrol.py ./
COPY checker ./checker
COPY scripts ./scripts
COPY content ./content
COPY --from=frontend /build/frontend/dist ./frontend/dist

# Один процесс + потоки: ограничение попыток входа и кеш проверок живут в памяти процесса.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 120"]
