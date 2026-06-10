#!/usr/bin/env python3
"""
深入调查PGML的所有表，寻找特征存储位置
"""

import sys
import os
import pandas as pd
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.env import *
import psycopg2

def investigate_pgml_tables():
    """调查PGML的所有表结构"""
    print("🔍 深入调查PGML表结构")

    try:
        # 连接到数据库
        conn = psycopg2.connect(
            host='localhost',
            port=pg_port,
            database=pg_db,
            user=pg_user
        )
        cursor = conn.cursor()

        # 1. 查看pgml schema下的所有表
        print(f"\n📋 PGML schema下的所有表:")
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'pgml'
            ORDER BY table_name
        """)
        pgml_tables = [row[0] for row in cursor.fetchall()]
        print(f"表数量: {len(pgml_tables)}")
        for table in pgml_tables:
            print(f"  - {table}")

        # 2. 检查关键表的详细结构
        key_tables = ['projects', 'models', 'deployments', 'snapshots', 'recipes']

        for table_name in key_tables:
            if table_name in pgml_tables:
                print(f"\n🔧 表结构: pgml.{table_name}")
                try:
                    cursor.execute(f"""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema = 'pgml' AND table_name = '{table_name}'
                        ORDER BY ordinal_position
                    """)
                    columns = cursor.fetchall()
                    for col in columns:
                        print(f"  {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")

                    # 查看数据样本
                    cursor.execute(f"SELECT COUNT(*) FROM pgml.{table_name}")
                    row_count = cursor.fetchone()[0]
                    print(f"  行数: {row_count}")

                    if row_count > 0:
                        cursor.execute(f"SELECT * FROM pgml.{table_name} LIMIT 3")
                        rows = cursor.fetchall()
                        print(f"  数据样本: {rows}")
                except Exception as e:
                    print(f"  ❌ 查询失败: {e}")

        # 3. 查看最近的训练项目详情
        print(f"\n🔍 最近的训练项目详情:")
        try:
            cursor.execute("""
                SELECT p.id, p.name, p.task, p.algorithm, p.status, p.created_at,
                       COUNT(m.id) as model_count
                FROM pgml.projects p
                LEFT JOIN pgml.models m ON p.id = m.project_id
                GROUP BY p.id, p.name, p.task, p.algorithm, p.status, p.created_at
                ORDER BY p.created_at DESC
                LIMIT 5
            """)
            projects = cursor.fetchall()
            for project in projects:
                print(f"  项目ID: {project[0]}, 名称: {project[1]}, 任务: {project[2]}")
                print(f"    算法: {project[3]}, 状态: {project[4]}, 模型数: {project[5]}")
                print(f"    创建时间: {project[6]}")
        except Exception as e:
            print(f"  ❌ 查询失败: {e}")

        # 4. 查看模型详情，寻找特征相关信息
        print(f"\n🔍 模型详情:")
        try:
            cursor.execute("""
                SELECT m.id, m.project_id, m.algorithm, m.hyperparameters, m.metrics,
                       m.created_at, p.name as project_name
                FROM pgml.models m
                JOIN pgml.projects p ON m.project_id = p.id
                ORDER BY m.created_at DESC
                LIMIT 3
            """)
            models = cursor.fetchall()
            for model in models:
                print(f"  模型ID: {model[0]}, 项目: {model[6]}")
                print(f"    算法: {model[2]}")
                print(f"    超参数: {model[3]}")
                print(f"    指标: {model[4]}")
                print(f"    创建时间: {model[5]}")
        except Exception as e:
            print(f"  ❌ 查询失败: {e}")

        # 5. 查看是否有特征相关的表或字段
        print(f"\n🔍 寻找特征相关的表/字段:")
        try:
            # 搜索包含feature、transform、preprocess等关键词的表和字段
            cursor.execute("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'pgml'
                AND (
                    column_name ILIKE '%feature%'
                    OR column_name ILIKE '%transform%'
                    OR column_name ILIKE '%preprocess%'
                    OR column_name ILIKE '%engineer%'
                )
                ORDER BY table_name, column_name
            """)
            feature_columns = cursor.fetchall()
            if feature_columns:
                print(f"  找到特征相关字段:")
                for table, column in feature_columns:
                    print(f"    {table}.{column}")
            else:
                print(f"  ❌ 没有找到明显的特征相关字段")
        except Exception as e:
            print(f"  ❌ 搜索失败: {e}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ 调查失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    investigate_pgml_tables()