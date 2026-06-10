#!/usr/bin/env python3
"""
简单的MADlib特征工程冒烟测试：
- 在PostgreSQL中使用MADlib对分类列做编码
- 调用MadlibMethod.fit_predict确保管线可跑通
"""

import os
import unittest
import pandas as pd

try:
    import psycopg2
except ImportError:
    psycopg2 = None

from src.env import pg_user, pg_db, pg_port
from frontend.comparison_methods import MadlibMethod, MADLIB_AVAILABLE


def _require_db_or_skip():
    """缺少依赖或连接失败时跳过测试（不预检查扩展，交由 madpack 自动安装）"""
    if not MADLIB_AVAILABLE or psycopg2 is None:
        raise unittest.SkipTest("psycopg2/MADlib 不可用，跳过测试")

    conn = None
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=pg_port,
            database=pg_db,
            user=pg_user,
        )
    except Exception as exc:
        raise unittest.SkipTest(f"无法连接数据库: {exc}")
    finally:
        if conn is not None:
            conn.close()


class TestMadlibMethod(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _require_db_or_skip()

    def test_fit_predict_smoke(self):
        df = pd.DataFrame(
            {
                "age": [20, 25, 30, 35, 40, 45, 50, 55, 60, 65],
                "gender": ["M", "F"] * 5,
                "chol": [180, 190, 185, 210, 200, 195, 205, 215, 225, 230],
                "smoker": [True, False] * 5,
                "target": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
            }
        )

        X = df.drop(columns=["target"])
        y = df["target"]

        method = MadlibMethod(
            db_config={
                "host": "localhost",
                "port": pg_port,
                "database": pg_db,
                "user": pg_user,
            }
        )

        metrics = method.fit_predict(X, y, task_type="classify")
        feature_info = method.get_feature_info()

        self.assertIn("accuracy", metrics)
        self.assertGreater(len(feature_info.get("feature_names", [])), 0)
        # fit_predict 在训练集（80%）上做特征生成，因此行数应与训练集一致
        self.assertEqual(feature_info["generated_features"].shape[0], len(method._X_train))


if __name__ == "__main__":
    unittest.main(verbosity=2)
