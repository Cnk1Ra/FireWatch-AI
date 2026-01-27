# ==============================================
# FIREWATCH AI - MAKEFILE
# ==============================================

.PHONY: help setup install run run-prod test lint format clean map docker

# Default target
help:
	@echo "🔥 FireWatch AI - Available Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup     - Create virtual environment and install dependencies"
	@echo "  make install   - Install dependencies only"
	@echo ""
	@echo "Development:"
	@echo "  make run       - Run API server (development mode with reload)"
	@echo "  make run-prod  - Run API server (production mode)"
	@echo "  make map       - Generate sample fire map"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test      - Run all tests"
	@echo "  make lint      - Check code style"
	@echo "  make format    - Format code with black and isort"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean     - Remove cache files and build artifacts"
	@echo "  make docker    - Build Docker image"
	@echo ""

# Setup virtual environment and install dependencies
setup:
	@echo "🔧 Setting up FireWatch AI..."
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	@if [ ! -f .env ]; then cp .env.example .env; fi
	@echo ""
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env and add your FIRMS_API_KEY"
	@echo "  2. Run: source venv/bin/activate"
	@echo "  3. Run: make run"
	@echo ""

# Install dependencies only
install:
	pip install -r requirements.txt

# Run development server
run:
	@echo "🚀 Starting FireWatch AI API..."
	@echo "📚 Documentation: http://localhost:8000/docs"
	@echo ""
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Run production server
run-prod:
	@echo "🚀 Starting FireWatch AI API (Production)..."
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Generate sample fire map
map:
	@echo "🗺️ Generating fire map..."
	python3 generate_map.py
	@echo "✅ Map saved to brazil_fire_map.html"
	@if command -v open &> /dev/null; then open brazil_fire_map.html; fi

# Run tests
test:
	@echo "🧪 Running tests..."
	pytest tests/ -v --tb=short

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term
	@echo "📊 Coverage report saved to htmlcov/index.html"

# Check code style
lint:
	@echo "🔍 Checking code style..."
	black --check src/ tests/
	isort --check-only src/ tests/
	mypy src/ --ignore-missing-imports

# Format code
format:
	@echo "🎨 Formatting code..."
	black src/ tests/
	isort src/ tests/
	@echo "✅ Code formatted"

# Clean cache and build artifacts
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	rm -rf dist/ build/ *.egg-info/
	@echo "✅ Cleaned"

# Build Docker image
docker:
	@echo "🐳 Building Docker image..."
	docker build -t firewatch-ai:latest -f docker/Dockerfile .
	@echo "✅ Image built: firewatch-ai:latest"

# Run with Docker Compose
docker-up:
	docker-compose -f docker/docker-compose.yml up -d
	@echo "✅ FireWatch AI running at http://localhost:8000"

docker-down:
	docker-compose -f docker/docker-compose.yml down

# Download static data files
download-data:
	@echo "📥 Downloading static data..."
	python3 scripts/download_static_data.py
	@echo "✅ Data downloaded"

# Check environment
check-env:
	@echo "🔍 Checking environment..."
	@python3 -c "import sys; print(f'Python: {sys.version}')"
	@python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; key=os.getenv('FIRMS_API_KEY',''); print(f'FIRMS_API_KEY: {\"configured\" if key else \"NOT SET\"}')"
