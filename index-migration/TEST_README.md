# Elasticsearch Index Manager Test Environment

This directory contains a comprehensive test suite for the Elasticsearch Index Manager with Docker-based Elasticsearch and Python virtual environment setup.

## Test Structure

```
src/py/
├── elasticsearch_index_manager.py    # Main application
├── test_elasticsearch_manager.py     # Unit tests (unittest framework)
├── test_pytest.py                   # Integration tests (pytest framework)
├── conftest.py                      # Pytest configuration and fixtures
├── docker-compose.yml              # Elasticsearch Docker setup
├── run_tests.sh                    # Test automation script
└── requirements.txt                # Python dependencies including test tools
```

## Quick Start

### Automated Test Run
```bash
chmod +x run_tests.sh
./run_tests.sh
```

This will:
1. Check Docker installation
2. Set up Python virtual environment
3. Start Elasticsearch in Docker
4. Run all tests
5. Clean up resources

### Manual Setup

#### 1. Start Elasticsearch
```bash
docker-compose up -d
```

#### 2. Set up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. Run Tests
```bash
# Unit tests only
python test_elasticsearch_manager.py

# Integration tests
RUN_INTEGRATION_TESTS=true python test_elasticsearch_manager.py

# Pytest with coverage
pytest test_pytest.py -v --cov=elasticsearch_index_manager --cov-report=term-missing
```

## Test Categories

### Unit Tests (`test_elasticsearch_manager.py`)
- **Configuration Testing**: Validates ElasticsearchConfig class
- **CSV Loading**: Tests CSV parsing and validation
- **Dry Run Operations**: Ensures dry-run mode works correctly
- **Settings Cleaning**: Tests removal of system-generated fields
- **Error Handling**: Tests graceful handling of various error conditions

### Integration Tests (`test_pytest.py`)
- **Real Elasticsearch Operations**: Tests against actual Elasticsearch instance
- **Complete Workflows**: End-to-end testing of reindex operations
- **Document Validation**: Verifies data integrity after operations
- **Error Scenarios**: Tests behavior with non-existent indices

## Docker Configuration

The `docker-compose.yml` sets up:
- **Elasticsearch 8.9.0** with security enabled
- **Credentials**: `elastic:testpassword123`
- **Ports**: 9200 (HTTP), 9300 (Transport)
- **Health Checks**: Automatic readiness detection
- **Memory**: 512MB heap size for testing

## Test Features

### Fixtures and Mocking
- **elasticsearch_config**: Provides test configuration
- **elasticsearch_client**: Real Elasticsearch client for integration tests
- **index_manager**: Real manager instance for operations
- **dry_run_manager**: Manager in dry-run mode for safe testing
- **sample_csv_file**: Temporary CSV with test data
- **cleanup_test_indices**: Automatic cleanup after tests

### Coverage Areas
- ✅ Connection handling and authentication
- ✅ Index operations (create, delete, read-only)
- ✅ Reindex operations with progress tracking
- ✅ CSV parsing and validation
- ✅ System index filtering
- ✅ Error handling and logging
- ✅ Settings cleaning and mapping preservation
- ✅ Document count validation
- ✅ Dry-run mode functionality

### Test Data
Tests use realistic data patterns:
- Multiple index types (user vs system indices)
- Various Elasticsearch versions (7.6.0, 7.12.1, 7.17.9)
- Different actions (delete, read-only, reindex)
- Edge cases (empty actions, invalid actions)

## Running Specific Test Categories

### Unit Tests Only
```bash
python test_elasticsearch_manager.py
```

### Integration Tests Only
```bash
RUN_INTEGRATION_TESTS=true python test_elasticsearch_manager.py
```

### Pytest with Coverage
```bash
pytest test_pytest.py -v --cov=elasticsearch_index_manager --cov-report=html
```

### Specific Test Classes
```bash
pytest test_pytest.py::TestIndexManager -v
pytest test_pytest.py::TestElasticsearchOperations -v
```

## Cleanup

### Stop Elasticsearch
```bash
docker-compose down -v
```

### Clean Virtual Environment
```bash
deactivate
rm -rf venv
```

### Complete Cleanup
```bash
./run_tests.sh cleanup
```

## Troubleshooting

### Elasticsearch Won't Start
- Check Docker logs: `docker-compose logs elasticsearch`
- Ensure ports 9200/9300 are not in use
- Verify Docker has enough memory allocated

### Tests Failing
- Ensure Elasticsearch is healthy: `curl -u elastic:testpassword123 http://localhost:9200/_cluster/health`
- Check virtual environment is activated
- Verify all dependencies are installed: `pip list`

### Permission Issues
- Make test script executable: `chmod +x run_tests.sh`
- Check Docker permissions for your user

## Test Output Example

```
========================================
Elasticsearch Index Manager Test Setup
========================================
[INFO] Checking Docker installation...
[INFO] Docker is installed and running ✓
[INFO] Setting up Python virtual environment...
[INFO] Virtual environment setup complete ✓
[INFO] Starting Elasticsearch in Docker...
[INFO] Elasticsearch is ready ✓
[INFO] Running tests...

test_config_creation_https (test_elasticsearch_manager.TestElasticsearchConfig) ... ok
test_csv_loading (test_elasticsearch_manager.TestElasticsearchIndexManager) ... ok
test_connection (test_elasticsearch_manager.TestElasticsearchIntegration) ... ok

=============================== 15 passed in 45.2s ===============================

[INFO] Test setup and execution complete!
```

This comprehensive test suite ensures the reliability and correctness of the Elasticsearch Index Manager across various scenarios and use cases.
