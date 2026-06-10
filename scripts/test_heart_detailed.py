#!/usr/bin/env python3
"""
详细的Heart数据集测试，收集特征和性能指标
"""

import sys
import time
import pandas as pd
import numpy as np

# 添加项目路径
sys.path.insert(0, '.')

def load_heart_dataset():
    """加载heart数据集"""
    print("📊 加载heart数据集...")
    dataset_path = "dataset/task/heart/train_new.csv"
    df = pd.read_csv(dataset_path)

    print(f"📊 原始数据形状: {df.shape}")

    # 目标变量是tenyearchd (10年冠心病风险预测)
    target_column = 'tenyearchd'
    y = df[target_column]
    X = df.drop(columns=[target_column, 'id'])  # 移除ID列

    print(f"📊 特征数据形状: {X.shape}")
    print(f"📊 目标变量分布: {y.value_counts().to_dict()}")

    return X, y

def test_method_detailed(method_name, method, X, y):
    """详细测试单个方法"""
    print(f"\n{'='*60}")
    print(f"🧪 详细测试 {method_name}")
    print(f"{'='*60}")

    result = {
        'method': method_name,
        'dataset': 'Heart',
        'sample_size': len(X),
        'original_features': X.shape[1],
        'success': False
    }

    # 检查方法是否可用（有些方法没有available属性）
    is_available = getattr(method, 'available', True)
    if not is_available:
        print(f"❌ {method_name} 不可用")
        return result

    try:
        # 记录原始特征
        original_feature_names = list(X.columns)
        print(f"📊 原始特征: {original_feature_names}")

        # 特征生成
        print(f"🔄 开始特征生成...")
        start_time = time.time()
        X_generated = method.generate_features(X, y)
        feature_time = time.time() - start_time

        print(f"⚡ 特征生成完成，耗时: {feature_time:.2f}秒")
        print(f"📊 原始特征数: {X.shape[1]}")
        print(f"📊 生成特征数: {X_generated.shape[1]}")

        # 获取生成的特征名称
        generated_feature_names = list(X_generated.columns)
        print(f"📊 生成特征: {generated_feature_names}")

        # 识别新特征
        new_features = [f for f in generated_feature_names if f not in original_feature_names]
        print(f"🆕 新特征数量: {len(new_features)}")
        if new_features:
            print(f"🆕 新特征样例: {new_features[:10]}")  # 显示前10个新特征

        # 模型评估
        print(f"🔄 开始模型评估...")
        start_time = time.time()
        metrics = method.fit_predict(X_generated, y, 'classify')
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
        print(f"🔍 特征描述: {feature_info['description']}")

        # 时间分解
        time_breakdown = method.get_time_breakdown()
        print(f"⏱️ 时间分解:")
        print(f"   - 预处理时间: {time_breakdown.get('preprocessing_time', 0):.2f}s")
        print(f"   - 特征生成时间: {time_breakdown.get('feature_generation_time', 0):.2f}s")
        print(f"   - 训练时间: {time_breakdown.get('training_time', 0):.2f}s")
        print(f"   - 总时间: {time_breakdown.get('total_time', 0):.2f}s")

        # 构建详细结果
        result.update({
            'success': True,
            'original_features': X.shape[1],
            'generated_features': X_generated.shape[1],
            'new_features_count': len(new_features),
            'new_features': new_features,
            'all_features': generated_feature_names,
            'feature_time': feature_time,
            'eval_time': eval_time,
            'metrics': metrics,
            'time_breakdown': time_breakdown,
            'feature_info': feature_info
        })

        # CAAFE额外信息
        if method_name == 'CAAFE' and feature_info.get('success'):
            result['llm_model'] = feature_info.get('llm_model', 'unknown')
            result['api_base'] = feature_info.get('api_base', 'unknown')
            result['iterations'] = feature_info.get('iterations', 0)

        print(f"✅ {method_name} 详细测试完成")

    except Exception as e:
        print(f"❌ {method_name} 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)

    return result

def main():
    """主测试函数"""
    print("🚀 开始Heart数据集详细特征工程测试")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 加载数据
    try:
        X, y = load_heart_dataset()
        print(f"✅ 数据加载完成")
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        return

    # 导入特征工程方法
    from frontend.comparison_methods import ComparisonEngine, AutoFeatMethod, CAAFEMethod

    # 测试各个方法
    results = {}

    # 测试Baseline
    print(f"\n{'#'*80}")
    print(f"# Baseline测试")
    print(f"{'#'*80}")
    from frontend.comparison_methods import BaselineMethod
    baseline_method = BaselineMethod()
    results['Baseline'] = test_method_detailed('Baseline', baseline_method, X, y)

    # 测试AutoFeat
    print(f"\n{'#'*80}")
    print(f"# AutoFeat测试")
    print(f"{'#'*80}")
    autofeat_method = AutoFeatMethod()
    results['AutoFeat'] = test_method_detailed('AutoFeat', autofeat_method, X, y)

    # 测试CAAFE (如果可用)
    print(f"\n{'#'*80}")
    print(f"# CAAFE测试")
    print(f"{'#'*80}")
    caafe_method = CAAFEMethod()
    if caafe_method.available:
        results['CAAFE'] = test_method_detailed('CAAFE', caafe_method, X, y)
    else:
        print("❌ CAAFE 不可用")
        results['CAAFE'] = {'method': 'CAAFE', 'success': False, 'error': 'Not available'}

    # 生成详细报告
    print(f"\n{'='*80}")
    print(f"📊 详细测试报告")
    print(f"{'='*80}")

    successful_results = {k: v for k, v in results.items() if v.get('success', False)}

    if successful_results:
        print(f"✅ 成功测试 {len(successful_results)} 个方法")

        print(f"\n📈 性能对比表:")
        print(f"{'方法':<10} {'原始特征':<8} {'生成特征':<8} {'新特征':<6} {'AUC':<8} {'Accuracy':<10} {'时间(s)':<8}")
        print("-" * 70)

        for method_name, result in successful_results.items():
            auc = result['metrics'].get('auc', 0)
            accuracy = result['metrics'].get('accuracy', 0)
            total_time = result['time_breakdown'].get('total_time', 0)
            print(f"{method_name:<10} {result['original_features']:<8} {result['generated_features']:<8} "
                  f"{result['new_features_count']:<6} {auc:<8.4f} {accuracy:<10.4f} {total_time:<8.2f}")

        # 详细特征信息
        print(f"\n🔍 详细特征信息:")
        for method_name, result in successful_results.items():
            print(f"\n📋 {method_name}:")
            print(f"   - 特征描述: {result['feature_info']['description']}")
            if result['new_features']:
                print(f"   - 新特征: {result['new_features'][:5]}")  # 显示前5个新特征
            else:
                print(f"   - 新特征: 无")

            # CAAFE特殊信息
            if method_name == 'CAAFE' and 'llm_model' in result:
                print(f"   - LLM模型: {result['llm_model']}")
                print(f"   - API端点: {result['api_base']}")
                print(f"   - 迭代次数: {result['iterations']}")

        # 找出最佳方法
        best_auc_method = max(successful_results.items(), key=lambda x: x[1]['metrics'].get('auc', 0))
        print(f"\n🏆 最佳AUC方法: {best_auc_method[0]} (AUC: {best_auc_method[1]['metrics'].get('auc', 0):.4f})")

        # 保存详细结果到文件
        import json
        with open('heart_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"📁 详细结果已保存到: heart_test_results.json")

    else:
        print(f"❌ 没有方法成功完成测试")

    print(f"\n🎉 测试完成!")
    return results

if __name__ == "__main__":
    results = main()