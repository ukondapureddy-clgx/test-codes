#!/bin/bash

# Elasticsearch Index Manager Test Setup Script
# This script sets up the test environment with Docker and virtual environment

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

echo "=========================================="
echo "Elasticsearch Index Manager Test Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed and running
check_docker() {
    print_status "Checking Docker installation..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    print_status "Docker is installed and running ✓"
}

# Check if Docker Compose is available
check_docker_compose() {
    print_status "Checking Docker Compose..."
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    else
        print_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    print_status "Docker Compose is available ✓"
}

# Setup Python virtual environment
setup_venv() {
    print_status "Setting up Python virtual environment..."
    
    cd "$PROJECT_DIR"
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Removing old one..."
        rm -rf venv
    fi
    
    python3 -m venv venv
    source venv/bin/activate
    
    print_status "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Install additional test dependencies
    pip install pytest pytest-cov pytest-mock
    
    print_status "Virtual environment setup complete ✓"
}

# Start Elasticsearch in Docker
start_elasticsearch() {
    print_status "Starting Elasticsearch in Docker..."
    
    cd "$PROJECT_DIR"
    
    # Stop any existing containers
    $DOCKER_COMPOSE_CMD down -v 2>/dev/null || true
    
    # Start Elasticsearch
    $DOCKER_COMPOSE_CMD up -d
    
    print_status "Waiting for Elasticsearch to be ready..."
    
    # Wait for Elasticsearch to be healthy
    max_attempts=60
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -u elastic:testpassword123 http://localhost:9200/_cluster/health?wait_for_status=yellow&timeout=1s > /dev/null 2>&1; then
            print_status "Elasticsearch is ready ✓"
            break
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "Elasticsearch failed to start within timeout"
        print_error "Check logs with: $DOCKER_COMPOSE_CMD logs elasticsearch"
        exit 1
    fi
    
    # Display cluster info
    print_status "Elasticsearch cluster information:"
    curl -s -u elastic:testpassword123 http://localhost:9200/_cluster/health | python3 -m json.tool
}

# Run tests
run_tests() {
    print_status "Running tests..."
    
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    print_status "Running unit tests..."
    python test_elasticsearch_manager.py
    
    print_status "Running integration tests..."
    RUN_INTEGRATION_TESTS=true python test_elasticsearch_manager.py
    
    print_status "Running pytest with coverage..."
    pytest test_elasticsearch_manager.py -v --cov=elasticsearch_index_manager --cov-report=term-missing
}

# Cleanup function
cleanup() {
    print_status "Cleaning up..."
    cd "$PROJECT_DIR"
    $DOCKER_COMPOSE_CMD down -v 2>/dev/null || true
    print_status "Cleanup complete ✓"
}

# Main execution
main() {
    case "${1:-all}" in
        "setup")
            check_docker
            check_docker_compose
            setup_venv
            start_elasticsearch
            ;;
        "test")
            run_tests
            ;;
        "cleanup")
            cleanup
            ;;
        "all")
            check_docker
            check_docker_compose
            setup_venv
            start_elasticsearch
            run_tests
            ;;
        *)
            echo "Usage: $0 [setup|test|cleanup|all]"
            echo "  setup   - Set up environment (venv, Docker)"
            echo "  test    - Run tests only"
            echo "  cleanup - Stop Docker containers"
            echo "  all     - Complete setup and test run (default)"
            exit 1
            ;;
    esac
}

# Trap to cleanup on script exit
trap cleanup EXIT

# Run main function
main "$@"

print_status "=========================================="
print_status "Test setup and execution complete!"
print_status "=========================================="
