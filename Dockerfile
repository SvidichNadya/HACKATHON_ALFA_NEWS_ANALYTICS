FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install -r requirements.lock
COPY radar ./radar
COPY static ./static
COPY templates ./templates
COPY data ./data
COPY wsgi.py entrypoint.sh ./
RUN useradd -r -u 10001 radar && mkdir -p /app/var && chown -R radar /app/var && chmod +x entrypoint.sh
USER radar
ENV RADAR_DB_PATH=/app/var/radar.sqlite3
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=4s --start-period=20s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"
ENTRYPOINT ["./entrypoint.sh"]
