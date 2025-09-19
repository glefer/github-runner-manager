# Makefile for GitHub Runner Manager

# Prefer project-local Poetry if available (e.g., when using a venv-managed binary)
POETRY := $(shell [ -x .venv/bin/poetry ] && echo .venv/bin/poetry || which poetry)

.PHONY: help install test test-v test-durations test-parallel test-cov test-cov-html run build-images start-runners stop-runners remove-runners list-runners check-update build all

help:
	@echo "GitHub Runner Manager commands:"
	@echo "  make install        - Install dependencies with Poetry"
	@echo "  make test           - Run tests"
	@echo "  make test-v         - Run tests (verbose)"
	@echo "  make test-durations - Run tests and show slowest durations"
	@echo "  make test-parallel  - Run tests in parallel if pytest-xdist is installed"
	@echo "  make test-cov       - Run tests with coverage (term-missing)"
	@echo "  make test-cov-html  - Run tests with coverage and generate HTML report"
	@echo "  make run            - Show help"
	@echo "  make build-images   - Build runner Docker images"
	@echo "  make start-runners  - Start all runners"
	@echo "  make stop-runners   - Stop all runners"
	@echo "  make remove-runners - Remove all runners"
	@echo "  make list-runners   - List all runners and their status"
	@echo "  make check-update   - Check for base image updates"

install:
	$(POETRY) install


test:
	$(POETRY) run pytest -q

test-durations:
	$(POETRY) run pytest -q --durations=10

test-cov:
	$(POETRY) run pytest -q --cov=src --cov-report=term-missing --cov-branch

test-cov-html:
	$(POETRY) run pytest -q --cov=src --cov-report=html
	@echo "Coverage HTML report generated at htmlcov/index.html"

run:
	$(POETRY) run python main.py --help

build-images:
	$(POETRY) run python main.py build-runners-images

start-runners:
	$(POETRY) run python main.py start-runners

stop-runners:
	$(POETRY) run python main.py stop-runners

remove-runners:
	$(POETRY) run python main.py remove-runners

list-runners:
	$(POETRY) run python main.py list-runners

check-update:
	$(POETRY) run python main.py check-base-image-update

build: check-update build-images

all: install build start-runners list-runners