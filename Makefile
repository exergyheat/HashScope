# HashScope Makefile

.PHONY: help
help: ## Show this help message
	@echo "HashScope - Bitcoin Mining MITM Proxy"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: up
up: ## Start all services with docker-compose
	docker-compose up -d

.PHONY: down
down: ## Stop all services
	docker-compose down

.PHONY: logs
logs: ## Show logs from all services
	docker-compose logs -f

.PHONY: logs-backend
logs-backend: ## Show backend logs
	docker-compose logs -f backend

.PHONY: logs-frontend
logs-frontend: ## Show frontend logs
	docker-compose logs -f frontend

.PHONY: build
build: ## Build all Docker images
	docker-compose build

.PHONY: rebuild
rebuild: ## Rebuild all Docker images from scratch
	docker-compose build --no-cache

.PHONY: restart
restart: down up ## Restart all services

.PHONY: test-backend
test-backend: ## Run backend tests
	cd backend && pytest -q

.PHONY: lint-backend
lint-backend: ## Lint backend code
	cd backend && python -m pylint hashscope || true

.PHONY: lint-frontend
lint-frontend: ## Lint frontend code
	cd frontend && npm run lint

.PHONY: dev-backend
dev-backend: ## Run backend in development mode (requires POOL_HOST env var)
	cd backend && uvicorn hashscope.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000

.PHONY: dev-frontend
dev-frontend: ## Run frontend in development mode
	cd frontend && npm run dev

.PHONY: install-backend
install-backend: ## Install backend dependencies
	cd backend && pip install -r requirements.txt

.PHONY: install-frontend
install-frontend: ## Install frontend dependencies
	cd frontend && npm ci

.PHONY: clean
clean: ## Clean up generated files and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true

.PHONY: status
status: ## Show status of running containers
	docker-compose ps

.DEFAULT_GOAL := help

