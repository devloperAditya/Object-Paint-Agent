.PHONY: install run test lint format docker-build docker-up docker-down clean

install:
	uv sync || pip install -e ".[dev]"

run:
	uv run python -m app.main || python -m app.main

test:
	uv run pytest tests/ -v || pytest tests/ -v

lint:
	ruff check app tests scripts

format:
	ruff format app tests scripts

docker-build:
	docker compose build

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf .ruff_cache .pytest_cache __pycache__ app/__pycache__ app/**/__pycache__ tests/__pycache__
	rm -rf data/ models/
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
