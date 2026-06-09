"""
Scan Kibana saved objects, detection rules, and Elasticsearch watchers
for references to the 'x_forwarded_for' field.
"""

import json
import urllib.request
import urllib.error
import base64
import ssl

# ── Configuration ────────────────────────────────────────────────────────────
ELASTIC_URL  = "https://observability-np-es.solutions.corelogic.com"   # Change me
KIBANA_URL   = "https://observability-np.solutions.corelogic.com"          # Change me
USERNAME     = "elastic"                                 # Change me
PASSWORD     = "8OS4TEjd39AUwq2qnqQZzCau"                                # Change me
SEARCH_FIELD = "x_forwarded_for"

# Set to True if you use a self-signed certificate
SKIP_TLS_VERIFY = False
# ─────────────────────────────────────────────────────────────────────────────

_token = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
_ssl_ctx = ssl.create_default_context()
if SKIP_TLS_VERIFY:
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE


def _request(url: str, *, kibana: bool = False):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {_token}")
    req.add_header("Content-Type", "application/json")
    if kibana:
        req.add_header("kbn-xsrf", "true")
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        print(f"  [HTTP {exc.code}] {url}")
        return {}


def contains_field(obj, field: str) -> bool:
    """Recursively check if `field` appears anywhere in `obj`."""
    raw = json.dumps(obj).lower()
    return field.lower() in raw


def _space_prefix(space_id: str) -> str:
    """Build Kibana API path prefix for a given space id."""
    return "" if space_id == "default" else f"/s/{space_id}"


def get_kibana_spaces() -> list[dict]:
    """
    Retrieve all Kibana spaces.
    Falls back to the default space if spaces API is unavailable.
    """
    data = _request(f"{KIBANA_URL}/api/spaces/space", kibana=True)
    if not isinstance(data, list) or not data:
        print("\n[WARN] Could not retrieve spaces; falling back to default space only.")
        return [{"id": "default", "name": "Default"}]

    spaces = []
    for sp in data:
        space_id = sp.get("id")
        if not space_id:
            continue
        spaces.append({"id": space_id, "name": sp.get("name", space_id)})

    if not spaces:
        spaces = [{"id": "default", "name": "Default"}]
    return spaces


# ── 1. Kibana Saved Objects ───────────────────────────────────────────────────
def scan_saved_objects(space_id: str, space_name: str):
    print(f"\n=== Kibana Saved Objects (space: {space_name} / {space_id}) ===")
    types = [
        "dashboard", "visualization", "lens", "map",
        "index-pattern", "search", "canvas-workpad",
    ]
    found = []
    per_page = 200
    prefix = _space_prefix(space_id)
    for obj_type in types:
        page = 1
        while True:
            url = (
                f"{KIBANA_URL}{prefix}/api/saved_objects/_find"
                f"?type={obj_type}&per_page={per_page}&page={page}"
            )
            data = _request(url, kibana=True)
            items = data.get("saved_objects", [])
            if not items:
                break
            for item in items:
                if contains_field(item, SEARCH_FIELD):
                    entry = {
                        "space": space_id,
                        "type": obj_type,
                        "id":   item.get("id"),
                        "title": item.get("attributes", {}).get("title", "<no title>"),
                    }
                    found.append(entry)
                    print(
                        f"  [MATCH] space={space_id}  type={obj_type}  "
                        f"id={entry['id']}  title={entry['title']}"
                    )
            if len(items) < per_page:
                break
            page += 1
    if not found:
        print("  No matches found.")
    return found


# ── 2. Kibana Detection Rules ─────────────────────────────────────────────────
def scan_detection_rules(space_id: str, space_name: str):
    print(f"\n=== Kibana Detection Rules (space: {space_name} / {space_id}) ===")
    found = []
    per_page = 100
    page = 1
    prefix = _space_prefix(space_id)
    while True:
        url = (
            f"{KIBANA_URL}{prefix}/api/detection_engine/rules/_find"
            f"?per_page={per_page}&page={page}"
        )
        data = _request(url, kibana=True)
        rules = data.get("data", [])
        if not rules:
            break
        for rule in rules:
            if contains_field(rule, SEARCH_FIELD):
                entry = {
                    "space": space_id,
                    "id":   rule.get("id"),
                    "name": rule.get("name", "<no name>"),
                    "type": rule.get("type"),
                }
                found.append(entry)
                print(
                    f"  [MATCH] space={space_id}  id={entry['id']}  "
                    f"name={entry['name']}  type={entry['type']}"
                )
        if len(rules) < per_page:
            break
        page += 1
    if not found:
        print("  No matches found.")
    return found


# ── 3. Field type in existing indices ───────────────────────────────────────
def scan_index_field_types():
    print("\n=== Field Type in Existing Indices ===")
    found = []

    # GET /_all/_mapping returns mappings for every index
    data = _request(f"{ELASTIC_URL}/_all/_mapping")
    if not data:
        print("  Could not retrieve index mappings.")
        return found

    for index_name, index_body in data.items():
        # Skip system indices
        if index_name.startswith("."):
            continue
        mappings = index_body.get("mappings", {})
        field_info = _find_field_in_mappings(mappings, SEARCH_FIELD)
        if field_info:
            entry = {
                "index":      index_name,
                "field":      SEARCH_FIELD,
                "field_type": field_info.get("type", "<object/nested>"),
                "mapping":    field_info,
            }
            found.append(entry)
            print(
                f"  [MATCH] index={index_name}  "
                f"field={SEARCH_FIELD}  type={entry['field_type']}"
            )

    if not found:
        print("  Field not found in any index mapping.")
    return found


def _find_field_in_mappings(mappings: dict, field: str) -> dict | None:
    """
    Walk a mappings dict (which may have a top-level 'properties' key or be
    nested under type names) and return the leaf mapping for `field`, or None.
    """
    # Support both 7.x (no type name) and older (has type name layer)
    props = mappings.get("properties")
    if props is None:
        # Try one level deeper (legacy type name)
        for v in mappings.values():
            if isinstance(v, dict) and "properties" in v:
                props = v["properties"]
                break
    if not props:
        return None
    return _walk_properties(props, field.split("."))


def _walk_properties(props: dict, parts: list) -> dict | None:
    """Recursively walk dot-notated field parts through nested properties."""
    key = parts[0]
    if key not in props:
        return None
    node = props[key]
    if len(parts) == 1:
        return node
    nested = node.get("properties") or node.get("fields", {})
    if not nested:
        return None
    return _walk_properties(nested, parts[1:])


# ── 4. Elasticsearch Watchers ─────────────────────────────────────────────────
def scan_watchers():
    print("\n=== Elasticsearch Watchers ===")
    found = []

    # Search all watchers via the .watches index
    url = f"{ELASTIC_URL}/.watches/_search?size=1000"
    data = _request(url)
    hits = data.get("hits", {}).get("hits", [])
    if not hits:
        print("  No watchers found (or .watches index not accessible).")
        return found

    for hit in hits:
        watcher_id = hit.get("_id")
        source = hit.get("_source", {})
        if contains_field(source, SEARCH_FIELD):
            entry = {
                "id":   watcher_id,
                "metadata": source.get("metadata", {}),
            }
            found.append(entry)
            print(f"  [MATCH] watcher_id={watcher_id}  metadata={entry['metadata']}")

    if not found:
        print("  No matches found.")
    return found


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Searching for field: '{SEARCH_FIELD}'")
    print(f"Kibana : {KIBANA_URL}")
    print(f"Elastic: {ELASTIC_URL}")

    spaces = get_kibana_spaces()
    print(f"\nDiscovered {len(spaces)} Kibana space(s).")

    saved_obj_matches = []
    rule_matches = []
    for space in spaces:
        space_id = space["id"]
        space_name = space["name"]
        saved_obj_matches.extend(scan_saved_objects(space_id, space_name))
        rule_matches.extend(scan_detection_rules(space_id, space_name))

    index_field_matches = scan_index_field_types()
    watcher_matches     = scan_watchers()

    total = (
        len(saved_obj_matches)
        + len(rule_matches)
        + len(index_field_matches)
        + len(watcher_matches)
    )
    print(f"\n{'='*60}")
    print(f"Total matches: {total}")
    print(f"  Saved objects   : {len(saved_obj_matches)}")
    print(f"  Detection rules : {len(rule_matches)}")
    print(f"  Index mappings  : {len(index_field_matches)}")
    print(f"  Watchers        : {len(watcher_matches)}")

    # Optionally dump results to JSON
    results = {
        "search_field":    SEARCH_FIELD,
        "saved_objects":   saved_obj_matches,
        "detection_rules": rule_matches,
        "index_mappings":  index_field_matches,
        "watchers":        watcher_matches,
    }
    output_file = "x_forwarded_for_scan_results.json"
    with open(output_file, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
