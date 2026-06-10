#!/usr/bin/env python3
"""
Standalone CAAFE integration test.
- Uses real dataset files from src/env.py (e.g., heart/train_new.csv).
- Forces OpenAI/DeepSeek env vars from src/env.py so caafe's LLM calls work.
- Bypasses Adda/auto-step; directly invokes ComparisonEngine with only CAAFE.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(FRONTEND) not in sys.path:
    sys.path.insert(0, str(FRONTEND))

from src.env import dataset_path, default_model, openai_api_key, openai_base_url  # noqa: E402
from src.llm.tests.test_util import task_config  # noqa: E402
from frontend.comparison_methods import run_comparison_from_csv  # noqa: E402


def _ensure_llm_env():
    os.environ["OPENAI_API_KEY"] = openai_api_key
    os.environ["OPENAI_API_BASE"] = openai_base_url
    os.environ["OPENAI_BASE_URL"] = openai_base_url
    os.environ["DEFAULT_LLM_MODEL"] = default_model
    print("[env] OPENAI_API_KEY set from src/env.py")
    print(f"[env] OPENAI_API_BASE: {openai_base_url}")
    print(f"[env] DEFAULT_LLM_MODEL: {default_model}")


def run_caafe(dataset: str = "heart"):
    """Load dataset, then run only CAAFE via ComparisonEngine."""
    task_name, target_col, task_type = task_config(dataset.lower())
    csv_file = Path(dataset_path) / task_name / "train_new.csv"
    if not csv_file.exists():
        raise FileNotFoundError(f"Dataset CSV not found: {csv_file}")

    print(f"[caafe] Dataset: {csv_file}")
    print(f"[caafe] Target column: {target_col}, task_type: {task_type}")
    print("[caafe] Running ComparisonEngine with methods=['CAAFE'] ...")

    results = run_comparison_from_csv(
        csv_path=str(csv_file),
        target_column=target_col,
        task_type=task_type,
        methods=["CAAFE"],
        time_limit=300,  # allow more time for LLM
    )

    print("[caafe] Completed. Summary:")
    print(json.dumps(_json_safe(results), indent=2, ensure_ascii=False))
    return results


def _json_safe(obj):
    """Convert nested results to JSON-serializable structures."""
    import numpy as np
    import pandas as pd

    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="list")
    if isinstance(obj, pd.Series):
        return obj.to_list()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


if __name__ == "__main__":
    _ensure_llm_env()
    run_caafe()
