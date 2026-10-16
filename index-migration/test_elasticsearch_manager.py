#!/usr/bin/env python3
"""
Unit tests for Elasticsearch Index Manager
"""

import csv
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, NotFoundError

from elasticsearch_index_manager import (
    ElasticsearchConfig,
    ElasticsearchIndexManager,
    IndexInfo
)


class TestElasticsearchConfig(unittest.TestCase):
    """Test ElasticsearchConfig class."""
    
    def test_config_creation_https(self):
        """Test config creation with HTTPS."""
        config = ElasticsearchConfig("localhost", "user", "pass", 9200, True)
        
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.username, "user")
        self.assertEqual(config.password, "pass")
        self.assertEqual(config.port, 9200)
        self.assertTrue(config.use_https)
        self.assertEqual(config.url, "https://localhost:9200")
    
    def test_config_creation_http(self):
        """Test config creation with HTTP."""
        config = ElasticsearchConfig("localhost", "user", "pass", 9200, False)
        
        self.assertEqual(config.url, "http://localhost:9200")
        self.assertFalse(config.use_https)


class TestIndexInfo(unittest.TestCase):
    """Test IndexInfo dataclass."""
    
    def test_index_info_creation(self):
        """Test IndexInfo creation."""
        info = IndexInfo("test_index", "7.6.0", "reindex")
        
        self.assertEqual(info.provided_name, "test_index")
        self.assertEqual(info.created_string, "7.6.0")
        self.assertEqual(info.action, "reindex")


class TestElasticsearchIndexManager(unittest.TestCase):
    """Test ElasticsearchIndexManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ElasticsearchConfig("localhost", "elastic", "testpassword123", 9200, False)
        self.manager = ElasticsearchIndexManager(self.config, dry_run=True)
        
        # Create a temporary CSV file for testing
        self.temp_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        csv_content = '''
"provided_name","created_string","Action"
"test_index_1","7.6.0","delete"
"test_index_2","7.12.1","read-only"
"test_index_3","7.17.9","reindex"
".kibana_test","7.6.0","delete"
"empty_action_index","7.6.0",""
"invalid_action_index","7.6.0","invalid"
'''
        self.temp_csv.write(csv_content.strip())
        self.temp_csv.close()
    
    def tearDown(self):
        """Clean up test fixtures."""
        os.unlink(self.temp_csv.name)
    
    def test_load_csv(self):
        """Test CSV loading functionality."""
        indices = self.manager.load_csv(self.temp_csv.name)
        
        # Should only load indices with valid actions (includes .kibana_test)
        self.assertEqual(len(indices), 4)
        
        # Check first index
        self.assertEqual(indices[0].provided_name, "test_index_1")
        self.assertEqual(indices[0].action, "delete")
        
        # Check second index
        self.assertEqual(indices[1].provided_name, "test_index_2")
        self.assertEqual(indices[1].action, "read-only")
        
        # Check third index
        self.assertEqual(indices[2].provided_name, "test_index_3")
        self.assertEqual(indices[2].action, "reindex")
    
    def test_load_csv_file_not_found(self):
        """Test CSV loading with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            self.manager.load_csv("nonexistent.csv")
    
    @patch('elasticsearch_index_manager.ElasticsearchIndexManager.index_exists')
    def test_process_indices_system_index_skipped(self, mock_exists):
        """Test that system indices are skipped."""
        mock_exists.return_value = True
        
        indices = [
            IndexInfo(".kibana_test", "7.6.0", "delete"),
            IndexInfo("user_index", "7.6.0", "delete")
        ]
        
        results = self.manager.process_indices(indices)
        
        # System index should be skipped
        self.assertIn(".kibana_test", results['skipped'])
        # User index should be processed (in dry run mode)
        self.assertIn("user_index", results['success'])
    
    @patch('elasticsearch_index_manager.ElasticsearchIndexManager.index_exists')
    def test_process_indices_nonexistent_index_skipped(self, mock_exists):
        """Test that non-existent indices are skipped."""
        mock_exists.return_value = False
        
        indices = [IndexInfo("nonexistent_index", "7.6.0", "delete")]
        
        results = self.manager.process_indices(indices)
        
        self.assertIn("nonexistent_index", results['skipped'])
    
    def test_clean_settings(self):
        """Test settings cleaning functionality."""
        test_settings = {
            "test_index": {
                "settings": {
                    "index": {
                        "uuid": "should-be-removed",
                        "version": "should-be-removed",
                        "creation_date": "should-be-removed",
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "refresh_interval": "30s"
                    }
                }
            }
        }
        
        cleaned = self.manager._clean_settings(test_settings)
        
        # Should not contain excluded fields
        self.assertNotIn("uuid", cleaned)
        self.assertNotIn("version", cleaned)
        self.assertNotIn("creation_date", cleaned)
        self.assertNotIn("number_of_shards", cleaned)
        
        # Should contain allowed fields
        self.assertEqual(cleaned.get("number_of_replicas"), 0)
        self.assertEqual(cleaned.get("refresh_interval"), "30s")


class TestElasticsearchIntegration(unittest.TestCase):
    """Integration tests with real Elasticsearch instance."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        cls.config = ElasticsearchConfig("localhost", "elastic", "testpassword123", 9200, False)
        cls.manager = ElasticsearchIndexManager(cls.config, dry_run=False)
        
        # Wait for Elasticsearch to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                if cls.manager.check_connection():
                    break
            except:
                if i == max_retries - 1:
                    raise unittest.SkipTest("Elasticsearch not available for integration tests")
                time.sleep(2)
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_index = f"test_index_{int(time.time())}"
        self.test_index_2 = f"test_index_2_{int(time.time())}"
        
        # Clean up any existing test indices
        try:
            self.manager.es.indices.delete(index=f"test_index_*")
        except:
            pass
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up test indices
        try:
            self.manager.es.indices.delete(index=f"test_index_*")
        except:
            pass
    
    def test_connection(self):
        """Test Elasticsearch connection."""
        self.assertTrue(self.manager.check_connection())
    
    def test_index_operations(self):
        """Test basic index operations."""
        # Create test index
        self.manager.es.indices.create(
            index=self.test_index,
            body={
                "settings": {"number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "title": {"type": "text"},
                        "created": {"type": "date"}
                    }
                }
            }
        )
        
        # Test index exists
        self.assertTrue(self.manager.index_exists(self.test_index))
        
        # Add some test documents
        for i in range(5):
            self.manager.es.index(
                index=self.test_index,
                body={
                    "title": f"Test Document {i}",
                    "created": "2025-08-27"
                }
            )
        
        # Refresh index
        self.manager.es.indices.refresh(index=self.test_index)
        
        # Test document count
        count = self.manager.get_document_count(self.test_index)
        self.assertEqual(count, 5)
        
        # Test get settings
        settings = self.manager.get_index_settings(self.test_index)
        self.assertIsNotNone(settings)
        
        # Test get mapping
        mapping = self.manager.get_index_mapping(self.test_index)
        self.assertIsNotNone(mapping)
        
        # Test set read-only
        self.assertTrue(self.manager.set_index_readonly(self.test_index))
        
        # Test delete index
        self.assertTrue(self.manager.delete_index(self.test_index))
        self.assertFalse(self.manager.index_exists(self.test_index))
    
    def test_reindex_operation(self):
        """Test complete reindex operation."""
        # Create source index with data
        self.manager.es.indices.create(
            index=self.test_index,
            body={
                "settings": {"number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "title": {"type": "text"},
                        "value": {"type": "integer"}
                    }
                }
            }
        )
        
        # Add test documents
        for i in range(10):
            self.manager.es.index(
                index=self.test_index,
                body={"title": f"Document {i}", "value": i}
            )
        
        self.manager.es.indices.refresh(index=self.test_index)
        
        # Create IndexInfo for reindex
        index_info = IndexInfo(self.test_index, "7.6.0", "reindex")
        
        # Perform reindex
        success = self.manager.perform_reindex(index_info)
        self.assertTrue(success)
        
        # Wait a bit for reindex to complete
        time.sleep(2)
        
        # Check that source index is read-only
        settings = self.manager.get_index_settings(self.test_index)
        source_settings = settings[self.test_index]['settings']['index']
        self.assertEqual(source_settings.get('blocks', {}).get('write'), 'true')
    
    def test_csv_processing_integration(self):
        """Test full CSV processing workflow."""
        # Create test indices
        test_indices = [
            ("csv_test_delete", "delete"),
            ("csv_test_readonly", "read-only"),
            ("csv_test_reindex", "reindex")
        ]
        
        for index_name, action in test_indices:
            self.manager.es.indices.create(
                index=index_name,
                body={
                    "settings": {"number_of_replicas": 0},
                    "mappings": {"properties": {"test": {"type": "text"}}}
                }
            )
            
            # Add a test document
            self.manager.es.index(index=index_name, body={"test": "data"})
        
        self.manager.es.indices.refresh(index="csv_test_*")
        
        # Create temporary CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["provided_name", "created_string", "Action"])
            for index_name, action in test_indices:
                writer.writerow([index_name, "7.6.0", action])
            csv_path = f.name
        
        try:
            # Load and process CSV
            indices = self.manager.load_csv(csv_path)
            results = self.manager.process_indices(indices)
            
            # Check results
            self.assertEqual(len(results['success']), 3)
            self.assertEqual(len(results['failed']), 0)
            
            # Verify delete operation
            self.assertFalse(self.manager.index_exists("csv_test_delete"))
            
            # Verify read-only operation
            settings = self.manager.get_index_settings("csv_test_readonly")
            if settings:  # Check if index still exists
                readonly_settings = settings["csv_test_readonly"]['settings']['index']
                self.assertEqual(readonly_settings.get('blocks', {}).get('write'), 'true')
            
        finally:
            os.unlink(csv_path)
            # Clean up remaining indices
            try:
                self.manager.es.indices.delete(index="csv_test_*")
            except:
                pass


if __name__ == '__main__':
    # Check if we should run integration tests
    run_integration = os.getenv('RUN_INTEGRATION_TESTS', 'false').lower() == 'true'
    
    if run_integration:
        # Run all tests including integration tests
        unittest.main(verbosity=2)
    else:
        # Run only unit tests
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # Add unit test classes
        suite.addTests(loader.loadTestsFromTestCase(TestElasticsearchConfig))
        suite.addTests(loader.loadTestsFromTestCase(TestIndexInfo))
        suite.addTests(loader.loadTestsFromTestCase(TestElasticsearchIndexManager))
        
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
