#!/usr/bin/env python3
"""
使用真实heart数据集测试AutoFeat和CAAFE对比方法
"""

import sys
import os
import time
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score, precision_score, recall_score

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from frontend.comparison_methods import AutoFeatMethod, CAAFEMethod, ComparisonEngine

def load_heart_dataset():
    """加载heart数据集"""
    print("📊 加载heart数据集...")

    dataset_path = "/home/lizhenyu/projects/autofe/dataset/task/heart/train_new.csv"
    df = pd.read_csv(dataset_path)

    print(f"📊 原始数据形状: {df.shape}")
    print(f"📊 数据列: {list(df.columns)}")

    # 目标变量是tenyearchd (10年冠心病风险预测)
    target_column = 'tenyearchd'
    y = df[target_column]
    X = df.drop(columns=[target_column, 'id'])  # 移除ID列，它不是有用的特征

    print(f"📊 特征数据形状: {X.shape}")
    print(f"📊 目标变量分布: {y.value_counts().to_dict()}")
    print(f"📊 缺失值统计:")
    print(X.isnull().sum()[X.isnull().sum() > 0])

    return X, y

def preprocess_heart_data(X, y):
    """预处理heart数据集"""
    print("🔄 预处理heart数据集...")

    # 处理缺失值
    X_processed = X.copy()

    # 数值型列用中位数填充
    numeric_columns = X_processed.select_dtypes(include=[np.number]).columns
    for col in numeric_columns:
        if X_processed[col].isnull().sum() > 0:
            median_val = X_processed[col].median()
            X_processed[col].fillna(median_val, inplace=True)
            print(f"   填充 {col} 缺失值，使用中位数: {median_val}")

    # 分类列用众数填充
    categorical_columns = X_processed.select_dtypes(include=['object']).columns
    for col in categorical_columns:
        if X_processed[col].isnull().sum() > 0:
            mode_val = X_processed[col].mode()[0] if not X_processed[col].mode().empty else 'unknown'
            X_processed[col].fillna(mode_val, inplace=True)
            print(f"   填充 {col} 缺失值，使用众数: {mode_val}")

    print(f"📊 预处理后缺失值数量: {X_processed.isnull().sum().sum()}")

    # 检查目标变量
    print(f"📊 目标变量类型: {y.dtype}")
    print(f"📊 目标变量唯一值: {y.unique()}")

    return X_processed, y

def test_method_on_heart_data(method_name, X, y, sample_size=None):
    """在heart数据集上测试指定方法"""
    print(f"\n{'='*60}")
    print(f"🧪 测试{method_name}方法 - Heart数据集")
    print(f"{'='*60}")

    # 使用完整数据集，与run_multimodel_type.py保持一致
    print(f"📊 使用完整数据集: {len(X)} 样本")
    X_sample = X
    y_sample = y

    print(f"📊 测试数据形状: {X_sample.shape}")
    print(f"📊 测试目标分布: {y_sample.value_counts().to_dict()}")

    # 选择方法
    if method_name.lower() == 'autofeat':
        method = AutoFeatMethod()
    elif method_name.lower() == 'caafe':
        method = CAAFEMethod()
    else:
        raise ValueError(f"不支持的方法: {method_name}")

    if not method.available:
        print(f"❌ {method_name}不可用")
        return None

    try:
        # 特征生成
        print(f"🔄 开始特征生成...")
        start_time = time.time()
        X_generated = method.generate_features(X_sample, y_sample)
        feature_time = time.time() - start_time

        print(f"⚡ 特征生成完成，耗时: {feature_time:.2f}秒")
        print(f"📊 原始特征数: {X_sample.shape[1]}")
        print(f"📊 生成特征数: {X_generated.shape[1]}")
        print(f"🆕 新增特征数: {X_generated.shape[1] - X_sample.shape[1]}")

        # 显示一些新生成的特征名称
        if X_generated.shape[1] > X_sample.shape[1]:
            new_features = list(X_generated.columns)[X_sample.shape[1]:]
            print(f"🆕 新特征样例: {new_features[:5]}")

        # 模型评估
        print(f"🔄 开始模型评估...")
        start_time = time.time()
        metrics = method.evaluate_features(X_generated, y_sample, 'classify')
        eval_time = time.time() - start_time

        print(f"⚡ 模型评估完成，耗时: {eval_time:.2f}秒")

        # 显示性能指标
        print(f"📈 性能指标:")
        print(f"   - AUC: {metrics.get('auc', 0):.4f}")
        print(f"   - Accuracy: {metrics.get('accuracy', 0):.4f}")
        print(f"   - F1 Score: {metrics.get('f1', 0):.4f}")
        print(f"   - Precision: {metrics.get('precision', 0):.4f}")
        print(f"   - Recall: {metrics.get('recall', 0):.4f}")

        # 获取特征信息
        feature_info = method.get_feature_info()
        print(f"🔍 特征信息: {feature_info['description']}")

        # 额外显示CAAFE的特殊信息
        if method_name.lower() == 'caafe' and feature_info.get('success'):
            if 'llm_model' in feature_info:
                print(f"🤖 LLM模型: {feature_info['llm_model']}")
            if 'api_base' in feature_info:
                print(f"🌐 API端点: {feature_info['api_base']}")
            if 'iterations' in feature_info:
                print(f"🔄 迭代次数: {feature_info['iterations']}")

        return {
            'method': method_name,
            'dataset': 'Heart',
            'sample_size': len(X_sample),
            'original_features': X_sample.shape[1],
            'generated_features': X_generated.shape[1],
            'new_features': X_generated.shape[1] - X_sample.shape[1],
            'feature_time': feature_time,
            'eval_time': eval_time,
            'metrics': metrics,
            'feature_info': feature_info,
            'success': True
        }

    except Exception as e:
        print(f"❌ {method_name}测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'method': method_name,
            'dataset': 'Heart',
            'sample_size': len(X_sample),
            'success': False,
            'error': str(e)
        }

def compare_methods_on_heart_data(X, y, sample_size=None):
    """在heart数据集上对比AutoFeat和CAAFE方法"""
    print(f"\n{'='*80}")
    print(f"🔧 Heart数据集方法对比")
    print(f"{'='*80}")

    # 测试AutoFeat (使用完整数据集)
    autofeat_result = test_method_on_heart_data('AutoFeat', X, y, sample_size)

    # 测试CAAFE (使用完整数据集)
    caafe_result = test_method_on_heart_data('CAAFE', X, y, sample_size)

    # 对比结果
    print(f"\n{'='*80}")
    print(f"📊 Heart数据集对比结果")
    print(f"{'='*80}")

    results = [autofeat_result, caafe_result]
    successful_results = [r for r in results if r and r.get('success', False)]

    if len(successful_results) >= 2:
        print(f"✅ 成功对比 {len(successful_results)} 个方法")

        print(f"\n📈 性能对比 (AUC):")
        for result in successful_results:
            method = result['method']
            auc = result['metrics'].get('auc', 0)
            accuracy = result['metrics'].get('accuracy', 0)
            f1 = result['metrics'].get('f1', 0)
            new_features = result['new_features']
            print(f"   {method:8s}: AUC={auc:.4f}, Accuracy={accuracy:.4f}, F1={f1:.4f}, 新特征={new_features}")

        print(f"\n⏱️ 时间对比:")
        for result in successful_results:
            method = result['method']
            feature_time = result['feature_time']
            eval_time = result['eval_time']
            total_time = feature_time + eval_time
            print(f"   {method:8s}: 特征生成={feature_time:.2f}s, 评估={eval_time:.2f}s, 总计={total_time:.2f}s")

        # 找出最佳方法
        best_method = max(successful_results, key=lambda x: x['metrics'].get('auc', 0))
        print(f"\n🏆 最佳方法: {best_method['method']} (AUC: {best_method['metrics'].get('auc', 0):.4f})")

    else:
        print(f"❌ 只有 {len(successful_results)} 个方法成功，无法进行有效对比")

    return successful_results

def test_with_comparison_engine(X, y, sample_size=None):
    """使用ComparisonEngine进行对比测试"""
    print(f"\n{'='*80}")
    print(f"🔧 使用ComparisonEngine测试")
    print(f"{'='*80}")

    # 使用完整数据集，与run_multimodel_type.py保持一致
    X_sample = X
    y_sample = y
    print(f"📊 使用完整数据集: {len(X_sample)} 样本")

    try:
        engine = ComparisonEngine()
        available_methods = engine.get_available_methods()
        print(f"📋 可用方法: {available_methods}")

        test_methods = ['AutoFeat', 'CAAFE']
        available_test_methods = [m for m in test_methods if m in available_methods]

        if not available_test_methods:
            print("❌ 没有可用的测试方法")
            return None

        print(f"🧪 测试方法: {available_test_methods}")

        start_time = time.time()
        results = engine.run_comparison(X_sample, y_sample, 'classify', available_test_methods, time_limit=120)
        total_time = time.time() - start_time

        print(f"⚡ ComparisonEngine总时间: {total_time:.2f}秒")
        print(f"📊 成功方法: {results['methods']}")

        # 显示详细结果
        print(f"\n📈 详细性能对比:")
        for i, method in enumerate(results['methods']):
            auc = results['performance_data']['auc'][i]
            accuracy = results['performance_data']['accuracy'][i]
            f1 = results['performance_data']['f1'][i] if 'f1' in results['performance_data'] else 0
            print(f"   {method:8s}: AUC={auc:.4f}, Accuracy={accuracy:.4f}, F1={f1:.4f}")

        return results

    except Exception as e:
        print(f"❌ ComparisonEngine测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """主测试函数"""
    print("🚀 开始Heart数据集AutoFeat和CAAFE对比测试")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 加载和预处理数据
    try:
        X, y = load_heart_dataset()
        X_processed, y_processed = preprocess_heart_data(X, y)
        print(f"✅ 数据加载和预处理完成")
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        return

    # 使用完整数据集，与run_multimodel_type.py保持一致
    print(f"\n📊 使用完整Heart数据集进行测试: {len(X_processed)} 样本")

    # 方法对比测试
    print(f"\n{'#'*80}")
    print(f"# 方法对比测试 (完整数据集)")
    print(f"{'#'*80}")

    comparison_results = compare_methods_on_heart_data(X_processed, y_processed)

    # 使用ComparisonEngine测试
    print(f"\n{'#'*80}")
    print(f"# ComparisonEngine测试 (完整数据集)")
    print(f"{'#'*80}")

    engine_results = test_with_comparison_engine(X_processed, y_processed)

    # 总结
    print(f"\n{'='*80}")
    print(f"🎉 Heart数据集测试完成")
    print(f"{'='*80}")

    if comparison_results:
        print(f"✅ 方法对比测试完成，成功方法数: {len(comparison_results)}")
        for result in comparison_results:
            method = result['method']
            auc = result['metrics'].get('auc', 0)
            new_features = result['new_features']
            print(f"   {method}: AUC={auc:.4f}, 新特征={new_features}")

    if engine_results:
        print(f"✅ ComparisonEngine测试完成")
        print(f"   成功方法: {engine_results['methods']}")

    return comparison_results, engine_results

if __name__ == "__main__":
    comparison_results, engine_results = main()