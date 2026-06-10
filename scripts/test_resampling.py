#!/usr/bin/env python3
"""
测试重采样版本的LLM DAG构造器
"""

import os
import sys
import pandas as pd
from src.llm.llm_dag_util_resample import LLMDagConstructor
from src.env import *
from src.llm.utils.common_utils import *

def test_resampling():
    """测试重采样功能"""
    print("=" * 50)
    print("测试重采样版本LLM DAG构造器")
    print("=" * 50)
    
    # 测试参数
    task_name = "heart"
    target_col = "target"
    task_type = "classify"
    
    # 模拟数据议程和描述
    data_agenda = [
        "age: Age of patient",
        "sex: Sex of patient (1=male, 0=female)", 
        "cp: Chest pain type",
        "trestbps: Resting blood pressure",
        "chol: Serum cholesterol",
        "fbs: Fasting blood sugar > 120 mg/dl",
        "restecg: Resting electrocardiographic results",
        "thalach: Maximum heart rate achieved",
        "exang: Exercise induced angina",
        "oldpeak: ST depression induced by exercise",
        "slope: Slope of peak exercise ST segment",
        "ca: Number of major vessels",
        "thal: Thalassemia",
        "target: Diagnosis of heart disease"
    ]
    
    data_desc = [
        "This dataset contains medical information about heart disease patients.",
        "The goal is to predict the presence of heart disease based on various medical indicators.",
        "This is a binary classification task where target=1 indicates presence of heart disease."
    ]
    
    print(f"任务: {task_name}")
    print(f"目标列: {target_col}")
    print(f"任务类型: {task_type}")
    print()
    
    # 创建重采样版本的构造器
    print("创建LLMDagConstructor (重采样版本)...")
    constructor = LLMDagConstructor(
        task_type=task_type,
        eval_model_type="RF",
        beam_limit=3,
        use_stratified_sampling=True,  # 启用分层采样
        sample_ratio=0.3,              # 采样30%的数据
        resample_interval=3            # 每3步重采样一次
    )
    
    print(f"分层采样: {constructor.use_stratified_sampling}")
    print(f"采样比例: {constructor.sample_ratio}")
    print(f"重采样间隔: {constructor.resample_interval}")
    print()
    
    # 模拟初始化任务参数（需要真实数据）
    try:
        # 尝试从数据库或CSV文件初始化
        constructor.init_task_params(
            data_agenda=data_agenda,
            data_desc=data_desc,
            target_col=target_col,
            tb_name=f"{task_name}_src_tb_train" if os.path.exists(f"{dataset_path}/{task_name}") else None,
            csv_path=f"{dataset_path}/{task_name}/train_new.csv" if os.path.exists(f"{dataset_path}/{task_name}/train_new.csv") else None,
            task_name=task_name
        )
        
        print("✓ 初始化成功")
        print(f"数据集大小: {constructor.total_dataset_size}")
        print(f"采样数据大小: {constructor.root.out_cur_df.shape}")
        
        # 测试重采样方法
        print("\n测试重采样方法...")
        new_sample = constructor.resample_data()
        if new_sample is not None:
            print(f"✓ 重采样成功: {new_sample.shape}")
            
            # 检查分层采样的效果
            if constructor.use_stratified_sampling and target_col in new_sample.columns:
                original_dist = constructor.original_df[target_col].value_counts(normalize=True)
                sample_dist = new_sample[target_col].value_counts(normalize=True)
                print(f"原始数据分布:\n{original_dist}")
                print(f"采样数据分布:\n{sample_dist}")
                
        # 测试重采样判断
        print(f"\n测试重采样判断...")
        for step in range(1, 10):
            constructor.step_count = step
            should_resample = constructor.should_resample()
            print(f"步骤 {step}: {'需要重采样' if should_resample else '不需要重采样'}")
            
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        print("这可能是由于缺少数据文件或数据库连接问题")
        
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    test_resampling()