FROM python:3.11-slim

WORKDIR /app

# Solo dependencias de ejecucion; pytest y httpx viven en requirements-dev.txt.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

# La API no necesita privilegios de root dentro del contenedor.
RUN useradd --system --no-create-home --uid 10001 gymkeep
USER gymkeep

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
