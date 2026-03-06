# =============================================================================
# Makefile — text_to_sql_demo
# Usage: make <target>
# =============================================================================

.PHONY: help install install-react seed \
        dev dev-backend dev-react dev-mlflow dev-streamlit \
        start stop-local stop stop-clean \
        test test-backend test-coverage \
        eval eval-judge eval-credit eval-fraud \
        lint format \
        build build-backend build-react build-frontend push \
        k8s-deploy k8s-delete k8s-status \
        clean

BACKEND_DIR  := backend
FRONTEND_DIR := frontend          # legacy Streamlit UI
REACT_DIR    := nedcard-ui        # React / Vite UI  ← primary UI
DATA_DIR     := data
COMPOSE      := infra/docker/docker-compose.yml
VENV         := .venv/bin

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Environment ──────────────────────────────────────────────────────────────

install: ## Install backend + Streamlit Python deps into .venv
	$(VENV)/pip install -r $(BACKEND_DIR)/requirements.txt
	$(VENV)/pip install -r $(FRONTEND_DIR)/requirements.txt

install-react: ## Install React/Vite frontend npm dependencies
	cd $(REACT_DIR) && npm install

# ── Data ─────────────────────────────────────────────────────────────────────

seed: ## Generate synthetic data and seed the local SQLite database
	@echo "Generating synthetic datasets..."
	python $(DATA_DIR)/synthetic/generate_credit_data.py --rows 500 --seed 42
	python $(DATA_DIR)/synthetic/generate_fraud_data.py --rows 300 --seed 42
	python $(DATA_DIR)/synthetic/generate_social_data.py --rows 400 --seed 42
	python $(DATA_DIR)/synthetic/generate_speech_transcripts.py --rows 50 --seed 42
	@echo "Seeding database..."
	python $(DATA_DIR)/seed_db.py
	@echo "✅ Database seeded at data/seeds/dev.db"

# ── Local Development ─────────────────────────────────────────────────────────
# ⚠️  Startup order matters: MLflow MUST be running before the backend starts.
#     base_graph.py calls mlflow.set_experiment() at import time.
#     Correct order: dev-mlflow → dev-backend → dev-react

dev-mlflow: ## (1) Start MLflow on :5000 — run this FIRST
	$(VENV)/mlflow server \
		--backend-store-uri "sqlite:///$(PWD)/mlflow.db" \
		--default-artifact-root "$(PWD)/mlartifacts" \
		--port 5000 \
		--host 127.0.0.1

dev-backend: ## (2) Start FastAPI backend on :8000 (requires MLflow on :5000)
	PYTHONPATH=$(BACKEND_DIR) $(VENV)/python -m uvicorn app.main:app \
		--reload --port 8000 --app-dir $(BACKEND_DIR)

dev-react: ## (3) Start React/Vite UI on :3002 — primary chat interface
	cd $(REACT_DIR) && npm run dev -- --port 3002

dev-streamlit: ## Start legacy Streamlit UI on :8501 (optional)
	$(VENV)/streamlit run $(FRONTEND_DIR)/app.py --server.port 8501

start: ## Start MLflow + backend + React together (correct order, all backgrounded except React)
	@echo "⚡  Starting MLflow on :5000..."
	@$(VENV)/mlflow server \
		--backend-store-uri "sqlite:///$(PWD)/mlflow.db" \
		--default-artifact-root "$(PWD)/mlartifacts" \
		--port 5000 --host 127.0.0.1 &
	@sleep 3
	@echo "🚀  Starting FastAPI backend on :8000..."
	@PYTHONPATH=$(BACKEND_DIR) $(VENV)/python -m uvicorn app.main:app \
		--reload --port 8000 --app-dir $(BACKEND_DIR) &
	@sleep 2
	@echo "🎨  Starting React UI on :3002 (foreground — Ctrl+C to stop all)..."
	@cd $(REACT_DIR) && npm run dev -- --port 3002

stop-local: ## Kill all local dev processes (MLflow, backend, React/Vite)
	@echo "Stopping local services..."
	@pkill -f "uvicorn app.main" 2>/dev/null || true
	@pkill -f "vite" 2>/dev/null || true
	@pkill -f "mlflow server" 2>/dev/null || true
	@lsof -ti :8000,:3002,:5000 | xargs kill -9 2>/dev/null || true
	@echo "✅  All local services stopped (ports 8000, 3002, 5000 cleared)"

dev: ## Start all services via Docker Compose (Streamlit → :8501, MLflow → :5000)
	@if [ ! -f .env ]; then echo "❌ .env not found. Copy .env.example to .env and fill in your keys."; exit 1; fi
	docker compose -f $(COMPOSE) up --build

stop: ## Stop Docker Compose services
	docker compose -f $(COMPOSE) down

stop-clean: ## Stop Docker Compose and remove all volumes
	docker compose -f $(COMPOSE) down -v

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run full pytest suite
	pytest -v --tb=short

test-backend: ## Run backend tests only
	pytest backend/tests/ -v --tb=short

test-coverage: ## Run tests with coverage report
	pytest --cov=backend/app --cov-report=html --cov-report=term-missing

# ── Evaluation ────────────────────────────────────────────────────────────────

eval: ## Run batch evals against the live backend (deterministic metrics only)
	@echo "Running batch eval — requires backend and MLflow to be running"
	cd backend && python -m app.evals.harness --backend http://localhost:8000

eval-judge: ## Run batch evals with LLM-judge metrics (costs OpenAI tokens, ~1 min extra)
	@echo "Running batch eval with LLM judge — requires backend and MLflow to be running"
	cd backend && python -m app.evals.harness --backend http://localhost:8000 --judge

eval-credit: ## Run credit use-case evals only
	cd backend && python -m app.evals.harness --backend http://localhost:8000 --use-case credit

eval-fraud: ## Run fraud use-case evals only
	cd backend && python -m app.evals.harness --backend http://localhost:8000 --use-case fraud

# ── Code Quality ──────────────────────────────────────────────────────────────

lint: ## Run ruff linter
	ruff check $(BACKEND_DIR) $(FRONTEND_DIR) $(DATA_DIR)

format: ## Auto-format with ruff
	ruff format $(BACKEND_DIR) $(FRONTEND_DIR) $(DATA_DIR)
	ruff check --fix $(BACKEND_DIR) $(FRONTEND_DIR) $(DATA_DIR)

# ── Docker ────────────────────────────────────────────────────────────────────

build: ## Build all Docker images via Compose
	docker compose -f $(COMPOSE) build

build-backend: ## Build backend Docker image only
	docker build -t text-to-sql-backend:latest $(BACKEND_DIR)

build-react: ## Build React/Vite UI for production (outputs to nedcard-ui/dist/)
	cd $(REACT_DIR) && npm run build

build-frontend: ## Build legacy Streamlit frontend Docker image
	docker build -t text-to-sql-frontend:latest $(FRONTEND_DIR)

# ── Kubernetes (AKS) ─────────────────────────────────────────────────────────

k8s-deploy: ## Apply all Kubernetes manifests to current kubectl context
	kubectl apply -f infra/k8s/

k8s-delete: ## Remove all Kubernetes resources
	kubectl delete -f infra/k8s/

k8s-status: ## Show pod status
	kubectl get pods -l app=text-to-sql-demo

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean: ## Remove generated data, caches, compiled files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	rm -f data/seeds/dev.db
	rm -f mlflow.db && rm -rf mlartifacts mlruns
