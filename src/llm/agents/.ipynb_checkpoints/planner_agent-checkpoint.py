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


class Planner:

    def __init__(self, root_node:LLMDAGNODE, target_col:str):

        """
        初始化Planner：
            1.初始化OpenAI服务
            2.初始化AssistantAgent
            3.初始化Agent记忆
        """
        self.dataframe_description = df_desc = get_column_info(cur_node.column_info, 800, root_node.attr_imp_order)
        
        self.model_client = OpenAIChatCompletionClient(
            model="gpt-4o-2024-08-06",
            base_url=env.openai_base_url,
            api_key=env.openai_api_key
        )

        # 计划记忆列表
        plan_memory = ListMemory()

        # TODO: 阅读文档，寻找适合工作记忆的数据结构

        # 核心agent
        # TODO: 界定core agent的角色定位
        self.core_agent = AssistantAgent(
            name = "Planner",
            model_client = self.model_client,
            # description = ""
            # tool = []
            # memory = []
        )

    def one_step_planning(self, current_dag:nx.DiGraph):

        """
        核心方法，用于单次节点拓展前的计划规划

        input:
            current_dag: 表示特征生成过程的有向无环图，用于序列化后组成prompt
        """
        serialized_tree_str = self._convert_dag_to_string(current_dag)

        # TODO: 构建各阶段prompt
        

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
    # TODO: 写调试方法
    
    
