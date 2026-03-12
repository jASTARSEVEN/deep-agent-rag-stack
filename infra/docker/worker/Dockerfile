FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY apps/worker /app

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

CMD ["celery", "-A", "worker.celery_app.celery_app", "worker", "--loglevel=INFO"]
