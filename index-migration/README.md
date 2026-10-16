# Elasticsearch Index Manager

This Python script processes a CSV file containing Elasticsearch index information and performs actions based on the "Action" column. It uses the official Elasticsearch Python client for robust and reliable operations.

## Features

- **Official Elasticsearch Client**: Uses the official `elasticsearch` Python library for reliable operations
- **Object-Oriented Design**: Clean, maintainable code structure
- **Comprehensive Logging**: Both console and file logging with detailed progress tracking
- **Multiple Operation Modes**:
  - **CSV Processing**: Process indices from CSV file
  - **Task Resume**: Resume interrupted reindex operations
  - **Index Analysis**: Analyze index status, blocks, aliases, and versions
- **Dry Run Mode**: Test operations without making actual changes
- **Action Support**:
  - `delete`: Deletes the specified index
  - `read-only`: Sets the index to read-only mode
  - `reindex`: Creates a new index and reindexes data from the source
- **Advanced Reindex Features**:
  - Pipeline management (temporary removal during reindex)
  - Replica optimization (set to 0 during reindex)
  - Document count validation
  - Alias transfer
  - Connection retry logic with exponential backoff
  - Time estimation for completion
- **Resume Capabilities**:
  - Resume monitoring existing reindex tasks
  - Complete all post-reindex steps after task completion
- **Index Analysis**:
  - Show index blocks, aliases, version info
  - Support for multiple output formats (human-readable, CSV)
  - Pattern-based filtering
- **Error Handling**: Proper exception handling with detailed error messages
- **Progress Tracking**: Real-time progress updates with time estimation

## Installation

1. (Optional) Set up tmux for long-running operations:
```bash
# Option 1: Configure mouse support globally first
echo "setw -g mouse on" >> ~/.tmux.conf

# Then start a new tmux session
tmux new-session -s elasticsearch-migration

# Option 2: Or start session and enable mouse within tmux
tmux new-session -s elasticsearch-migration
# Inside tmux, press Ctrl+b then : and type: setw -g mouse on
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic CSV Processing

#### Dry Run Mode (Default)
```bash
python elasticsearch_index_manager.py indices.csv \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

#### Execute Operations
```bash
python elasticsearch_index_manager.py indices.csv \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key \
    --execute
```

### Authentication Methods

#### API Key Authentication (Recommended)
```bash
python elasticsearch_index_manager.py indices.csv \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key \
    --execute
```

#### Basic Authentication
```bash
python elasticsearch_index_manager.py indices.csv \
    --host https://your-elasticsearch:443 \
    --username elastic \
    --password your_password \
    --execute
```

### Resume Operations

#### Resume Task Monitoring Only
```bash
python elasticsearch_index_manager.py \
    --resume-task ABC123 \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

#### Resume Task and Complete All Post-Reindex Steps
```bash
python elasticsearch_index_manager.py \
    --resume-and-complete ABC123 old_index new_index \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

#### Resume with Pipeline Restoration
```bash
python elasticsearch_index_manager.py \
    --resume-and-complete ABC123 old_index new_index \
    --original-pipeline my_pipeline \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

### Index Analysis

#### Analyze All Indices (Human-Readable)
```bash
python elasticsearch_index_manager.py --analyze \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

#### Analyze in CSV Format
```bash
python elasticsearch_index_manager.py --analyze --output csv \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

#### Analyze with Pattern
```bash
python elasticsearch_index_manager.py --analyze --pattern "watcher*" \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

#### Analyze System Indices
```bash
python elasticsearch_index_manager.py --analyze --pattern ".*" \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

#### Analyze with Version Filtering

##### Find indices with version less than 8.0
```bash
python elasticsearch_index_manager.py --analyze --version-lt 8.0 \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

##### Find indices with version less than 9.0 (for migration planning)
```bash
python elasticsearch_index_manager.py --analyze --version-lt 9.0 --output csv \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

##### Find indices exactly on version 7.6
```bash
python elasticsearch_index_manager.py --analyze --version-eq 7.6 \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

##### Find old indices (version less than or equal to 8.0) with blocks
```bash
python elasticsearch_index_manager.py --analyze --version-le 8.0 --pattern "*log*" \
    --host https://your-elasticsearch:443 \
    --api-key your_api_key
```

### Using Environment Variables
```bash
export ELASTICSEARCH_HOST="https://your-elasticsearch"
export ELASTICSEARCH_PORT="443"
export ELASTICSEARCH_API_KEY="your_api_key"

python elasticsearch_index_manager.py indices.csv \
    --host "$ELASTICSEARCH_HOST" \
    --port "$ELASTICSEARCH_PORT" \
    --api-key "$ELASTICSEARCH_API_KEY" \
    --execute
```

## Command Line Arguments

### Required Arguments
- `--host`: Elasticsearch host (required)

### Authentication (choose one)
- `--api-key`: Elasticsearch API key (recommended)
- `--username` + `--password`: Basic authentication

### Optional Arguments
- `csv_file`: Path to CSV file (required for normal processing)
- `--port`: Elasticsearch port (default: 9200)
- `--http`: Use HTTP instead of HTTPS
- `--execute`: Execute operations (without this flag, runs in dry-run mode)
- `--swap-original-name`: After a validated reindex, atomically delete the source index and create an alias with the source's name pointing to the new index, so clients keep using the old name (irreversible; also works with `--resume-and-complete`). Prompts for confirmation before deleting
- `--yes`: Skip the confirmation prompt (needed for non-interactive runs)

### Resume Options
- `--resume-task TASK_ID`: Resume monitoring an existing reindex task
- `--resume-and-complete TASK_ID SOURCE_INDEX TARGET_INDEX`: Resume task and complete post-reindex steps
- `--original-pipeline PIPELINE_NAME`: Original pipeline to restore (use with --resume-and-complete)

### Analysis Options
- `--analyze`: Enable index analysis mode
- `--pattern PATTERN`: Index pattern to analyze (default: *)
- `--output FORMAT`: Output format - human or csv (default: human)

### Version Filtering Options (for analysis mode)
- `--version-lt VERSION`: Show indices with version less than specified (e.g., 8.0 or 9.0)
- `--version-le VERSION`: Show indices with version less than or equal to specified
- `--version-gt VERSION`: Show indices with version greater than specified
- `--version-ge VERSION`: Show indices with version greater than or equal to specified
- `--version-eq VERSION`: Show indices with version equal to specified

## CSV Format

The CSV file should have the following columns:
- `provided_name`: The name of the index
- `created_string`: The version when the index was created
- `Action`: The action to perform (`delete`, `read-only`, or `reindex`)

Example:
```csv
"provided_name","created_string","Action"
"elastic_customproperties_v1_int","7.6.0","reindex"
"elastic_offices_test","7.6.0","delete"
"elastic_cprindex","7.6.0","read-only"
```

## Actions Explained

### Delete
- Permanently removes the index from Elasticsearch
- Use with caution as this operation is irreversible

### Read-Only
- Sets the index to read-only mode by adding `index.blocks.write: true`
- Prevents new writes while maintaining read access

### Reindex
Complete 15-step reindex process:
1. Check source index exists
2. Get source index settings and mappings
3. Get source document count and aliases
4. Get source index aliases
5. Set source index to read-only
6. Create target index with same settings/mappings
7. **Remove default_pipeline from target index** (for performance)
8. Set target index replicas to 0 (for performance)
9. Perform reindex operation
10. Wait for reindex completion with progress tracking
11. Refresh target index
12. Validate document counts
13. Set target index replicas back to 1
14. **Restore default_pipeline to target index**
15. Transfer aliases from source to target

## Index Analysis Output

The analysis mode shows comprehensive index information:

### Human-Readable Format
```
========================================================================================================================
INDEX ANALYSIS REPORT
========================================================================================================================
Index Name                               Blocks               Aliases                        Version         Docs        
------------------------------------------------------------------------------------------------------------------------
my-app-logs-2023-01                      WRITE                app-logs,current-logs          7.13.4          1,234,567   
old-watcher-index                        READ_ONLY            watcher-current                7.10.2          45,678      
user-data                                NONE                 users,active-users             8.7.1           89,012      
========================================================================================================================
```

### CSV Format
```csv
index_name,blocks,aliases,version_created,version_readable,document_count
my-app-logs-2023-01,WRITE,app-logs,7130499,7.13.4,1234567
old-watcher-index,READ_ONLY,watcher-current,7100299,7.10.2,45678
user-data,NONE,users,8070199,8.7.1,89012
```

### Block Types
- `READ`: Read operations blocked
- `WRITE`: Write operations blocked  
- `READ_ONLY`: Index is read-only
- `READ_ONLY_DELETE`: Read-only but allows deletions
- `NONE`: No blocks active

## Resume Functionality

### When to Use Resume
- SSH connection drops during long reindex operations
- Script interruption during reindex process
- Manual monitoring of existing reindex tasks

### Resume Task Only
```bash
# Only monitors task completion, no post-processing
python elasticsearch_index_manager.py --resume-task ABC123 --host ... --api-key ...
```

### Resume and Complete
```bash
# Completes full workflow: task monitoring + validation + replica settings + pipeline restoration + alias transfer
python elasticsearch_index_manager.py --resume-and-complete ABC123 source_index target_index --host ... --api-key ...
```

## Advanced Features

### Connection Resilience
- Exponential backoff retry logic (30s → 60s → 120s → 240s → 300s)
- Maximum 5 retry attempts for connection errors
- Automatic retry reset on successful connection

### Progress Tracking
- Real-time progress percentage
- Document processing speed calculation
- Time estimation with two methods:
  - Progress-based: Overall completion projection
  - Speed-based: Recent processing velocity (more accurate)

### Pipeline Management
- Temporary pipeline removal during reindex for better performance
- Automatic pipeline restoration after completion
- Support for custom pipeline names in resume mode

### Performance Optimizations
- Replica count set to 0 during reindex
- Index refresh after reindex completion
- Connection pooling and timeout management

### Version Filtering
- Support for semantic version comparison (major.minor.patch)
- Multiple comparison operators: lt, le, gt, ge, eq
- Handles both readable versions (8.7.1) and internal version numbers (8070199)
- Useful for migration planning and identifying outdated indices
- Can be combined with pattern matching for targeted analysis

## Logging

The script creates two types of logs:
- **Console output**: INFO level and above
- **File output**: `elasticsearch_manager.log` with DEBUG level and above

## Safety Features

- **Dry Run by Default**: Operations are simulated unless `--execute` flag is used
- **System Index Protection**: Automatically skips indices starting with `.`
- **Existence Checks**: Verifies index exists before attempting operations
- **Connection Validation**: Tests Elasticsearch connection before processing
- **Comprehensive Error Handling**: Graceful handling of failures with detailed logging

## Example Output

```
2025-08-27 10:30:15,123 - elasticsearch_manager - INFO - Connected to Elasticsearch cluster: my-cluster
2025-08-27 10:30:15,124 - elasticsearch_manager - INFO - Cluster status: green
2025-08-27 10:30:15,125 - elasticsearch_manager - INFO - Loaded 45 indices from trestle.index.7.csv
2025-08-27 10:30:15,126 - elasticsearch_manager - INFO - Processing index elastic_customproperties_v1_int with action: reindex
2025-08-27 10:30:15,127 - elasticsearch_manager - INFO - [DRY RUN] Would set index elastic_customproperties_v1_int to read-only
2025-08-27 10:30:15,128 - elasticsearch_manager - INFO - [DRY RUN] Would create index elastic_customproperties_v1_int_reindexed_1724745015
2025-08-27 10:30:15,129 - elasticsearch_manager - INFO - [DRY RUN] Would reindex from elastic_customproperties_v1_int to elastic_customproperties_v1_int_reindexed_1724745015
```
