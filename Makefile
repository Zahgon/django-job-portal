.DEFAULT_GOAL := dev

dev:
	alembic upgrade head && uvicorn app.main:app --reload

migrate:
	alembic upgrade head

revision:
	alembic revision -m "$(m)"

test:
	pytest -q

bi:
	isort . && black .
