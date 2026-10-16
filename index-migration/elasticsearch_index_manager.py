#!/usr/bin/env python3
"""
Elasticsearch Index Manager

This script processes a CSV file containing index information and performs
actions based on the Action column: delete, read-only, or reindex operations.

Authentication Methods:
1. Basic Authentication:
   python elasticsearch_index_manager.py file.csv --host localhost --username elastic --password mypassword

2. API Key Authentication:
   python elasticsearch_index_manager.py file.csv --host localhost --api-key "your_api_key_here"

To create an API key in Elasticsearch:
   curl -X POST "https://your-elasticsearch:9200/_security/api_key" \
     -H "Content-Type: application/json" \
     -H "Authorization: Basic base64(username:password)" \
     -d '{"name": "index-manager-key", "expiration": "7d"}'

Example usage with API key:
   export API_KEY="your_api_key_here"
   python elasticsearch_index_manager.py data.csv --host localhost --api-key "$API_KEY" --http
"""

import csv
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, NotFoundError, RequestError


@dataclass
class IndexInfo:
    """Data class to hold index information from CSV."""
    provided_name: str
    created_string: str
    action: str


class ElasticsearchConfig:
    """Configuration class for Elasticsearch connection."""
    
    def __init__(self, host: str, username: str = None, password: str = None, 
                 api_key: str = None, port: int = 9200, use_https: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.api_key = api_key
        self.use_https = use_https
        self.scheme = "https" if use_https else "http"
        self.url = f"{self.scheme}://{host}:{port}"
        
        # Validate authentication method
        if not api_key and not (username and password):
            raise ValueError("Either API key or username/password must be provided")
        if api_key and (username or password):
            raise ValueError("Cannot use both API key and username/password authentication")


class ElasticsearchIndexManager:
    """Main class for managing Elasticsearch indices based on CSV input."""
    
    def __init__(self, config: ElasticsearchConfig, dry_run: bool = True, swap_original_name: bool = False,
                 auto_confirm: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.swap_original_name = swap_original_name
        self.auto_confirm = auto_confirm
        
        # Initialize Elasticsearch client with appropriate authentication
        client_kwargs = {
            'verify_certs': False,  # Disable SSL verification for self-signed certs
            'ssl_show_warn': False,  # Suppress SSL warnings
            'request_timeout': 30,
            'max_retries': 3,
            'retry_on_timeout': True
        }
        
        if config.api_key:
            # Use API Key authentication
            self.es = Elasticsearch(
                [config.url],
                api_key=config.api_key,
                **client_kwargs
            )
        else:
            # Use Basic authentication
            self.es = Elasticsearch(
                [config.url],
                basic_auth=(config.username, config.password),
                **client_kwargs
            )
        
        # Setup logging
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger('elasticsearch_manager')
        logger.setLevel(logging.INFO)
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Create file handler
        log_file = Path(__file__).parent / 'elasticsearch_manager.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def load_csv(self, csv_path: str) -> List[IndexInfo]:
        """Load and parse the CSV file."""
        indices = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Clean the keys and values (remove quotes)
                    cleaned_row = {k.strip('"'): v.strip('"') for k, v in row.items()}
                    
                    index_info = IndexInfo(
                        provided_name=cleaned_row.get('provided_name', ''),
                        created_string=cleaned_row.get('created_string', ''),
                        action=cleaned_row.get('Action', '').lower().strip()
                    )
                    
                    # Only process indices with valid actions
                    if index_info.action in ['delete', 'read-only', 'reindex']:
                        indices.append(index_info)
                        
            self.logger.info(f"Loaded {len(indices)} indices from {csv_path}")
            return indices
            
        except Exception as e:
            self.logger.error(f"Error loading CSV file {csv_path}: {e}")
            raise
    
    def check_connection(self) -> bool:
        """Check if we can connect to Elasticsearch."""
        try:
            # Log authentication method
            auth_method = "API Key" if self.config.api_key else "Basic Auth"
            self.logger.info(f"Using {auth_method} authentication")
            
            health = self.es.cluster.health()
            
            self.logger.info(f"Connected to Elasticsearch cluster: {health.get('cluster_name')}")
            self.logger.info(f"Cluster status: {health.get('status')}")
            self.logger.info(f"Number of nodes: {health.get('number_of_nodes')}")
            return True
            
        except ConnectionError as e:
            self.logger.error(f"Failed to connect to Elasticsearch: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to Elasticsearch: {e}")
            return False
    
    def index_exists(self, index_name: str) -> bool:
        """Check if an index exists."""
        try:
            return self.es.indices.exists(index=index_name)
        except Exception as e:
            self.logger.error(f"Error checking if index {index_name} exists: {e}")
            return False
    
    def get_index_settings(self, index_name: str) -> Optional[Dict]:
        """Get index settings."""
        try:
            return self.es.indices.get_settings(index=index_name)
        except NotFoundError:
            self.logger.error(f"Index {index_name} not found")
            return None
        except Exception as e:
            self.logger.error(f"Error getting settings for index {index_name}: {e}")
            return None
    
    def get_index_mapping(self, index_name: str) -> Optional[Dict]:
        """Get index mapping."""
        try:
            return self.es.indices.get_mapping(index=index_name)
        except NotFoundError:
            self.logger.error(f"Index {index_name} not found")
            return None
        except Exception as e:
            self.logger.error(f"Error getting mapping for index {index_name}: {e}")
            return None
    
    def get_document_count(self, index_name: str) -> Optional[int]:
        """Get the document count for an index."""
        try:
            result = self.es.count(index=index_name)
            return result.get('count', 0)
        except NotFoundError:
            self.logger.error(f"Index {index_name} not found")
            return None
        except Exception as e:
            self.logger.error(f"Error getting document count for index {index_name}: {e}")
            return None
    
    def set_index_readonly(self, index_name: str, block: str = "read_only") -> bool:
        """Set an index to read-only mode using block API."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would set index {index_name} to {block} using block API")
            return True
            
        try:
            # Use the block API endpoint to set read-only
            response = self.es.indices.add_block(
                index=index_name,
                block=block
            )
            
            self.logger.info(f"Successfully set index {index_name} to {block} using block API")
            return True
            
        except RequestError as e:
            self.logger.error(f"Request error setting index {index_name} to read-only: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error setting index {index_name} to read-only: {e}")
            return False
    
    def set_replica_count(self, index_name: str, replica_count: int) -> bool:
        """Set the number of replicas for an index."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would set index {index_name} replica count to {replica_count}")
            return True
            
        try:
            settings = {
                "index": {
                    "number_of_replicas": replica_count
                }
            }
            
            self.es.indices.put_settings(index=index_name, settings=settings)
            self.logger.info(f"Successfully set index {index_name} replica count to {replica_count}")
            return True
            
        except RequestError as e:
            self.logger.error(f"Request error setting replica count for {index_name}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error setting replica count for {index_name}: {e}")
            return False
    
    def get_replica_count(self, index_name: str) -> Optional[int]:
        """Get the current number of replicas for an index."""
        try:
            settings = self.get_index_settings(index_name)
            if settings and index_name in settings:
                replica_setting = settings[index_name]['settings']['index'].get('number_of_replicas', '1')
                return int(replica_setting)
            return None
        except Exception as e:
            self.logger.error(f"Error getting replica count for {index_name}: {e}")
            return None
    
    def get_index_aliases(self, index_name: str) -> List[str]:
        """Get all aliases for an index."""
        try:
            aliases_response = self.es.indices.get_alias(index=index_name)
            if index_name in aliases_response:
                aliases = list(aliases_response[index_name]['aliases'].keys())
                self.logger.info(f"Index {index_name} has aliases: {aliases}")
                return aliases
            return []
        except NotFoundError:
            self.logger.info(f"Index {index_name} not found or has no aliases")
            return []
        except Exception as e:
            self.logger.error(f"Error getting aliases for {index_name}: {e}")
            return []
    
    def transfer_aliases(self, source_index: str, target_index: str) -> bool:
        """Transfer all aliases from source index to target index."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would transfer aliases from {source_index} to {target_index}")
            return True
        
        try:
            # Get all aliases from source index
            source_aliases = self.get_index_aliases(source_index)
            
            if not source_aliases:
                self.logger.info(f"No aliases to transfer from {source_index}")
                return True
            
            # Prepare actions for atomic alias switch
            actions = []
            
            for alias_name in source_aliases:
                # Remove alias from source index
                actions.append({
                    "remove": {
                        "index": source_index,
                        "alias": alias_name
                    }
                })
                
                # Add alias to target index
                actions.append({
                    "add": {
                        "index": target_index,
                        "alias": alias_name
                    }
                })
            
            # Execute atomic alias switch
            self.es.indices.update_aliases(body={"actions": actions})
            
            self.logger.info(f"✓ Successfully transferred {len(source_aliases)} aliases from {source_index} to {target_index}")
            self.logger.info(f"Transferred aliases: {', '.join(source_aliases)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error transferring aliases from {source_index} to {target_index}: {e}")
            return False
    
    def _confirm_swap(self, source_index: str, target_index: str) -> bool:
        """Ask the operator to confirm deleting the source index (skipped in dry run or with --yes)."""
        if self.dry_run or self.auto_confirm:
            return True
        if not sys.stdin.isatty():
            self.logger.warning("No interactive terminal available; use --yes to skip the confirmation prompt")
            return False

        source_count = self.get_document_count(source_index)
        target_count = self.get_document_count(target_index)
        print(f"\nReindex finished: {source_index} ({source_count} docs) -> {target_index} ({target_count} docs)")
        print(f"Deleting '{source_index}' is IRREVERSIBLE; '{source_index}' will become an alias of '{target_index}'.")
        answer = input(f"Type 'yes' to delete '{source_index}' and create the alias: ").strip().lower()
        return answer == 'yes'

    def swap_index_for_alias(self, source_index: str, target_index: str) -> bool:
        """Atomically delete the source index and expose the target under the source's name via an alias."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would delete {source_index} and alias {source_index} -> {target_index}")
            return True

        try:
            self.es.indices.update_aliases(body={"actions": [
                {"remove_index": {"index": source_index}},
                {"add": {"index": target_index, "alias": source_index}}
            ]})
            self.logger.info(f"✓ Deleted {source_index} and created alias {source_index} -> {target_index}")
            return True
        except Exception as e:
            self.logger.error(f"Error swapping {source_index} for alias to {target_index}: {e}")
            return False

    def create_alias(self, index_name: str, alias_name: str) -> bool:
        """Create an alias for an index."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would create alias {alias_name} for index {index_name}")
            return True
        
        try:
            self.es.indices.put_alias(index=index_name, name=alias_name)
            self.logger.info(f"✓ Created alias {alias_name} for index {index_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error creating alias {alias_name} for index {index_name}: {e}")
            return False
    
    def delete_index(self, index_name: str) -> bool:
        """Delete an index."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would delete index {index_name}")
            return True
            
        try:
            self.es.indices.delete(index=index_name)
            self.logger.info(f"Successfully deleted index {index_name}")
            return True
            
        except NotFoundError:
            self.logger.warning(f"Index {index_name} not found, cannot delete")
            return False
        except Exception as e:
            self.logger.error(f"Error deleting index {index_name}: {e}")
            return False
    
    def create_index(self, index_name: str, settings: Dict, mappings: Dict) -> bool:
        """Create a new index with given settings and mappings."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would create index {index_name}")
            return True
            
        try:
            # Clean settings - remove system-generated fields
            clean_settings = self._clean_settings(settings)
            
            index_config = {
                "settings": clean_settings,
                "mappings": mappings
            }
            
            self.es.indices.create(index=index_name, body=index_config)
            self.logger.info(f"Successfully created index {index_name}")
            return True
            
        except RequestError as e:
            self.logger.error(f"Request error creating index {index_name}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error creating index {index_name}: {e}")
            return False
    
    def _clean_settings(self, settings: Dict) -> Dict:
        """Clean index settings by removing system-generated fields."""
        if not settings:
            return {}
            
        # Get the first index settings (assuming single index)
        index_settings = list(settings.values())[0] if settings else {}
        settings_dict = index_settings.get('settings', {}).get('index', {})
        
        # Fields to exclude from settings
        exclude_fields = {
            'uuid', 'version', 'creation_date', 'provided_name', 
            'routing_partition_size', 'blocks','verified_read_only'
        }
        
        clean_settings = {}
        for key, value in settings_dict.items():
            if key not in exclude_fields:
                clean_settings[key] = value
                
        return clean_settings
    
    def _remove_default_pipeline(self, index_name: str) -> Optional[str]:
        """Remove default_pipeline from index settings and return its value."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would remove default_pipeline from {index_name}")
            return None
            
        try:
            settings = self.get_index_settings(index_name)
            if not settings or index_name not in settings:
                return None
                
            current_pipeline = settings[index_name]['settings']['index'].get('default_pipeline')
            
            if current_pipeline:
                # Remove the default_pipeline setting
                self.es.indices.put_settings(
                    index=index_name,
                    settings={
                        "index": {
                            "default_pipeline": None
                        }
                    }
                )
                self.logger.info(f"Removed default_pipeline '{current_pipeline}' from {index_name}")
                return current_pipeline
            else:
                self.logger.info(f"No default_pipeline found in {index_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error removing default_pipeline from {index_name}: {e}")
            return None
    
    def _restore_default_pipeline(self, index_name: str, pipeline_name: str) -> bool:
        """Restore default_pipeline to index settings."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would restore default_pipeline '{pipeline_name}' to {index_name}")
            return True
            
        if not pipeline_name:
            return True
            
        try:
            self.es.indices.put_settings(
                index=index_name,
                settings={
                    "index": {
                        "default_pipeline": pipeline_name
                    }
                }
            )
            self.logger.info(f"Restored default_pipeline '{pipeline_name}' to {index_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error restoring default_pipeline to {index_name}: {e}")
            return False
    
    def reindex_data(self, source_index: str, target_index: str) -> Optional[str]:
        """Reindex data from source to target index."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would reindex from {source_index} to {target_index}")
            return "dry_run_task_id"
            
        try:
            reindex_body = {
                "source": {"index": source_index},
                "dest": {"index": target_index}
            }
            
            # Start reindex operation (can be async)
            result = self.es.reindex(body=reindex_body, wait_for_completion=False)
            
            task_id = result.get('task')
            self.logger.info(f"Reindex task started for {source_index} -> {target_index}")
            self.logger.info(f"Task ID: {task_id}")
            
            return task_id
            
        except RequestError as e:
            self.logger.error(f"Request error reindexing from {source_index} to {target_index}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error reindexing from {source_index} to {target_index}: {e}")
            return None
    
    def wait_for_reindex_completion(self, task_id: str) -> bool:
        """Wait for reindex task to complete."""
        if self.dry_run or task_id == "dry_run_task_id":
            return True
            
        retry_count = 0
        max_retries = 5
        retry_delay = 60  # Start with 60 seconds delay
        start_time = time.time()
        last_progress_time = None
        last_created_count = 0
        
        try:
            while True:
                try:
                    task_info = self.es.tasks.get(task_id=task_id)
                    retry_count = 0  # Reset retry count on successful connection
                    retry_delay = 60  # Reset delay
                    
                    if task_info.get('completed', False):
                        self.logger.info(f"Reindex task {task_id} completed")
                        
                        # Check for failures first
                        response = task_info.get('response', {})
                        failures = response.get('failures', [])
                        
                        if failures:
                            self.logger.error(f"Reindex task {task_id} completed with failures:")
                            for failure in failures:
                                index = failure.get('index', 'unknown')
                                doc_id = failure.get('id', 'unknown')
                                cause = failure.get('cause', {})
                                error_type = cause.get('type', 'unknown_error')
                                reason = cause.get('reason', 'unknown reason')
                                status = failure.get('status', 'unknown')
                                
                                self.logger.error(f"  - Index: {index}, Document ID: {doc_id}")
                                self.logger.error(f"    Error: {error_type} - {reason}")
                                self.logger.error(f"    Status: {status}")
                            
                            return False
                        
                        # Log task statistics if no failures
                        if response:
                            created = response.get('created', 0)
                            updated = response.get('updated', 0)
                            deleted = response.get('deleted', 0)
                            total = response.get('total', 0)
                            
                            self.logger.info(f"Reindex stats - Total: {total}, Created: {created}, "
                                           f"Updated: {updated}, Deleted: {deleted}")
                        
                        return True
                        
                    # Log progress if available
                    status = task_info.get('task', {}).get('status', {})
                    if status:
                        created = status.get('created', 0)
                        total = status.get('total', 0)
                        if total > 0:
                            progress = (created / total) * 100
                            current_time = time.time()
                            elapsed_time = current_time - start_time
                            
                            # Calculate estimated time remaining
                            if progress > 0:
                                # Method 1: Based on overall progress
                                estimated_total_time = elapsed_time * (100 / progress)
                                remaining_time_overall = estimated_total_time - elapsed_time
                                
                                # Method 2: Based on recent processing speed (if we have previous data)
                                remaining_time_speed = None
                                if last_progress_time and created > last_created_count:
                                    time_delta = current_time - last_progress_time
                                    docs_delta = created - last_created_count
                                    docs_per_second = docs_delta / time_delta
                                    remaining_docs = total - created
                                    if docs_per_second > 0:
                                        remaining_time_speed = remaining_docs / docs_per_second
                                
                                # Use speed-based estimate if available and reasonable, otherwise use overall
                                if remaining_time_speed and remaining_time_speed > 0:
                                    remaining_time = remaining_time_speed
                                    method = "(speed-based)"
                                else:
                                    remaining_time = remaining_time_overall
                                    method = "(progress-based)"
                                
                                # Format time remaining
                                if remaining_time > 3600:  # More than 1 hour
                                    hours = int(remaining_time // 3600)
                                    minutes = int((remaining_time % 3600) // 60)
                                    time_str = f"{hours}h {minutes}m {method}"
                                elif remaining_time > 60:  # More than 1 minute
                                    minutes = int(remaining_time // 60)
                                    seconds = int(remaining_time % 60)
                                    time_str = f"{minutes}m {seconds}s {method}"
                                else:  # Less than 1 minute
                                    seconds = int(remaining_time)
                                    time_str = f"{seconds}s {method}"
                                
                                self.logger.info(f"Reindex progress: {progress:.1f}% ({created}/{total}) - Est. {time_str} remaining")
                            else:
                                self.logger.info(f"Reindex progress: {progress:.1f}% ({created}/{total})")
                            
                            last_progress_time = current_time
                            last_created_count = created
                    
                    self.logger.info(f"Reindex task {task_id} still running...")
                    
                except (ConnectionError, Exception) as e:
                    retry_count += 1
                    if retry_count <= max_retries:
                        self.logger.warning(f"Connection error (attempt {retry_count}/{max_retries}): {e}")
                        self.logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 300)  # Exponential backoff, max 5 minutes
                        continue
                    else:
                        self.logger.error(f"Max retries ({max_retries}) exceeded. Connection failed: {e}")
                        self.logger.error(f"Task {task_id} may still be running on the server. Check manually.")
                        return False
                
                time.sleep(30)  # Wait 30 seconds before checking again
                
        except Exception as e:
            self.logger.error(f"Error waiting for reindex task {task_id}: {e}")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a specific task."""
        try:
            task_info = self.es.tasks.get(task_id=task_id)
            self.logger.info(f"Task {task_id} status: {json.dumps(task_info, indent=2)}")
            return task_info
        except Exception as e:
            self.logger.error(f"Error getting task {task_id} status: {e}")
            return None
    
    def _execute_with_retry(self, operation_func, operation_name: str, *args, **kwargs):
        """Execute an operation with retry logic for connection issues."""
        retry_count = 0
        max_retries = 3
        retry_delay = 30
        
        while retry_count <= max_retries:
            try:
                return operation_func(*args, **kwargs)
            except (ConnectionError, Exception) as e:
                retry_count += 1
                if retry_count <= max_retries:
                    self.logger.warning(f"Connection error during {operation_name} (attempt {retry_count}/{max_retries}): {e}")
                    self.logger.info(f"Retrying {operation_name} in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 120)  # Exponential backoff, max 2 minutes
                    continue
                else:
                    self.logger.error(f"Max retries ({max_retries}) exceeded for {operation_name}. Error: {e}")
                    raise e
    
    def check_and_wait_for_task(self, task_id: str) -> bool:
        """Check if a task exists and wait for its completion. Useful for reconnecting to existing tasks."""
        self.logger.info(f"Checking status of existing task: {task_id}")
        
        try:
            # First check if task exists
            task_info = self.es.tasks.get(task_id=task_id)
            
            if task_info.get('completed', False):
                self.logger.info(f"Task {task_id} is already completed")
                return True
            else:
                self.logger.info(f"Task {task_id} is still running, monitoring progress...")
                return self.wait_for_reindex_completion(task_id)
                
        except Exception as e:
            self.logger.error(f"Task {task_id} not found or error occurred: {e}")
            return False
    
    def perform_reindex(self, index_info: IndexInfo) -> bool:
        """Perform complete reindex operation with replica management."""
        import time
        start_time = time.time()
        source_index = index_info.provided_name
        target_index = f"{source_index}_{int(time.time())}"

        self.logger.info(f"Starting reindex operation for {source_index}")

        # 1. Check if source index exists
        if not self.index_exists(source_index):
            self.logger.warning(f"Source index {source_index} does not exist")
            return False

        # 2. Get source index settings and mappings
        settings = self.get_index_settings(source_index)
        mappings = self.get_index_mapping(source_index)

        if not settings or not mappings:
            self.logger.error(f"Could not retrieve settings/mappings for {source_index}")
            return False

        # 3. Get source document count and aliases for validation
        source_doc_count = self.get_document_count(source_index)
        if source_doc_count is None:
            self.logger.error(f"Could not get document count for source index {source_index}")
            return False

        self.logger.info(f"Source index {source_index} contains {source_doc_count} documents")

        # 4. Get source index aliases
        source_aliases = self.get_index_aliases(source_index)
        if source_aliases:
            self.logger.info(f"Source index {source_index} has aliases: {', '.join(source_aliases)}")
        else:
            self.logger.info(f"Source index {source_index} has no aliases")

        # 5. Block writes on the source; the write block (unlike read_only) still allows deleting the index
        if not self.set_index_readonly(source_index, block="write"):
            return False

        # 6. Create target index
        target_mappings = mappings.get(source_index, {}).get('mappings', {})
        if not self.create_index(target_index, settings, target_mappings):
            return False

        # 7. Remove default_pipeline temporarily from target index for faster reindexing
        self.logger.info(f"Temporarily removing default_pipeline from {target_index} for reindex")
        original_pipeline = self._remove_default_pipeline(target_index)

        # 8. Set target index replicas to 0 for faster reindexing
        original_replica_count = self.get_replica_count(target_index)
        self.logger.info(f"Setting target index {target_index} replicas to 0 for faster reindexing")
        if not self.set_replica_count(target_index, 0):
            self.logger.warning(f"Could not set replica count to 0 for {target_index}, continuing anyway")

        # 9. Perform reindex
        task_id = self.reindex_data(source_index, target_index)
        if not task_id:
            return False

        # 10. Wait for reindex completion
        if not self.wait_for_reindex_completion(task_id):
            self.logger.error(f"Reindex operation failed or timed out")
            return False

        # 11. Refresh target index to make documents available for count
        try:
            if not self.dry_run:
                self.logger.info(f"Refreshing target index {target_index}")
                self._execute_with_retry(self.es.indices.refresh, "index refresh", index=target_index)
                self.logger.info(f"Target index {target_index} refreshed successfully")
                time.sleep(1)  # Brief pause to ensure refresh is processed
        except Exception as e:
            self.logger.warning(f"Could not refresh target index {target_index}: {e}")

        # 12. Validate document counts
        try:
            validation_result = self._execute_with_retry(self.validate_reindex, "reindex validation", source_index, target_index)
            if not validation_result:
                self.logger.error(f"Reindex validation failed for {source_index} -> {target_index}")
                return False
        except Exception as e:
            self.logger.error(f"Error during reindex validation: {e}")
            return False

        # 13. Set target index replicas back to 1 (or original count)
        final_replica_count = 1 if original_replica_count is None else min(original_replica_count, 1)
        self.logger.info(f"Setting target index {target_index} replicas to {final_replica_count}")
        try:
            replica_result = self._execute_with_retry(self.set_replica_count, "replica count setting", target_index, final_replica_count)
            if not replica_result:
                self.logger.warning(f"Could not set replica count to {final_replica_count} for {target_index}")
        except Exception as e:
            self.logger.warning(f"Error setting replica count for {target_index}: {e}")

        # 14. Restore default_pipeline to target index
        if original_pipeline:
            try:
                pipeline_result = self._execute_with_retry(self._restore_default_pipeline, "pipeline restoration", target_index, original_pipeline)
                if not pipeline_result:
                    self.logger.warning(f"Could not restore default_pipeline to {target_index}")
            except Exception as e:
                self.logger.warning(f"Error restoring default_pipeline to {target_index}: {e}")

        # 15. Transfer aliases from source to target index
        if source_aliases:
            self.logger.info(f"Transferring aliases from {source_index} to {target_index}")
            try:
                alias_result = self._execute_with_retry(self.transfer_aliases, "alias transfer", source_index, target_index)
                if not alias_result:
                    self.logger.error(f"Failed to transfer aliases from {source_index} to {target_index}")
                    return False
            except Exception as e:
                self.logger.error(f"Error transferring aliases: {e}")
                return False

        # 16. Optionally replace the source index with an alias of the same name
        if self.swap_original_name:
            if not self._confirm_swap(source_index, target_index):
                self.logger.warning(f"Swap declined; {source_index} was kept and {target_index} holds the copy")
            elif not self._execute_with_retry(self.swap_index_for_alias, "index swap", source_index, target_index):
                return False

        elapsed = time.time() - start_time
        self.logger.info(f"Reindex operation for {source_index} -> {target_index} took {elapsed:.2f} seconds")

        self.logger.info(f"\u2713 Reindex operation completed successfully: {source_index} -> {target_index}")
        if source_aliases:
            self.logger.info(f"\u2713 Aliases transferred: {', '.join(source_aliases)}")
        return True
    
    def validate_reindex(self, source_index: str, target_index: str) -> bool:
        """Validate that reindex operation was successful by comparing document counts."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would validate reindex from {source_index} to {target_index}")
            return True
        
        try:
            self.logger.info(f"Validating reindex from {source_index} to {target_index}")
            
            source_count = self.get_document_count(source_index)
            target_count = self.get_document_count(target_index)
            
            if source_count is None or target_count is None:
                self.logger.error(f"Could not get document counts for validation")
                return False
            
            self.logger.info(f"Document count validation - Source: {source_count}, Target: {target_count}")
            
            if source_count == target_count:
                self.logger.info(f"✓ Reindex validation successful: {source_count} documents in both indices")
                return True
            else:
                self.logger.error(f"✗ Reindex validation failed: {source_count} in source, {target_count} in target")
                return False
                
        except Exception as e:
            self.logger.error(f"Error validating reindex: {e}")
            return False
    
    def _parse_es_version(self, version_str: str) -> Optional[Tuple[int, int, int]]:
        """Parse Elasticsearch version string to tuple of integers for comparison."""
        try:
            if version_str == 'UNKNOWN' or not version_str:
                return None
            
            # Handle both formats: "8.7.1" and version numbers like "8070199"
            if '.' in str(version_str):
                # Already in readable format like "8.7.1"
                parts = str(version_str).split('.')
                major = int(parts[0])
                minor = int(parts[1]) if len(parts) > 1 else 0
                patch = int(parts[2]) if len(parts) > 2 else 0
            else:
                # Version number format like "8070199"
                version_num = str(version_str)
                if len(version_num) >= 7:
                    major = int(version_num[0])
                    minor = int(version_num[1:3].lstrip('0') or '0')
                    patch = int(version_num[3:5].lstrip('0') or '0')
                else:
                    # Fallback for shorter version numbers
                    return None
            
            return (major, minor, patch)
        except (ValueError, IndexError):
            return None
    
    def _compare_versions(self, version1: str, version2: str, operator: str) -> bool:
        """Compare two version strings using the specified operator."""
        v1_tuple = self._parse_es_version(version1)
        v2_tuple = self._parse_es_version(version2)
        
        if v1_tuple is None or v2_tuple is None:
            return False
        
        if operator == 'lt':
            return v1_tuple < v2_tuple
        elif operator == 'le':
            return v1_tuple <= v2_tuple
        elif operator == 'gt':
            return v1_tuple > v2_tuple
        elif operator == 'ge':
            return v1_tuple >= v2_tuple
        elif operator == 'eq':
            return v1_tuple == v2_tuple
        else:
            return False
    
    def analyze_indices(self, pattern: str = "*", output_format: str = "human", 
                       version_filters: Optional[Dict[str, str]] = None) -> None:
        """Analyze all indices and show their status, aliases, and version info."""
        try:
            # Get all indices matching pattern
            indices_info = self.es.indices.get(index=pattern, ignore_unavailable=True)
            
            analysis_results = []
            
            for index_name, index_data in indices_info.items():
                # Skip system indices if not explicitly requested
                if index_name.startswith('.') and pattern == "*":
                    continue
                
                settings = index_data.get('settings', {}).get('index', {})
                
                # Get blocks information
                def _parse_block_value(value):
                    """Parse block value - can be boolean, string, or None"""
                    if value is None:
                        return False
                    if isinstance(value, bool):
                        return value
                    if isinstance(value, str):
                        return value.lower() in ('true', '1', 'yes')
                    return bool(value)
                
                # Get blocks from the correct location (not under index.blocks but just blocks)
                blocks_section = index_data.get('settings', {}).get('index', {}).get('blocks', {})
                
                # Get raw blocks for debugging
                raw_blocks = {
                    'read': blocks_section.get('read'),
                    'write': blocks_section.get('write'),
                    'read_only': blocks_section.get('read_only'),
                    'read_only_allow_delete': blocks_section.get('read_only_allow_delete')
                }
                
                blocks = {
                    'read': _parse_block_value(raw_blocks['read']),
                    'write': _parse_block_value(raw_blocks['write']),
                    'read_only': _parse_block_value(raw_blocks['read_only']),
                    'read_only_allow_delete': _parse_block_value(raw_blocks['read_only_allow_delete'])
                }
                
                # Debug logging for blocks (only if any blocks exist)
                if any(v is not None for v in raw_blocks.values()):
                    self.logger.debug(f"Index {index_name} blocks - Raw: {raw_blocks}, Parsed: {blocks}")
                
                # Format blocks status
                if any(blocks.values()):
                    block_status = []
                    if blocks['read']: block_status.append('READ')
                    if blocks['write']: block_status.append('WRITE')
                    if blocks['read_only']: block_status.append('READ_ONLY')
                    if blocks['read_only_allow_delete']: block_status.append('READ_ONLY_DELETE')
                    blocks_str = ','.join(block_status)
                else:
                    blocks_str = 'NONE'
                
                # Get aliases
                aliases = self.get_index_aliases(index_name)
                aliases_str = ','.join(aliases) if aliases else 'NONE'
                
                # Get version info
                version_info = settings.get('version', {})
                created_version = version_info.get('created', 'UNKNOWN')
                
                # Convert version number to readable format
                if created_version != 'UNKNOWN':
                    try:
                        version_num = str(created_version)
                        if len(version_num) >= 7:
                            major = version_num[0]
                            minor = version_num[1:3].lstrip('0') or '0'
                            patch = version_num[3:5].lstrip('0') or '0'
                            build = version_num[5:]
                            version_readable = f"{major}.{minor}.{patch}"
                        else:
                            version_readable = created_version
                    except:
                        version_readable = created_version
                else:
                    version_readable = 'UNKNOWN'
                
                # Get document count
                doc_count = self.get_document_count(index_name) or 0
                
                analysis_results.append({
                    'index_name': index_name,
                    'blocks': blocks_str,
                    'aliases': aliases_str,
                    'version_created': created_version,
                    'version_readable': version_readable,
                    'document_count': doc_count
                })
            
            # Apply version filters if provided
            if version_filters:
                filtered_results = []
                for result in analysis_results:
                    include_result = True
                    
                    for operator, target_version in version_filters.items():
                        if not self._compare_versions(result['version_readable'], target_version, operator):
                            include_result = False
                            break
                    
                    if include_result:
                        filtered_results.append(result)
                
                analysis_results = filtered_results
                self.logger.info(f"Applied version filters: {version_filters}")
                self.logger.info(f"Results after filtering: {len(analysis_results)} indices")
            
            # Output results
            if output_format.lower() == 'csv':
                self._output_analysis_csv(analysis_results)
            else:
                self._output_analysis_human(analysis_results)
                
        except Exception as e:
            self.logger.error(f"Error analyzing indices: {e}")
    
    def _output_analysis_csv(self, results: List[Dict]) -> None:
        """Output analysis results in CSV format."""
        import csv
        import sys
        
        # Define CSV headers
        headers = ['index_name', 'blocks', 'aliases', 'version_created', 'version_readable', 'document_count']
        
        writer = csv.DictWriter(sys.stdout, fieldnames=headers)
        writer.writeheader()
        
        for result in sorted(results, key=lambda x: x['index_name']):
            writer.writerow(result)
    
    def _output_analysis_human(self, results: List[Dict]) -> None:
        """Output analysis results in human-readable format."""
        self.logger.info("=" * 120)
        self.logger.info("INDEX ANALYSIS REPORT")
        self.logger.info("=" * 120)
        
        # Header
        header = f"{'Index Name':<40} {'Blocks':<20} {'Aliases':<30} {'Version':<15} {'Docs':<12}"
        self.logger.info(header)
        self.logger.info("-" * 120)
        
        # Sort results by index name
        for result in sorted(results, key=lambda x: x['index_name']):
            index_name = result['index_name']
            blocks = result['blocks']
            aliases = result['aliases']
            version = result['version_readable']
            doc_count = f"{result['document_count']:,}"
            
            # Truncate long values for display
            if len(index_name) > 38:
                index_name = index_name[:35] + "..."
            if len(aliases) > 28:
                aliases = aliases[:25] + "..."
            if len(blocks) > 18:
                blocks = blocks[:15] + "..."
                
            line = f"{index_name:<40} {blocks:<20} {aliases:<30} {version:<15} {doc_count:<12}"
            self.logger.info(line)
        
        self.logger.info("-" * 120)
        self.logger.info(f"Total indices analyzed: {len(results)}")
        
        # Summary statistics
        blocked_indices = [r for r in results if r['blocks'] != 'NONE']
        aliased_indices = [r for r in results if r['aliases'] != 'NONE']
        total_docs = sum(r['document_count'] for r in results)
        
        self.logger.info(f"Indices with blocks: {len(blocked_indices)}")
        self.logger.info(f"Indices with aliases: {len(aliased_indices)}")
        self.logger.info(f"Total documents: {total_docs:,}")
        self.logger.info("=" * 120)
    
    def process_indices(self, indices: List[IndexInfo]) -> Dict[str, List[str]]:
        """Process all indices according to their actions."""
        results = {
            'success': [],
            'failed': [],
            'skipped': []
        }
        
        for index_info in indices:
            index_name = index_info.provided_name
            action = index_info.action
            
            self.logger.info(f"Processing index {index_name} with action: {action}")
            
            # Skip system indices (starting with .)
            if index_name.startswith('.'):
                self.logger.info(f"Skipping system index: {index_name}")
                results['skipped'].append(index_name)
                continue
            
            # Check if index exists
            if not self.index_exists(index_name):
                self.logger.warning(f"Index {index_name} does not exist, skipping")
                results['skipped'].append(index_name)
                continue
            
            success = False
            
            if action == 'delete':
                success = self.delete_index(index_name)
            elif action == 'read-only':
                success = self.set_index_readonly(index_name)
            elif action == 'reindex':
                success = self.perform_reindex(index_info)
            else:
                self.logger.warning(f"Unknown action '{action}' for index {index_name}")
                results['skipped'].append(index_name)
                continue
            
            if success:
                results['success'].append(index_name)
            else:
                results['failed'].append(index_name)
        
        return results
    
    def print_summary(self, results: Dict[str, List[str]]):
        """Print a summary of the operations."""
        self.logger.info("=" * 50)
        self.logger.info("OPERATION SUMMARY")
        self.logger.info("=" * 50)
        self.logger.info(f"Successful operations: {len(results['success'])}")
        for index in results['success']:
            self.logger.info(f"  ✓ {index}")
        
        self.logger.info(f"Failed operations: {len(results['failed'])}")
        for index in results['failed']:
            self.logger.info(f"  ✗ {index}")
        
        self.logger.info(f"Skipped operations: {len(results['skipped'])}")
        for index in results['skipped']:
            self.logger.info(f"  - {index}")


def main():
    """Main function to run the index manager."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Elasticsearch Index Manager',
        epilog='''
Examples:
  # Normal CSV processing
  python %(prog)s indices.csv --host https://es.example.com --api-key your_api_key
  
  # Resume task monitoring only
  python %(prog)s --resume-task ABC123 --host https://es.example.com --api-key your_api_key
  
  # Resume task and complete all post-reindex steps
  python %(prog)s --resume-and-complete ABC123 old_index new_index --host https://es.example.com --api-key your_api_key
  
  # Resume with pipeline restoration
  python %(prog)s --resume-and-complete ABC123 old_index new_index --original-pipeline my_pipeline --host https://es.example.com --api-key your_api_key
  
  # Analyze all indices (human-readable format)
  python %(prog)s --analyze --host https://es.example.com --api-key your_api_key
  
  # Analyze specific indices pattern in CSV format
  python %(prog)s --analyze --pattern "watcher*" --output csv --host https://es.example.com --api-key your_api_key
  
  # Analyze system indices
  python %(prog)s --analyze --pattern ".*" --host https://es.example.com --api-key your_api_key
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('csv_file', nargs='?', help='Path to CSV file containing index information')
    parser.add_argument('--host', required=True, help='Elasticsearch host')
    
    # Authentication options
    auth_group = parser.add_mutually_exclusive_group(required=True)
    auth_group.add_argument('--username', help='Elasticsearch username (requires --password)')
    auth_group.add_argument('--api-key', help='Elasticsearch API key')
    
    parser.add_argument('--password', help='Elasticsearch password (required with --username)')
    parser.add_argument('--port', type=int, default=9200, help='Elasticsearch port (default: 9200)')
    parser.add_argument('--http', action='store_true', help='Use HTTP instead of HTTPS')
    parser.add_argument('--execute', action='store_true', help='Execute operations (default is dry-run)')
    parser.add_argument('--swap-original-name', action='store_true',
                        help='After a validated reindex, delete the source index and create an alias with its name '
                             'pointing to the new index (IRREVERSIBLE; works with --resume-and-complete too)')
    parser.add_argument('--yes', action='store_true', help='Skip the confirmation prompt before deleting the source index')
    
    # Task resume option
    parser.add_argument('--resume-task', help='Resume monitoring an existing reindex task by task ID')
    parser.add_argument('--resume-and-complete', nargs=3, metavar=('TASK_ID', 'SOURCE_INDEX', 'TARGET_INDEX'),
                        help='Resume task and complete all post-reindex steps (task_id source_index target_index)')
    parser.add_argument('--original-pipeline', help='Original pipeline to restore (use with --resume-and-complete)')
    
    # Analysis mode
    parser.add_argument('--analyze', action='store_true', help='Analyze indices and show status, aliases, and version info')
    parser.add_argument('--pattern', default='*', help='Index pattern to analyze (default: *)')
    parser.add_argument('--output', choices=['human', 'csv'], default='human', help='Output format: human or csv (default: human)')
    
    # Version filtering options
    parser.add_argument('--version-lt', type=str, help='Show indices with version less than specified (e.g., 8.0 or 9.0)')
    parser.add_argument('--version-le', type=str, help='Show indices with version less than or equal to specified (e.g., 8.0 or 9.0)')
    parser.add_argument('--version-gt', type=str, help='Show indices with version greater than specified (e.g., 8.0 or 9.0)')
    parser.add_argument('--version-ge', type=str, help='Show indices with version greater than or equal to specified (e.g., 8.0 or 9.0)')
    parser.add_argument('--version-eq', type=str, help='Show indices with version equal to specified (e.g., 8.0 or 9.0)')
    
    args = parser.parse_args()
    
    # Validate authentication arguments
    if args.username and not args.password:
        parser.error("--password is required when using --username")
    if args.password and not args.username:
        parser.error("--username is required when using --password")
    
    # Validate arguments based on mode
    if args.resume_task or args.resume_and_complete or args.analyze:
        if args.csv_file:
            parser.error("Cannot use CSV file with --resume-task, --resume-and-complete, or --analyze")
        if args.resume_task and args.resume_and_complete:
            parser.error("Cannot use both --resume-task and --resume-and-complete")
        if args.analyze and (args.resume_task or args.resume_and_complete):
            parser.error("Cannot use --analyze with resume options")
    else:
        if not args.csv_file:
            parser.error("CSV file is required unless using --resume-task, --resume-and-complete, or --analyze")
    
    # Create configuration
    config = ElasticsearchConfig(
        host=args.host,
        username=args.username,
        password=args.password,
        api_key=getattr(args, 'api_key', None),
        port=args.port,
        use_https=not args.http
    )
    
    # Create manager
    manager = ElasticsearchIndexManager(config, dry_run=not args.execute, swap_original_name=args.swap_original_name,
                                        auto_confirm=args.yes)
    
    # Check connection
    if not manager.check_connection():
        sys.exit(1)
    
    # Handle task resume mode
    if args.resume_task:
        manager.logger.info(f"Resuming task: {args.resume_task}")
        success = manager.check_and_wait_for_task(args.resume_task)
        if success:
            manager.logger.info("Task completed successfully!")
            sys.exit(0)
        else:
            manager.logger.error("Task failed or not found")
            sys.exit(1)
    
    # Handle resume and complete mode
    if args.resume_and_complete:
        task_id, source_index, target_index = args.resume_and_complete
        manager.logger.info(f"Resuming task {task_id} and completing post-reindex steps for {source_index} -> {target_index}")
        
        # First wait for task completion
        manager.logger.info("Checking task status...")
        success = manager.check_and_wait_for_task(task_id)
        if not success:
            manager.logger.error("Task failed or not found")
            sys.exit(1)
        
        # Then complete all post-reindex steps
        manager.logger.info("Task completed successfully. Proceeding with post-reindex steps...")
        
        try:
            # Restore original pipeline if provided
            if args.original_pipeline:
                manager.logger.info(f"Restoring original pipeline '{args.original_pipeline}' to index '{target_index}'")
                manager._restore_default_pipeline(target_index, args.original_pipeline)
            
            # Set replicas to 1
            manager.logger.info(f"Setting replicas to 1 for index '{target_index}'")
            manager._execute_with_retry(
                lambda: manager.es.indices.put_settings(
                    index=target_index,
                    body={'index': {'number_of_replicas': 1}}
                ),
                "set_replicas"
            )
            
            # Validate document count
            manager.logger.info(f"Validating document count between '{source_index}' and '{target_index}'")
            validation_success = manager.validate_reindex(source_index, target_index)
            if not validation_success:
                manager.logger.warning(f"Document count validation failed for {source_index} -> {target_index}")
                if args.swap_original_name:
                    manager.logger.error("Refusing to swap original name because validation failed")
                    sys.exit(1)
            
            # Transfer aliases
            manager.logger.info(f"Transferring aliases from '{source_index}' to '{target_index}'")
            manager.transfer_aliases(source_index, target_index)

            if args.swap_original_name:
                if not manager._confirm_swap(source_index, target_index):
                    manager.logger.warning(f"Swap declined; {source_index} was kept")
                elif not manager.swap_index_for_alias(source_index, target_index):
                    sys.exit(1)
            
            manager.logger.info(f"✅ Resume and complete finished successfully for {source_index} -> {target_index}")
            sys.exit(0)
            
        except Exception as e:
            manager.logger.error(f"Failed during post-reindex steps: {e}")
            sys.exit(1)
    
    # Handle analysis mode
    if args.analyze:
        manager.logger.info(f"Analyzing indices with pattern: {args.pattern}")
        
        # Collect version filters
        version_filters = {}
        if args.version_lt:
            version_filters['lt'] = args.version_lt
        if args.version_le:
            version_filters['le'] = args.version_le
        if args.version_gt:
            version_filters['gt'] = args.version_gt
        if args.version_ge:
            version_filters['ge'] = args.version_ge
        if args.version_eq:
            version_filters['eq'] = args.version_eq
        
        # Pass version filters if any are specified
        if version_filters:
            manager.analyze_indices(args.pattern, args.output, version_filters)
        else:
            manager.analyze_indices(args.pattern, args.output)
        sys.exit(0)
    
    # Normal CSV processing mode
    # Load CSV
    try:
        indices = manager.load_csv(args.csv_file)
    except Exception as e:
        manager.logger.error(f"Failed to load CSV: {e}")
        sys.exit(1)
    
    # Process indices
    results = manager.process_indices(indices)
    
    # Print summary
    manager.print_summary(results)
    
    if not args.execute:
        manager.logger.info("This was a DRY RUN. Use --execute to perform actual operations.")


if __name__ == '__main__':
    main()
