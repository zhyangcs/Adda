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
                    'operation_desc': f'{dataset_name}数据集的原始特征根节点',
                    'expanded': False  # 是否已扩展过
                }
            },
            'relations': [],
            'next_node_id': 2,
            'root_id': '1'
        }

        self.add_notification(f"任务已创建: {task_description}", 'success')
        return task_id

    def add_notification(self, message: str, notice_type: str = 'info'):
        """添加通知"""
        notification = {
            'id': str(uuid.uuid4()),
            'notice_description': message,
            'notice_type': notice_type,
            'timestamp': datetime.now().isoformat()
        }
        self.notifications.append(notification)
        # 保持最近50条通知
        if len(self.notifications) > 50:
            self.notifications = self.notifications[-50:]

    def expand_tree(self, task_id: str) -> Dict[str, Any]:
        """扩展特征树：选择一个未扩展的节点，生成3个子节点"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'fail', 'message': '任务不存在'}

        tree_state = self.tree_states.get(task_id)
        if not tree_state:
            return {'status': 'fail', 'message': '特征树状态不存在'}

        # 找到未扩展的节点（包括根节点）
        unexpanded_nodes = [node_id for node_id, node in tree_state['nodes'].items()
                           if not node.get('expanded', False)]

        if not unexpanded_nodes:
            return {'status': 'fail', 'message': '所有节点都已扩展'}

        # 选择一个节点进行扩展（这里选择第一个）
        parent_id = unexpanded_nodes[0]

        # 标记父节点为已扩展
        tree_state['nodes'][parent_id]['expanded'] = True

        # 生成3个子节点
        new_nodes = []
        dataset = task['dataset']
        base_performance = PERFORMANCE_BASELINES.get(dataset, {'base_auc': 0.75, 'variance': 0.05})

        # 根据数据集选择合适的特征操作模板
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
            'message': f'节点{parent_id}扩展完成，生成了3个新特征',
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
                    'desc': '将年龄分组，创建年龄段特征'
                },
                {
                    'name': 'risk_interaction',
                    'code': "df['risk_interaction'] = df['chol'] * df['trestbps'] / 1000",
                    'op_type': 'Interaction',
                    'desc': '胆固醇和血压的交互特征'
                },
                {
                    'name': 'normalized_thalach',
                    'code': "df['norm_thalach'] = (df['thalach'] - df['thalach'].mean()) / df['thalach'].std()",
                    'op_type': 'Scaling',
                    'desc': '标准化最大心率特征'
                }
            ]
        else:
            # 通用特征操作
            return [
                {
                    'name': 'log_transform',
                    'code': "df['log_feature'] = np.log1p(df['numeric_feature'])",
                    'op_type': 'Transformation',
                    'desc': '对数变换特征'
                },
                {
                    'name': 'feature_interaction',
                    'code': "df['interaction'] = df['feature1'] * df['feature2']",
                    'op_type': 'Interaction',
                    'desc': '特征交互'
                },
                {
                    'name': 'feature_scaling',
                    'code': "df['scaled_feature'] = (df['feature'] - df['feature'].mean()) / df['feature'].std()",
                    'op_type': 'Scaling',
                    'desc': '特征标准化'
                }
            ]

    def generate_jsontree(self, task_id: str) -> Dict[str, Any]:
        """生成特征树JSON数据"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'fail', 'message': '任务不存在'}

        tree_state = self.tree_states.get(task_id)
        if not tree_state:
            return {'status': 'fail', 'message': '特征树状态不存在'}

        # 转换为前端需要的格式
        nodes = list(tree_state['nodes'].values())
        relations = tree_state['relations']

        # 选择一些叶子节点作为当前选中（不包括根节点）
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
            return {'status': 'fail', 'message': '任务不存在'}

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
            'message': f'性能测试完成，使用{len(selected_nodes)}个特征',
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
                        'operation_desc': f'{dataset}数据集的原始特征根节点',
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
            'message': f'端到端自动化特征工程完成，搜索深度{actual_depth}，生成{node_count}个特征',
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
                'message': f'{model_type}模型训练完成',
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
            'message': f"任务 '{task['task_description']}' 已初始化"
        }

    def stop_task(self, task_id: str) -> Dict[str, Any]:
        """停止任务"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'fail', 'message': '任务不存在'}

        task['status'] = 'stopped'
        self.add_notification(f"任务已停止: {task['task_description']}", 'info')

        return {
            'status': 'success',
            'message': '任务已成功停止'
        }

    def clear_task(self, task_id: str) -> Dict[str, Any]:
        """清除任务"""
        if task_id in self.tasks:
            task_desc = self.tasks[task_id]['task_description']
            del self.tasks[task_id]
            self.add_notification(f"任务已清除: {task_desc}", 'info')

        return {
            'status': 'success',
            'message': '任务状态已清除'
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