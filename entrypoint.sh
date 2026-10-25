#!/bin/sh
set -e
# Seed once, before workers start, so that several workers never race on the same bootstrap.
python -m radar.cli init
export RADAR_SEED_ON_START=0
exec gunicorn wsgi:app --bind 0.0.0.0:8000 --workers "${WEB_WORKERS:-2}" --threads 4 --timeout 120 --access-logfile -
