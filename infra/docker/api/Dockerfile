FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONPATH=/app/src

# 僅讓依賴層受 pyproject 變動影響，避免 README 或程式碼修改打破快取。
COPY apps/api/pyproject.toml /app/
RUN pip install --upgrade pip && \
    python -c "import tomllib; f = open('pyproject.toml', 'rb'); data = tomllib.load(f); deps = data['project'].get('dependencies', []); print('\n'.join(deps))" > requirements.txt && \
    pip install -r requirements.txt

# 複製應用程式原始碼；執行期透過 PYTHONPATH 載入，不在 image 內重跑 editable install。
COPY apps/api /app

EXPOSE 8000

CMD ["langgraph", "dev", "--config", "langgraph.json", "--host", "0.0.0.0", "--port", "8000", "--no-browser", "--no-reload"]
