#!/usr/bin/env python3
"""
测试AutoFeat和PGML对比方法的详细性能和功能
"""

import sys
import os
import time
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification, make_regression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score, mean_squared_error, r2_score

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from frontend.comparison_methods import AutoFeatMethod, PGMLMethod, ComparisonEngine

def create_classification_dataset(n_samples=200, n_features=8, n_informative=5):
    """创建分类数据集"""
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=n_informative,
        n_redundant=max(0, n_features - n_informative - 1),
        n_repeated=0,
        n_clusters_per_class=1,
        random_state=42
    )

    # 转换为DataFrame
    feature_names = [f'feature_{i+1}' for i in range(n_features)]
    X_df = pd.DataFrame(X, columns=feature_names)
    y_series = pd.Series(y)

    return X_df, y_series

def create_regression_dataset(n_samples=200, n_features=8, n_informative=5):
    """创建回归数据集"""
    X, y = make_regression(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=n_informative,
        noise=0.1,
        random_state=42
    )

    # 转换为DataFrame
    feature_names = [f'feature_{i+1}' for i in range(n_features)]
    X_df = pd.DataFrame(X, columns=feature_names)
    y_series = pd.Series(y)

    return X_df, y_series

def test_autofeat_method(X, y, task_type="classify"):
    """测试AutoFeat方法"""
    print(f"\n{'='*60}")
    print(f"🧪 测试AutoFeat方法 ({task_type.upper()}任务)")
    print(f"{'='*60}")

    try:
        # 检查AutoFeat是否可用
        autofeat_method = AutoFeatMethod()
        if not autofeat_method.available:
            print("❌ AutoFeat不可用，跳过测试")
            return None

        print(f"📊 原始数据形状: {X.shape}")
        print(f"📊 目标变量分布: {y.value_counts().to_dict() if task_type == 'classify' else f'均值: {y.mean():.3f}, 标准差: {y.std():.3f}'}")

        # 特征生成
        start_time = time.time()
        X_generated = autofeat_method.generate_features(X, y)
        feature_time = time.time() - start_time

        print(f"⚡ 特征生成时间: {feature_time:.2f}秒")
        print(f"📊 生成后数据形状: {X_generated.shape}")
        print(f"🆕 新增特征数量: {X_generated.shape[1] - X.shape[1]}")

        # 模型评估
        start_time = time.time()
        metrics = autofeat_method.evaluate_features(X_generated, y, task_type)
        eval_time = time.time() - start_time

        print(f"⚡ 评估时间: {eval_time:.2f}秒")

        if task_type == "classify":
            print(f"📈 性能指标:")
            print(f"   - AUC: {metrics.get('auc', 0):.4f}")
            print(f"   - Accuracy: {metrics.get('accuracy', 0):.4f}")
            print(f"   - F1 Score: {metrics.get('f1', 0):.4f}")
            print(f"   - Precision: {metrics.get('precision', 0):.4f}")
            print(f"   - Recall: {metrics.get('recall', 0):.4f}")
        else:
            print(f"📈 性能指标:")
            print(f"   - RMSE: {metrics.get('rmse', 0):.4f}")
            print(f"   - MSE: {metrics.get('mse', 0):.4f}")
            print(f"   - MAE: {metrics.get('mae', 0):.4f}")
            print(f"   - R²: {metrics.get('r2', 0):.4f}")

        # 获取特征信息
        feature_info = autofeat_method.get_feature_info()
        print(f"🔍 特征信息: {feature_info['description']}")

        # 显示一些生成的特征名称
        if 'new_feature_names' in feature_info and feature_info['new_feature_names']:
            print(f"🆕 新特征样例: {feature_info['new_feature_names'][:5]}")

        return {
            'method': 'AutoFeat',
            'task_type': task_type,
            'original_features': X.shape[1],
            'generated_features': X_generated.shape[1],
            'new_features': X_generated.shape[1] - X.shape[1],
            'feature_time': feature_time,
            'eval_time': eval_time,
            'metrics': metrics,
            'feature_info': feature_info,
            'success': True
        }

    except Exception as e:
        print(f"❌ AutoFeat测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'method': 'AutoFeat',
            'task_type': task_type,
            'success': False,
            'error': str(e)
        }

def test_pgml_method(X, y, task_type="classify"):
    """测试PGML方法"""
    print(f"\n{'='*60}")
    print(f"🧪 测试PGML方法 ({task_type.upper()}任务)")
    print(f"{'='*60}")

    try:
        # 检查PGML是否可用
        pgml_method = PGMLMethod()
        if not pgml_method.available:
            print("❌ PGML不可用，跳过测试")
            return None

        print(f"📊 原始数据形状: {X.shape}")
        print(f"📊 目标变量分布: {y.value_counts().to_dict() if task_type == 'classify' else f'均值: {y.mean():.3f}, 标准差: {y.std():.3f}'}")

        # 特征生成
        start_time = time.time()
        X_generated = pgml_method.generate_features(X, y)
        feature_time = time.time() - start_time

        print(f"⚡ 特征生成时间: {feature_time:.2f}秒")
        print(f"📊 生成后数据形状: {X_generated.shape}")
        print(f"🆕 新增特征数量: {X_generated.shape[1] - X.shape[1]}")

        # 模型评估
        start_time = time.time()
        metrics = pgml_method.evaluate_features(X_generated, y, task_type)
        eval_time = time.time() - start_time

        print(f"⚡ 评估时间: {eval_time:.2f}秒")

        if task_type == "classify":
            print(f"📈 性能指标:")
            print(f"   - AUC: {metrics.get('auc', 0):.4f}")
            print(f"   - Accuracy: {metrics.get('accuracy', 0):.4f}")
            print(f"   - F1 Score: {metrics.get('f1', 0):.4f}")
            print(f"   - Precision: {metrics.get('precision', 0):.4f}")
            print(f"   - Recall: {metrics.get('recall', 0):.4f}")
        else:
            print(f"📈 性能指标:")
            print(f"   - RMSE: {metrics.get('rmse', 0):.4f}")
            print(f"   - MSE: {metrics.get('mse', 0):.4f}")
            print(f"   - MAE: {metrics.get('mae', 0):.4f}")
            print(f"   - R²: {metrics.get('r2', 0):.4f}")

        # 获取特征信息
        feature_info = pgml_method.get_feature_info()
        print(f"🔍 特征信息: {feature_info['description']}")

        return {
            'method': 'PGML',
            'task_type': task_type,
            'original_features': X.shape[1],
            'generated_features': X_generated.shape[1],
            'new_features': X_generated.shape[1] - X.shape[1],
            'feature_time': feature_time,
            'eval_time': eval_time,
            'metrics': metrics,
            'feature_info': feature_info,
            'success': True
        }

    except Exception as e:
        print(f"❌ PGML测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'method': 'PGML',
            'task_type': task_type,
            'success': False,
            'error': str(e)
        }

def test_comparison_engine(X, y, task_type="classify"):
    """测试对比引擎"""
    print(f"\n{'='*60}")
    print(f"🔧 测试ComparisonEngine ({task_type.upper()}任务)")
    print(f"{'='*60}")

    try:
        engine = ComparisonEngine()
        available_methods = engine.get_available_methods()
        print(f"📋 可用方法: {available_methods}")

        # 只测试AutoFeat和PGML
        test_methods = ['AutoFeat', 'PGML']
        available_test_methods = [m for m in test_methods if m in available_methods]

        if not available_test_methods:
            print("❌ 没有可用的测试方法")
            return None

        print(f"🧪 将测试方法: {available_test_methods}")

        start_time = time.time()
        results = engine.run_comparison(X, y, task_type, available_test_methods, time_limit=60)
        total_time = time.time() - start_time

        print(f"⚡ 对比测试总时间: {total_time:.2f}秒")
        print(f"📊 成功测试的方法: {results['methods']}")

        # 显示性能对比
        if task_type == "classify":
            print(f"\n📈 性能对比 (AUC):")
            for i, method in enumerate(results['methods']):
                auc = results['performance_data']['auc'][i]
                accuracy = results['performance_data']['accuracy'][i]
                print(f"   {method:10s}: AUC={auc:.4f}, Accuracy={accuracy:.4f}")
        else:
            print(f"\n📈 性能对比 (RMSE):")
            for i, method in enumerate(results['methods']):
                rmse = results['performance_data']['rmse'][i] if 'rmse' in results['performance_data'] else 0
                r2 = results['performance_data']['r2'][i] if 'r2' in results['performance_data'] else 0
                print(f"   {method:10s}: RMSE={rmse:.4f}, R²={r2:.4f}")

        # 显示时间对比
        print(f"\n⏱️ 时间对比:")
        for i, method in enumerate(results['methods']):
            total_t = results['time_data']['totalTime'][i]
            feature_t = results['time_data']['featureGenerationTime'][i]
            print(f"   {method:10s}: 总时间={total_t:.2f}s, 特征生成={feature_t:.2f}s")

        return results

    except Exception as e:
        print(f"❌ ComparisonEngine测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """主测试函数"""
    print("🚀 开始AutoFeat和PGML对比方法测试")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 测试结果汇总
    all_results = []

    # 1. 分类任务测试
    print(f"\n{'#'*80}")
    print(f"# 分类任务测试")
    print(f"{'#'*80}")

    X_cls, y_cls = create_classification_dataset(n_samples=100, n_features=6)

    # 测试AutoFeat分类
    print("🔄 测试AutoFeat对比方法...")
    autofeat_cls_result = test_autofeat_method(X_cls, y_cls, "classify")
    if autofeat_cls_result:
        all_results.append(autofeat_cls_result)

    # 测试PGML分类
    print("🔄 测试PGML对比方法...")
    pgml_cls_result = test_pgml_method(X_cls, y_cls, "classify")
    if pgml_cls_result:
        all_results.append(pgml_cls_result)

    # 测试对比引擎分类
    comparison_cls_result = test_comparison_engine(X_cls, y_cls, "classify")

    # 2. 回归任务测试
    print(f"\n{'#'*80}")
    print(f"# 回归任务测试")
    print(f"{'#'*80}")

    X_reg, y_reg = create_regression_dataset(n_samples=100, n_features=6)

    # 测试AutoFeat回归
    autofeat_reg_result = test_autofeat_method(X_reg, y_reg, "regress")
    if autofeat_reg_result:
        all_results.append(autofeat_reg_result)

    # 测试PGML回归
    pgml_reg_result = test_pgml_method(X_reg, y_reg, "regress")
    if pgml_reg_result:
        all_results.append(pgml_reg_result)

    # 测试对比引擎回归
    comparison_reg_result = test_comparison_engine(X_reg, y_reg, "regress")

    # 3. 结果汇总和对比
    print(f"\n{'='*80}")
    print(f"📊 测试结果汇总")
    print(f"{'='*80}")

    print("🔄 对比autofeat和pgml的性能表现...")
    print("🔄 验证两种方法的特征生成能力...")

    successful_results = [r for r in all_results if r and r.get('success', False)]

    if successful_results:
        print(f"✅ 成功完成的测试: {len(successful_results)}")

        for result in successful_results:
            print(f"\n🔸 {result['method']} - {result['task_type'].upper()}:")
            print(f"   原始特征: {result['original_features']}")
            print(f"   生成特征: {result['generated_features']}")
            print(f"   新增特征: {result['new_features']}")
            print(f"   特征生成时间: {result['feature_time']:.2f}s")
            print(f"   评估时间: {result['eval_time']:.2f}s")

            # 关键性能指标
            if result['task_type'] == 'classify':
                auc = result['metrics'].get('auc', 0)
                accuracy = result['metrics'].get('accuracy', 0)
                print(f"   AUC: {auc:.4f}, Accuracy: {accuracy:.4f}")
            else:
                rmse = result['metrics'].get('rmse', 0)
                r2 = result['metrics'].get('r2', 0)
                print(f"   RMSE: {rmse:.4f}, R²: {r2:.4f}")

    print(f"\n🎉 测试完成！")

    return all_results

if __name__ == "__main__":
    results = main()