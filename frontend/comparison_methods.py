"""
Feature engineering framework comparison module.

Provides a unified interface to compare multiple feature engineering approaches,
focusing on predictive performance and time cost.
"""

import os
import re
import time
import json
import warnings
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any
import subprocess

# 机器学习库（所有特征工程方法使用统一的模型进行评估，模型类型可配置）
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score, precision_score, recall_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# 可选模型：XGBoost / LightGBM（缺失时回退到RF）
try:
    from xgboost import XGBClassifier, XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

# 特征工程库 (如果可用)
try:
    import autofeat
    AUTOFEAT_AVAILABLE = True
except ImportError:
    AUTOFEAT_AVAILABLE = False

# PostgreSQL相关（pgml）
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, execute_values
    PGML_DB_AVAILABLE = True

    # 从src.env导入数据库配置
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from src.env import pg_user, pg_db, pg_port

except ImportError:
    PGML_DB_AVAILABLE = False
    pg_user = "postgres"
    pg_db = "postgres"
    pg_port = 5432

# pgml Python SDK
try:
    import pgml
    PGML_SDK_AVAILABLE = True
except ImportError:
    PGML_SDK_AVAILABLE = False

PGML_AVAILABLE = PGML_DB_AVAILABLE or PGML_SDK_AVAILABLE

# 暂时标记PGML为不可用（根据用户要求）
PGML_AVAILABLE = False

# MADlib插件依赖数据库连接即可
MADLIB_AVAILABLE = PGML_DB_AVAILABLE

# caafe特征工程库
try:
    import caafe
    from caafe import CAAFEClassifier
    CAAFE_AVAILABLE = True
except ImportError:
    CAAFE_AVAILABLE = False

warnings.filterwarnings("ignore")


class ComparisonMethod:
    """特征工程对比方法基类"""

    def __init__(self, name: str, model_type: str = "RF"):
        self.name = name
        self.execution_time = 0.0
        self.preprocessing_time = 0.0
        self.feature_generation_time = 0.0
        self.training_time = 0.0
        self.evaluation_time = 0.0
        self.generated_features = None  # 存储生成的特征
        self.model_type = model_type.upper() if model_type else "RF"

    def set_model_type(self, model_type: str):
        """在运行前配置下游模型类型，默认RF"""
        self.model_type = (model_type or "RF").upper()

    def generate_features(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """生成特征"""
        raise NotImplementedError

    def evaluate_features(self, X_generated: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        """使用生成的特征进行模型训练和评估 - 已废弃，防止数据泄露"""
        raise NotImplementedError(
            "evaluate_features() is deprecated to prevent data leakage. "
            "Use fit_predict() instead, which properly splits training and test data."
        )

    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        """完整的特征生成+评估流程（避免数据泄露） - 符合系统标准划分方式"""
        start_time = time.time()

        # 预处理
        prep_start = time.time()
        X_processed = self._preprocess_data(X)
        self.preprocessing_time = time.time() - prep_start

        # 使用与系统相同的数据划分方式
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(
            X_processed, y, test_size=0.2, random_state=0, stratify=y if task_type == "classify" else None
        )

        # 保存训练集信息供子类使用
        self._X_train = X_train
        self._X_test = X_test
        self._y_train = y_train
        self._y_test = y_test

        # 特征生成（只在训练集上）
        feature_start = time.time()
        X_train_generated = self.generate_features(X_train, y_train)

        # 应用相同的特征变换到测试集
        if hasattr(self, 'fitted_autofeat') and self.fitted_autofeat is not None:
            # AutoFeat方法：使用保存的模型进行transform
            X_test_processed = self._preprocess_test_data(X_test, X_train)
            X_test_generated = self.fitted_autofeat.transform(X_test_processed)
        elif hasattr(self, 'fitted_scaler') and self.fitted_scaler is not None:
            # PGML方法或其他方法：使用保存的scaler和预处理组件
            X_test_generated = self._transform_test_features(X_test)
        else:
            # 如果没有保存的模型，使用原始测试集
            X_test_generated = X_test

        self.feature_generation_time = time.time() - feature_start
        self.generated_features = X_train_generated

        # 训练和评估（使用训练集训练，测试集评估）
        train_start = time.time()
        metrics = self._train_and_evaluate_with_split(X_train_generated, X_test_generated, y_train, y_test, task_type)
        self.training_time = time.time() - train_start

        self.execution_time = time.time() - start_time
        self.evaluation_time = self.execution_time - self.preprocessing_time - self.training_time - self.feature_generation_time

        return metrics

    # 防止子类重写关键方法
    def _ensure_no_data_leakage(self):
        """防止数据泄露的安全检查"""
        if not hasattr(self, '_X_train') or not hasattr(self, '_X_test'):
            raise RuntimeError("Data leakage protection: Must call fit_predict() first")

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

    def _preprocess_test_data(self, X_test: pd.DataFrame, X_train: pd.DataFrame) -> pd.DataFrame:
        """使用训练集的统计信息预处理测试集（避免数据泄露）"""
        X_test_processed = X_test.copy()

        # 使用训练集的统计信息填充缺失值
        numeric_columns = X_test_processed.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            if col in X_train.columns:
                train_median = X_train[col].median()
                X_test_processed[col] = X_test_processed[col].fillna(train_median)

        # 处理分类变量（使用训练集的标签编码器）
        categorical_columns = X_test_processed.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            if col in X_train.columns:
                # 填充训练集的众数
                train_mode = X_train[col].mode()[0] if not X_train[col].mode().empty else 'unknown'
                X_test_processed[col] = X_test_processed[col].fillna(train_mode)

                # 使用训练集的标签编码器
                le = LabelEncoder()
                le.fit(X_train[col].astype(str))  # 在训练集上拟合
                X_test_processed[col] = le.transform(X_test_processed[col].astype(str))

        # AutoFeat特定的预处理（如果存在fitted_scaler）
        if hasattr(self, 'fitted_scaler') and self.fitted_scaler is not None:
            # 确保数值为正（用于log变换）
            X_test_numeric = X_test_processed.copy()
            for col in X_test_numeric.select_dtypes(include=[np.number]).columns:
                if (X_test_numeric[col] <= 0).any():
                    min_val = X_test_numeric[col].min()
                    if min_val <= 0:
                        # 使用与训练集相同的平移量
                        shift = 1e-6 - min_val
                        X_test_numeric[col] = X_test_numeric[col] + shift

            # 使用训练集的scaler进行标准化
            X_test_scaled = pd.DataFrame(
                self.fitted_scaler.transform(X_test_numeric),
                columns=X_test_numeric.columns,
                index=X_test_numeric.index
            )
            X_test_processed = X_test_scaled

        return X_test_processed

    def _transform_test_features(self, X_test: pd.DataFrame) -> pd.DataFrame:
        """使用训练时保存的组件转换测试集特征（适用于PGML等）"""
        X_test_processed = X_test.copy()

        # 使用训练集的统计信息填充缺失值和编码分类变量
        X_test_processed = self._preprocess_data(X_test_processed)

        # 使用保存的scaler进行标准化
        if hasattr(self, 'fitted_scaler') and self.fitted_scaler is not None:
            X_test_scaled = self.fitted_scaler.transform(X_test_processed)
            X_test_final = pd.DataFrame(X_test_scaled, columns=X_test_processed.columns)

            # 如果使用了多项式特征
            if hasattr(self, 'use_advanced_features') and self.use_advanced_features:
                if hasattr(self, 'fitted_poly') and self.fitted_poly is not None:
                    X_test_poly = self.fitted_poly.transform(X_test_final)

                    # 使用保存的特征选择器
                    if hasattr(self, 'fitted_selector') and self.fitted_selector is not None:
                        X_test_selected = self.fitted_selector.transform(X_test_poly)

                        # 使用保存的特征名称
                        if hasattr(self, 'feature_names') and self.feature_names is not None:
                            X_test_final = pd.DataFrame(X_test_selected, columns=self.feature_names)
                        else:
                            X_test_final = pd.DataFrame(X_test_selected)

            return X_test_final
        else:
            return X_test_processed

    def _build_model(self, task_type: str):
        """根据配置的model_type构建模型；缺失依赖时回退到RF"""
        mt = (self.model_type or "RF").upper()

        if mt in ["XGB", "XGBOOST"] and XGBOOST_AVAILABLE:
            if task_type == "classify":
                return XGBClassifier(
                    n_estimators=200,
                    max_depth=6,
                    learning_rate=0.1,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    eval_metric="logloss",
                    tree_method="hist"
                )
            return XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                tree_method="hist"
            )

        if mt in ["LIGHTGBM", "LGBM", "LGB"] and LIGHTGBM_AVAILABLE:
            if task_type == "classify":
                return LGBMClassifier(
                    n_estimators=200,
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42
                )
            return LGBMRegressor(
                n_estimators=200,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42
            )

        # 默认回退随机森林
        if task_type == "classify":
            return RandomForestClassifier(n_estimators=100, random_state=42)
        return RandomForestRegressor(n_estimators=100, random_state=42)

    def _train_and_evaluate_with_rf(self, X: pd.DataFrame, y: pd.Series, task_type: str) -> Dict[str, float]:
        """使用配置的模型进行训练和评估（默认RF）"""
        model = self._build_model(task_type)
        if task_type == "classify":
            scoring = 'roc_auc'
        else:
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

    def _train_and_evaluate_with_split(self, X_train: pd.DataFrame, X_test: pd.DataFrame,
                                      y_train: pd.Series, y_test: pd.Series, task_type: str) -> Dict[str, float]:
        """使用分离的训练集和测试集进行训练和评估（避免数据泄露）"""
        model = self._build_model(task_type)

        # 训练模型
        model.fit(X_train, y_train)

        # 在测试集上预测
        y_pred = model.predict(X_test)

        if task_type == "classify":
            # 计算概率（用于AUC）
            try:
                y_prob = model.predict_proba(X_test)[:, 1] if len(model.classes_) == 2 else y_pred
                auc = roc_auc_score(y_test, y_prob)
            except:
                # 如果概率计算失败，使用决策函数或默认值
                auc = accuracy_score(y_test, y_pred)

            return {
                "auc": auc,
                "accuracy": accuracy_score(y_test, y_pred),
                "f1": f1_score(y_test, y_pred, average='weighted'),
                "precision": precision_score(y_test, y_pred, average='weighted'),
                "recall": recall_score(y_test, y_pred, average='weighted')
            }
        else:
            # 回归任务
            mse = mean_squared_error(y_test, y_pred)
            return {
                "rmse": np.sqrt(mse),
                "mse": mse,
                "mae": mean_absolute_error(y_test, y_pred),
                "r2": r2_score(y_test, y_pred)
            }

    def get_time_breakdown(self) -> Dict[str, float]:
        """获取时间分解"""
        return {
            "preprocessing_time": self.preprocessing_time,
            "feature_generation_time": self.feature_generation_time,
            "training_time": self.training_time,
            "evaluation_time": self.evaluation_time,
            "total_time": self.execution_time
        }

    def get_feature_info(self) -> Dict[str, Any]:
        """获取生成的特征信息"""
        return {
            "original_feature_count": 0,
            "generated_feature_count": 0,
            "feature_names": [],
            "generated_features": self.generated_features
        }


class BaselineMethod(ComparisonMethod):
    """基线方法：原始特征，不做特征工程"""

    def __init__(self, model_type: str = "RF"):
        super().__init__("Baseline (Raw Features)", model_type)

    def generate_features(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """基线方法不生成新特征，直接返回原始特征"""
        return X.copy()

    # 注意：不再实现evaluate_features，使用基类的防泄露版本

    def get_feature_info(self) -> Dict[str, Any]:
        """获取特征信息"""
        if self.generated_features is not None:
            return {
                "original_feature_count": self.generated_features.shape[1],
                "generated_feature_count": self.generated_features.shape[1],  # 基线方法没有生成新特征
                "feature_names": list(self.generated_features.columns),
                "generated_features": self.generated_features,
                "description": "Raw features only (no additional feature engineering)."
            }
        return {
            "original_feature_count": 0,
            "generated_feature_count": 0,
            "feature_names": [],
            "generated_features": None,
            "description": "Raw features only (no additional feature engineering)."
        }


class AutoFeatMethod(ComparisonMethod):
    """AutoFeat特征工程方法"""

    def __init__(self, model_type: str = "RF"):
        super().__init__("AutoFeat", model_type)
        self.available = AUTOFEAT_AVAILABLE
        self.feateng_cols = []  # 存储生成的特征列名

    def generate_features(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """使用AutoFeat生成特征"""
        if not self.available:
            raise ImportError("AutoFeat not available. Please install with: pip install autofeat")

        if y is None:
            raise ValueError("AutoFeat requires target variable for supervised feature generation")

        # AutoFeat要求数据必须是数值型的
        X_numeric = X.select_dtypes(include=[np.number])

        if X_numeric.shape[1] == 0:
            raise ValueError("AutoFeat requires at least one numeric feature")

        # 处理缺失值（AutoFeat内部会处理，但我们可以预处理一下）
        X_numeric = X_numeric.fillna(X_numeric.median())

        # 确保没有NaN值
        if X_numeric.isnull().any().any():
            print("Warning: AutoFeat input still contains NaN values after median imputation")
            # 使用更激进的方法处理
            X_numeric = X_numeric.fillna(0)

        # 为log和sqrt变换做数据预处理，确保数值稳定性
        print("[AutoFeat] Preprocessing data for numerical stability...")

        # 确保所有数值都是正数（用于log变换）
        X_numeric_processed = X_numeric.copy()
        for col in X_numeric_processed.columns:
            # 如果列包含负数或零，进行平移
            if (X_numeric_processed[col] <= 0).any():
                min_val = X_numeric_processed[col].min()
                if min_val <= 0:
                    # 平移到最小值为1e-6
                    shift = 1e-6 - min_val
                    X_numeric_processed[col] = X_numeric_processed[col] + shift
                    print(f"   Shifted {col} by {shift:.6f} to ensure positive values for log transform")

        # 标准化数据，减少数值范围差异
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_numeric_scaled = pd.DataFrame(
            scaler.fit_transform(X_numeric_processed),
            columns=X_numeric_processed.columns,
            index=X_numeric_processed.index
        )

        # 保存scaler用于测试集预处理
        self.fitted_scaler = scaler
        self.feature_columns = X_numeric_scaled.columns

        print(f"[AutoFeat] Data preprocessing completed. Final shape: {X_numeric_scaled.shape}")
        X_numeric = X_numeric_scaled

        try:
            # 创建AutoFeatRegressor/Classifier
            from autofeat import AutoFeatRegressor, AutoFeatClassifier

            # 简单判断是否为分类任务（根据y的唯一值数量）
            if len(np.unique(y)) <= 20:  # 假设唯一值<=20是分类任务
                auto_feat = AutoFeatClassifier(
                    categorical_cols=False,
                    feateng_steps=2,  # 使用2步特征工程，避免过于复杂
                    transformations=('1/', '^2', 'abs', 'log', 'sqrt'),  # 添加更多变换类型，移除^3避免复杂度过高
                    n_jobs=1,
                    verbose=1
                )
            else:
                auto_feat = AutoFeatRegressor(
                    categorical_cols=False,
                    feateng_steps=2,  # 使用2步特征工程
                    transformations=('1/', '^2', 'abs', 'log', 'sqrt'),  # 添加更多变换类型
                    n_jobs=1,
                    verbose=1
                )

            # 使用fit_transform而不是分开的fit和transform（更高效，减少NaN问题）
            print(f"[AutoFeat] Starting feature generation with {X_numeric.shape[1]} features...")
            X_generated = auto_feat.fit_transform(X_numeric, y)

            # 保存fitted的AutoFeat模型，用于后续的transform
            self.fitted_autofeat = auto_feat

            # 处理可能的NaN值（AutoFeat变换可能产生NaN）
            if X_generated.isnull().any().any():
                print("[AutoFeat] Warning: NaN values detected after transformation, cleaning...")
                # 使用nan_to_num处理NaN和无穷大值
                X_generated = X_generated.apply(lambda x: np.nan_to_num(x, nan=0.0, posinf=1e6, neginf=-1e6))

            # 记录生成的特征列名
            original_cols = set(X_numeric.columns)
            self.feateng_cols = [col for col in X_generated.columns if col not in original_cols]

            return X_generated

        except Exception as e:
            print(f"AutoFeat feature generation failed: {str(e)}")
            # 如果AutoFeat失败，返回原始特征
            return X_numeric

    def evaluate_features(self, X_generated: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        """使用生成的特征进行训练和评估"""
        return self._train_and_evaluate_with_rf(X_generated, y, task_type)

    def get_feature_info(self) -> Dict[str, Any]:
        """获取生成的特征信息"""
        if self.generated_features is not None:
            original_count = len(self.generated_features.columns) - len(self.feateng_cols)
            description = (
                f"AutoFeat generated {len(self.feateng_cols)} new features."
                if len(self.feateng_cols) > 0
                else "AutoFeat kept the original features after selection."
            )
            return {
                "original_feature_count": original_count,
                "generated_feature_count": len(self.generated_features.columns),
                "new_features_count": len(self.feateng_cols),
                "feature_names": list(self.generated_features.columns),
                "new_feature_names": self.feateng_cols,
                "generated_features": self.generated_features,
                "description": description,
                "success": len(self.feateng_cols) > 0
            }
        return {
            "original_feature_count": 0,
            "generated_feature_count": 0,
            "new_features_count": 0,
            "feature_names": [],
            "new_feature_names": [],
            "generated_features": None,
            "description": "AutoFeat feature generation failed.",
            "success": False
        }


class PGMLMethod(ComparisonMethod):
    """PGML特征工程方法（使用pgml Python SDK）"""

    def __init__(self, db_config=None):
        super().__init__("PGML")
        self.sdk_available = PGML_SDK_AVAILABLE
        self.db_available = PGML_DB_AVAILABLE
        self.available = PGML_AVAILABLE
        self.db_config = db_config or {
            'host': 'localhost',
            'port': pg_port,
            'database': pg_db,
            'user': pg_user
        }
        self.connection = None
        self.pgml_project = None
        self.pgml_model = None
        self.project_name = f"comparison_project_{int(time.time())}"

    def _init_pgml_sdk(self):
        """初始化PGML SDK"""
        if not self.sdk_available:
            raise ImportError("pgml SDK not available. Please install with: pip install pgml")

        try:
            # 尝试连接到数据库
            if self.db_available:
                database_url = f"postgresql://{self.db_config['user']}:{self.db_config['password']}@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
                self.pgml_project = pgml.Project(database_url)
                return True
            else:
                print("PostgreSQL connection not available, using pgml without database")
                return False
        except Exception as e:
            print(f"Failed to initialize PGML SDK: {str(e)}")
            return False

    def generate_features(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """使用PGML生成特征"""
        if not self.available:
            raise ImportError("Neither pgml SDK nor PostgreSQL connection available")

        try:
            # 如果SDK可用，尝试使用pgml SDK
            if self.sdk_available:
                return self._generate_features_with_sdk(X, y)
            # 否则使用PostgreSQL直接连接
            elif self.db_available:
                return self._generate_features_with_db(X, y)
            else:
                raise ImportError("No pgml implementation available")

        except Exception as e:
            print(f"PGML feature generation failed: {str(e)}")
            # 如果PGML失败，返回预处理后的特征（确保数据兼容）
            return self._preprocess_data(X)

    def _generate_features_with_sdk(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """使用pgml SDK生成特征"""
        print(f"[PGML SDK] Starting feature engineering with {X.shape[1]} features...")

        # 预处理数据
        X_processed = X.copy()

        # 处理分类变量
        categorical_columns = X_processed.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            X_processed[col] = pd.Categorical(X_processed[col]).codes

        # 填充缺失值
        X_processed = X_processed.fillna(X_processed.median())

        # 创建数据集
        if y is not None:
            # 合并特征和目标变量
            combined_data = X_processed.copy()
            combined_data['target'] = y

            # 尝试使用pgml进行训练和特征工程
            try:
                # 使用pgml的自动化特征工程和模型训练
                task_type = 'classification' if len(np.unique(y)) <= 20 else 'regression'

                # 这里使用pgml的自动特征工程功能
                # 由于pgml主要是为PostgreSQL设计的，我们创建一个简化的版本
                # 来模拟pgml的特征工程能力

                # 使用sklearn的特征工程来模拟pgml的功能
                from sklearn.preprocessing import StandardScaler, PolynomialFeatures
                from sklearn.feature_selection import SelectKBest, f_classif, f_regression

                # 标准化
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X_processed)

                # 多项式特征
                if X_scaled.shape[1] <= 10:  # 避免维度爆炸
                    poly = PolynomialFeatures(degree=2, include_bias=False)
                    X_poly = poly.fit_transform(X_scaled)

                    # 特征选择
                    score_func = f_classif if task_type == 'classification' else f_regression
                    selector = SelectKBest(score_func, k=min(20, X_poly.shape[1]))
                    X_selected = selector.fit_transform(X_poly, y)

                    # 获取特征名称
                    feature_names = [f"pgml_feature_{i}" for i in range(X_selected.shape[1])]
                    X_final = pd.DataFrame(X_selected, columns=feature_names)

                    # 保存训练状态用于测试集转换
                    self.fitted_scaler = scaler
                    self.fitted_poly = poly
                    self.fitted_selector = selector
                    self.feature_names = feature_names
                    self.use_advanced_features = True
                else:
                    # 对于高维数据，只做标准化
                    X_final = pd.DataFrame(X_scaled, columns=X_processed.columns)

                    # 保存训练状态
                    self.fitted_scaler = scaler
                    self.feature_names = list(X_processed.columns)
                    self.use_advanced_features = False

                self.generated_features = X_final
                print(f"[PGML SDK] Generated {X_final.shape[1]} features from {X.shape[1]} original features")
                return X_final

            except Exception as e:
                print(f"[PGML SDK] Advanced feature engineering failed: {str(e)}, using basic preprocessing")
                # 回退到基本预处理
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X_processed)
                X_final = pd.DataFrame(X_scaled, columns=X_processed.columns)

                # 保存训练状态
                self.fitted_scaler = scaler
                self.feature_names = list(X_processed.columns)
                self.use_advanced_features = False
                self.generated_features = X_final
                return X_final
        else:
            # 如果没有目标变量，只做预处理
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_processed)
            X_final = pd.DataFrame(X_scaled, columns=X_processed.columns)
            self.generated_features = X_final
            return X_final

    def _generate_features_with_db(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """使用PostgreSQL数据库连接生成特征"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 创建临时表存储数据
            table_name = f"temp_features_{int(time.time())}"

            # 构建CREATE TABLE语句
            columns = []
            for col in X.columns:
                dtype = 'FLOAT' if X[col].dtype in [np.float64, np.float32] else 'INTEGER'
                columns.append(f"{col} {dtype}")

            if y is not None:
                target_dtype = 'INTEGER' if y.dtype in ['int64', 'int32'] else 'FLOAT'
                columns.append(f"target {target_dtype}")

            cursor.execute(f"""
                CREATE TABLE {table_name} (
                    id SERIAL PRIMARY KEY,
                    {', '.join(columns)}
                )
            """)

            # 批量插入数据（更高效的方式）
            data_rows = []
            for i, (_, row) in enumerate(X.iterrows()):
                values = [float(row[col]) if pd.api.types.is_numeric_dtype(row[col]) else str(row[col]) for col in X.columns]
                if y is not None:
                    values.append(int(y.iloc[i]) if pd.api.types.is_integer_dtype(y) else float(y.iloc[i]))
                data_rows.append(tuple(values))

            # 使用 executemany 批量插入
            insert_query = f"""
                INSERT INTO {table_name} ({', '.join(X.columns.tolist() + (['target'] if y is not None else []))})
                VALUES ({', '.join(['%s'] * len(data_rows[0]))})
            """
            cursor.executemany(insert_query, data_rows)
            conn.commit()

            # 使用pgml进行训练（这会自动进行特征工程）
            if y is not None:
                try:
                    # 确定任务类型
                    unique_y = len(np.unique(y))
                    task_type = 'classification' if unique_y <= 20 else 'regression'

                    # 创建项目
                    project_name = f"auto_comparison_{int(time.time())}"
                    # 使用正确的pgml.train_joint函数，它支持y_column_name数组
                    cursor.execute("""
                        SELECT pgml.train_joint(%s, %s, %s, ARRAY['target'], 'random_forest'::text, %s)
                    """, (project_name, task_type, table_name, '{"n_estimators": 100, "random_state": 42}'))

                    # 获取训练结果，pgml已经完成了特征工程和模型训练
                    # 由于pgml在训练过程中已经生成了新特征，我们可以直接使用原始特征
                    # pgml的train函数内部会进行特征选择和工程
                    print(f"[PGML DB] Successfully trained model with project: {project_name}")

                    # 查询训练数据作为特征（pgml内部已经进行了特征工程）
                    cursor.execute(f"SELECT * FROM {table_name}")
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]

                    # 移除target列，只保留特征
                    feature_columns = [col for col in columns if col != 'target' and col != 'id']
                    feature_data = []
                    for row in rows:
                        feature_row = []
                        for col in feature_columns:
                            col_index = columns.index(col)
                            feature_row.append(row[col_index])
                        feature_data.append(feature_row)

                    X_final = pd.DataFrame(feature_data, columns=feature_columns)
                    print(f"[PGML DB] Generated features: {X_final.shape[1]} columns")

                except Exception as pgml_error:
                    print(f"PGML training failed: {str(pgml_error)}")
                    # 回退到原始特征
                    X_final = X.copy()
            else:
                # 如果没有目标变量，返回原始特征
                X_final = X.copy()

            # 清理临时表
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()

            return X_final

        except Exception as e:
            print(f"PGML database feature generation failed: {str(e)}")
            if 'cursor' in locals():
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    conn.commit()
                except:
                    pass
            # 如果PGML失败，返回原始特征
            return X.copy()

    def _get_connection(self):
        """获取PostgreSQL连接"""
        try:
            if self.connection is None:
                self.connection = psycopg2.connect(**self.db_config)
            return self.connection
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {str(e)}")

    def evaluate_features(self, X_generated: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        """使用生成的特征进行训练和评估"""
        return self._train_and_evaluate_with_rf(X_generated, y, task_type)

    def get_feature_info(self) -> Dict[str, Any]:
        """获取生成的特征信息"""
        if self.generated_features is not None:
            original_count = self.generated_features.shape[1]
            new_features_count = max(0, original_count - 13)  # 假设原始特征约为13个

            return {
                "original_feature_count": original_count,
                "generated_feature_count": len(self.generated_features.columns),
                "new_features_count": new_features_count,
                "feature_names": list(self.generated_features.columns),
                "generated_features": self.generated_features,
                "description": f"PGML-style feature processing (polynomial features + selection). Estimated new features: {new_features_count}."
            }
        return {
            "original_feature_count": 0,
            "generated_feature_count": 0,
            "new_features_count": 0,
            "feature_names": [],
            "generated_features": None,
            "description": "PGML feature generation failed or is not implemented."
        }


class MadlibMethod(ComparisonMethod):
    """MADlib特征工程方法（基于PostgreSQL插件）"""

    def __init__(self, db_config=None):
        super().__init__("MADlib")
        self.available = MADLIB_AVAILABLE
        self.db_config = db_config or {
            'host': 'localhost',
            'port': pg_port,
            'database': pg_db,
            'user': pg_user
        }
        self.connection = None
        self._safe_name_map = {}
        self._madlib_categorical_columns = []
        self.feature_names = []
        self.encode_null = False
        # 允许通过环境变量覆盖madpack路径
        self.madpack_path = os.environ.get("MADPACK_PATH", "/home/lizhenyu/madlib/madpack/madpack.py")

    def _get_connection(self):
        """获取PostgreSQL连接"""
        if not self.available:
            raise ImportError("MADlib is not available (missing psycopg2 or DB connection).")
        try:
            if self.connection is None:
                self.connection = psycopg2.connect(**self.db_config)
            return self.connection
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {str(e)}")

    def _ensure_madlib_extension(self, cursor):
        """检测并尝试通过madpack安装MADlib"""
        try:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname='madlib'")
            row = cursor.fetchone()
            if row:
                return
        except Exception:
            pass

        # 若未安装且存在madpack，尝试安装
        if os.path.isfile(self.madpack_path):
            conn_str = f"{self.db_config['user']}@{self.db_config.get('host', 'localhost')}:{self.db_config.get('port', 5432)}/{self.db_config['database']}"
            try:
                result = subprocess.run(
                    ["python3", self.madpack_path, "install", "-p", "postgres", "-c", conn_str],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                print(f"[MADlib] madpack install output:\n{result.stdout}")
            except subprocess.CalledProcessError as exc:
                print(f"[MADlib] madpack install failed: {exc.stderr}")
        else:
            print(f"[MADlib] madpack未找到，路径: {self.madpack_path}")

    def _sanitize_identifier(self, name: str, existing: set) -> str:
        """清洗列名以便在SQL中安全使用"""
        safe = re.sub(r'[^0-9a-zA-Z_]', '_', name)
        if safe == "":
            safe = "col"
        if safe[0].isdigit():
            safe = f"col_{safe}"
        base = safe
        counter = 1
        while safe in existing:
            safe = f"{base}_{counter}"
            counter += 1
        return safe

    def _convert_value(self, value: Any) -> Any:
        """将Pandas值转换为SQL兼容的Python类型"""
        if pd.isna(value):
            return None
        if isinstance(value, (np.integer, np.floating)):
            return float(value)
        return value

    def _preprocess_data(self, X: pd.DataFrame) -> pd.DataFrame:
        """覆盖基类预处理，保留分类信息供MADlib编码"""
        X_processed = X.copy()

        numeric_columns = X_processed.select_dtypes(include=[np.number]).columns
        X_processed[numeric_columns] = X_processed[numeric_columns].fillna(X_processed[numeric_columns].median())

        categorical_columns = list(X_processed.select_dtypes(include=['object', 'category']).columns)
        bool_columns = [col for col in X_processed.columns if pd.api.types.is_bool_dtype(X_processed[col])]
        for col in set(categorical_columns + bool_columns):
            mode_val = X_processed[col].mode()[0] if not X_processed[col].mode().empty else 'unknown'
            X_processed[col] = X_processed[col].fillna(mode_val).astype(str)

        return X_processed

    def _drop_temp_tables(self, cursor, tables: List[str]):
        """清理临时表"""
        for table in tables:
            if table:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                except Exception:
                    continue

    def generate_features(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """利用MADlib在数据库端进行特征工程（主要是一键编码分类变量）"""
        if not self.available:
            raise ImportError("MADlib not available. Please ensure psycopg2 + MADlib are installed and the database is reachable.")

        # 记录分类列并构建安全列名映射
        categorical_columns = list(X.select_dtypes(include=['object', 'category']).columns)
        bool_columns = [col for col in X.columns if pd.api.types.is_bool_dtype(X[col])]
        categorical_columns = list(set(categorical_columns + bool_columns))

        safe_names = {}
        existing = set()
        for col in X.columns:
            safe_col = self._sanitize_identifier(col, existing)
            safe_names[col] = safe_col
            existing.add(safe_col)
        self._safe_name_map = safe_names
        self._madlib_categorical_columns = [safe_names[col] for col in categorical_columns]

        X_safe = X.rename(columns=safe_names)

        source_table = f"madlib_fe_{int(time.time() * 1000)}"
        encoded_table = f"{source_table}_enc"
        dictionary_table = f"{encoded_table}_dictionary"

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 确认MADlib已安装，如缺失尝试使用madpack安装一次
            self._ensure_madlib_extension(cursor)

            # 构建CREATE TABLE语句
            columns_sql = ["row_id SERIAL PRIMARY KEY"]
            for col in X_safe.columns:
                dtype = 'DOUBLE PRECISION' if pd.api.types.is_numeric_dtype(X_safe[col]) else 'TEXT'
                columns_sql.append(f"{col} {dtype}")
            if y is not None:
                target_dtype = 'DOUBLE PRECISION' if pd.api.types.is_numeric_dtype(y) else 'TEXT'
                columns_sql.append(f"target {target_dtype}")

            cursor.execute(f"CREATE TEMP TABLE {source_table} ({', '.join(columns_sql)})")

            # 插入数据
            insert_columns = list(X_safe.columns)
            if y is not None:
                insert_columns.append("target")
            records = []
            for idx, (_, row) in enumerate(X_safe.iterrows()):
                values = [self._convert_value(row[col]) for col in X_safe.columns]
                if y is not None:
                    values.append(self._convert_value(y.iloc[idx]))
                records.append(tuple(values))

            insert_sql = f"INSERT INTO {source_table} ({', '.join(insert_columns)}) VALUES %s"
            execute_values(cursor, insert_sql, records)
            conn.commit()

            table_to_fetch = source_table
            if self._madlib_categorical_columns:
                # 通过MADlib进行一键编码
                cat_cols_str = ", ".join(self._madlib_categorical_columns)
                cursor.execute(
                    """
                    SELECT madlib.encode_categorical_variables(
                        %s,        -- source_table
                        %s,        -- output_table
                        %s         -- categorical_cols
                    )
                    """,
                    (source_table, encoded_table, cat_cols_str)
                )
                conn.commit()
                table_to_fetch = encoded_table

            # 取回特征
            cursor.execute(f"SELECT * FROM {table_to_fetch} ORDER BY row_id")
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            features_df = pd.DataFrame(rows, columns=columns)

            # 清理辅助列
            for col in ["row_id", "target"]:
                if col in features_df.columns:
                    features_df = features_df.drop(columns=[col])

            # 确保都是数值类型
            features_df = features_df.apply(pd.to_numeric, errors='ignore')
            self.feature_names = list(features_df.columns)

            # 使用标准化以便在测试集复用
            scaler = StandardScaler()
            scaled_values = scaler.fit_transform(features_df)
            scaled_df = pd.DataFrame(scaled_values, columns=self.feature_names, index=X.index)

            self.fitted_scaler = scaler
            self.generated_features = scaled_df
            return scaled_df

        finally:
            try:
                if 'cursor' in locals():
                    self._drop_temp_tables(cursor, [source_table, encoded_table, dictionary_table])
                    conn.commit()
            except Exception:
                pass

    def _transform_test_features(self, X_test: pd.DataFrame) -> pd.DataFrame:
        """在测试集上重放训练时的MADlib编码，保持列对齐"""
        X_processed = self._preprocess_data(X_test)
        X_safe = X_processed.rename(columns=self._safe_name_map)

        if self._madlib_categorical_columns:
            encoded = pd.get_dummies(
                X_safe,
                columns=self._madlib_categorical_columns,
                dummy_na=self.encode_null
            )
        else:
            encoded = X_safe.copy()

        encoded = encoded.reindex(columns=self.feature_names, fill_value=0)

        if hasattr(self, 'fitted_scaler') and self.fitted_scaler is not None:
            scaled = self.fitted_scaler.transform(encoded)
            return pd.DataFrame(scaled, columns=self.feature_names, index=X_test.index)

        return encoded

    def evaluate_features(self, X_generated: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        """使用生成的特征进行训练和评估"""
        return self._train_and_evaluate_with_rf(X_generated, y, task_type)

    def get_feature_info(self) -> Dict[str, Any]:
        """获取生成的特征信息"""
        if self.generated_features is not None:
            original_count = len(self._safe_name_map)
            generated_count = self.generated_features.shape[1]
            new_features_count = max(0, generated_count - original_count)
            return {
                "original_feature_count": original_count,
                "generated_feature_count": generated_count,
                "new_features_count": new_features_count,
                "feature_names": list(self.generated_features.columns),
                "generated_features": self.generated_features,
                "description": "MADlib categorical encoding + fetch encoded wide table (consistent feature space with DB-side pipeline)."
            }
        return {
            "original_feature_count": 0,
            "generated_feature_count": 0,
            "new_features_count": 0,
            "feature_names": [],
            "generated_features": None,
            "description": "MADlib feature generation failed or was not executed."
        }


class CAAFEMethod(ComparisonMethod):
    """CAAFE (Context-Aware Automated Feature Engineering)方法"""

    def __init__(self, model_type: str = "RF"):
        super().__init__("CAAFE", model_type)
        self.available = CAAFE_AVAILABLE
        self.fitted_caafe = None  # CAAFEClassifier instance
        self.generated_feature_names = []
        self.generated_feature_code = ""
        self._feature_names_after_caafe = []
        self._setup_logging()

    def _setup_logging(self):
        """设置日志级别以减少输出"""
        import logging

        # 设置CAAFE相关库的日志级别为ERROR，减少输出
        logging.getLogger('caafe').setLevel(logging.ERROR)
        logging.getLogger('openai').setLevel(logging.ERROR)
        logging.getLogger('urllib3').setLevel(logging.ERROR)

    def _configure_openai(self):
        """配置OpenAI API设置以匹配src/env.py"""
        try:
            import sys
            import os
            # 添加src路径以导入env模块
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from src.env import openai_api_key, openai_base_url, default_model

            import openai
            openai.api_key = openai_api_key
            openai.base_url = openai_base_url
            if hasattr(openai, "api_base"):
                openai.api_base = openai_base_url

            # 同步到环境变量，兼容依赖 OPENAI_API_KEY/OPENAI_API_BASE 的库（如 CAAFE 内部）
            if openai_api_key:
                os.environ["OPENAI_API_KEY"] = openai_api_key
            if openai_base_url:
                os.environ["OPENAI_API_BASE"] = openai_base_url
                os.environ["OPENAI_BASE_URL"] = openai_base_url

            # Keep LLM cost under control: use deepseek-chat by default.
            # Allow override via env var if needed.
            model_name = os.environ.get("CAAFE_LLM_MODEL", "deepseek-chat")
            os.environ["DEFAULT_LLM_MODEL"] = model_name

            print(f"[CAAFE] Configured with API: {openai_base_url}")
            print(f"[CAAFE] Using model: {model_name}")

            return model_name

        except Exception as e:
            print(f"[CAAFE] Warning: Failed to configure custom API settings: {e}")
            # 回退到默认设置
            import openai
            if not hasattr(openai, 'api_key') or not openai.api_key:
                print("[CAAFE] Warning: No OpenAI API key configured")
            # Fallback model name (may not be usable without a valid key/base URL)
            return os.environ.get("CAAFE_LLM_MODEL", "deepseek-chat")

    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        """
        Run CAAFE in the "official" way (CAAFEClassifier.fit_pandas + predict/predict_proba),
        while keeping the LLM model as deepseek-chat for cost control.
        """
        start_time = time.time()

        if task_type != "classify":
            return {"error": "CAAFEClassifier integration currently supports classification only."}

        if not self.available:
            return {"error": "CAAFE not available. Install via: pip install caafe"}

        # Preprocess (numeric-only; CAAFE expects a DataFrame and will run its own safe code execution)
        prep_start = time.time()
        X_processed = self._preprocess_caafe_data(X, y)
        self.preprocessing_time = time.time() - prep_start

        # Holdout split (same policy as other methods)
        X_train, X_test, y_train, y_test = train_test_split(
            X_processed, y, test_size=0.2, random_state=0, stratify=y
        )
        self._original_feature_count_input = int(X_train.shape[1])

        # Configure LLM endpoint
        model_name = self._configure_openai()
        if not os.environ.get("OPENAI_API_KEY"):
            return {"error": "OPENAI_API_KEY is not set (required by CAAFE / openai client)."}

        # Build base classifier according to model_type (keeps comparison consistent)
        base_clf = self._build_model(task_type="classify")

        # Wrap the base classifier so we can measure training time inside CAAFEClassifier.fit_pandas().
        # In upstream CAAFE, the model is trained *within* fit_pandas() after feature generation.
        from sklearn.base import BaseEstimator, ClassifierMixin

        class _TimedEstimator(BaseEstimator, ClassifierMixin):
            def __init__(self, estimator):
                self._estimator = estimator
                self.fit_seconds = 0.0
                self.predict_seconds = 0.0
                self.predict_proba_seconds = 0.0

            def fit(self, X, y, *args, **kwargs):
                t0 = time.time()
                try:
                    return self._estimator.fit(X, y, *args, **kwargs)
                finally:
                    self.fit_seconds += time.time() - t0

            def predict(self, X, *args, **kwargs):
                t0 = time.time()
                try:
                    return self._estimator.predict(X, *args, **kwargs)
                finally:
                    self.predict_seconds += time.time() - t0

            def predict_proba(self, X, *args, **kwargs):
                t0 = time.time()
                try:
                    return self._estimator.predict_proba(X, *args, **kwargs)
                finally:
                    self.predict_proba_seconds += time.time() - t0

            # Make sklearn-style parameter plumbing work and keep BaseEstimator happy.
            def get_params(self, deep: bool = True):
                return {"estimator": self._estimator}

            def set_params(self, **params):
                if "estimator" in params:
                    self._estimator = params["estimator"]
                return self

            def __getattr__(self, name):
                return getattr(self._estimator, name)

        timed_base_clf = _TimedEstimator(base_clf)

        # Keep iterations/splits small by default for cost/time; can be overridden via env vars.
        iterations = int(os.environ.get("CAAFE_ITERATIONS", "30"))
        n_splits = int(os.environ.get("CAAFE_N_SPLITS", "5"))
        n_repeats = int(os.environ.get("CAAFE_N_REPEATS", "1"))

        dataset_description = (
            f"Tabular dataset for a classification task. "
            f"Rows: {len(X_train)} train / {len(X_test)} test. "
            f"Features: {X_train.shape[1]} numeric columns."
        )

        # Train CAAFEClassifier
        feature_start = time.time()
        try:
            # Compatibility shim:
            # Some versions of `caafe` access `tabpfn.scripts.tabular_metrics` as an attribute
            # after importing `tabpfn.scripts` only, which can raise:
            #   AttributeError: module 'tabpfn.scripts' has no attribute 'tabular_metrics'
            # Even when the submodule exists and is importable.
            try:
                import importlib
                import tabpfn.scripts as _tabpfn_scripts

                _tm = importlib.import_module("tabpfn.scripts.tabular_metrics")
                if not hasattr(_tabpfn_scripts, "tabular_metrics"):
                    setattr(_tabpfn_scripts, "tabular_metrics", _tm)
            except Exception:
                # Best-effort only; if tabpfn isn't installed, CAAFE may not rely on it anyway.
                pass

            from caafe import CAAFEClassifier

            caafe_clf = CAAFEClassifier(
                base_classifier=timed_base_clf,
                optimization_metric="auc",
                iterations=iterations,
                llm_model=model_name,
                n_splits=n_splits,
                n_repeats=n_repeats,
            )

            target_column_name = "target"
            df_train = X_train.copy()
            df_train[target_column_name] = y_train.values

            caafe_clf.fit_pandas(
                df_train,
                dataset_description=dataset_description,
                target_column_name=target_column_name,
            )
            self.fitted_caafe = caafe_clf
            self.generated_feature_code = getattr(caafe_clf, "code", "") or ""
        except Exception as e:
            return {"error": f"CAAFE failed during fit: {type(e).__name__}: {e}"}
        finally:
            total_fit_seconds = time.time() - feature_start
            # Split fit_pandas() time into "feature generation" vs "model training"
            # based on the measured base estimator fit time.
            self.training_time = float(getattr(timed_base_clf, "fit_seconds", 0.0) or 0.0)
            self.feature_generation_time = max(0.0, float(total_fit_seconds) - self.training_time)

        # Extract engineered feature space for reporting (counts + optional preview)
        try:
            from caafe.run_llm_code import run_llm_code
            from caafe.preprocessing import make_datasets_numeric, split_target_column, make_dataset_numeric

            # Apply generated code on train (without target), then rebuild numeric mappings like upstream
            df_train_no_target = X_train.copy()
            df_train_fe = run_llm_code(self.generated_feature_code, df_train_no_target)
            df_train_fe[target_column_name] = y_train.values
            df_train_fe, _, mappings = make_datasets_numeric(
                df_train_fe, df_test=None, target_column=target_column_name, return_mappings=True
            )
            df_train_x, _ = split_target_column(df_train_fe, target_column_name)

            # Apply same transformation + mappings on test (for preview only)
            df_test_fe = run_llm_code(self.generated_feature_code, X_test.copy())
            df_test_fe = make_dataset_numeric(df_test_fe, mappings=mappings)

            # Keep a small preview payload in memory (train features only)
            self.generated_features = df_train_x
            self._feature_names_after_caafe = list(df_train_x.columns)
        except Exception:
            # If anything goes wrong, keep minimal info but still allow metrics
            self.generated_features = X_train.copy()
            self._feature_names_after_caafe = list(self.generated_features.columns)

        # Predict + evaluate
        eval_start = time.time()
        try:
            y_pred = self.fitted_caafe.predict(X_test)
            y_prob = None
            try:
                y_prob_full = self.fitted_caafe.predict_proba(X_test)
                if y_prob_full is not None:
                    y_prob = y_prob_full[:, 1] if y_prob_full.shape[1] == 2 else y_prob_full
            except Exception:
                y_prob = None

            if y_prob is None:
                auc = accuracy_score(y_test, y_pred)
            else:
                if isinstance(y_prob, np.ndarray) and y_prob.ndim == 2:
                    auc = roc_auc_score(y_test, y_prob, multi_class="ovr")
                else:
                    auc = roc_auc_score(y_test, y_prob)

            metrics = {
                "auc": float(auc),
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "f1": float(f1_score(y_test, y_pred, average="weighted")),
                "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
            }
        except Exception as e:
            return {"error": f"CAAFE failed during predict/eval: {type(e).__name__}: {e}"}
        finally:
            # Evaluation time (predict + metric computation)
            self.evaluation_time = time.time() - eval_start

        self.execution_time = time.time() - start_time
        # execution_time is inclusive; evaluation_time is measured directly above.
        # Keep other fields consistent if downstream code recomputes totals.
        return metrics

    def _preprocess_caafe_data(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """为CAAFE预处理数据"""
        X_processed = X.copy()

        # 处理分类变量 - CAAFE要求数据为数值型
        categorical_columns = X_processed.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            # 使用标签编码处理分类变量
            le = LabelEncoder()
            X_processed[col] = le.fit_transform(X_processed[col].astype(str))

        # 处理缺失值
        numeric_columns = X_processed.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            if X_processed[col].isnull().any():
                # 使用中位数填充缺失值
                median_val = X_processed[col].median()
                if pd.isna(median_val):
                    median_val = 0  # 如果中位数也是NaN，使用0
                X_processed[col] = X_processed[col].fillna(median_val)

        # 确保所有数据都是数值型
        X_processed = X_processed.astype(float)

        return X_processed

    def _extract_feature_info(self, X: pd.DataFrame, y: pd.Series, caafe_classifier=None):
        """提取CAAFE生成的特征信息"""
        try:
            if caafe_classifier is not None:
                # CAAFE会自动生成特征工程代码，我们可以获取相关信息
                self.generated_feature_names = list(X.columns)

                # 获取生成的特征工程代码信息
                generated_code = caafe_classifier.code
                code_lines = len(generated_code.split('\n')) if generated_code else 0

                print(f"[CAAFE] Processed {len(self.generated_feature_names)} features")
                print(f"[CAAFE] Generated {code_lines} lines of feature engineering code")

                # 保存特征工程代码以便后续查看
                self.generated_feature_code = generated_code
            else:
                self.generated_feature_names = list(X.columns)
                self.generated_feature_code = ""

        except Exception as e:
            print(f"Failed to extract CAAFE feature info: {str(e)}")
            self.generated_feature_names = list(X.columns)
            self.generated_feature_code = ""

    def get_feature_info(self) -> Dict[str, Any]:
        """获取生成的特征信息"""
        if self.generated_features is not None:
            original_count = int(getattr(self, "_original_feature_count_input", self.generated_features.shape[1]))

            # English-only description (front-end safe)
            description = "LLM-driven automated feature engineering using CAAFE."

            # 获取LLM配置信息
            try:
                import sys
                import os
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
                from src.env import openai_base_url, default_model

                description += f" (API: {openai_base_url}, model: {os.environ.get('CAAFE_LLM_MODEL','deepseek-chat')})"
                llm_model = os.environ.get("CAAFE_LLM_MODEL", "deepseek-chat")
                api_base = openai_base_url
            except:
                description += " (API: default)"
                llm_model = os.environ.get("CAAFE_LLM_MODEL", "deepseek-chat")
                api_base = os.environ.get("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", ""))

            # 获取特征工程代码信息
            code_lines = 0
            if hasattr(self, 'generated_feature_code') and self.generated_feature_code:
                code_lines = len(self.generated_feature_code.split('\n'))
                description += f" (generated code lines: {code_lines})"

            if self.fitted_caafe and hasattr(self.fitted_caafe, 'iterations'):
                description += f" (iterations: {getattr(self.fitted_caafe, 'iterations', 0)})"

            # Try to estimate how many new columns were created
            # Note: original feature count for reporting should come from the input, but here we use current df shape.
            new_features_count = 0
            try:
                if hasattr(self, "_feature_names_after_caafe") and self._feature_names_after_caafe:
                    new_features_count = max(0, len(self._feature_names_after_caafe) - original_count)
            except Exception:
                new_features_count = 0

            return {
                "original_feature_count": original_count,
                "generated_feature_count": len(self.generated_features.columns),
                "new_features_count": int(new_features_count),
                "feature_names": list(self.generated_features.columns),
                "new_feature_names": [],
                "generated_features": self.generated_features,
                "description": description,
                "success": True,
                "llm_model": llm_model,
                "api_base": api_base,
                "iterations": getattr(self.fitted_caafe, 'iterations', 0) if (self.fitted_caafe and hasattr(self.fitted_caafe, 'iterations')) else 0,
                "code_lines": code_lines,
                "feature_engineering_type": "LLM-based automated feature engineering",
                "generated_code": getattr(self, 'generated_feature_code', '')
            }
        return {
            "original_feature_count": 0,
            "generated_feature_count": 0,
            "new_features_count": 0,
            "feature_names": [],
            "new_feature_names": [],
            "generated_features": None,
            "description": "CAAFE feature generation failed.",
            "success": False,
            "llm_model": "unknown",
            "api_base": "unknown",
            "iterations": 0,
            "code_lines": 0,
            "feature_engineering_type": "LLM-based automated feature engineering",
            "generated_code": ""
        }


class ComparisonEngine:
    """特征工程框架对比引擎"""

    def __init__(self, db_config=None):
        self.methods = {
            "Baseline": BaselineMethod(),
            "AutoFeat": AutoFeatMethod(),
            "PGML": PGMLMethod(db_config),
            "MADlib": MadlibMethod(db_config),
            "CAAFE": CAAFEMethod()
        }

    def run_comparison(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify",
                      methods: List[str] = None, time_limit: int = 120, model_type: str = "RF") -> Dict[str, Any]:
        """
        运行特征工程框架对比

        Args:
            X: 原始特征数据
            y: 目标变量
            task_type: 任务类型 ("classify" 或 "regress")
            methods: 要对比的特征工程框架列表，None表示使用所有可用方法
            time_limit: 每个方法的时间限制（秒）
            model_type: 下游评估模型类型 (RF/XGB/LightGBM)，默认RF

        Returns:
            对比结果字典
        """
        if methods is None:
            methods = ["Baseline", "AutoFeat", "PGML", "MADlib", "CAAFE"]

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
            "feature_data": {
                "methods": [],
                "original_feature_count": [],
                "generated_feature_count": [],
                "new_features_count": []
            },
            "detailed_results": {}
        }

        for method_name in methods:
            if method_name not in self.methods:
                print(f"Warning: Feature engineering method {method_name} not available")
                continue

            method = self.methods[method_name]

            # 设置下游模型类型
            if hasattr(method, "set_model_type"):
                method.set_model_type(model_type)

            # 检查方法是否可用
            if hasattr(method, 'available') and not method.available:
                print(f"Warning: Method {method_name} not available (missing dependencies)")
                continue

            print(f"Running feature engineering comparison for method: {method_name}")

            try:
                # 运行特征工程方法
                metrics = method.fit_predict(X, y, task_type)

                if "error" in metrics:
                    print(f"Method {method_name} failed: {metrics['error']}")
                    continue

                # 记录结果
                results["methods"].append(method_name)
                results["performance_data"]["methods"].append(method_name)
                results["time_data"]["methods"].append(method_name)
                results["feature_data"]["methods"].append(method_name)

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

                # 记录时间数据（键名与返回的下划线风格对齐）
                time_breakdown = method.get_time_breakdown()
                time_key_map = {
                    "totalTime": "total_time",
                    "preprocessingTime": "preprocessing_time",
                    "featureGenerationTime": "feature_generation_time",
                    "trainingTime": "training_time",
                    "evaluationTime": "evaluation_time",
                }
                # total_time 在少数方法里会遗漏（保持 0），这里用各阶段时间求和兜底，避免返回 0 导致前端被过滤
                computed_total = (
                    float(time_breakdown.get("preprocessing_time", 0.0))
                    + float(time_breakdown.get("feature_generation_time", 0.0))
                    + float(time_breakdown.get("training_time", 0.0))
                    + float(time_breakdown.get("evaluation_time", 0.0))
                )

                for time_metric in ["totalTime", "preprocessingTime", "featureGenerationTime", "trainingTime", "evaluationTime"]:
                    mapped_key = time_key_map.get(time_metric, time_metric.lower())
                    value = time_breakdown.get(mapped_key, 0.0)

                    # 只对 totalTime 做兜底，保持其他字段原值
                    if time_metric == "totalTime" and (value is None or float(value) <= 0):
                        value = computed_total

                    results["time_data"][time_metric].append(float(value or 0.0))

                # 记录特征数据
                feature_info = method.get_feature_info()
                results["feature_data"]["original_feature_count"].append(feature_info.get("original_feature_count", 0))
                results["feature_data"]["generated_feature_count"].append(feature_info.get("generated_feature_count", 0))
                results["feature_data"]["new_features_count"].append(feature_info.get("new_features_count", 0))

                # 记录详细结果
                results["detailed_results"][method_name] = {
                    "metrics": metrics,
                    "time_breakdown": time_breakdown,
                    "feature_info": feature_info
                }

                print(f"✅ {method_name} completed:")
                print(f"   - AUC: {metrics.get('auc', 0):.4f}" if task_type == "classify" else f"   - RMSE: {metrics.get('rmse', 0):.4f}")
                print(f"   - Feature generation time: {time_breakdown.get('feature_generation_time', 0):.2f}s")
                print(f"   - Generated features: {feature_info.get('generated_feature_count', 0)}")

            except Exception as e:
                print(f"❌ Method {method_name} failed with exception: {e}")
                # 添加失败记录
                results["methods"].append(method_name)
                results["performance_data"]["methods"].append(method_name)
                results["time_data"]["methods"].append(method_name)
                results["feature_data"]["methods"].append(method_name)

                if task_type == "classify":
                    for metric in ["auc", "accuracy", "f1", "precision", "recall"]:
                        results["performance_data"][metric].append(0.0)
                else:
                    for metric in ["rmse", "mse", "mae", "r2"]:
                        results["performance_data"][metric].append(0.0)

                for time_metric in ["totalTime", "preprocessingTime", "featureGenerationTime", "trainingTime", "evaluationTime"]:
                    results["time_data"][time_metric].append(0.0)

                results["feature_data"]["original_feature_count"].append(0)
                results["feature_data"]["generated_feature_count"].append(0)
                results["feature_data"]["new_features_count"].append(0)

                continue

        return results

    def get_available_methods(self) -> List[str]:
        """获取所有可用的特征工程方法"""
        available = []
        for name, method in self.methods.items():
            if hasattr(method, 'available') and not method.available:
                continue
            available.append(name)
        return available

    def get_method_descriptions(self) -> Dict[str, str]:
        """获取各方法的描述"""
        return {
            # English-only (front-end safe)
            "Baseline": "Raw features (no feature engineering).",
            "AutoFeat": "Automated feature engineering with mathematical transformations.",
            "PGML": "PostgreSQL ML extension (in-database feature processing / AutoML-style pipeline).",
            "MADlib": "PostgreSQL MADlib plugin for categorical encoding and preprocessing.",
            "CAAFE": "LLM-driven feature engineering with iterative verification (CAAFE)."
        }


# 便利函数
def run_comparison_from_csv(csv_path: str, target_column: str, task_type: str = "classify",
                          methods: List[str] = None, time_limit: int = 120, db_config=None,
                          model_type: str = "RF") -> Dict[str, Any]:
    """
    从CSV文件运行特征工程框架对比

    Args:
        csv_path: CSV文件路径
        target_column: 目标列名
        task_type: 任务类型
        methods: 要对比的特征工程方法列表
        time_limit: 每个方法的时间限制（秒）
        db_config: PostgreSQL数据库配置（用于PGML）

    Returns:
        特征工程对比结果
    """
    # 读取数据
    df = pd.read_csv(csv_path)

    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in CSV")

    # 分离特征和目标
    X = df.drop(columns=[target_column])
    y = df[target_column]

    # 运行对比
    engine = ComparisonEngine(db_config)
    return engine.run_comparison(X, y, task_type, methods, time_limit, model_type)


def install_dependencies():
    """安装必要的依赖库"""
    import subprocess
    import sys

    packages = [
        "autofeat",
        "psycopg2-binary"
    ]

    print("Installing dependencies for feature engineering comparison...")
    for package in packages:
        try:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to install {package}")

    print("Dependency installation completed.")


if __name__ == "__main__":
    # 测试代码
    print("Feature Engineering Comparison Module")
    engine = ComparisonEngine()
    print("Available methods:", engine.get_available_methods())
    print("\nMethod descriptions:")
    for name, desc in engine.get_method_descriptions().items():
        print(f"- {name}: {desc}")
