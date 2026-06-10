#!/usr/bin/env python3
"""
CAAFE vs AutoFeat 对比测试脚本
测试执行时间、AUC和特征生成数量
"""

import pandas as pd
import numpy as np
import warnings
import time
import sys
import os
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings('ignore')

# 设置环境变量
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from src.env import openai_api_key, openai_base_url
os.environ['OPENAI_API_KEY'] = openai_api_key
os.environ['OPENAI_BASE_URL'] = openai_base_url

def load_and_prepare_data():
    """加载和准备heart数据集"""
    print("📊 Loading Heart Disease dataset...")
    df = pd.read_csv('dataset/task/heart/train_new.csv')

    # 使用完整数据集进行公平对比
    X = df.drop('tenyearchd', axis=1)
    y = df['tenyearchd']

    print(f"📏 Dataset size: {X.shape[0]} rows, {X.shape[1]} features")
    print(f"🎯 Target distribution: {y.value_counts().to_dict()}")

    return X, y

def evaluate_features(X, y, method_name="Method"):
    """评估特征生成效果的通用函数"""
    print(f"\n🔬 Evaluating {method_name} features...")

    # 分割数据
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )

    # 使用随机森林进行评估
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )

    # 训练和预测
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)
    y_pred_proba = rf.predict_proba(X_test)[:, 1]

    # 计算指标
    auc = roc_auc_score(y_test, y_pred_proba)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"📈 {method_name} - AUC: {auc:.4f}, Accuracy: {accuracy:.4f}")

    return auc, accuracy

def test_caafe(X, y):
    """测试CAAFE方法"""
    print("\n🚀 Testing CAAFE Method")
    print("=" * 50)

    try:
        from frontend.comparison_methods import CAAFEMethod

        caafe = CAAFEMethod()
        if not caafe.available:
            print("❌ CAAFE not available")
            return None, None, 0, "CAAFE not available"

        print(f"🔑 API Key: {openai_api_key[:8]}...")
        print(f"🌐 Base URL: {openai_base_url}")

        # 记录开始时间
        start_time = time.time()

        # 生成特征
        print("⏱️  Starting CAAFE feature generation...")
        X_gen = caafe.generate_features(X, y)

        # 记录执行时间
        execution_time = time.time() - start_time

        # 获取特征数量
        n_features = X_gen.shape[1]

        # 获取生成的代码信息
        info = caafe.get_feature_info()
        generated_code = info.get('generated_code', '')
        code_length = len(generated_code) if generated_code else 0

        print(f"✅ CAAFE completed in {execution_time:.1f} seconds")
        print(f"📊 Features: {X.shape[1]} → {n_features} (+{n_features - X.shape[1]})")
        print(f"📝 Generated code: {code_length} characters")

        # 评估性能
        auc, accuracy = evaluate_features(X_gen, y, "CAAFE")

        return {
            'method': 'CAAFE',
            'execution_time': execution_time,
            'original_features': X.shape[1],
            'generated_features': n_features,
            'new_features': n_features - X.shape[1],
            'auc': auc,
            'accuracy': accuracy,
            'code_length': code_length,
            'success': True
        }, X_gen, execution_time, "Success"

    except Exception as e:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print(f"❌ CAAFE failed after {elapsed:.1f} seconds: {str(e)}")
        return None, None, elapsed, f"Error: {str(e)}"

def test_autofeat(X, y):
    """测试AutoFeat方法"""
    print("\n🔧 Testing AutoFeat Method")
    print("=" * 50)

    try:
        from frontend.comparison_methods import AutoFeatMethod

        autofeat = AutoFeatMethod()
        if not autofeat.available:
            print("❌ AutoFeat not available")
            return None, None, 0, "AutoFeat not available"

        # 记录开始时间
        start_time = time.time()

        # 生成特征
        print("⏱️  Starting AutoFeat feature generation...")
        X_gen = autofeat.generate_features(X, y)

        # 记录执行时间
        execution_time = time.time() - start_time

        # 获取特征数量
        n_features = X_gen.shape[1]

        print(f"✅ AutoFeat completed in {execution_time:.1f} seconds")
        print(f"📊 Features: {X.shape[1]} → {n_features} (+{n_features - X.shape[1]})")

        # 评估性能
        auc, accuracy = evaluate_features(X_gen, y, "AutoFeat")

        return {
            'method': 'AutoFeat',
            'execution_time': execution_time,
            'original_features': X.shape[1],
            'generated_features': n_features,
            'new_features': n_features - X.shape[1],
            'auc': auc,
            'accuracy': accuracy,
            'code_length': 0,  # AutoFeat doesn't generate code
            'success': True
        }, X_gen, execution_time, "Success"

    except Exception as e:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print(f"❌ AutoFeat failed after {elapsed:.1f} seconds: {str(e)}")
        return None, None, elapsed, f"Error: {str(e)}"

def test_baseline(X, y):
    """测试基线方法（原始特征）"""
    print("\n📈 Testing Baseline (Original Features)")
    print("=" * 50)

    # 评估原始特征
    auc, accuracy = evaluate_features(X, y, "Baseline")

    return {
        'method': 'Baseline',
        'execution_time': 0,
        'original_features': X.shape[1],
        'generated_features': X.shape[1],
        'new_features': 0,
        'auc': auc,
        'accuracy': accuracy,
        'code_length': 0,
        'success': True
    }

def create_comparison_table(results):
    """创建对比表格"""
    print("\n📊 COMPARISON RESULTS")
    print("=" * 80)

    if not results:
        print("❌ No results to compare")
        return

    # 表头
    print(f"{'Method':<12} {'Time(s)':<8} {'Features':<10} {'New':<5} {'AUC':<8} {'Accuracy':<10} {'Status':<15}")
    print("-" * 80)

    # 结果行
    for result in results:
        if result and result.get('success'):
            print(f"{result['method']:<12} "
                  f"{result['execution_time']:<8.1f} "
                  f"{result['generated_features']:<10} "
                  f"{result['new_features']:<5} "
                  f"{result['auc']:<8.4f} "
                  f"{result['accuracy']:<10.4f} "
                  f{"✅ Success":<15}")
        else:
            method = result.get('method', 'Unknown') if result else 'Unknown'
            print(f"{method:<12} {'-':<8} {'-':<10} {'-':<5} {'-':<8} {'-':<10} {'❌ Failed':<15}")

    print("-" * 80)

    # 详细分析
    successful_results = [r for r in results if r and r.get('success')]
    if len(successful_results) > 1:
        print("\n📈 Detailed Analysis:")

        # 找出最佳方法
        best_auc = max(successful_results, key=lambda x: x['auc'])
        fastest = min(successful_results, key=lambda x: x['execution_time'] if x['execution_time'] > 0 else float('inf'))
        most_features = max(successful_results, key=lambda x: x['new_features'])

        print(f"🏆 Best AUC: {best_auc['method']} ({best_auc['auc']:.4f})")
        print(f"⚡ Fastest: {fastest['method']} ({fastest['execution_time']:.1f}s)")
        print(f"🔧 Most Features: {most_features['method']} (+{most_features['new_features']} features)")

        if successful_results[0]['method'] == 'Baseline':
            baseline_auc = successful_results[0]['auc']
            improvement_results = [r for r in successful_results[1:] if r['auc'] > baseline_auc]
            if improvement_results:
                best_improvement = max(improvement_results, key=lambda x: x['auc'] - baseline_auc)
                improvement = best_improvement['auc'] - baseline_auc
                print(f"📈 Best Improvement over Baseline: {best_improvement['method']} (+{improvement:.4f} AUC)")

def main():
    """主函数"""
    print("🔬 CAAFE vs AutoFeat Comparison Test")
    print("=" * 60)

    # 加载数据
    X, y = load_and_prepare_data()

    results = []

    # 测试基线
    print("\n" + "="*60)
    baseline_result = test_baseline(X, y)
    results.append(baseline_result)

    # 测试CAAFE
    print("\n" + "="*60)
    caafe_result, X_caafe, caafe_time, caafe_status = test_caafe(X, y)
    if caafe_result:
        results.append(caafe_result)
    else:
        # 创建失败结果记录
        results.append({
            'method': 'CAAFE',
            'execution_time': caafe_time,
            'original_features': X.shape[1],
            'generated_features': X.shape[1],
            'new_features': 0,
            'auc': 0,
            'accuracy': 0,
            'code_length': 0,
            'success': False,
            'status': caafe_status
        })

    # 测试AutoFeat
    print("\n" + "="*60)
    autofeat_result, X_autofeat, autofeat_time, autofeat_status = test_autofeat(X, y)
    if autofeat_result:
        results.append(autofeat_result)
    else:
        # 创建失败结果记录
        results.append({
            'method': 'AutoFeat',
            'execution_time': autofeat_time,
            'original_features': X.shape[1],
            'generated_features': X.shape[1],
            'new_features': 0,
            'auc': 0,
            'accuracy': 0,
            'code_length': 0,
            'success': False,
            'status': autofeat_status
        })

    # 创建对比表格
    create_comparison_table(results)

    print(f"\n🏁 Test completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()