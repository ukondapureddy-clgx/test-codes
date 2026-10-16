# Reindex Guide: Migrating Old Indices with `elasticsearch_index_manager.py`

Step-by-step process for reindexing indices created before Elasticsearch 8.0 (for
example 7.6.2, 7.13.4, 7.17.9) so they are ready for an upgrade, keeping the
original index name working through an alias.

## How it works

For each `reindex` row in the CSV, the script:

1. Checks the source index exists and reads its settings, mappings and doc count.
2. **Blocks writes on the source** (`write` block). Writers get a 403 from here until the swap.
3. Creates a new index `<source>_<unix timestamp>` with the same settings and mappings
   (the `blocks` setting is not copied, so the new index is writable).
4. Temporarily removes `default_pipeline` and sets replicas to 0 for speed.
5. Runs the reindex task and waits for it to finish.
6. Refreshes the new index and **validates that doc counts match**.
7. Restores replicas (1) and `default_pipeline`.
8. Transfers any existing aliases to the new index.
9. With `--swap-original-name`: shows both doc counts and **asks for confirmation**.
   On `yes`, one atomic `_aliases` call deletes the old index and creates an alias
   with the old name pointing at the new index. Clients using the old name keep working.

If you do not confirm (or do not use `--swap-original-name`), the old index is kept
(write-blocked) and the new `<source>_<timestamp>` index holds the copy.

## Prerequisites

- Python 3 (Ubuntu: `sudo apt install -y python3 python3-venv python3-pip`)
- An Elasticsearch API key with `manage` privileges (create index, delete index,
  aliases, settings) and read on the target indices
- The **Elasticsearch** endpoint, not Kibana. Hostnames with `kb` are usually Kibana;
  the Elasticsearch one usually has `es`, e.g.
  `common-services-es-search-int.solutions.corelogic.com`
- Writers to the indices paused, or able to retry on 403 (see "Write outage" below)

## Setup

```bash
cd scripts/index/index-migration
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional sanity check: compiles the script without running it to catch a broken or
# truncated copy. No output means the file has no syntax errors; any error is printed
# with a line number.
python -m py_compile elasticsearch_index_manager.py

# Host is the BARE hostname: no https://, no port
export H="common-services-es-search-int.solutions.corelogic.com"
export API_KEY="<your api key>"

# Optional: confirm you are talking to Elasticsearch (JSON with cluster_name/version)
curl -sk -H "Authorization: ApiKey $API_KEY" https://$H/ | head -c 300; echo
```

Verify you have the current script (it must contain the `write` block fix):

```bash
grep -n 'block="write"' elasticsearch_index_manager.py   # expect one match
```

## Step 1: Get the list of indices to reindex

Run the analysis (read-only). It lists indices created before 8.0, with their blocks,
aliases, version and doc count:

```bash
python elasticsearch_index_manager.py --analyze --version-lt 8.0 \
    --host $H --port 443 --api-key "$API_KEY"

# Narrow it down (faster on big clusters)
python elasticsearch_index_manager.py --analyze --pattern "clp-spatial-dedupe-*" --version-lt 8.0 \
    --host $H --port 443 --api-key "$API_KEY"
```

Note any index that already has a block (the `Blocks` column) or aliases before you start.

## Step 2: Copy the indices into the CSV

Use the full, exact index names from the report (the table truncates long names). Keep
the header and set `Action` to `reindex`. `created_string` is informational only.

```bash
cat > reindex.csv <<'EOF'
"provided_name","created_string","Action"
"clp-spatial-dedupe-jun-2022","7.13.4","reindex"
"clp-spatial-dedupe-jan-1970","7.13.4","reindex"
"clp-spatial-dedupe-jan-2022","7.13.4","reindex"
EOF
```

Do not add a second row for the same index. Indices starting with `.` are skipped.

## Step 3: Dry run (no changes)

```bash
python elasticsearch_index_manager.py reindex.csv --host $H --port 443 --api-key "$API_KEY" \
    --swap-original-name
```

Without `--execute` the script only reads from the cluster and logs
`[DRY RUN] Would ...` lines. The `ERROR - Index ..._<ts> not found` line during the dry
run is expected (the target is never created).

## Step 4: Execute

Use tmux so an SSH drop does not interrupt it:

```bash
tmux new -s reindex
python elasticsearch_index_manager.py reindex.csv --host $H --port 443 --api-key "$API_KEY" \
    --swap-original-name --execute
```

For each index the script pauses:

```
Reindex finished: <index> (N docs) -> <index>_<ts> (N docs)
Deleting '<index>' is IRREVERSIBLE; '<index>' will become an alias of '<index>_<ts>'.
Type 'yes' to delete '<index>' and create the alias:
```

- Type `yes` only if both doc counts match.
- Anything else keeps the old index; the copy stays as `<index>_<ts>`.
- `--yes` skips the prompt (needed for non-interactive runs). Without it, a run with no
  terminal declines the swap instead of deleting.

First run with a small test index, and consider omitting `--swap-original-name` the
first time so the old index stays until you have checked the copy.

## Step 5: Verify

```
GET _alias/<index>                      # alias -> <index>_<ts>
GET <index>/_count                      # same count as before
GET <index>_<ts>/_settings?filter_path=*.settings.index.blocks    # empty = writable
GET _cat/indices/<prefix>*?v
```

Re-run the analysis to confirm the new indices report a version of 8.x or later:

```bash
python elasticsearch_index_manager.py --analyze --pattern "<prefix>*" \
    --host $H --port 443 --api-key "$API_KEY"
```

## Write outage and blocks

- Writes to the source are blocked from step 2 of the process until the swap. Writers
  get 403 `cluster_block_exception`; documents they fail to write are lost unless they
  retry or queue. Pause writers first, or run in a quiet window.
- Reindexing uses the `write` block on the source. It is deliberately not `read_only`,
  because `read_only` also blocks deleting the index and makes the swap fail.
- The new index has no blocks, so it accepts writes immediately. After the swap, writers
  using the old name write through the alias to the new index.
- If a reindex fails midway, the source stays write-blocked. Unblock it and retry:

  ```
  PUT <index>/_settings
  { "index.blocks.write": null }
  ```

## Resume an interrupted run

If the script was interrupted while the reindex task was running, find the task ID in the
log (`Task ID: ...`) and resume:

```bash
# Monitor only
python elasticsearch_index_manager.py --resume-task <TASK_ID> \
    --host $H --port 443 --api-key "$API_KEY"

# Monitor, validate, restore replicas, transfer aliases, and swap
python elasticsearch_index_manager.py --resume-and-complete <TASK_ID> <SOURCE_INDEX> <TARGET_INDEX> \
    --host $H --port 443 --api-key "$API_KEY" --swap-original-name --execute
```

Add `--original-pipeline <name>` to restore a `default_pipeline` that was removed during
the reindex.

## Cleaning up after a failed run

Only needed if an earlier run failed or used an older script. Check for a leftover
`read_only` block on the source (an empty `{}` is good) and clear it, otherwise the swap
fails with `cluster_block_exception ... index read-only (api)`:

```
GET <index>/_settings?filter_path=*.settings.index.blocks
PUT <index>/_settings
{ "index.blocks.read_only": null }
```

Delete leftover `<index>_<timestamp>` copies from failed runs before retrying:

```
GET _cat/indices/<prefix>*?v
DELETE <index>_<timestamp>
```

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `NotFoundError(404...)` on connect, or `{"statusCode":404,...}` from curl | You are hitting Kibana. Use the Elasticsearch hostname. |
| `Failed to resolve 'https'` | `--host` contains `https://`. Use the bare hostname and `--port 443`. |
| `cluster_block_exception ... index read-only (api)` on the swap | A `read_only` block is on the source (from an older script version or a failed run). Clear it (see below) and make sure `block="write"` is in the script. |
| `security_exception` / `unauthorized` | API key lacks privileges (`manage` on the indices). |
| Analysis looks stuck | It makes several calls per index. Wait, or narrow with `--pattern`. |
| `Swap declined` in the log | You did not type `yes`; the old index was kept. |
| `Reindex validation failed` | Doc counts differ. The swap is skipped; investigate before retrying. |
| Dry run shows no new indices on the cluster | Expected. Add `--execute`. |

## Command reference (additions for the swap)

| Flag | Purpose |
| --- | --- |
| `--execute` | Perform the operations (default is dry run). |
| `--swap-original-name` | After a validated reindex, delete the source index and create an alias with its name pointing to the new index. Irreversible. |
| `--yes` | Skip the confirmation prompt before deleting the source index. |

See `README.md` for the remaining options (analysis filters, resume, authentication).
