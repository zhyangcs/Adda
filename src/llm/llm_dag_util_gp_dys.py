import dataclasses
import pandas as pd
import re
import termcolor
import networkx as nx
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import StratifiedKFold, KFold, cross_val_score, cross_validate
from src.pg.op_type import *
from src.llm.utils.llm_util import *
from src.llm.utils.parse_util import *
from src.llm.utils.prompt import *
import hashlib
import time
import yaml
from src.pg.py_to_udf import *
import threading
import warnings
from networkx.drawing.nx_agraph import to_agraph
import pickle
from collections import OrderedDict
import heapq
from src.llm.astar_func import *
from src.llm.llm_dag_node import *
from src.llm.agents.nl_agent import *
from src.llm.agents.code_agent import *
from src.llm.utils.code_metrics import *
from src.llm.agents.divide_agent import *
import src.llm.llm_dag_node 
from sklearn.metrics import make_scorer
from src.llm.utils.rag_util import *
import src.env
import torch
from transformers import AutoModel, AutoTokenizer, AutoConfig
from src.llm.utils.common_utils import *
import concurrent.futures
from src.llm.agents.planner_agent import Planner
from bayes_opt import BayesianOptimization
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, Matern, WhiteKernel, ConstantKernel
from scipy.stats import norm
from collections import defaultdict


warnings.filterwarnings("ignore")
# from src.llm.prompt_utils import *

@dataclasses.dataclass
class DRAWNODE():
    """DAG可视化节点数据结构"""
    node_id: int          # 节点唯一标识
    task_code: str        # 特征生成代码
    score: float          # 节点评估分数
    exec_time: float      # 执行耗时
    
    def __hash__(self):
        return hash(self.node_id)

        
@dataclasses.dataclass
class FidelityLevel():
    """保真度层级数据结构"""
    level_id: int         # 保真度层级ID
    sample_ratio: float   # 采样比例 (0.01, 0.04, 0.16, 0.64, 1.0)
    cost: float          # 计算成本
    name: str            # 保真度层级名称
    
    def __hash__(self):
        return hash(self.level_id)
        
        
@dataclasses.dataclass  
class EvaluationRecord():
    """多保真度评估记录"""
    feature_set_id: str   # 特征集合ID
    fidelity_level: int   # 保真度层级
    performance: float    # 模型性能分数
    cost: float          # 评估成本
    timestamp: float     # 评估时间戳
    node: 'LLMDAGNODE'   # 对应的DAG节点
    

class MultiFidelityBayesianOptimizer():
    """多保真度贝叶斯优化器
    
    实现基于多保真度贝叶斯优化的渐进式采样策略，用于高效搜索特征空间
    """
    
    def __init__(self, dataset_size: int, budget: float = 1000.0, random_state: int = 42):
        """
        参数:
            dataset_size: 完整数据集大小
            budget: 总计算预算
            random_state: 随机种子
        """
        # 定义保真度层级（几何级数）
        self.fidelity_levels = [
            FidelityLevel(0, 0.01, 1.0, "level_1%"),    # s_1 = 1%*D
            FidelityLevel(1, 0.04, 4.0, "level_4%"),    # s_2 = 4%*D  
            FidelityLevel(2, 0.16, 16.0, "level_16%"),  # s_3 = 16%*D
            FidelityLevel(3, 0.64, 64.0, "level_64%"),  # s_4 = 64%*D
            FidelityLevel(4, 1.0, 100.0, "level_100%")  # s_5 = 100%*D
        ]
        
        self.dataset_size = dataset_size
        self.budget = budget
        self.spent_budget = 0.0
        self.random_state = random_state
        
        # 存储所有评估记录
        self.evaluation_history = []
        
        # GP模型和数据
        self.gp_model = None
        self.X_observed = []  # 特征集合编码 + 保真度层级
        self.y_observed = []  # 对应的性能分数
        
        # 初始化随机数生成器
        np.random.seed(random_state)
        
    def get_fidelity_cost(self, fidelity_level: int) -> float:
        """获取指定保真度层级的成本"""
        return self.fidelity_levels[fidelity_level].cost
        
    def get_sample_size(self, fidelity_level: int) -> int:
        """获取指定保真度层级的样本大小"""
        ratio = self.fidelity_levels[fidelity_level].sample_ratio
        return max(1, int(self.dataset_size * ratio))
        
    def encode_feature_set(self, node: 'LLMDAGNODE') -> np.ndarray:
        """将特征集合编码为向量表示
        
        使用节点的嵌入向量作为特征集合的编码
        """
        if node.attr_embs is not None:
            # 使用平均池化将嵌入向量降维到固定大小
            emb_vector = node.attr_embs.mean(dim=0).cpu().numpy()
            return emb_vector
        else:
            # 如果没有嵌入向量，使用节点ID的哈希值作为编码
            feature_hash = hash(str(node.node_id)) % 1000000
            return np.array([feature_hash / 1000000.0])
    
    def multifidelity_kernel(self, X1: np.ndarray, X2: np.ndarray) -> np.ndarray:
        """多保真度核函数 k((x,s), (x',s')) = k_x(x,x') * k_s(s,s')
        
        参数:
            X1, X2: 包含特征向量和保真度层级的输入矩阵
                   格式: [feature_vector..., fidelity_level]
        """
        # 检查输入维度
        if X1.ndim == 1:
            X1 = X1.reshape(1, -1)
        if X2.ndim == 1:
            X2 = X2.reshape(1, -1)
            
        # 分离特征向量和保真度层级
        features1 = X1[:, :-1]  # 特征部分
        fidelities1 = X1[:, -1]  # 保真度部分
        
        features2 = X2[:, :-1]
        fidelities2 = X2[:, -1]
        
        # 如果特征维度为0，使用常数核
        if features1.shape[1] == 0:
            K_x = np.ones((len(X1), len(X2)))
        else:
            # 特征核：使用RBF核
            feature_kernel = RBF(length_scale=1.0)
            K_x = feature_kernel(features1, features2)
        
        # 保真度核：指数衰减核
        K_s = np.zeros((len(fidelities1), len(fidelities2)))
        for i, s1 in enumerate(fidelities1):
            for j, s2 in enumerate(fidelities2):
                # 保真度相关性随层级差异指数衰减
                K_s[i, j] = np.exp(-0.5 * (s1 - s2)**2)
        
        return K_x * K_s
    
    def update_gp_model(self):
        """更新高斯过程模型"""
        if len(self.X_observed) < 2:
            return
            
        X = np.array(self.X_observed)
        y = np.array(self.y_observed)
        
        # 使用简单的RBF核（避免自定义核的复杂性）
        kernel = ConstantKernel(1.0) * RBF(1.0) + WhiteKernel(1e-5)
        
        self.gp_model = GaussianProcessRegressor(
            kernel=kernel,
            random_state=self.random_state,
            alpha=1e-6,
            normalize_y=True
        )
        
        try:
            self.gp_model.fit(X, y)
        except Exception as e:
            print(f"GP模型拟合失败: {e}")
            # 如果拟合失败，将模型设为None
            self.gp_model = None
    
    def expected_improvement_per_cost(self, X_candidate: np.ndarray, xi: float = 0.01) -> np.ndarray:
        """计算单位成本期望提升 (Expected Improvement per unit of Cost)
        
        参数:
            X_candidate: 候选点矩阵 [feature_vector..., fidelity_level]
            xi: 探索参数
        """
        if self.gp_model is None:
            # 如果还没有GP模型，返回随机值
            return np.random.random(len(X_candidate))
        
        # 预测均值和方差
        mu, sigma = self.gp_model.predict(X_candidate, return_std=True)
        sigma = sigma.reshape(-1, 1).ravel()
        
        # 当前最佳值（在最高保真度上）
        best_f = max(self.y_observed) if self.y_observed else 0
        
        # 计算期望提升
        with np.errstate(divide='warn'):
            imp = mu - best_f - xi
            Z = imp / sigma
            ei = imp * norm.cdf(Z) + sigma * norm.pdf(Z)
            ei[sigma == 0.0] = 0.0
        
        # 获取成本
        costs = np.array([self.get_fidelity_cost(int(x[-1])) for x in X_candidate])
        
        # 计算单位成本期望提升
        eipu = ei / costs
        
        return eipu
    
    def select_next_evaluation(self, candidate_nodes: list) -> tuple:
        """选择下一个评估点 (特征集合, 保真度层级)
        
        参数:
            candidate_nodes: 候选节点列表
            
        返回:
            (selected_node, fidelity_level): 选择的节点和保真度层级
        """
        if len(candidate_nodes) == 0:
            return None, None
            
        # 生成候选点矩阵
        candidates = []
        node_fidelity_pairs = []
        
        for node in candidate_nodes:
            feature_encoding = self.encode_feature_set(node)
            for fidelity_level in range(len(self.fidelity_levels)):
                # 检查预算约束
                cost = self.get_fidelity_cost(fidelity_level)
                if self.spent_budget + cost <= self.budget:
                    candidate_x = np.concatenate([feature_encoding, [fidelity_level]])
                    candidates.append(candidate_x)
                    node_fidelity_pairs.append((node, fidelity_level))
        
        if len(candidates) == 0:
            return None, None
            
        X_candidates = np.array(candidates)
        
        # 计算采集函数值
        eipu_values = self.expected_improvement_per_cost(X_candidates)
        
        # 选择最大化采集函数的点
        best_idx = np.argmax(eipu_values)
        selected_node, selected_fidelity = node_fidelity_pairs[best_idx]
        
        return selected_node, selected_fidelity
    
    def add_evaluation_record(self, node: 'LLMDAGNODE', fidelity_level: int, 
                            performance: float, cost: float):
        """添加评估记录"""
        # 创建评估记录
        record = EvaluationRecord(
            feature_set_id=str(node.node_id),
            fidelity_level=fidelity_level, 
            performance=performance,
            cost=cost,
            timestamp=time.time(),
            node=node
        )
        
        self.evaluation_history.append(record)
        
        # 更新观测数据
        feature_encoding = self.encode_feature_set(node)
        x_obs = np.concatenate([feature_encoding, [fidelity_level]])
        self.X_observed.append(x_obs)
        self.y_observed.append(performance)
        
        # 更新预算
        self.spent_budget += cost
        
        # 更新GP模型
        self.update_gp_model()
    
    def get_best_feature_set(self):
        """获取预测性能最佳的特征集合"""
        if not self.evaluation_history:
            return None
            
        # 在最高保真度上找到最佳特征集合
        highest_fidelity = len(self.fidelity_levels) - 1
        highest_fidelity_records = [r for r in self.evaluation_history 
                                  if r.fidelity_level == highest_fidelity]
        
        if highest_fidelity_records:
            best_record = max(highest_fidelity_records, key=lambda r: r.performance)
            return best_record.node
        
        # 如果没有最高保真度的记录，使用GP模型预测
        if self.gp_model is not None:
            all_nodes = list(set(r.node for r in self.evaluation_history))
            best_predicted_performance = -float('inf')
            best_node = None
            
            for node in all_nodes:
                feature_encoding = self.encode_feature_set(node)
                x_pred = np.concatenate([feature_encoding, [highest_fidelity]]).reshape(1, -1)
                predicted_performance, _ = self.gp_model.predict(x_pred, return_std=True)
                
                if predicted_performance[0] > best_predicted_performance:
                    best_predicted_performance = predicted_performance[0]
                    best_node = node
            
            return best_node
        
        # 备选方案：返回当前最佳记录
        best_record = max(self.evaluation_history, key=lambda r: r.performance)
        return best_record.node
    
    def is_budget_exhausted(self) -> bool:
        """检查预算是否耗尽"""
        return self.spent_budget >= self.budget
        
    def cold_start_initialization(self, initial_nodes: list, n_init: int = 10):
        """冷启动初始化
        
        在最低保真度上随机评估n_init个特征集合
        """
        if len(initial_nodes) == 0:
            return []
            
        # 随机选择节点进行初始化
        if len(initial_nodes) <= n_init:
            selected_nodes = initial_nodes
        else:
            selected_nodes = np.random.choice(initial_nodes, size=n_init, replace=False)
        
        initialized_records = []
        lowest_fidelity = 0  # 最低保真度层级
        
        for node in selected_nodes:
            if self.is_budget_exhausted():
                break
                
            cost = self.get_fidelity_cost(lowest_fidelity)
            if self.spent_budget + cost > self.budget:
                continue
                
            # 使用占位符性能分数，实际实现中会在外部调用evaluate_node_at_fidelity
            performance = 0.5  # 占位符，实际评估在外部完成
            
            self.add_evaluation_record(node, lowest_fidelity, performance, cost)
            initialized_records.append((node, lowest_fidelity, performance))
            
        return initialized_records

        
# RAG计算相似度的嵌入向量模型设置        
config = AutoConfig.from_pretrained(rag_model_id_or_path, trust_remote_code=True)
config.use_sdpa = True
config.use_flash_attn = False
# emb_model = AutoModel.from_pretrained(rag_model_id_or_path, trust_remote_code=True, config=config, device_map="cuda:0")
emb_model = AutoModel.from_pretrained(rag_model_id_or_path, trust_remote_code=True, config=config, device_map="cpu", local_files_only=True)
emb_model.eval()
emb_tokenizer = AutoTokenizer.from_pretrained(rag_model_id_or_path, trust_remote_code=True, local_files_only=True)   
 
class LLMDagConstructor():
    """LLM驱动的特征工程DAG构造器
    
    核心功能：
    - 管理特征生成的有向无环图(DAG)
    - 执行A*搜索算法生成特征
    - 评估特征节点性能
    - 与NLAgent/CodeAgent交互生成自然语言描述和代码
    """
    
    def __init__(self, task_type:str, eval_model_type:str, beam_limit:int = 6, async_mode:bool = False, do_feature_selection:bool = False, boost_training:bool = False, high_order_num:int = 2, token_limit:int = 800, use_multifidelity:bool = True, mf_budget:float = 1000.0):
        """
        参数:
            task_type: 任务类型(分类/回归)
            eval_model_type: 评估模型类型(RF/XGB等)
            beam_limit: 搜索宽度限制
            async_mode: 是否启用异步执行模式
            do_feature_selection: 是否执行特征选择
            boost_training: 是否启用加速训练模式
            high_order_num: 高阶特征生成阶数
            token_limit: LLM的token限制
            use_multifidelity: 是否使用多保真度贝叶斯优化
            mf_budget: 多保真度优化的计算预算
        """
        self.node_id = global_node_id
        self.column_info = {}
        self.boost_training = boost_training
        self.async_mode = async_mode
        self.beam_limit = beam_limit
        self.task_type = task_type
        self.use_multifidelity = use_multifidelity
        self.mf_budget = mf_budget
        print(f"current task type is {task_type}")
        
        if self.async_mode:
            self.aliveLock = threading.Lock()
            self.execnumLock = threading.Lock()
            self.finishedLock = threading.Lock()
        self.exec_thread = []
        self.barrier_thread = []
        self.attrname2node = {}
        self.finished_num = []
        self.finish = False
        
        self.do_feature_selection = do_feature_selection
        self.eval_model_type, self.eval_model = get_model(eval_model_type, task_type)
        self.high_order_num = high_order_num
        self.token_limit = token_limit
        self.nl_agent = NLAgent(self.eval_model_type)
        
        # 多保真度优化器（在初始化任务参数时创建）
        self.mf_optimizer = None
        
        
    def init_task_params(self, data_agenda:list[str], data_desc:list[str], target_col:str, tb_name:str = None, csv_path:str = None, do_unfinished:bool = False, task_name:str = None):
        """
        初始化任务参数（参考test_util.py的TestDir类）
        
        参数:
            data_agenda: 数据列描述列表
            data_desc: 数据集总体描述 
            target_col: 目标列名
            tb_name: 数据库表名
            csv_path: 数据文件路径
            do_unfinished: 是否继续未完成任务
            task_name: 任务名称
        """
        # 如果不是处理未完成的任务，则进行初始化
        if not do_unfinished:
            # 设置目标列和任务描述
            self.target_col = target_col
            self.task_desc = "".join(data_desc)
            
            # 使用正则表达式解析数据议程中的每一行
            # 格式为 "列名:列描述"
            pattern = r"(.*?):(.*?)"
            for line in data_agenda:
                match = re.search(pattern, line)
                if match:
                    # 将列信息存储到column_info字典中
                    self.column_info[match.group(1)] = line
                    # 如果是目标列，在描述后添加标记
                    if match.group(1) == self.target_col:
                        self.column_info[match.group(1)] = self.column_info[match.group(1)][:-1] + " (target column)\n"
                else:
                    # 如果匹配失败，打印错误信息并终止程序
                    print("match failed", line)
                    assert 0 == 1

            # 设置表名
            self.tb_name = tb_name        
            
            # 获取数据集大小并初始化多保真度优化器
            if tb_name != None:
                # 获取表中的总行数
                self.total_dataset_size = int(pd.read_sql(f"SELECT COUNT(*) FROM {tb_name}", get_conn())['count'][0])
                print(f"Total dataset size: {self.total_dataset_size}")
                
                # 初始化多保真度贝叶斯优化器
                if self.use_multifidelity:
                    self.mf_optimizer = MultiFidelityBayesianOptimizer(
                        dataset_size=self.total_dataset_size,
                        budget=self.mf_budget,
                        random_state=42
                    )
                    print(f"Initialized multi-fidelity optimizer with budget {self.mf_budget}")
                
                # 使用多保真度策略采样数据，初始时使用最低保真度
                if self.use_multifidelity:
                    initial_sample_size = self.mf_optimizer.get_sample_size(0)  # 最低保真度
                else:
                    # 原有逻辑：读取数据，最多读取4000行或总行数的1/4
                    initial_sample_size = min(4000, self.total_dataset_size//4)
                
                df = pd.read_sql(f"SELECT * FROM {tb_name} LIMIT {initial_sample_size}", get_conn())
                print(f"Initial sampling {df.shape} (fidelity level: {'MF-Level0' if self.use_multifidelity else 'Fixed'})")
                
            # 如果提供了CSV文件路径，从CSV文件读取数据
            elif csv_path != None:
                df = pd.read_csv(csv_path)
                self.total_dataset_size = len(df)
                
                # 初始化多保真度优化器
                if self.use_multifidelity:
                    self.mf_optimizer = MultiFidelityBayesianOptimizer(
                        dataset_size=self.total_dataset_size,
                        budget=self.mf_budget,
                        random_state=42
                    )
                    
                    # 使用多保真度策略采样
                    initial_sample_size = self.mf_optimizer.get_sample_size(0)
                    df = df.sample(n=min(initial_sample_size, len(df)), random_state=42)
                    print(f"CSV sampling {df.shape} from total {self.total_dataset_size} (MF-Level0)")

            # 初始化根节点
            self.init_root_node(df)  
            
            # 初始化层级状态列表，第一层只包含根节点
            self.level_states = [[self.root]]
            
            # 创建有向图
            self.dag = nx.DiGraph()
            # 添加根节点到图中
            self.dag.add_node(self.root)
            
            # 如果提供了任务名称，设置任务名称
            if task_name != None:
                self.task_name = task_name
            
            # 绘制当前状态图（用于调试）
            self.draw_current(self.root.node_id)
            
            # 初始化前一个索引
            self.pre_idx = 0
        
    def generate_emb(self, node):
        """生成节点操作的嵌入向量（使用Hugging Face模型）
        
        实现要点：
        1. 使用最后token池化策略
        2. 支持左填充处理
        3. 进行L2归一化
        """
        def last_token_pool(last_hidden_states: torch.Tensor,
                        attention_mask: torch.Tensor) -> torch.Tensor:
            left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
            if left_padding:
                return last_hidden_states[:, -1]
            else:
                sequence_lengths = attention_mask.sum(dim=1) - 1
                batch_size = last_hidden_states.shape[0]
                return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]
        
        t1 = time.time()
        # add the embedding information
        op_list = node.operation_desc
        if type(op_list) == "str":
            op_list = [op_list]
        input_batch = emb_tokenizer(op_list, padding=True, max_length=512, truncation=True, return_tensors="pt").to(emb_model.device)
        with torch.no_grad():
            outputs = emb_model(**input_batch)
            embedding = last_token_pool(outputs.last_hidden_state, input_batch['attention_mask'])
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=-1)
            if node.attr_embs == None:
                node.attr_embs = embedding
            else:
                node.attr_embs = torch.concat([node.attr_embs, embedding], dim=0)
                
        return node
        
    def task_to_features(self, cur_node:LLMDAGNODE, cur_step_idx:int = 0):
        """将任务描述转换为特征节点（核心生成逻辑）
        
        实现流程：
        1. NLAgent生成特征描述
        2. CodeAgent生成可执行代码
        3. 复杂度检查与代码分割
        4. DAG节点添加与可视化
        """
        def gen_code_node(next_node):
            """
            生成特征节点的代码并验证其可执行性
            
            参数:
                next_node: LLMDAGNODE对象，待生成代码的节点
                
            返回:
                tuple: (next_node, success)
                    - next_node: 处理后的节点对象，如果生成失败则为None
                    - success: 布尔值，表示代码生成是否成功
            """
            try:
                # 1. 使用code_agent生成特征转换代码
                could_exec_code = code_agent.feature_to_code(next_node)
                
                # 2. 检查是否需要分治处理
                # 条件1: 当前步骤小于高阶特征数且代码生成失败
                # 条件2: 代码复杂度超过阈值
                if cur_step_idx < self.high_order_num and not could_exec_code or whether_code_complex(next_node.task_code, next_node.column_info):
                    # 使用分治策略重新生成代码
                    next_node, could_exec_code = divide_agent.divide_code(next_node)
                    
                # 3. 如果代码生成成功，尝试生成修复特征
                if could_exec_code:
                    could_exec_fix = code_agent.generate_fixing_features(next_node, self.label)
                else:
                    could_exec_fix = False
                    
                # 4. 生成节点的嵌入向量（用于相似度计算）
                next_node = self.generate_emb(next_node)
                
                # 5. 返回结果
                # 只有当代码生成和修复特征都成功时，才返回成功
                if could_exec_code and could_exec_fix:
                    return next_node, True
                else:
                    return None, False
            
            except Exception as e:
                # 6. 异常处理
                print(termcolor.colored(f"Error: {e}", "red"))
                return None, False
        
        # 1. NLAgent generate the description
        nodes = topKSimilarNodes(cur_node, self.dag, src.env.topK_rag)
        example_prompt = nodes2example(nodes, self.dag)
        next_state = self.nl_agent.task_to_desc(cur_node, src.env.diverse_num, self.target_col, cur_step_idx, self.high_order_num, self.token_limit, example_prompt)

        # 2. CodeAgent generate the code and fixing code
        code_agent = CodeAgent()
        divide_agent = DivideAgent(self.token_limit)
        next_states_with_code = []
        # for next_node in next_state[:]:
        #     try:
        #         could_exec_code = code_agent.feature_to_code(next_node)
        #         # for each node, check whether need to be divide and conquer
        #         if cur_step_idx < self.high_order_num and not could_exec_code or whether_code_complex(next_node.task_code, next_node.column_info):
        #             next_node, could_exec_code = divide_agent.divide_code(next_node)

        #         if could_exec_code:
        #             could_exec_fix = code_agent.generate_fixing_features(next_node, self.label)
        #         else:
        #             could_exec_fix = False
                
        #         # generate the embedding msg
        #         next_node = self.generate_emb(next_node)    
                    
        #         if could_exec_code and could_exec_fix:
        #             next_states_with_code.append(next_node)
        #             self.dag.add_node(next_node)
        #             self.dag.add_edge(cur_node, next_node)
        #             self.attrname2node[list(next_node.write_set)[0]] = next_node
        #             self.draw_current(next_node.node_id)
        #         else:
        #             print(termcolor.colored(f"Drop node for code: {could_exec_code}, for fix: {could_exec_fix}", "red"))
                    
        #     except Exception as e:
        #         # if exception occur in the middle, then we drop the code
        #         print(termcolor.colored(f"Error: {e}", "red"))
        #         continue
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = executor.map(gen_code_node, next_state[:])
        # print(termcolor.colored(f"Get fully {len(results)}"))
        for next_node, success in results:
            if success:
                next_states_with_code.append(next_node)
                self.dag.add_node(next_node)
                self.dag.add_edge(cur_node, next_node)
                self.attrname2node[list(next_node.write_set)[0]] = next_node
                self.draw_current(next_node.node_id)
            else:
                print(termcolor.colored(f"Drop node for code", "red"))
        
        return next_states_with_code
 
    def draw_current(self, idx:int = 0):
        """DAG可视化方法
        
        功能：
        1. 将内存中的特征工程DAG转换为可视化图形
        2. 保存当前特征生成流程的快照
        3. 展示节点评估分数和执行耗时等关键指标
        
        参数：
        idx -- 用于区分不同阶段的绘图序号（默认0）
        """
        if hasattr(self, 'task_name'):
            # 数据结构转换：将LLMDAGNODE转换为轻量级绘图节点
            draw_nodes = nx.DiGraph()
            nodes_map = dict()  # 原始节点到绘图节点的映射

            # 节点转换（保留核心元数据）
            for node in self.dag.nodes:
                new_node = DRAWNODE(
                    node_id=node.node_id,
                    task_code=node.task_code,
                    score=node.final_score,
                    exec_time=node.exec_time
                )
                nodes_map[node] = new_node
                draw_nodes.add_node(new_node)
            
            # 边关系重建
            for edge in self.dag.edges:
                draw_nodes.add_edge(nodes_map[edge[0]], nodes_map[edge[1]])
                
            # 图形渲染配置
            agraph = to_agraph(draw_nodes)  # 转换为Graphviz对象
            agraph.graph_attr['rankdir'] = 'LR'  # 从左到右布局
            agraph.layout(prog='dot')  # 使用层次布局算法

            # 持久化存储
            dir_path = os.path.join(test_save_path, self.task_name, "graph")
            os.makedirs(dir_path, exist_ok=True)  # 自动创建目录
            agraph.draw(os.path.join(dir_path, f"current_graph_{idx}.png"))  # 保存为PNG
            
    def python2c_code(code, input_feature, output_feature) -> str:
        prompt_str = f"""{APPLY_PYTHON2C_PROMPT.format(python_code = code, input_feature = input_feature, output_feature = output_feature)}\n"""
        retry_time = 1
        while retry_time > 0:
            try: 
                raw_code = send_prompt("", prompt_str)
                print(termcolor.colored(raw_code, "green"))
                code = parse_code(raw_code, language="c++")
                print(termcolor.colored(code, "green"))
                # check whether the code could be compiled
                cur_udf = Py2Udf.get_udf_from_template(code)
                code_path = os.path.join(udf_path, "code", "tmpudf.cpp")
                lib_path = os.path.join(udf_path, "lib", "tmpudf.so")
                with open(code_path, 'w') as f:
                    f.write(cur_udf)
                compile_udf(code_path=code_path, lib_path=lib_path)
                break 
            except Exception as e:
                print(e, termcolor.colored("Error:regrenerate the code", "red"))
                retry_time -= 1
                continue
        return code
                
    def pair_to_code(self, cur_node:LLMDAGNODE, pair:tuple[str, str]):
        if pair[0] == "No need to preprocess":
            return "no need", ""
        elif pair[1] in cur_node.column_info.keys():
            if pair[0] == "Fill NaN":
                new_col_name = pair[1] + "_Fillna"
                return "df['%s'] = df['%s'].fillna(df['%s'].mode()[0])" %(new_col_name, pair[1], pair[1]), new_col_name
            elif pair[0] == "Normalization":
                new_col_name = pair[1] + "_Norm"
                return """from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
df['%s'] = scaler.fit_transform(df[['%s']])""" %(new_col_name, pair[1]), new_col_name
            elif pair[0] == "Label encoding":
                new_col_name = pair[1] + "_Label"
                return """from sklearn.preprocessing import LabelEncoder
label_encoder = LabelEncoder()
df['%s'] = label_encoder.fit_transform(df[['%s']])""" %(new_col_name, pair[1]), new_col_name
        return "", ""
    
    def astar_one_step_multifidelity(self, cur_feature_idx: int, planner_agents: Planner):
        """多保真度A*算法单步执行
        
        使用贝叶斯优化策略选择下一个要评估的 (节点, 保真度层级) 对
        """
        if not self.use_multifidelity or self.mf_optimizer is None:
            # 如果未启用多保真度，回退到原有方法
            return self.astar_one_step(cur_feature_idx, planner_agents)
        
        # 检查预算是否耗尽
        if self.mf_optimizer.is_budget_exhausted():
            print(termcolor.colored(f"Multi-fidelity budget exhausted (spent: {self.mf_optimizer.spent_budget:.1f})", "yellow"))
            return
        
        # 收集所有候选节点（当前状态中的节点）
        candidate_nodes = [node for node in self.cur_states]
        
        if len(candidate_nodes) == 0:
            print(termcolor.colored("No candidate nodes available", "yellow"))
            return
            
        # 使用贝叶斯优化选择下一个评估点
        selected_node, selected_fidelity = self.mf_optimizer.select_next_evaluation(candidate_nodes)
        
        if selected_node is None:
            print(termcolor.colored("No valid evaluation candidate found (budget constraint)", "yellow"))
            return
        
        # 移除选中的节点从当前状态
        if selected_node in self.cur_states:
            self.cur_states.remove(selected_node)
            heapq.heapify(self.cur_states)
        
        print(termcolor.colored(f"Selected node {selected_node.node_id} at fidelity level {selected_fidelity}", "blue"))
        
        # 执行特征生成（如果需要）
        if selected_fidelity == 0 or len(selected_node.operation_desc) == 0:
            # 对于最低保真度或根节点，生成新的特征
            selected_node.planner_suggest = planner_agents.one_step_planning(self.dag)[1]
            next_states = self.task_to_features(selected_node, cur_feature_idx)
        else:
            # 对于高保真度评估，直接评估现有节点
            next_states = [selected_node]
        
        # 在选定的保真度层级上评估节点（们）
        for node in next_states:
            performance, cost = self.evaluate_node_at_fidelity(node, selected_fidelity)
            
            # 更新节点的最终分数（用于A*算法）
            if selected_fidelity == len(self.mf_optimizer.fidelity_levels) - 1:
                # 最高保真度的结果直接作为最终分数
                node.final_score = performance
            else:
                # 低保真度结果需要调整权重
                node.final_score = performance * 0.8  # 降权处理
            
            # 添加评估记录到多保真度优化器
            self.mf_optimizer.add_evaluation_record(node, selected_fidelity, performance, cost)
            
            # 计算启发式函数值并加入优先队列
            total_node_num = 0
            for dag_node in self.dag.nodes:
                total_node_num += (1 + self.dag.out_degree(dag_node))
                
            node.utility = monte_carlo_like_heuristic_func(
                self.dag.out_degree(node) + 1, 
                total_node_num, 
                node.final_score
            )
            
            # 将节点重新加入候选队列
            if node not in self.cur_states:
                heapq.heappush(self.cur_states, node)
        
        # 更新前序状态
        self.pre_states = self.cur_states.copy()
        self.node_id = src.llm.llm_dag_node.global_node_id
        
        # 打印多保真度优化器状态
        print(f"Multi-fidelity optimizer status: budget used {self.mf_optimizer.spent_budget:.1f}/{self.mf_optimizer.budget}, "
              f"evaluations: {len(self.mf_optimizer.evaluation_history)}")

    def astar_one_step(self, cur_feature_idx:int, planner_agents:Planner):
        '''
        For cur_states, we generate the next states using the self-defined function
        '''
        # 如果启用了多保真度，使用多保真度方法
        if self.use_multifidelity and self.mf_optimizer is not None:
            return self.astar_one_step_multifidelity(cur_feature_idx, planner_agents)
            
        # 原有的A*单步逻辑
        # TEST: Planner执行一次
        next_node_id, suggestions_str = planner_agents.one_step_planning(self.dag)

        # 1. generate the next states from original states
        next_states = []

        # 根据next_node_id查找并移除节点
        index_to_remove = None
        for i, node in enumerate(self.cur_states):
            if node.node_id == next_node_id:
                index_to_remove = i
                break
        
        if index_to_remove is None:
            raise ValueError(f"Node with id {next_node_id} not found in cur_states")
        
        # 移除找到的节点并重新构建堆
        cur_node = self.cur_states.pop(index_to_remove)
        heapq.heapify(self.cur_states)
                
        print(termcolor.colored(f"the current node: {cur_node.node_id}", "blue"))

        cur_node.planner_suggest = suggestions_str

        cur_next_states = self.task_to_features(cur_node, cur_feature_idx)
        next_states += cur_next_states
                
        # 2. choose the top-k states, by self
        total_node_num = 0
        for node in self.dag.nodes:
            total_node_num += (1 + self.dag.out_degree(node))
        for next_node in next_states:
            self.evaluate_node(next_node)
            next_node.utility = monte_carlo_like_heuristic_func(self.dag.out_degree(next_node)+1, total_node_num, next_node.final_score)
            heapq.heappush(self.cur_states, next_node)
        cur_node.utility = monte_carlo_like_heuristic_func(self.dag.out_degree(cur_node)+1, total_node_num, cur_node.final_score)
        self.pre_states = self.cur_states.copy()
        self.node_id = src.llm.llm_dag_node.global_node_id
        
    def astar_k_step(self, step_num:int, data_agenda:list[str] = None, data_desc:list[str] = None, target_col:str = None, tb_name:str=None, csv_path:str=None, do_unfinished:bool = False, task_name:str = None):
        """A*算法多步执行入口函数（支持多保真度贝叶斯优化）
        参数:
            step_num: 需要执行的搜索步数（节点扩展次数）
            data_agenda: 数据列描述列表
            data_desc: 数据集总体描述
            target_col: 目标列名
            tb_name: 数据库表名
            csv_path: 数据文件路径
            do_unfinished: 是否继续未完成任务
            task_name: 任务名称
        """
        # 初始化A*搜索类型
        self.search_type = "ASTAR"
        # 同步全局节点ID（用于节点唯一标识）
        src.llm.llm_dag_node.global_node_id = self.node_id
        
        # 初始化任务参数（数据加载/预处理）
        self.init_task_params(data_agenda, data_desc, target_col, tb_name, csv_path, do_unfinished, task_name)
        data_age = '\n'.join(self.column_info.values())

        # TEST: 测试planner
        planner_agents = Planner(self.root, target_col, self.task_desc, data_age)

        # 新建任务时初始化优先队列
        if not do_unfinished:
            self.cur_states = []
            heapq.heappush(self.cur_states, self.root)  # 使用最小堆实现优先队列
            self.pre_states = self.cur_states.copy()  # 保存前序状态用于恢复
            
            # 多保真度优化：冷启动初始化
            if self.use_multifidelity and self.mf_optimizer is not None:
                print("Performing cold start initialization...")
                initial_nodes = [self.root]  # 从根节点开始
                self.mf_optimizer.cold_start_initialization(initial_nodes, n_init=3)
        
        # 设置当前搜索状态（异步模式暂不支持）
        self.cur_states = self.pre_states
        # 获取断点续做起始索引
        start_idx = self.pre_idx
        if start_idx != 0:
            print(f"current states is reload: {self.finish}, {start_idx}")
            self.draw_current(-20)  # 绘制当前DAG状态（调试用）
        
        # 用于追踪性能收敛的变量
        best_performance_history = []
        convergence_threshold = 0.001  # 性能改善阈值
        convergence_patience = 5       # 连续多少步没有改善就终止
        no_improvement_count = 0
            
        # 主循环：执行指定步数的节点扩展
        for i in range(start_idx, step_num, 1):
            # ---- Add check here ----
            if not self.cur_states: # Check if heap is empty before starting step
                print(termcolor.colored(f"A* Search stopped at step {i} because the candidate heap is empty.", "yellow"))
                break # Stop the loop gracefully
            # ---- End check ----
            
            # 多保真度优化：检查终止条件
            if self.use_multifidelity and self.mf_optimizer is not None:
                # 预算耗尽检查
                if self.mf_optimizer.is_budget_exhausted():
                    print(termcolor.colored(f"Multi-fidelity optimization stopped at step {i} due to budget exhaustion.", "yellow"))
                    break
                
                # 性能收敛检查
                if len(self.mf_optimizer.evaluation_history) > 0:
                    # 获取当前最佳性能
                    current_best = max(record.performance for record in self.mf_optimizer.evaluation_history)
                    best_performance_history.append(current_best)
                    
                    # 检查是否有足够的历史记录来判断收敛
                    if len(best_performance_history) > convergence_patience:
                        # 计算最近几步的性能改善
                        recent_improvement = (best_performance_history[-1] - 
                                            best_performance_history[-convergence_patience-1])
                        
                        if recent_improvement < convergence_threshold:
                            no_improvement_count += 1
                        else:
                            no_improvement_count = 0
                        
                        # 如果连续多步没有显著改善，提前终止
                        if no_improvement_count >= convergence_patience:
                            print(termcolor.colored(
                                f"Multi-fidelity optimization stopped at step {i} due to performance convergence "
                                f"(improvement < {convergence_threshold} for {convergence_patience} steps).", "yellow"))
                            break

            self.astar_one_step(i, planner_agents)          # 单步A*搜索
            self.draw_current(-1*i)         # 可视化当前状态
            self.pre_idx = i + 1            # 更新进度标识
            
            # 持久化当前状态（防止意外中断）
            with open(os.path.join(proj_path, "src", "cur_states.pkl"), "wb") as f:
                pickle.dump(self, f)
        
        # 多保真度优化：最终推荐
        if self.use_multifidelity and self.mf_optimizer is not None:
            best_node = self.mf_optimizer.get_best_feature_set()
            if best_node is not None:
                print(termcolor.colored(f"Multi-fidelity optimization recommends node {best_node.node_id} "
                                      f"with predicted best performance.", "green"))
                
                # 确保最佳节点在输出节点中
                if hasattr(self, 'output_nodes'):
                    self.output_nodes = [best_node]
                
            # 打印优化总结
            total_evaluations = len(self.mf_optimizer.evaluation_history)
            budget_used = self.mf_optimizer.spent_budget
            print(f"Multi-fidelity optimization summary:")
            print(f"  Total evaluations: {total_evaluations}")
            print(f"  Budget used: {budget_used:.1f}/{self.mf_optimizer.budget}")
            print(f"  Budget efficiency: {total_evaluations/budget_used:.2f} evals per cost unit")
                
        # 后处理：生成最终特征代码
        self.compute_best_code()
        self.finish = True  # 标记任务完成


    # TODO: 参照astar_k_step，写planner_k_step方法，该方法用于使用planner类替代蒙特卡洛算法来拓展搜索树
        # 1. 编写Planner类，其能够根据设计，结合输入进行分析，完成任务
        # 2. 编写planner_k_step()，要求调用Planner类
        # 3. 编写planner_one_step()，要求使用传入的Planner类弹出下一步要拓展的节点并调用MainAgent等进行处理
        
    def async_task_to_features(self, cur_node:LLMDAGNODE, cur_feature_idx:int, next_states):
        cur_next_states = self.task_to_features(cur_node, cur_feature_idx)
        self.finishedLock.acquire()
        next_states += cur_next_states
        self.finishedLock.release()
    
    def init_root_node(self, df):
        '''
        get score in the root node
        '''
        # df = pd.read_csv(rootpath + self.dir_name + "/train_new.csv")
        
        if self.target_col in df.columns:
            # change the column of 
            self.label, _ = prepare_df_for_train(pd.DataFrame(df[self.target_col]))
            df = df.drop(columns = [self.target_col])
        else:
            print(df.columns)
            print(termcolor.colored("Error: the target column is not in the dataframe", "red"))
        
        final_score, init_scores, attr_imp_list = self.get_scores(df)
        op_list = list(self.column_info.values())
        print("type of op_list", type(op_list))
        
        if self.async_mode:
            self.aliveLock.acquire()
        self.root = LLMDAGNODE(allocate_node_id(), "", set(), set(), df, df, self.column_info, op_list , OpTypeEnum.UNSUPPORT, init_scores, final_score, "", [], [], None, True, True, 0, attr_imp_list, None)
        
        # init the embedding msg
        self.root = self.generate_emb(self.root)
        
        self.root.attr_imp_order = list(self.column_info.keys())
        if self.async_mode:
            self.aliveLock.release()
        
    def evaluate_node_at_fidelity(self, node: LLMDAGNODE, fidelity_level: int):
        """在指定保真度层级上评估节点性能
        
        参数:
            node: 要评估的节点
            fidelity_level: 保真度层级 (0-4)
            
        返回:
            (performance_score, cost): 性能分数和计算成本
        """
        if not self.use_multifidelity or self.mf_optimizer is None:
            # 如果未启用多保真度，使用原有方法
            return self.evaluate_node(node), 1.0
            
        # 获取指定保真度层级的样本大小
        sample_size = self.mf_optimizer.get_sample_size(fidelity_level) 
        cost = self.mf_optimizer.get_fidelity_cost(fidelity_level)
        
        try:
            # 从数据库或原始数据源获取指定大小的样本
            if hasattr(self, 'tb_name') and self.tb_name is not None:
                # 从数据库采样
                sampled_df = pd.read_sql(f"SELECT * FROM {self.tb_name} ORDER BY RANDOM() LIMIT {sample_size}", get_conn())
            else:
                # 如果是CSV数据，从原始数据中采样
                # 这里假设我们保存了原始数据的引用
                sampled_df = node.out_cur_df.sample(n=min(sample_size, len(node.out_cur_df)), random_state=42)
            
            # 为节点准备数据
            if self.target_col in sampled_df.columns:
                label_df = pd.DataFrame(sampled_df[self.target_col])
                sampled_df = sampled_df.drop(columns=[self.target_col])
                sample_label, _ = prepare_df_for_train(label_df)
            else:
                sample_label = self.label[:len(sampled_df)] if len(self.label) >= len(sampled_df) else self.label
            
            # 评估性能
            performance_score = self.get_scores_with_data(sampled_df, sample_label)
            
            print(f"Evaluated node {node.node_id} at fidelity level {fidelity_level} "
                  f"(sample_size={sample_size}, cost={cost:.1f}, score={performance_score:.4f})")
            
            return performance_score, cost
            
        except Exception as e:
            print(f"Error evaluating node {node.node_id} at fidelity {fidelity_level}: {e}")
            # 如果评估失败，返回较低的分数和预期成本
            return 0.1, cost

    def get_scores_with_data(self, df: pd.DataFrame, label=None):
        """使用指定数据和标签计算模型性能分数
        
        参数:
            df: 特征数据框
            label: 标签数据，如果为None则使用self.label
            
        返回:
            平均交叉验证分数
        """
        try:
            if label is None:
                label = self.label
                
            new_df, new_label = prepare_df_for_train(df, label)
            skf = StratifiedKFold(n_splits=min(5, len(new_df)), shuffle=True, random_state=1) if self.task_type == "classify" else KFold(n_splits=min(5, len(new_df)), shuffle=True, random_state=1)
            new_df = move_id_to_first(new_df, 'id')
            
            result = cross_validate(self.eval_model, new_df, new_label, cv=skf, scoring="roc_auc" if self.task_type == "classify" else make_scorer(one_minus_rae), return_estimator=True)
            cv_result = result['test_score']
            
            return cv_result.mean()
        except Exception as e:
            print(termcolor.colored(f"Error in get_scores_with_data: {e}", "red"))
            return 0.1

    def evaluate_node(self, node: LLMDAGNODE):
        """评估节点性能（原有方法，保持向后兼容性）"""
        print(termcolor.colored(f"the node{node.node_id} is evaluating : \n {node.task_code}, \n {node.out_cur_df.info()}", "yellow"))
        node.final_score, node.scores, node.attr_imp_order = self.get_scores(node.out_cur_df)
        return node.final_score

    def get_scores(self, df:pd.DataFrame):
        """
        get roc auc score in the raw model for lightgbm
        """
        try:
            new_df, new_label = prepare_df_for_train(df, self.label)
            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=1) if self.task_type == "classify" else KFold(n_splits=5, shuffle=True, random_state=1)
            new_df = move_id_to_first(new_df, 'id')
            
            result = cross_validate(self.eval_model, new_df, new_label, cv=skf, scoring="roc_auc" if self.task_type == "classify" else make_scorer(one_minus_rae), return_estimator=True)
            cv_result = result['test_score']
            
            print(termcolor.colored(f"the model name: {self.eval_model_type}, cv result {cv_result}, cv_mean {cv_result.mean()}", "yellow"))
        except Exception as e:
            print(termcolor.colored(f"Error in get_scores: {e}", "red"))
            return -1, None, None
        
        return cv_result.mean(), None, None # do not consider the feature importance in this version
        
    def compute_best_code(self, file_path:str = None):
        """
        for each leave node, we fetch all features, and choose the most important features, then we decide topk features we choose
        """
        if file_path != None:
            os.makedirs(file_path, exist_ok=True)
        if self.search_type == "BFS":
            self.output_nodes = self.cur_states
        elif self.search_type == "ASTAR":
            # get the topk nodes for score
            nodes = self.dag.nodes()
            self.output_nodes = heapq.nlargest(1, nodes, key = lambda x: x.final_score) # you could change the topk here [we current use 1]
            
        self.pipes = [PIPE() for _ in range(len(self.output_nodes))]
        for idx in range(len(self.pipes)):
            self.pipes[idx].pipe_id = idx
            
        for idx, node in enumerate(self.output_nodes):
            print("--------------------------")
            print(node.whole_code)
            score, _, _ = self.get_scores(self.root.out_cur_df)
            score1, _, _ = self.get_scores(node.out_cur_df)
            print(termcolor.colored("the original final score: "+str(score), "red"))
            print(termcolor.colored("the whole feature score: "+str(score1), "red"))
            
            # set the whole code    
            code_list = []
            code_list.append(self.fetch_code_from_leaf(node))
            non_numeric_cols = node.out_cur_df.select_dtypes(exclude=np.number).columns.tolist()
            
            for col in non_numeric_cols:
                if f"{col}_Label" not in node.out_cur_df.columns:
                    code_list.append("\n# task desc: convert the non-numeric columns to numeric columns\n")
                    code, _ = self.pair_to_code(node, ("Label encoding", col))
                    code_list.append(code)
            
            drop_cols = ",".join(list(map(lambda x: "'"+x+"'" ,non_numeric_cols)))
            node.drop_attrs = non_numeric_cols
            code_list.append("\n# task desc: drop the columns not used in the best model")
            code_list.append("\ndf = df.drop(columns = [%s])" %(drop_cols))
            node.whole_code = "".join(code_list)
            
            
    def get_best_code(self):
        """
        store the best code to the given location `file_path`
        """
        pycode_file = os.path.join(test_save_path, self.task_name, "pycodes")
        if not os.path.exists(pycode_file):
            os.makedirs(pycode_file)
        for idx, node in enumerate(self.output_nodes):
            code_path = os.path.join(pycode_file, f"pipeline_{node.node_id}.py")
            with open(code_path, "w") as f:
                f.write("import pandas as pd\n")
                f.write("import psycopg2\n")
                f.write(f"conn = psycopg2.connect(dbname='{pg_db}', user='{pg_user}', port={pg_port})\n")
                f.write('df = pd.read_sql(\"SELECT * FROM %s LIMIT 500\", conn)\n' %(self.tb_name))
                f.write(node.whole_code)
            self.pipes[idx].code_path = code_path
                
        return [node.node_id for node in self.output_nodes]


    def retest_time(self, new_df):
        # from the root, we reexec the code and reeval the time with larger df
        cur_node = self.root
        queue = list(self.dag.successors(cur_node))
        self.root.out_cur_df = new_df
        while len(queue) > 0:
            cur_node = queue.pop(0)
            cur_node.in_cur_df = cur_node.out_cur_df
            
            exec_env = {'df': cur_node.in_cur_df}
            # first we exec the fixing node
            for node in cur_node.fixing_node[:] + [cur_node]:
                startt = time.time()
                exec(node.task_code, exec_env)
                endt = time.time()
                node.exec_time = endt - startt
            for node in self.dag.successors(cur_node):
                queue.append(node)
        
        self.draw_current(-1)
        
    def correct_node(self, node_id, code):
        for node in self.dag.nodes:
            nodes = [node] + node.fixing_node
            for in_node in nodes:
                if in_node.node_id == node_id:
                    in_node.task_code = code
                    return True
        return False
    
    def fetch_code_from_leaf(self, node:LLMDAGNODE):
        """
        fetch the code from the leaf to the root
        """
        cur_node = node
        code_map= OrderedDict()
        while True:
            if cur_node == self.root:
                break
            # add_unsupport = "[UNSUPPORT]" if cur_node.op_type == OpTypeEnum.UNSUPPORT else ""
            add_unsupport = ""
            print(cur_node.operation_desc)
            code_map[list(cur_node.write_set)[0]] = f"# task desc: node[{cur_node.node_id}]:" + add_unsupport  + "\n" + cur_node.task_code + "\n"
            for fixing_node in cur_node.fixing_node:
                target_col = list(fixing_node.write_set)[0]
                if target_col in code_map:
                    del code_map[target_col]
                code_map[target_col] = f"# task desc: node[{fixing_node.node_id}] fixing:" + fixing_node.operation_desc + "\n" + fixing_node.task_code + "\n"
            cur_node = list(self.dag.predecessors(cur_node))[0]
        
        code = ""
        for key, value in code_map.items():
            code = value + code
        return code
    
    def generate_feature(self, input_df, idx=0):
        # generate relevant N(pipe num) output_df contain the feature 
        import traceback
        for node in self.output_nodes[idx:]:
            try:
                exec_env = get_script_scope("")
                exec_env['df'] = input_df.copy(deep=True)
                # first we exec the fixing node
                exec(node.whole_code, exec_env)
                return exec_env['df']
            except Exception as e:
                print(termcolor.colored(f"Error:exec the code {e}", "red"))
                print(node.whole_code)
                traceback.print_exc()
        return input_df