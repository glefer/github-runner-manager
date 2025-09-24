# Makefile for GitHub Runner Manager
# Prefer project-local Poetry if available (e.g., when using a venv-managed binary)
POETRY := $(shell [ -x .venv/bin/poetry ] && echo .venv/bin/poetry || which poetry)

.PHONY: help install test test-v test-durations test-parallel test-cov test-cov-html run build-images start-runners stop-runners remove-runners list-runners check-update build all pre-commit

# Each target should be documented with a comment starting with '##'
help:
    @echo "Available commands:"; \
    awk 'BEGIN {FS = ":|##"} /^[a-zA-Z0-9][^:]*:.*##/ {printf "  %-18s %s\n", $$1, $$3}' $(MAKEFILE_LIST)

install:        ## Install dependencies with Poetry
	$(POETRY) install

test:           ## Run tests
	$(POETRY) run pytest -q

test-durations: ## Run tests and show slowest durations
	$(POETRY) run pytest -q --durations=10

test-cov:       ## Run tests with coverage (term-missing)
	$(POETRY) run pytest -q --cov=src --cov-report=term-missing --cov-branch

test-cov-html:  ## Run tests with coverage and generate HTML report
	$(POETRY) run pytest -q --cov=src --cov-report=html
	@echo "Coverage HTML report generated at htmlcov/index.html"

test-v:         ## Run tests (verbose)
	$(POETRY) run pytest -v

test-parallel:  ## Run tests in parallel if pytest-xdist is installed
	$(POETRY) run pytest -n auto

run:            ## Show help
	$(POETRY) run python main.py --help

build-images:   ## Build runner Docker images
	$(POETRY) run python main.py build-runners-images

start-runners:  ## Start all runners
	$(POETRY) run python main.py start-runners

stop-runners:   ## Stop all runners
	$(POETRY) run python main.py stop-runners

remove-runners: ## Remove all runners
	$(POETRY) run python main.py remove-runners

list-runners:   ## List all runners and their status
	$(POETRY) run python main.py list-runners

check-update:   ## Check for base image updates
	$(POETRY) run python main.py check-base-image-update

pre-commit:     ## Run pre-commit hooks on all files
	$(POETRY) run pre-commit run --all-files

build:          ## Check for updates and build images
	$(MAKE) check-update
	$(MAKE) build-images

all:            ## Install, build, and start runners
	$(MAKE) install
	$(MAKE) build
	$(MAKE) start-runners
	$(MAKE) list-runners