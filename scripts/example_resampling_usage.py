#!/usr/bin/env python3
"""
使用重采样版本的示例脚本
"""

import os
import sys
from src.llm.llm_dag_util_resample import LLMDagConstructor
from src.env import *

def main():
    """使用重采样版本的主要示例"""
    
    # 配置参数
    task_name = "heart"  # 可以改为其他数据集名称
    model_type = "RF"    # 模型类型
    iter_num = 10        # 迭代次数
    sample_ratio = 0.25  # 采样比例
    resample_interval = 3 # 重采样间隔
    
    print(f"开始任务: {task_name}")
    print(f"模型类型: {model_type}")
    print(f"迭代次数: {iter_num}")
    print(f"采样策略: 分层采样 (比例: {sample_ratio})")
    print(f"重采样间隔: {resample_interval} 步")
    print("-" * 50)
    
    # 创建重采样版本的构造器
    constructor = LLMDagConstructor(
        task_type="classify",  # 根据具体任务调整
        eval_model_type=model_type,
        beam_limit=3,
        use_stratified_sampling=True,
        sample_ratio=sample_ratio,
        resample_interval=resample_interval,
        token_limit=8000
    )
    
    # 这里应该从实际数据源获取data_agenda和data_desc
    # 由于需要真实的数据配置，这里只是展示调用方式
    
    print("重采样版本已准备就绪!")
    print("使用方法:")
    print("1. 确保数据已导入数据库")
    print("2. 配置正确的data_agenda和data_desc")
    print("3. 调用constructor.astar_k_step()开始搜索")
    
    return constructor

if __name__ == "__main__":
    constructor = main()