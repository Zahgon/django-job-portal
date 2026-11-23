#!/bin/bash
# Bring the schema up to date, then serve the application.
set -euo pipefail

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
