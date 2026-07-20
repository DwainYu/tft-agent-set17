# =============================================================================
# Makefile – TFT Agent Set17
# =============================================================================

.PHONY: up down logs build push deploy-kind test test-unit test-integration \
        test-eval lint fmt pre-commit help

# Default registry for push target
REGISTRY ?= ghcr.io/dwainyu/tft-agent-set17

# Kind cluster name
KIND_CLUSTER ?= tft-local

# ---------------------------------------------------------------------------
# Docker Compose
# ---------------------------------------------------------------------------

## up: Start all services in the background
up:
	docker compose up -d

## down: Stop and remove all services
down:
	docker compose down

## logs: Tail logs from all running services
logs:
	docker compose logs -f

## build: Build (or rebuild) all images
build:
	docker compose build

## push: Tag and push images to REGISTRY
push:
	docker compose push

# ---------------------------------------------------------------------------
# Kubernetes (kind) deployment
# ---------------------------------------------------------------------------

## deploy-kind: Create a kind cluster (if needed), build, load, and apply manifests
deploy-kind:
	@# Create the cluster only if it does not already exist
	@kind get clusters | grep -q "^$(KIND_CLUSTER)$$" || kind create cluster --name $(KIND_CLUSTER)
	docker build -t $(REGISTRY):latest .
	kind load docker-image $(REGISTRY):latest --name $(KIND_CLUSTER)
	kubectl apply -f k8s/

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

## test: Run the full test suite (all markers)
test:
	pytest

## test-unit: Run unit tests only
test-unit:
	pytest -m unit

## test-integration: Run integration tests only
test-integration:
	pytest -m integration

## test-eval: Run evaluation tests only
test-eval:
	pytest -m eval

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

## lint: Check code style with ruff
lint:
	ruff check .

## fmt: Auto-fix and format code with ruff
fmt:
	ruff check --fix .
	ruff format .

## pre-commit: Run all pre-commit hooks against every file
pre-commit:
	pre-commit run --all-files

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

## help: Show this message
help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@sed -n 's/^## //p' $(MAKEFILE_LIST) | column -t -s ':'
	@echo ""
