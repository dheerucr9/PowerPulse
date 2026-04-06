FROM node:18-slim AS frontend
WORKDIR /app/frontend
# Install node deps with a platform/arch that matches the actual build container
# (avoids esbuild "Exec format error" when the host and build arch differ)
COPY frontend/package*.json ./
RUN ARCH=$(uname -m); \
    case "$ARCH" in \
      x86_64) NPM_ARCH=x64 ;; \
      aarch64) NPM_ARCH=arm64 ;; \
      armv7l) NPM_ARCH=arm ;; \
      *) NPM_ARCH=$ARCH ;; \
    esac; \
    npm_config_arch=$NPM_ARCH npm_config_platform=linux npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY --from=frontend /app/static/dist ./static/dist

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
