"""
对比方法模块
提供多种机器学习方法的特征工程和模型训练对比功能
无需PostgreSQL扩展，使用Python库实现
"""

import os
import time
import json
import warnings
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any

# 机器学习库
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.svm import SVC, SVR
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder, PolynomialFeatures
from sklearn.feature_selection import SelectKBest, f_classif, f_regression, RFE
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score, precision_score, recall_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# AutoML库 (如果可用)
try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False

try:
    from autosklearn.classification import AutoSklearnClassifier
    from autosklearn.regression import AutoSklearnRegressor
    AUTOSKLEARN_AVAILABLE = True
except ImportError:
    AUTOSKLEARN_AVAILABLE = False

try:
    import tpot
    TPOT_AVAILABLE = True
except ImportError:
    TPOT_AVAILABLE = False

warnings.filterwarnings("ignore")


class ComparisonMethod:
    """对比方法基类"""

    def __init__(self, name: str):
        self.name = name
        self.execution_time = 0.0
        self.preprocessing_time = 0.0
        self.feature_generation_time = 0.0
        self.training_time = 0.0
        self.evaluation_time = 0.0

    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        """训练模型并返回性能指标"""
        raise NotImplementedError

    def get_time_breakdown(self) -> Dict[str, float]:
        """获取时间分解"""
        return {
            "preprocessing_time": self.preprocessing_time,
            "feature_generation_time": self.feature_generation_time,
            "training_time": self.training_time,
            "evaluation_time": self.evaluation_time,
            "total_time": self.execution_time
        }


class BaselineMethod(ComparisonMethod):
    """基线方法：原始特征 + 标准模型"""

    def __init__(self):
        super().__init__("Baseline (Raw Features)")

    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        start_time = time.time()

        # 预处理
        prep_start = time.time()
        X_processed = self._preprocess_data(X)
        self.preprocessing_time = time.time() - prep_start

        # 特征生成（基线方法不做特征工程）
        self.feature_generation_time = 0.0

        # 训练和评估
        train_start = time.time()
        metrics = self._train_and_evaluate(X_processed, y, task_type)
        self.training_time = time.time() - train_start

        self.execution_time = time.time() - start_time
        self.evaluation_time = self.execution_time - self.preprocessing_time - self.training_time

        return metrics

    def _preprocess_data(self, X: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        X_processed = X.copy()

        # 处理缺失值
        numeric_columns = X_processed.select_dtypes(include=[np.number]).columns
        X_processed[numeric_columns] = X_processed[numeric_columns].fillna(X_processed[numeric_columns].median())

        categorical_columns = X_processed.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            X_processed[col] = X_processed[col].fillna(X_processed[col].mode()[0] if not X_processed[col].mode().empty else 'unknown')
            le = LabelEncoder()
            X_processed[col] = le.fit_transform(X_processed[col].astype(str))

        return X_processed

    def _train_and_evaluate(self, X: pd.DataFrame, y: pd.Series, task_type: str) -> Dict[str, float]:
        """训练模型和评估"""
        if task_type == "classify":
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            scoring = 'roc_auc'
        else:
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            scoring = 'neg_mean_squared_error'

        # 交叉验证评估
        cv_scores = cross_val_score(model, X, y, cv=5, scoring=scoring)

        if task_type == "classify":
            mean_score = cv_scores.mean()

            # 计算其他指标
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1] if len(model.classes_) == 2 else y_pred

            return {
                "auc": mean_score,
                "accuracy": accuracy_score(y_test, y_pred),
                "f1": f1_score(y_test, y_pred, average='weighted'),
                "precision": precision_score(y_test, y_pred, average='weighted'),
                "recall": recall_score(y_test, y_pred, average='weighted')
            }
        else:
            mean_score = -cv_scores.mean()  # 转换为正值

            # 计算其他指标
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            return {
                "rmse": np.sqrt(mean_score),
                "mse": mean_score,
                "mae": mean_absolute_error(y_test, y_pred),
                "r2": r2_score(y_test, y_pred)
            }


class PolynomialFeaturesMethod(ComparisonMethod):
    """多项式特征方法"""

    def __init__(self):
        super().__init__("Polynomial Features")

    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        start_time = time.time()

        # 预处理
        prep_start = time.time()
        X_processed = self._preprocess_data(X)
        self.preprocessing_time = time.time() - prep_start

        # 特征生成
        feature_start = time.time()
        X_poly = self._generate_polynomial_features(X_processed)
        self.feature_generation_time = time.time() - feature_start

        # 训练和评估
        train_start = time.time()
        metrics = self._train_and_evaluate(X_poly, y, task_type)
        self.training_time = time.time() - train_start

        self.execution_time = time.time() - start_time
        self.evaluation_time = self.execution_time - self.preprocessing_time - self.training_time - self.feature_generation_time

        return metrics

    def _preprocess_data(self, X: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        X_processed = X.copy()

        # 只选择数值型特征
        numeric_columns = X_processed.select_dtypes(include=[np.number]).columns
        X_processed = X_processed[numeric_columns]

        # 处理缺失值
        X_processed = X_processed.fillna(X_processed.median())

        # 标准化
        scaler = StandardScaler()
        X_processed = pd.DataFrame(scaler.fit_transform(X_processed), columns=X_processed.columns)

        return X_processed

    def _generate_polynomial_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """生成多项式特征"""
        # 限制特征数量，避免维度爆炸
        if X.shape[1] > 10:
            # 选择最重要的5个特征
            selector = SelectKBest(f_classif, k=5)
            X_selected = selector.fit_transform(X, np.zeros(X.shape[0]))  # 这里需要真实标签，临时用零
            X = pd.DataFrame(X_selected, columns=[f"feature_{i}" for i in range(X_selected.shape[1])])

        poly = PolynomialFeatures(degree=2, include_bias=False)
        X_poly = poly.fit_transform(X)

        # 获取特征名称
        feature_names = poly.get_feature_names_out(X.columns)
        X_poly_df = pd.DataFrame(X_poly, columns=feature_names)

        return X_poly_df

    def _train_and_evaluate(self, X: pd.DataFrame, y: pd.Series, task_type: str) -> Dict[str, float]:
        """训练模型和评估"""
        baseline = BaselineMethod()
        return baseline._train_and_evaluate(X, y, task_type)


class FeatureSelectionMethod(ComparisonMethod):
    """特征选择方法"""

    def __init__(self):
        super().__init__("Feature Selection + RF")

    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        start_time = time.time()

        # 预处理
        prep_start = time.time()
        X_processed = self._preprocess_data(X)
        self.preprocessing_time = time.time() - prep_start

        # 特征选择
        feature_start = time.time()
        X_selected = self._select_features(X_processed, y, task_type)
        self.feature_generation_time = time.time() - feature_start

        # 训练和评估
        train_start = time.time()
        metrics = self._train_and_evaluate(X_selected, y, task_type)
        self.training_time = time.time() - train_start

        self.execution_time = time.time() - start_time
        self.evaluation_time = self.execution_time - self.preprocessing_time - self.training_time - self.feature_generation_time

        return metrics

    def _preprocess_data(self, X: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        X_processed = X.copy()

        # 处理缺失值
        numeric_columns = X_processed.select_dtypes(include=[np.number]).columns
        X_processed[numeric_columns] = X_processed[numeric_columns].fillna(X_processed[numeric_columns].median())

        categorical_columns = X_processed.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            X_processed[col] = X_processed[col].fillna(X_processed[col].mode()[0] if not X_processed[col].mode().empty else 'unknown')
            le = LabelEncoder()
            X_processed[col] = le.fit_transform(X_processed[col].astype(str))

        return X_processed

    def _select_features(self, X: pd.DataFrame, y: pd.Series, task_type: str) -> pd.DataFrame:
        """特征选择"""
        if task_type == "classify":
            selector = SelectKBest(f_classif, k=min(10, X.shape[1]))
        else:
            selector = SelectKBest(f_regression, k=min(10, X.shape[1]))

        X_selected = selector.fit_transform(X, y)
        selected_features = X.columns[selector.get_support()]

        return pd.DataFrame(X_selected, columns=selected_features)

    def _train_and_evaluate(self, X: pd.DataFrame, y: pd.Series, task_type: str) -> Dict[str, float]:
        """训练模型和评估"""
        baseline = BaselineMethod()
        return baseline._train_and_evaluate(X, y, task_type)


class XGBoostMethod(ComparisonMethod):
    """XGBoost方法"""

    def __init__(self):
        super().__init__("XGBoost")
        self.available = XGB_AVAILABLE

    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        if not self.available:
            return {"error": "XGBoost not available"}

        start_time = time.time()

        # 预处理
        prep_start = time.time()
        X_processed = self._preprocess_data(X)
        self.preprocessing_time = time.time() - prep_start

        # 特征生成（XGBoost主要靠模型能力，不做额外特征工程）
        self.feature_generation_time = 0.0

        # 训练和评估
        train_start = time.time()
        metrics = self._train_and_evaluate(X_processed, y, task_type)
        self.training_time = time.time() - train_start

        self.execution_time = time.time() - start_time
        self.evaluation_time = self.execution_time - self.preprocessing_time - self.training_time

        return metrics

    def _preprocess_data(self, X: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        X_processed = X.copy()

        # 处理缺失值（XGBoost可以处理缺失值，但这里还是简单处理）
        numeric_columns = X_processed.select_dtypes(include=[np.number]).columns
        X_processed[numeric_columns] = X_processed[numeric_columns].fillna(X_processed[numeric_columns].median())

        categorical_columns = X_processed.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            X_processed[col] = X_processed[col].fillna(X_processed[col].mode()[0] if not X_processed[col].mode().empty else 'unknown')
            le = LabelEncoder()
            X_processed[col] = le.fit_transform(X_processed[col].astype(str))

        return X_processed

    def _train_and_evaluate(self, X: pd.DataFrame, y: pd.Series, task_type: str) -> Dict[str, float]:
        """训练XGBoost模型和评估"""
        if task_type == "classify":
            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                eval_metric='logloss'
            )
            scoring = 'roc_auc'
        else:
            model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                eval_metric='rmse'
            )
            scoring = 'neg_mean_squared_error'

        # 交叉验证评估
        cv_scores = cross_val_score(model, X, y, cv=5, scoring=scoring)

        if task_type == "classify":
            mean_score = cv_scores.mean()

            # 计算其他指标
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1] if len(model.classes_) == 2 else y_pred

            return {
                "auc": mean_score,
                "accuracy": accuracy_score(y_test, y_pred),
                "f1": f1_score(y_test, y_pred, average='weighted'),
                "precision": precision_score(y_test, y_pred, average='weighted'),
                "recall": recall_score(y_test, y_pred, average='weighted')
            }
        else:
            mean_score = -cv_scores.mean()

            # 计算其他指标
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            return {
                "rmse": np.sqrt(mean_score),
                "mse": mean_score,
                "mae": mean_absolute_error(y_test, y_pred),
                "r2": r2_score(y_test, y_pred)
            }


class AutoMLMethod(ComparisonMethod):
    """AutoML方法"""

    def __init__(self):
        super().__init__("AutoML (Auto-sklearn)")
        self.available = AUTOSKLEARN_AVAILABLE

    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify", time_limit: int = 300) -> Dict[str, float]:
        if not self.available:
            return {"error": "Auto-sklearn not available"}

        start_time = time.time()

        # 预处理
        prep_start = time.time()
        X_processed = self._preprocess_data(X)
        y_processed = self._preprocess_target(y)
        self.preprocessing_time = time.time() - prep_start

        # AutoML训练（包含特征生成和模型训练）
        automl_start = time.time()
        metrics = self._train_automl(X_processed, y_processed, task_type, time_limit)
        self.feature_generation_time = time.time() - automl_start  # AutoML包含特征工程
        self.training_time = 0.0  # AutoML统一处理

        self.execution_time = time.time() - start_time
        self.evaluation_time = self.execution_time - self.preprocessing_time - self.feature_generation_time

        return metrics

    def _preprocess_data(self, X: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        X_processed = X.copy()

        # 处理缺失值
        numeric_columns = X_processed.select_dtypes(include=[np.number]).columns
        X_processed[numeric_columns] = X_processed[numeric_columns].fillna(X_processed[numeric_columns].median())

        categorical_columns = X_processed.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            X_processed[col] = X_processed[col].fillna(X_processed[col].mode()[0] if not X_processed[col].mode().empty else 'unknown')
            le = LabelEncoder()
            X_processed[col] = le.fit_transform(X_processed[col].astype(str))

        return X_processed

    def _preprocess_target(self, y: pd.Series):
        """预处理目标变量"""
        if y.dtype == 'object':
            le = LabelEncoder()
            return le.fit_transform(y)
        return y

    def _train_automl(self, X: pd.DataFrame, y, task_type: str, time_limit: int) -> Dict[str, float]:
        """训练AutoML模型"""
        if task_type == "classify":
            automl = AutoSklearnClassifier(
                time_left_for_this_task=time_limit,
                per_run_time_limit=30,
                ensemble_size=50,
                random_state=42
            )
        else:
            automl = AutoSklearnRegressor(
                time_left_for_this_task=time_limit,
                per_run_time_limit=30,
                ensemble_size=50,
                random_state=42
            )

        # 分割数据用于最终评估
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # 训练AutoML
        automl.fit(X_train, y_train)

        # 预测和评估
        y_pred = automl.predict(X_test)

        if task_type == "classify":
            y_prob = automl.predict_proba(X_test)[:, 1] if len(automl.classes_) == 2 else y_pred

            return {
                "auc": roc_auc_score(y_test, y_prob),
                "accuracy": accuracy_score(y_test, y_pred),
                "f1": f1_score(y_test, y_pred, average='weighted'),
                "precision": precision_score(y_test, y_pred, average='weighted'),
                "recall": recall_score(y_test, y_pred, average='weighted')
            }
        else:
            return {
                "rmse": np.sqrt(mean_squared_error(y_test, y_pred)),
                "mse": mean_squared_error(y_test, y_pred),
                "mae": mean_absolute_error(y_test, y_pred),
                "r2": r2_score(y_test, y_pred)
            }


class ComparisonEngine:
    """对比方法引擎"""

    def __init__(self):
        self.methods = {
            "Baseline": BaselineMethod(),
            "PolynomialFeatures": PolynomialFeaturesMethod(),
            "FeatureSelection": FeatureSelectionMethod(),
            "XGBoost": XGBoostMethod(),
            "AutoML": AutoMLMethod()
        }

    def run_comparison(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify",
                      methods: List[str] = None, time_limit: int = 300) -> Dict[str, Any]:
        """
        运行方法对比

        Args:
            X: 特征数据
            y: 目标变量
            task_type: 任务类型 ("classify" 或 "regress")
            methods: 要对比的方法列表，None表示使用所有可用方法
            time_limit: AutoML时间限制

        Returns:
            对比结果字典
        """
        if methods is None:
            methods = ["Baseline", "PolynomialFeatures", "FeatureSelection", "XGBoost", "AutoML"]

        results = {
            "methods": [],
            "performance_data": {
                "methods": [],
                "auc": [] if task_type == "classify" else None,
                "accuracy": [] if task_type == "classify" else None,
                "f1": [] if task_type == "classify" else None,
                "precision": [] if task_type == "classify" else None,
                "recall": [] if task_type == "classify" else None,
                "rmse": [] if task_type != "classify" else None,
                "mse": [] if task_type != "classify" else None,
                "mae": [] if task_type != "classify" else None,
                "r2": [] if task_type != "classify" else None
            },
            "time_data": {
                "methods": [],
                "totalTime": [],
                "preprocessingTime": [],
                "featureGenerationTime": [],
                "trainingTime": [],
                "evaluationTime": []
            },
            "detailed_results": {}
        }

        for method_name in methods:
            if method_name not in self.methods:
                print(f"Warning: Method {method_name} not available")
                continue

            method = self.methods[method_name]

            # 检查方法是否可用
            if hasattr(method, 'available') and not method.available:
                print(f"Warning: Method {method_name} not available (missing dependencies)")
                continue

            print(f"Running comparison for method: {method_name}")

            try:
                # 运行方法
                if method_name == "AutoML":
                    metrics = method.fit_predict(X, y, task_type, time_limit)
                else:
                    metrics = method.fit_predict(X, y, task_type)

                if "error" in metrics:
                    print(f"Method {method_name} failed: {metrics['error']}")
                    continue

                # 记录结果
                results["methods"].append(method_name)
                results["performance_data"]["methods"].append(method_name)
                results["time_data"]["methods"].append(method_name)

                # 记录性能指标
                if task_type == "classify":
                    for metric in ["auc", "accuracy", "f1", "precision", "recall"]:
                        if metric in metrics:
                            results["performance_data"][metric].append(metrics[metric])
                        else:
                            results["performance_data"][metric].append(0.0)
                else:
                    for metric in ["rmse", "mse", "mae", "r2"]:
                        if metric in metrics:
                            results["performance_data"][metric].append(metrics[metric])
                        else:
                            results["performance_data"][metric].append(0.0)

                # 记录时间数据
                time_breakdown = method.get_time_breakdown()
                for time_metric in ["totalTime", "preprocessingTime", "featureGenerationTime", "trainingTime", "evaluationTime"]:
                    results["time_data"][time_metric].append(time_breakdown.get(time_metric.lower(), 0.0))

                # 记录详细结果
                results["detailed_results"][method_name] = {
                    "metrics": metrics,
                    "time_breakdown": time_breakdown
                }

            except Exception as e:
                print(f"Method {method_name} failed with exception: {e}")
                continue

        return results

    def get_available_methods(self) -> List[str]:
        """获取所有可用的方法"""
        available = []
        for name, method in self.methods.items():
            if hasattr(method, 'available') and not method.available:
                continue
            available.append(name)
        return available


# 便利函数
def run_comparison_from_csv(csv_path: str, target_column: str, task_type: str = "classify",
                          methods: List[str] = None, time_limit: int = 300) -> Dict[str, Any]:
    """
    从CSV文件运行对比

    Args:
        csv_path: CSV文件路径
        target_column: 目标列名
        task_type: 任务类型
        methods: 要对比的方法列表
        time_limit: AutoML时间限制

    Returns:
        对比结果
    """
    # 读取数据
    df = pd.read_csv(csv_path)

    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in CSV")

    # 分离特征和目标
    X = df.drop(columns=[target_column])
    y = df[target_column]

    # 运行对比
    engine = ComparisonEngine()
    return engine.run_comparison(X, y, task_type, methods, time_limit)


if __name__ == "__main__":
    # 测试代码
    print("Comparison Methods Module")
    print("Available methods:", ComparisonEngine().get_available_methods())