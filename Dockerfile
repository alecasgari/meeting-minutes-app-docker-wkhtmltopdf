FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps for wkhtmltopdf and fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget fonts-liberation \
    wkhtmltopdf \
    fonts-noto fonts-noto-cjk fonts-noto-color-emoji \
    fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create app user
RUN useradd -ms /bin/bash appuser

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# Persistent data dir for sqlite/uploads
RUN mkdir -p /data && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

# Gunicorn server (threads for I/O, longer timeout for PDF generation)
CMD gunicorn app:app -b 0.0.0.0:8000 --workers 3 --threads 2 --timeout 120


