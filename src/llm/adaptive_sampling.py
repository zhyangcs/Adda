import dataclasses
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from sklearn.model_selection import StratifiedKFold, KFold
from sklearn.metrics import roc_auc_score, mean_squared_error
import warnings
warnings.filterwarnings("ignore")

@dataclasses.dataclass
class SamplingConfig:
    """自适应采样配置类"""
    base_ratio: float = 0.05              # 基础采样率
    max_ratio: float = 0.2                # 最大采样率
    min_ratio: float = 0.01               # 最小采样率
    scales: List[float] = None            # 多尺度采样比例
    consistency_threshold: float = 0.1    # 一致性阈值
    max_iterations: int = 3               # 最大迭代次数
    adaptive_enabled: bool = True         # 是否启用自适应采样

    def __post_init__(self):
        if self.scales is None:
            self.scales = [0.05, 0.1, 0.15]

class AdaptiveSamplingValidator:
    """自适应采样验证器

    基于迭代重采样论文的思想，验证特征在sample和完整数据集上的一致性
    """

    def __init__(self, eval_model, task_type: str, config: SamplingConfig = None):
        self.eval_model = eval_model
        self.task_type = task_type
        self.config = config or SamplingConfig()

    def validate_feature_consistency(self, node, original_df: pd.DataFrame,
                                    target_col: str) -> Tuple[float, float, List[float]]:
        """验证特征在sample和完整数据集上的一致性

        Args:
            node: 特征节点
            original_df: 原始完整数据集
            target_col: 目标列名

        Returns:
            Tuple[consistency_score, bias, multi_scale_scores]
                - consistency_score: 一致性分数 (0-1, 越高越好)
                - bias: 性能偏差 (0-1, 越低越好)
                - multi_scale_scores: 多尺度评估分数列表
        """
        multi_scale_scores = []

        # 多尺度采样验证
        for scale in self.config.scales:
            sample_df = self._stratified_sample(original_df, target_col, scale)
            score = self._evaluate_node_on_data(node, sample_df, target_col)
            multi_scale_scores.append(score)

        # 计算稳定性指标
        if len(multi_scale_scores) > 1:
            score_variance = np.var(multi_scale_scores)
            score_mean = np.mean(multi_scale_scores)
            stability = 1 - (score_variance / (score_mean + 1e-6))
        else:
            stability = 1.0

        # 计算偏差（与基准比较）
        baseline_score = self._evaluate_node_on_data(
            node, original_df.sample(n=min(1000, len(original_df)), random_state=42),
            target_col
        )

        bias = 0
        for score in multi_scale_scores:
            relative_error = abs(score - baseline_score) / (abs(baseline_score) + 1e-6)
            bias += relative_error

        bias = bias / len(multi_scale_scores)

        # 一致性分数 = 稳定性 * (1 - 偏差)
        consistency_score = stability * (1 - bias)

        return consistency_score, bias, multi_scale_scores

    def adaptive_sampling_ratio(self, node, feature_complexity: float = None) -> float:
        """根据特征复杂度和历史性能自适应调整采样率

        Args:
            node: 特征节点
            feature_complexity: 特征复杂度 (0-1)

        Returns:
            采样率
        """
        if not self.config.adaptive_enabled:
            return self.config.base_ratio

        base_ratio = self.config.base_ratio

        # 根据特征复杂度调整
        if feature_complexity:
            if feature_complexity > 0.8:
                # 复杂特征使用更大采样
                ratio = min(self.config.max_ratio, base_ratio * 2)
            elif feature_complexity < 0.3:
                # 简单特征使用较小采样
                ratio = max(self.config.min_ratio, base_ratio * 0.8)
            else:
                ratio = base_ratio
        else:
            ratio = base_ratio

        # 根据历史一致性调整
        if hasattr(node, 'consistency_history') and node.consistency_history:
            avg_consistency = np.mean(node.consistency_history)
            if avg_consistency < self.config.consistency_threshold:
                # 历史一致性差，增加采样
                ratio = min(self.config.max_ratio, ratio * 1.5)
            elif avg_consistency > 0.9:
                # 历史一致性好，可以减少采样
                ratio = max(self.config.min_ratio, ratio * 0.8)

        return ratio

    def iterative_validation(self, node, original_df: pd.DataFrame,
                           target_col: str) -> Dict[str, Any]:
        """迭代验证机制

        类似论文中的迭代重优化，通过多次采样验证直到特征表现稳定

        Args:
            node: 特征节点
            original_df: 原始完整数据集
            target_col: 目标列名

        Returns:
            验证结果字典
        """
        results = {
            'iterations': [],
            'final_consistency': 0,
            'final_bias': 0,
            'converged': False,
            'recommended_sampling_ratio': self.config.base_ratio
        }

        current_ratio = self.config.base_ratio

        for iteration in range(self.config.max_iterations):
            # 当前迭代采样
            sample_df = self._stratified_sample(original_df, target_col, current_ratio)

            # 评估性能
            score = self._evaluate_node_on_data(node, sample_df, target_col)
            consistency, bias, _ = self.validate_feature_consistency(
                node, original_df, target_col
            )

            # 记录结果
            results['iterations'].append({
                'iteration': iteration + 1,
                'sampling_ratio': current_ratio,
                'score': score,
                'consistency': consistency,
                'bias': bias
            })

            # 检查收敛
            if consistency >= (1 - self.config.consistency_threshold):
                results['converged'] = True
                results['final_consistency'] = consistency
                results['final_bias'] = bias
                results['recommended_sampling_ratio'] = current_ratio
                break

            # 调整采样率
            if bias > self.config.consistency_threshold:
                current_ratio = min(self.config.max_ratio, current_ratio * 1.2)

        if not results['converged']:
            # 未收敛，使用最后一次结果
            last_iteration = results['iterations'][-1]
            results['final_consistency'] = last_iteration['consistency']
            results['final_bias'] = last_iteration['bias']
            results['recommended_sampling_ratio'] = current_ratio

        return results

    def _stratified_sample(self, df: pd.DataFrame, target_col: str,
                          ratio: float) -> pd.DataFrame:
        """分层采样"""
        if target_col not in df.columns:
            return df.sample(n=max(1, int(len(df) * ratio)), random_state=42)

        try:
            # 分层采样
            sampled_df = df.groupby(target_col).apply(
                lambda x: x.sample(n=max(1, int(len(x) * ratio)), random_state=42)
            ).reset_index(drop=True)
            return sampled_df
        except:
            # 分层采样失败，使用随机采样
            return df.sample(n=max(1, int(len(df) * ratio)), random_state=42)

    def _evaluate_node_on_data(self, node, df: pd.DataFrame,
                              target_col: str) -> float:
        """在给定数据集上评估节点性能"""
        try:
            # 准备数据
            if target_col in df.columns:
                test_df = df.copy()
                labels = test_df[target_col]
                test_df = test_df.drop(columns=[target_col])
            else:
                # 如果没有目标列，使用节点自带的标签
                if hasattr(node, 'label') and node.label is not None:
                    labels = node.label
                    test_df = df.copy()
                else:
                    return 0.5  # 默认分数

            # 确保特征列存在
            if hasattr(node, 'out_cur_df') and not node.out_cur_df.empty:
                test_df = node.out_cur_df

            # 使用模型评估
            if self.task_type == "classify":
                # 分类任务使用AUC
                from sklearn.model_selection import cross_val_score
                scores = cross_val_score(self.eval_model, test_df, labels,
                                       cv=3, scoring='roc_auc')
                return np.mean(scores)
            else:
                # 回归任务使用负MSE
                from sklearn.model_selection import cross_val_score
                scores = cross_val_score(self.eval_model, test_df, labels,
                                       cv=3, scoring='neg_mean_squared_error')
                return -np.mean(scores)  # 转为正值

        except Exception as e:
            print(f"Error evaluating node: {e}")
            return 0.5  # 默认分数

class AdaptiveSamplingEstimator:
    """自适应采样估计器

    基于论文的选择性估计器思想，为特征搜索提供准确的性能估计
    """

    def __init__(self, config: SamplingConfig = None):
        self.config = config or SamplingConfig()
        self.estimate_history = {}

    def estimate_feature_performance(self, feature_id: str, node,
                                   original_df: pd.DataFrame, target_col: str,
                                   eval_model, task_type: str) -> Dict[str, Any]:
        """估计特征性能

        Args:
            feature_id: 特征标识
            node: 特征节点
            original_df: 原始数据集
            target_col: 目标列
            eval_model: 评估模型
            task_type: 任务类型

        Returns:
            性能估计结果
        """
        validator = AdaptiveSamplingValidator(eval_model, task_type, self.config)

        # 迭代验证
        validation_results = validator.iterative_validation(node, original_df, target_col)

        # 估计性能
        estimated_performance = validation_results['iterations'][-1]['score']

        # 计算置信度
        consistency = validation_results['final_consistency']
        confidence = consistency  # 简化的置信度计算

        # 记录历史
        self.estimate_history[feature_id] = {
            'estimated_performance': estimated_performance,
            'confidence': confidence,
            'validation_results': validation_results,
            'timestamp': pd.Timestamp.now()
        }

        return {
            'feature_id': feature_id,
            'estimated_performance': estimated_performance,
            'confidence': confidence,
            'validation_results': validation_results,
            'recommended_sampling_ratio': validation_results['recommended_sampling_ratio']
        }