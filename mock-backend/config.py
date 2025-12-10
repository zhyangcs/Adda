"""
Mock Backend Configuration
模拟ADDA后端的配置文件
"""

# Flask配置（与真实后端网络配置保持一致）
DEBUG = True
# 监听 0.0.0.0，便于通过本机 IP 访问（例如 10.82.1.203:5000）
HOST = '0.0.0.0'
PORT = 5000

# CORS配置：mock 环境仅单独运行，放宽为全部允许，方便前端从任意 Origin 调试
CORS_ORIGINS = ["*"]

# 数据集配置
DATASETS = {
    '1': 'Titanic',
    '2': 'Heart',
    '3': 'Bank',
    '4': 'Diabetes',
    '5': 'Bike',
    '6': 'House'
}

# LLM模型配置
LLM_MODELS = {
    '1': 'Openai-gpt4-turbo',
    '2': 'Openai-gpt4o',
    '3': 'Openai-gpt4o-mini',
    '4': 'Deepseek-v3'
}

# ML模型配置
ML_MODELS = ['RF', 'XGB', 'LightGBM']

# 模拟延迟配置（秒）
SIMULATION_DELAYS = {
    'check_format': 1.0,
    'get_treejson': 0.5,
    'next_step': 8.0,  # 模拟真实的特征生成时间
    'auto_step': 12.0, # 模拟端到端执行
    'test_performance': 3.0,
    'gen_model': 2.0
}

# Mock数据配置
MAX_NODES_PER_TREE = 15
MAX_EXECUTION_STEPS = 8

# 性能基准配置
PERFORMANCE_BASELINES = {
    'Titanic': {'base_auc': 0.78, 'variance': 0.05},
    'Heart': {'base_auc': 0.82, 'variance': 0.04},
    'Bank': {'base_auc': 0.75, 'variance': 0.06},
    'Diabetes': {'base_auc': 0.80, 'variance': 0.03},
    'Bike': {'base_auc': 0.70, 'variance': 0.08},
    'House': {'base_auc': 0.85, 'variance': 0.02}
}

# 特征操作模板
FEATURE_OPERATIONS = [
    {
        'name': 'risk_score_v2',
        'code': "df['risk_score_v2'] = df['age'] * 0.3 + df['chol'] * 0.2 + df['thalach'] * 0.5",
        'desc': '计算心血管风险分数v2，结合年龄、胆固醇和最大心率',
        'op_type': 'Transformation'
    },
    {
        'name': 'bmi_category',
        'code': "df['bmi_category'] = pd.cut(df['bmi'], bins=[0, 18.5, 25, 30, float('inf')], labels=['Underweight', 'Normal', 'Overweight', 'Obese'])",
        'desc': '根据BMI值创建体重分类',
        'op_type': 'Binning'
    },
    {
        'name': 'age_chol_interaction',
        'code': "df['age_chol_interaction'] = df['age'] * df['chol']",
        'desc': '年龄和胆固醇的交互特征',
        'op_type': 'Interaction'
    },
    {
        'name': 'log_transform_fbs',
        'code': "df['log_transform_fbs'] = np.log1p(df['fbs'])",
        'desc': '对空腹血糖进行对数变换',
        'op_type': 'Transformation'
    },
    {
        'name': 'cp_thalach_ratio',
        'code': "df['cp_thalach_ratio'] = df['cp'] / df['thalach']",
        'desc': '胸痛类型与最大心率的比值',
        'op_type': 'Ratio'
    },
    {
        'name': 'scaled_oldpeak',
        'code': "df['scaled_oldpeak'] = (df['oldpeak'] - df['oldpeak'].mean()) / df['oldpeak'].std()",
        'desc': '标准化ST段压低值',
        'op_type': 'Scaling'
    }
]

# SQL代码模板
SQL_TEMPLATES = {
    'training_sql': """
-- 训练数据准备
CREATE TABLE training_features AS
SELECT
    {feature_columns},
    target_column
FROM source_table
WHERE split = 'train';

-- 模型训练
SELECT * FROM train_random_forest(
    'training_features',
    '{target_column}',
    '{model_params}'
);
""",
    'prediction_sql': """
-- 预测数据准备
CREATE TABLE prediction_features AS
SELECT
    {feature_columns}
FROM source_table
WHERE split = 'test';

-- 模型预测
SELECT id, predict_random_forest({feature_values}) AS prediction
FROM prediction_features;
""",
    'udf_sql': """
-- 创建特征工程UDF
CREATE OR REPLACE FUNCTION feature_engineering_udf(
    input_params JSON
) RETURNS JSON AS $$
BEGIN
    -- 特征转换逻辑
    RETURN transformed_features;
END;
$$ LANGUAGE plpython3u;
""",
    'all_sql': """
-- 完整的特征工程和ML流程
{training_sql}
{prediction_sql}
{udf_sql}
"""
}