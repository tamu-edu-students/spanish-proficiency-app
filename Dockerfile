# ── Stage 1: build the React frontend ───────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Django + Channels app served by Daphne ─────────────
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY manage.py .
COPY backend/ ./backend/
COPY spanish/ ./spanish/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN python manage.py collectstatic --noinput

EXPOSE 8080
CMD daphne -b 0.0.0.0 -p ${PORT:-8080} backend.asgi:application
