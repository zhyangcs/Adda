#!/usr/bin/env python3
"""
测试API调用的超时功能
"""

import sys
import os
import time
from src.llm.utils.llm_util import send_prompt, send_prompt_n

def test_timeout():
    """测试API调用的超时功能"""
    print("=" * 50)
    print("测试API调用超时功能")
    print("=" * 50)
    
    # 测试简单的send_prompt
    print("\n1. 测试send_prompt超时...")
    test_prompt = "请简单回答：1+1等于几？"
    
    try:
        start_time = time.time()
        response = send_prompt("", test_prompt)
        end_time = time.time()
        
        if response is not None:
            print(f"✓ send_prompt成功，耗时: {end_time - start_time:.2f}秒")
            print(f"响应: {response[:100]}...")
        else:
            print("✗ send_prompt失败，返回None")
    except Exception as e:
        print(f"✗ send_prompt异常: {e}")
    
    # 测试send_prompt_n
    print("\n2. 测试send_prompt_n超时...")
    try:
        start_time = time.time()
        responses = send_prompt_n("", test_prompt, n=2)
        end_time = time.time()
        
        if responses and len(responses) > 0:
            print(f"✓ send_prompt_n成功，获得{len(responses)}个响应，耗时: {end_time - start_time:.2f}秒")
            for i, resp in enumerate(responses):
                print(f"响应{i+1}: {resp[:100]}...")
        else:
            print("✗ send_prompt_n失败，返回空列表")
    except Exception as e:
        print(f"✗ send_prompt_n异常: {e}")
    
    print("\n" + "=" * 50)
    print("超时测试完成")
    print("=" * 50)

if __name__ == "__main__":
    test_timeout()