#!/bin/sh
set -eu

log() {
  printf '[startup] %s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

on_exit() {
  status=$?
  if [ "$status" -ne 0 ]; then
    printf '[startup] %s FAILED (exit=%s); inspect preceding log lines\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$status" >&2
  else
    log "Startup command finished."
  fi
}
trap on_exit EXIT

log "Container entrypoint started."
log "Checking Django settings and installed apps..."
python manage.py check

log "Applying database migrations..."
python manage.py migrate --noinput

log "Loading demo data (idempotent command)..."
python manage.py seed_demo

log "Collecting static assets..."
python manage.py collectstatic --noinput

log "Starting Gunicorn; access/error logs will be written to container stdout/stderr."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --graceful-timeout 30 \
  --access-logfile - \
  --error-logfile - \
  --capture-output \
  --log-level "${GUNICORN_LOG_LEVEL:-info}"
