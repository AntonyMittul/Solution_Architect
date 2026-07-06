# Development commands. On Windows without make, run the underlying commands directly.

.PHONY: up down api worker web migrate check test smoke

up:            ## start postgres + redis for local dev
	docker compose up -d postgres redis

down:
	docker compose down

api:           ## run the API with hot reload (needs `make up`)
	cd backend && uv run uvicorn aisa.platform.app:app --reload --port 8000

worker:        ## run the job worker (needs `make up`)
	cd backend && uv run python -m aisa.platform.worker

web:
	cd web && npm run dev

migrate:
	cd backend && uv run alembic upgrade head

check:         ## all backend quality gates (same as CI)
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports

test:
	cd backend && uv run pytest -q

smoke:         ## walking-skeleton smoke test against a running api+worker
	cd backend && uv run python scripts/smoke.py
