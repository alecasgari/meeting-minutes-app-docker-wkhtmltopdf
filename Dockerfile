FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PUPPETEER_CACHE_DIR=/var/cache/pyppeteer \
    PYPPETEER_HOME=/var/cache/pyppeteer

# System deps for Chromium/pyppeteer and fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget fonts-liberation \
    libasound2 libatk1.0-0 libcairo2 libgbm1 libgtk-3-0 \
    libnss3 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libxshmfence1 libxi6 libxss1 libxkbcommon0 \
    libcups2 libdrm2 libpangocairo-1.0-0 libpango-1.0-0 \
    fonts-noto fonts-noto-cjk fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache dir for pyppeteer Chromium
RUN mkdir -p /var/cache/pyppeteer && useradd -ms /bin/bash appuser

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# Persistent data dir for sqlite/uploads
RUN mkdir -p /data && chown -R appuser:appuser /app /data /var/cache/pyppeteer
USER appuser

# Pre-download Chromium for pyppeteer at build-time to avoid runtime fetch
RUN python - <<'PY'
import asyncio, sys
from pyppeteer import chromium_downloader as cd

async def main():
    try:
        ok = cd.check_chromium()
        if not ok:
            path = await cd.download_chromium()
            print('Downloaded Chromium to:', path)
        print('Chromium executable:', cd.chromium_executable())
    except Exception as e:
        print('WARN: Chromium predownload failed:', e, file=sys.stderr)

asyncio.run(main())
PY

EXPOSE 8000

# Gunicorn server (threads for I/O, longer timeout for PDF generation)
CMD gunicorn app:app -b 0.0.0.0:8000 --workers 3 --threads 2 --timeout 120


