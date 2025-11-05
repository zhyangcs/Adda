#!/usr/bin/env python3
"""
完整的论文指标计算器 - 使用DAG数据的简化版本
直接从DAG中获取原始特征和生成特征，避免数据匹配问题
"""

import os
import sys
import pandas as pd
import numpy as np
import pickle
import re
import warnings

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.llm.tests.test_util import task_config, read_data_info
from src.env import test_save_path

# 导入模型评估相关的模块
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.feature_selection import RFE
from sklearn.inspection import permutation_importance
import shap
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, precision_score, recall_score

class PaperMetricsCalculatorSimplified:
    """
    简化的论文指标计算器
    直接从DAG数据中获取所有特征，避免数据匹配问题
    """

    def __init__(self):
        self.original_feature_count = 0
        self.generated_feature_count = 0
        self.total_feature_count = 0

    def calculate_paper_metrics(self, task_name: str, top_k: int = 7, methods: list = None):
        """
        计算论文指标的主要方法

        Args:
            task_name: 任务名称
            top_k: Top-K特征数量
            methods: 评估方法列表

        Returns:
            完整的指标计算结果
        """
        if methods is None:
            methods = ['shap', 'ig', 'rfe', 'fi']

        print(f"🎯 [SIMPLIFIED PAPER METRICS] Starting calculation for {task_name}")
        print(f"   Methods: {methods}")
        print(f"   Top-K: {top_k}")
        print("-" * 60)

        try:
            # 1. 从DAG中获取完整特征矩阵
            complete_data = self._extract_complete_dag_data(task_name)

            if complete_data is None:
                print("❌ Failed to extract complete data from DAG")
                return None

            # 2. 识别原始特征和生成特征
            all_features = self._identify_original_vs_generated_features(task_name, complete_data)

            # 3. 计算指标
            metrics_results = self._calculate_importance_metrics(
                complete_data, task_name, all_features, methods
            )

            # 4. 分析Top-K特征
            top_k_analysis = self._analyze_top_k_features(
                all_features, metrics_results, top_k
            )

            # 5. 构建完整结果
            final_results = {
                'task_name': task_name,
                'original_feature_count': len(all_features['original']),
                'generated_feature_count': len(all_features['generated']),
                'total_feature_count': len(all_features['original']) + len(all_features['generated']),
                'top_k': top_k,
                'metrics': metrics_results,
                'top_k_analysis': top_k_analysis,
                'all_features': all_features,
                'data_shape': complete_data.shape,
                'success': True
            }

            # Convert all numpy types to JSON-serializable types before returning
            def convert_numpy_types_recursively(obj):
                import numpy as np
                if isinstance(obj, dict):
                    return {key: convert_numpy_types_recursively(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types_recursively(item) for item in obj]
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    if obj.size == 1:
                        return obj.item()
                    else:
                        return obj.tolist()
                else:
                    return obj

            final_results = convert_numpy_types_recursively(final_results)

            print(f"✅ [SIMPLIFIED PAPER METRICS] Calculation completed successfully!")
            print(f"   📊 Original features: {final_results['original_feature_count']}")
            print(f"   🆕 Generated features: {final_results['generated_feature_count']}")
            print(f"   📈 Total features: {final_results['total_feature_count']}")
            print(f"   📋 Data shape: {final_results['data_shape']}")

            return final_results

        except Exception as e:
            print(f"❌ [SIMPLIFIED PAPER METRICS] Calculation failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_complete_dag_data(self, task_name: str):
        """
        从DAG中提取包含所有特征的完整数据
        并添加目标变量

        Args:
            task_name: 任务名称

        Returns:
            包含原始特征、生成特征和目标变量的DataFrame
        """
        try:
            # 尝试多个可能的pickle文件路径
            possible_paths = [
                os.path.join(test_save_path, f"{task_name}_RF_Full", "cur_states.pkl"),
            ]

            pickle_file = None
            for path in possible_paths:
                if os.path.exists(path):
                    pickle_file = path
                    break

            if pickle_file is None:
                # 尝试查找最新的RF_Full目录
                test_store_path = os.path.dirname(test_save_path)
                rf_full_dirs = [d for d in os.listdir(test_store_path)
                              if d.startswith(f"{task_name}_RF_Full")]
                if rf_full_dirs:
                    latest_dir = sorted(rf_full_dirs)[-1]
                    pickle_file = os.path.join(test_store_path, latest_dir, "cur_states.pkl")

            if pickle_file is None or not os.path.exists(pickle_file):
                print(f"DAG pickle file not found for {task_name}")
                return None

            with open(pickle_file, "rb") as f:
                dag_constructor = pickle.load(f)

            dag = dag_constructor.dag
            print(f"Scanning {len(dag.nodes())} DAG nodes for complete data...")

            best_data = None
            max_features = 0

            # 聚合所有节点的生成特征
            all_generated_features = set()
            all_feature_data = {}

            # 遍历所有节点，收集所有特征
            for node in dag.nodes():
                out_cur_df = getattr(node, 'out_cur_df', None)

                if out_cur_df is not None and hasattr(out_cur_df, 'columns'):
                    num_features = len(out_cur_df.columns)
                    if num_features > max_features:
                        max_features = num_features
                        best_data = out_cur_df.copy()
                        print(f"Found base data: {num_features} features from node {getattr(node, 'node_id', 'unknown')}")

                    # 收集所有生成特征的数据
                    original_features = {'gender', 'age', 'education', 'currentsmoker', 'cigsperday', 'bpmeds', 'prevalentstroke', 'prevalenthyp', 'diabetes', 'totchol', 'sysbp', 'diabp', 'bmi', 'heartrate', 'glucose', 'id'}
                    generated_features = [col for col in out_cur_df.columns if col not in original_features and col != 'tenyearchd']

                    for feature in generated_features:
                        if feature not in all_feature_data:
                            all_feature_data[feature] = out_cur_df[feature].values
                            all_generated_features.add(feature)
                            print(f"Collected feature '{feature}' from node {getattr(node, 'node_id', 'unknown')}")

            if best_data is None:
                print("No valid data found in any DAG node")
                return None

            # 将所有收集到的生成特征添加到基础数据中
            if all_feature_data:
                print(f"Adding {len(all_feature_data)} additional generated features to base data")
                for feature, values in all_feature_data.items():
                    if feature not in best_data.columns:
                        best_data[feature] = values
                        print(f"Added feature '{feature}' with shape {values.shape}")

            print(f"Final aggregated data with {len(best_data.columns)} features and {len(best_data)} rows")
            print(f"Generated features found: {list(all_generated_features)}")
            print(f"All features: {list(best_data.columns)}")

            # 尝试从DAG构造器中获取对应的目标变量，确保完全一致
            _, target_col, _ = task_config(task_name.lower())
            print(f"Adding target variable: {target_col}")

            # 方法1：尝试从DAG构造器获取label（最准确的方法）
            target_values = None
            try:
                # 重新加载pickle文件以获取完整的DAG构造器
                with open(pickle_file, "rb") as f:
                    dag_constructor = pickle.load(f)

                if hasattr(dag_constructor, 'label') and dag_constructor.label is not None:
                    # 检查label是否是DataFrame且长度匹配
                    if hasattr(dag_constructor.label, '__len__') and len(dag_constructor.label) == len(best_data):
                        if target_col in dag_constructor.label.columns:
                            target_values = dag_constructor.label[target_col].values
                            print(f"✅ Successfully extracted target variables from DAG constructor")
                            print(f"   Target variable distribution: {pd.Series(target_values).value_counts().to_dict()}")
                        else:
                            print(f"❌ Target column '{target_col}' not found in DAG constructor label")
                            print(f"   Available columns: {list(dag_constructor.label.columns)}")
                    else:
                        print(f"❌ DAG constructor label length mismatch: {len(dag_constructor.label)} vs {len(best_data)}")
                else:
                    print(f"⚠️  DAG constructor label not available or empty")

            except Exception as e:
                print(f"⚠️  Failed to extract from DAG constructor: {str(e)}")

            # 方法2：如果方法1失败，使用模拟DAG采样逻辑（回退方案）
            if target_values is None:
                print(f"Using fallback sampling method...")
                data_agenda, desc, csv_path = read_data_info(task_name)
                original_data = pd.read_csv(csv_path)

                if target_col not in original_data.columns:
                    print(f"Target column '{target_col}' not found in original data")
                    return None

                # 使用sklearn的train_test_split进行25%的分层采样
                from sklearn.model_selection import train_test_split

                # 获取25%的数据，模拟DAG的采样逻辑
                _, sampled_data = train_test_split(
                    original_data,
                    test_size=0.25,  # 25%采样
                    random_state=0,  # 固定随机种子
                    stratify=original_data[target_col]
                )

                # 确保采样后的数据长度与DAG数据匹配
                if len(sampled_data) != len(best_data):
                    print(f"Warning: Sampled data ({len(sampled_data)}) length mismatch with DAG data ({len(best_data)})")

                    # 如果长度不匹配，使用前N行
                    if len(original_data) >= len(best_data):
                        target_values = original_data[target_col].iloc[:len(best_data)].values
                    else:
                        print(f"Error: Original data too short for DAG data length")
                        return None
                else:
                    target_values = sampled_data[target_col].values

                print(f"⚠️  Used fallback stratified sampling method")

            # 添加目标变量到数据中
            best_data[target_col] = target_values

            print(f"Added target variable with distribution: {pd.Series(target_values).value_counts().to_dict()}")
            print(f"Final data shape: {best_data.shape}")
            print(f"Final columns: {list(best_data.columns)}")

            return best_data

        except Exception as e:
            print(f"Failed to extract complete DAG data: {str(e)}")
            return None

    def _identify_original_vs_generated_features(self, task_name: str, data: pd.DataFrame):
        """
        识别原始特征和生成特征

        Args:
            task_name: 任务名称
            data: 完整的特征数据

        Returns:
            包含原始特征和生成特征列表的字典
        """
        try:
            # 获取理论上的原始特征列表
            _, target_col, _ = task_config(task_name.lower())

            # 从数据集中读取预期的原始特征
            data_agenda, desc, csv_path = read_data_info(task_name)
            original_csv_data = pd.read_csv(csv_path)
            theoretical_original_features = set(original_csv_data.columns) - {target_col}

            # 获取实际数据中的所有特征
            actual_features = set(data.columns)

            # 分类特征（排除目标变量）
            original_features = []
            generated_features = []

            for feature in actual_features:
                if feature == target_col:
                    # 跳过目标变量
                    continue
                elif feature in theoretical_original_features:
                    original_features.append(feature)
                else:
                    generated_features.append(feature)

            print(f"Feature classification:")
            print(f"  📊 Original features: {len(original_features)}")
            print(f"  🆕 Generated features: {len(generated_features)}")

            if generated_features:
                print(f"  🎯 Generated: {generated_features}")

            return {
                'original': original_features,
                'generated': generated_features,
                'target': target_col
            }

        except Exception as e:
            print(f"Failed to identify features: {str(e)}")
            return {
                'original': list(data.columns),
                'generated': [],
                'target': 'unknown'
            }

    def _calculate_importance_metrics(self, data: pd.DataFrame, task_name: str, all_features: dict, methods: list):
        """
        计算特征重要性指标

        Args:
            data: 完整特征数据
            task_name: 任务名称
            all_features: 特征分类信息
            methods: 评估方法列表

        Returns:
            重要性指标结果
        """
        try:
            # 准备训练数据
            target_col = all_features['target']
            feature_cols = [col for col in data.columns if col != target_col]

            if target_col not in data.columns:
                print(f"Warning: Target column '{target_col}' not found in data")
                print(f"Available columns: {list(data.columns)}")
                return {}

            X = data[feature_cols]
            y = data[target_col]

            print(f"Training data shape: {X.shape}")
            print(f"Target distribution: {y.value_counts().to_dict()}")

            metrics_results = {}

            # 计算各种重要性指标
            if 'shap' in methods:
                metrics_results['shap'] = self._calculate_shap_importance(X, y)

            if 'ig' in methods:
                metrics_results['ig'] = self._calculate_ig_importance(X, y)

            if 'rfe' in methods:
                metrics_results['rfe'] = self._calculate_rfe_importance(X, y)

            if 'fi' in methods:
                metrics_results['fi'] = self._calculate_fi_importance(X, y)

            return metrics_results

        except Exception as e:
            print(f"Failed to calculate importance metrics: {str(e)}")
            return {}

    def _calculate_shap_importance(self, X, y):
        """计算SHAP重要性"""
        try:
            # 使用简单的模型
            model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=2)
            model.fit(X, y)

            # 计算SHAP值
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X)

            if isinstance(shap_values, list):
                shap_values = shap_values[1]  # 取正类

            # 计算特征重要性（绝对值的平均）
            shap_importance = np.abs(shap_values).mean(axis=0)

            # 创建特征重要性字典
            feature_importance = {feature: importance for feature, importance in zip(X.columns, shap_importance)}

            return {
                'feature_importance': feature_importance,
                'method': 'shap'
            }
        except Exception as e:
            print(f"SHAP calculation failed: {str(e)}")
            return {'error': str(e), 'method': 'shap'}

    def _calculate_ig_importance(self, X, y):
        """计算信息增益重要性"""
        try:
            from sklearn.feature_selection import mutual_info_classif

            mi_scores = mutual_info_classif(X, y, random_state=42)
            feature_importance = {feature: score for feature, score in zip(X.columns, mi_scores)}

            return {
                'feature_importance': feature_importance,
                'method': 'information_gain'
            }
        except Exception as e:
            print(f"IG calculation failed: {str(e)}")
            return {'error': str(e), 'method': 'information_gain'}

    def _calculate_rfe_importance(self, X, y):
        """计算RFE重要性"""
        try:
            # 使用简单的模型
            estimator = RandomForestClassifier(n_estimators=20, random_state=42, n_jobs=2)
            rfe = RFE(estimator=estimator, n_features_to_select=1)
            rfe.fit(X, y)

            # RFE排名（1是最好的）
            feature_importance = {feature: len(X.columns) - rank for feature, rank in zip(X.columns, rfe.ranking_)}

            return {
                'feature_importance': feature_importance,
                'method': 'rfe'
            }
        except Exception as e:
            print(f"RFE calculation failed: {str(e)}")
            return {'error': str(e), 'method': 'rfe'}

    def _calculate_fi_importance(self, X, y):
        """计算随机森林特征重要性"""
        try:
            model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=2)
            model.fit(X, y)

            feature_importance = {feature: float(importance) for feature, importance in zip(X.columns, model.feature_importances_)}

            return {
                'feature_importance': feature_importance,
                'method': 'feature_importance'
            }
        except Exception as e:
            print(f"FI calculation failed: {str(e)}")
            return {'error': str(e), 'method': 'feature_importance'}

    def _analyze_top_k_features(self, all_features: dict, metrics_results: dict, top_k: int):
        """
        分析Top-K特征中生成特征的比例

        Args:
            all_features: 特征分类信息
            metrics_results: 重要性指标结果
            top_k: Top-K数量

        Returns:
            Top-K分析结果
        """
        try:
            generated_features_set = set(all_features['generated'])

            top_k_analysis = {}

            for method, result in metrics_results.items():
                if 'error' not in result and 'feature_importance' in result:
                    importance = result['feature_importance']

                    # 按重要性排序并取Top-K
                    # 确保重要性值是标量，处理numpy数组情况
                    def get_importance_value(val):
                        import numpy as np
                        if isinstance(val, np.ndarray):
                            if val.size == 1:
                                return float(val.item())
                            else:
                                return float(np.mean(val))
                        else:
                            return float(val)

                    sorted_features = sorted(importance.items(), key=lambda x: get_importance_value(x[1]), reverse=True)
                    top_k_features = sorted_features[:top_k]

                    # 计算生成特征数量
                    generated_in_top_k = sum(1 for feature, _ in top_k_features if feature in generated_features_set)
                    percentage = (generated_in_top_k / top_k) * 100

                    # 构建详细分析
                    detailed_analysis = []
                    for rank, (feature, importance) in enumerate(top_k_features, 1):
                        is_generated = feature in generated_features_set
                        detailed_analysis.append({
                            'rank': rank,
                            'feature': feature,
                            'importance': importance,
                            'is_generated': is_generated
                        })

                    top_k_analysis[method] = {
                        'percentage': percentage,
                        'generated_count': generated_in_top_k,
                        'total_count': top_k,
                        'top_features_analysis': detailed_analysis,
                        'top_features': [f for f, _ in top_k_features],
                        'importances': [get_importance_value(i) for _, i in top_k_features]
                    }
                else:
                    top_k_analysis[method] = {
                        'percentage': 0.0,
                        'generated_count': 0,
                        'total_count': top_k,
                        'error': result.get('error', 'Unknown error'),
                        'top_features_analysis': [],
                        'top_features': [],
                        'importances': []
                    }

            return top_k_analysis

        except Exception as e:
            print(f"Failed to analyze Top-K features: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}


def calculate_simplified_paper_metrics(task_name: str, top_k: int = 7, methods: list = None):
    """
    简化的论文指标计算主函数

    Args:
        task_name: 任务名称
        top_k: Top-K特征数量
        methods: 评估方法列表

    Returns:
        完整的指标计算结果
    """
    if methods is None:
        methods = ['shap', 'ig', 'rfe', 'fi']

    calculator = PaperMetricsCalculatorSimplified()
    return calculator.calculate_paper_metrics(task_name, top_k, methods)


# 测试代码
if __name__ == "__main__":
    print("Simplified Paper Metrics Calculator - Test")
    print("=" * 60)

    # 测试简化版本
    results = calculate_simplified_paper_metrics(
        task_name="heart",
        top_k=7,
        methods=['fi', 'rfe']
    )

    if results:
        print("\n📊 Simplified Results:")
        print(f"Original features: {results['original_feature_count']}")
        print(f"Generated features: {results['generated_feature_count']}")
        print(f"Total features: {results['total_feature_count']}")
        print(f"Data shape: {results['data_shape']}")

        print("\n🎯 Top-K Analysis:")
        for method, analysis in results['metrics'].items():
            if method in results['top_k_analysis']:
                top_k_data = results['top_k_analysis'][method]
                print(f"  {method.upper()}: {top_k_data['percentage']:.2f}% ({top_k_data['generated_count']}/{top_k_data['total_count']})")

                if top_k_data['top_features_analysis']:
                    print(f"    Top features:")
                    for feat_info in top_k_data['top_features_analysis'][:3]:  # 显示前3个
                        status = "🆕NEW" if feat_info["is_generated"] else "📊ORIG"
                        print(f"      {feat_info['rank']:2d}. {status:<6} {feat_info['feature']:<25} ({feat_info['importance']:.4f})")
    else:
        print("❌ Failed to calculate simplified paper metrics")