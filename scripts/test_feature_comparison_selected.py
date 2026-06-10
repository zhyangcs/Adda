#!/usr/bin/env python3
"""
Smoke test for comparison methods (AutoFeat, MADlib, CAAFE) with configurable downstream model.
Generates a synthetic classification dataset, filters available methods, and runs the comparison
engine using the same downstream model type (RF/XGB/LightGBM) for fairness.
"""

import os
import sys
import time
from typing import List

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from frontend.comparison_methods import ComparisonEngine  # noqa: E402


def create_classification_dataset(n_samples: int = 300, n_features: int = 12, n_informative: int = 6):
    """Build a balanced binary classification dataset."""
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=n_informative,
        n_redundant=max(0, n_features - n_informative - 2),
        n_repeated=0,
        n_clusters_per_class=1,
        flip_y=0.01,
        class_sep=1.2,
        random_state=42
    )
    feature_names = [f"feature_{i+1}" for i in range(n_features)]
    return pd.DataFrame(X, columns=feature_names), pd.Series(y)


def run_selected_methods(methods: List[str], model_type: str = "RF"):
    """Run ComparisonEngine on selected methods with a synthetic dataset."""
    X, y = create_classification_dataset()
    engine = ComparisonEngine()

    available = set(engine.get_available_methods())
    chosen = [m for m in methods if m in available]

    if not chosen:
        print("No selected methods are available; skipping.")
        return None

    print(f"Running comparison for methods: {chosen} with model_type={model_type}")
    start = time.time()
    results = engine.run_comparison(
        X=X,
        y=y,
        task_type="classify",
        methods=chosen,
        time_limit=120,
        model_type=model_type
    )
    elapsed = time.time() - start

    print(f"Completed in {elapsed:.2f}s")
    print("\nPerformance (AUC, Accuracy):")
    for i, method in enumerate(results["methods"]):
        auc = results["performance_data"]["auc"][i]
        acc = results["performance_data"]["accuracy"][i]
        print(f"  {method:10s} | AUC={auc:.4f} | Acc={acc:.4f}")

    print("\nTiming (total, feature_generation):")
    for i, method in enumerate(results["methods"]):
        total_t = results["time_data"]["totalTime"][i]
        feat_t = results["time_data"]["featureGenerationTime"][i]
        print(f"  {method:10s} | total={total_t:.2f}s | feature_gen={feat_t:.2f}s")

    return results


def main():
    # Target methods: AutoFeat, MADlib, CAAFE (skip RL or other methods)
    methods_to_test = ["AutoFeat", "MADlib", "CAAFE"]
    model_type = os.getenv("COMPARE_MODEL_TYPE", "XGB")
    run_selected_methods(methods_to_test, model_type=model_type)


if __name__ == "__main__":
    main()

