#!/usr/bin/env python3
"""
完整论文指标计算模块

基于论文的真实含义：
- 获取所有原始特征
- 获取所有生成的特征（不仅仅是最佳特征）
- 在完整特征集上计算SHAP、IG、RFE、FI指标
- 统计Top-7中生成特征的百分比
"""

import os
import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import warnings
import pickle
import re

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入项目依赖
from src.llm.tests.test_util import task_config, read_data_info
from src.env import dataset_path, test_save_path
from frontend.feature_importance_calculator import calculate_importance_from_data


class CompletePaperMetricsCalculator:
    """
    完整的论文指标计算器

    实现论文Table 10的真实逻辑：
    - 获取所有原始特征 + 所有生成特征
    - 在完整特征集上计算重要性指标
    - 统计Top-7中生成特征的百分比
    """

    def __init__(self, dataset_path_override: str = None):
        """
        初始化计算器

        Args:
            dataset_path_override: 覆盖默认数据集路径
        """
        self.dataset_path = dataset_path_override or dataset_path

    def get_all_original_features(self, task_name: str) -> List[str]:
        """
        获取数据集中的所有原始特征

        Args:
            task_name: 任务名称

        Returns:
            原始特征列表
        """
        try:
            # 读取原始CSV文件
            csv_path = os.path.join(self.dataset_path, task_name, "train_new.csv")
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"Data file not found: {csv_path}")

            df = pd.read_csv(csv_path)

            # 获取目标列名
            _, target_col, _ = task_config(task_name.lower())

            # 返回除目标列外的所有列
            original_features = [col for col in df.columns if col != target_col]
            print(f"Found {len(original_features)} original features in dataset")

            return original_features

        except Exception as e:
            print(f"Failed to get original features: {str(e)}")
            return []

    def extract_all_generated_features(self, task_name: str) -> List[str]:
        """
        从Adda DAG中提取所有生成的特征

        Args:
            task_name: 任务名称

        Returns:
            所有生成特征列表
        """
        try:
            # 尝试多个可能的pickle文件路径
            possible_paths = [
                os.path.join(test_save_path, f"{task_name}_RF_Full", "cur_states.pkl"),
                os.path.join(test_save_path, task_name, "cur_states.pkl"),
                # 尝试找到最新的RF_Full目录
            ]

            # 如果上述路径都不存在，尝试查找最新的RF_Full目录
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
                print(f"DAG pickle file not found in any expected location")
                print("Searched paths:")
                for path in possible_paths:
                    print(f"  - {path}")
                return []

            with open(pickle_file, "rb") as f:
                dag_constructor = pickle.load(f)

            generated_features = []
            dag = dag_constructor.dag

            print(f"DAG has {len(dag.nodes())} nodes")

            # 遍历DAG中的所有节点，提取每个节点的write_set中的特征
            for node in dag.nodes():
                node_data = dag.nodes[node]

                # 跳过根节点（原始特征节点）- 通过node_id判断
                if hasattr(node, 'node_id') and node.node_id == 1:
                    continue

                # 方法1: 从节点的write_set中提取生成的特征（最准确的方法）
                write_set = node_data.get('write_set', set())
                if write_set:
                    generated_features.extend(list(write_set))
                    print(f"Found {len(write_set)} features in write_set of node {node}: {write_set}")

                # 方法2: 从fixing_node中提取特征（如果有）
                fixing_nodes = node_data.get('fixing_node', [])
                for fixing_node in fixing_nodes:
                    fixing_write_set = fixing_node.get('write_set', set())
                    if fixing_write_set:
                        generated_features.extend(list(fixing_write_set))
                        print(f"Found {len(fixing_write_set)} features in fixing_node of node {node}: {fixing_write_set}")

                # 方法3: 从out_cur_df的列名中提取新特征
                out_cur_df = node_data.get('out_cur_df')
                if out_cur_df is not None and hasattr(out_cur_df, 'columns') and len(out_cur_df.columns) > 0:
                    # 获取输出DataFrame的所有列名
                    out_columns = list(out_cur_df.columns)
                    print(f"Node {node} out_cur_df columns: {out_columns}")
                    generated_features.extend(out_columns)

                # 方法4: 从节点字符串描述中提取特征（回退方案）
                node_str = str(node)
                print(f"Node string representation: {node_str[:200]}...")

                # 从字符串中提取write_set信息
                write_set_pattern = r"write_set=\{([^}]+)\}"
                write_set_match = re.search(write_set_pattern, node_str)
                if write_set_match:
                    write_set_content = write_set_match.group(1)
                    # 提取单引号中的特征名
                    feature_pattern = r"'([^']+)'"
                    features_from_str = re.findall(feature_pattern, write_set_content)
                    if features_from_str:
                        generated_features.extend(features_from_str)
                        print(f"Found {len(features_from_str)} features from node string: {features_from_str}")

                # 从字符串中提取fixing_node信息
                fixing_node_pattern = r"fixing_node=\[([^\]]+)\]"
                fixing_node_match = re.search(fixing_node_pattern, node_str)
                if fixing_node_match:
                    fixing_node_content = fixing_node_match.group(1)
                    fixing_features = re.findall(feature_pattern, fixing_node_content)
                    if fixing_features:
                        generated_features.extend(fixing_features)
                        print(f"Found {len(fixing_features)} features from fixing_node string: {fixing_features}")

            # 去重并过滤
            generated_features = list(set(generated_features))  # 去重
            generated_features = [f for f in generated_features if f and f.strip()]  # 过滤空值

            print(f"Extracted {len(generated_features)} features from DAG nodes")

            # 过滤掉原始特征和目标变量
            try:
                original_features = self.get_all_original_features(task_name)
                _, target_col, _ = task_config(task_name.lower())

                # 创建排除集合（原始特征 + 目标变量）
                excluded_set = set([f.lower() for f in original_features])
                excluded_set.add(target_col.lower())

                # 只保留真正的生成特征
                true_generated = []
                for f in generated_features:
                    if f.lower() not in excluded_set:
                        true_generated.append(f)

                generated_features = true_generated
                print(f"After filtering original features and target: {len(generated_features)} true generated features")

            except Exception as e:
                print(f"Warning: Failed to filter original features: {e}")

            print(f"Final generated features: {generated_features}")

            # 如果确实没有生成特征，使用回退方案
            if len(generated_features) == 0:
                print("No features extracted from DAG, using fallback from pycodes")
                generated_features = self._extract_features_from_pycodes(task_name)

            return generated_features

        except Exception as e:
            print(f"Failed to extract generated features: {str(e)}")
            # 回退方案：从pycodes目录中提取
            return self._extract_features_from_pycodes(task_name)

    def _extract_feature_name_from_desc(self, desc: str, node_id: int) -> Optional[str]:
        """
        从描述中提取特征名称

        Args:
            desc: 特征描述
            node_id: 节点ID

        Returns:
            提取的特征名称
        """
        if not desc:
            return None

        # 方法1: 查找赋值语句 df['feature_name'] = ...
        assignment_pattern = r"df\['([^']+)'\]\s*="
        matches = re.findall(assignment_pattern, desc)
        if matches:
            return matches[0]

        # 方法2: 查找变量赋值 feature_name = ...
        var_pattern = r"(\w+)\s*="
        var_matches = re.findall(var_pattern, desc)
        if var_matches:
            # 过滤掉常见的Python关键字
            filtered = [v for v in var_matches if v not in ['import', 'from', 'def', 'class', 'if', 'for', 'while']]
            if filtered:
                return filtered[0]

        # 方法3: 使用节点ID
        return f"generated_feature_{node_id}"

    def _extract_features_from_pycodes(self, task_name: str) -> List[str]:
        """
        从pycodes目录中提取特征名称（回退方案）

        Args:
            task_name: 任务名称

        Returns:
            特征名称列表
        """
        try:
            # 尝试多个可能的pycodes路径
            possible_paths = [
                os.path.join(test_save_path, f"{task_name}_RF_Full", "pycodes"),
            ]

            # 如果上述路径不存在，尝试查找最新的RF_Full目录
            pycodes_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    pycodes_path = path
                    break

            if pycodes_path is None:
                # 尝试查找最新的RF_Full目录
                test_store_path = os.path.dirname(test_save_path)
                rf_full_dirs = [d for d in os.listdir(test_store_path)
                              if d.startswith(f"{task_name}_RF_Full")]
                if rf_full_dirs:
                    latest_dir = sorted(rf_full_dirs)[-1]
                    pycodes_path = os.path.join(test_store_path, latest_dir, "pycodes")

            if pycodes_path is None or not os.path.exists(pycodes_path):
                print(f"Pycodes directory not found for {task_name}")
                return []

            generated_features = []

            for file_name in os.listdir(pycodes_path):
                if file_name.endswith('.py'):
                    file_path = os.path.join(pycodes_path, file_name)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # 提取所有df['feature'] = ... 中的特征名
                    pattern = r"df\['([^']+)'\]\s*="
                    matches = re.findall(pattern, content)
                    generated_features.extend(matches)

            # 过滤和去重
            generated_features = list(set(generated_features))
            generated_features = [f for f in generated_features if not f.isdigit() and f.strip()]

            # 获取原始特征列表和目标变量来过滤
            try:
                original_features = self.get_all_original_features(task_name)
                _, target_col, _ = task_config(task_name.lower())

                # 创建原始特征和目标变量的集合
                excluded_set = set([f.lower() for f in original_features])
                excluded_set.add(target_col.lower())

                # 只保留不在原始特征中且不是目标变量的特征
                true_generated = []
                for f in generated_features:
                    if f.lower() not in excluded_set:
                        true_generated.append(f)

                generated_features = true_generated
                print(f"After filtering original features and target variable: {len(generated_features)} true generated features")

            except Exception as e:
                print(f"Warning: Failed to filter original features: {e}")

            print(f"Extracted {len(generated_features)} features from pycodes (fallback)")
            return generated_features

        except Exception as e:
            print(f"Failed to extract from pycodes: {str(e)}")
            return []

    def build_complete_feature_matrix(
        self,
        task_name: str,
        original_features: List[str],
        generated_features: List[str]
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        构建包含原始和生成特征的完整特征矩阵

        Args:
            task_name: 任务名称
            original_features: 原始特征列表
            generated_features: 生成特征列表

        Returns:
            (特征矩阵, 目标变量)
        """
        print("Building complete feature matrix...")

        # 1. 读取原始数据
        data_path = os.path.join(self.dataset_path, task_name, "train_new.csv")
        df = pd.read_csv(data_path)
        _, target_col, _ = task_config(task_name.lower())

        print(f"Original data shape: {df.shape}")

        # 2. 提取原始特征数据
        available_original = [f for f in original_features if f in df.columns]
        X_original = df[available_original].copy()
        y = df[target_col].copy()

        print(f"Available original features: {len(available_original)}/{len(original_features)}")

        # 3. 尝试从DAG中获取生成特征
        X_generated = pd.DataFrame(index=df.index)

        if generated_features:
            print(f"Attempting to generate {len(generated_features)} features...")
            X_generated = self._generate_features_from_dag(
                task_name, df, generated_features
            )

        # 4. 合并特征
        all_feature_names = list(X_original.columns) + list(X_generated.columns)
        X_complete = pd.concat([X_original, X_generated], axis=1)

        print(f"Complete feature matrix shape: {X_complete.shape}")
        print(f"Total features: {len(all_feature_names)}")

        # 5. 处理缺失值
        X_complete = X_complete.fillna(X_complete.median(numeric_only=True))
        X_complete = X_complete.fillna(0)  # 填充剩余的缺失值

        return X_complete, y

    def _generate_features_from_dag(
        self,
        task_name: str,
        df: pd.DataFrame,
        generated_features: List[str]
    ) -> pd.DataFrame:
        """
        从DAG节点的输出中直接获取生成的特征数据

        Args:
            task_name: 任务名称
            df: 原始数据（用于确保索引匹配）
            generated_features: 要获取的特征列表

        Returns:
            生成的特征数据
        """
        try:
            # 保存原始数据索引
            original_index = df.index

            # 尝试多个可能的pickle文件路径
            possible_paths = [
                os.path.join(test_save_path, f"{task_name}_RF_Full", "cur_states.pkl"),
            ]

            # 如果上述路径不存在，尝试查找最新的RF_Full目录
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
                print(f"DAG pickle file not found for feature generation: {task_name}")
                return pd.DataFrame(index=original_index)

            with open(pickle_file, "rb") as f:
                dag_constructor = pickle.load(f)

            dag = dag_constructor.dag
            X_generated = pd.DataFrame(index=original_index)

            print(f"Attempting to extract features from {len(dag.nodes())} DAG nodes")

            # 使用字符串解析方法，检查所有节点并获取特征数据
            for node in dag.nodes():
                node_str = str(node)

                # 跳过根节点 - 通过node_id判断
                if hasattr(node, 'node_id') and node.node_id == 1:
                    continue

                # 从节点字符串中识别这个节点包含哪些生成特征
                node_features = set()

                # 从字符串中提取write_set信息
                write_set_pattern = r"write_set=\{([^}]+)\}"
                write_set_match = re.search(write_set_pattern, node_str)
                if write_set_match:
                    write_set_content = write_set_match.group(1)
                    feature_pattern = r"'([^']+)'"
                    features_from_str = re.findall(feature_pattern, write_set_content)
                    node_features.update(features_from_str)

                # 从字符串中提取fixing_node信息
                fixing_node_pattern = r"fixing_node=\[([^\]]+)\]"
                fixing_node_match = re.search(fixing_node_pattern, node_str)
                if fixing_node_match:
                    fixing_node_content = fixing_node_match.group(1)
                    fixing_features = re.findall(feature_pattern, fixing_node_content)
                    node_features.update(fixing_features)

                # 检查这个节点是否包含我们要找的生成特征
                target_features = node_features & set(generated_features)

                if target_features:
                    print(f"Node {node} contains {len(target_features)} target features: {target_features}")

                    # 使用正确的数据访问方式：直接访问节点属性
                    out_cur_df = getattr(node, 'out_cur_df', None)

                    if out_cur_df is not None and hasattr(out_cur_df, 'columns'):
                        print(f"Node {node} out_cur_df shape: {out_cur_df.shape}, columns: {list(out_cur_df.columns)}")

                        # 确保索引匹配，将特征数据添加到结果中
                        for feature_name in target_features:
                            if feature_name in out_cur_df.columns:
                                print(f"Extracting feature '{feature_name}' with shape {out_cur_df[feature_name].shape}")

                                # 如果输出DataFrame的索引与原始数据不同，需要重新索引
                                if not out_cur_df.index.equals(original_index):
                                    if len(out_cur_df) == len(original_index):
                                        # 长度相同，直接重新索引
                                        X_generated[feature_name] = out_cur_df[feature_name].values
                                        print(f"Reindexed feature '{feature_name}'")
                                    else:
                                        print(f"Warning: Length mismatch for feature {feature_name}")
                                        print(f"  Original data length: {len(original_index)}")
                                        print(f"  Feature data length: {len(out_cur_df)}")
                                        # 截断或填充到匹配长度
                                        min_len = min(len(out_cur_df), len(original_index))
                                        if min_len > 0:
                                            X_generated[feature_name].iloc[:min_len] = out_cur_df[feature_name].iloc[:min_len].values
                                else:
                                    X_generated[feature_name] = out_cur_df[feature_name]
                                    print(f"Directly assigned feature '{feature_name}'")
                            else:
                                print(f"Feature '{feature_name}' not found in out_cur_df columns")
                    else:
                        print(f"Node {node} has no valid out_cur_df")

                    # 也检查fixing_node中的特征数据
                    fixing_nodes = getattr(node, 'fixing_node', [])
                    for i, fixing_node in enumerate(fixing_nodes):
                        fixing_out_cur_df = getattr(fixing_node, 'out_cur_df', None)
                        if fixing_out_cur_df is not None and hasattr(fixing_out_cur_df, 'columns'):
                            fixing_target_features = set(fixing_out_cur_df.columns) & set(generated_features)
                            for feature_name in fixing_target_features:
                                if feature_name in fixing_out_cur_df.columns:
                                    print(f"Extracting fixing feature '{feature_name}' from fixing_node[{i}]")
                                    if len(fixing_out_cur_df) == len(original_index):
                                        X_generated[feature_name] = fixing_out_cur_df[feature_name].values
                                        print(f"Successfully added fixing feature '{feature_name}'")

            print(f"Successfully generated {len(X_generated.columns)} features from DAG")
            print(f"Generated features: {list(X_generated.columns)}")

            return X_generated

        except Exception as e:
            print(f"Feature generation from DAG failed: {str(e)}")
            # 如果从DAG获取失败，返回空的DataFrame
            return pd.DataFrame(index=df.index)

    def calculate_complete_paper_metrics(
        self,
        task_name: str,
        top_k: int = 7,
        methods: List[str] = None
    ) -> Dict[str, Any]:
        """
        计算完整的论文指标

        Args:
            task_name: 任务名称
            top_k: Top-k特征数量
            methods: 重要性计算方法列表

        Returns:
            论文指标结果
        """
        if methods is None:
            methods = ["fi", "rfe", "shap", "ig"]

        print(f"🎯 [PAPER METRICS] Starting calculation for {task_name}")
        print(f"   Methods: {methods}")
        print(f"   Top-K: {top_k}")
        print("-" * 60)

        # 1. 获取所有原始特征
        print("📋 [PAPER METRICS] Step 1: Getting original features...")
        original_features = self.get_all_original_features(task_name)
        if not original_features:
            raise ValueError("No original features found")
        print(f"   ✅ Found {len(original_features)} original features")
        print(f"   📊 First 5: {original_features[:5]}")

        # 2. 获取所有生成特征
        print(f"\n🆕 [PAPER METRICS] Step 2: Extracting generated features...")
        generated_features = self.extract_all_generated_features(task_name)
        print(f"   ✅ Found {len(generated_features)} generated features")
        if generated_features:
            print(f"   🆕 Generated: {generated_features}")
        else:
            print("   ⚠️  No generated features found!")

        # 3. 构建完整特征矩阵
        print(f"\n🔧 [PAPER METRICS] Step 3: Building complete feature matrix...")
        X_complete, y = self.build_complete_feature_matrix(
            task_name, original_features, generated_features
        )
        print(f"   ✅ Built feature matrix: {X_complete.shape}")
        print(f"   📊 Feature columns: {list(X_complete.columns)}")

        # 4. 计算任务类型
        try:
            _, _, task_type = task_config(task_name.lower())
            print(f"   🎯 Task type: {task_type}")
        except:
            task_type = "classify"  # 默认分类任务
            print(f"   ⚠️  Using default task type: {task_type}")

        # 5. 计算重要性指标
        print(f"\n📈 [PAPER METRICS] Step 4: Calculating importance metrics...")
        all_feature_names = list(X_complete.columns)
        print(f"   📊 Total features for importance calculation: {len(all_feature_names)}")

        importance_results = calculate_importance_from_data(
            X_complete, y,
            task_type=task_type,
            feature_names=all_feature_names,
            methods=methods
        )

        print(f"   ✅ Importance calculation completed")
        for method in methods:
            if method in importance_results and importance_results[method]:
                print(f"   📈 {method.upper()}: {len(importance_results[method])} features ranked")
            else:
                print(f"   ❌ {method.upper()}: Failed to calculate")

        # 6. 统计Top-7中生成特征的百分比
        print(f"\n🎯 [PAPER METRICS] Step 5: Analyzing Top-K features...")
        generated_set = set([f.lower().strip() for f in generated_features])
        print(f"   🆕 Generated features set: {len(generated_set)} features")
        results = {}

        for method in methods:
            print(f"   📊 Analyzing {method.upper()}...")
            if method in importance_results and importance_results[method]:
                method_results = self._calculate_method_percentage(
                    importance_results[method],
                    generated_set,
                    top_k
                )
                results[method] = method_results
                print(f"      ✅ {method.upper()}: {method_results['percentage']:.2f}% "
                      f"({method_results['generated_count']}/{top_k})")

                # 显示Top-K详情
                if method_results['top_features_analysis']:
                    print(f"      🏆 Top-{top_k} {method.upper()} features:")
                    for feature_info in method_results['top_features_analysis'][:5]:
                        status = "🆕" if feature_info["is_generated"] else "📊"
                        print(f"         {status} {feature_info['feature']} "
                              f"({feature_info['importance']:.4f})")
            else:
                results[method] = {
                    "percentage": 0.0,
                    "generated_count": 0,
                    "top_features_analysis": [],
                    "error": f"Method {method} failed to calculate"
                }
                print(f"      ❌ {method.upper()}: Failed")

        # 7. 返回结果
        print(f"\n✅ [PAPER METRICS] Calculation completed successfully!")
        print("-" * 60)
        return {
            "task_name": task_name,
            "method_name": "Adda",
            "original_feature_count": len(original_features),
            "generated_feature_count": len(generated_features),
            "total_feature_count": len(all_feature_names),
            "top_k": top_k,
            "metrics": results,
            "all_features": {
                "original": original_features,
                "generated": generated_features,
                "all": all_feature_names
            }
        }

    def _calculate_method_percentage(
        self,
        importance_list: List[Dict[str, float]],
        generated_set: set,
        top_k: int
    ) -> Dict[str, Any]:
        """
        计算单个方法的百分比

        Args:
            importance_list: 重要性列表
            generated_set: 生成特征集合
            top_k: top-k数量

        Returns:
            包含百分比和分析结果的字典
        """
        if not importance_list:
            return {"percentage": 0.0, "generated_count": 0, "top_features_analysis": []}

        # 取top-k特征
        top_k_features = importance_list[:top_k]

        # 统计新生成的特征数量
        generated_count = 0
        top_features_analysis = []

        for i, feature_info in enumerate(top_k_features):
            feature_name = feature_info["feature"]
            is_generated = feature_name.lower().strip() in generated_set

            if is_generated:
                generated_count += 1

            top_features_analysis.append({
                "rank": i + 1,
                "feature": feature_name,
                "importance": feature_info["importance"],
                "is_generated": is_generated
            })

        # 计算百分比
        percentage = (generated_count / top_k) * 100.0 if top_k > 0 else 0.0

        return {
            "percentage": percentage,
            "generated_count": generated_count,
            "top_k_count": top_k,
            "top_features_analysis": top_features_analysis
        }


def calculate_complete_paper_metrics(
    task_name: str,
    top_k: int = 7,
    methods: List[str] = None,
    dataset_path: str = None
) -> Dict[str, Any]:
    """
    便利函数：计算完整论文指标

    Args:
        task_name: 任务名称
        top_k: top-k数量
        methods: 重要性方法列表
        dataset_path: 数据集路径

    Returns:
        完整论文指标结果
    """
    calculator = CompletePaperMetricsCalculator(dataset_path)
    return calculator.calculate_complete_paper_metrics(task_name, top_k, methods)


if __name__ == "__main__":
    # 测试代码
    print("Complete Paper Metrics Calculator - Test")
    print("=" * 60)

    task_name = "heart"

    try:
        # 计算完整论文指标
        results = calculate_complete_paper_metrics(
            task_name=task_name,
            top_k=7,
            methods=["fi", "rfe"]  # 先用基础方法测试
        )

        print(f"✅ Results for {results['task_name']}:")
        print(f"Original features: {results['original_feature_count']}")
        print(f"Generated features: {results['generated_feature_count']}")
        print(f"Total features: {results['total_feature_count']}")
        print(f"Top-{results['top_k']} metrics:")

        for method, metric_data in results['metrics'].items():
            if 'percentage' in metric_data:
                print(f"  {method.upper()}: {metric_data['percentage']:.2f}% "
                      f"({metric_data['generated_count']}/{metric_data['top_k_count']})")
            else:
                print(f"  {method.upper()}: Error - {metric_data.get('error', 'Unknown error')}")

        print(f"\n📊 Detailed Analysis:")
        for method, metric_data in results['metrics'].items():
            if 'top_features_analysis' in metric_data and metric_data['top_features_analysis']:
                print(f"\n{method.upper()} Top Features:")
                for feature_info in metric_data['top_features_analysis']:
                    status = "🆕" if feature_info["is_generated"] else "📊"
                    print(f"  {status} {feature_info['rank']:2d}. {feature_info['feature']:<25} "
                          f"(importance: {feature_info['importance']:.4f})")

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()