# Makefile for Elasticsearch Index Manager
.PHONY: help setup test test-unit test-integration clean start-es stop-es

# Default target
help:
	@echo "Elasticsearch Index Manager - Available targets:"
	@echo "  setup           - Set up environment (venv + Docker)"
	@echo "  test            - Run all tests"
	@echo "  test-unit       - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  start-es        - Start Elasticsearch in Docker"
	@echo "  stop-es         - Stop Elasticsearch"
	@echo "  clean           - Clean up everything"
	@echo "  install         - Install dependencies in venv"

# Setup environment
setup:
	@echo "Setting up test environment..."
	./run_tests.sh setup

# Run all tests
test:
	@echo "Running all tests..."
	./run_tests.sh test

# Run unit tests only
test-unit:
	@echo "Running unit tests..."
	@if [ -d "venv" ]; then \
		source venv/bin/activate && python test_elasticsearch_manager.py; \
	else \
		echo "Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi

# Run integration tests only
test-integration:
	@echo "Running integration tests..."
	@if [ -d "venv" ]; then \
		source venv/bin/activate && RUN_INTEGRATION_TESTS=true python test_elasticsearch_manager.py; \
	else \
		echo "Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi

# Run pytest with coverage
test-pytest:
	@echo "Running pytest with coverage..."
	@if [ -d "venv" ]; then \
		source venv/bin/activate && pytest test_pytest.py -v --cov=elasticsearch_index_manager --cov-report=term-missing; \
	else \
		echo "Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi

# Start Elasticsearch
start-es:
	@echo "Starting Elasticsearch..."
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose up -d; \
	elif docker compose version >/dev/null 2>&1; then \
		docker compose up -d; \
	else \
		echo "Docker Compose not found"; \
		exit 1; \
	fi

# Stop Elasticsearch
stop-es:
	@echo "Stopping Elasticsearch..."
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose down -v; \
	elif docker compose version >/dev/null 2>&1; then \
		docker compose down -v; \
	else \
		echo "Docker Compose not found"; \
		exit 1; \
	fi

# Install dependencies
install:
	@echo "Installing dependencies..."
	@if [ ! -d "venv" ]; then \
		python3 -m venv venv; \
	fi
	@source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# Clean up
clean:
	@echo "Cleaning up..."
	./run_tests.sh cleanup
	rm -rf venv
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -f .coverage
	rm -f elasticsearch_manager.log

# Development targets
dev-setup: install start-es
	@echo "Development environment ready!"

lint:
	@if [ -d "venv" ]; then \
		source venv/bin/activate && python -m flake8 elasticsearch_index_manager.py test_*.py; \
	else \
		echo "Virtual environment not found. Run 'make install' first."; \
	fi
