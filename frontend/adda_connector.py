# demo/adda_connector.py
import os
import sys
import pickle
import re
import json
from collections import deque
import pandas as pd
import networkx as nx
import shutil

# 添加项目根目录到Python路径（确保能访问src目录下的模块）
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入Adda系统核心模块
from src.llm.llm_dag_util import *  # DAG构造器核心逻辑
from src.pg.sql_utils import *
from src.pg.import_table import *    # 数据表导入功能
from src.pg.python_polish import *
from src.pg.func_utils import *
from src.env import *                # 环境配置
from src.llm.tests.test_util import task_config  # 任务配置加载器

class AddaConnector:
    """Adda系统与Flask前端的桥梁类"""
    
    def __init__(self):
        """初始化连接器状态"""
        # self.current_tree = None     # 当前特征树结构
        self.current_tree = {  # 初始化空树结构
            "root_id": 1,
            "parent_child_relations": [],
            "node_info": [{
                "node_id": 1,
                "feature_name": "All original features",
                "task_code": "# Initializing...",
                "op_type": "root",
                "score": 0.0,
                "exec_time": 0.0,
                "operation_desc": "任务初始化中"
            }],
            "cur_selected_idx": []
        }
        self.current_model = None    # 当前训练好的模型
        self.llm_dag_constructor = None  # LLM DAG构造器实例
        self.force_new = True
        self.count_idx = 0
    
    def start_task(self, task_description, dataset, model):
        """
        初始化特征工程任务（核心方法）
        
        参数:
            task_description (str): 用户输入的任务描述（自然语言）
            dataset (str): 数据集名称（对应config.yaml中的配置）
            model (str): 评估模型类型（如RF/XGBoost等）
            
        返回:
            tuple: (成功状态, 消息, 树结构数据)
        """
        try:
            # # test_util.py预处理段
            # 从test_util导入任务配置（参考test_util.py第29-41行）
            task_name, target_col, task_type = task_config(dataset.lower())
            
            # 导入并分割数据集（参考test_util.py的main函数）
            importTable_with_split(
                os.path.join(dataset_path, task_name, "train_new.csv"),
                f"{task_name}_src_tb",
                target_col,
                get_conn(),
                False,
                task_type
            )
            
            # # TestDir.py预处理段
            # 读取数据信息(获取数据特征描述、任务描述和CSV路径)
            data_agenda, desc, csv_path = read_data_info(task_name)
            unfinished = False # TODO: 需要修改此逻辑
            
            states_path = os.path.join(proj_path, "src", "cur_states.pkl")
            task_path = os.path.join(test_save_path, task_name)
            if os.path.exists(states_path) and not self.force_new:
                # 如果有未完成的模型且不强制创建新模型，则加载之前的状态
                print("reload the unfinished model")
                ctor = pickle.load(open(states_path, "rb"))
                unfinished = True
            else: # 默认执行此逻辑
                # 否则清空目录内容并创建新的LLMDagConstructor
                os.system(f"rm -rf {task_path}")
                # 参考TestDir的初始化方法：ctor = LLMDagConstructor(self.task_type, beam_limit=1, eval_model_type=self.model_type, do_feature_selection=False, high_order_num=high_order_num, token_limit=token_limit)
                # 初始化DAG构造器（参数参考TestDir.test_astar_step第100行）
                self.llm_dag_constructor = LLMDagConstructor(
                    task_type=task_type,
                    eval_model_type="RF",  # 硬编码为RF（随机森林）
                    beam_limit=1,          # 与测试配置保持一致
                    do_feature_selection=False,  # 不启用特征选择
                    high_order_num=5,       # 不允许生成二阶特征
                    token_limit=128000
                )

            # # llm_dag_util.py astar_k_step预处理段
            self.llm_dag_constructor.search_type = "ASTAR"
            src.llm.llm_dag_node.global_node_id = self.llm_dag_constructor.node_id
            
            # 初始化任务参数（数据加载/预处理）
            self.llm_dag_constructor.init_task_params(data_agenda, desc, target_col, f"{task_name}_src_tb", csv_path, unfinished, task_name)
            
            # 新建任务时初始化优先队列
            if not unfinished:
                self.llm_dag_constructor.cur_states = []
                heapq.heappush(self.llm_dag_constructor.cur_states, self.llm_dag_constructor.root)  # 使用最小堆实现优先队列
                self.llm_dag_constructor.pre_states = self.llm_dag_constructor.cur_states.copy()  # 保存前序状态用于恢复
            
            # 设置当前搜索状态（异步模式暂不支持）
            self.llm_dag_constructor.cur_states = self.llm_dag_constructor.pre_states
            
            # 获取断点续做起始索引
            self.count_idx = 0
            self.count_idx = self.llm_dag_constructor.pre_idx
            if self.count_idx != 0:
                print(f"current states is reload: {self.llm_dag_constructor.finish}, {self.count_idx}")
                self.llm_dag_constructor.draw_current(-20)  # 绘制当前DAG状态（调试用）

            # # 预处理结束
            print("successfuly init the task")

            # 生成前端需要的树形结构
            tree_structure = self._convert_dag_to_tree()
            return True, "任务启动成功", tree_structure
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"任务启动失败: {str(e)}", None
    
    def next_step(self):
        """生成下一步特征"""
        try:
            if not self.llm_dag_constructor:
                return False, "No active task, please start a task first", None
                
            # 调用Adda llm_dag_constructor.astar_one_step生成下一步特征
            # 模拟LLM DAG构造器生成下一步节点
            # TODO: 替换为实际调用，如self.llm_dag_constructor.compute_next_feature()
            # if self.count_idx < len(self.llm_dag_constructor.cur_states): # TODO: 按照llm_dag_constructor源代码的逻辑，不应该出现越界问题的
            self.llm_dag_constructor.astar_one_step(self.count_idx)
            self.count_idx += 1
            self.llm_dag_constructor.pre_idx = self.count_idx
            
            self.llm_dag_constructor.draw_current(-1*self.count_idx)
            
            # 每次执行后保存状态（与test_util.py逻辑一致）
            with open(os.path.join(proj_path, "src", "cur_states.pkl"), "wb") as f:
                pickle.dump(self.llm_dag_constructor, f)
            
            # 生成真实树结构
            self.current_tree = self._convert_dag_to_tree()
            
            if self.current_tree:
                # new_node_id = max([node["node_id"] for node in self.current_tree["node_info"]]) + 1
                # parent_id = self.current_tree["node_info"][-1]["node_id"]
                
                # feature_name = f"Generated_Feature_{new_node_id}"
                # feature_code = f"df['{feature_name}'] = df['feature_{parent_id}'] * 2"
                
                # self.current_tree["node_info"].append({
                #     "node_id": new_node_id,
                #     "feature_name": feature_name,
                #     "task_code": feature_code,
                #     "op_type": "generated",
                #     "operation_desc": "Generated through LLM"
                # })
                # self.current_tree["parent_child_relations"].append([parent_id, new_node_id])
                
                # 保持与原有返回结构一致
                return True, "Feature generated successfully", self.current_tree
            else:
                return False, "Error with tree structure", None
        except Exception as e:
            return False, f"Error generating feature: {str(e)}", None
    
    def test_performance(self, selected_node_ids):
        """测试选定特征的性能（真实评估逻辑）"""
        try:
            if not self.llm_dag_constructor:
                return False, "No active task, please start a task first", None
            
            # 合并所有选中节点的特征
            selected_nodes = [n for n in self.llm_dag_constructor.dag.nodes 
                            if n.node_id in selected_node_ids]
            
            # 按DAG层级排序确保特征叠加顺序
            dag = self.llm_dag_constructor.dag
            root_node = next(n for n in dag.nodes if isinstance(n, LLMDAGNODE) and dag.in_degree(n) == 0)
            sorted_nodes = sorted(selected_nodes, key=lambda n: len(nx.shortest_path(dag, root_node, n)))
            
            # 合并特征并去重
            merged_df = pd.concat([n.out_cur_df for n in sorted_nodes], axis=1)
            merged_df = merged_df.loc[:,~merged_df.columns.duplicated()]
            
            # 处理目标列
            target_col = self.llm_dag_constructor.target_col
            encoded_target = f"{target_col}_Label"
            if encoded_target in merged_df:
                merged_df = merged_df.rename(columns={encoded_target: target_col})
            
            # 调用核心评估方法
            score, _, _ = self.llm_dag_constructor.get_scores(merged_df)
            
            # 根据任务类型格式化结果
            task_type = self.llm_dag_constructor.task_type
            metric = "AUC" if task_type == "classify" else "1-RAE"
            return True, f"{metric}: {score:.4f}", None
            
        except Exception as e:
            return False, f"Error testing performance: {str(e)}", None
    
    def generate_model(self, selected_node_ids):
        """生成真实模型（基于LLMDagConstructor的最佳代码）"""
        try:
            if not self.llm_dag_constructor:
                return False, "No active task", None
            
            if not self.llm_dag_constructor.finish:
                return False, "Task is not finished", None

            # 获取最佳特征工程管道（参考llm_dag_util.py 487-527行）
            # best_code = self.llm_dag_constructor.get_best_code()
            
            # if not best_code:
            #     return False, "No valid features generated", None
        

            # 获取完整特征工程代码
            # feature_pipeline = "\n".join([
            #     self.llm_dag_constructor.fetch_code_from_leaf(best_node),
            #     best_node.whole_code
            # ])
            
            # 序列化模型和特征管道（参考test_util.py状态保存逻辑）
            # model_bytes = pickle.dumps({
            #     'model': self.llm_dag_constructor.eval_model,
            #     'feature_pipeline': feature_pipeline
            # })
            model_bytes = pickle.dumps(self.llm_dag_constructor)
            
            return True, "Model generated successfully", model_bytes
        except Exception as e:
            return False, f"Error generating model: {str(e)}", None
    
    def stop_task(self):
        
        if self.llm_dag_constructor:
            
            """停止任务，计算最佳特征工程节点（astar_k_step后处理逻辑）"""
            # 计算最佳特征工程节点
            self.llm_dag_constructor.compute_best_code()
            self.llm_dag_constructor.finish = True  # 仅标记完成，不重置实例
        
            """停止当前任务（参考test_util.py的状态保存逻辑）"""
            # 保存当前状态（与test_util.py第87行逻辑一致）
            task_path = os.path.join(test_save_path, self.llm_dag_constructor.task_name)
            os.makedirs(task_path, exist_ok=True)
            with open(os.path.join(task_path, "cur_states.pkl"), "wb") as f:
                pickle.dump(self.llm_dag_constructor, f)
            
            # 重置任务状态
            # self.llm_dag_constructor = None TODO: 注意，为了使用户在停止任务后可以继续使用model下载功能，这里不会重置任务状态
            # 被设计为只有在使用clear按钮时才会重置任务状态
            self.current_tree = None 
            return True, "任务已停止并保存"
        
        return False, "没有活动任务可停止"
    
    def clear_task(self):
        """完全清除任务状态（参考__init__初始化逻辑）"""
        if self.llm_dag_constructor:
            # 删除保存的状态文件（与test_util.py清理逻辑一致）
            task_path = os.path.join(test_save_path, self.llm_dag_constructor.task_name)
            if os.path.exists(task_path):
                shutil.rmtree(task_path)
            
            # 完全重置状态
            self.__init__()  # 重新初始化实例
            return True, "任务已清除并重置"
        return False, "没有活动任务可清除"
    
    def _convert_dag_to_tree(self):
        """
        将DAG结构转换为前端树形结构（基于draw_current的中间数据）
        
        新实现逻辑：
        1. 使用DRAWNODE作为中间数据结构
        2. 保持DAG的拓扑层次关系
        3. 添加评估分数和执行耗时
        """
        if not self.llm_dag_constructor:
            return None
            
        # 使用draw_current的中间数据结构
        dag = self.llm_dag_constructor.dag
        draw_nodes = nx.DiGraph()
        nodes_map = {}
        
        # 重建DRAWNODE结构（参考llm_dag_util.py 478-514行）
        for node in dag.nodes:
            drawn_node = DRAWNODE(
                node_id=node.node_id,
                task_code=node.task_code,
                score=node.final_score,
                exec_time=node.exec_time
            )
            nodes_map[node] = drawn_node
            draw_nodes.add_node(drawn_node)
        
        for edge in dag.edges:
            draw_nodes.add_edge(nodes_map[edge[0]], nodes_map[edge[1]])
        
        # 构建树形结构
        tree = {
            "root_id": 1,
            "parent_child_relations": [],
            "node_info": [{
                "node_id": 1,
                "feature_name": "All original features",
                "task_code": "# Root node",
                "op_type": "root",
                "score": 0.0,
                "exec_time": 0.0,
                "operation_desc": "特征树根节点"
            }],
            "cur_selected_idx": []  # 新增必填字段
        }

        # 建立原始node_id映射
        # id_mapping = {n.node_id: n for n in draw_nodes.nodes}
        
        # 层次遍历构建树结构
        visited = set()
        root_nodes = [n for n in draw_nodes.nodes if draw_nodes.in_degree(n) == 0]
        
        for root_node in root_nodes:
            queue = deque([(1, root_node)])  # 元组格式：(父ID, 当前节点)
            
            while queue:
                parent_id, current = queue.popleft()
                
                if current.node_id in visited:
                    continue
                visited.add(current.node_id)

                # 添加节点信息（使用原始node_id）
                if current.node_id != 1:  # 跳过已添加的根节点
                    tree["node_info"].append({
                        "node_id": current.node_id,
                        "feature_name": self._get_feature_name(current.task_code),
                        "task_code": current.task_code,
                        "op_type": self._infer_op_type(current.task_code),
                        "score": current.score,
                        "exec_time": current.exec_time, # 真的需要这两项吗？ TODO: 这部分的信息可能需要体现在前端界面的其他部分而不是在特征树上
                        "operation_desc": self._generate_desc(current.task_code)
                    })

                # 添加父子关系
                if parent_id != current.node_id:  # 避免根节点自连接
                    tree["parent_child_relations"].append([parent_id, current.node_id])

                # 添加子节点到队列
                for successor in draw_nodes.successors(current):
                    queue.append((current.node_id, successor))

        # 添加调试输出
        print("Final tree structure:", json.dumps(tree, indent=2, ensure_ascii=False))
        return tree
    
    def _get_feature_name(self, task_code: str) -> str:
        """严格提取单个特征名称"""
        pattern = r"df\['([^']+)'\]"
        match = re.search(pattern, task_code)
        return match.group(1) if match else "Unnamed_Feature"
    
    def _infer_op_type(self, task_code: str) -> str:
        """推断操作类型（参考llm_dag_util.py的代码分析逻辑）"""
        if "pd.cut" in task_code:
            return "Discretization"
        elif "groupby" in task_code:
            return "Aggregation"
        elif "LabelEncoder" in task_code:
            return "Encoding"
        return "Transformation"
    
    def _generate_desc(self, task_code: str) -> str:
        """生成自然语言描述（对接NLAgent的功能）"""
        # 模拟NLAgent的生成逻辑，实际应调用NLAgent接口
        if "fillna" in task_code:
            return "处理缺失值"
        elif "apply(" in task_code:
            return "应用自定义函数"
        return "特征转换操作"