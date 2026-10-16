#!/usr/bin/env python3
"""
Test script for Elasticsearch Index Manager
"""

import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

from elasticsearch_index_manager import ElasticsearchIndexManager, ElasticsearchConfig, IndexInfo


def test_csv_loading():
    """Test CSV loading functionality."""
    print("Testing CSV loading...")
    
    # Create a dummy config for testing
    config = ElasticsearchConfig("localhost", "test", "test")
    manager = ElasticsearchIndexManager(config, dry_run=True)
    
    # Test with the actual CSV file
    csv_path = "../../resources/table/trestle.index.7.csv"
    
    try:
        indices = manager.load_csv(csv_path)
        print(f"Successfully loaded {len(indices)} indices")
        
        # Print first few indices
        print("\nFirst 5 indices with actions:")
        for i, index_info in enumerate(indices[:5]):
            print(f"  {i+1}. {index_info.provided_name} -> {index_info.action}")
        
        # Count actions
        action_counts = {}
        for index_info in indices:
            action = index_info.action
            action_counts[action] = action_counts.get(action, 0) + 1
        
        print(f"\nAction summary:")
        for action, count in action_counts.items():
            print(f"  {action}: {count}")
            
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_index_filtering():
    """Test system index filtering."""
    print("\nTesting system index filtering...")
    
    # Create test data
    test_indices = [
        IndexInfo(".kibana_1", "7.6.0", "delete"),
        IndexInfo("elastic_properties_v1_int", "7.6.0", "reindex"),
        IndexInfo(".security-7", "7.6.0", "read-only"),
        IndexInfo("elastic_offices_test", "7.6.0", "delete"),
    ]
    
    system_indices = [idx for idx in test_indices if idx.provided_name.startswith('.')]
    user_indices = [idx for idx in test_indices if not idx.provided_name.startswith('.')]
    
    print(f"System indices (should be skipped): {len(system_indices)}")
    for idx in system_indices:
        print(f"  - {idx.provided_name}")
    
    print(f"User indices (will be processed): {len(user_indices)}")
    for idx in user_indices:
        print(f"  - {idx.provided_name} -> {idx.action}")


if __name__ == "__main__":
    print("=" * 50)
    print("Elasticsearch Index Manager - Test Suite")
    print("=" * 50)
    
    success = test_csv_loading()
    test_index_filtering()
    
    print("\n" + "=" * 50)
    if success:
        print("All tests passed!")
    else:
        print("Some tests failed!")
    print("=" * 50)
