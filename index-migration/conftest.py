#!/usr/bin/env python3
"""
Pytest configuration and additional test utilities
"""

import pytest
import time
import tempfile
import os
from elasticsearch import Elasticsearch
from elasticsearch_index_manager import ElasticsearchConfig, ElasticsearchIndexManager


@pytest.fixture(scope="session")
def elasticsearch_config():
    """Provide Elasticsearch configuration for tests."""
    return ElasticsearchConfig(
        host="localhost",
        username="elastic", 
        password="testpassword123",
        port=9200,
        use_https=False
    )


@pytest.fixture(scope="session")
def elasticsearch_client(elasticsearch_config):
    """Provide Elasticsearch client for tests."""
    es = Elasticsearch(
        [elasticsearch_config.url],
        basic_auth=(elasticsearch_config.username, elasticsearch_config.password),
        verify_certs=False,
        ssl_show_warn=False
    )
    
    # Wait for Elasticsearch to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            if es.ping():
                break
        except:
            if i == max_retries - 1:
                pytest.skip("Elasticsearch not available")
            time.sleep(1)
    
    return es


@pytest.fixture
def index_manager(elasticsearch_config):
    """Provide IndexManager instance for tests."""
    return ElasticsearchIndexManager(elasticsearch_config, dry_run=False)


@pytest.fixture
def dry_run_manager(elasticsearch_config):
    """Provide IndexManager instance in dry-run mode for tests."""
    return ElasticsearchIndexManager(elasticsearch_config, dry_run=True)


@pytest.fixture
def test_index_name():
    """Provide unique test index name."""
    return f"pytest_test_index_{int(time.time())}"


@pytest.fixture
def sample_csv_file():
    """Create a temporary CSV file for testing."""
    content = '''
"provided_name","created_string","Action"
"test_delete_index","7.6.0","delete"
"test_readonly_index","7.12.1","read-only"
"test_reindex_source","7.17.9","reindex"
".system_index","7.6.0","delete"
"empty_action","7.6.0",""
"invalid_action","7.6.0","unknown"
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(content.strip())
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    os.unlink(temp_path)


@pytest.fixture(autouse=True)
def cleanup_test_indices(elasticsearch_client):
    """Automatically cleanup test indices after each test."""
    yield
    
    # Cleanup any test indices
    try:
        elasticsearch_client.indices.delete(index="pytest_test_*,test_*", ignore=[404])
    except:
        pass
