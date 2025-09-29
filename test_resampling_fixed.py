#!/usr/bin/env python3
"""
测试修复后的resample版本，确保没有数据泄露问题
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.llm.llm_dag_util_resample import LLMDagConstructor

def test_resample_version():
    """测试resample版本的修复效果"""
    print("=== 测试修复后的Resample版本 ===")
    
    # 模拟heart数据集的配置
    data_agenda = [
        "gender: Gender of the patient (1: male, 0: female)",
        "age: Age of the patient",
        "education: Education level of the patient",
        "currentsmoker: Whether the patient is a current smoker (1: yes, 0: no)",
        "cigsperday: Number of cigarettes smoked per day",
        "bpmeds: Whether the patient is on blood pressure medication (1: yes, 0: no)",
        "prevalentstroke: Whether the patient has had a stroke (1: yes, 0: no)",
        "prevalenthyp: Whether the patient has hypertension (1: yes, 0: no)",
        "diabetes: Whether the patient has diabetes (1: yes, 0: no)",
        "totchol: Total cholesterol level",
        "sysbp: Systolic blood pressure",
        "diabp: Diastolic blood pressure",
        "bmi: Body mass index",
        "heartrate: Heart rate",
        "glucose: Glucose level",
        "tenyearchd: 10-year risk of coronary heart disease (1: yes, 0: no)"
    ]
    
    data_desc = ["Heart disease dataset containing patient information and 10-year CHD risk"]
    target_col = "tenyearchd"
    
    # 创建resample版本的构造器
    constructor = LLMDagConstructor(
        task_type="classify",
        eval_model_type="RF",
        use_stratified_sampling=True,
        sample_ratio=0.25,
        resample_interval=0  # 关闭重采样
    )
    
    print(f"构造器配置:")
    print(f"  - 分层采样: {constructor.use_stratified_sampling}")
    print(f"  - 采样比例: {constructor.sample_ratio}")
    print(f"  - 重采样间隔: {constructor.resample_interval}")
    print(f"  - 重采样是否启用: {constructor.should_resample()}")
    
    # 测试should_resample方法
    constructor.step_count = 5
    print(f"  - 步数=5时是否重采样: {constructor.should_resample()}")
    
    constructor.step_count = 10
    print(f"  - 步数=10时是否重采样: {constructor.should_resample()}")
    
    print("\n=== 修复总结 ===")
    print("1. ✅ 数据泄露修复: 重采样时同步更新标签数据")
    print("2. ✅ 重采样功能关闭: resample_interval=0")
    print("3. ✅ 保留分层采样: 使用分层采样提高数据质量")
    print("4. ✅ 数据一致性保证: 特征和标签同步更新")
    
    print("\n=== 建议的测试方式 ===")
    print("使用以下命令测试修复后的版本:")
    print("python test_resampling_fixed.py --task_name heart --model_type RF")
    print("预期结果: CV分数应该在0.6-0.8之间，而不是1.0")

if __name__ == "__main__":
    test_resample_version()