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
from typing import Tuple

from src.llm.utils.llm_util import *
from src.llm.llm_dag_node import *

from src.llm.utils.planner_prompts.agent_prompt_i import * # 具有详细思维链指导要求的分析步骤提示词、基于自然语言的可信度等级划分、新的生成格式要求与生成格式提醒

# 调试
import pandas as pd
import networkx as nx
from src.llm.llm_dag_node import LLMDAGNODE, allocate_node_id
from src.pg.op_type import OpTypeEnum


class Planner:

    def __init__(self, root_node:LLMDAGNODE, target_col:str, task_description:str, data_agenda:str, max_retries:int = 3):

        """
        初始化Planner：
            1.初始化OpenAI服务
            2.初始化AssistantAgent
            3.初始化Agent记忆
            4.初始化重试机制参数
        """
        
        self.task_description = task_description # 任务描述
        self.target_col = target_col # 目标列
        self.data_agenda = data_agenda # 数据信息
        self.max_retries = max_retries  # 最大重试次数

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

        # 使用ReAct框架解析LLM响应，支持错误检测和重试机制
        # 获取当前DAG中的节点列表用于验证
        current_dag_nodes = list(current_dag.nodes) if current_dag else []
        
        try:
            node_number, suggestions = self._parse_llm_response_with_retry(result3, current_dag_nodes=current_dag_nodes)
            print(f"成功解析响应 - 节点编号: {node_number}, 建议: {suggestions[:100]}...")
            self.already_list.append(node_number)
            return node_number, suggestions
        except ValueError as e:
            print(f"解析LLM响应最终失败: {str(e)}")
            # 为了保持向后兼容性，可以选择一个默认节点或抛出异常
            # 这里选择抛出异常，让调用者处理
            raise e

    def _parse_llm_response_with_retry(self, result3: str, retry_count: int = 0, current_dag_nodes: list = None) -> Tuple[int, str]:
        """
        使用ReAct框架解析LLM响应，支持错误检测和重试机制
        
        Args:
            result3: LLM的响应内容
            retry_count: 当前重试次数
            current_dag_nodes: 当前DAG中的节点列表（可选）
            
        Returns:
            tuple[int, str]: (节点编号, 建议内容)
            
        Raises:
            ValueError: 当重试次数超过最大限制时抛出异常
        """
        try:
            return self._parse_llm_response(result3, current_dag_nodes)
        except (ValueError, IndexError, AttributeError) as e:
            print(f"第{retry_count + 1}次解析失败: {str(e)}")
            
            if retry_count >= self.max_retries:
                print(f"已达到最大重试次数{self.max_retries}，放弃重试")
                raise ValueError(f"解析LLM响应失败，已重试{self.max_retries}次") from e
            
            print(f"准备进行第{retry_count + 2}次重试...")
            return self._retry_with_error_feedback(result3, retry_count, str(e), current_dag_nodes)
    
    def _parse_llm_response(self, result3: str, current_dag_nodes: list = None) -> Tuple[int, str]:
        """
        解析LLM响应的核心逻辑
        
        Args:
            result3: LLM的响应内容
            current_dag_nodes: 当前DAG中的节点列表（可选）
            
        Returns:
            tuple[int, str]: (节点编号, 建议内容)
            
        Raises:
            ValueError: 当无法解析出有效的节点编号时抛出异常
        """
        # 1. 解析待拓展节点编号
        node_number = self._extract_node_number(result3)
        
        # 2. 解析建议内容
        suggestions = self._extract_suggestions(result3)
        
        # 3. 验证节点编号的合理性
        self._validate_node_number(node_number, current_dag_nodes)
        
        return node_number, suggestions
    
    def _extract_node_number(self, result3: str) -> int:
        """
        从LLM响应中提取节点编号，支持多种格式
        
        Args:
            result3: LLM的响应内容
            
        Returns:
            int: 提取的节点编号
            
        Raises:
            ValueError: 当无法提取节点编号时抛出异常
        """
        # 尝试标准格式 <ext>节点编号</ext>
        ext_pattern = re.compile(r'<ext>(.*?)</ext>', re.DOTALL)
        ext_matches = ext_pattern.findall(result3)
        
        if ext_matches:
            try:
                return int(ext_matches[0].strip())
            except ValueError as e:
                raise ValueError(f"节点编号格式错误: {ext_matches[0]}") from e
        
        # 尝试备选格式：寻找数字编号
        # 格式1: "节点X" 或 "node X"
        node_pattern = re.compile(r'(?:节点|node)\s*(\d+)', re.IGNORECASE)
        node_matches = node_pattern.findall(result3)
        
        if node_matches:
            try:
                return int(node_matches[0])
            except ValueError as e:
                raise ValueError(f"备选格式节点编号解析失败: {node_matches[0]}") from e
        
        # 格式2: "拓展节点编号: X" 或 "选择节点: X"
        select_pattern = re.compile(r'(?:拓展节点编号|选择节点|待拓展节点)[:：]\s*(\d+)', re.IGNORECASE)
        select_matches = select_pattern.findall(result3)
        
        if select_matches:
            try:
                return int(select_matches[0])
            except ValueError as e:
                raise ValueError(f"选择格式节点编号解析失败: {select_matches[0]}") from e
        
        # 格式3: 寻找独立的数字（作为最后备选）
        number_pattern = re.compile(r'\b(\d+)\b')
        numbers = number_pattern.findall(result3)
        
        # 过滤掉明显不是节点编号的数字（如年份、百分比等）
        valid_numbers = []
        for num in numbers:
            num_int = int(num)
            # 合理的节点编号范围（1-1000）
            if 1 <= num_int <= 1000:
                valid_numbers.append(num_int)
        
        if valid_numbers:
            # 选择第一个合理的数字
            return valid_numbers[0]
        
        raise ValueError("无法从LLM响应中提取节点编号")
    
    def _extract_suggestions(self, result3: str) -> str:
        """
        从LLM响应中提取建议内容
        
        Args:
            result3: LLM的响应内容
            
        Returns:
            str: 提取的建议内容
        """
        # 尝试标准格式 <sug>建议内容</sug>
        sug_pattern = re.compile(r'<sug>(.*?)</sug>', re.DOTALL)
        sug_matches = sug_pattern.findall(result3)
        
        if sug_matches:
            return sug_matches[0].strip()
        
        # 如果没有找到标准格式，返回空字符串
        return ""
    
    def _validate_node_number(self, node_number: int, current_dag_nodes: list = None) -> None:
        """
        验证节点编号的合理性
        
        Args:
            node_number: 要验证的节点编号
            current_dag_nodes: 当前DAG中的节点列表（可选）
            
        Raises:
            ValueError: 当节点编号不合理时抛出异常
        """
        if not isinstance(node_number, int):
            raise ValueError(f"节点编号必须是整数，得到: {type(node_number)}")
        
        if node_number <= 0:
            raise ValueError(f"节点编号必须大于0，得到: {node_number}")
        
        if node_number in self.already_list:
            print(f"警告: 节点{node_number}已经在已选择列表中")
            raise ValueError(f"节点{node_number}已经被选择过，请选择其他节点")
        
        # 验证节点是否存在于当前DAG中
        if current_dag_nodes is not None:
            node_exists = any(node.node_id == node_number for node in current_dag_nodes)
            if not node_exists:
                raise ValueError(f"节点{node_number}不存在于当前DAG中，请选择存在的节点")
            
            # 提供可选节点建议
            available_nodes = [node.node_id for node in current_dag_nodes if node.node_id not in self.already_list]
            if available_nodes:
                print(f"可选择的节点: {available_nodes[:10]}...")  # 显示前10个可用节点
    
    def _retry_with_error_feedback(self, original_response: str, retry_count: int, error_message: str, current_dag_nodes: list = None) -> Tuple[int, str]:
        """
        在重试时向LLM提供错误反馈
        
        Args:
            original_response: 原始的LLM响应
            retry_count: 当前重试次数
            error_message: 错误信息
            current_dag_nodes: 当前DAG中的节点列表（可选）
            
        Returns:
            tuple[int, str]: (节点编号, 建议内容)
        """
        print(f"向LLM提供错误反馈: {error_message}")
        
        # 构建可用节点信息
        available_nodes_info = ""
        if current_dag_nodes:
            available_nodes = [node.node_id for node in current_dag_nodes if node.node_id not in self.already_list]
            if available_nodes:
                available_nodes_info = f"\n可选择的节点编号: {available_nodes[:10]}{'...' if len(available_nodes) > 10 else ''}"
        
        # 构建错误反馈提示词
        error_feedback_prompt = f"""
你的上一次响应没有按照要求的格式输出。具体错误信息：
{error_message}

请严格按照以下格式重新生成响应：
1. 必须包含 <ext>待拓展节点编号</ext> 标签，其中待拓展节点编号是纯数字
2. 必须包含 <sug>若干条建议</sug> 标签
3. 待拓展节点编号必须是特征生成树中已有的节点编号
4. 不能选择之前已经选择过的节点编号: {self.already_list}
{available_nodes_info}

你之前的分析结果：{original_response}

请重新生成符合格式要求的响应：
"""
        
        # 调用LLM重新生成响应
        retry_result = asyncio.run(self.core_agent.run(task=error_feedback_prompt)).messages[-1].content
        print(f"第{retry_count + 2}次重试的LLM响应:")
        print("=" * 50)
        print(retry_result)
        print("=" * 50)
        
        # 递归调用解析函数
        return self._parse_llm_response_with_retry(retry_result, retry_count + 1, current_dag_nodes)

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
        