FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    HOME=/tmp \
    TMPDIR=/tmp \
    UPLOAD_TEMP_DIR=/tmp/markforge

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        fonts-dejavu \
        libmagic1 \
        libreoffice-writer \
        pandoc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY wsgi.py .

RUN groupadd --gid 10001 markforge \
    && useradd --uid 10001 --gid 10001 --home-dir /tmp --shell /usr/sbin/nologin markforge \
    && mkdir -p /tmp/markforge \
    && chown -R markforge:markforge /tmp/markforge

USER 10001:10001

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:5000/api/v1/health || exit 1

CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "180", "--access-logfile", "-", "--error-logfile", "-"]
