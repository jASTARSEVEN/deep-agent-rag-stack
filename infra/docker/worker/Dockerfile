FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONPATH=/app/src

# OpenDataLoader / Java runtime shared libraries.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        default-jre-headless \
        libxcb1 \
        libxext6 \
        libxrender1 \
        libsm6 \
        libglib2.0-0 \
        libgl1 && \
    rm -rf /var/lib/apt/lists/*

# 僅讓依賴層受 pyproject 變動影響，避免 README 或程式碼修改打破快取。
COPY apps/worker/pyproject.toml /app/
RUN pip install --upgrade pip && \
    python -c "import tomllib; f = open('pyproject.toml', 'rb'); data = tomllib.load(f); deps = data['project'].get('dependencies', []); print('\n'.join(deps))" > requirements.txt && \
    pip install -r requirements.txt

# OpenDataLoader 透過 Python 套件安裝執行期依賴；目前 compose 路徑要求 Java 11+。

# 複製應用程式原始碼；執行期透過 PYTHONPATH 載入，不在 image 內重跑 editable install。
COPY apps/worker /app

CMD ["celery", "-A", "worker.celery_app.celery_app", "worker", "--loglevel=INFO"]
