#!/usr/bin/env python3
"""
Integration test that mirrors POST /auto-step/ with CAAFE enabled.
Runs against the real datasets/database and uses the OpenAI/DeepSeek
credentials from src/env.py so that the LLM-dependent CAAFE path is
exercised exactly like the frontend would.
"""

import json
import os
import sys
import time
from pathlib import Path

# Ensure project root on sys.path so frontend imports work when run directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Ensure frontend package-level imports (e.g., adda_connector) resolve
FRONTEND = ROOT / "frontend"
if str(FRONTEND) not in sys.path:
    sys.path.insert(0, str(FRONTEND))

from src.env import default_model, openai_api_key, openai_base_url  # noqa: E402
from frontend.app import app  # noqa: E402


def _ensure_llm_env():
    """Force env vars so caafe's OpenAI client picks them up."""
    os.environ["OPENAI_API_KEY"] = openai_api_key
    os.environ["OPENAI_API_BASE"] = openai_base_url
    os.environ["OPENAI_BASE_URL"] = openai_base_url
    # Some client code reads this custom name; keep it in sync.
    os.environ["DEFAULT_LLM_MODEL"] = default_model

    print("[env] OPENAI_API_KEY set from src/env.py")
    print(f"[env] OPENAI_API_BASE: {openai_base_url}")
    print(f"[env] DEFAULT_LLM_MODEL: {default_model}")


def run_autostep_with_caafe(
    dataset: str = "heart",
    model_type: str = "RF",
    max_search_depth: int = 1,
):
    """
    Fire a POST /auto-step/ request through Flask's test client to
    simulate the real API call (imports data to DB, runs A* search,
    executes comparison methods including CAAFE).
    """
    payload = {
        "taskDescription": f"Auto-step regression for {dataset}",
        "dataset": dataset,
        "model_type": model_type,
        "max_search_depth": max_search_depth,
        "use_performance_test": True,
        # Explicitly include CAAFE so the LLM path is exercised
        "comparison_methods": ["Adda", "CAAFE"],
    }

    print("[auto-step] Starting request with payload:")
    print(json.dumps(payload, indent=2))

    with app.test_client() as client:
        start = time.time()
        resp = client.post(
            "/auto-step/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        duration = time.time() - start

        try:
            resp_json = resp.get_json() if resp.is_json else json.loads(resp.data)
        except Exception:
            resp_json = {"status": "fail", "message": resp.data.decode("utf-8", "ignore")}

    print(f"[auto-step] HTTP {resp.status_code} in {duration:.1f}s")
    print(json.dumps(resp_json, indent=2, ensure_ascii=False))
    return resp_json


if __name__ == "__main__":
    _ensure_llm_env()
    run_autostep_with_caafe()
