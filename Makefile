.PHONY: lint build test help install dev clean

pre-ci: fmt lint test ## run this before committing

fmt: ## run formatting and lint fixes
	uv run --extra lint black .
	uv run --extra lint ruff check --fix .

lint: ## run lint checkers
	uv run --extra lint ruff check .
	uv run --extra lint black --check --diff .
	uv run --extra lint mypy --check-untyped-defs src/myai

dev: ## install cli in development mode
	pip install -e .

build: ## build project
	uv build

install: ## install the built package
	uv pip install --find-links=./dist myai

test: ## run tests
	uv run --extra test pytest --cov=./src -vvv -n auto --cov-report term-missing tests/

clean: ## clean build artifacts
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

help: ## shows this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
