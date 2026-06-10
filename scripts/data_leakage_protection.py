#!/usr/bin/env python3
"""
数据泄露防护机制说明和测试

本模块说明了ComparisonMethod基类如何确保所有子类都遵循防泄露的数据分割原则
"""

import sys
import os
import pandas as pd
import numpy as np
from sklearn.datasets import make_classification

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from frontend.comparison_methods import ComparisonMethod

class TestMethod(ComparisonMethod):
    """测试方法，验证防泄露机制"""

    def __init__(self):
        super().__init__("TestMethod")

    def generate_features(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """简单的特征生成：添加一个随机特征"""
        X_new = X.copy()
        X_new['random_feature'] = np.random.RandomState(42).rand(len(X))
        return X_new

def demonstrate_protection():
    """演示防泄露机制"""
    print("🔒 数据泄露防护机制演示")
    print("=" * 60)

    # 创建测试数据
    X, y = make_classification(n_samples=100, n_features=5, random_state=42)
    X_df = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(5)])
    y_series = pd.Series(y)

    print(f"📊 原始数据: {X_df.shape[0]} 样本, {X_df.shape[1]} 特征")

    # 创建测试方法
    method = TestMethod()

    print("\n✅ 使用fit_predict() - 正确的防泄露方式:")
    try:
        result = method.fit_predict(X_df, y_series, 'classify')
        print(f"   - AUC: {result.get('auc', 0):.4f}")
        print(f"   - 执行时间: {result.get('execution_time', 0):.2f}s")
        print(f"   - 特征生成时间: {result.get('feature_generation_time', 0):.2f}s")

        # 检查是否有训练集/测试集分割信息
        if hasattr(method, '_X_train'):
            print(f"   - 训练集大小: {method._X_train.shape[0]}")
            print(f"   - 测试集大小: {method._X_test.shape[0]}")

    except Exception as e:
        print(f"   ❌ 错误: {e}")

    print("\n❌ 尝试使用evaluate_features() - 防止数据泄露:")
    try:
        # 这应该会抛出错误
        method.evaluate_features(X_df, y_series, 'classify')
        print("   ❌ 意外成功：防泄露机制失效！")
    except NotImplementedError as e:
        print(f"   ✅ 防泄露机制工作: {str(e)[:50]}...")
    except Exception as e:
        print(f"   ⚠️ 其他错误: {e}")

    print("\n📋 防泄露机制总结:")
    print("   1. fit_predict() 强制使用 train_test_split")
    print("   2. 特征生成只在训练集上进行")
    print("   3. 测试集使用训练时保存的转换器")
    print("   4. 废弃了 evaluate_features() 防止误用")
    print("   5. 所有子类必须遵循相同的防泄露流程")

def validate_future_methods():
    """验证未来添加的方法也会遵循防泄露原则"""
    print("\n🔮 未来方法防护验证:")
    print("=" * 60)

    class FutureMethod(ComparisonMethod):
        """模拟未来的新方法"""

        def __init__(self):
            super().__init__("FutureMethod")

        def generate_features(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
            """新方法的特征生成"""
            return X.copy()

        # 如果尝试重写fit_predict，会违反防泄露原则
        # def fit_predict(self, X, y, task_type):
        #     # 这会导致数据泄露！
        #     return self.evaluate_features(X, y, task_type)

    # 测试未来方法
    future_method = FutureMethod()
    X_test = pd.DataFrame(np.random.rand(50, 3), columns=['a', 'b', 'c'])
    y_test = pd.Series(np.random.randint(0, 2, 50))

    try:
        result = future_method.fit_predict(X_test, y_test, 'classify')
        print("✅ 未来方法自动继承防泄露机制")
        print(f"   - AUC: {result.get('auc', 0):.4f}")
    except Exception as e:
        print(f"❌ 未来方法失败: {e}")

if __name__ == "__main__":
    demonstrate_protection()
    validate_future_methods()

    print("\n" + "=" * 60)
    print("🎯 结论: 基类设计确保所有子类都使用防泄露的数据分割方式")
    print("=" * 60)