root@sbx-blue-logstash-vm-logs-2gpf:/home/ukondapureddy_solutions_corelogi/pci-logs-restore# cat logs-pci-restore.py
from datetime import datetime
import time
from os import environ as env
from elasticsearch import Elasticsearch
from elasticsearch import NotFoundError
import logging
import warnings
from logging.handlers import RotatingFileHandler
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Set
import uuid

LOG_FILE = "re_index.log"
CHECKPOINT_FILE = "processed_indices.json"

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(threadName)s — %(name)s — %(message)s"
)

file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=100 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

if not root_logger.handlers:
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

# Capture warnings
logging.captureWarnings(True)

# Enable Elasticsearch internals
logging.getLogger("elasticsearch").setLevel(logging.INFO)
logging.getLogger("elastic_transport").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.WARNING)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration  (override any value via environment variable)
# ---------------------------------------------------------------------------
ELASTICSEARCH_HOST = env.get(
    "ELASTICSEARCH_HOST",
    "https://observability-np-es.solutions.corelogic.com",
)
ELASTICSEARCH_API_KEY = env.get("ELASTICSEARCH_API_KEY", "NGowN2RKMEJMdUtFX2VXbmt4YlU6SHp0SXgwUUxBczEwOTZOZGcwS3JrZw==")
REPO_NAME             = env.get("REPO_NAME",             "gcs-observability")
INDEX_PREFIX          = env.get("INDEX_PREFIX",           "logs-pci")
TARGET_COMBINED_INDEX = env.get("TARGET_COMBINED_INDEX",  "pci-analysis-unified")
CONCURRENT_TASKS      = int(env.get("CONCURRENT_TASKS",  "3"))

if not ELASTICSEARCH_API_KEY:
    raise EnvironmentError(
        "ELASTICSEARCH_API_KEY environment variable is required but not set."
    )

# ---------------------------------------------------------------------------
# Elasticsearch client
# ---------------------------------------------------------------------------
while True:
    try:
        es = Elasticsearch(
            hosts=[ELASTICSEARCH_HOST],
            api_key=ELASTICSEARCH_API_KEY,
            request_timeout=300,
            retry_on_timeout=True,
            max_retries=3,  # This is for internal retries, but our loop is infinite
        )
        health = es.cluster.health()
        log.info("Cluster health: %s", health["status"])
        break  # Success, exit the loop
    except Exception as exc:
        log.error("Elasticsearch cluster not available: %s. Retrying in 10 seconds...", exc)
        time.sleep(10)

# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            # Store as set of tuples
            return set(tuple(pair) for pair in json.load(f))
    return set()

def save_checkpoint(processed_pairs):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump([list(pair) for pair in processed_pairs], f)

# ---------------------------------------------------------------------------
# Step 1 – Discover indices and map each to its LATEST snapshot
# ---------------------------------------------------------------------------
def get_index_snapshot_pairs() -> list[tuple[str, str]]:
    log.info("Scanning repository '%s' for snapshots…", REPO_NAME)
    index_snapshot_pairs: list[tuple[str, str]] = []
    seen_indices: set[str] = set()
    after_token: str | None = None

    while True:
        kwargs: dict = dict(
            repository=REPO_NAME,
            snapshot="logs-pci-*",
            size=200,
            sort="start_time",
            order="desc",
        )
        if after_token:
            kwargs["after"] = after_token

        res = es.snapshot.get(**kwargs)
        snapshots = res.get("snapshots", [])
        if not snapshots:
            break

        for snp in snapshots:
            snap_name = snp["snapshot"]
            for idx in snp.get("indices", []):
                if idx.startswith(INDEX_PREFIX):
                    index_snapshot_pairs.append((idx, snap_name))

        after_token = res.get("next")
        if not after_token:
            break

    log.info("Found %d unique (index, snapshot) pairs.", len(index_snapshot_pairs))
    return index_snapshot_pairs

# ---------------------------------------------------------------------------
# Step 2 – Create the target index (once, before the worker threads start)
# ---------------------------------------------------------------------------
def create_target_index() -> None:
    if es.indices.exists(index=TARGET_COMBINED_INDEX):
        log.info("Target index '%s' already exists – skipping creation.", TARGET_COMBINED_INDEX)
        return

    log.info("Creating target index '%s' with 10 shards…", TARGET_COMBINED_INDEX)
    es.indices.create(
        index=TARGET_COMBINED_INDEX,
        settings={
            "index.number_of_shards": 10,
            "index.number_of_replicas": 0,
            "index.codec": "best_compression",
            "index.lifecycle.name": None,
            "index.routing.allocation.include._tier_preference": "data_cold",
            "index.mapping.total_fields.limit": 2000,
            "index.refresh_interval": "-1",   # disabled during bulk load for speed
        },
    )

# ---------------------------------------------------------------------------
# Helpers – wait for restore / reindex to finish
# ---------------------------------------------------------------------------
def _wait_for_green(index: str, timeout_minutes: int = 250) -> None:
    log.info("    Waiting for '%s' to turn GREEN…", index)
    es.cluster.health(
        index=index,
        wait_for_status="green",
        timeout=f"{timeout_minutes}m",
    )

def _wait_for_task(task_id: str, poll_interval: int = 15, timeout: int = 14400) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        info = es.tasks.get(task_id=task_id)
        if info.get("completed"):
            return info.get("response", {})
        time.sleep(poll_interval)
    raise TimeoutError(f"Task {task_id} did not complete within {timeout // 60
} minutes.")

# ---------------------------------------------------------------------------
# Step 3 – Per-index worker: Restore → Reindex → Delete
# ---------------------------------------------------------------------------
def process_index(source_index: str, snapshot_name: str) -> tuple[str, str, bool]:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    temp_name = f"tmp-restore-{source_index}-{timestamp}-{unique_id}"

    try:
        # Clean up any leftover temp indices from prior failed/incomplete runs
        temp_pattern = f"tmp-restore-{source_index}-*"
        temp_indices = es.indices.get(index=temp_pattern, ignore_unavailable=True)
        for idx in temp_indices:
            log.warning("[%s] Stale temp index '%s' found – deleting before restore.", source_index, idx)
            try:
                es.indices.delete(index=idx)
            except NotFoundError:
                # Index does not exist, safe to ignore
                pass

        # Proceed with restore as before...
        log.info("[%s] Restoring from snapshot '%s'…", source_index, snapshot_name)
        # ... (rest of your code)
        es.snapshot.restore(
            repository=REPO_NAME,
            snapshot=snapshot_name,
            indices=source_index,
            rename_pattern=source_index,
            rename_replacement=temp_name,
            index_settings={
                "index.number_of_replicas": 0,
                "index.lifecycle.name": None,
                "index.routing.allocation.include._tier_preference": "data_cold",
            },
            include_global_state=False,
            include_aliases=False,
            wait_for_completion=True,
        )

        _wait_for_green(temp_name)

        # 3. Server-side reindex
        log.info("[%s] Server-side reindex → '%s'…", source_index, TARGET_COMBINED_INDEX)
        task_resp = es.reindex(
            source={"index": temp_name, "size": 5000},
            dest={"index": TARGET_COMBINED_INDEX, "op_type": "index"},
            script={
            "source": "ctx._id = params.snapshot + '-' + ctx._id",
             "params": {"snapshot": snapshot_name}
       },
            conflicts="proceed",
            slices="auto",
            wait_for_completion=False,
        )
        task_id = task_resp["task"]
        result = _wait_for_task(task_id)

        created  = result.get("created", 0)
        updated  = result.get("updated", 0)
        failures = result.get("failures", [])
        log.info(
            "[%s] Reindex done — created: %d, updated: %d, failures: %d",
            source_index, created, updated, len(failures),
        )
        if failures:
            log.warning("[%s] First failure sample: %s", source_index, failures[1])

        # 4. Delete the temporary restored index to reclaim disk space
        try:
            es.indices.delete(index=temp_name)
            log.info("[%s] ✓ Temp index deleted. Done.", source_index)
        except NotFoundError:
            log.info("[%s] Temp index %s already deleted or not found.", source_index, temp_name)
        except Exception as exc:
            log.error("[%s] ✗ Failed to delete temp index: %s", source_index, exc, exc_info=True)

        return source_index, snapshot_name, True

    except Exception as exc:
        log.error("[%s] ✗ Failed: %s", source_index, exc, exc_info=True)
        # Try to delete temp index if it exists, but ignore NotFoundError
        try:
            es.indices.delete(index=temp_name)
        except NotFoundError:
            log.info("[%s] Temp index %s already deleted or not found (cleanup after failure).", source_index, temp_name)
        except Exception:
            pass  # Ignore any other exception during cleanup
        return source_index, snapshot_name, False

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    index_snapshot_pairs = get_index_snapshot_pairs()
    processed_pairs = load_checkpoint()

    # Only process pairs not already done
    to_process = [(idx, snap) for idx, snap in index_snapshot_pairs if (idx, snap) not in processed_pairs]

    if not to_process:
        log.info("All (index, snapshot) pairs have been processed. Exiting.")
        return

    create_target_index()

    log.info(
        "Starting processing of %d (index, snapshot) pairs with %d concurrent workers…",
        len(to_process), CONCURRENT_TASKS,
    )

    with ThreadPoolExecutor(max_workers=CONCURRENT_TASKS) as executor:
        futures = {
            executor.submit(process_index, idx, snap): (idx, snap)
            for idx, snap in to_process
        }
        for future in as_completed(futures):
            try:
                idx, snap, ok = future.result()
                if ok:
                    processed_pairs.add((idx, snap))
                    save_checkpoint(processed_pairs)
                    log.info("Processed pair: (snapshot: %s, index: %s)", snap, idx)
                else:
                    log.error("Stopping due to failure on index: %s (snapshot: %s)", idx, snap)
                    return  # Stop immediately on failure
            except Exception as exc:
                log.error("Exception in worker: %s", exc, exc_info=True)

    # Re-enable refresh on the target index now that bulk loading is done
    es.indices.put_settings(
        index=TARGET_COMBINED_INDEX,
        settings={"index.refresh_interval": "1s"},
    )

if __name__ == "__main__":
    main()
