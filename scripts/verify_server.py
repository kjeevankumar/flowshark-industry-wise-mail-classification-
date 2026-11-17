"""Verification script to test live FastAPI server startup and endpoints."""

import sys
import threading
import time
import urllib.request
import json
import uvicorn

sys.path.insert(0, ".")

def run_server():
    config = uvicorn.Config("app.main:app", host="127.0.0.1", port=8001, log_level="warning")
    server = uvicorn.Server(config)
    server.run()

def main():
    print("Starting background Uvicorn server on port 8001...")
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Wait for server to bind
    time.sleep(2)

    try:
        # Test /api/email/health
        health_url = "http://127.0.0.1:8001/api/email/health"
        print(f"Testing {health_url}...")
        with urllib.request.urlopen(health_url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Health Response ({resp.status}): {data}")
            assert resp.status == 200
            assert data["status"] == "healthy"

        # Test /docs
        docs_url = "http://127.0.0.1:8001/docs"
        print(f"Testing {docs_url}...")
        with urllib.request.urlopen(docs_url, timeout=5) as resp:
            print(f"Swagger UI Response ({resp.status}): OK")
            assert resp.status == 200

        # Test /api/email/config-status
        config_url = "http://127.0.0.1:8001/api/email/config-status"
        print(f"Testing {config_url}...")
        with urllib.request.urlopen(config_url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Config Status ({resp.status}): configured={data['configured']}, masked_email={data.get('gmail_address_masked')}")
            assert resp.status == 200

        # Test /api/dashboard/summary
        summary_url = "http://127.0.0.1:8001/api/dashboard/summary"
        print(f"Testing {summary_url}...")
        with urllib.request.urlopen(summary_url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Dashboard Summary ({resp.status}): total_synced={data['total_synced']}, new_leads={data['new_leads_count']}, needs_review={data['needs_review_count']}")
            assert resp.status == 200

        # Test /api/emails?limit=3
        emails_url = "http://127.0.0.1:8001/api/emails?limit=3"
        print(f"Testing {emails_url}...")
        with urllib.request.urlopen(emails_url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Inbox Emails ({resp.status}): total={data['total']}, returned={len(data['items'])}")
            assert resp.status == 200
            assert len(data["items"]) > 0

        # Test frontend /
        root_url = "http://127.0.0.1:8001/"
        print(f"Testing Frontend UI at {root_url}...")
        with urllib.request.urlopen(root_url, timeout=5) as resp:
            content = resp.read().decode("utf-8")
            assert "<title>FlowShark AI" in content or "div id=\"root\"" in content
            print(f"Frontend UI Response ({resp.status}): OK (Found FlowShark root HTML)")

        print("\n=======================================================")
        print(">>> ALL LIVE FASTAPI & FRONTEND ENDPOINTS VERIFIED! <<<")
        print("=======================================================")
    except Exception as err:
        print(f"Verification failed: {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
