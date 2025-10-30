// 端到端页面模拟数据
export interface FeatureInfo {
  description: string
  pythonCode: string
  sqlCode: string
}

export interface PerformanceData {
  methods: string[]
  auc: number[]
  f1: number[]
}

export interface TimeData {
  methods: string[]
  totalTime: number[]  // 秒
  trainingTime: number[]  // 秒
}

export interface FeatureImportance {
  feature: string
  importance: number
}

export interface ImportanceData {
  shap: FeatureImportance[]
  ig: FeatureImportance[]
  rfe: FeatureImportance[]
  fi: FeatureImportance[]
}

// 特征信息模拟数据
export const mockFeatureInfo: FeatureInfo = {
  description: `基于心脏病数据集生成的复合特征工程结果。

**主要特征组合：**
1. **age_group**: 将连续年龄分组（<30, 30-50, 50-70, >70）
2. **chol_risk_ratio**: 胆固醇与最大胆固醇的比值，标准化风险指标
3. **bp_category**: 血压分类（正常/高血压前期/高血压）
4. **heart_rate_reserve**: 最大心率与静息心率的差值
5. **risk_score**: 综合风险评分，基于多个临床指标

**特征工程策略：**
- 数据分箱和标准化处理
- 领域知识驱动的特征交叉
- 统计学特征变换
- 业务逻辑特征构造

这些特征在随机森林模型上表现出良好的预测能力，AUC达到0.89。`,

  pythonCode: `import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif

def create_heart_features(df):
    """
    心脏病数据集特征工程函数

    Args:
        df: 原始DataFrame，包含age, sex, cp, trestbps, chol, fbs, restecg,
            thalach, exang, oldpeak, slope, ca, thal等列

    Returns:
        processed_df: 包含新生成特征的DataFrame
    """
    df_processed = df.copy()

    # 1. 年龄分组特征
    df_processed['age_group'] = pd.cut(
        df_processed['age'],
        bins=[0, 30, 50, 70, 100],
        labels=['young', 'middle', 'senior', 'elderly']
    )

    # 2. 胆固醇风险比值
    max_chol = df_processed['chol'].max()
    df_processed['chol_risk_ratio'] = df_processed['chol'] / max_chol

    # 3. 血压分类
    def categorize_bp(bp):
        if bp < 120:
            return 'normal'
        elif bp < 140:
            return 'elevated'
        else:
            return 'high'

    df_processed['bp_category'] = df_processed['trestbps'].apply(categorize_bp)

    # 4. 心率储备
    # 估算最大心率 = 220 - 年龄
    df_processed['max_hr_estimated'] = 220 - df_processed['age']
    df_processed['heart_rate_reserve'] = (
        df_processed['max_hr_estimated'] - df_processed['thalach']
    )

    # 5. 胸痛类型严重程度评分
    cp_severity = {0: 0, 1: 1, 2: 2, 3: 3}  # 0=无症状, 3=典型心绞痛
    df_processed['cp_severity'] = df_processed['cp'].map(cp_severity)

    # 6. ST段压差与年龄比值
    df_processed['oldpeak_age_ratio'] = (
        df_processed['oldpeak'] / df_processed['age']
    )

    # 7. 综合风险评分
    def calculate_risk_score(row):
        score = 0
        # 年龄风险
        if row['age'] > 60:
            score += 2
        elif row['age'] > 45:
            score += 1

        # 胆固醇风险
        if row['chol'] > 240:
            score += 2
        elif row['chol'] > 200:
            score += 1

        # 血压风险
        if row['trestbps'] > 140:
            score += 2
        elif row['trestbps'] > 120:
            score += 1

        # 胸痛风险
        if row['cp'] in [1, 2]:  # 典型心绞痛
            score += 2

        # 运动诱发心绞痛
        if row['exang'] == 1:
            score += 1

        return score

    df_processed['risk_score'] = df_processed.apply(calculate_risk_score, axis=1)

    # 8. 血糖血压组合指标
    df_processed['glucose_bp_product'] = df_processed['fbs'] * df_processed['trestbps']

    # 9. 心电图异常指标
    df_processed['ecg_abnormal'] = (df_processed['restecg'] != 0).astype(int)

    # 10. 血管数量与年龄交互
    df_processed['ca_age_interaction'] = df_processed['ca'] * (df_processed['age'] / 100)

    # 数值特征标准化
    numeric_features = [
        'chol_risk_ratio', 'heart_rate_reserve', 'oldpeak_age_ratio',
        'risk_score', 'glucose_bp_product', 'ca_age_interaction'
    ]

    scaler = StandardScaler()
    df_processed[numeric_features] = scaler.fit_transform(df_processed[numeric_features])

    # 分类特征编码
    categorical_features = ['age_group', 'bp_category']
    df_processed = pd.get_dummies(df_processed, columns=categorical_features, drop_first=True)

    return df_processed

# 使用示例
if __name__ == "__main__":
    # 加载数据
    heart_data = pd.read_csv('heart.csv')

    # 创建特征
    engineered_features = create_heart_features(heart_data)

    print(f"原始特征数量: {heart_data.shape[1]}")
    print(f"工程后特征数量: {engineered_features.shape[1]}")
    print("\\n生成的特征列表:")
    for col in engineered_features.columns:
        if col not in heart_data.columns:
            print(f"  - {col}")`,

  sqlCode: `-- 心脏病特征工程SQL实现
-- 基于UCI心脏病数据集的特征生成

WITH
-- 1. 年龄分组特征
age_groups AS (
    SELECT
        *,
        CASE
            WHEN age < 30 THEN 'young'
            WHEN age < 50 THEN 'middle'
            WHEN age < 70 THEN 'senior'
            ELSE 'elderly'
        END as age_group,
        -- 年龄数值分组编码
        CASE
            WHEN age < 30 THEN 0
            WHEN age < 50 THEN 1
            WHEN age < 70 THEN 2
            ELSE 3
        END as age_group_encoded
    FROM heart_data
),

-- 2. 计算胆固醇统计值用于标准化
chol_stats AS (
    SELECT
        MAX(chol) as max_chol,
        AVG(chol) as avg_chol,
        STDDEV(chol) as std_chol
    FROM heart_data
),

-- 3. 主要特征计算
feature_engineering AS (
    SELECT
        ag.*,
        cs.max_chol,

        -- 胆固醇风险比值
        ROUND(ag.chol::NUMERIC / cs.max_chol, 4) as chol_risk_ratio,

        -- 血压分类
        CASE
            WHEN trestbps < 120 THEN 'normal'
            WHEN trestbps < 140 THEN 'elevated'
            ELSE 'high'
        END as bp_category,

        -- 血压分类编码
        CASE
            WHEN trestbps < 120 THEN 0
            WHEN trestbps < 140 THEN 1
            ELSE 2
        END as bp_category_encoded,

        -- 估算最大心率
        220 - ag.age as max_hr_estimated,

        -- 心率储备
        (220 - ag.age) - ag.thalach as heart_rate_reserve,

        -- 胸痛严重程度评分
        CASE cp
            WHEN 0 THEN 0  -- 无症状
            WHEN 1 THEN 2  -- 典型心绞痛
            WHEN 2 THEN 3  -- 非典型心绞痛
            WHEN 3 THEN 1  -- 非心绞痛疼痛
        END as cp_severity,

        -- ST段压差与年龄比值
        ROUND(ag.oldpeak::NUMERIC / NULLIF(ag.age, 0), 4) as oldpeak_age_ratio

    FROM age_groups ag, chol_stats cs
),

-- 4. 综合风险评分计算
risk_scoring AS (
    SELECT
        *,
        -- 年龄风险评分
        CASE
            WHEN age > 60 THEN 2
            WHEN age > 45 THEN 1
            ELSE 0
        END +
        -- 胆固醇风险评分
        CASE
            WHEN chol > 240 THEN 2
            WHEN chol > 200 THEN 1
            ELSE 0
        END +
        -- 血压风险评分
        CASE
            WHEN trestbps > 140 THEN 2
            WHEN trestbps > 120 THEN 1
            ELSE 0
        END +
        -- 胸痛风险评分
        CASE
            WHEN cp IN (1, 2) THEN 2
            ELSE 0
        END +
        -- 运动诱发心绞痛评分
        exang +
        -- ST段异常评分
        CASE
            WHEN oldpeak > 2.0 THEN 2
            WHEN oldpeak > 1.0 THEN 1
            ELSE 0
        END as risk_score

    FROM feature_engineering
),

-- 5. 最终特征集合
final_features AS (
    SELECT
        -- 原始ID
        id,

        -- 数值特征（需要后续标准化）
        chol_risk_ratio,
        heart_rate_reserve,
        oldpeak_age_ratio,
        risk_score,

        -- 血糖血压组合指标
        fbs * trestbps as glucose_bp_product,

        -- 心电图异常指标
        CASE WHEN restecg != 0 THEN 1 ELSE 0 END as ecg_abnormal,

        -- 血管数量与年龄交互
        ROUND(ca * (age::NUMERIC / 100), 4) as ca_age_interaction,

        -- 分类特征编码
        age_group_encoded,
        bp_category_encoded,
        cp_severity,

        -- 标记字段
        age_group,
        bp_category,

        -- 保持原始字段用于模型训练
        age, sex, cp, trestbps, chol, fbs, restecg,
        thalach, exang, oldpeak, slope, ca, thal, target

    FROM risk_scoring
)

-- 最终结果
SELECT
    ff.*,

    -- 特征标准化（使用Z-score标准化）
    ROUND((ff.chol_risk_ratio - sub.chol_risk_avg) / NULLIF(sub.chol_risk_std, 0), 4) as chol_risk_ratio_std,
    ROUND((ff.heart_rate_reserve - sub.hr_reserve_avg) / NULLIF(sub.hr_reserve_std, 0), 4) as heart_rate_reserve_std,
    ROUND((ff.risk_score - sub.risk_score_avg) / NULLIF(sub.risk_score_std, 0), 4) as risk_score_std

FROM final_features ff
CROSS JOIN (
    SELECT
        AVG(chol_risk_ratio) as chol_risk_avg,
        STDDEV(chol_risk_ratio) as chol_risk_std,
        AVG(heart_rate_reserve) as hr_reserve_avg,
        STDDEV(heart_rate_reserve) as hr_reserve_std,
        AVG(risk_score) as risk_score_avg,
        STDDEV(risk_score) as risk_score_std
    FROM final_features
) sub
ORDER BY id;

-- 特征统计摘要查询
SELECT
    'Feature Statistics' as analysis_type,
    COUNT(*) as total_records,
    COUNT(DISTINCT age_group) as unique_age_groups,
    COUNT(DISTINCT bp_category) as unique_bp_categories,
    AVG(risk_score) as avg_risk_score,
    MAX(risk_score) as max_risk_score,
    MIN(risk_score) as min_risk_score
FROM final_features;

-- 特征重要性查询（基于相关性）
SELECT
    'Feature Correlation with Target' as analysis_type,
    feature_name,
    ROUND(correlation_coefficient, 4) as correlation_with_target,
    ROUND(abs(correlation_coefficient), 4) as absolute_importance
FROM (
    SELECT
        'chol_risk_ratio' as feature_name,
        CORR(chol_risk_ratio, target) as correlation_coefficient
    FROM final_features

    UNION ALL

    SELECT
        'heart_rate_reserve' as feature_name,
        CORR(heart_rate_reserve, target) as correlation_coefficient
    FROM final_features

    UNION ALL

    SELECT
        'risk_score' as feature_name,
        CORR(risk_score, target) as correlation_coefficient
    FROM final_features
) importance_analysis
ORDER BY absolute_importance DESC;`
}

// 性能对比模拟数据
export const mockPerformanceData: PerformanceData = {
  methods: ['Adda', 'AutoFeat', 'FeatureTools', 'DeepFeatureSynthesis'],
  auc: [0.89, 0.82, 0.79, 0.85],
  f1: [0.87, 0.80, 0.77, 0.83]
}

// 用时对比模拟数据
export const mockTimeData: TimeData = {
  methods: ['Adda', 'AutoFeat', 'FeatureTools', 'DeepFeatureSynthesis'],
  totalTime: [120, 180, 95, 240],  // 秒
  trainingTime: [45, 120, 60, 180]  // 秒
}

// 特征重要性模拟数据
export const mockImportanceData: ImportanceData = {
  shap: [
    { feature: 'age_group', importance: 0.24 },
    { feature: 'chol_risk_ratio', importance: 0.18 },
    { feature: 'heart_rate_reserve', importance: 0.15 },
    { feature: 'risk_score', importance: 0.12 },
    { feature: 'bp_category', importance: 0.10 },
    { feature: 'oldpeak_age_ratio', importance: 0.08 },
    { feature: 'cp_severity', importance: 0.07 },
    { feature: 'ca_age_interaction', importance: 0.06 }
  ],
  ig: [
    { feature: 'age_group', importance: 0.31 },
    { feature: 'chol_risk_ratio', importance: 0.22 },
    { feature: 'risk_score', importance: 0.18 },
    { feature: 'heart_rate_reserve', importance: 0.12 },
    { feature: 'bp_category', importance: 0.09 },
    { feature: 'cp_severity', importance: 0.05 },
    { feature: 'oldpeak_age_ratio', importance: 0.03 }
  ],
  rfe: [
    { feature: 'age_group', importance: 0.28 },
    { feature: 'risk_score', importance: 0.20 },
    { feature: 'chol_risk_ratio', importance: 0.16 },
    { feature: 'heart_rate_reserve', importance: 0.14 },
    { feature: 'bp_category', importance: 0.11 },
    { feature: 'cp_severity', importance: 0.06 },
    { feature: 'oldpeak_age_ratio', importance: 0.05 }
  ],
  fi: [
    { feature: 'age_group', importance: 0.26 },
    { feature: 'chol_risk_ratio', importance: 0.19 },
    { feature: 'risk_score', importance: 0.17 },
    { feature: 'heart_rate_reserve', importance: 0.13 },
    { feature: 'bp_category', importance: 0.10 },
    { feature: 'cp_severity', importance: 0.08 },
    { feature: 'ca_age_interaction', importance: 0.04 },
    { feature: 'glucose_bp_product', importance: 0.03 }
  ]
}