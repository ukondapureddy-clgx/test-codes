#!/usr/bin/env python3
"""
Pytest-based tests for Elasticsearch Index Manager
"""

import pytest
import time
import tempfile
import os
from unittest.mock import patch, MagicMock

from elasticsearch_index_manager import IndexInfo


class TestIndexManager:
    """Test class for IndexManager functionality."""
    
    def test_csv_loading(self, dry_run_manager, sample_csv_file):
        """Test CSV file loading."""
        indices = dry_run_manager.load_csv(sample_csv_file)
        
        # Should load only valid actions (includes .system_index)
        assert len(indices) == 4
        
        actions = [idx.action for idx in indices]
        assert "delete" in actions
        assert "read-only" in actions
        assert "reindex" in actions
    
    def test_csv_loading_invalid_file(self, dry_run_manager):
        """Test CSV loading with invalid file."""
        with pytest.raises(FileNotFoundError):
            dry_run_manager.load_csv("nonexistent.csv")
    
    def test_dry_run_operations(self, dry_run_manager, test_index_name):
        """Test that dry run mode doesn't perform actual operations."""
        # All operations should return True in dry run mode
        assert dry_run_manager.delete_index(test_index_name) == True
        assert dry_run_manager.set_index_readonly(test_index_name) == True
        
        # Create fake index info for reindex test
        index_info = IndexInfo(test_index_name, "7.6.0", "reindex")
        
        # Mock the helper methods to simulate existing index
        with patch.object(dry_run_manager, 'index_exists', return_value=True), \
             patch.object(dry_run_manager, 'get_index_settings', return_value={"test": "settings"}), \
             patch.object(dry_run_manager, 'get_index_mapping', return_value={"test": "mapping"}):
            
            assert dry_run_manager.perform_reindex(index_info) == True


class TestElasticsearchOperations:
    """Test actual Elasticsearch operations."""
    
    def test_connection(self, index_manager):
        """Test Elasticsearch connection."""
        assert index_manager.check_connection() == True
    
    def test_index_lifecycle(self, index_manager, elasticsearch_client, test_index_name):
        """Test complete index lifecycle: create, check, modify, delete."""
        # Create test index
        elasticsearch_client.indices.create(
            index=test_index_name,
            body={
                "settings": {"number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "title": {"type": "text"},
                        "count": {"type": "integer"}
                    }
                }
            }
        )
        
        # Test index exists
        assert index_manager.index_exists(test_index_name) == True
        
        # Add test documents
        for i in range(3):
            elasticsearch_client.index(
                index=test_index_name,
                body={"title": f"Test {i}", "count": i}
            )
        
        elasticsearch_client.indices.refresh(index=test_index_name)
        
        # Test document count
        count = index_manager.get_document_count(test_index_name)
        assert count == 3
        
        # Test get settings
        settings = index_manager.get_index_settings(test_index_name)
        assert settings is not None
        assert test_index_name in settings
        
        # Test get mapping
        mapping = index_manager.get_index_mapping(test_index_name)
        assert mapping is not None
        assert test_index_name in mapping
        
        # Test set read-only
        assert index_manager.set_index_readonly(test_index_name) == True
        
        # Verify read-only setting
        updated_settings = index_manager.get_index_settings(test_index_name)
        index_settings = updated_settings[test_index_name]['settings']['index']
        assert index_settings.get('blocks', {}).get('write') == 'true'
        
        # Test delete
        assert index_manager.delete_index(test_index_name) == True
        assert index_manager.index_exists(test_index_name) == False
    
    def test_reindex_operation(self, index_manager, elasticsearch_client, test_index_name):
        """Test reindex operation."""
        source_index = test_index_name
        
        # Create source index with data
        elasticsearch_client.indices.create(
            index=source_index,
            body={
                "settings": {"number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "data": {"type": "text"},
                        "value": {"type": "integer"}
                    }
                }
            }
        )
        
        # Add test data
        test_docs = [
            {"data": "test1", "value": 1},
            {"data": "test2", "value": 2},
            {"data": "test3", "value": 3}
        ]
        
        for doc in test_docs:
            elasticsearch_client.index(index=source_index, body=doc)
        
        elasticsearch_client.indices.refresh(index=source_index)
        
        # Verify source has data
        source_count = index_manager.get_document_count(source_index)
        assert source_count == 3
        
        # Perform reindex
        index_info = IndexInfo(source_index, "7.6.0", "reindex")
        success = index_manager.perform_reindex(index_info)
        assert success == True
        
        # Check that source is now read-only
        settings = index_manager.get_index_settings(source_index)
        source_settings = settings[source_index]['settings']['index']
        assert source_settings.get('blocks', {}).get('write') == 'true'
    
    def test_error_handling(self, index_manager):
        """Test error handling for non-existent indices."""
        fake_index = "definitely_does_not_exist_index"
        
        # These should handle errors gracefully
        assert index_manager.index_exists(fake_index) == False
        assert index_manager.get_index_settings(fake_index) is None
        assert index_manager.get_index_mapping(fake_index) is None
        assert index_manager.get_document_count(fake_index) is None
        
        # Delete should return False for non-existent index
        assert index_manager.delete_index(fake_index) == False


class TestCSVProcessing:
    """Test CSV processing and bulk operations."""
    
    def test_process_indices_filtering(self, index_manager, sample_csv_file, elasticsearch_client):
        """Test that indices are properly filtered during processing."""
        # Create test indices that exist
        test_indices = ["test_delete_index", "test_readonly_index", "test_reindex_source"]
        
        for idx_name in test_indices:
            elasticsearch_client.indices.create(
                index=idx_name,
                body={
                    "settings": {"number_of_replicas": 0},
                    "mappings": {"properties": {"test": {"type": "text"}}}
                }
            )
            elasticsearch_client.index(index=idx_name, body={"test": "data"})
        
        elasticsearch_client.indices.refresh(index="test_*")
        
        # Load CSV and process
        indices = index_manager.load_csv(sample_csv_file)
        results = index_manager.process_indices(indices)
        
        # System indices should be skipped
        assert len(results['skipped']) >= 1  # At least .system_index
        
        # Valid operations should succeed
        assert len(results['success']) >= 2  # delete and read-only should work
        
        # Check specific results
        assert "test_delete_index" in results['success']
        assert "test_readonly_index" in results['success']
        
        # Verify delete worked
        assert index_manager.index_exists("test_delete_index") == False
        
        # Verify read-only worked
        if index_manager.index_exists("test_readonly_index"):
            settings = index_manager.get_index_settings("test_readonly_index")
            readonly_settings = settings["test_readonly_index"]['settings']['index']
            assert readonly_settings.get('blocks', {}).get('write') == 'true'
    
    def test_settings_cleaning(self, index_manager):
        """Test that index settings are properly cleaned."""
        test_settings = {
            "test_index": {
                "settings": {
                    "index": {
                        "uuid": "test-uuid-should-be-removed",
                        "version": {"created": "7060099"},
                        "creation_date": "1234567890",
                        "number_of_shards": "1",
                        "number_of_replicas": "0",
                        "refresh_interval": "30s",
                        "max_result_window": "10000"
                    }
                }
            }
        }
        
        cleaned = index_manager._clean_settings(test_settings)
        
        # Should remove system fields
        assert "uuid" not in cleaned
        assert "version" not in cleaned
        assert "creation_date" not in cleaned
        assert "number_of_shards" not in cleaned
        
        # Should keep user settings
        assert cleaned.get("number_of_replicas") == "0"
        assert cleaned.get("refresh_interval") == "30s"
        assert cleaned.get("max_result_window") == "10000"


class TestValidation:
    """Test validation functionality."""
    
    def test_reindex_validation(self, index_manager, elasticsearch_client, test_index_name):
        """Test reindex validation by document count."""
        source_index = test_index_name
        target_index = f"{test_index_name}_target"
        
        # Create indices with same document count
        for idx_name in [source_index, target_index]:
            elasticsearch_client.indices.create(
                index=idx_name,
                body={
                    "settings": {"number_of_replicas": 0},
                    "mappings": {"properties": {"test": {"type": "text"}}}
                }
            )
            
            # Add same number of documents
            for i in range(5):
                elasticsearch_client.index(index=idx_name, body={"test": f"data{i}"})
        
        elasticsearch_client.indices.refresh(index=f"{test_index_name}*")
        
        # Validation should pass
        assert index_manager.validate_reindex(source_index, target_index) == True
        
        # Add extra document to target
        elasticsearch_client.index(index=target_index, body={"test": "extra"})
        elasticsearch_client.indices.refresh(index=target_index)
        
        # Validation should fail
        assert index_manager.validate_reindex(source_index, target_index) == False
