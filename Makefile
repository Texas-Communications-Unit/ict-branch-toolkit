.PHONY: setup up down reset test lint format docs check migrations schema

setup:
	cp .env.example .env
	docker compose build

up:
	docker compose up --build

down:
	docker compose down

reset:
	docker compose down --volumes --remove-orphans

test:
	docker compose run --rm backend pytest
	docker compose run --rm frontend pnpm exec vitest run

lint:
	docker compose run --rm backend ruff check .
	docker compose run --rm backend python manage.py check
	docker compose run --rm frontend pnpm lint
	docker compose run --rm frontend pnpm typecheck

format:
	docker compose run --rm backend ruff format .
	docker compose run --rm frontend pnpm format

docs:
	python scripts/check-markdown-links.py

migrations:
	docker compose run --rm backend python manage.py makemigrations --check --dry-run

schema:
	docker compose run --rm backend python manage.py spectacular --file openapi.yaml --validate

check: docs lint migrations test schema
	docker compose build
