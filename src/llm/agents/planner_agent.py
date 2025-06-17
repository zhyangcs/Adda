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
        self.plan_memory = ListMemory()
        self.working_memory = ListMemory()

        # 核心agent
        self.core_agent = None
        self.already_list = []

    def one_step_planning(self, current_dag:nx.DiGraph):

        """
        核心方法，用于单次节点拓展前的计划规划

        input:
            current_dag: 表示特征生成过程的有向无环图，用于序列化后组成prompt
        """
        # 重置core agent
        self.core_agent = AssistantAgent(
            name = "Planner",
            model_client = self.model_client,
            description = CORE_AGENT_DESCRIPTION,
            memory = [self.plan_memory, self.working_memory]
        )

        self.serialized_tree_str = self._convert_dag_to_string(current_dag) # 序列化后的生成树

        # 1.对执行结果进行分析
        # 构建分析用prompt
        analysis_prompts = ANALYSISI_PROMPT.format(
            task_desc = self.task_description,
            base_feature_info = self.data_agenda,
            target_column_name = self.target_col,
            feature_generation_tree = self.serialized_tree_str
        )

        result1 = asyncio.run(self.core_agent.run(task=analysis_prompts)).messages[-1].content
        print(result1)

        # 2.根据分析结果，对任务进行猜想
        sepculate_prompt = SEPCULATE_PROMPT.format(result1=result1)
        result2 = asyncio.run(self.core_agent.run(task=sepculate_prompt)).messages[-1].content
        print(result2)

        # 解析添加操作
        add_pattern = re.compile(r'<add>(.*?)</add>', re.DOTALL)
        add_matches = add_pattern.findall(result2)
        for match in add_matches:
            # 将描述和可信度作为整体注入记忆条目
            memory_entry = match.strip()
            full_content = memory_entry
            memory_content = MemoryContent(content=full_content, mime_type="text/plain")
            # 添加到工作记忆
            asyncio.run(self.working_memory.add(memory_content))
        
        # 解析删除操作
        del_pattern = re.compile(r'<del>(.*?)</del>', re.DOTALL)
        del_matches = del_pattern.findall(result2)
        for idx in del_matches:
            # 转换为整数索引并删除对应记忆
            idx_str = idx.strip()
            try:
                index = int(idx_str) - 1  # 假设序号从1开始
            except ValueError:
                print(f"删除索引格式错误: {idx_str}，跳过删除操作")
                continue
            if 0 <= index < len(self.working_memory.content):
                self.working_memory.content.pop(index)
            else:
                print(f"删除索引超出范围: {idx_str}，跳过删除操作")
        
        # 解析修改操作
        rev_pattern = re.compile(r'<rev>\[(.*?)\](.*?)</rev>', re.DOTALL)
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
        planning_prompt = PLANNING_PROMPT.format(
            feature_generation_tree=self.serialized_tree_str, 
            result2=result2,
            already_list=self.already_list
        )
        result3 = asyncio.run(self.core_agent.run(task=planning_prompt)).messages[-1].content
        print(result3)

        # 解析result3中的待拓展节点和建议
        ext_pattern = re.compile(r'<ext>(.*?)</ext>', re.DOTALL)
        ext_matches = ext_pattern.findall(result3)
        if ext_matches:
            node_number = int(ext_matches[0].strip())
            # 存储节点编号，可根据需要进行后续处理
            print(f"提取到待拓展节点编号: {node_number}")
        
        sug_pattern = re.compile(r'<sug>(.*?)</sug>', re.DOTALL)
        sug_matches = sug_pattern.findall(result3)
        if sug_matches:
            suggestions = sug_matches[0].strip()
            # 存储建议，可根据需要进行后续处理
            print(f"提取到建议: {suggestions}")
        else:
            suggestions = ""

        self.already_list.append(node_number)

        return node_number, suggestions

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
        