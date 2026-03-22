default:
    @just --list

sync:
    uv sync --dev

build:
    uv build

test:
    uv run pytest -p no:cacheprovider -q

lint:
    uv run ruff check .

fmt:
    uv run ruff format .

fmt-check:
    uv run ruff format --check .

typecheck:
    uv run ty check src tests

check:
    uv run ruff check .
    uv run ruff format --check .
    uv run ty check src tests
    uv run pytest -p no:cacheprovider -q

fix:
    uv run ruff check . --fix
    uv run ruff format .

hooks:
    uv run pre-commit install

pre-commit:
    uv run pre-commit run --all-files

publish-test:
    uv publish --index testpypi

publish:
    uv publish
