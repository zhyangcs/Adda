import sys
import os

from src import env
import asyncio

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.agents.web_surfer import MultimodalWebSurfer
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType

import termcolor
import re
from datetime import datetime

import networkx as ni
import json

from src.llm.utils.llm_util import *
from src.llm.llm_dag_node import *
from src.llm.utils.agent_prompt import *

# 调试
import pandas as pd
import networkx as nx
from src.llm.llm_dag_node import LLMDAGNODE, allocate_node_id
from src.pg.op_type import OpTypeEnum


class Planner:

    def __init__(self, root_node:LLMDAGNODE, target_col:str, task_description:str, data_agenda:str):

        """
        初始化Planner：
            1.初始化OpenAI服务
            2.初始化AssistantAgent
            3.初始化Agent记忆
        """
        
        self.task_description = task_description # 任务描述
        self.target_col = target_col # 目标列
        self.data_agenda = data_agenda # 数据信息

        self.model_client = OpenAIChatCompletionClient(
            model="gpt-4o-2024-08-06",
            base_url=env.openai_base_url,
            api_key=env.openai_api_key
        )

        # 计划记忆列表
        plan_memory = ListMemory()
        working_memory = ListMemory()

        # 核心agent
        self.core_agent = AssistantAgent(
            name = "Planner",
            model_client = self.model_client,
            description = CORE_AGENT_DESCRIPTION,
            memory = [plan_memory, working_memory]
        )

    def one_step_planning(self, current_dag:nx.DiGraph):

        """
        核心方法，用于单次节点拓展前的计划规划

        input:
            current_dag: 表示特征生成过程的有向无环图，用于序列化后组成prompt
        """
        self.serialized_tree_str = self._convert_dag_to_string(current_dag) # 序列化后的生成树

        # TODO: 构建各阶段prompt

        # 1.对执行结果进行分析
        # 构建分析用prompt
        # analysis_prompts = ANALYSISI_PROMPT.format(
        #     task_desc = self.task_description,
        #     base_feature_info = self.data_agenda,
        #     target_column_name = self.target_col,
        #     feature_generation_tree = self.serialized_tree_str
        # )

        # # print(analysis_prompts)
        # # exit()

        # result1 = asyncio.run(self.core_agent.run(task=analysis_prompts)).messages[1].content
        # print(result1)
        # exit()

        result1 = """
在之前的特征搜索过程中，agent们尝试从基础特征到新的特征生成，所记录的特征生成树和效果如下：

特征生成树中的节点信息仅包含一个根节点，表示没有进行进一步的特征生成。以下是对该节点信息的分析：

1. **节点1**：
   - **特征生成代码**：没有记录任何特征生成代码，表明该节点没有通过计算或组合生成新的特征。
   - **模型精度**：使用基础特征进行机器学习预测时，模型的精度为0.6771。

在给出的特征生成树和关系中，仅有一个节点，没有其他特征组合计算或新的特征生成尝试。因此，无法进一步分析特征组合的效果，以及特征计算对模型精度的影响。也无从探析特定基础特征或计算方法（如加减乘除、对数操作等）能够增加或减少模型预测精度的具体规律。

总结来说，在这个特征生成过程中：
- 没有进行任何新特征生成尝试。
- 当前基于基础特征的模型达到了精度0.6771。

由于缺乏后续节点生成关系和不同特征组合尝试的信息，因此无法评价特征生成树中的其他生成方向走势。
        """

        # 2.根据分析结果，对任务进行猜想
        # sepculate_prompt = SEPCULATE_PROMPT.format(result1=result1)
        # result2 = asyncio.run(self.core_agent.run(task=sepculate_prompt)).messages[1].content
        # print(result2)
        # exit()
        # TODO: 从result2中提取猜想增删改操作，并根据标签类型进行分类操作
        result2 = """
根据之前的分析结果和根节点的信息，以及通用特征构建实践，我对新特征的组合和计算方式作出以下猜想：

1. **猜想1**：尝试组合年龄(age)与吸烟相关特征（如currentsmoker和cigsperday），生成一个新的特征"age_smoker_interaction"，可能提高模型对心脏病风险的预测效果。
   - **可信度**：中等，因为年龄和吸烟是公认的心血管风险因子，可以通过交互效应影响心脏病风险。

2. **猜想2**：通过组合身体指标，如体重指数(bmi)和血糖(glucose)，生成一个新的特征"bmi_glucose_ratio"，可能提高模型识别肥胖或代谢综合征患者的能力。
   - **可信度**：较高，因为肥胖和糖尿病均是心脏病的风险因子，比例形式可以揭示潜在关系。

3. **猜想3**：使用对数变换处理总胆固醇（totchol）以生成一个新特征"log_totchol"，可能提高模型效果。
   - **可信度**：较低，因为对数变换在处理较大数值范围数据时能稳定模型，但其实际效果依赖特征分布。

4. **猜想4**：组合收缩压（sysbp）和舒张压（diabp）生成一个新的特征"pulse_pressure"，评估其对心脏病风险的预测效果。
   - **可信度**：中等，因为脉压与心血管事件关系密切。

根据上述猜想的可信度评估，我将进行以下工作记忆调整：

<add>猜想1：年龄与吸烟相关特征组合，生成"age_smoker_interaction" + 中等<add> 
<add>猜想2：组合体重指数与血糖生成"bmi_glucose_ratio" + 较高<add> 
<add>猜想3：对数变换总胆固醇生成"log_totchol" + 较低<add> 
<add>猜想4：组合收缩压与舒张压生成"pulse_pressure" + 中等<add> 

TERMINATE
        """
        # 解析添加操作
        add_pattern = re.compile(r'<add>(.*?)<add>', re.DOTALL)
        add_matches = add_pattern.findall(result2)
        for match in add_matches:
            # 分离猜想内容和可信度
            content_str, confidence = match.rsplit('+', 1)
            content_str = content_str.strip()
            confidence = confidence.strip()
            # 创建带可信度的记忆内容
            full_content = f"{content_str} (可信度: {confidence})"
            memory_content = MemoryContent(content=full_content, mime_type="text/plain")
            # 添加到工作记忆
            asyncio.run(self.working_memory.add(memory_content))
        
        # 解析删除操作
        del_pattern = re.compile(r'<del>(.*?)<del>', re.DOTALL)
        del_matches = del_pattern.findall(result2)
        for idx in del_matches:
            # 转换为整数索引并删除对应记忆
            index = int(idx.strip()) - 1  # 假设序号从1开始
            if 0 <= index < len(self.working_memory.content):
                self.working_memory.content.pop(index)
        
        # 解析修改操作
        rev_pattern = re.compile(r'<rev>\[(.*?)\](.*?)<rev>', re.DOTALL)
        rev_matches = rev_pattern.findall(result2)
        for idx, new_content in rev_matches:
            # 转换为整数索引并修改对应记忆
            index = int(idx.strip()) - 1  # 假设序号从1开始
            if 0 <= index < len(self.working_memory.content):
                self.working_memory.content[index] = MemoryContent(
                    content=new_content.strip(), mime_type="text/plain"
                )
        
        print(self.working_memory.content)

        # 3.生成和调整计划
        planning_prompt = PLANNING_PROMPT.format(result2=result2)
        result3 = asyncio.run(self.core_agent.run(task=planning_prompt)).messages[1].content

    def _convert_dag_to_string(self, current_dag:ni.DiGraph):
        """
        将DAG结构序列化为包含 node_id、task_code 和 final_score 的 JSON 字符串。
        输出格式：
        {
            "node_info": [
                {
                    "node_id": 1,
                    "task_code": "df['new_col'] = df['col1'] + df['col2']",
                    "final_score": 0.85
                },
                ...
            ],
            "parent_child_relations": [
                [1, 2],
                [1, 3],
                ...
            ]
        }
        """
        if not current_dag:
            return None
    
        # 提取节点信息
        node_info = []
        for node in current_dag.nodes:
            node_info.append({
                "node_id": node.node_id,
                "task_code": node.task_code,
                "final_score": node.final_score
            })
    
        # 提取边信息
        parent_child_relations = []
        for edge in current_dag.edges:
            parent_id = edge[0].node_id
            child_id = edge[1].node_id
            parent_child_relations.append([parent_id, child_id])
    
        # 构建 JSON 数据结构
        result = {
            "node_info": node_info,
            "parent_child_relations": parent_child_relations
        }
    
        # 序列化为 JSON 字符串
        return json.dumps(result, ensure_ascii=False, indent=2)
    

if __name__ == '__main__':
    # 模拟根节点数据
    root_node = LLMDAGNODE(
        node_id=allocate_node_id(),
        task_code="",
        read_set=set(),
        write_set=set(),
        in_cur_df=pd.DataFrame({
            'age': [25, 30, 35],
            'income': [50000, 60000, 70000],
            'tenyearchd': [0, 1, 0]
        }),
        out_cur_df=pd.DataFrame({
            'age': [25, 30, 35],
            'income': [50000, 60000, 70000],
            'tenyearchd': [0, 1, 0]
        }),
        column_info={
            'age': '年龄 (数值型)',
            'income': '收入 (数值型)',
            'tenyearchd': '目标变量: 是否有十年以上信用记录 (0/1)'
        },
        operation_desc="Root node",
        op_type=OpTypeEnum.UNSUPPORT,
        scores=pd.DataFrame(),
        final_score=0.0,
        whole_code="",
        fixing_node=[],
        drop_attrs=[],
        exec_time=0.0,
        attr_imp_order=['age', 'income', 'tenyearchd']
    )
    target_col = "tenyearchd"
    
    # 添加调试日志配置
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    # 初始化Planner
    logger.debug("初始化Planner实例...")
    planner = Planner(root_node, target_col)
    
    # 创建测试DAG
    current_dag = nx.DiGraph()
    current_dag.add_node(root_node)
    logger.debug(f"创建测试DAG，包含{len(current_dag.nodes)}个节点")
    
    # 调用one_step_planning方法进行调试
    logger.debug("开始执行one_step_planning...")
    try:
        planner.one_step_planning(current_dag)
        logger.debug("one_step_planning执行完成")
    except Exception as e:
        logger.error(f"one_step_planning执行失败: {str(e)}", exc_info=True)