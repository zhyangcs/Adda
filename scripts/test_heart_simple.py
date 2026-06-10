#!/usr/bin/env python3
"""
简化的heart数据集测试脚本，测试AutoFeat和CAAFE
"""

import sys
import os
import time
import pandas as pd
import numpy as np

# 添加项目路径
sys.path.insert(0, '.')

def main():
    print("🚀 开始简化Heart数据集测试")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 加载数据
    dataset_path = "/home/lizhenyu/projects/autofe/dataset/task/heart/train_new.csv"
    print(f"📊 加载数据: {dataset_path}")

    df = pd.read_csv(dataset_path)
    print(f"📊 原始数据形状: {df.shape}")
    print(f"📊 数据列: {list(df.columns)}")

    # 目标变量是tenyearchd (10年冠心病风险预测)
    target_column = 'tenyearchd'
    y = df[target_column]
    X = df.drop(columns=[target_column, 'id'])  # 移除ID列

    print(f"📊 特征数据形状: {X.shape}")
    print(f"📊 目标变量分布: {y.value_counts().to_dict()}")

    # 导入特征工程方法
    from frontend.comparison_methods import ComparisonEngine

    engine = ComparisonEngine()
    available_methods = engine.get_available_methods()
    print(f"📋 可用方法: {available_methods}")

    # 测试方法
    test_methods = ['AutoFeat', 'CAAFE']
    test_methods = [m for m in test_methods if m in available_methods]

    print(f"🧪 将要测试的方法: {test_methods}")

    if not test_methods:
        print("❌ 没有可用的测试方法")
        return

    # 运行对比测试
    try:
        print(f"🔄 开始运行特征工程对比...")
        start_time = time.time()

        results = engine.run_comparison(X, y, 'classify', test_methods, time_limit=300)  # 5分钟限制

        total_time = time.time() - start_time
        print(f"⚡ 总时间: {total_time:.2f}秒")

        # 显示结果
        print(f"\n📊 结果:")
        print(f"✅ 成功方法: {results['methods']}")

        if results['methods']:
            print(f"\n📈 性能对比:")
            for i, method in enumerate(results['methods']):
                auc = results['performance_data']['auc'][i]
                accuracy = results['performance_data']['accuracy'][i]
                f1 = results['performance_data']['f1'][i] if 'f1' in results['performance_data'] else 0
                new_features = results['feature_data']['new_features_count'][i]
                print(f"   {method:8s}: AUC={auc:.4f}, Accuracy={accuracy:.4f}, F1={f1:.4f}, 新特征={new_features}")

        print(f"\n🎉 测试完成!")

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()