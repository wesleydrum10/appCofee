FROM node:22-bookworm-slim AS assets
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system app \
    && useradd --system --gid app --create-home app

COPY --chown=app:app . .
COPY --from=assets --chown=app:app /build/static/css/tailwind.css /app/static/css/tailwind.css
RUN mkdir -p /app/media /app/staticfiles \
    && chown app:app /app/media /app/staticfiles \
    && chmod +x /app/docker/entrypoint.sh

USER app
# Build sem banco, variáveis de produção ou segredos; não ficam no ambiente final.
RUN DEBUG=True python manage.py collectstatic --noinput
EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
