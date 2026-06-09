import requests
import csv

# Set your Elasticsearch details directly here
ES_HOST = "https://observability-es.solutions.corelogic.com"
REPO = "gcs-observability"
API_KEY = "cTc4dFpaNEJNd1BrR2VtelU4T0k6R0t6Z0lLRExVd196UEJ3T1kxUDVzdw=="

headers = {"Authorization": f"ApiKey {API_KEY}"}

def fetch_snapshots():
    params = {
        "index_details": "true",
        "filter_path": "snapshots.snapshot,snapshots.index_details.logs-pci-*.size_in_bytes"
    }
    snapshots_url = f"{ES_HOST}/_snapshot/{REPO}/_all"
    try:
        resp = requests.get(snapshots_url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json().get("snapshots", [])
    except requests.RequestException as e:
        print(f"Error fetching snapshots: {e}")
        return []

def process_snapshots(snapshots):
    total_size_bytes = 0
    results = []
    for snap in snapshots:
        snapshot_name = snap.get("snapshot")
        index_details = snap.get("index_details", {})
        logs_pci_indices = [idx for idx in index_details.keys() if idx.startswith("logs-pci-")]

        if not logs_pci_indices:
            continue

        for idx in logs_pci_indices:
            size_bytes = index_details[idx].get("size_in_bytes", 0)
            size_gb = size_bytes / (1024 ** 3)
            results.append({
                "snapshot": snapshot_name,
                "index": idx,
                "size_gb": round(size_gb, 2)
            })
            total_size_bytes += size_bytes
    return results, total_size_bytes

def export_to_csv(results, filename="logs_pci_indices.csv"):
    with open(filename, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["snapshot", "index", "size_gb"])
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"Results exported to {filename}")

def main():
    snapshots = fetch_snapshots()
    if not snapshots:
        print("No snapshots found or error occurred.")
        return

    results, total_size_bytes = process_snapshots(snapshots)
    for row in results:
        print(f"Snapshot: {row['snapshot']}, Index: {row['index']}, Size: {row['size_gb']} GB")

    total_size_tb = total_size_bytes / (1024 ** 4)
    print(f"\nTotal size of all logs-pci-* indices (across all snapshots): {total_size_tb:.2f} TB")
    
    export_to_csv(results)

if __name__ == "__main__":
    main()