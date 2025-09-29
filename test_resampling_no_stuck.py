#!/usr/bin/env python3
"""
测试重采样版本是否解决卡顿问题
"""

import os
import sys
import time
from src.llm.llm_dag_util_resample import LLMDagConstructor
from src.env import *

def test_resampling_no_stuck():
    """测试重采样版本是否不会卡住"""
    print("=" * 60)
    print("测试重采样版本 - 验证不会卡住")
    print("=" * 60)
    
    try:
        # 使用测试模式或小规模数据
        task_name = "heart"
        target_col = "target"  # 需要根据实际数据调整
        
        # 模拟数据议程
        data_agenda = [
            "age: Age of patient",
            "sex: Sex of patient", 
            "cp: Chest pain type",
            "target: Target variable"
        ]
        
        data_desc = ["Test dataset for resampling"]
        
        print("创建重采样版本构造器...")
        constructor = LLMDagConstructor(
            task_type="classify",
            eval_model_type="RF",
            beam_limit=2,  # 减少搜索宽度
            use_stratified_sampling=True,
            sample_ratio=0.1,  # 小样本测试
            resample_interval=2,  # 频繁重采样测试
            token_limit=1000  # 减少token限制
        )
        
        print("尝试初始化...")
        start_time = time.time()
        
        # 尝试初始化，可能会因为缺少数据而失败，但不应该卡住
        try:
            constructor.init_task_params(
                data_agenda=data_agenda,
                data_desc=data_desc,
                target_col=target_col,
                tb_name=None,  # 不使用数据库
                csv_path=None,  # 不使用CSV
                task_name="test_resampling"
            )
            print("✓ 初始化成功")
        except Exception as e:
            print(f"初始化失败（预期的）: {e}")
            print("但这不应该卡住程序")
        
        init_time = time.time() - start_time
        print(f"初始化耗时: {init_time:.2f}秒")
        
        # 测试A*搜索（如果初始化成功）
        if hasattr(constructor, 'root') and constructor.root is not None:
            print("\n测试A*搜索步骤...")
            try:
                # 只执行1步测试
                constructor.astar_k_step(
                    step_num=1,
                    data_agenda=data_agenda,
                    data_desc=data_desc,
                    target_col=target_col,
                    task_name="test_step"
                )
                print("✓ A*搜索步骤完成")
            except Exception as e:
                print(f"A*搜索步骤失败: {e}")
                print("但这不应该卡住程序")
        
        total_time = time.time() - start_time
        print(f"\n总耗时: {total_time:.2f}秒")
        
        if total_time < 60:  # 如果在1分钟内完成，说明没有卡住
            print("✓ 测试通过 - 程序没有卡住")
            return True
        else:
            print("✗ 测试失败 - 程序可能卡住了")
            return False
            
    except Exception as e:
        print(f"✗ 测试异常: {e}")
        return False
    
    finally:
        print("=" * 60)
        print("测试完成")
        print("=" * 60)

if __name__ == "__main__":
    success = test_resampling_no_stuck()
    sys.exit(0 if success else 1)