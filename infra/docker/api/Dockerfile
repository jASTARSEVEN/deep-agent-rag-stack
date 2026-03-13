FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY apps/api /app

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["langgraph", "dev", "--config", "langgraph.json", "--host", "0.0.0.0", "--port", "8000", "--no-browser", "--no-reload"]
