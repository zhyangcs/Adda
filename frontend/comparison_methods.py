"""
Feature engineering framework comparison module.

Provides a unified interface to compare multiple feature engineering approaches,
focusing on predictive performance and time cost.

Environment Variables:
- AUTOFEAT_FEATSEL_RUNS: Number of feature selection runs for AutoFeat (default: 20)
"""

import os
import re
import time
import json
import warnings
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
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

# PGML SDK may fail to import on some systems; DB path is sufficient.
if not PGML_DB_AVAILABLE:
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
        # Time accounting (aligned for fair benchmarking):
        # - feature_generation_time: feature search / generation on training split only
        # - feature_transform_time: applying the learned transformation to test split
        # - training_time: model.fit on training split only
        # - prediction_time: model inference on test split (predict / predict_proba)
        # - evaluation_time: metric computation / remaining overhead
        self.feature_generation_time = 0.0
        self.feature_transform_time = 0.0
        self.training_time = 0.0
        self.prediction_time = 0.0
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
        """完整的特征生成+评估流程（避免数据泄露）"""
        start_time = time.time()

        # Expose task type to subclasses that need it (e.g., AutoFeatClassifier vs AutoFeatRegressor)
        self._task_type = task_type

        # IMPORTANT: per user request, remove all in-module data preprocessing.
        # That means:
        # - No categorical encoding.
        # - No dropping rows for feature search.
        # - No train-time statistics computed from the full dataset.
        #
        # Downstream training still requires a numeric matrix; later we will keep only numeric
        # columns (non-numeric columns are ignored) and apply a strict NaN/inf guard right before
        # model.fit/predict to avoid runtime errors.
        prep_start = time.time()
        X_full = X.copy()
        # Keep y as a pandas Series for consistent indexing/stratify behavior.
        y_full = pd.Series(y, index=X_full.index)
        # Feature-search mask is kept for API compatibility but does nothing under "no preprocessing".
        complete_mask = pd.Series(True, index=X_full.index)
        self.preprocessing_time = time.time() - prep_start

        # Split on a *single* dataframe that includes the target column (same random_state/stratify semantics).
        _target_key = "__target__"
        df_all = X_full.copy()
        df_all[_target_key] = np.asarray(y_full)
        if task_type == "classify":
            df_train, df_test = train_test_split(
                df_all, test_size=0.2, random_state=0, stratify=df_all[_target_key]
            )
        else:
            df_train, df_test = train_test_split(df_all, test_size=0.2, random_state=0)

        y_train_full = df_train[_target_key]
        y_test = df_test[_target_key]
        X_train_raw = df_train.drop(columns=[_target_key])
        X_test_raw = df_test.drop(columns=[_target_key])

        # Keep raw splits for methods that need to re-apply preprocessing after fitting (e.g., AutoFeat scaling).
        self._X_train_raw = X_train_raw
        self._X_test_raw = X_test_raw

        # Feature-search subset (complete-case rows) inside the TRAIN split only.
        # These rows are used to fit feature generation / feature selection logic.
        try:
            train_complete_mask = complete_mask.loc[X_train_raw.index]
        except Exception:
            # Fallback if index alignment fails for any reason.
            train_complete_mask = pd.Series(True, index=X_train_raw.index)

        X_train_search = X_train_raw.loc[train_complete_mask]
        y_train_search = y_train_full.loc[train_complete_mask]

        # Save for transparency/debugging.
        self._train_rows_full = int(len(X_train_raw))
        self._train_rows_search = int(len(X_train_search))
        self._test_rows_full = int(len(X_test_raw))

        # 保存训练集信息供子类使用
        self._X_train = X_train_search
        self._y_train = y_train_search
        self._y_test = y_test

        # Feature generation (TRAIN split only)
        feat_fit_start = time.time()
        X_train_generated = self.generate_features(X_train_search, y_train_search)
        self.feature_generation_time = time.time() - feat_fit_start
        self.generated_features = X_train_generated

        # Apply the learned feature transformation to TEST split (tracked separately)
        feat_transform_start = time.time()
        # Preprocessing is already applied globally above; test split is ready.
        X_test_basic = X_test_raw
        self._X_test = X_test_basic
        if hasattr(self, 'fitted_autofeat') and self.fitted_autofeat is not None:
            X_test_processed = X_test_raw.copy()
            # AutoFeat is usually fitted on numeric-only columns (and possibly scaled);
            # make sure test-time transform sees the exact same columns in the same order.
            autofeat_cols = getattr(self, "_autofeat_input_columns", None)
            if isinstance(autofeat_cols, (list, tuple)) and len(autofeat_cols) > 0:
                for c in autofeat_cols:
                    if c not in X_test_processed.columns:
                        X_test_processed[c] = 0.0
                X_test_processed = X_test_processed[list(autofeat_cols)]
            else:
                X_test_processed = X_test_processed.select_dtypes(include=[np.number])
            X_test_generated = self.fitted_autofeat.transform(X_test_processed)
        elif hasattr(self, 'fitted_scaler') and self.fitted_scaler is not None:
            X_test_generated = self._transform_test_features(X_test_basic)
        else:
            X_test_generated = X_test_basic
        self.feature_transform_time = time.time() - feat_transform_start

        # Build the feature matrix for final downstream model training.
        # Requirement:
        # - Feature search / fitting uses X_train_search only.
        # - Final model training uses the FULL training split (X_train_raw / y_train_full).
        #
        # For methods that expose a fitted transformer (e.g. AutoFeat), apply that transformer to
        # the full training split. Otherwise, fall back to using the generated features from the
        # search subset (best-effort; some methods have no reusable transform API).
        X_train_full_generated = None

        if hasattr(self, "fitted_autofeat") and getattr(self, "fitted_autofeat", None) is not None:
            # Mirror the test-time transform logic for the full training split.
            X_train_full_processed = X_train_raw.copy()
            autofeat_cols = getattr(self, "_autofeat_input_columns", None)
            if isinstance(autofeat_cols, (list, tuple)) and len(autofeat_cols) > 0:
                for c in autofeat_cols:
                    if c not in X_train_full_processed.columns:
                        X_train_full_processed[c] = 0.0
                X_train_full_processed = X_train_full_processed[list(autofeat_cols)]
            else:
                X_train_full_processed = X_train_full_processed.select_dtypes(include=[np.number])
            try:
                X_train_full_generated = self.fitted_autofeat.transform(X_train_full_processed)
            except Exception:
                X_train_full_generated = None
        elif (self.__class__.__name__ == "BaselineMethod") or str(getattr(self, "name", "")).lower().startswith("baseline"):
            # Baseline has no fitted transformer; it is identity.
            X_train_full_generated = X_train_raw
        elif hasattr(self, "fitted_scaler") and getattr(self, "fitted_scaler", None) is not None:
            # Some methods learn a scaler/transform; apply it to the full training split.
            try:
                X_train_full_generated = self._transform_test_features(X_train_raw)
            except Exception:
                X_train_full_generated = None

        # Ensure numeric matrix and align columns.
        def _drop_id_like_columns(df_in: pd.DataFrame) -> pd.DataFrame:
            # In Adda's in-DB pipeline, `id` is a join key, not a model feature.
            # Drop common id-like columns to avoid leakage / unfair baselines.
            cols = list(df_in.columns)
            drop_cols = []
            for c in cols:
                cl = str(c).strip().lower()
                if cl == "id" or cl.endswith("_id") or cl == "index":
                    drop_cols.append(c)
            return df_in.drop(columns=drop_cols, errors="ignore")

        def _to_numeric_frame(obj: Any) -> pd.DataFrame:
            if isinstance(obj, pd.DataFrame):
                df_obj = obj
            else:
                df_obj = pd.DataFrame(obj)
            df_num = df_obj.select_dtypes(include=[np.number])
            return _drop_id_like_columns(df_num)

        if X_train_full_generated is None:
            X_train_fit = _to_numeric_frame(X_train_generated)
            y_train_fit = y_train_search
        else:
            X_train_fit = _to_numeric_frame(X_train_full_generated)
            y_train_fit = y_train_full

        X_train_generated = _to_numeric_frame(X_train_generated)
        X_test_generated = _to_numeric_frame(X_test_generated)

        if X_train_fit.shape[1] == 0:
            return {"error": "No numeric features available after minimal preprocessing (cannot train downstream model)."}

        # Align test columns to train columns (fill missing engineered columns with 0).
        try:
            X_test_generated = X_test_generated.reindex(columns=list(X_train_fit.columns), fill_value=0.0)
        except Exception:
            pass

        # Adda PL/Python UDF path applies a strict NaN guard before training/prediction:
        #   replace inf/-inf with NaN, then fill NaN with 0.
        X_train_fit = X_train_fit.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        X_test_generated = X_test_generated.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        # Train and evaluate (timed as: fit-only, then predict-only, then metric-only/overhead)
        model = self._build_model(task_type)

        fit_start = time.time()
        model.fit(X_train_fit, y_train_fit)
        self.training_time = time.time() - fit_start

        pred_start = time.time()
        y_pred = model.predict(X_test_generated)
        y_prob = None
        if task_type == "classify":
            try:
                y_prob = model.predict_proba(X_test_generated)[:, 1] if len(model.classes_) == 2 else None
            except Exception:
                y_prob = None
        self.prediction_time = time.time() - pred_start

        metric_start = time.time()
        if task_type == "classify":
            try:
                auc = roc_auc_score(y_test, y_prob if y_prob is not None else y_pred)
            except Exception:
                auc = accuracy_score(y_test, y_pred)
            metrics = {
                "auc": auc,
                "accuracy": accuracy_score(y_test, y_pred),
                "f1": f1_score(y_test, y_pred, average='weighted'),
                "precision": precision_score(y_test, y_pred, average='weighted'),
                "recall": recall_score(y_test, y_pred, average='weighted'),
            }
        else:
            mse = mean_squared_error(y_test, y_pred)
            # RAE (relative absolute error): sum(|y - y_hat|) / sum(|y - mean(y)|)
            # Paper-style score: 1 - RAE (higher is better; can be negative if worse than mean baseline).
            y_true_arr = np.asarray(y_test, dtype=float)
            y_pred_arr = np.asarray(y_pred, dtype=float)
            rae_num = float(np.sum(np.abs(y_true_arr - y_pred_arr)))
            rae_den = float(np.sum(np.abs(y_true_arr - float(np.mean(y_true_arr)))))
            if rae_den <= 0:
                rae = 0.0 if rae_num <= 0 else float("inf")
            else:
                rae = rae_num / rae_den
            one_minus_rae = 1.0 - rae if np.isfinite(rae) else float("-inf")
            metrics = {
                "rmse": np.sqrt(mse),
                "mse": mse,
                "mae": mean_absolute_error(y_test, y_pred),
                "r2": r2_score(y_test, y_pred),
                "rae": float(rae),
                "one_minus_rae": float(one_minus_rae),
            }

        self.execution_time = time.time() - start_time
        # "evaluation_time" keeps legacy meaning: metrics + remaining overhead not captured elsewhere.
        self.evaluation_time = (
            time.time() - metric_start
            + max(
                0.0,
                self.execution_time
                - self.preprocessing_time
                - self.feature_generation_time
                - self.feature_transform_time
                - self.training_time
                - self.prediction_time,
            )
        )
        return metrics

    # 防止子类重写关键方法
    def _ensure_no_data_leakage(self):
        """防止数据泄露的安全检查"""
        if not hasattr(self, '_X_train') or not hasattr(self, '_X_test'):
            raise RuntimeError("Data leakage protection: Must call fit_predict() first")

    @staticmethod
    def _prepare_df_for_train_adda_standard(
        df: pd.DataFrame,
        label: Optional[pd.Series] = None,
    ) -> tuple[pd.DataFrame, Optional[pd.Series]]:
        """
        Legacy helper. Per user request, this is now a no-op (except for copying and
        preserving label alignment).
        """
        if label is not None:
            return df.copy(), label.copy()
        return df.copy(), None

    @staticmethod
    def _encode_and_mark_complete_adda_standard(
        df: pd.DataFrame,
        label: pd.Series,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """
        No-preprocessing variant:
        - Keeps the original columns unchanged (no categorical encoding).
        - Drops rows where label is NaN (cannot stratify/evaluate).
        - Returns a "complete-case" mask computed after inf->NaN replacement (best-effort).
        """
        X_raw = df.copy()
        y_raw = pd.Series(label, index=df.index)

        combined = X_raw.copy()
        combined["__target__"] = y_raw
        combined = combined.replace([float("inf"), float("-inf")], float("nan"))

        # If label has NaN, it cannot be used for stratification/metrics; drop those rows globally.
        label_ok = combined["__target__"].notna()
        combined = combined.loc[label_ok]

        complete_mask = ~combined.isna().any(axis=1)

        X_full = combined.drop(columns=["__target__"])
        y_full = combined["__target__"]

        return X_full, y_full, complete_mask

    def _preprocess_data(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        No-op preprocessing (per user request).
        """
        return X.copy()

    def _preprocess_test_data(self, X_test: pd.DataFrame, X_train: pd.DataFrame) -> pd.DataFrame:
        # Adda-original path does not use a separate "test preprocessing" mapping.
        # Keep the signature for legacy callers, but apply the same encoding-only behavior.
        return self._preprocess_data(X_test)

    def _transform_test_features(self, X_test: pd.DataFrame) -> pd.DataFrame:
        """使用训练时保存的组件转换测试集特征（适用于PGML等）"""
        X_test_processed = X_test.copy()

        # Minimal test preprocessing (no categorical encoding here).
        X_test_processed = self._preprocess_data(X_test_processed)
        X_test_processed = X_test_processed.select_dtypes(include=[np.number])

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
            "feature_transform_time": self.feature_transform_time,
            "training_time": self.training_time,
            "prediction_time": self.prediction_time,
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

    class _AutoFeatStableLassoShim:
        """
        Drop-in replacement for sklearn's LassoLarsCV used by `autofeat==0.1`.

        Why: new scikit-learn versions can raise broadcasting errors inside LassoLarsCV's
        LARS path solver on some datasets (e.g. boston_house split), which makes AutoFeat's
        internal end-to-end mode fail.

        This shim uses coordinate-descent Lasso (no CV). It's much more stable and typically
        faster than LassoCV for this use-case, while still providing coef_/intercept_/predict/score.
        """

        def __init__(self, eps: float = 1e-8, *args, **kwargs):
            # Keep signature compatible with callers that pass eps=...
            self.eps = eps
            # If caller provided alpha, honor it; otherwise choose a small default.
            alpha = kwargs.pop("alpha", 1e-3)
            max_iter = kwargs.pop("max_iter", 10000)
            # Avoid unexpected kwargs breaking instantiation.
            try:
                from sklearn.linear_model import Lasso

                self._model = Lasso(
                    alpha=float(alpha),
                    max_iter=int(max_iter),
                    random_state=0,
                    fit_intercept=True,
                )
            except Exception as e:
                raise ImportError(f"Failed to create Lasso shim for AutoFeat: {e}")

            self.coef_ = None
            self.intercept_ = 0.0

        def fit(self, X, y):
            self._model.fit(X, y)
            self.coef_ = getattr(self._model, "coef_", None)
            self.intercept_ = float(getattr(self._model, "intercept_", 0.0))
            return self

        def predict(self, X):
            return self._model.predict(X)

        def score(self, X, y):
            return self._model.score(X, y)

    def __init__(
        self,
        model_type: str = "RF",
        *,
        # Keep comparability with upstream `autofeat` by default.
        enable_numerical_stability_preprocessing: bool = False,
        # If True, use AutoFeat's own estimator training/prediction when available (paper-style end-to-end).
        # In `autofeat==0.1`, this corresponds to AutoFeatRegression training a final linear model internally.
        use_autofeat_internal_model: Optional[bool] = None,
        # Older autofeat (0.1) uses these knobs; newer versions may ignore them.
        featsel_runs: Optional[int] = None,
        max_gb: Optional[float] = None,
        units: Optional[Dict[str, Any]] = None,
        feateng_steps: Optional[int] = None,
        transformations: Optional[Tuple] = None,
        n_jobs: Optional[int] = None,
        verbose: Optional[int] = None,
    ):
        super().__init__("AutoFeat", model_type)
        self.available = AUTOFEAT_AVAILABLE
        self.feateng_cols = []  # 存储生成的特征列名
        self.enable_numerical_stability_preprocessing = enable_numerical_stability_preprocessing
        # Default to "paper-style" internal model for old versions unless explicitly disabled.
        # Can be overridden via env var AUTOFEAT_USE_INTERNAL_MODEL=0/1.
        if use_autofeat_internal_model is None:
            env_flag = os.environ.get("AUTOFEAT_USE_INTERNAL_MODEL", "").strip()
            if env_flag in {"0", "false", "False", "no", "NO"}:
                self.use_autofeat_internal_model = False
            elif env_flag in {"1", "true", "True", "yes", "YES"}:
                self.use_autofeat_internal_model = True
            else:
                self.use_autofeat_internal_model = True
        else:
            self.use_autofeat_internal_model = bool(use_autofeat_internal_model)

        self.autofeat_params: Dict[str, Any] = {
            "featsel_runs": featsel_runs,
            "max_gb": max_gb,
            "units": units,
            "feateng_steps": feateng_steps,
            "transformations": transformations,
            "n_jobs": n_jobs,
            "verbose": verbose,
        }
        self.autofeat_version: Optional[str] = None
        self._positive_shift_by_col: Optional[Dict[str, float]] = None
        # Train-derived clipping bounds to prevent inf/NaN in old `autofeat==0.1`
        self._clip_bounds_by_col: Optional[Dict[str, tuple[float, float]]] = None
        # Whether we've patched `autofeat==0.1` sklearn compatibility shims.
        self._autofeat_compat_patched: bool = False

    def _instantiate_autofeat(self) -> Any:
        """Instantiate the correct AutoFeat class for the installed package version."""
        import inspect
        import autofeat as _autofeat_pkg

        self.autofeat_version = getattr(_autofeat_pkg, "__version__", None) or getattr(_autofeat_pkg, "version", None)
        version = str(self.autofeat_version or "")

        # `autofeat==0.1` uses `sklearn.linear_model.LassoLarsCV` in multiple places.
        # With newer scikit-learn versions, LassoLarsCV can raise
        #   ValueError: operands could not be broadcast together with shapes (n,) (n-1,)
        # inside the LARS path solver on some datasets (including our boston_house split).
        #
        # We cannot change `autofeat==0.1` (user constraint), so we patch its internal references
        # to use a stable Lasso shim (no CV) to avoid both the crash and excessive runtime.
        if (not self._autofeat_compat_patched) and version.startswith("0.1"):
            try:
                import autofeat.autofeat as _af_autofeat_mod
                import autofeat.featsel as _af_featsel_mod

                # Patch both modules, since both import `sklearn.linear_model as lm`.
                _af_autofeat_mod.lm.LassoLarsCV = AutoFeatMethod._AutoFeatStableLassoShim
                _af_featsel_mod.lm.LassoLarsCV = AutoFeatMethod._AutoFeatStableLassoShim
                self._autofeat_compat_patched = True
            except Exception:
                # Best-effort only; if patching fails we keep the original behavior.
                self._autofeat_compat_patched = False

        # `autofeat==0.1` default transformations include log/sqrt/1/, which frequently create NaN/inf
        # once feature combinations generate negative/zero intermediate values. The library then may
        # drop rows internally (without dropping y), causing shape mismatch errors.
        #
        # To keep the internal end-to-end path reliable for 0.1, we default to a safer subset unless
        # the caller explicitly provided `transformations`.
        if version.startswith("0.1") and self.autofeat_params.get("transformations") is None:
            self.autofeat_params["transformations"] = ["abs", "^2", "^3"]

        is_classification = getattr(self, "_task_type", None) == "classify"
        AutoFeatRegressor = getattr(_autofeat_pkg, "AutoFeatRegressor", None)
        AutoFeatClassifier = getattr(_autofeat_pkg, "AutoFeatClassifier", None)
        AutoFeatRegression = getattr(_autofeat_pkg, "AutoFeatRegression", None)

        if is_classification and AutoFeatClassifier is not None:
            cls = AutoFeatClassifier
        elif (not is_classification) and AutoFeatRegressor is not None:
            cls = AutoFeatRegressor
        elif AutoFeatRegression is not None:
            cls = AutoFeatRegression
        else:
            raise ImportError("Unsupported autofeat version: cannot find AutoFeat* class entry point.")

        sig = inspect.signature(cls.__init__)
        allowed = set(sig.parameters.keys())
        params: Dict[str, Any] = {}
        if "categorical_cols" in allowed:
            # In older versions (0.1), categorical_cols defaults to [] (list of column names).
            params["categorical_cols"] = []
        for k, v in (self.autofeat_params or {}).items():
            if v is None:
                continue
            if k not in allowed:
                continue
            if k == "categorical_cols" and isinstance(v, bool):
                v = [] if v is False else []
            params[k] = v

        return cls(**params)

    def _prepare_autofeat_input(self, X: pd.DataFrame, *, fit: bool) -> pd.DataFrame:
        """Prepare numeric-only input for AutoFeat; optionally fit and store scalers/shifts."""
        X_numeric = X.select_dtypes(include=[np.number])
        if X_numeric.shape[1] == 0:
            raise ValueError("AutoFeat requires at least one numeric feature")
        X_numeric = X_numeric.fillna(X_numeric.median())
        if X_numeric.isnull().any().any():
            X_numeric = X_numeric.fillna(0)

        # Compatibility guard for very old autofeat (0.1) + modern pandas/numpy:
        # default transformations include log/sqrt/1/, which can produce NaN/inf on non-positive values
        # and may cause internal row-dropping leading to shape mismatches.
        try:
            version = str(getattr(self, "autofeat_version", "") or "")
            transformations_used = self.autofeat_params.get("transformations") if isinstance(self.autofeat_params, dict) else None
            if transformations_used is None:
                # 0.1 default (from signature): ['exp','log','abs','sqrt','^2','^3','1/']
                transformations_used = ["exp", "log", "abs", "sqrt", "^2", "^3", "1/"]
            needs_positive = any(t in {"log", "sqrt"} for t in transformations_used)
            needs_nonzero = any(t in {"1/"} for t in transformations_used)
            if version.startswith("0.1"):
                # 1) Shift columns to avoid log/sqrt of non-positive and 1/ near zero.
                #    (Leakage-free: derive from train, apply same shift to test.)
                X_np = X_numeric.copy()
                if fit:
                    shift_by_col: Dict[str, float] = {}
                    if needs_positive or needs_nonzero:
                        for col in X_np.columns:
                            col_min = float(np.nanmin(X_np[col].to_numpy(dtype=float, copy=False)))
                            if col_min <= 0:
                                shift = 1e-6 - col_min
                                shift_by_col[str(col)] = shift
                                X_np[col] = X_np[col] + shift
                    self._positive_shift_by_col = shift_by_col
                else:
                    stored = getattr(self, "_positive_shift_by_col", None)
                    if isinstance(stored, dict) and stored:
                        for col, shift in stored.items():
                            if col in X_np.columns:
                                X_np[col] = X_np[col] + float(shift)

                # 2) Clip to train-derived bounds to prevent exp/power overflow and infinities.
                #    This targets the common `autofeat==0.1` failure where internal code drops rows
                #    due to inf/NaN created by aggressive default transformations.
                if fit:
                    clip_bounds: Dict[str, tuple[float, float]] = {}
                    for col in X_np.columns:
                        arr = X_np[col].to_numpy(dtype=float, copy=False)
                        # Robust bounds; avoid extremes from outliers.
                        lo = float(np.nanpercentile(arr, 1.0))
                        hi = float(np.nanpercentile(arr, 99.0))
                        if not np.isfinite(lo) or not np.isfinite(hi) or lo >= hi:
                            lo = float(np.nanmin(arr))
                            hi = float(np.nanmax(arr))
                        if not np.isfinite(lo) or not np.isfinite(hi) or lo >= hi:
                            lo, hi = -1.0, 1.0
                        clip_bounds[str(col)] = (lo, hi)
                    self._clip_bounds_by_col = clip_bounds
                else:
                    clip_bounds = getattr(self, "_clip_bounds_by_col", None) or {}

                if isinstance(clip_bounds, dict) and clip_bounds:
                    for col in X_np.columns:
                        b = clip_bounds.get(str(col))
                        if b is None:
                            continue
                        lo, hi = b
                        X_np[col] = X_np[col].clip(lower=float(lo), upper=float(hi))

                # 3) Ensure finite numeric matrix (avoid downstream row filtering).
                X_np = X_np.replace([np.inf, -np.inf], np.nan)
                if X_np.isnull().any().any():
                    X_np = X_np.fillna(0.0)

                # 4) Extra guard for 1/ transformation: avoid values too close to 0.
                if needs_nonzero:
                    X_vals = X_np.to_numpy(dtype=float, copy=False)
                    tiny_mask = np.isfinite(X_vals) & (np.abs(X_vals) < 1e-6)
                    if np.any(tiny_mask):
                        X_vals = X_vals.copy()
                        X_vals[tiny_mask] = np.sign(X_vals[tiny_mask]) * 1e-6
                        X_np = pd.DataFrame(X_vals, columns=X_np.columns, index=X_np.index)

                X_numeric = X_np
        except Exception:
            pass

        if self.enable_numerical_stability_preprocessing:
            X_numeric_processed = X_numeric.copy()
            positive_shift_by_col: Dict[str, float] = {}
            for col in X_numeric_processed.columns:
                if (X_numeric_processed[col] <= 0).any():
                    min_val = X_numeric_processed[col].min()
                    if min_val <= 0:
                        shift = 1e-6 - float(min_val)
                        positive_shift_by_col[str(col)] = shift
                        X_numeric_processed[col] = X_numeric_processed[col] + shift

            from sklearn.preprocessing import StandardScaler
            if fit:
                scaler = StandardScaler()
                X_numeric_scaled = pd.DataFrame(
                    scaler.fit_transform(X_numeric_processed),
                    columns=X_numeric_processed.columns,
                    index=X_numeric_processed.index
                )
                self.fitted_scaler = scaler
                self._positive_shift_by_col = positive_shift_by_col
                X_numeric = X_numeric_scaled
            else:
                # Apply stored shift + scaler
                shift_by_col = getattr(self, "_positive_shift_by_col", None)
                for col in X_numeric_processed.columns:
                    if (X_numeric_processed[col] <= 0).any():
                        shift = None
                        if isinstance(shift_by_col, dict) and str(col) in shift_by_col:
                            shift = shift_by_col[str(col)]
                        if shift is not None:
                            X_numeric_processed[col] = X_numeric_processed[col] + shift
                if hasattr(self, "fitted_scaler") and self.fitted_scaler is not None:
                    X_numeric_scaled = pd.DataFrame(
                        self.fitted_scaler.transform(X_numeric_processed),
                        columns=X_numeric_processed.columns,
                        index=X_numeric_processed.index
                    )
                    X_numeric = X_numeric_scaled
        else:
            if fit:
                self.fitted_scaler = None
                self._positive_shift_by_col = None

        self._autofeat_input_columns = list(X_numeric.columns)
        return X_numeric

    @staticmethod
    def _align_xy_for_autofeat(X_df: pd.DataFrame, y: pd.Series | np.ndarray | list) -> tuple[pd.DataFrame, np.ndarray]:
        """
        Older autofeat versions (e.g. 0.1) can be sensitive to non-contiguous pandas indices.
        Force a clean 0..n-1 index on X and a length-matched numpy y.
        """
        X_out = X_df.reset_index(drop=True)
        y_arr = np.asarray(y)
        if y_arr.ndim > 1:
            y_arr = y_arr.reshape(-1)
        # If y came in as a pandas Series with its own index, align by position after reset.
        if len(y_arr) != len(X_out):
            try:
                y_arr = np.asarray(pd.Series(y).reset_index(drop=True))
            except Exception:
                pass
        return X_out, y_arr.astype(float, copy=False)

    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        """
        If `use_autofeat_internal_model` is enabled and the installed package supports it,
        run AutoFeat in its native end-to-end mode (fit + predict), counting that wall time.
        Otherwise, fall back to the base implementation (fit_transform + downstream model training).
        """
        self._task_type = task_type
        if not self.use_autofeat_internal_model:
            return super().fit_predict(X, y, task_type)

        # `autofeat==0.1` exposes regression only; for classification we must fall back.
        if task_type == "classify":
            try:
                import autofeat as _autofeat_pkg
                if getattr(_autofeat_pkg, "AutoFeatClassifier", None) is None:
                    return super().fit_predict(X, y, task_type)
            except Exception:
                return super().fit_predict(X, y, task_type)

        start_time = time.time()

        # Split exactly like Adda import_table_with_split (single df split, random_state=0, stratify only for classify)
        _target_key = "__target__"
        df_all = X.copy()
        df_all[_target_key] = np.asarray(y)
        if task_type == "classify":
            df_train, df_test = train_test_split(
                df_all, test_size=0.2, random_state=0, stratify=df_all[_target_key]
            )
        else:
            df_train, df_test = train_test_split(df_all, test_size=0.2, random_state=0)

        y_train = df_train[_target_key]
        y_test = df_test[_target_key]
        X_train_raw = df_train.drop(columns=[_target_key])
        X_test_raw = df_test.drop(columns=[_target_key])

        # Preprocess (train-only) for leakage-free stats, then prepare AutoFeat numeric input
        prep_start = time.time()
        X_train_basic = self._preprocess_data(X_train_raw)
        self.preprocessing_time = time.time() - prep_start

        # Reduce run-to-run drift (older autofeat versions use randomized selection runs).
        try:
            import random as _random
            _random.seed(0)
            np.random.seed(0)
        except Exception:
            pass

        # Best-effort sympy compatibility shim for older autofeat versions
        try:
            import types
            import sympy as _sp
            if hasattr(_sp, "Add"):
                add_obj = getattr(_sp, "add", None)
                if add_obj is None or not hasattr(add_obj, "Add"):
                    setattr(_sp, "add", types.SimpleNamespace(Add=_sp.Add))
        except Exception:
            pass

        try:
            auto_feat = self._instantiate_autofeat()

            feat_start = time.time()
            X_train_numeric = self._prepare_autofeat_input(X_train_basic, fit=True)
            X_train_numeric, y_train_arr = self._align_xy_for_autofeat(X_train_numeric, y_train)
            # Prefer fit_transform to match autofeat's intended usage (and internal model training).
            try:
                auto_feat.fit_transform(X_train_numeric, y_train_arr)
            except Exception:
                auto_feat.fit(X_train_numeric, y_train_arr)
            self.fitted_autofeat = auto_feat
            # In internal mode, this "feature_generation_time" includes AutoFeat's own model training as well.
            self.feature_generation_time = time.time() - feat_start

            # Predict on test (AutoFeat does its own transform internally when calling predict)
            test_basic = self._preprocess_test_data(X_test_raw, X_train_raw)
            X_test_numeric = self._prepare_autofeat_input(test_basic, fit=False)
            X_test_numeric = X_test_numeric.reset_index(drop=True)

            pred_start = time.time()
            y_pred = auto_feat.predict(X_test_numeric)
            self.prediction_time = time.time() - pred_start
            self.feature_transform_time = 0.0  # bundled into prediction_time for internal AutoFeat predict
            self.training_time = 0.0  # bundled into feature_generation_time for internal AutoFeat fit

            metric_start = time.time()
            if task_type == "classify":
                # Prefer proba if available
                y_prob = None
                try:
                    if hasattr(auto_feat, "predict_proba"):
                        y_prob = auto_feat.predict_proba(X_test_numeric)
                except Exception:
                    y_prob = None
                try:
                    auc = roc_auc_score(y_test, y_prob[:, 1] if isinstance(y_prob, np.ndarray) and y_prob.ndim == 2 else y_pred)
                except Exception:
                    auc = accuracy_score(y_test, y_pred)
                metrics = {
                    "auc": float(auc),
                    "accuracy": float(accuracy_score(y_test, y_pred)),
                    "f1": float(f1_score(y_test, y_pred, average="weighted")),
                    "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
                    "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
                }
            else:
                mse = mean_squared_error(y_test, y_pred)
                y_true_arr = np.asarray(y_test, dtype=float)
                y_pred_arr = np.asarray(y_pred, dtype=float)
                rae_num = float(np.sum(np.abs(y_true_arr - y_pred_arr)))
                rae_den = float(np.sum(np.abs(y_true_arr - float(np.mean(y_true_arr)))))
                if rae_den <= 0:
                    rae = 0.0 if rae_num <= 0 else float("inf")
                else:
                    rae = rae_num / rae_den
                one_minus_rae = 1.0 - rae if np.isfinite(rae) else float("-inf")
                metrics = {
                    "rmse": float(np.sqrt(mse)),
                    "mse": float(mse),
                    "mae": float(mean_absolute_error(y_test, y_pred)),
                    "r2": float(r2_score(y_test, y_pred)),
                    "rae": float(rae),
                    "one_minus_rae": float(one_minus_rae),
                }

            self.execution_time = time.time() - start_time
            self.evaluation_time = time.time() - metric_start
            # Keep generated_features for reporting (train features only, if available)
            self.generated_features = X_train_numeric
            return metrics

        except Exception as e:
            # If internal mode fails for any reason, fall back to external mode (keeps system usable).
            print(f"AutoFeat internal end-to-end failed: {type(e).__name__}: {e}. Falling back to external evaluation.")
            return super().fit_predict(X, y, task_type)

    def generate_features(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """使用AutoFeat生成特征"""
        if not self.available:
            raise ImportError("AutoFeat not available. Please install with: pip install autofeat")

        if y is None:
            raise ValueError("AutoFeat requires target variable for supervised feature generation")

        try:
            # Reduce run-to-run drift (older autofeat versions use randomized selection runs).
            try:
                import random as _random
                _random.seed(0)
                np.random.seed(0)
            except Exception:
                pass

            # Best-effort sympy compatibility shim for older autofeat versions
            try:
                import types
                import sympy as _sp
                # Older autofeat versions may reference `sympy.add.Add` (module + class).
                # Newer sympy versions may not expose `sympy.add` as a module.
                if hasattr(_sp, "Add"):
                    add_obj = getattr(_sp, "add", None)
                    if add_obj is None or not hasattr(add_obj, "Add"):
                        setattr(_sp, "add", types.SimpleNamespace(Add=_sp.Add))
            except Exception:
                pass

            # Instantiate first so we know the installed version (used by preprocessing guards)
            auto_feat = self._instantiate_autofeat()
            X_numeric = self._prepare_autofeat_input(X, fit=True)

            # 使用fit_transform而不是分开的fit和transform（更高效，减少NaN问题）
            print(f"[AutoFeat] Starting feature generation with {X_numeric.shape[1]} features...")
            X_numeric_aligned, y_arr = self._align_xy_for_autofeat(X_numeric, y)
            X_generated = auto_feat.fit_transform(X_numeric_aligned, y_arr)

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
                "success": len(self.feateng_cols) > 0,
                "autofeat_version": self.autofeat_version,
                "autofeat_params": self.autofeat_params,
                "enable_numerical_stability_preprocessing": self.enable_numerical_stability_preprocessing,
            }
        return {
            "original_feature_count": 0,
            "generated_feature_count": 0,
            "new_features_count": 0,
            "feature_names": [],
            "new_feature_names": [],
            "generated_features": None,
            "description": "AutoFeat feature generation failed.",
            "success": False,
            "autofeat_version": self.autofeat_version,
            "autofeat_params": self.autofeat_params,
            "enable_numerical_stability_preprocessing": self.enable_numerical_stability_preprocessing,
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
        """使用PostgreSQL数据库连接 + pgml.train 生成特征"""
        table_name = f"pgml_feat_{int(time.time())}"
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # ---- 1. 上传数据到临时表 ----
            safe_cols = []
            col_defs = ["id SERIAL PRIMARY KEY"]
            for col in X.columns:
                safe = re.sub(r'[^a-zA-Z0-9_]', '_', str(col)).lower()
                safe_cols.append(safe)
                dt = 'DOUBLE PRECISION' if pd.api.types.is_numeric_dtype(X[col]) else 'TEXT'
                col_defs.append(f"{safe} {dt}")
            if y is not None:
                target_dt = 'INTEGER' if pd.api.types.is_integer_dtype(y) else 'DOUBLE PRECISION'
                col_defs.append(f"target {target_dt}")

            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            cursor.execute(f"CREATE TABLE {table_name} ({', '.join(col_defs)})")

            # 批量插入
            insert_cols = safe_cols + (['target'] if y is not None else [])
            records = []
            for idx, (_, row) in enumerate(X.iterrows()):
                vals = []
                for c in X.columns:
                    v = row[c]
                    if pd.isna(v):
                        vals.append(None)
                    elif pd.api.types.is_numeric_dtype(type(v)):
                        vals.append(float(v))
                    else:
                        vals.append(str(v))
                if y is not None:
                    yv = y.iloc[idx]
                    vals.append(int(yv) if pd.api.types.is_integer_dtype(y) else float(yv))
                records.append(tuple(vals))

            from psycopg2.extras import execute_values
            placeholders = ', '.join(insert_cols)
            execute_values(cursor, f"INSERT INTO {table_name} ({placeholders}) VALUES %s", records)
            conn.commit()

            # ---- 2. 使用 pgml.train 训练模型 ----
            if y is not None:
                unique_y = len(np.unique(y.dropna()))
                task_type = 'classification' if unique_y <= 20 else 'regression'
                project_name = f"pgml_cmp_{int(time.time())}"

                try:
                    cursor.execute(
                        "SELECT * FROM pgml.train(%s, %s, %s, %s, %s, %s::jsonb)",
                        (
                            project_name,
                            task_type,
                            table_name,
                            'target',
                            'random_forest',
                            json.dumps({"n_estimators": 100, "random_state": 42}),
                        ),
                    )
                    train_result = cursor.fetchone()
                    conn.commit()
                    print(f"[PGML DB] pgml.train result: {train_result}")
                except Exception as pgml_err:
                    conn.rollback()
                    print(f"[PGML DB] pgml.train failed: {pgml_err}")

            # ---- 3. 读回特征（pgml 不显式生成新列，返回原始特征） ----
            cursor.execute(f"SELECT {', '.join(safe_cols)} FROM {table_name} ORDER BY id")
            rows = cursor.fetchall()
            X_final = pd.DataFrame(rows, columns=safe_cols, index=X.index)

            # 确保数值类型
            X_final = X_final.apply(pd.to_numeric, errors='coerce')
            X_final = X_final.fillna(0.0)

            self.generated_features = X_final
            print(f"[PGML DB] Returned {X_final.shape[1]} feature columns")
            return X_final

        except Exception as e:
            print(f"PGML database feature generation failed: {e}")
            return X.copy()
        finally:
            try:
                if 'cursor' in locals():
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    conn.commit()
            except Exception:
                pass

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

    @staticmethod
    def _patch_openai_legacy_chatcompletion():
        """
        Patch openai>=1.x to provide legacy ChatCompletion.create used by caafe<=0.1.x.
        """
        try:
            import openai
        except Exception:
            return

        # If legacy API is already available without errors, keep it.
        try:
            _ = getattr(openai, "ChatCompletion", None)
        except Exception:
            _ = None

        def _get_base_url():
            return (
                getattr(openai, "base_url", None)
                or getattr(openai, "api_base", None)
                or os.environ.get("OPENAI_BASE_URL")
                or os.environ.get("OPENAI_API_BASE")
                or None
            )

        def _chatcompletion_create(**kwargs):
            client = openai.OpenAI(
                api_key=getattr(openai, "api_key", None) or os.environ.get("OPENAI_API_KEY"),
                base_url=_get_base_url(),
            )
            resp = client.chat.completions.create(**kwargs)
            # caafe expects a dict-like response with choices[0].message["content"]
            if hasattr(resp, "model_dump"):
                return resp.model_dump()
            return resp

        try:
            openai.ChatCompletion = type(
                "ChatCompletion",
                (),
                {"create": staticmethod(_chatcompletion_create)},
            )
        except Exception:
            pass

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

        # Keep preprocessing consistent with Adda-original standard:
        # - encode categoricals with pandas category codes
        # - do NOT drop NaNs for evaluation
        # - only complete-case rows participate in feature search/fitting
        prep_start = time.time()
        X_full, y_full, complete_mask = self._encode_and_mark_complete_adda_standard(X, y)
        self.preprocessing_time = time.time() - prep_start

        # Holdout split (same policy as other methods)
        X_train, X_test, y_train, y_test = train_test_split(
            X_full, y_full, test_size=0.2, random_state=0, stratify=y_full
        )
        self._original_feature_count_input = int(X_train.shape[1])

        # Feature-search subset for fitting CAAFE (complete-case rows within training split only)
        try:
            train_complete_mask = complete_mask.loc[X_train.index]
        except Exception:
            train_complete_mask = pd.Series(True, index=X_train.index)

        X_train_search = X_train.loc[train_complete_mask]
        y_train_search = y_train.loc[train_complete_mask]

        # CAAFE expects numeric data; cast to float and apply NaN guard on the matrices we pass in.
        def _drop_id_like_columns(df_in: pd.DataFrame) -> pd.DataFrame:
            cols = list(df_in.columns)
            drop_cols = []
            for c in cols:
                cl = str(c).strip().lower()
                if cl == "id" or cl.endswith("_id") or cl == "index":
                    drop_cols.append(c)
            return df_in.drop(columns=drop_cols, errors="ignore")

        X_train_search = _drop_id_like_columns(
            X_train_search.select_dtypes(include=[np.number]).astype(float)
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        X_test_eval = _drop_id_like_columns(
            X_test.select_dtypes(include=[np.number]).astype(float)
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        # Configure LLM endpoint
        model_name = self._configure_openai()
        # Ensure legacy ChatCompletion API is available for older caafe versions.
        self._patch_openai_legacy_chatcompletion()
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
        iterations = int(os.environ.get("CAAFE_ITERATIONS", "15"))
        n_splits = int(os.environ.get("CAAFE_N_SPLITS", "5"))
        n_repeats = int(os.environ.get("CAAFE_N_REPEATS", "1"))

        dataset_description = (
            f"Tabular dataset for a classification task. "
            f"Rows: {len(X_train_search)} train (feature search) / {len(X_test_eval)} test (evaluation). "
            f"Features: {X_train_search.shape[1]} numeric columns."
        )

        # Train CAAFEClassifier
        feature_start = time.time()
        _restore_ipy_display = None
        _alarm_handler = None
        _alarm_active = False
        try:
            # Silence IPython Markdown display spam in non-notebook runs.
            try:
                import IPython.display as _ipd

                _restore_ipy_display = _ipd.display
                _ipd.display = lambda *args, **kwargs: None
            except Exception:
                _restore_ipy_display = None

            # Hard timeout guard: avoid endless retry loops inside caafe.
            timeout_seconds = int(os.environ.get("CAAFE_TIMEOUT_SECONDS", "600"))
            if timeout_seconds > 0:
                try:
                    import signal
                    import threading

                    if threading.current_thread() is threading.main_thread():
                        def _timeout_handler(_signum, _frame):
                            raise TimeoutError(
                                f"CAAFE fit exceeded {timeout_seconds}s (likely repeated LLM failures)."
                            )

                        _alarm_handler = signal.getsignal(signal.SIGALRM)
                        signal.signal(signal.SIGALRM, _timeout_handler)
                        signal.alarm(timeout_seconds)
                        _alarm_active = True
                except Exception:
                    _alarm_active = False

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
            df_train = X_train_search.copy()
            df_train[target_column_name] = np.asarray(y_train_search)

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
            if _alarm_active:
                try:
                    import signal
                    signal.alarm(0)
                    if _alarm_handler is not None:
                        signal.signal(signal.SIGALRM, _alarm_handler)
                except Exception:
                    pass
            if _restore_ipy_display is not None:
                try:
                    import IPython.display as _ipd
                    _ipd.display = _restore_ipy_display
                except Exception:
                    pass
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
            df_train_no_target = X_train_search.copy()
            df_train_fe = run_llm_code(self.generated_feature_code, df_train_no_target)
            df_train_fe[target_column_name] = np.asarray(y_train_search)
            df_train_fe, _, mappings = make_datasets_numeric(
                df_train_fe, df_test=None, target_column=target_column_name, return_mappings=True
            )
            df_train_x, _ = split_target_column(df_train_fe, target_column_name)

            # Apply same transformation + mappings on test (for preview only)
            df_test_fe = run_llm_code(self.generated_feature_code, X_test_eval.copy())
            df_test_fe = make_dataset_numeric(df_test_fe, mappings=mappings)

            # Keep a small preview payload in memory (train features only)
            self.generated_features = df_train_x
            self._feature_names_after_caafe = list(df_train_x.columns)
        except Exception:
            # If anything goes wrong, keep minimal info but still allow metrics
            self.generated_features = X_train.copy()
            self._feature_names_after_caafe = list(self.generated_features.columns)

        # Final model training on FULL train split + evaluate on FULL test split.
        # Feature code is generated/fitted using X_train_search only (above).
        eval_start = time.time()
        try:
            from caafe.run_llm_code import run_llm_code
            from caafe.preprocessing import make_datasets_numeric, split_target_column, make_dataset_numeric

            # Build mappings from the feature-search subset (consistent with upstream caafe preprocessing)
            target_column_name = "target"
            df_search_fe = run_llm_code(self.generated_feature_code, X_train_search.copy())
            df_search_fe[target_column_name] = np.asarray(y_train_search)
            df_search_fe, _, mappings = make_datasets_numeric(
                df_search_fe, df_test=None, target_column=target_column_name, return_mappings=True
            )

            # Apply to FULL train
            X_train_full_eval = (
                X_train.select_dtypes(include=[np.number])
                .astype(float)
                .replace([np.inf, -np.inf], np.nan)
                .fillna(0.0)
            )
            df_train_full_fe = run_llm_code(self.generated_feature_code, X_train_full_eval.copy())
            df_train_full_fe[target_column_name] = np.asarray(y_train)
            df_train_full_fe = make_dataset_numeric(df_train_full_fe, mappings=mappings)
            df_train_full_x, _ = split_target_column(df_train_full_fe, target_column_name)

            # Apply to FULL test
            df_test_full_fe = run_llm_code(self.generated_feature_code, X_test_eval.copy())
            df_test_full_fe[target_column_name] = np.asarray(y_test)
            df_test_full_fe = make_dataset_numeric(df_test_full_fe, mappings=mappings)
            df_test_full_x, _ = split_target_column(df_test_full_fe, target_column_name)

            # NaN/inf guard (Adda-style)
            df_train_full_x = df_train_full_x.replace([np.inf, -np.inf], np.nan).fillna(0.0)
            df_test_full_x = df_test_full_x.replace([np.inf, -np.inf], np.nan).fillna(0.0)

            # Align columns
            df_test_full_x = df_test_full_x.reindex(columns=list(df_train_full_x.columns), fill_value=0.0)

            # Train downstream model on FULL train split
            model = self._build_model(task_type="classify")
            fit_start = time.time()
            model.fit(df_train_full_x, y_train)
            self.training_time = time.time() - fit_start

            pred_start = time.time()
            y_pred = model.predict(df_test_full_x)
            y_prob = None
            try:
                y_prob_full = model.predict_proba(df_test_full_x)
                if y_prob_full is not None:
                    y_prob = y_prob_full[:, 1] if y_prob_full.shape[1] == 2 else y_prob_full
            except Exception:
                y_prob = None
            self.prediction_time = time.time() - pred_start

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


class SmartFeatMethod(ComparisonMethod):
    """SmartFeat: 智能统计特征生成 + 特征选择"""

    def __init__(self, model_type: str = "RF", *, max_new_features: int = 30):
        super().__init__("SmartFeat", model_type)
        self.available = True  # pure sklearn, always available
        self.max_new_features = max_new_features
        self.fitted_selector = None
        self.fitted_scaler = None
        self.selected_feature_names: List[str] = []
        self._original_feature_count_input = 0

    # ------------------------------------------------------------------
    def generate_features(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Generate statistical interaction & aggregate features, then select top-K."""
        from sklearn.preprocessing import StandardScaler
        self._original_feature_count_input = X.shape[1]

        # Encode categoricals
        X_num = X.copy()
        for col in X_num.select_dtypes(include=['object', 'category', 'bool']).columns:
            X_num[col] = pd.Categorical(X_num[col]).codes

        X_num = X_num.apply(pd.to_numeric, errors='coerce').fillna(0.0)
        X_num = X_num.replace([np.inf, -np.inf], 0.0)

        num_cols = list(X_num.columns)
        new_features: Dict[str, pd.Series] = {}

        # --- pairwise interactions (top pairs by variance) ---
        # limit to first 15 columns to keep cost manageable
        sel_cols = num_cols[:15]
        for i in range(len(sel_cols)):
            for j in range(i + 1, len(sel_cols)):
                ci, cj = sel_cols[i], sel_cols[j]
                ai, aj = X_num[ci], X_num[cj]
                new_features[f"{ci}__x__{cj}"] = ai * aj
                new_features[f"{ci}__sub__{cj}"] = ai - aj
                denom = aj.replace(0, np.nan)
                ratio = ai / denom
                new_features[f"{ci}__div__{cj}"] = ratio.fillna(0.0).replace([np.inf, -np.inf], 0.0)

        # --- unary transforms ---
        for c in sel_cols:
            s = X_num[c]
            if (s >= 0).all():
                new_features[f"{c}__sqrt"] = np.sqrt(s)
            new_features[f"{c}__sq"] = s ** 2
            new_features[f"{c}__abs"] = s.abs()

        if not new_features:
            self.generated_features = X_num
            self.selected_feature_names = list(X_num.columns)
            return X_num

        new_df = pd.DataFrame(new_features, index=X_num.index)
        # drop constant or all-NaN cols
        new_df = new_df.loc[:, new_df.nunique() > 1]
        new_df = new_df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        combined = pd.concat([X_num, new_df], axis=1)

        # --- feature selection ---
        if y is not None and combined.shape[1] > self.max_new_features:
            from sklearn.feature_selection import SelectKBest, f_classif, f_regression, mutual_info_classif, mutual_info_regression

            unique_y = len(np.unique(y.dropna()))
            if unique_y <= 20:
                score_func = mutual_info_classif
            else:
                score_func = mutual_info_regression

            k = min(self.max_new_features, combined.shape[1])
            selector = SelectKBest(score_func, k=k)
            try:
                y_clean = pd.to_numeric(y, errors='coerce').fillna(0).values
                selector.fit(combined.values, y_clean)
                mask = selector.get_support()
                combined = combined.loc[:, mask]
                self.fitted_selector = selector
            except Exception as sel_err:
                print(f"[SmartFeat] Feature selection failed: {sel_err}, keeping all")

        self.generated_features = combined
        self.selected_feature_names = list(combined.columns)
        return combined

    # ------------------------------------------------------------------
    def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify") -> Dict[str, float]:
        start_time = time.time()

        prep_start = time.time()
        X_full, y_full, complete_mask = self._encode_and_mark_complete_adda_standard(X, y)
        self.preprocessing_time = time.time() - prep_start

        self._original_feature_count_input = X_full.shape[1]

        # Split
        if task_type == "classify":
            X_train, X_test, y_train, y_test = train_test_split(
                X_full, y_full, test_size=0.2, random_state=0, stratify=y_full
            )
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X_full, y_full, test_size=0.2, random_state=0
            )

        # Feature generation on train
        feat_start = time.time()
        X_train_gen = self.generate_features(X_train, y_train)
        self.feature_generation_time = time.time() - feat_start

        # Apply same columns to test
        gen_cols = list(X_train_gen.columns)
        X_test_gen = self._apply_same_features(X_test, gen_cols)

        # Train & evaluate
        train_start = time.time()
        model = self._build_model(task_type)
        model.fit(X_train_gen.values, y_train.values)
        self.training_time = time.time() - train_start

        pred_start = time.time()
        metrics = self._evaluate(model, X_test_gen, y_test, task_type)
        self.prediction_time = time.time() - pred_start

        self.execution_time = time.time() - start_time
        return metrics

    def _apply_same_features(self, X: pd.DataFrame, gen_cols: List[str]) -> pd.DataFrame:
        """Re-create the same generated columns for test data."""
        X_num = X.copy()
        for col in X_num.select_dtypes(include=['object', 'category', 'bool']).columns:
            X_num[col] = pd.Categorical(X_num[col]).codes
        X_num = X_num.apply(pd.to_numeric, errors='coerce').fillna(0.0)
        X_num = X_num.replace([np.inf, -np.inf], 0.0)

        existing = set(X_num.columns)
        for col_name in gen_cols:
            if col_name in existing:
                continue
            if '__x__' in col_name:
                parts = col_name.split('__x__')
                if len(parts) == 2 and parts[0] in X_num.columns and parts[1] in X_num.columns:
                    X_num[col_name] = X_num[parts[0]] * X_num[parts[1]]
            elif '__sub__' in col_name:
                parts = col_name.split('__sub__')
                if len(parts) == 2 and parts[0] in X_num.columns and parts[1] in X_num.columns:
                    X_num[col_name] = X_num[parts[0]] - X_num[parts[1]]
            elif '__div__' in col_name:
                parts = col_name.split('__div__')
                if len(parts) == 2 and parts[0] in X_num.columns and parts[1] in X_num.columns:
                    denom = X_num[parts[1]].replace(0, np.nan)
                    X_num[col_name] = (X_num[parts[0]] / denom).fillna(0.0).replace([np.inf, -np.inf], 0.0)
            elif '__sqrt' in col_name:
                base = col_name.replace('__sqrt', '')
                if base in X_num.columns:
                    X_num[col_name] = np.sqrt(X_num[base].clip(lower=0))
            elif '__sq' in col_name:
                base = col_name.replace('__sq', '')
                if base in X_num.columns:
                    X_num[col_name] = X_num[base] ** 2
            elif '__abs' in col_name:
                base = col_name.replace('__abs', '')
                if base in X_num.columns:
                    X_num[col_name] = X_num[base].abs()

        X_num = X_num.reindex(columns=gen_cols, fill_value=0.0)
        X_num = X_num.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return X_num

    def _evaluate(self, model, X_test: pd.DataFrame, y_test: pd.Series, task_type: str) -> Dict[str, float]:
        y_pred = model.predict(X_test.values)
        if task_type == "classify":
            y_prob = None
            try:
                probs = model.predict_proba(X_test.values)
                y_prob = probs[:, 1] if probs.shape[1] == 2 else probs
            except Exception:
                pass
            auc = roc_auc_score(y_test, y_prob) if y_prob is not None else accuracy_score(y_test, y_pred)
            return {
                "auc": float(auc),
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "f1": float(f1_score(y_test, y_pred, average="weighted")),
                "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
            }
        else:
            y_mean = np.mean(y_test)
            rae = np.sum(np.abs(y_test - y_pred)) / (np.sum(np.abs(y_test - y_mean)) + 1e-12)
            return {
                "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
                "mse": float(mean_squared_error(y_test, y_pred)),
                "mae": float(mean_absolute_error(y_test, y_pred)),
                "r2": float(r2_score(y_test, y_pred)),
                "rae": float(rae),
                "one_minus_rae": float(1.0 - rae),
            }

    # ------------------------------------------------------------------
    def get_feature_info(self) -> Dict[str, Any]:
        if self.generated_features is not None:
            orig = int(self._original_feature_count_input)
            gen = len(self.generated_features.columns)
            return {
                "original_feature_count": orig,
                "generated_feature_count": gen,
                "new_features_count": max(0, gen - orig),
                "feature_names": list(self.generated_features.columns),
                "new_feature_names": [c for c in self.generated_features.columns
                                      if '__' in str(c)],
                "generated_features": self.generated_features,
                "description": f"SmartFeat: statistical interaction features + mutual-info selection. {gen} features ({max(0, gen - orig)} new).",
                "success": True,
            }
        return {
            "original_feature_count": 0,
            "generated_feature_count": 0,
            "new_features_count": 0,
            "feature_names": [],
            "new_feature_names": [],
            "generated_features": None,
            "description": "SmartFeat feature generation did not run.",
            "success": False,
        }


class ComparisonEngine:
    """特征工程框架对比引擎"""

    def __init__(self, db_config=None, autofeat_params=None):
        # 设置 AutoFeat 参数
        autofeat_kwargs = autofeat_params or {}

        # 从环境变量获取 featsel_runs，默认值从5增加到20
        if 'featsel_runs' not in autofeat_kwargs:
            env_featsel_runs = os.environ.get('AUTOFEAT_FEATSEL_RUNS')
            if env_featsel_runs:
                try:
                    autofeat_kwargs['featsel_runs'] = int(env_featsel_runs)
                except ValueError:
                    autofeat_kwargs['featsel_runs'] = 1  # 默认20次运行
            else:
                autofeat_kwargs['featsel_runs'] = 1  # 默认20次运行

        self.methods = {
            "Baseline": BaselineMethod(),
            "AutoFeat": AutoFeatMethod(**autofeat_kwargs),
            "PGML": PGMLMethod(db_config),
            "MADlib": MadlibMethod(db_config),
            "CAAFE": CAAFEMethod(),
            "SmartFeat": SmartFeatMethod()
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
            methods = ["Baseline", "AutoFeat", "PGML", "MADlib", "CAAFE", "SmartFeat"]

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
                "r2": [] if task_type != "classify" else None,
                # Paper-style regression score: 1 - RAE
                "rae": [] if task_type != "classify" else None,
                "one_minus_rae": [] if task_type != "classify" else None,
            },
            "time_data": {
                "methods": [],
                "totalTime": [],
                "preprocessingTime": [],
                "featureGenerationTime": [],
                "featureTransformTime": [],
                "trainingTime": [],
                "predictionTime": [],
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
                    for metric in ["one_minus_rae", "rae", "rmse", "mse", "mae", "r2"]:
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
                    "featureTransformTime": "feature_transform_time",
                    "trainingTime": "training_time",
                    "predictionTime": "prediction_time",
                    "evaluationTime": "evaluation_time",
                }
                # total_time 在少数方法里会遗漏（保持 0），这里用各阶段时间求和兜底，避免返回 0 导致前端被过滤
                computed_total = (
                    float(time_breakdown.get("preprocessing_time", 0.0))
                    + float(time_breakdown.get("feature_generation_time", 0.0))
                    + float(time_breakdown.get("feature_transform_time", 0.0))
                    + float(time_breakdown.get("training_time", 0.0))
                    + float(time_breakdown.get("prediction_time", 0.0))
                    + float(time_breakdown.get("evaluation_time", 0.0))
                )

                for time_metric in [
                    "totalTime",
                    "preprocessingTime",
                    "featureGenerationTime",
                    "featureTransformTime",
                    "trainingTime",
                    "predictionTime",
                    "evaluationTime",
                ]:
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
                print(
                    f"   - AUC: {metrics.get('auc', 0):.4f}"
                    if task_type == "classify"
                    else f"   - 1-RAE: {metrics.get('one_minus_rae', 0):.4f} (RMSE: {metrics.get('rmse', 0):.4f})"
                )
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
                    for metric in ["one_minus_rae", "rae", "rmse", "mse", "mae", "r2"]:
                        results["performance_data"][metric].append(0.0)

                for time_metric in [
                    "totalTime",
                    "preprocessingTime",
                    "featureGenerationTime",
                    "featureTransformTime",
                    "trainingTime",
                    "predictionTime",
                    "evaluationTime",
                ]:
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
            "CAAFE": "LLM-driven feature engineering with iterative verification (CAAFE).",
            "SmartFeat": "Statistical interaction features with intelligent mutual-information selection."
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
