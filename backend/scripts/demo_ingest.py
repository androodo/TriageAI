"""Demo ingestion script — loads sample CI run to BuildLens for local testing."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from httpx import AsyncClient

API_BASE = "http://localhost:8000"


async def ingest_demo_run():
    """Ingest a single demo CI run for testing."""

    demo_run = {
        "repo_name": "demo/payment-service",
        "branch": "main",
        "commit_sha": "deadbeefcafe",
        "pipeline_id": "demo-001",
        "environment": "development",
        "status": "failed",
        "test_suite_name": "integration",
        "failed_test_names": ["test_payment_timeout", "test_checkout"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_log_text": """FAILED tests/test_payment.py::test_payment_timeout
Error: asyncio.TimeoutError: Request to /api/payment timed out after 30s

FAILED tests/test_checkout.py::test_checkout
AssertionError: expected 200 got 500
  +  where 200 = <Response>.status_code
  +  and   where 500 = <Response>.status_code

2 failed, 12 passed in 34.56s""",
    }

    async with AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/api/runs/ingest",
            json=demo_run,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        result = response.json()

    print(f"\n✅ Demo CI run ingested successfully")
    print(f"   Run ID: {result['id']}")
    print(f"   Triage available: {result['triage_available']}")
    print(f"\n🔗 View at http://localhost:3000/runs/{result['id']} (when frontend is running)")
    print(f"   Or call API: GET http://localhost:8000/api/runs/{result['id']}")


if __name__ == "__main__":
    print("🚀 Ingesting demo CI run to BuildLens AI...")
    try:
        asyncio.run(ingest_demo_run())
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n📝 Make sure:")
        print("   1. BuildLens backend is running at http://localhost:8000")
        print("   2. PostgreSQL is running (docker-compose up postgres backend)")
        print("   3. OPENAI_API_KEY is set (see .env.example)")
