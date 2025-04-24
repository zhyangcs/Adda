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
import asyncio
from src.llm.agents.autogen_code_generator import generate_code_autogen
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.linear_model import RidgeCV
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
from sklearn.preprocessing import LabelEncoder, KBinsDiscretizer
from autogen_agentchat.agents import AssistantAgent # Ensure AssistantAgent is imported
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken


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

        
# RAG计算相似度的嵌入向量模型设置        
config = AutoConfig.from_pretrained(rag_model_id_or_path, trust_remote_code=True)
config.use_sdpa = True
config.use_flash_attn = False
emb_model = AutoModel.from_pretrained(rag_model_id_or_path, trust_remote_code=True, config=config, device_map="cuda:0")
emb_model.eval()
emb_tokenizer = AutoTokenizer.from_pretrained(rag_model_id_or_path, trust_remote_code=True)   
 
# --- Define Planner Agent Logic ---
async def run_planner_agent(
    initial_data_desc: str,
    initial_col_info: dict, # Pass column info dictionary
    initial_stats_summary: str,
    target_col: str,
    client: OpenAIChatCompletionClient # Reuse one of the existing clients
    ) -> str:
    """Runs a Planner agent to generate a high-level feature engineering plan."""
    print(termcolor.colored("[Planner Agent] Generating global plan...", "blue"))
    if not client:
        print(termcolor.colored("[Planner Agent] Error: LLM client not available.", "red"))
        return ""

    # Prepare a concise context for the planner
    col_desc_for_planner = get_column_info(initial_col_info, 1000) # Limit token usage for column descriptions
    planner_context = f"""
/* Initial Data Description:
{col_desc_for_planner}
*/

Target Column: {target_col}

/* Initial Statistical Insights Summary:
{initial_stats_summary}
*/
"""

    planner_system_prompt = f"""You are a **Strategic Feature Engineering Planner**.
Based on the initial data description, target column ('{target_col}'), and statistical insights summary provided below, generate a concise, high-level strategic plan (3-5 bullet points) for the feature engineering process.

Focus on:
- Key areas to investigate (e.g., handling high correlation, exploring non-linearities suggested by MI).
- Potentially promising feature types (e.g., interactions involving important features, transformations for skewed data).
- Prioritization (e.g., "First address missing values, then explore interactions.").

Your output should be ONLY the bulleted list representing the plan. No extra text.

**Input Context:**
{planner_context}

**Output Example:**
*   Address high correlation between 'feat_A' and 'feat_B' by creating ratio/difference features.
*   Explore non-linear transformations (e.g., log, sqrt) for features 'feat_C', 'feat_D' based on high MI scores.
*   Prioritize interaction features involving top important features identified by LGBM ('feat_X', 'feat_Y').
*   Investigate features discriminating between the clusters identified by K-Means, focusing on 'feat_Z'.
"""

    planner_agent = AssistantAgent(
        name="PlannerAgent",
        model_client=client,
        system_message=planner_system_prompt,
        # No tools needed for the planner itself
    )

    try:
        # Use on_messages for a single turn interaction
        response = await planner_agent.on_messages(
             [TextMessage(content="Generate the feature engineering plan based on the provided context.", source="user")],
             CancellationToken(),
        )
        plan = response.chat_message.content.strip()
        print(termcolor.colored(f"[Planner Agent] Generated Plan:\n{plan}", "green"))
        # Basic cleanup: remove potential markdown list markers if LLM adds them inconsistently
        plan = re.sub(r'^[\*\-\+] ', '', plan, flags=re.MULTILINE).strip()
        return plan
    except Exception as e:
        print(termcolor.colored(f"[Planner Agent] Error generating plan: {e}", "red"))
        return "" # Return empty plan on error

class LLMDagConstructor():
    """LLM驱动的特征工程DAG构造器
    
    核心功能：
    - 管理特征生成的有向无环图(DAG)
    - 执行A*搜索算法生成特征
    - 评估特征节点性能
    - 与NLAgent/CodeAgent交互生成自然语言描述和代码
    """
    
    def __init__(self, task_type:str, eval_model_type:str, beam_limit:int = 6, async_mode:bool = False, do_feature_selection:bool = False, boost_training:bool = False, high_order_num:int = 2, token_limit:int = 800):
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
        """
        self.node_id = global_node_id
        self.column_info = {}
        self.boost_training = boost_training
        self.async_mode = async_mode
        self.beam_limit = beam_limit
        self.task_type = task_type
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
        self.global_plan = "" # Initialize global plan attribute
        # Initialize LLM Clients here (as implemented previously)
        self.client_coder = None
        self.client_validator = None
        try:
            # Consider reusing clients if appropriate for your application structure
            # It's generally more efficient than creating new ones for every operation.
            # Ensure API_KEY, BASE_URL, and MODEL constants/variables are defined appropriately.
            # Example uses constants defined earlier in the file or imported.
            # We should use src.env imported earlier
            self.client_coder = OpenAIChatCompletionClient(model='gpt-4o', base_url=src.env.openai_base_url, api_key=src.env.openai_api_key)
            # self.client_validator = OpenAIChatCompletionClient(model='gpt-4o', base_url=src.env.BASE_URL, api_key=src.env.API_KEY)
            print(termcolor.colored("LLMDagConstructor: LLM clients initialized successfully.", "green"))
        except Exception as e:
            print(termcolor.colored(f"LLMDagConstructor: Error initializing LLM clients: {e}. Global plan and code generation might fail.", "red"))
            # Depending on requirements, you might want to raise the exception or handle it differently.
            self.client_coder = None
            self.client_validator = None
        
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
        # 数据预处理逻辑
        if not do_unfinished:
            self.target_col = target_col
            self.task_desc = "".join(data_desc)
            
            pattern = r"(.*?):(.*?)"
            for line in data_agenda:
                match = re.search(pattern, line)
                if match:
                    self.column_info[match.group(1)] = line
                    if match.group(1) == self.target_col:
                        self.column_info[match.group(1)] = self.column_info[match.group(1)][:-1] + " (target column)\n"
                else:
                    print("match failed", line)
                    assert 0 == 1
            self.tb_name = tb_name        
            if tb_name != None:
                # get the row number of the task
                row_num = int(pd.read_sql(f"SELECT COUNT(*) FROM {tb_name}", get_conn())['count'][0])
                df = pd.read_sql(f"SELECT * FROM {tb_name} LIMIT {min(4000, row_num//4)}", get_conn())
                print(f"Current sampling {df.shape}")
            elif csv_path != None:
                df = pd.read_csv(csv_path)
            self.init_root_node(df)  
            self.level_states = [[self.root]]
            self.dag = nx.DiGraph()
            self.dag.add_node(self.root)
            # for print the draw for debug
            if task_name != None:
                self.task_name = task_name
            self.draw_current(self.root.node_id)
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
        if isinstance(op_list, str):
            op_list = [op_list]
        elif not isinstance(op_list, list):
             # Handle other potential types or raise an error
             print(termcolor.colored(f"Warning: Unexpected type for operation_desc: {type(op_list)}. Converting to string list.", "yellow"))
             op_list = [str(op_list)] # Default to string conversion

        if not op_list: # Handle empty list case
            print(termcolor.colored(f"Warning: Node {node.node_id} has empty operation_desc. Skipping embedding generation.", "yellow"))
            return node

        try:
            input_batch = emb_tokenizer(op_list, padding=True, max_length=512, truncation=True, return_tensors="pt").to(emb_model.device)
            with torch.no_grad():
                outputs = emb_model(**input_batch)
                embedding = last_token_pool(outputs.last_hidden_state, input_batch['attention_mask'])
                embedding = torch.nn.functional.normalize(embedding, p=2, dim=-1)
                if node.attr_embs is None:
                    node.attr_embs = embedding
                else:
                    # Ensure consistent device placement for concatenation
                    node.attr_embs = node.attr_embs.to(embedding.device)
                    node.attr_embs = torch.cat([node.attr_embs, embedding], dim=0)
        except Exception as e:
            print(termcolor.colored(f"Error during embedding generation for node {node.node_id}: {e}", "red"))
            # Decide how to handle embedding errors (e.g., continue without embedding?)

        return node

    async def _run_autogen_code_gen_and_process(self, next_node: LLMDAGNODE, cur_step_idx: int):
        """Helper function to run Autogen code generation and subsequent processing."""
        try:
            # 2a. Autogen generates and validates the code
            generated_code, autogen_success = await generate_code_autogen(next_node)
            
            if not autogen_success or generated_code is None:
                print(termcolor.colored(f"Autogen failed to generate/validate code for node {next_node.node_id}", "red"))
                return None, False

            # Assign the validated code
            next_node.task_code = generated_code
            could_exec_code = True # Autogen success implies code is likely executable
            
            # 2b. Check complexity and divide if necessary (using the validated code)
            # Initialize divide_agent here as it was moved from task_to_features
            divide_agent = DivideAgent(self.token_limit) 
            if cur_step_idx < self.high_order_num and whether_code_complex(next_node.task_code, next_node.column_info):
                 print(termcolor.colored(f"Code for node {next_node.node_id} is complex, attempting division.", "yellow"))
                 next_node, could_exec_code = divide_agent.divide_code(next_node)
                 if not could_exec_code:
                      print(termcolor.colored(f"Division failed for node {next_node.node_id}", "red"))
                      return None, False # Division failed

            # 2c. Generate Embeddings (using the potentially divided node)
            # The NL description might be less accurate if divided, but task_code is the primary source now
            next_node = self.generate_emb(next_node)
            
            # No fixing step needed as Autogen includes validation
            return next_node, True

        except Exception as e:
            print(termcolor.colored(f"Error during Autogen processing for node {next_node.node_id}: {e}", "red"))
            import traceback
            traceback.print_exc() # Print full traceback for debugging
            return None, False


    def task_to_features(self, cur_node:LLMDAGNODE, cur_step_idx:int = 0, stats_summary:str="", global_plan:str=""): # Add global_plan
        """将任务描述转换为特征节点（核心生成逻辑）"""
        # 1. NLAgent generate the description nodes
        nodes = topKSimilarNodes(cur_node, self.dag, src.env.topK_rag)
        example_prompt = nodes2example(nodes, self.dag)
        # next_state contains LLMDAGNODE instances with NL descriptions, etc.
        # Pass stats_summary to nl_agent
        next_state = self.nl_agent.task_to_desc(
            cur_node,
            # src.env.diverse_num,
            3,
            self.target_col,
            cur_step_idx,
            self.high_order_num,
            self.token_limit,
            example_prompt,
            stats_summary=stats_summary,
            global_plan=global_plan # Pass it along
            )

        # 2. Generate, validate, and process code using Autogen for each description node
        next_states_with_code = []
        
        # Use ThreadPoolExecutor to run the async helper function for each node
        # Note: asyncio.run() creates a new event loop per call inside the thread.
        # Consider a fully async approach if performance becomes an issue.
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Pass self to map function if helper needs access to self.generate_emb etc.
            # Use lambda to wrap the asyncio.run call
            future_to_node = {executor.submit(asyncio.run, self._run_autogen_code_gen_and_process(node, cur_step_idx)): node for node in next_state}
            
            results = []
            for future in concurrent.futures.as_completed(future_to_node):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    original_node = future_to_node[future]
                    print(termcolor.colored(f'Node {original_node.node_id} generated an exception: {exc}', "red"))
                    results.append((None, False)) # Append failure tuple

        # Process results from the executor
        for next_node, success in results:
            if success and next_node is not None:
                # Ensure write_set is not empty before accessing
                if next_node.write_set:
                    output_col_name = list(next_node.write_set)[0]
                    self.dag.add_node(next_node)
                    self.dag.add_edge(cur_node, next_node)
                    self.attrname2node[output_col_name] = next_node
                    self.draw_current(next_node.node_id)
                    next_states_with_code.append(next_node)
                    print(termcolor.colored(f"Successfully processed node {next_node.node_id} with code.", "green"))
                else:
                     print(termcolor.colored(f"Drop node (ID unknown, post-processing) due to empty write_set after processing.", "red"))
            else:
                # Node ID might not be available if next_node is None
                print(termcolor.colored(f"Drop node during code generation/processing phase.", "red"))
        
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
                # Ensure node has the required attributes, provide defaults if necessary
                node_id = getattr(node, 'node_id', -1) # Default ID if missing
                task_code = getattr(node, 'task_code', "N/A") # Default code
                score = getattr(node, 'final_score', float('nan')) # Default score
                exec_time = getattr(node, 'exec_time', float('nan')) # Default time

                new_node = DRAWNODE(
                    node_id=node_id,
                    task_code=task_code,
                    score=score,
                    exec_time=exec_time
                )
                nodes_map[node] = new_node
                draw_nodes.add_node(new_node)
            
            # 边关系重建
            for edge in self.dag.edges:
                 # Ensure edge source and target are in nodes_map
                 if edge[0] in nodes_map and edge[1] in nodes_map:
                    draw_nodes.add_edge(nodes_map[edge[0]], nodes_map[edge[1]])
                 else:
                      print(termcolor.colored(f"Warning: Skipping edge {edge} in draw_current due to missing node mapping.", "yellow"))

                
            # 图形渲染配置
            try:
                agraph = to_agraph(draw_nodes)  # 转换为Graphviz对象
                agraph.graph_attr['rankdir'] = 'LR'  # 从左到右布局
                agraph.layout(prog='dot')  # 使用层次布局算法

                # 持久化存储
                dir_path = os.path.join(test_save_path, self.task_name, "graph")
                os.makedirs(dir_path, exist_ok=True)  # 自动创建目录
                agraph.draw(os.path.join(dir_path, f"current_graph_{idx}.png"))  # 保存为PNG
            except Exception as e:
                print(termcolor.colored(f"Error during graph drawing: {e}", "red"))
                # Optionally log the error and continue, or re-raise
            
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
    
    def astar_one_step(self, cur_feature_idx:int):
        '''
        For cur_states, we generate the next states using the self-defined function
        '''
        # 1. generate the next states from original states
        next_states = []

        if not self.cur_states: # Check if heap is empty
            print(termcolor.colored("A* Search Warning: cur_states heap is empty. Stopping search.", "yellow"))
            return # Cannot proceed

        cur_node = heapq.heappop(self.cur_states)
        print(termcolor.colored(f"the current node: {cur_node.node_id}", "blue"))

        # --- Generate Statistical Summary for the current node's data ---
        stats_summary_str = ""
        if isinstance(cur_node.out_cur_df, pd.DataFrame) and not cur_node.out_cur_df.empty:
            try:
                stats_summary_str = self._generate_statistical_summary(
                    cur_node.out_cur_df,
                    target_col_name=self.target_col, # Pass the name
                    target_col_data=self.label      # Pass the actual label data
                )
            except Exception as e:
                print(termcolor.colored(f"Failed to generate stats summary for node {cur_node.node_id}: {e}", "yellow"))
        else:
            print(termcolor.colored(f"Skipping stats summary for node {cur_node.node_id}: DataFrame invalid.", "yellow"))

        print(termcolor.colored(f"Generated stats summary for node {cur_node.node_id}:\n{stats_summary_str}", "magenta"))
        # --- End Statistical Summary ---

        # task_to_features now handles code generation internally using Autogen
        # It populates next_node.task_code but not next_node.out_cur_df
        # Pass the summary to task_to_features
        cur_next_states = self.task_to_features(cur_node, cur_feature_idx, stats_summary=stats_summary_str, global_plan=self.global_plan)

        # 2. Execute code, evaluate, and choose the top-k states
        total_node_num = 0
        # Recalculate total nodes *before* potentially adding new ones in the loop
        for node in self.dag.nodes:
            total_node_num += (1 + self.dag.out_degree(node))

        valid_next_nodes_for_heap = [] # Nodes that successfully execute and evaluate
        for next_node in cur_next_states:
            if next_node is not None and hasattr(next_node, 'node_id') and hasattr(next_node, 'task_code') and next_node.task_code:
                execution_success = False
                # Check if parent DataFrame is valid
                if isinstance(cur_node.out_cur_df, pd.DataFrame) and not cur_node.out_cur_df.empty:
                    exec_env = {
                        'df': cur_node.out_cur_df.copy(), # Use a copy of parent's output df
                        'np': np,
                        'pd': pd
                    }
                    try:
                        print(termcolor.colored(f"Executing code for node {next_node.node_id}...", "cyan"))
                        start_time = time.time()
                        # Execute the generated code
                        exec(next_node.task_code, exec_env)
                        end_time = time.time()
                        next_node.exec_time = end_time - start_time

                        # Check execution result and update out_cur_df
                        if 'df' in exec_env and isinstance(exec_env['df'], pd.DataFrame):
                            next_node.out_cur_df = exec_env['df']
                            print(termcolor.colored(f"Code execution successful for node {next_node.node_id}. Time: {next_node.exec_time:.2f}s", "green"))
                            execution_success = True
                        else:
                            print(termcolor.colored(f"Warning: 'df' not found or not a DataFrame after executing code for node {next_node.node_id}.", "yellow"))
                            next_node.out_cur_df = None # Mark as invalid

                    except Exception as e:
                        print(termcolor.colored(f"Error executing code for node {next_node.node_id}: {e}", "red"))
                        # print(termcolor.colored(f"Failing Code:\\n{next_node.task_code}", "red")) # Optional: print failing code
                        next_node.exec_time = float('nan')
                        next_node.out_cur_df = None # Mark as invalid
                        # Let evaluate_node handle the failure based on out_cur_df being None
                else:
                    print(termcolor.colored(f"Skipping code execution for node {next_node.node_id}: Parent node {cur_node.node_id} DataFrame is invalid.", "yellow"))
                    next_node.out_cur_df = None # Mark as invalid

                # Evaluate the node *after* attempting code execution
                # evaluate_node should handle cases where out_cur_df is None/invalid and return score -1
                self.evaluate_node(next_node)

                # Proceed with utility calculation and heap push only if execution AND evaluation were successful
                if execution_success and next_node.final_score is not None and next_node.final_score != -1:
                    # Calculate utility and add to list for later heap push
                    out_degree = 0
                    # Node was added in task_to_features, should be in DAG
                    if self.dag.has_node(next_node):
                         out_degree = self.dag.out_degree(next_node)
                    else:
                         # This case should ideally not happen if task_to_features added the node
                         print(termcolor.colored(f"Warning: Node {next_node.node_id} not found in DAG when calculating utility.", "yellow"))

                    next_node.utility = monte_carlo_like_heuristic_func(out_degree + 1, total_node_num, next_node.final_score)
                    valid_next_nodes_for_heap.append(next_node) # Add to list for pushing onto heap later
                elif execution_success: # Execution ok, but evaluation failed
                    print(termcolor.colored(f"Skipping node {next_node.node_id} in A* heap push due to failed evaluation ({next_node.final_score}).", "yellow"))
                else: # Execution failed
                     print(termcolor.colored(f"Skipping node {next_node.node_id} in A* heap push due to failed code execution.", "yellow"))
            else:
                 # Handle cases where next_node is None or missing attributes earlier
                 print(termcolor.colored(f"Skipping invalid node from task_to_features output.", "yellow"))


        # Push valid nodes (those that executed AND evaluated successfully) onto the heap
        for node_to_push in valid_next_nodes_for_heap:
             heapq.heappush(self.cur_states, node_to_push)

        # Re-calculate and potentially re-push cur_node if it's still relevant/valid
        # Ensure cur_node score is valid before calculating utility
        if cur_node.final_score is not None and cur_node.final_score != -1:
            out_degree = 0
            if self.dag.has_node(cur_node):
                 out_degree = self.dag.out_degree(cur_node)
            # Recalculate total_node_num as it might have changed if nodes were added
            current_total_node_num = sum(1 + self.dag.out_degree(n) for n in self.dag.nodes)
            cur_node.utility = monte_carlo_like_heuristic_func(out_degree + 1, current_total_node_num, cur_node.final_score)
            # Optional: Consider if cur_node should always be pushed back or only under certain conditions
            # heapq.heappush(self.cur_states, cur_node) # Re-add parent node only if needed by algorithm variant
        else:
            print(termcolor.colored(f"Warning: cur_node {cur_node.node_id} has invalid score ({cur_node.final_score}) after expansion. Not re-adding to heap.", "yellow"))

        # Limit the size of the heap (beam search aspect)
        while len(self.cur_states) > self.beam_limit:
            heapq.heappop(self.cur_states) # Remove lowest utility node

        self.pre_states = self.cur_states.copy()
        self.node_id = src.llm.llm_dag_node.global_node_id
        
    def astar_k_step(self, step_num:int, data_agenda:list[str] = None, data_desc:list[str] = None, target_col:str = None, tb_name:str=None, csv_path:str=None, do_unfinished:bool = False, task_name:str = None):
        """A*算法多步执行入口函数
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
        
        # Ensure root node was initialized correctly
        if not hasattr(self, 'root') or self.root is None:
            print(termcolor.colored("Error: Root node not initialized. Cannot start A* search.", "red"))
            return # Or raise an exception
            
        # 新建任务时初始化优先队列
        if not do_unfinished:
            self.cur_states = []
            # Evaluate root node before adding to heap
            self.evaluate_node(self.root)
            if self.root.final_score is not None and self.root.final_score != -1:
                self.root.utility = monte_carlo_like_heuristic_func(1, 1, self.root.final_score) # Initial utility
                heapq.heappush(self.cur_states, self.root)  # 使用最小堆实现优先队列
            else:
                 print(termcolor.colored(f"Warning: Root node evaluation failed (score: {self.root.final_score}). Cannot start A* search.", "yellow"))
                 return # Cannot start with invalid root
            self.pre_states = self.cur_states.copy()  # 保存前序状态用于恢复
        
        # 设置当前搜索状态（异步模式暂不支持）
        self.cur_states = self.pre_states
        # 获取断点续做起始索引
        start_idx = self.pre_idx
        if start_idx != 0:
            print(f"current states is reload: {self.finish}, {start_idx}")
            self.draw_current(-20)  # 绘制当前DAG状态（调试用）
            
        # --- Run Planner Agent ONCE if starting fresh ---
        if not do_unfinished:
            print(termcolor.colored("Generating initial global plan...", "blue"))
            initial_stats_summary = ""
            if isinstance(self.root.out_cur_df, pd.DataFrame) and not self.root.out_cur_df.empty:
                 try:
                      initial_stats_summary = self._generate_statistical_summary(
                           self.root.out_cur_df,
                           target_col_name=self.target_col,
                           target_col_data=self.label
                      )
                      print(termcolor.colored(f"Generated initial stats summary for planner: {initial_stats_summary}", "magenta"))
                 except Exception as e:
                      print(termcolor.colored(f"Failed to generate initial stats summary for planner: {e}", "yellow"))
            else:
                 print(termcolor.colored("Skipping initial stats summary for planner: Root DataFrame invalid.", "yellow"))

            # Run the planner agent (make sure client_coder is initialized)
            if self.client_coder:
                 self.global_plan = asyncio.run(run_planner_agent(
                      initial_data_desc="".join(data_desc), # Pass data description string
                      initial_col_info=self.root.column_info, # Pass column info dict
                      initial_stats_summary=initial_stats_summary,
                      target_col=self.target_col,
                      client=self.client_coder # Reuse coder client
                 ))
            else:
                 print(termcolor.colored("Skipping global plan generation: LLM client not initialized.", "red"))
        elif not hasattr(self, 'global_plan'): # Handle loading state where plan might be missing
             print(termcolor.colored("Warning: Loading unfinished state, but global_plan attribute missing. Proceeding without plan.", "yellow"))
             self.global_plan = ""
        else:
             print(termcolor.colored(f"Loaded global plan:\n{self.global_plan}", "cyan"))
        # --- End Planner Agent Run ---
        
        # test
        # exit()

        # --- Initialize A* Heap (if starting fresh) ---
        if not do_unfinished:
            # ... (Initialize self.cur_states and self.pre_states as before) ...
             self.cur_states = []
             self.evaluate_node(self.root)
             if self.root.final_score is not None and self.root.final_score != -1:
                 self.root.utility = monte_carlo_like_heuristic_func(1, 1, self.root.final_score)
                 heapq.heappush(self.cur_states, self.root)
             else:
                  print(termcolor.colored(f"Warning: Root node evaluation failed... Cannot start A* search.", "yellow"))
                  asyncio.run(self.close_clients()) # Close clients if search cannot start
                  return
             self.pre_states = self.cur_states.copy()
        # ---

        # 主循环：执行指定步数的节点扩展
        for i in range(start_idx, step_num, 1):
             if not self.cur_states: # 检查堆是否为空
                 print(termcolor.colored(f"A* Search stopped at step {i} because the candidate heap is empty.", "yellow"))
                 break # 停止循环
             print(f"--- A* Step {i} ---")
             self.astar_one_step(i)          # 单步A*搜索
             self.draw_current(-1*i)         # 可视化当前状态
             self.pre_idx = i + 1            # 更新进度标识
            
             # 持久化当前状态（防止意外中断）
             # Ensure proj_path is defined correctly in the environment
             try:
                 save_path = os.path.join(proj_path, "src", "cur_states.pkl")
                 with open(save_path, "wb") as f:
                     pickle.dump(self, f)
             except NameError:
                  print(termcolor.colored("Warning: proj_path not defined. Cannot save state.", "yellow"))
             except Exception as e:
                  print(termcolor.colored(f"Error saving state: {e}", "red"))
                
                
        # 后处理：生成最终特征代码
        self.compute_best_code()
        self.finish = True  # 标记任务完成
        print("--- A* Search Finished --- ")
        
    def async_task_to_features(self, cur_node:LLMDAGNODE, cur_feature_idx:int, next_states):
        # This async method seems designed for a different concurrency model (likely using threading.Thread)
        # It conflicts with the ThreadPoolExecutor + asyncio.run approach in the modified task_to_features.
        # If async_mode=True is used, this needs to be reconciled or the ThreadPoolExecutor approach adapted.
        # For now, assuming async_mode=False or the ThreadPoolExecutor approach is the primary path.
        print(termcolor.colored("Warning: async_task_to_features called, but current implementation uses ThreadPoolExecutor.", "yellow"))
        # Original logic preserved for reference:
        # cur_next_states = self.task_to_features(cur_node, cur_feature_idx)
        # self.finishedLock.acquire()
        # next_states += cur_next_states
        # self.finishedLock.release()
        pass # Placeholder, needs rework if async_mode=True is critical path
    
    def init_root_node(self, df):
        '''
        get score in the root node
        '''
        # df = pd.read_csv(rootpath + self.dir_name + "/train_new.csv")
        
        if self.target_col in df.columns:
            # change the column of 
            try:
                self.label, _ = prepare_df_for_train(pd.DataFrame(df[self.target_col]))
                df_processed = df.drop(columns = [self.target_col])
            except Exception as e:
                 print(termcolor.colored(f"Error during initial label processing: {e}", "red"))
                 # Handle error appropriately, maybe raise or return?
                 raise ValueError(f"Failed to process target column '{self.target_col}'") from e
        else:
            print(df.columns)
            print(termcolor.colored(f"Error: the target column '{self.target_col}' is not in the dataframe", "red"))
            raise ValueError(f"Target column '{self.target_col}' not found in input DataFrame.")
        
        # Ensure df_processed exists before passing to get_scores
        final_score, init_scores, attr_imp_list = self.get_scores(df_processed)
        op_list = list(self.column_info.values())
        print("type of op_list", type(op_list))
        
        # Handle potential evaluation failure
        if final_score == -1:
            print(termcolor.colored("Error: Root node evaluation failed. Cannot initialize root node.", "red"))
            # Decide how to handle this (e.g., raise exception, set root to None)
            self.root = None # Indicate failure
            return
            
        # Removed async lock as it's not used in the current flow
        # if self.async_mode:
        #     self.aliveLock.acquire()
        self.root = LLMDAGNODE(allocate_node_id(), "", set(), set(), df_processed, df_processed, self.column_info, op_list , OpTypeEnum.UNSUPPORT, init_scores, final_score, "", [], [], None, True, True, 0, attr_imp_list, None)
        
        # init the embedding msg
        self.root = self.generate_emb(self.root)
        
        self.root.attr_imp_order = list(self.column_info.keys())
        # Removed async lock release
        # if self.async_mode:
        #     self.aliveLock.release()
        print(termcolor.colored(f"Root node initialized with score: {self.root.final_score}", "green"))
        
    def evaluate_node(self, node:LLMDAGNODE):
        '''
        evaluate the node by the score of the model
        '''
        if node is None or not hasattr(node, 'node_id') or not hasattr(node, 'out_cur_df'):
             print(termcolor.colored(f"Error: Attempting to evaluate an invalid node.", "red"))
             # Assign a default failure score if node object exists but is incomplete
             if node is not None:
                 node.final_score = -1
                 node.scores = None
                 node.attr_imp_order = None
             return -1 # Indicate failure
             
        # Check if out_cur_df is a valid DataFrame
        if not isinstance(node.out_cur_df, pd.DataFrame) or node.out_cur_df.empty:
            print(termcolor.colored(f"Error: Node {node.node_id} has invalid or empty out_cur_df. Cannot evaluate.", "red"))
            node.final_score = -1
            node.scores = None
            node.attr_imp_order = None
            return -1 # Indicate failure
            
        print(termcolor.colored(f"Evaluating node {node.node_id}...", "yellow"))
        # Ensure task_code is a string for printing
        task_code_str = str(getattr(node, 'task_code', 'N/A'))
        # print(termcolor.colored(f"the node{node.node_id} is evaluating : \n {task_code_str}, \n {node.out_cur_df.info()}", "yellow"))
        
        # Ensure self.label is valid before calling get_scores
        if not hasattr(self, 'label') or self.label is None:
            print(termcolor.colored(f"Error: Label data is missing. Cannot evaluate node {node.node_id}.", "red"))
            node.final_score = -1
            node.scores = None
            node.attr_imp_order = None
            return -1
            
        node.final_score, node.scores, node.attr_imp_order = self.get_scores(node.out_cur_df)
        
        if node.final_score == -1:
             print(termcolor.colored(f"Evaluation failed for node {node.node_id}.", "red"))
        else:
             print(termcolor.colored(f"Node {node.node_id} evaluated with score: {node.final_score}", "green"))
             
        return node.final_score

    def get_scores(self, df:pd.DataFrame):
        """
        get roc auc score in the raw model for lightgbm
        """
        # Add checks for df and self.label validity
        if not isinstance(df, pd.DataFrame) or df.empty:
            print(termcolor.colored("Error in get_scores: Input DataFrame is invalid or empty.", "red"))
            return -1, None, None
        if not hasattr(self, 'label') or self.label is None:
             print(termcolor.colored("Error in get_scores: Label data is missing.", "red"))
             return -1, None, None
             
        try:
            # Ensure label length matches df length after potential drops/preprocessing
            new_df, new_label = prepare_df_for_train(df, self.label)
            
            # Check alignment after prepare_df_for_train
            if len(new_df) != len(new_label):
                 print(termcolor.colored(f"Error in get_scores: Mismatch between processed data ({len(new_df)}) and label ({len(new_label)}) lengths.", "red"))
                 # Attempt to align by index if possible, otherwise fail
                 common_index = new_df.index.intersection(new_label.index)
                 if len(common_index) > 0:
                      print(termcolor.colored(f"Attempting to align data and labels on common index (size: {len(common_index)}).", "yellow"))
                      new_df = new_df.loc[common_index]
                      new_label = new_label.loc[common_index]
                      if new_df.empty:
                           print(termcolor.colored("Error: Data empty after index alignment.", "red"))
                           return -1, None, None
                 else:
                      print(termcolor.colored("Error: Cannot align data and labels.", "red"))
                      return -1, None, None
                      
            # Check if new_df is empty after processing
            if new_df.empty:
                 print(termcolor.colored("Error in get_scores: DataFrame is empty after preprocessing.", "red"))
                 return -1, None, None

            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=1) if self.task_type == "classify" else KFold(n_splits=5, shuffle=True, random_state=1)
            # new_df = move_id_to_first(new_df, 'id') # Assuming 'id' might not always exist or be needed
            
            # Check for sufficient samples for CV splits
            min_samples_required = skf.get_n_splits()
            if len(new_df) < min_samples_required:
                 print(termcolor.colored(f"Warning in get_scores: Not enough samples ({len(new_df)}) for {min_samples_required}-fold CV. Returning score -1.", "yellow"))
                 return -1, None, None
                 
            # Handle potential errors during cross-validation itself
            scoring_metric = "roc_auc" if self.task_type == "classify" else make_scorer(one_minus_rae)
            result = cross_validate(self.eval_model, new_df, new_label, cv=skf, scoring=scoring_metric, return_estimator=True, error_score='raise') # Raise error to catch issues
            cv_result = result['test_score']
            
            print(termcolor.colored(f"the model name: {self.eval_model_type}, cv result {cv_result}, cv_mean {cv_result.mean()}", "yellow"))
        except ValueError as ve:
             # Catch specific errors like incompatible data types or shapes
             print(termcolor.colored(f"ValueError during cross-validation: {ve}", "red"))
             # Potentially inspect new_df.info() or new_df.dtypes here
             return -1, None, None
        except Exception as e:
            print(termcolor.colored(f"Error in get_scores during cross-validation: {e}", "red"))
            import traceback
            traceback.print_exc()
            return -1, None, None
        
        # Return mean score, handle potential NaN result from mean()
        mean_score = cv_result.mean()
        if pd.isna(mean_score):
            print(termcolor.colored("Warning: CV mean score is NaN.", "yellow"))
            return -1, None, None 
            
        return mean_score, None, None # do not consider the feature importance in this version
        
    def compute_best_code(self, file_path:str = None):
        """
        for each leave node, we fetch all features, and choose the most important features, then we decide topk features we choose
        """
        if file_path is not None:
            os.makedirs(file_path, exist_ok=True)
            
        # Ensure dag exists and has nodes
        if not hasattr(self, 'dag') or not self.dag.nodes:
             print(termcolor.colored("Error: DAG not initialized or empty. Cannot compute best code.", "red"))
             self.output_nodes = []
             self.pipes = []
             return
             
        if self.search_type == "BFS":
            # Assuming self.cur_states holds the final BFS layer nodes
            self.output_nodes = self.cur_states if hasattr(self, 'cur_states') else []
        elif self.search_type == "ASTAR":
            # get the topk nodes for score
            nodes = list(self.dag.nodes())
            # Filter out nodes with invalid scores before sorting
            valid_nodes = [n for n in nodes if hasattr(n, 'final_score') and n.final_score is not None and n.final_score != -1]
            if not valid_nodes:
                 print(termcolor.colored("Warning: No valid nodes found in DAG to determine best code.", "yellow"))
                 self.output_nodes = []
                 self.pipes = []
                 return
                 
            self.output_nodes = heapq.nlargest(1, valid_nodes, key = lambda x: x.final_score) # you could change the topk here [we current use 1]
        else:
            print(termcolor.colored(f"Warning: Unknown search type '{self.search_type}'. Cannot determine output nodes.", "yellow"))
            self.output_nodes = []
            
        self.pipes = [PIPE() for _ in range(len(self.output_nodes))]
        for idx in range(len(self.pipes)):
            self.pipes[idx].pipe_id = idx
            
        for idx, node in enumerate(self.output_nodes):
            print("--------------------------")
            print(f"Processing output node {node.node_id} with score {node.final_score}")
            # print(node.whole_code) # whole_code is generated below
            
            # Ensure root node and its df are valid for comparison score
            root_score = -1
            if hasattr(self, 'root') and self.root and hasattr(self.root, 'out_cur_df'):
                 root_score, _, _ = self.get_scores(self.root.out_cur_df)
            else:
                 print(termcolor.colored("Warning: Root node or its DataFrame is invalid for base score calculation.", "yellow"))
                 
            node_score, _, _ = self.get_scores(node.out_cur_df)
            print(termcolor.colored("the original final score: "+str(root_score), "red"))
            print(termcolor.colored("the whole feature score: "+str(node_score), "red"))
            
            # set the whole code    
            code_list = []
            try:
                 code_list.append(self.fetch_code_from_leaf(node))
                 
                 # Safely get non-numeric columns
                 if isinstance(node.out_cur_df, pd.DataFrame):
                     non_numeric_cols = node.out_cur_df.select_dtypes(exclude=np.number).columns.tolist()
                 else:
                     print(termcolor.colored(f"Warning: node {node.node_id} out_cur_df is not a DataFrame. Skipping non-numeric handling.", "yellow"))
                     non_numeric_cols = []
                     
                 # Add label encoding for non-numeric columns if needed
                 for col in non_numeric_cols:
                     if f"{col}_Label" not in node.out_cur_df.columns:
                         code_list.append("\n# task desc: convert the non-numeric columns to numeric columns\n")
                         code, _ = self.pair_to_code(node, ("Label encoding", col))
                         if code: # Ensure pair_to_code returned valid code
                             code_list.append(code)
                         else:
                              print(termcolor.colored(f"Warning: Failed to generate Label Encoding code for column '{col}'.", "yellow"))
                 
                 # Add drop columns step
                 if non_numeric_cols:
                     drop_cols = ",".join([f"'{x}'" for x in non_numeric_cols]) # Corrected map function
                     node.drop_attrs = non_numeric_cols
                     code_list.append("\n# task desc: drop the original non-numeric columns")
                     code_list.append(f"\ndf = df.drop(columns = [{drop_cols}], errors='ignore')") # Add errors='ignore'
                 else:
                     node.drop_attrs = []
                     
                 node.whole_code = "".join(code_list)
                 print(f"Generated whole_code for node {node.node_id}")
                 # print(node.whole_code) # Optional: print generated code
                 
            except Exception as e:
                 print(termcolor.colored(f"Error generating whole_code for node {node.node_id}: {e}", "red"))
                 node.whole_code = "# Error generating code" # Mark node as having errored code
                 import traceback
                 traceback.print_exc()
            
            
    def get_best_code(self):
        """
        store the best code to the given location `file_path`
        """
        # Ensure task_name is set
        if not hasattr(self, 'task_name') or not self.task_name:
            print(termcolor.colored("Error: task_name not set. Cannot save best code.", "red"))
            return []
            
        pycode_file = os.path.join(test_save_path, self.task_name, "pycodes")
        if not os.path.exists(pycode_file):
            try:
                os.makedirs(pycode_file)
            except OSError as e:
                 print(termcolor.colored(f"Error creating directory {pycode_file}: {e}", "red"))
                 return [] # Cannot proceed without directory
                 
        # Ensure output_nodes and pipes exist and have the same length
        if not hasattr(self, 'output_nodes') or not hasattr(self, 'pipes') or len(self.output_nodes) != len(self.pipes):
             print(termcolor.colored("Error: Mismatch between output_nodes and pipes or they don't exist.", "red"))
             return []
             
        output_node_ids = []
        for idx, node in enumerate(self.output_nodes):
             # Check if node and whole_code are valid
             if node is None or not hasattr(node, 'node_id') or not hasattr(node, 'whole_code') or not node.whole_code or "# Error generating code" in node.whole_code:
                  print(termcolor.colored(f"Skipping saving code for invalid or errored node at index {idx}.", "yellow"))
                  continue
                  
             code_path = os.path.join(pycode_file, f"pipeline_{node.node_id}.py")
             try:
                 with open(code_path, "w") as f:
                     # Add necessary imports at the beginning
                     f.write("import pandas as pd\n")
                     f.write("import numpy as np\n") # Add numpy
                     f.write("from sklearn.preprocessing import LabelEncoder, StandardScaler\n") # Add sklearn imports if used
                     # Add database connection details (ensure these vars are defined)
                     try:
                         f.write("import psycopg2\n")
                         f.write(f"conn = psycopg2.connect(dbname='{pg_db}', user='{pg_user}', port={pg_port})\n")
                         f.write(f'df = pd.read_sql("SELECT * FROM {self.tb_name} LIMIT 500", conn)\n\n') # Add newline
                     except NameError:
                         print(termcolor.colored("Warning: Database config (pg_db, pg_user, pg_port) not defined. Skipping DB load in saved code.", "yellow"))
                     except Exception as db_e:
                          print(termcolor.colored(f"Error writing DB connection details: {db_e}", "red"))
                          
                     # Write the generated feature code
                     f.write("# --- Feature Engineering Code ---\n")
                     f.write(node.whole_code)
                     f.write("\n# --- End of Code --- \n")
                 self.pipes[idx].code_path = code_path
                 output_node_ids.append(node.node_id)
                 print(termcolor.colored(f"Saved best code for node {node.node_id} to {code_path}", "green"))
             except IOError as e:
                  print(termcolor.colored(f"Error writing code file {code_path}: {e}", "red"))
             except Exception as e:
                  print(termcolor.colored(f"Unexpected error saving code for node {node.node_id}: {e}", "red"))
                
        return output_node_ids


    def retest_time(self, new_df):
        # from the root, we reexec the code and reeval the time with larger df
        if not hasattr(self, 'root') or self.root is None:
             print(termcolor.colored("Error: Root node not initialized. Cannot retest time.", "red"))
             return
             
        cur_node = self.root
        queue = list(self.dag.successors(cur_node)) # Start from root's successors
        # Initialize root's time if not already done
        if not hasattr(self.root, 'exec_time'):
             self.root.exec_time = 0.0 
        self.root.out_cur_df = new_df.copy() # Use a copy
        visited = {self.root} # Keep track of visited nodes

        while queue:
            cur_node = queue.pop(0)
            if cur_node in visited:
                 continue
            visited.add(cur_node)
            
            # Find predecessors (should ideally be only one in this structure)
            predecessors = list(self.dag.predecessors(cur_node))
            if not predecessors:
                 print(termcolor.colored(f"Warning: Node {cur_node.node_id} has no predecessors. Skipping retest.", "yellow"))
                 continue
            pred_node = predecessors[0] # Assume single predecessor
            
            # Ensure predecessor DataFrame is valid
            if not hasattr(pred_node, 'out_cur_df') or not isinstance(pred_node.out_cur_df, pd.DataFrame):
                 print(termcolor.colored(f"Warning: Predecessor {pred_node.node_id} for node {cur_node.node_id} has invalid DataFrame. Skipping retest.", "yellow"))
                 continue
                 
            cur_node.in_cur_df = pred_node.out_cur_df.copy() # Get input from predecessor
            
            exec_env = {'df': cur_node.in_cur_df} 
            total_exec_time = 0.0
            node_failed = False
            
            # Execute fixing nodes first, then the main node code
            nodes_to_exec = cur_node.fixing_node[:] + [cur_node]
            
            for node_step in nodes_to_exec:
                 # Ensure node_step and its task_code are valid
                 if node_step is None or not hasattr(node_step, 'task_code') or not isinstance(node_step.task_code, str):
                      print(termcolor.colored(f"Warning: Invalid node or task_code encountered during retest for node {cur_node.node_id}. Skipping step.", "yellow"))
                      node_failed = True
                      break # Stop processing this node group
                      
                 startt = time.time()
                 try:
                     # Use restricted exec environment if possible
                     exec(node_step.task_code, exec_env)
                     # Update df for the next step within this group
                     if 'df' in exec_env:
                          exec_env['df'] = exec_env['df'] 
                     else:
                          print(termcolor.colored(f"Warning: 'df' not found in exec_env after executing code for step node {node_step.node_id}.", "yellow"))
                          node_failed = True
                          break
                          
                 except Exception as e:
                     print(termcolor.colored(f"Error re-executing code for node {node_step.node_id}: {e}", "red"))
                     node_failed = True
                     # Optionally log traceback
                     break # Stop processing this node group
                 endt = time.time()
                 exec_time = endt - startt
                 node_step.exec_time = exec_time # Store time on the specific node/fixing_node
                 total_exec_time += exec_time
                 
            # If execution failed for any step, mark node and don't proceed
            if node_failed:
                 print(termcolor.colored(f"Execution failed for node {cur_node.node_id} group. Assigning NaN time.", "red"))
                 cur_node.exec_time = float('nan')
                 # Decide if we should still try to process successors or stop propagation
                 continue # Move to next node in queue
                 
            # Assign total time to the main node for simplicity in drawing?
            # Or keep individual times? Let's assign total for now.
            cur_node.exec_time = total_exec_time 
            # Update the node's output dataframe
            if 'df' in exec_env and isinstance(exec_env['df'], pd.DataFrame):
                 cur_node.out_cur_df = exec_env['df']
            else:
                 print(termcolor.colored(f"Warning: Final 'df' is not a DataFrame for node {cur_node.node_id}. Output df not updated.", "yellow"))
                 cur_node.out_cur_df = None # Mark as invalid
                 continue # Don't add successors if output is invalid
                 
            # Add successors to the queue
            for successor in self.dag.successors(cur_node):
                 if successor not in visited:
                     queue.append(successor)
        
        print(termcolor.colored("Retest time finished.", "green"))
        self.draw_current(-1) # Draw the updated graph with new times
        
    def correct_node(self, node_id, code):
        for node in self.dag.nodes:
            nodes_to_check = [node] + getattr(node, 'fixing_node', []) # Handle missing fixing_node
            for in_node in nodes_to_check:
                if hasattr(in_node, 'node_id') and in_node.node_id == node_id:
                    in_node.task_code = code
                    print(termcolor.colored(f"Corrected code for node {node_id}", "green"))
                    return True
        print(termcolor.colored(f"Node {node_id} not found for code correction.", "yellow"))
        return False
    
    def fetch_code_from_leaf(self, node:LLMDAGNODE):
        """
        fetch the code from the leaf to the root
        """
        if node is None or not hasattr(node, 'node_id'):
             print(termcolor.colored("Error: Cannot fetch code from invalid leaf node.", "red"))
             return "# Error: Invalid node provided\n"
             
        cur_node = node
        code_map = OrderedDict()
        path_nodes = [] # Keep track of nodes in path to avoid cycles
        
        while cur_node is not None and cur_node != self.root and cur_node not in path_nodes:
            path_nodes.append(cur_node)
            
            # Ensure node attributes are valid
            node_id = getattr(cur_node, 'node_id', 'UNKNOWN')
            task_code = getattr(cur_node, 'task_code', '# Missing task code')
            op_desc = getattr(cur_node, 'operation_desc', ['# Missing operation description'])
            write_set = getattr(cur_node, 'write_set', set())
            fixing_nodes = getattr(cur_node, 'fixing_node', [])
            
            if not write_set:
                 print(termcolor.colored(f"Warning: Node {node_id} in path has empty write_set. Skipping code fetch for this node.", "yellow"))
                 # Get the predecessor and continue
                 predecessors = list(self.dag.predecessors(cur_node))
                 cur_node = predecessors[0] if predecessors else None
                 continue
                 
            output_col = list(write_set)[0] # Get primary output column
            add_unsupport = "" # Removed [UNSUPPORT] flag
            # Ensure task_code is a string
            if not isinstance(task_code, str):
                 task_code = "# Invalid task code (not a string)"
                 
            # Add main node code
            code_map[output_col] = f"# task desc: node[{node_id}]: {op_desc[0] if op_desc else ''}{add_unsupport}\n{task_code}\n"
            
            # Add fixing node code, overwriting if target col is the same
            for fixing_node in fixing_nodes:
                 fix_node_id = getattr(fixing_node, 'node_id', 'FIX_UNKNOWN')
                 fix_task_code = getattr(fixing_node, 'task_code', '# Missing fixing task code')
                 fix_op_desc = getattr(fixing_node, 'operation_desc', '# Missing fixing op desc')
                 fix_write_set = getattr(fixing_node, 'write_set', set())
                 
                 if not fix_write_set:
                      print(termcolor.colored(f"Warning: Fixing node {fix_node_id} for node {node_id} has empty write_set. Skipping.", "yellow"))
                      continue
                      
                 target_col = list(fix_write_set)[0]
                 # Ensure fix_task_code is a string
                 if not isinstance(fix_task_code, str):
                      fix_task_code = "# Invalid fixing task code (not a string)"
                      
                 code_map[target_col] = f"# task desc: node[{fix_node_id}] fixing: {fix_op_desc}\n{fix_task_code}\n"
                 
            # Move to the predecessor
            predecessors = list(self.dag.predecessors(cur_node))
            if not predecessors:
                 print(termcolor.colored(f"Warning: Node {node_id} has no predecessors but is not root. Stopping code fetch.", "yellow"))
                 break # Stop if no predecessor found
            cur_node = predecessors[0] # Assume a single predecessor for now
            
        # Check for cycles
        if cur_node in path_nodes:
             print(termcolor.colored(f"Error: Cycle detected in fetch_code_from_leaf involving node {cur_node.node_id}. Returning partial code.", "red"))
             # Return code accumulated so far
             code = ""
             for key, value in reversed(code_map.items()): # Reverse to get root-to-leaf order
                 code += value
             return code + "\n# Error: Cycle detected" 
             
        # Combine the collected code blocks in reverse order (root to leaf)
        code = ""
        for key, value in reversed(code_map.items()):
            code += value
        return code
    
    def generate_feature(self, input_df, idx=0):
        # generate relevant N(pipe num) output_df contain the feature 
        import traceback
        
        # Ensure output_nodes exists and idx is valid
        if not hasattr(self, 'output_nodes') or idx >= len(self.output_nodes):
            print(termcolor.colored(f"Error: Invalid index {idx} or output_nodes not set.", "red"))
            return input_df # Return original df if cannot generate
            
        output_node = self.output_nodes[idx]
        
        # Check if the selected node and its code are valid
        if output_node is None or not hasattr(output_node, 'whole_code') or not output_node.whole_code or "# Error generating code" in output_node.whole_code:
            print(termcolor.colored(f"Error: Cannot generate feature for node at index {idx} due to invalid node or code.", "red"))
            return input_df
            
        try:
            # Ensure input_df is a DataFrame
            if not isinstance(input_df, pd.DataFrame):
                 raise TypeError("Input must be a pandas DataFrame")
                 
            # Use a restricted execution scope
            exec_env = get_script_scope("") 
            # Pass a copy to avoid modifying the original DataFrame outside the function
            exec_env['df'] = input_df.copy(deep=True)
            
            # Execute the combined code for the pipeline
            exec(output_node.whole_code, exec_env)
            
            # Return the modified DataFrame from the execution scope
            if 'df' in exec_env and isinstance(exec_env['df'], pd.DataFrame):
                return exec_env['df']
            else:
                 print(termcolor.colored(f"Warning: 'df' not found or not a DataFrame in exec_env after executing whole_code for node {output_node.node_id}.", "yellow"))
                 return input_df # Return original on failure
                 
        except Exception as e:
            print(termcolor.colored(f"Error executing generated code for node {output_node.node_id}: {e}", "red"))
            print("--- Failing Code ---:")
            print(output_node.whole_code)
            print("--- Traceback ---:")
            traceback.print_exc()
            return input_df # Return original df on execution error

    def _generate_statistical_summary(
        self,
        df: pd.DataFrame,
        sample_size: int = 5000,
        target_col_name: str | None = None,
        target_col_data: pd.Series | np.ndarray | None = None
    ) -> str:
        """Generates an enhanced statistical summary string for the given DataFrame."""
        if not isinstance(df, pd.DataFrame) or df.empty:
            return "Input DataFrame is empty or invalid."
 
        summary_parts = ["--- Statistical Insights Summary ---"]
        # Ensure consistent sampling by using the DataFrame's index if target_col_data is provided
        sample_indices = df.index if len(df) <= sample_size else df.sample(n=sample_size, random_state=42).index
        df_sample = df.loc[sample_indices]

        # Align target_col_data with the sample if provided
        aligned_target_data = None
        if target_col_data is not None and target_col_name:
            try:
                # Ensure target_col_data is a pandas Series for easier indexing
                if isinstance(target_col_data, np.ndarray):
                    target_col_data = pd.Series(target_col_data, index=df.index) # Assume original df index alignment

                if isinstance(target_col_data, pd.Series):
                     # Check if index types match before attempting intersection
                     if df_sample.index.dtype == target_col_data.index.dtype:
                         common_index = df_sample.index.intersection(target_col_data.index)
                         aligned_target_data = target_col_data.loc[common_index]
                         # Align df_sample as well, in case target had NaNs dropped etc.
                         df_sample = df_sample.loc[common_index]
                         if aligned_target_data.empty or df_sample.empty:
                              print(termcolor.colored("Warning: Target data or features became empty after index alignment.", "yellow"))
                              aligned_target_data = None # Reset if alignment failed
                         else:
                             print(termcolor.colored(f"Successfully aligned target data (size: {len(aligned_target_data)}) with sampled features.", "grey"))
                     else:
                          print(termcolor.colored(f"Warning: Index type mismatch between features ({df_sample.index.dtype}) and target ({target_col_data.index.dtype}). Cannot align target data.", "yellow"))
                          aligned_target_data = None
                else:
                    print(termcolor.colored("Warning: target_col_data is not a Series or ndarray. Cannot align.", "yellow"))
                    aligned_target_data = None
            except Exception as e:
                 print(termcolor.colored(f"Error aligning target data: {e}. Proceeding without MI/LGBM.", "yellow"))
                 aligned_target_data = None

        df_sample = df.sample(n=min(len(df), sample_size), random_state=42) if len(df) > sample_size else df
        numeric_cols = df_sample.select_dtypes(include=np.number).columns.tolist()
        all_cols = df_sample.columns.tolist()
        categorical_cols = df_sample.select_dtypes(include=['object', 'category']).columns.tolist()
 
        df_numeric_sample = df_sample[numeric_cols].copy() if numeric_cols else pd.DataFrame()
 
        # --- Univariate Statistics ---
        summary_parts.append("\n[Univariate Statistics]")
        # Numeric Columns
        if numeric_cols:
             summary_parts.append("Numeric Columns (Top 5 by variance shown):")
             numeric_stats = df_numeric_sample.agg(['mean', 'median', 'std', 'min', 'max', 'skew']).transpose()
             numeric_stats['nan%'] = df_numeric_sample.isnull().mean() * 100
             # Show top 5 by standard deviation (as a proxy for variance)
             top_var_cols = numeric_stats['std'].nlargest(5).index.tolist()
             stats_to_show = numeric_stats.loc[top_var_cols] if len(top_var_cols) >= 5 else numeric_stats # Show all if less than 5
             for col, stats in stats_to_show.iterrows():
                  summary_parts.append(f"- '{col}': Mean={stats['mean']:.2f}, Median={stats['median']:.2f}, Std={stats['std']:.2f}, Skew={stats['skew']:.2f}, NaN={stats['nan%']:.1f}%")
        else:
             summary_parts.append("No numeric columns found.")

        # Categorical Columns
        if categorical_cols:
             summary_parts.append("\nCategorical Columns (Top 3 by unique values shown):")
             cat_stats = pd.DataFrame(index=categorical_cols)
             cat_stats['nunique'] = df_sample[categorical_cols].nunique()
             cat_stats['nan%'] = df_sample[categorical_cols].isnull().mean() * 100
             # Show top 3 by nunique
             top_nunique_cols = cat_stats['nunique'].nlargest(3).index.tolist()
             stats_to_show_cat = cat_stats.loc[top_nunique_cols] if len(top_nunique_cols) >=3 else cat_stats

             for col, stats in stats_to_show_cat.iterrows():
                  top_vals = df_sample[col].value_counts(normalize=True).head(3) # Top 3 value frequencies
                  top_vals_str = ", ".join([f"'{k}' ({v:.1%})" for k, v in top_vals.items()])
                  summary_parts.append(f"- '{col}': Unique={int(stats['nunique'])}, TopVals=[{top_vals_str}], NaN={stats['nan%']:.1f}%")
        else:
            summary_parts.append("No categorical columns found.")


        # --- Correlation Summary ---
        if not df_numeric_sample.empty:
            try:
                # ... (Correlation logic remains the same as before) ...
                corr_matrix = df_numeric_sample.corr()
                high_corr_threshold = 0.8
                low_corr_threshold = -0.8 # For negative corr
                high_corr_pairs = []
                neg_corr_pairs = []
                processed_in_pair = set()
                for i in range(len(corr_matrix.columns)):
                    for j in range(i):
                        col1, col2 = corr_matrix.columns[i], corr_matrix.columns[j]
                        # Check if correlation calculation resulted in NaN (can happen with low variance cols)
                        corr_val = corr_matrix.iloc[i, j]
                        if pd.isna(corr_val):
                            continue
                        if abs(corr_val) > high_corr_threshold:
                            if col1 not in processed_in_pair and col2 not in processed_in_pair:
                                pair = (col1, col2, corr_val)
                                if corr_val > high_corr_threshold:
                                    high_corr_pairs.append(pair)
                                    processed_in_pair.add(col1)
                                    processed_in_pair.add(col2)
                                elif corr_val < low_corr_threshold:
                                    neg_corr_pairs.append(pair)
                                    processed_in_pair.add(col1)
                                    processed_in_pair.add(col2)


                if high_corr_pairs:
                    # Sort by absolute correlation descending for display
                    high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                    summary_parts.append("\n[Correlation Insights]")
                    summary_parts.append(f"High Positive Correlation ( > {high_corr_threshold:.1f}):")
                    for p in high_corr_pairs[:5]: # Limit displayed pairs
                         summary_parts.append(f"- '{p[0]}' & '{p[1]}': {p[2]:.2f}")
                else:
                     summary_parts.append(f"\n[Correlation Insights]\nNo strong positive correlations ( > {high_corr_threshold:.1f}) found.")

                if neg_corr_pairs:
                    neg_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                    summary_parts.append(f"High Negative Correlation ( < {low_corr_threshold:.1f}):")
                    for p in neg_corr_pairs[:3]: # Limit displayed pairs
                         summary_parts.append(f"- '{p[0]}' & '{p[1]}': {p[2]:.2f}")
                # else: No need to explicitly state no negative corr if positive exists

            except Exception as e:
                summary_parts.append(f"\n[Correlation Insights]\nAnalysis failed: {e}")
        else:
             summary_parts.append("\n[Correlation Insights]\nNo numeric columns for analysis.")

        # --- PCA Insights (Enhanced) ---
        if not df_numeric_sample.empty:
            try:
                df_pca_input = df_numeric_sample.fillna(df_numeric_sample.median())
                if df_pca_input.empty or df_pca_input.shape[1] < 2:
                     summary_parts.append("\n[PCA Insights]\nSkipped: Not enough numeric features or data.")
                else:
                     scaler_pca = StandardScaler()
                     scaled_data_pca = scaler_pca.fit_transform(df_pca_input)
                     n_components_pca = min(5, df_pca_input.shape[1]) # Show more components
                     pca = PCA(n_components=n_components_pca, random_state=42)
                     pca.fit(scaled_data_pca)
                     variance_explained = pca.explained_variance_ratio_
                     cumulative_variance = np.cumsum(variance_explained)
                     summary_parts.append(f"\n[PCA Insights] (on {df_pca_input.shape[1]} numeric features)")
                     # summary_parts.append(f"Top {n_components_pca} components capture {cumulative_variance[-1]*100:.1f}% total variance.")
                     # Show top contributing features for each component
                     for i in range(n_components_pca):
                          component = pca.components_[i]
                          feature_loadings = pd.Series(component, index=df_pca_input.columns).abs().sort_values(ascending=False)
                          top_features = feature_loadings.head(5).index.tolist() # Show more features
                          summary_parts.append(f"- Comp. {i+1} ({variance_explained[i]*100:.1f}% var, cum: {cumulative_variance[i]*100:.1f}%) influenced by: {top_features}")
            except Exception as e:
                summary_parts.append(f"\n[PCA Insights]\nAnalysis failed: {e}")
        else:
             summary_parts.append("\n[PCA Insights]\nSkipped: No numeric columns.")


        # --- Mutual Information (MI) Insights (if target_col provided) ---
        if target_col_name and aligned_target_data is not None:
            target_type = 'unknown'
            try:
                # Prepare data for MI - handle NaNs and non-numeric types
                # X_mi = df_sample.drop(columns=[target_col_name], errors='ignore').copy() # Use df_sample aligned earlier
                X_mi = df_sample.copy() # Use df_sample aligned earlier
                y_mi = aligned_target_data.copy()
                # Basic target preprocessing
                if pd.api.types.is_numeric_dtype(y_mi):
                    y_mi.fillna(y_mi.median(), inplace=True)
                    target_type = 'regression'
                    # Optional: Discretize target for MI if it's continuous?
                    # discretizer = KBinsDiscretizer(n_bins=5, encode='ordinal', strategy='uniform')
                    # y_mi = discretizer.fit_transform(y_mi.values.reshape(-1, 1)).ravel()
                elif pd.api.types.is_categorical_dtype(y_mi) or pd.api.types.is_object_dtype(y_mi):
                     y_mi.fillna(y_mi.mode()[0], inplace=True)
                     le = LabelEncoder()
                     y_mi = le.fit_transform(y_mi)
                     target_type = 'classification'
                else:
                     raise ValueError("Target column type not suitable for MI analysis.")

                # Preprocess features for MI (handle NaNs, encode categoricals)
                processed_features_mi = {}
                feature_names_mi = []
                discrete_mask_mi = []
                for col in X_mi.columns:
                    if pd.api.types.is_numeric_dtype(X_mi[col]):
                        processed_features_mi[col] = X_mi[col].fillna(X_mi[col].median()).values
                        feature_names_mi.append(col)
                        discrete_mask_mi.append(False) # Continuous features
                    elif pd.api.types.is_categorical_dtype(X_mi[col]) or pd.api.types.is_object_dtype(X_mi[col]):
                        filled_col = X_mi[col].fillna(X_mi[col].mode()[0])
                        le = LabelEncoder()
                        processed_features_mi[col] = le.fit_transform(filled_col).astype(int) # Ensure integer type
                        feature_names_mi.append(col)
                        discrete_mask_mi.append(True) # Discrete features
                    # else: skip other types

                if not feature_names_mi:
                     summary_parts.append("\n[Mutual Information]\nSkipped: No suitable features found after preprocessing.")
                else:
                    # Stack processed features into a 2D array
                    X_mi_processed = np.column_stack([processed_features_mi[name] for name in feature_names_mi])

                    # Calculate MI based on target type
                    if target_type == 'regression':
                        mi_scores = mutual_info_regression(X_mi_processed, y_mi, discrete_features=discrete_mask_mi, random_state=42)
                    elif target_type == 'classification':
                        mi_scores = mutual_info_classif(X_mi_processed, y_mi, discrete_features=discrete_mask_mi, random_state=42)
                    else: # Should not happen if initial check is done
                         raise ValueError("Unknown target type for MI.")

                    mi_series = pd.Series(mi_scores, index=feature_names_mi).sort_values(ascending=False)
                    top_n_mi = min(10, len(mi_series)) # Show more features
                    summary_parts.append(f"\n[Mutual Information] (relevance to '{target_col_name}')")
                    summary_parts.append(f"Top {top_n_mi} features by MI score:")
                    for feature, score in mi_series.head(top_n_mi).items():
                        summary_parts.append(f"- {feature}: {score:.3f}") # Higher score = more informative

            except Exception as e:
                summary_parts.append(f"\n[Mutual Information]\nAnalysis failed: {e}")
        elif target_col_name:
             summary_parts.append(f"\n[Mutual Information]\nSkipped: Target column '{target_col_name}' data not available or alignment failed.")
        else:
             summary_parts.append("\n[Mutual Information]\nSkipped: Target column not provided.")


        # --- Basic LGBM Feature Importance (if target_col provided) ---
        if target_col_name and aligned_target_data is not None:
            try:
                # Prepare data - Use numeric and simple categorical
                X_lgbm = df_sample.copy() # Use aligned df_sample
                y_lgbm = aligned_target_data.copy()
                lgbm_feature_names = []
                categorical_features_lgbm = []

                # Preprocessing
                for col in X_lgbm.columns:
                    if pd.api.types.is_numeric_dtype(X_lgbm[col]):
                        X_lgbm[col] = X_lgbm[col].fillna(X_lgbm[col].median())
                        lgbm_feature_names.append(col)
                    elif X_lgbm[col].nunique() < 20 and pd.api.types.is_object_dtype(X_lgbm[col]): # Simple categorical encoding
                         X_lgbm[col] = X_lgbm[col].fillna(X_lgbm[col].mode()[0]).astype('category')
                         lgbm_feature_names.append(col)
                         categorical_features_lgbm.append(col)
                    # else: drop other types

                X_lgbm = X_lgbm[lgbm_feature_names] # Keep only processed columns

                if X_lgbm.empty:
                    raise ValueError("No features left after preprocessing for LGBM.")

                # Determine task type and model
                if pd.api.types.is_numeric_dtype(y_lgbm):
                    y_lgbm = y_lgbm.fillna(y_lgbm.median())
                    lgbm_params = {'objective': 'regression_l1', 'metric': 'mae', 'n_estimators': 50, 'learning_rate': 0.05, 'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 1, 'verbose': -1, 'n_jobs': -1, 'seed': 42, 'boosting_type': 'gbdt'}
                    model = lgb.LGBMRegressor(**lgbm_params)
                else: # Assume classification
                     y_lgbm = y_lgbm.fillna(y_lgbm.mode()[0])
                     le_lgbm = LabelEncoder()
                     y_lgbm = le_lgbm.fit_transform(y_lgbm)
                     num_class = len(le_lgbm.classes_)
                     lgbm_params = {'objective': 'multiclass' if num_class > 2 else 'binary', 'metric': 'multi_logloss' if num_class > 2 else 'binary_logloss', 'n_estimators': 50, 'learning_rate': 0.05, 'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 1, 'verbose': -1, 'n_jobs': -1, 'seed': 42, 'boosting_type': 'gbdt'}
                     if num_class > 2:
                         lgbm_params['num_class'] = num_class
                     model = lgb.LGBMClassifier(**lgbm_params)

                # Train model
                model.fit(X_lgbm, y_lgbm, categorical_feature=[col for col in categorical_features_lgbm if col in X_lgbm.columns])

                # Get feature importance
                importances = pd.Series(model.feature_importances_, index=lgbm_feature_names).sort_values(ascending=False)
                top_n_lgbm = min(10, len(importances)) # Show more features
                summary_parts.append(f"\n[LGBM Importance] (predicting '{target_col_name}')")
                summary_parts.append(f"Top {top_n_lgbm} features by importance:")
                for feature, score in importances.head(top_n_lgbm).items():
                    summary_parts.append(f"- {feature}: {score}")

            except Exception as e:
                summary_parts.append(f"\n[LGBM Importance]\nAnalysis failed: {e}")
        elif target_col_name:
             summary_parts.append(f"\n[LGBM Importance]\nSkipped: Target column '{target_col_name}' data not available or alignment failed.")
        else:
             summary_parts.append("\n[LGBM Importance]\nSkipped: Target column not provided.")


        # --- K-Means Clustering Insights (Enhanced) ---
        if not df_numeric_sample.empty:
            try:
                df_kmeans_input = df_numeric_sample.fillna(df_numeric_sample.median())
                if df_kmeans_input.empty or df_kmeans_input.shape[1] < 1:
                     summary_parts.append("\n[Clustering Insights]\nSkipped: Not enough numeric features or data.")
                else:
                     scaler_kmeans = StandardScaler()
                     scaled_data_kmeans = scaler_kmeans.fit_transform(df_kmeans_input)

                     # Find optimal K using silhouette score
                     best_k = -1
                     best_score = -1.1 # Initialize below valid range
                     max_k = min(6, scaled_data_kmeans.shape[0] - 1) if scaled_data_kmeans.shape[0] > 1 else -1
                     silhouette_scores = {}

                     if max_k >= 2:
                         for k in range(2, max_k + 1):
                             try:
                                 kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto') # Use 'auto' for n_init
                                 labels = kmeans.fit_predict(scaled_data_kmeans)
                                 # Need at least 2 unique labels for silhouette score
                                 if len(np.unique(labels)) > 1:
                                     score = silhouette_score(scaled_data_kmeans, labels)
                                     silhouette_scores[k] = score
                                     if score > best_score:
                                         best_score = score
                                         best_k = k
                                 else:
                                     # If only 1 cluster is formed, score is undefined, skip k
                                     print(termcolor.colored(f"Silhouette calculation skipped for k={k}: Only 1 cluster found.", "grey"))
                                     continue
                             except Exception as kmeans_e:
                                  print(termcolor.colored(f"Silhouette calculation failed for k={k}: {kmeans_e}", "grey"))
                                  continue

                     if best_k != -1:
                          kmeans = KMeans(n_clusters=best_k, random_state=42, n_init='auto')
                          labels = kmeans.fit_predict(scaled_data_kmeans)
                          centroids_scaled = kmeans.cluster_centers_
                          # Inverse transform centroids to original scale for interpretability
                          centroids_original = scaler_kmeans.inverse_transform(centroids_scaled)
                          centroid_df = pd.DataFrame(centroids_original, columns=df_kmeans_input.columns)
                          centroid_df_scaled = pd.DataFrame(centroids_scaled, columns=df_kmeans_input.columns) # Scaled version for variance calc

                          # Identify features with largest variance across centroids (potential separators)
                          centroid_variance = centroid_df_scaled.var(axis=0).sort_values(ascending=False)
                          top_separator_features = centroid_variance.head(5).index.tolist() # More features
                          # Identify features with smallest variance across centroids (common features)
                          least_variance_features = centroid_variance.nsmallest(3).index.tolist()

                          summary_parts.append(f"\n[Clustering Insights] (K-Means on {df_kmeans_input.shape[1]} numeric features)")
                          summary_parts.append(f"Optimal K found: {best_k} (Max Silhouette Score: {best_score:.2f})")
                          cluster_counts = pd.Series(labels).value_counts().sort_index()
                          summary_parts.append(f"Cluster sizes: {dict(cluster_counts)}")
                          summary_parts.append(f"Features varying MOST across clusters (potential separators): {top_separator_features}")
                          summary_parts.append(f"Features varying LEAST across clusters (common traits): {least_variance_features}")

                          # Show centroid means for top separating features
                          summary_parts.append("Centroid Means (Original Scale) for Top Separating Features:")
                          for cluster_i in range(best_k):
                             means = centroid_df.loc[cluster_i, top_separator_features].to_dict()
                             means_str = ", ".join([f"'{k}': {v:.2f}" for k, v in means.items()])
                             summary_parts.append(f"- Cluster {cluster_i}: {means_str}")
                     else:
                          summary_parts.append("\n[Clustering Insights]\nCould not determine optimal K or data unsuitable for K-Means.")

            except Exception as e:
                summary_parts.append(f"\n[Clustering Insights]\nAnalysis failed: {e}")
        else:
            summary_parts.append("\n[Clustering Insights]\nSkipped: No numeric columns.")

        summary_parts.append("\n--- End Summary ---")
        return "\n".join(summary_parts)

    async def close_clients(self):
        # Close clients if they are still open
        if self.client_coder:
            await self.client_coder.close()
        if self.client_validator:
            await self.client_validator.close()