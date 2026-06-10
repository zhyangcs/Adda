#!/usr/bin/env python3
"""
分析PGML特征工程，找出如何获取生成的特征
"""

import sys
import os
import pandas as pd
import numpy as np
from sklearn.datasets import make_classification

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.env import *
import psycopg2

def test_pgml_feature_generation():
    """测试PGML的特征生成功能"""
    print("🔍 分析PGML特征生成机制")

    try:
        # 连接到数据库
        conn = psycopg2.connect(
            host='localhost',
            port=pg_port,
            database=pg_db,
            user=pg_user
        )
        cursor = conn.cursor()

        # 创建测试数据
        X, y = make_classification(n_samples=100, n_features=5, n_informative=3, n_redundant=1, random_state=42)
        X_df = pd.DataFrame(X, columns=['feature_1', 'feature_2', 'feature_3', 'feature_4', 'feature_5'])
        y_series = pd.Series(y)

        print(f"📊 创建测试数据: {X_df.shape}")

        # 创建临时表
        table_name = "pgml_feature_test"
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")

        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                feature_1 FLOAT,
                feature_2 FLOAT,
                feature_3 FLOAT,
                feature_4 FLOAT,
                feature_5 FLOAT,
                target INTEGER
            )
        """)

        # 插入数据
        for i, (_, row) in enumerate(X_df.iterrows()):
            cursor.execute(f"""
                INSERT INTO {table_name} (feature_1, feature_2, feature_3, feature_4, feature_5, target)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (float(row['feature_1']), float(row['feature_2']), float(row['feature_3']), float(row['feature_4']), float(row['feature_5']), int(y_series[i])))

        conn.commit()
        print("✅ 数据插入完成")

        # 测试不同的PGML特征工程方法

        print(f"\n🔧 方法1: pgml.train() 基础训练")
        try:
            cursor.execute("""
                SELECT pgml.train('feature_test_basic', 'classification', %s, 'target')
            """, (table_name,))
            print("✅ 基础训练完成")
        except Exception as e:
            print(f"❌ 基础训练失败: {e}")

        print(f"\n🔧 方法2: pgml.train_joint() 联合训练")
        try:
            cursor.execute("""
                SELECT pgml.train_joint('feature_test_joint', 'classification', %s, ARRAY['target'], 'random_forest')
            """, (table_name,))
            print("✅ 联合训练完成")
        except Exception as e:
            print(f"❌ 联合训练失败: {e}")

        print(f"\n🔧 方法3: 查询训练后的特征")
        try:
            # 查看pgml内部表，了解特征工程结果
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'pgml' AND table_name LIKE '%feature%'
            """)
            pgml_tables = cursor.fetchall()
            print(f"📋 PGML相关表: {[t[0] for t in pgml_tables]}")

            # 查询部署信息 - 先查看表结构
            try:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'pgml' AND table_name = 'deployments'
                """)
                columns = [row[0] for row in cursor.fetchall()]
                print(f"📋 deployments表字段: {columns}")

                # 使用存在的字段查询
                if columns:
                    query_fields = ', '.join(columns)
                    cursor.execute(f"""
                        SELECT {query_fields} FROM pgml.deployments
                        ORDER BY id DESC LIMIT 5
                    """)
                    deployments = cursor.fetchall()
                    print(f"📋 最近部署: {deployments}")
            except Exception as table_error:
                print(f"📋 查询部署信息失败: {table_error}")

        except Exception as e:
            print(f"❌ 查询失败: {e}")
            conn.rollback()  # 回滚事务

        print(f"\n🔧 方法4: 尝试获取特征重要性")
        try:
            # 查询特征重要性
            cursor.execute("""
                SELECT * FROM pgml.inspect('feature_test_joint')
            """)
            inspection = cursor.fetchall()
            print(f"📊 模型检查结果: {inspection}")

        except Exception as e:
            print(f"❌ 特征重要性查询失败: {e}")

        print(f"\n🔧 方法5: 使用pgml进行预测来获取特征变换")
        try:
            # 使用训练好的模型进行预测，这可能触发特征变换
            cursor.execute("""
                SELECT pgml.predict('feature_test_joint', %s)
            """, (table_name,))
            predictions = cursor.fetchall()
            print(f"📊 预测结果样例: {predictions[:5]}")

        except Exception as e:
            print(f"❌ 预测失败: {e}")

        print(f"\n🎯 结论:")
        print("1. PGML内部进行了特征工程，但外部难以直接获取生成的特征")
        print("2. PGML的特征工程是模型训练的一部分，不独立暴露")
        print("3. 对比方法中PGML的作用更多是展示其内部特征工程能力")
        print("4. 如果需要看到具体的生成特征，可能需要使用PGML的特定API")

        # 清理
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ 分析失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pgml_feature_generation()