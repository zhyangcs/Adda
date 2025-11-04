"""
Mock数据生成器
提供模拟ADDA系统的假数据
"""

import random
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any
from config import DATASETS, LLM_MODELS, ML_MODELS, PERFORMANCE_BASELINES, FEATURE_OPERATIONS


class MockDataGenerator:
    """Mock数据生成器类"""

    def __init__(self):
        self.tasks = {}
        self.notifications = []
        self.execution_states = {}
        self.tree_states = {}  # 存储每个任务的特征树状态

    def create_task(self, task_description: str, dataset_id: str, model_id: str) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        dataset_name = DATASETS.get(dataset_id, 'Unknown')
        model_name = LLM_MODELS.get(model_id, 'Openai-gpt4o')

        task = {
            'task_id': task_id,
            'task_description': task_description,
            'dataset': dataset_name,
            'dataset_id': dataset_id,
            'model': model_name,
            'model_id': model_id,
            'created_at': datetime.now().isoformat(),
            'status': 'initialized',
            'current_step': 0,
            'max_steps': random.randint(5, 12)
        }

        self.tasks[task_id] = task

        # 初始化特征树状态（只有根节点）
        self.tree_states[task_id] = {
            'nodes': {
                '1': {
                    'node_id': '1',
                    'feature_name': 'All original features',
                    'task_code': '# Root node - original dataset features',
                    'op_type': 'root',
                    'score': 0.0,
                    'exec_time': 0.0,
                    'operation_desc': f'Original feature root node for {dataset_name} dataset',
                    'expanded': False  # Whether it has been expanded
                }
            },
            'relations': [],
            'next_node_id': 2,
            'root_id': '1'
        }

        self.add_notification(f"Task created: {task_description}", 'success')
        return task_id

    def add_notification(self, message: str, notice_type: str = 'info'):
        """Add notification"""
        notification = {
            'id': str(uuid.uuid4()),
            'notice_description': message,
            'notice_type': notice_type,
            'timestamp': datetime.now().isoformat()
        }
        self.notifications.append(notification)
        # Keep only the last 50 notifications
        if len(self.notifications) > 50:
            self.notifications = self.notifications[-50:]

    def expand_tree(self, task_id: str) -> Dict[str, Any]:
        """Expand feature tree: select an unexpanded node and generate 3 child nodes"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'fail', 'message': 'Task does not exist'}

        tree_state = self.tree_states.get(task_id)
        if not tree_state:
            return {'status': 'fail', 'message': 'Feature tree state does not exist'}

        # 找到未扩展的节点（包括根节点）
        unexpanded_nodes = [node_id for node_id, node in tree_state['nodes'].items()
                           if not node.get('expanded', False)]

        if not unexpanded_nodes:
            return {'status': 'fail', 'message': 'All nodes have been expanded'}

        # Select a node to expand (choose the first one)
        parent_id = unexpanded_nodes[0]

        # Mark parent node as expanded
        tree_state['nodes'][parent_id]['expanded'] = True

        # Generate 3 child nodes
        new_nodes = []
        dataset = task['dataset']
        base_performance = PERFORMANCE_BASELINES.get(dataset, {'base_auc': 0.75, 'variance': 0.05})

        # Select appropriate feature operation templates based on dataset
        feature_templates = self._get_feature_templates_for_dataset(dataset)

        for i in range(3):
            node_id = str(tree_state['next_node_id'])
            tree_state['next_node_id'] += 1

            template = feature_templates[i % len(feature_templates)]

            # 计算性能分数
            base_score = base_performance['base_auc']
            variance = base_performance['variance']
            score = base_score + random.uniform(0.02, 0.15) + random.uniform(-variance, variance)
            score = max(0.5, min(0.95, score))

            new_node = {
                'node_id': node_id,
                'feature_name': template['name'],
                'task_code': template['code'],
                'op_type': template['op_type'],
                'score': round(score, 4),
                'exec_time': round(random.uniform(0.1, 2.0), 3),
                'operation_desc': template['desc'],
                'expanded': False
            }

            tree_state['nodes'][node_id] = new_node
            tree_state['relations'].append([parent_id, node_id])
            new_nodes.append(new_node)

        return {
            'status': 'success',
            'message': f'Node {parent_id} expansion completed, generated 3 new features',
            'new_nodes': new_nodes,
            'parent_id': parent_id
        }

    def _get_feature_templates_for_dataset(self, dataset: str) -> List[Dict]:
        """根据数据集返回合适的特征操作模板"""
        if dataset in ['Heart', 'Titanic']:
            return [
                {
                    'name': 'age_binning',
                    'code': "df['age_group'] = pd.cut(df['age'], bins=[0, 25, 50, 75, 100], labels=['Young', 'Adult', 'Middle', 'Senior'])",
                    'op_type': 'Binning',
                    'desc': 'Age grouping feature engineering'
                },
                {
                    'name': 'risk_interaction',
                    'code': "df['risk_interaction'] = df['chol'] * df['trestbps'] / 1000",
                    'op_type': 'Interaction',
                    'desc': 'Cholesterol and blood pressure interaction feature'
                },
                {
                    'name': 'normalized_thalach',
                    'code': "df['norm_thalach'] = (df['thalach'] - df['thalach'].mean()) / df['thalach'].std()",
                    'op_type': 'Scaling',
                    'desc': 'Normalized maximum heart rate feature'
                }
            ]
        else:
            # General feature operations
            return [
                {
                    'name': 'log_transform',
                    'code': "df['log_feature'] = np.log1p(df['numeric_feature'])",
                    'op_type': 'Transformation',
                    'desc': 'Logarithmic transformation feature'
                },
                {
                    'name': 'feature_interaction',
                    'code': "df['interaction'] = df['feature1'] * df['feature2']",
                    'op_type': 'Interaction',
                    'desc': 'Feature interaction'
                },
                {
                    'name': 'feature_scaling',
                    'code': "df['scaled_feature'] = (df['feature'] - df['feature'].mean()) / df['feature'].std()",
                    'op_type': 'Scaling',
                    'desc': 'Feature standardization'
                }
            ]

    def generate_jsontree(self, task_id: str) -> Dict[str, Any]:
        """Generate feature tree JSON data"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'fail', 'message': 'Task does not exist'}

        tree_state = self.tree_states.get(task_id)
        if not tree_state:
            return {'status': 'fail', 'message': 'Feature tree state does not exist'}

        # Convert to frontend format
        nodes = list(tree_state['nodes'].values())
        relations = tree_state['relations']

        # Select some leaf nodes as currently selected (excluding root node)
        leaf_nodes = [node_id for node_id, node in tree_state['nodes'].items()
                     if node_id != '1' and not any(rel[0] == node_id for rel in relations)]
        selected_nodes = leaf_nodes[:2] if len(leaf_nodes) >= 2 else leaf_nodes

        tree_data = {
            'root_id': tree_state['root_id'],
            'parent_child_relations': relations,
            'node_info': nodes,
            'cur_selected_idx': selected_nodes
        }

        return {
            'status': 'success',
            'json': tree_data
        }

    def generate_performance_metrics(self, task_id: str, selected_nodes: List[str],
                                   model_type: str = 'RF', use_in_db_ml: bool = True) -> Dict[str, Any]:
        """生成性能测试结果"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'fail', 'message': 'Task does not exist'}

        dataset = task['dataset']
        base_performance = PERFORMANCE_BASELINES.get(dataset, {'base_auc': 0.75, 'variance': 0.05})

        # 基于选中节点数量和类型计算性能
        node_count = len(selected_nodes)
        base_score = base_performance['base_auc']

        # 更多节点通常带来更好的性能
        node_bonus = min(node_count * 0.03, 0.15)
        # 不同模型类型的性能差异
        model_bonus = {'RF': 0.0, 'XGB': 0.02, 'LightGBM': 0.01}.get(model_type, 0.0)
        # in-database ML的性能提升
        in_db_bonus = 0.02 if use_in_db_ml else 0.0

        final_score = base_score + node_bonus + model_bonus + in_db_bonus + random.uniform(-0.02, 0.02)
        final_score = max(0.5, min(0.98, final_score))

        # 生成SQL代码
        feature_columns = [f"feature_{i}" for i in range(node_count)]
        sql_code = self._generate_sql_code(feature_columns, model_type)

        return {
            'status': 'success',
            'message': f'Performance test completed, using {len(selected_nodes)} features',
            'performance_info': {
                'score': round(final_score, 4),
                'metric': 'AUC',
                'selected_nodes': selected_nodes,
                'in_db_ml': use_in_db_ml,
                'node_count': node_count,
                'method': f'{model_type} {"(In-Database)" if use_in_db_ml else "(Simulation)"}'
            },
            'sql_code': sql_code,
            'sql_file_paths': {
                'training_sql_path': f'/tmp/training_{task_id[:8]}.sql',
                'prediction_sql_path': f'/tmp/prediction_{task_id[:8]}.sql',
                'udf_sql_path': f'/tmp/udf_{task_id[:8]}.sql'
            }
        }

    def _generate_sql_code(self, feature_columns: List[str], model_type: str) -> Dict[str, str]:
        """生成SQL代码"""
        feature_list = ', '.join(feature_columns)
        model_params = f"n_estimators=100, max_depth=10, model_type='{model_type}'"

        return {
            'training_sql': f"""
-- 训练数据准备
CREATE TABLE training_features AS
SELECT {feature_list}, target_column
FROM source_table
WHERE split = 'train';

-- {model_type}模型训练
SELECT * FROM train_{model_type.lower()}(
    'training_features',
    'target_column',
    '{model_params}'
);
""".strip(),
            'prediction_sql': f"""
-- 预测数据准备
CREATE TABLE prediction_features AS
SELECT {feature_list}
FROM source_table
WHERE split = 'test';

-- 模型预测
SELECT id, predict_{model_type.lower()}({feature_list}) AS prediction
FROM prediction_features;
""".strip(),
            'udf_sql': f"""
-- 创建{model_type}特征工程UDF
CREATE OR REPLACE FUNCTION feature_engineering_{model_type.lower()}(
    input_params JSON
) RETURNS JSON AS $$
import json
import pandas as pd
def transform_features(params):
    # 特征转换逻辑
    result = {{
        'transformed_features': [],
        'model_type': '{model_type}',
        'timestamp': datetime.now().isoformat()
    }}
    return json.dumps(result)
$$ LANGUAGE plpython3u;
""".strip(),
            'all_sql': f"""
-- 完整的{model_type}特征工程和ML流程
-- 步骤1: 数据预处理
-- 步骤2: 特征工程
-- 步骤3: 模型训练
-- 步骤4: 模型预测
""".strip()
        }

    def generate_auto_step_result(self, task_description: str, dataset: str,
                                model_type: str = 'RF', max_search_depth: int = 2) -> Dict[str, Any]:
        """生成端到端自动化执行结果"""
        # 模拟搜索过程
        actual_depth = random.randint(1, max_search_depth)
        node_count = random.randint(5, 15)

        # 创建新任务（用于auto-step）
        dataset_id = '2'  # 默认使用Heart数据集
        model_id = '2'   # 默认使用Openai-gpt4o
        task_id = self.create_task(task_description, dataset_id, model_id)

        # 扩展特征树多次以生成足够的节点
        for _ in range(actual_depth):
            expand_result = self.expand_tree(task_id)
            if expand_result['status'] == 'fail':
                break

        # 生成特征树
        tree_result = self.generate_jsontree(task_id)

        # 确保tree_result包含有效数据
        if tree_result['status'] != 'success' or 'json' not in tree_result:
            # 如果生成失败，创建一个基本的树结构
            tree_result = {
                'status': 'success',
                'json': {
                    'root_id': '1',
                    'parent_child_relations': [],
                    'node_info': [{
                        'node_id': '1',
                        'feature_name': 'All original features',
                        'task_code': '# Root node - original dataset features',
                        'op_type': 'root',
                        'score': 0.0,
                        'exec_time': 0.0,
                        'operation_desc': f'Original feature root node for {dataset} dataset',
                        'expanded': False
                    }],
                    'cur_selected_idx': []
                }
            }

        # 生成性能指标
        base_performance = PERFORMANCE_BASELINES.get(dataset, {'base_auc': 0.75, 'variance': 0.05})
        final_score = base_performance['base_auc'] + random.uniform(0.05, 0.15)
        final_score = max(0.6, min(0.95, final_score))

        execution_time = random.uniform(30, 120)  # 30-120秒执行时间

        # 生成最佳特征信息
        node_info = tree_result['json']['node_info']
        best_node = node_info[1] if len(node_info) > 1 else node_info[0]

        return {
            'status': 'success',
            'message': f'End-to-end automated feature engineering completed, search depth {actual_depth}, generated {node_count} features',
            'tree': tree_result['json'],
            'finished': True,
            'search_depth': actual_depth,
            'performance_metrics': {
                'auc': round(final_score, 4),
                'execution_time': round(execution_time, 2),
                'model_type': model_type,
                'task_name': dataset,
                'task_type': 'classification',
                'row_num': random.randint(800, 5000),
                'col_num': random.randint(10, 50),
                'method': f'{model_type}_auto_ml'
            },
            'sql_code': self._generate_sql_code(
                [f'feature_{i}' for i in range(random.randint(3, 8))],
                model_type
            ),
            'best_features': {
                'success': True,
                'node_id': best_node['node_id'],
                'final_score': best_node['score'],
                'python_code': best_node['task_code'],
                'sql_code': f"SELECT {best_node['feature_name']} FROM processed_data;",
                'feature_descriptions': [best_node['operation_desc']],
                'feature_count': len(tree_result['json']['node_info']) - 1,
                'operation_desc': best_node['operation_desc'],
                'exec_time': best_node['exec_time']
            },
            'training_result': {
                'success': True,
                'message': f'{model_type} model training completed',
                'model_type': model_type,
                'method': 'auto_ml_pipeline'
            }
        }

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'fail', 'initialized': False, 'message': '任务不存在'}

        return {
            'status': 'success',
            'initialized': True,
            'message': f"Task '{task['task_description']}' initialized"
        }

    def stop_task(self, task_id: str) -> Dict[str, Any]:
        """Stop task"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'fail', 'message': 'Task does not exist'}

        task['status'] = 'stopped'
        self.add_notification(f"Task stopped: {task['task_description']}", 'info')

        return {
            'status': 'success',
            'message': 'Task stopped successfully'
        }

    def clear_task(self, task_id: str) -> Dict[str, Any]:
        """Clear task"""
        if task_id in self.tasks:
            task_desc = self.tasks[task_id]['task_description']
            del self.tasks[task_id]
            self.add_notification(f"Task cleared: {task_desc}", 'info')

        return {
            'status': 'success',
            'message': 'Task state cleared'
        }

    def get_all_e2e_data(self) -> Dict[str, Any]:
        """获取所有端到端页面数据"""
        feature_info = {
            'description': """基于心脏病数据集生成的复合特征工程结果。

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

这些特征在随机森林模型上表现出良好的预测能力，AUC达到0.89。""",
            'pythonCode': '''import pandas as pd
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
    print("\\\\n生成的特征列表:")
    for col in engineered_features.columns:
        if col not in heart_data.columns:
            print(f"  - {col}")''',
            'sqlCode': '''-- 心脏病特征工程SQL实现
-- 基于UCI心脏病数据集的特征生成

WITH
-- 1. 年龄分组特征
age_groups AS (
    SELECT
        *,
        CASE
            WHEN age < 30 THEN \'young\'
            WHEN age < 50 THEN \'middle\'
            WHEN age < 70 THEN \'senior\'
            ELSE \'elderly\'
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
            WHEN trestbps < 120 THEN \'normal\'
            WHEN trestbps < 140 THEN \'elevated\'
            ELSE \'high\'
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
ORDER BY id;'''
        }

        performance_data = {
            'methods': ['Adda', 'AutoFeat', 'FeatureTools', 'DeepFeatureSynthesis'],
            'auc': [0.89, 0.82, 0.79, 0.85],
            'f1': [0.87, 0.80, 0.77, 0.83]
        }

        time_data = {
            'methods': ['Adda', 'AutoFeat', 'FeatureTools', 'DeepFeatureSynthesis'],
            'totalTime': [120, 180, 95, 240],  # 秒
            'trainingTime': [45, 120, 60, 180]  # 秒
        }

        importance_data = {
            'shap': [
                {'feature': 'age_group', 'importance': 0.24},
                {'feature': 'chol_risk_ratio', 'importance': 0.18},
                {'feature': 'heart_rate_reserve', 'importance': 0.15},
                {'feature': 'risk_score', 'importance': 0.12},
                {'feature': 'bp_category', 'importance': 0.10},
                {'feature': 'oldpeak_age_ratio', 'importance': 0.08},
                {'feature': 'cp_severity', 'importance': 0.07},
                {'feature': 'ca_age_interaction', 'importance': 0.06}
            ],
            'ig': [
                {'feature': 'age_group', 'importance': 0.31},
                {'feature': 'chol_risk_ratio', 'importance': 0.22},
                {'feature': 'risk_score', 'importance': 0.18},
                {'feature': 'heart_rate_reserve', 'importance': 0.12},
                {'feature': 'bp_category', 'importance': 0.09},
                {'feature': 'cp_severity', 'importance': 0.05},
                {'feature': 'oldpeak_age_ratio', 'importance': 0.03}
            ],
            'rfe': [
                {'feature': 'age_group', 'importance': 0.28},
                {'feature': 'risk_score', 'importance': 0.20},
                {'feature': 'chol_risk_ratio', 'importance': 0.16},
                {'feature': 'heart_rate_reserve', 'importance': 0.14},
                {'feature': 'bp_category', 'importance': 0.11},
                {'feature': 'cp_severity', 'importance': 0.06},
                {'feature': 'oldpeak_age_ratio', 'importance': 0.05}
            ],
            'fi': [
                {'feature': 'age_group', 'importance': 0.26},
                {'feature': 'chol_risk_ratio', 'importance': 0.19},
                {'feature': 'risk_score', 'importance': 0.17},
                {'feature': 'heart_rate_reserve', 'importance': 0.13},
                {'feature': 'bp_category', 'importance': 0.10},
                {'feature': 'cp_severity', 'importance': 0.08},
                {'feature': 'ca_age_interaction', 'importance': 0.04},
                {'feature': 'glucose_bp_product', 'importance': 0.03}
            ]
        }

        return {
            'status': 'success',
            'data': {
                'featureInfo': feature_info,
                'performanceData': performance_data,
                'timeData': time_data,
                'importanceData': importance_data
            }
        }

    def get_notifications(self) -> Dict[str, Any]:
        """获取通知列表"""
        return {
            'notifications': [
                {
                    'notice_description': n['notice_description'],
                    'notice_type': n['notice_type']
                }
                for n in sorted(self.notifications, key=lambda x: x['timestamp'], reverse=True)[:20]
            ]
        }


# 全局Mock数据生成器实例
mock_generator = MockDataGenerator()