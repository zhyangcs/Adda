#!/usr/bin/env python3
"""
修复版特征工程框架对比测试脚本
使用heart数据集测试Baseline、AutoFeat和PGML方法
"""

import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, List, Any

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入配置
from src.env import pg_user, pg_db, pg_port

# 导入对比方法模块
from frontend.comparison_methods import ComparisonEngine, run_comparison_from_csv

def test_comparison_methods_fixed():
    """测试修复后的特征工程对比方法"""
    print("=" * 80)
    print("🚀 修复版特征工程框架对比测试 - Heart数据集")
    print("=" * 80)

    # 数据集路径
    csv_path = "/home/lizhenyu/projects/autofe/dataset/task/heart/train_new.csv"
    target_column = "tenyearchd"  # 10年冠心病风险
    task_type = "classify"  # 分类任务

    print(f"📁 数据集: {csv_path}")
    print(f"🎯 目标列: {target_column}")
    print(f"📊 任务类型: {task_type}")
    print("-" * 80)

    # 检查数据集
    if not os.path.exists(csv_path):
        print(f"❌ 数据集文件不存在: {csv_path}")
        return

    try:
        # 读取数据
        df = pd.read_csv(csv_path)
        print(f"✅ 数据集加载成功")
        print(f"📋 数据形状: {df.shape}")
        print(f"📋 目标列分布: {df[target_column].value_counts().to_dict()}")
        print("-" * 80)

        # 测试方法列表
        methods_to_test = ["Baseline", "AutoFeat"]

        print(f"🧪 测试方法: {methods_to_test}")
        print("-" * 80)

        # 创建对比引擎
        engine = ComparisonEngine()

        # 显示可用方法
        available_methods = engine.get_available_methods()
        print(f"🔧 可用方法: {available_methods}")
        print("-" * 80)

        # 分离特征和目标
        X = df.drop(columns=[target_column, "id"])  # 删除id列，不是有效特征
        y = df[target_column]

        print(f"📊 特征矩阵形状: {X.shape}")
        print(f"🎯 目标向量形状: {y.shape}")
        print(f"📋 特征列: {list(X.columns)}")
        print("-" * 80)

        # 运行对比测试
        print("🏃‍♂️ 开始运行特征工程对比测试...")
        print()

        results = engine.run_comparison(
            X=X,
            y=y,
            task_type=task_type,
            methods=methods_to_test,
            time_limit=180  # 每个方法3分钟
        )

        # 显示结果
        print("📊 测试结果:")
        print("=" * 80)

        if results and results.get("methods"):
            print(f"✅ 成功完成 {len(results['methods'])} 个方法的测试")
            print()

            # 性能对比
            print("🎯 性能指标对比:")
            print("-" * 50)
            print(f"{'方法':12} | {'AUC':<8} | {'Accuracy':<8} | {'F1':<8}")
            print("-" * 50)
            for i, method in enumerate(results["methods"]):
                auc = results["performance_data"]["auc"][i] if results["performance_data"]["auc"] else 0.0
                accuracy = results["performance_data"]["accuracy"][i] if results["performance_data"]["accuracy"] else 0.0
                f1 = results["performance_data"]["f1"][i] if results["performance_data"]["f1"] else 0.0
                print(f"{method:12} | {auc:<8.4f} | {accuracy:<8.4f} | {f1:<8.4f}")

            print()

            # 时间对比
            print("⏱️  时间对比 (秒):")
            print("-" * 60)
            print(f"{'方法':12} | {'总计':<8} | {'预处理':<8} | {'特征生成':<10} | {'训练':<8}")
            print("-" * 60)
            for i, method in enumerate(results["methods"]):
                total_time = results["time_data"]["totalTime"][i]
                prep_time = results["time_data"]["preprocessingTime"][i]
                feature_time = results["time_data"]["featureGenerationTime"][i]
                train_time = results["time_data"]["trainingTime"][i]
                print(f"{method:12} | {total_time:<8.2f} | {prep_time:<8.2f} | {feature_time:<10.2f} | {train_time:<8.2f}")

            print()

            # 特征对比
            print("🔧 特征对比:")
            print("-" * 45)
            print(f"{'方法':12} | {'原始':<6} | {'生成后':<8} | {'新增':<6}")
            print("-" * 45)
            for i, method in enumerate(results["methods"]):
                orig_count = results["feature_data"]["original_feature_count"][i]
                gen_count = results["feature_data"]["generated_feature_count"][i]
                new_count = results["feature_data"]["new_features_count"][i]
                print(f"{method:12} | {orig_count:<6} | {gen_count:<8} | {new_count:<6}")

            print()

            # 详细结果
            print("📋 详细结果:")
            print("-" * 60)
            for method in results["methods"]:
                if method in results["detailed_results"]:
                    detail = results["detailed_results"][method]
                    feature_info = detail.get("feature_info", {})
                    description = feature_info.get("description", "No description available")
                    new_features = feature_info.get("new_feature_names", [])
                    print(f"{method}: {description}")
                    if new_features:
                        print(f"  新增特征示例: {new_features[:3]}...")

            print()
            print("✅ Baseline和AutoFeat测试完成！")

        else:
            print("❌ 测试失败，没有返回有效结果")

    except Exception as e:
        print(f"❌ 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

def test_pgml_with_project_config():
    """使用项目配置测试PGML方法"""
    print("=" * 80)
    print("🗄️  PGML方法测试（使用项目配置）")
    print("=" * 80)

    print(f"📋 项目数据库配置:")
    print(f"   - 数据库: {pg_db}")
    print(f"   - 用户: {pg_user}")
    print(f"   - 端口: {pg_port}")
    print()

    # 数据集路径
    csv_path = "/home/lizhenyu/projects/autofe/dataset/task/heart/train_new.csv"
    target_column = "tenyearchd"

    try:
        # 测试主数据库连接
        print("🔗 测试主数据库连接...")
        import psycopg2

        try:
            conn = psycopg2.connect(dbname=pg_db, user=pg_user, port=pg_port)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"✅ 主数据库连接成功: {version[:50]}...")

            # 检查是否有数据
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
            table_count = cursor.fetchone()[0]
            print(f"📊 数据库中有 {table_count} 个表")

            cursor.close()
            conn.close()

            # 测试PGML数据库连接
            print("\n🔗 测试PGML数据库连接...")
            try:
                conn_pgml = psycopg2.connect(dbname="postgresml", user="postgresml", port=5433)
                cursor_pgml = conn_pgml.cursor()
                cursor_pgml.execute("SELECT version();")
                pgml_version = cursor_pgml.fetchone()[0]
                print(f"✅ PGML数据库连接成功: {pgml_version[:50]}...")

                # 检查pgml扩展
                cursor_pgml.execute("SELECT COUNT(*) FROM pg_extension WHERE extname = 'pgml';")
                pgml_exists = cursor_pgml.fetchone()[0] > 0
                if pgml_exists:
                    print("✅ PGML扩展已安装")
                else:
                    print("❌ PGML扩展未安装，尝试安装...")
                    try:
                        cursor_pgml.execute("CREATE EXTENSION IF NOT EXISTS pgml;")
                        conn_pgml.commit()
                        print("✅ PGML扩展安装成功")
                    except Exception as e:
                        print(f"❌ PGML扩展安装失败: {e}")
                        return

                cursor_pgml.close()
                conn_pgml.close()

                # 使用PGML数据库配置运行测试
                print("\n🧪 运行PGML特征工程测试...")
                pgml_db_config = {
                    'host': 'localhost',
                    'port': 5433,
                    'database': 'postgresml',
                    'user': 'postgresml',
                    'password': ''  # PGML通常不需要密码
                }

                results = run_comparison_from_csv(
                    csv_path=csv_path,
                    target_column=target_column,
                    task_type="classify",
                    methods=["PGML"],
                    time_limit=180,
                    db_config=pgml_db_config
                )

                if results and results.get("methods"):
                    print("✅ PGML测试成功")
                    method = results["methods"][0]
                    auc = results["performance_data"]["auc"][0]
                    feature_time = results["time_data"]["featureGenerationTime"][0]
                    gen_features = results["feature_data"]["generated_feature_count"][0]
                    print(f"📊 性能: AUC = {auc:.4f}")
                    print(f"⏱️  特征生成时间: {feature_time:.2f}s")
                    print(f"🔧 生成特征数量: {gen_features}")
                else:
                    print("❌ PGML测试失败，没有返回结果")

            except Exception as e:
                print(f"❌ PGML数据库连接失败: {str(e)}")
                print("💡 请检查PGML是否运行在5433端口")

        except Exception as e:
            print(f"❌ 主数据库连接失败: {str(e)}")
            print("💡 请检查PostgreSQL是否运行以及配置是否正确")

    except Exception as e:
        print(f"❌ PGML测试失败: {str(e)}")

def test_autofeat_detailed():
    """详细测试AutoFeat功能"""
    print("=" * 80)
    print("🔬 AutoFeat详细功能测试")
    print("=" * 80)

    # 数据集路径
    csv_path = "/home/lizhenyu/projects/autofe/dataset/task/heart/train_new.csv"
    target_column = "tenyearchd"

    try:
        # 读取数据
        df = pd.read_csv(csv_path)
        X = df.drop(columns=[target_column, "id"])
        y = df[target_column]

        # 只选择数值型特征
        X_numeric = X.select_dtypes(include=[np.number])
        print(f"📊 数值型特征: {list(X_numeric.columns)}")
        print(f"📊 数值型特征形状: {X_numeric.shape}")

        # 测试AutoFeat
        from autofeat import AutoFeatClassifier
        import time

        print("\n🧪 创建AutoFeat分类器...")
        auto_feat = AutoFeatClassifier(
            categorical_cols=False,
            feateng_steps=2,
            n_jobs=1,
            verbose=1
        )

        print("🏃‍♂️ 开始训练AutoFeat...")
        start_time = time.time()

        auto_feat.fit(X_numeric, y)

        fit_time = time.time() - start_time
        print(f"✅ AutoFeat训练完成，耗时: {fit_time:.2f}s")

        print("🔄 转换数据...")
        start_time = time.time()

        X_generated = auto_feat.transform(X_numeric)

        transform_time = time.time() - start_time
        print(f"✅ 数据转换完成，耗时: {transform_time:.2f}s")

        print(f"📊 原始特征数量: {X_numeric.shape[1]}")
        print(f"📊 生成后特征数量: {X_generated.shape[1]}")
        print(f"🆕 新增特征数量: {X_generated.shape[1] - X_numeric.shape[1]}")

        # 显示新增特征
        original_cols = set(X_numeric.columns)
        new_features = [col for col in X_generated.columns if col not in original_cols]

        if new_features:
            print(f"\n🔧 新增特征示例（前10个）:")
            for i, feature in enumerate(new_features[:10]):
                print(f"  {i+1:2d}. {feature}")
        else:
            print("\n⚠️  没有生成新的特征")

        # 使用生成的特征训练模型
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score

        print(f"\n🎯 使用生成特征训练随机森林...")
        rf = RandomForestClassifier(n_estimators=100, random_state=42)

        cv_scores = cross_val_score(rf, X_generated, y, cv=5, scoring='roc_auc')

        print(f"📊 5折交叉验证AUC: {cv_scores.mean():.4f} (±{cv_scores.std():.4f})")

        # 与原始特征对比
        print(f"\n📊 使用原始特征的对比:")
        rf_original = RandomForestClassifier(n_estimators=100, random_state=42)
        cv_scores_original = cross_val_score(rf_original, X_numeric, y, cv=5, scoring='roc_auc')
        print(f"📊 原始特征AUC: {cv_scores_original.mean():.4f} (±{cv_scores_original.std():.4f})")

        # 计算改进
        improvement = cv_scores.mean() - cv_scores_original.mean()
        print(f"\n📈 AUC改进: {improvement:+.4f}")

        if improvement > 0:
            print(f"✅ AutoFeat特征工程提升了模型性能!")
        else:
            print(f"⚠️  AutoFeat特征工程未能提升模型性能")

    except Exception as e:
        print(f"❌ AutoFeat详细测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 修复版特征工程框架对比测试开始")
    print()

    # 运行主要测试
    test_comparison_methods_fixed()
    print()

    # 详细测试AutoFeat
    test_autofeat_detailed()
    print()

    # 测试PGML
    test_pgml_with_project_config()

    print()
    print("🏁 所有测试完成！")