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
from src.llm.agent_status_wrapper import agent_status_wrapper  # Agent状态包装器
import warnings
import termcolor
import pandas as pd

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

        # 连接WebSocket服务器到Agent状态包装器
        # 注意：这里需要延迟设置，因为WebSocket服务器在Flask应用启动后才完全初始化
        self._setup_websocket_connection()
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

            # 缓存数据信息，避免在auto_step中重复读取
            self.llm_dag_constructor.data_agenda = data_agenda
            self.llm_dag_constructor.data_desc = desc
            self.llm_dag_constructor.csv_path = csv_path

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

            # 添加手动创建的特征节点用于测试（节省LLM API token）
            if task_name == "mock_data":
                self._add_mock_feature_nodes()

            # 生成前端需要的树形结构
            tree_structure = self._convert_dag_to_tree()
            # 缓存树结构，供/get-treejson读取
            if tree_structure:
                self.current_tree = tree_structure
            print(f"Generated tree structure: {tree_structure}")
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
    
    def test_performance(self, selected_node_ids, model_type="RF", use_in_db_ml=True):
        """
        测试选定节点特征组合的性能
        支持真正的in-database ML训练和测试

        Args:
            selected_node_ids: 选择的节点ID列表
            model_type: 模型类型 (RF, XGB, LightGBM)
            use_in_db_ml: 是否使用in-database ML (默认True)

        Returns:
            Tuple of (success, message, performance_info)
        """
        try:
            if not self.llm_dag_constructor:
                return False, "No active task, please start a task first", None

            if not selected_node_ids:
                return False, "No nodes selected for performance testing", None

            # 验证节点是否存在
            existing_node_ids = [str(n.node_id) for n in self.llm_dag_constructor.dag.nodes()]
            invalid_nodes = [nid for nid in selected_node_ids if str(nid) not in existing_node_ids]
            if invalid_nodes:
                return False, f"Invalid node IDs: {invalid_nodes}", None

            # 检查是否只选择了根节点（根节点无法直接用于训练）
            if len(selected_node_ids) == 1 and selected_node_ids[0] == "1":
                return False, "根节点仅包含原始数据，无法直接用于模型训练。请先点击'Next Step'按钮生成特征节点，然后选择生成的特征节点进行测试。", None

            # 如果使用in-database ML，调用新的多节点训练方法
            if use_in_db_ml:
                return self._test_performance_in_db(selected_node_ids, model_type)
            else:
                # 保持原有的模拟方法作为备选
                return self._test_performance_simulation(selected_node_ids)

        except Exception as e:
            return False, f"Error testing performance: {str(e)}", None

    def _test_performance_in_db(self, selected_node_ids, model_type):
        """
        已弃用：使用新的_run_multimodal_performance方法替代
        保留此方法是为了向后兼容，但会重定向到新方法
        """
        print("Warning: _test_performance_in_db is deprecated, using _run_multimodal_performance instead")

        # 获取任务名称
        task_name = getattr(self.llm_dag_constructor, 'task_name', None)

        # 调用新的性能测试方法
        performance_result = self._run_multimodal_performance(model_type=model_type, task_name=task_name)

        if performance_result.get("success", False):
            auc = performance_result.get("auc", 0.0)
            exec_time = performance_result.get("execution_time", 0.0)

            # 构建结果消息
            node_desc = f"nodes {', '.join(selected_node_ids)}"
            message = f"In-DB ML AUC: {auc:.4f} for {node_desc} ({model_type}, {exec_time:.2f}s)"

            return True, message, performance_result
        else:
            return False, performance_result.get("error", "In-DB ML training failed"), None

    def _test_performance_simulation(self, selected_node_ids):
        """
        使用原有的模拟方法进行性能测试（作为备选方案）
        """
        try:
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

            # 构建结果消息
            node_desc = f"node {selected_node_ids[0]}" if len(selected_node_ids) == 1 else f"nodes {', '.join(selected_node_ids)}"
            message = f"Simulation {metric}: {score:.4f} for {node_desc}"

            # 性能信息
            performance_info = {
                "score": score,
                "metric": metric,
                "selected_nodes": selected_node_ids,
                "in_db_ml": False,
                "node_count": len(selected_node_ids),
                "method": "simulation"
            }

            return True, message, performance_info

        except Exception as e:
            return False, f"Simulation performance test failed: {str(e)}", None
    
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
        # 使用真实的根节点分数/耗时，如果不可用则回退为0
        root_score = 0.0
        root_exec_time = 0.0
        try:
            if getattr(self, "llm_dag_constructor", None) and getattr(self.llm_dag_constructor, "root", None):
                root_score = float(getattr(self.llm_dag_constructor.root, "final_score", 0.0) or 0.0)
                root_exec_time = float(getattr(self.llm_dag_constructor.root, "exec_time", 0.0) or 0.0)
        except Exception:
            pass

        tree = {
            "root_id": 1,
            "parent_child_relations": [],
            "node_info": [{
                "node_id": 1,
                "feature_name": "All original features",
                "task_code": "# Root node",
                "op_type": "root",
                "score": root_score,
                "exec_time": root_exec_time,
                "operation_desc": "root node"
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

    def _run_multimodal_performance(self, model_type="RF", task_name=None):
        """
        直接模仿 run_multimodel_type.py 的做法来执行性能测试
        避开有bug的 test_performance 方法

        参数:
            model_type: 模型类型 (RF, XGB, LightGBM)
            task_name: 任务名称（如果不提供，尝试从当前DAG构造器获取）

        返回:
            dict: 包含性能指标、SQL代码和执行结果的字典
        """
        warnings.filterwarnings("ignore")

        try:
            # 1. 验证LLMDagConstructor状态
            if not self.llm_dag_constructor:
                return {
                    "success": False,
                    "error": "LLMDagConstructor未初始化",
                    "auc": 0.0,
                    "execution_time": 0.0,
                    "sql_code": {}
                }

            # 2. 获取任务配置
            if not task_name:
                # 尝试从DAG构造器获取任务名称
                task_name = getattr(self.llm_dag_constructor, 'task_name', 'heart')

            try:
                actual_task_name, target_col, task_type = task_config(task_name)
            except Exception as e:
                # 如果无法获取配置，使用默认值
                print(f"Warning: 无法获取任务配置，使用默认值: {e}")
                actual_task_name = task_name
                target_col = "target"
                task_type = "classify"

            # 3. 设置目录和文件路径（完全按照run_multimodel_type.py的方式）
            dir_path = os.path.join(test_save_path, actual_task_name)
            postfix = f"_{model_type}_Full"
            origin_name = os.path.join(test_save_path, f"{actual_task_name}{postfix}")
            exec_name = os.path.join(test_save_path, actual_task_name)

            print(f"Debug: _run_multimodal_performance - dir_path={dir_path}")
            print(f"Debug: _run_multimodal_performance - postfix={postfix}")
            print(f"Debug: _run_multimodal_performance - origin_name={origin_name}")
            print(f"Debug: _run_multimodal_performance - exec_name={exec_name}")
            print(f"Debug: _run_multimodal_performance - origin_name exists: {os.path.exists(origin_name)}")

            # 4. 修复目录重命名逻辑 - 跳过重命名，直接使用现有目录
            # 因为auto-step已经将pickle文件保存在正确位置
            print(f"Debug: Skipping directory rename, using existing directory structure")
            # if os.path.exists(origin_name):
            #     os.rename(origin_name, exec_name)

            # 5. 设置数据库连接
            conn = get_conn()
            cursor = conn.cursor()

            # 6. 设置数据文件和表名
            csvpath = os.path.join(dataset_path, actual_task_name, "train_new.csv")
            db_tb_name = f"{actual_task_name}_src_tb"
            pycodepath = os.path.join(test_save_path, actual_task_name, "pycodes")

            # 检查数据文件是否存在
            if not os.path.exists(csvpath):
                return {
                    "success": False,
                    "error": f"数据文件不存在: {csvpath}",
                    "auc": 0.0,
                    "execution_time": 0.0,
                    "sql_code": {}
                }

            # 7. 读取数据并计算行数列数
            df = pd.read_csv(csvpath)
            row_num, col_num = df.shape[0] - int(df.shape[0]/5), df.shape[1]
            os.makedirs(pycodepath, exist_ok=True)

            # 8. 加载LLMDagConstructor状态（关键步骤）
            last_pipector_path = os.path.join(test_save_path, actual_task_name, "cur_states.pkl")

            print(f"Debug: Looking for pickle file at {last_pipector_path}")
            print(f"Debug: Pickle file exists: {os.path.exists(last_pipector_path)}")

            # 如果pickle文件不存在，尝试使用当前的DAG构造器
            if not os.path.exists(last_pipector_path):
                print(f"Debug: Pickle file not found at standard path, using current DAG constructor state")
                pipeCtor = self.llm_dag_constructor
                print(f"Debug: Using current DAG constructor with {len(pipeCtor.dag.nodes())} nodes")
            else:
                print(f"Debug: Loading pickle file from {last_pipector_path}")
                with open(last_pipector_path, "rb") as f:
                    pipeCtor = pickle.load(f)
                print(f"Debug: Successfully loaded pickle file with {len(pipeCtor.dag.nodes())} nodes")

            # 9. 设置表名
            pipeCtor.tb_name = db_tb_name

            # 10. 检查是否有有效的pipes（关键修复）
            if not hasattr(pipeCtor, 'pipes') or not pipeCtor.pipes:
                print("Debug: No pipes found in DAG constructor, attempting to compute best code")
                try:
                    # 尝试计算最佳代码（现在这个方法会自动调用get_best_code来设置code_path）
                    pipeCtor.compute_best_code()

                    if not hasattr(pipeCtor, 'pipes') or not pipeCtor.pipes:
                        return {
                            "success": False,
                            "error": "没有生成有效的特征管道。请尝试增加搜索深度或检查数据质量。",
                            "auc": 0.0,
                            "execution_time": 0.0,
                            "sql_code": {}
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"计算最佳特征失败: {str(e)}。请尝试增加搜索深度或检查数据质量。",
                        "auc": 0.0,
                        "execution_time": 0.0,
                        "sql_code": {}
                    }

            # 过滤掉None pipes
            valid_pipes = [pipe for pipe in pipeCtor.pipes if pipe is not None]
            if not valid_pipes:
                return {
                    "success": False,
                    "error": "所有特征管道都无效。这可能是由于数据质量问题或搜索深度不足导致的。",
                    "auc": 0.0,
                    "execution_time": 0.0,
                    "sql_code": {}
                }

            print(f"Debug: Found {len(valid_pipes)} valid pipes out of {len(pipeCtor.pipes)} total pipes")

            # 11. 初始化PythonPolisher（完全按照run_multimodel_type.py的参数）
            pipes = pipeCtor.pipes
            polisher = PythonPolisher(
                db_tb_name,
                target_col,
                "df",
                pipes,
                dir_path,
                2,  # do_optimize
                col_num,
                pipeCtor,
                id_col='id',
                total_num=row_num,
                do_optimize=2,
                task_type=task_type,
                use_py_train_pred=True,
                model_type=model_type
            )

            # 12. 执行代码优化
            polisher.polish_code()

            # 13. 创建model_table并清理旧模型（完全复制run_multimodel_type.py的逻辑）
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS model_table (
                tb_name TEXT,
                model_type TEXT,
                path TEXT UNIQUE,
                version SERIAL,
                PRIMARY KEY (tb_name, model_type, version)
            );
            """
            cursor.execute(create_table_sql)

            # 清理旧模型
            cursor.execute(f"""
                DELETE FROM model_table
                WHERE tb_name = '{db_tb_name}'
                AND model_type = '{model_type}'
            """)
            os.system(f"rm -f {model_store_path}/{db_tb_name}_{model_type}_*.pkl")
            conn.commit()

            # 14. 生成SQL并执行训练（核心步骤）- 修复空scores错误
            try:
                print("Debug: Starting SQL generation...")
                scores, auc_result, best_auc = polisher.generate_sql()
                speed_record = polisher.speed_record

                # 检查返回结果是否有效
                if not scores or not auc_result:
                    return {
                        "success": False,
                        "error": "SQL生成失败：没有有效的特征管道可用于生成SQL。这通常意味着没有生成任何有效特征。",
                        "auc": 0.0,
                        "execution_time": 0.0,
                        "sql_code": {}
                    }

                auc_answer = best_auc
                print(f"Debug: SQL generation completed successfully, AUC: {auc_answer}")

            except Exception as sql_error:
                error_msg = f"SQL生成失败: {str(sql_error)}"
                print(f"Debug: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "auc": 0.0,
                    "execution_time": 0.0,
                    "sql_code": {}
                }

            # 15. 恢复目录名称
            if os.path.exists(exec_name):
                os.rename(exec_name, origin_name)

            # 16. 读取生成的SQL文件 - 修复路径问题
            # SQL文件实际在 origin_name 目录中
            sql_dir_path = origin_name if os.path.exists(origin_name) else dir_path
            print(f"Debug: Reading SQL files from {sql_dir_path}")
            sql_code = self._read_generated_sql_files(sql_dir_path, 0)  # 第一个pipeline
            print(f"Debug: Read SQL code with {len(sql_code.get('all_sql', ''))} characters")

            # 17. 准备返回结果
            execution_time = speed_record.get("sql", [0])[0] if speed_record and "sql" in speed_record else 0.0

            result = {
                "success": True,
                "auc": float(auc_answer) if auc_answer is not None else 0.0,
                "execution_time": float(execution_time),
                "model_type": model_type,
                "task_name": actual_task_name,
                "target_column": target_col,
                "task_type": task_type,
                "sql_code": sql_code,
                "sql_file_paths": self._get_sql_file_paths(dir_path, 0),
                "method": "in_database_ml",
                "row_num": row_num,
                "col_num": col_num
            }

            print(termcolor.colored(f"Performance testing completed. Final AUC: {auc_answer}, Execution time: {execution_time:.2f}s", "yellow"))

            return result

        except Exception as e:
            # 确保在出错时恢复目录名称
            try:
                if 'exec_name' in locals() and 'origin_name' in locals():
                    if os.path.exists(exec_name):
                        os.rename(exec_name, origin_name)
            except:
                pass

            error_msg = f"性能测试失败: {str(e)}"
            print(termcolor.colored(error_msg, "red"))

            return {
                "success": False,
                "error": error_msg,
                "auc": 0.0,
                "execution_time": 0.0,
                "sql_code": {}
            }

        finally:
            # 确保关闭数据库连接
            try:
                if 'conn' in locals():
                    conn.close()
            except:
                pass

    def _read_generated_sql_files(self, dir_path: str, pipe_idx: int) -> dict:
        """
        读取生成的SQL文件内容，只提取特征相关的代码，过滤训练/预测特定部分
        """
        sql_code = {
            "feature_sql": "",
            "all_sql": ""
        }

        try:
            # 只读取训练SQL文件中的特征生成部分
            train_sql_path = os.path.join(dir_path, f"pipe_train_{pipe_idx}", "spsql.sql")
            if os.path.exists(train_sql_path):
                with open(train_sql_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                    # 提取特征相关的SQL（排除RF_train调用）
                    lines = content.split('\n')
                    feature_lines = []

                    for i, line in enumerate(lines):
                        # 检查是否到达模型训练部分
                        if 'RF_train' in line or 'model_table' in line:
                            break
                        feature_lines.append(line)

                    # 去除末尾的空行和逗号
                    while feature_lines and (feature_lines[-1].strip() == '' or feature_lines[-1].strip() == ','):
                        feature_lines.pop()

                    # 添加合适的结尾
                    if feature_lines:
                        feature_lines.append(') -- 特征数据生成完成')

                    sql_code["feature_sql"] = '\n'.join(feature_lines)

            # 读取UDF SQL文件
            udf_sql_path = os.path.join(dir_path, f"pipe_train_{pipe_idx}", "spudf.sql")
            if os.path.exists(udf_sql_path):
                with open(udf_sql_path, 'r', encoding='utf-8') as f:
                    udf_content = f.read()

                    # 提取特征相关的UDF（排除训练/预测函数）
                    # 只保留udf_1, udf_2, udf_3等特征生成函数
                    lines = udf_content.split('\n')
                    feature_udf_lines = []
                    current_function = None
                    in_feature_function = False

                    for line in lines:
                        # 检测UDF函数定义
                        if line.strip().startswith('CREATE OR REPLACE FUNCTION udf_'):
                            func_name = line.split('udf_')[1].split(' ')[0]
                            # 只保留特征生成相关的UDF（1,2,3等）
                            if func_name.isdigit() and int(func_name) <= 10:  # 假设特征UDF编号不超过10
                                current_function = f'udf_{func_name}'
                                in_feature_function = True
                                feature_udf_lines.append(line)
                            else:
                                in_feature_function = False
                        elif in_feature_function and line.strip().startswith('$$'):
                            # UDF函数结束
                            current_function = None
                            in_feature_function = False
                            feature_udf_lines.append(line)
                        elif in_feature_function:
                            # 在特征UDF函数内部
                            feature_udf_lines.append(line)

                    sql_code["udf_sql"] = '\n'.join(feature_udf_lines)

            # 组合特征相关的SQL
            if sql_code["udf_sql"] and sql_code["feature_sql"]:
                sql_code["all_sql"] = (
                    "-- 特征生成相关的UDF函数\n" +
                    sql_code["udf_sql"] + "\n\n" +
                    "-- 特征生成SQL查询\n" +
                    sql_code["feature_sql"]
                )
            elif sql_code["udf_sql"]:
                sql_code["all_sql"] = "-- 特征生成相关的UDF函数\n" + sql_code["udf_sql"]
            elif sql_code["feature_sql"]:
                sql_code["all_sql"] = "-- 特征生成SQL查询\n" + sql_code["feature_sql"]

        except Exception as e:
            print(f"Warning: Failed to read SQL files: {e}")

        return sql_code

    def _get_sql_file_paths(self, dir_path: str, pipe_idx: int) -> dict:
        """
        获取生成的SQL文件路径（从train_node_model.py复制过来）
        """
        file_paths = {
            "training_sql_path": "",
            "prediction_sql_path": "",
            "udf_sql_path": ""
        }

        try:
            file_paths["training_sql_path"] = os.path.join(dir_path, f"pipe_train_{pipe_idx}", "spsql.sql")
            file_paths["prediction_sql_path"] = os.path.join(dir_path, f"pipe_predict_{pipe_idx}", "spsql.sql")
            file_paths["udf_sql_path"] = os.path.join(dir_path, f"pipe_train_{pipe_idx}", "spudf.sql")
        except Exception as e:
            print(f"Warning: Failed to get SQL file paths: {e}")

        return file_paths

    def _get_best_features_info(self, task_name):
        """
        获取最佳特征信息，包括Python代码、SQL代码和特征描述
        """
        try:
            # 1. 确保LLMDagConstructor已初始化
            if not self.llm_dag_constructor:
                print("LLMDagConstructor未初始化，无法获取最佳特征信息")
                return {
                    "success": False,
                    "error": "LLMDagConstructor未初始化",
                    "python_code": "",
                    "sql_code": "",
                    "feature_descriptions": []
                }

            # 2. 确保compute_best_code已被执行
            if not hasattr(self.llm_dag_constructor, 'output_nodes') or not self.llm_dag_constructor.output_nodes:
                print("尚未执行compute_best_code，正在执行...")
                self.llm_dag_constructor.compute_best_code()

            # 3. 获取最佳节点
            best_nodes = self.llm_dag_constructor.output_nodes
            if not best_nodes:
                print("未找到最佳节点")
                return {
                    "success": False,
                    "error": "未找到最佳节点",
                    "python_code": "",
                    "sql_code": "",
                    "feature_descriptions": []
                }

            # 4. 提取最佳特征信息
            best_node = best_nodes[0]  # 取第一个最佳节点
            print(f"Selected best node: {best_node.node_id}, operation: {getattr(best_node, 'operation_desc', 'None')}")

            # 获取Python代码
            python_code = getattr(best_node, 'whole_code', '')
            if not python_code:
                python_code = getattr(best_node, 'task_code', '')

            # 获取特征描述 - 简化版本，直接使用最佳节点的描述
            feature_descriptions = []
            if hasattr(best_node, 'operation_desc') and best_node.operation_desc:
                feature_descriptions.append({
                    "node_id": best_node.node_id,
                    "description": best_node.operation_desc,
                    "feature_name": getattr(best_node, 'feature_name', ''),
                    "op_type": str(getattr(best_node, 'op_type', 'Unknown')),
                    "score": getattr(best_node, 'final_score', 0.0),
                    "exec_time": getattr(best_node, 'exec_time', 0.0)
                })

            print(f"Retrieved {len(feature_descriptions)} feature descriptions, Python code length: {len(python_code)}")

            return {
                "success": True,
                "node_id": best_node.node_id,
                "final_score": getattr(best_node, 'final_score', 0.0),
                "python_code": python_code,
                "sql_code": "",  # SQL代码将在性能测试阶段生成
                "feature_descriptions": feature_descriptions,
                "feature_count": len(feature_descriptions),
                "operation_desc": getattr(best_node, 'operation_desc', ''),
                "exec_time": getattr(best_node, 'exec_time', 0.0)
            }

        except Exception as e:
            error_msg = f"获取最佳特征信息失败: {str(e)}"
            print(termcolor.colored(error_msg, "red"))
            return {
                "success": False,
                "error": error_msg,
                "python_code": "",
                "sql_code": "",
                "feature_descriptions": []
            }

    def _extract_feature_descriptions(self, node):
        """
        从节点回溯到根节点，提取路径上所有节点的特征描述
        """
        descriptions = []
        try:
            current_node = node

            # 回溯到根节点，收集所有操作描述
            while hasattr(current_node, 'node_id') and current_node.node_id != 1:
                if hasattr(current_node, 'operation_desc') and current_node.operation_desc:
                    # 获取op_type的字符串表示，确保JSON可序列化
                    op_type = getattr(current_node, 'op_type', None)
                    op_type_str = str(op_type) if op_type else 'Unknown'

                    descriptions.append({
                        "node_id": current_node.node_id,
                        "description": current_node.operation_desc,
                        "feature_name": list(current_node.write_set)[0] if current_node.write_set else "",
                        "op_type": op_type_str,
                        "score": getattr(current_node, 'final_score', 0.0),
                        "exec_time": getattr(current_node, 'exec_time', 0.0)
                    })

                # 移动到前驱节点
                predecessors = list(self.llm_dag_constructor.dag.predecessors(current_node))
                if predecessors:
                    current_node = predecessors[0]
                else:
                    break

            # 反转列表，使其从根节点到叶子节点
            descriptions.reverse()

            return descriptions

        except Exception as e:
            print(f"提取特征描述失败: {str(e)}")
            return []

    # _get_best_node_sql_code 方法已移除，因为SQL代码获取逻辑已整合到 _run_multimodal_performance 方法中

    def train_on_single_node(self, node_id, task_name=None, model_type="RF", dataset_path=None):
        """
        重构后的单节点训练方法，使用_run_multimodal_performance替代NodeModelTrainer
        避开有bug的NodeModelTrainer依赖

        参数:
            node_id: 节点ID（现在此参数主要用于兼容性，实际使用整个DAG的状态）
            task_name: 数据集类型（如: heart, diabetes, titanic等）
            model_type: 模型类型（RF/XGB/LightGBM等）
            dataset_path: 数据集路径（可选，保留用于兼容性）

        返回:
            tuple: (成功状态, 结果信息, 性能指标)
        """
        print(f"Info: train_on_single_node called with node_id={node_id}, using _run_multimodal_performance")

        # 直接调用新的性能测试方法
        performance_result = self._run_multimodal_performance(model_type=model_type, task_name=task_name)

        if performance_result.get("success", False):
            auc = performance_result.get("auc", 0.0)
            exec_time = performance_result.get("execution_time", 0.0)

            # 构建结果信息
            result_info = {
                "model_table": performance_result.get("task_name", "unknown") + "_src_tb",
                "target_column": performance_result.get("target_column", "target"),
                "task_type": performance_result.get("task_type", "classify"),
                "sql_files_generated": True,
                "sql_code": performance_result.get("sql_code", {}),
                "sql_file_paths": performance_result.get("sql_file_paths", {}),
                "node_id": node_id,  # 为了兼容性保留
                "method": "in_database_ml_refactored"
            }

            message = f"节点 {node_id} 训练成功: AUC={auc:.4f}, 耗时={exec_time:.2f}s"

            return True, message, performance_result
        else:
            error_msg = performance_result.get("error", "单节点训练失败")
            return False, error_msg, None

    def _add_mock_feature_nodes(self):
        """手动添加mock特征节点，节省LLM API token"""
        try:
            from src.llm.llm_dag_node import LLMDAGNODE
            import pandas as pd
            import numpy as np

            print("添加mock特征节点...")

            # 获取根节点
            root_node = None
            for node in self.llm_dag_constructor.dag.nodes():
                if hasattr(node, 'node_id') and node.node_id == 1:
                    root_node = node
                    break

            if not root_node:
                print("未找到根节点")
                return

            # 创建mock数据
            df = pd.DataFrame({
                'age': [25, 35, 45, 55, 65, 30, 40, 50, 60, 70],
                'sex': [1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
                'cp': [120, 130, 140, 150, 160, 125, 135, 145, 155, 165],
                'trestbps': [120, 130, 140, 150, 160, 125, 135, 145, 155, 165],
                'chol': [200, 220, 240, 260, 280, 210, 230, 250, 270, 290],
                'fbs': [1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
                'restecg': [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
                'thalach': [150, 140, 130, 120, 110, 145, 135, 125, 115, 105],
                'exang': [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
                'oldpeak': [2.0, 3.0, 1.0, 4.0, 0.5, 2.5, 3.5, 1.5, 4.5, 0.0],
                'slope': [1, 2, 3, 1, 2, 3, 1, 2, 3, 1],
                'ca': [0, 1, 2, 0, 1, 2, 0, 1, 2, 0],
                'thal': [1, 2, 3, 1, 2, 3, 1, 2, 3, 1],
                'tenyearchd': [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
            })

            # 定义特征节点
            mock_nodes = [
                {
                    'node_id': 2,
                    'feature_name': 'risk_score_v2',
                    'task_code': '''
# 节点2: 风险分数计算v2
def calculate_risk_score_v2(row):
    ratio_bp = row['cp'] / row['trestbps'] if row['trestbps'] > 0 else 0

    if row['fbs'] == 1:
        glucose_factor = row['chol'] / df['chol'].mean()
        ratio_bp += glucose_factor

    risk_score = (ratio_bp * row['age']) / (row['thalach'] + 1)
    return risk_score

df['risk_score_v2'] = df.apply(calculate_risk_score_v2, axis=1)
                    ''',
                    'op_type': 'Transformation',
                    'score': 0.72,
                    'exec_time': 0.15,
                    'operation_desc': '计算心血管风险分数v2'
                },
                {
                    'node_id': 3,
                    'feature_name': 'risk_factor_score',
                    'task_code': '''
# 节点3: 风险因子分数
df['risk_factor_score'] = (
    df['age'] * df['cp'] +
    df['chol'] * df['fbs'] +
    df['oldpeak'] * df['exang']
) / 100
                    ''',
                    'op_type': 'Aggregation',
                    'score': 0.68,
                    'exec_time': 0.12,
                    'operation_desc': '聚合风险因子分数'
                },
                {
                    'node_id': 4,
                    'feature_name': 'health_index',
                    'task_code': '''
# 节点4: 健康指数
df['health_index'] = (
    np.sqrt(df['age'] * df['cp']) +
    np.log1p(df['chol']) +
    df['thalach'] / df['age'] -
    df['oldpeak'] * df['slope']
)
                    ''',
                    'op_type': 'Transformation',
                    'score': 0.75,
                    'exec_time': 0.18,
                    'operation_desc': '计算综合健康指数'
                }
            ]

            # 创建节点对象并添加到DAG
            for node_data in mock_nodes:
                try:
                    # 创建一个包含新特征的DataFrame
                    df_with_feature = df.copy()

                    # 执行特征代码
                    exec(node_data['task_code'], {'df': df_with_feature, 'np': np})

                    node = LLMDAGNODE(
                        node_id=node_data['node_id'],
                        task_code=node_data['task_code'],
                        read_set=set(df.columns),
                        write_set=set(df_with_feature.columns),
                        in_cur_df=df.copy(),
                        out_cur_df=df_with_feature,
                        column_info={col: 'float' for col in df_with_feature.columns},
                        op_list=[],
                        op_type=node_data['op_type'],
                        init_scores=[],
                        final_score=node_data['score'],
                        operation_desc=node_data['operation_desc'],
                        sql_code=f"SELECT *, {node_data['feature_name']} FROM features",
                        dependency=[root_node],
                        attr_imp_list=[],
                        op_sql=[],
                        in_train=True,
                        in_test=True,
                        exec_time=node_data['exec_time'],
                        attr_imp_order=[],
                        whole_code=node_data['task_code']
                    )

                    # 添加到DAG
                    self.llm_dag_constructor.dag.add_node(node)
                    self.llm_dag_constructor.dag.add_edge(root_node, node)

                    print(f"成功添加节点 {node.node_id}: {node_data['feature_name']}")

                except Exception as e:
                    print(f"创建节点 {node_data['node_id']} 失败: {e}")
                    continue

            print(f"Mock特征节点添加完成，共添加 {len(mock_nodes)} 个节点")

        except Exception as e:
            print(f"添加mock特征节点失败: {e}")
            import traceback
            traceback.print_exc()

    def _setup_websocket_connection(self):
        """设置WebSocket连接到Agent状态包装器"""
        try:
            # 导入WebSocket服务器（延迟导入避免循环依赖）
            from websocket_server import get_websocket_server

            print("[WS SETUP] Importing WebSocket server...")
            # 获取WebSocket服务器实例
            ws_server = get_websocket_server()
            print(f"[WS SETUP] Got WebSocket server: {ws_server}")

            # 将WebSocket服务器连接到Agent状态包装器
            print("[WS SETUP] Connecting WebSocket server to Agent status wrapper...")
            agent_status_wrapper.set_websocket_server(ws_server)
            print("[WS SETUP] WebSocket server connected to Agent status wrapper successfully")

        except Exception as e:
            print(f"[WS SETUP ERROR] Failed to setup WebSocket connection: {e}")
            import traceback
            traceback.print_exc()
            # 即使WebSocket连接失败，也不影响正常功能
            pass