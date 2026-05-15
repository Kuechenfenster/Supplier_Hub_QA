FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir pandas openpyxl

COPY backend/ ./backend/
COPY static/ ./static/
COPY index.html ./

RUN mkdir -p backend/data/incoming/boms backend/data/documents backend/data/processed backend/data/reports backend/db

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENV BASE_DIR=/app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/api/health')" || exit 1

EXPOSE 9000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "backend/main.py"]