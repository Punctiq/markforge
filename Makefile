# ── MarkForge · Makefile ───────────────────────────────────────────────────────
.PHONY: install install-dev run test lint format clean

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

run:
	FLASK_ENV=development flask --app wsgi:app run --reload --port 5000

test:
	pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	ruff check app/ tests/
	mypy app/ --ignore-missing-imports

format:
	black app/ tests/
	ruff check --fix app/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage