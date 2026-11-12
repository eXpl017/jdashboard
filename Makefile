install:
	uv sync --extra dev

# Host development server. Defaults to port 8001 so it never collides with
# the container, which publishes 8000 by default.
# Override with: make run DEV_PORT=8002
run:
	@uv run python scripts/check_port.py $${DEV_PORT:-8001} $${HOST:-127.0.0.1}
	uv run uvicorn app.main:app --reload --host $${HOST:-127.0.0.1} --port $${DEV_PORT:-8001}

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f dashboard

# One-shot checks used while verifying a change.
verify:
	uv run ruff check .
	uv run pytest -q
	uv run python scripts/check_port.py $${DEV_PORT:-8001}
