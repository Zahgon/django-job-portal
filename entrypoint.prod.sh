#!/bin/bash
# Bring the schema up to date, then serve the application behind gunicorn.
set -euo pipefail

alembic upgrade head
exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000
