"""Trigger export bundle generation via the API."""
import json
import sys
import urllib.request

url = "http://localhost:8000/export"
req = urllib.request.Request(
    url,
    data=b"{}",
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"ERROR {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
except urllib.error.URLError as e:
    print(f"Connection error: {e.reason}", file=sys.stderr)
    sys.exit(1)

print(f"Bundle   : {result['bundle_path']}")
print(f"Manifest : {result['manifest_path']}")
print(f"Records  : {result['record_count']}")
print(f"Entries  : {result.get('manifest_entry_count', 'N/A')}")
