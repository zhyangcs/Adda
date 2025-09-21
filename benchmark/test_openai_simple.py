#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版测试脚本：测试OpenAI API响应格式
用于快速验证LLM响应的格式是否符合预期
"""

import os
import sys
import re
from typing import List

# 简化的prompt模板（与nl_agent.py中使用的相同）
PROMPT_TEMPLATE = """/* Data description: 
Columns in `df` (true feature dtypes listed here, categoricals encoded as int):
For each attribute, the following information is provided:
age (int64): Age of the patient in years
sex (int64): Gender of the patient (1=male, 0=female)
cp (int64): Chest pain type (1=typical angina, 2=atypical angina, 3=non-anginal pain, 4=asymptomatic)
trestbps (int64): Resting blood pressure in mm Hg
chol (int64): Serum cholesterol in mg/dl
fbs (int64): Fasting blood sugar > 120 mg/dl (1=true, 0=false)
restecg (int64): Resting electrocardiographic results (0=normal, 1=ST-T wave abnormality, 2=left ventricular hypertrophy)
thalach (int64): Maximum heart rate achieved
exang (int64): Exercise induced angina (1=yes, 0=no)
oldpeak (float64): ST depression induced by exercise relative to rest
slope (int64): Slope of the peak exercise ST segment (1=upsloping, 2=flat, 3=downsloping)
ca (int64): Number of major vessels colored by fluoroscopy
thal (int64): Thalassemia (3=normal, 6=fixed defect, 7=reversable defect)
*/ 

In this task, you should generate a meaningful new feature for predicting Outcome using open-world knowledge and the attribute set.
The downstream RandomForest machine learning model will be trained on the new feature you generate.
You can try to prioritize attributes that are less frequently used, if you have multiple choices at the same time.
you should execute one of the following operations to generate a new feature:
an Multiple-Elements operation: use +,-,*,/,&,|,!,>>,<< and some arithmetic operator to transform **several input features** to **one new feature**. you should generate the feature which is meaningful to the real world instead of randomly arithmetic combination of several features.
an Unary-Elements operation: use discretization or apply a custom function to transform **one input feature** to **one new feature**. 

No previous features generated.
Output format:
'new_feature': the name of the new feature.
'detailed description': a description of the new feature.
'brief description': a brief description of the new feature.
'relevant': a list of relevant columns used to extract the feature (excluding attribute target).
except the four lines above, do not generate other useless msg, including the operation type.
notice: do not generate the same feature we have generated before !!!
Moreover, do not use the target_col(target) to be the relevant column for generating the new feature."""

def test_parse_logic(response: str) -> List[str]:
    """测试解析逻辑，模拟nl_agent.py中的parse_nl_comma方法"""
    print(f"\n=== 测试解析响应 ===")
    print(f"响应内容:\n{response}")
    
    # 期望的字段列表
    expected_fields = ["new_feature", "detailed description", "brief description", "relevant"]
    print(f"期望字段: {expected_fields}")
    
    # 按行分割，查找包含冒号的行
    lines = [line.strip() for line in response.split("\n") if line.strip() and ":" in line]
    print(f"找到的带冒号行数: {len(lines)}")
    
    if len(lines) != len(expected_fields):
        print(f"❌ 行数不匹配！期望{len(expected_fields)}行，实际{len(lines)}行")
        return []
    
    results = []
    for i, line in enumerate(lines):
        print(f"\n--- 解析第{i+1}行 ---")
        print(f"行内容: {line}")
        print(f"期望字段: {expected_fields[i]}")
        
        # 尝试解析每一行
        try:
            # 使用正则表达式匹配格式
            pattern1 = r"""'(.*)':(.*)"""
            pattern2 = r'"(.*)":(.*)'
            
            match1 = re.search(pattern1, line)
            match2 = re.search(pattern2, line)
            
            if match1:
                match = match1
            elif match2:
                match = match2
            else:
                print(f"❌ 正则匹配失败")
                results.append("")
                continue
            
            # 提取内容
            if match.group(1) == expected_fields[i]:
                content = match.group(2).strip()
            else:
                content = match.group(1).strip()
            
            # 处理方括号
            if content.startswith("[") and content.endswith("]"):
                content = content[1:-1]
            
            # 清理引号和逗号
            content = content.strip(",").strip("'").strip('"').strip()
            
            print(f"✅ 解析成功: {content}")
            results.append(content)
            
        except Exception as e:
            print(f"❌ 解析失败: {e}")
            results.append("")
    
    print(f"\n=== 最终解析结果 ===")
    print(f"结果: {results}")
    print(f"长度: {len(results)}")
    
    return results

def test_index_access(results: List[str]):
    """测试索引访问，模拟原始代码中的问题"""
    print(f"\n=== 测试索引访问 ===")
    
    if not results:
        print("❌ 没有解析结果，无法测试索引访问")
        return
    
    try:
        # 模拟原始代码中的索引访问逻辑
        if len(results) >= 4:
            # 这些是原始代码中可能导致索引越界的操作
            op_type = "BINARY" if "UNARY" not in results[0] else "DISCRETIZE"
            out_attr = results[-4] if len(results) > 3 else ""
            operation_desc = results[-3] if len(results) > 2 else ""
            operation_desc_brief = results[-2] if len(results) > 1 else ""
            rel_cols = results[-1] if len(results) > 0 else ""
            
            print(f"✅ 索引访问成功:")
            print(f"  op_type: {op_type}")
            print(f"  out_attr: {out_attr}")
            print(f"  operation_desc: {operation_desc}")
            print(f"  operation_desc_brief: {operation_desc_brief}")
            print(f"  rel_cols: {rel_cols}")
        else:
            print(f"❌ 结果长度不足4个元素，无法进行索引访问")
            print(f"当前长度: {len(results)}")
            
    except IndexError as e:
        print(f"❌ 索引访问失败: {e}")
        print(f"尝试访问的索引超出了列表范围")
    except Exception as e:
        print(f"❌ 其他错误: {e}")

def test_openai_api():
    """测试OpenAI API调用"""
    print("=== 测试OpenAI API ===")
    
    # 检查环境变量
    api_key = "sk-XFOqa14voF6GcmRF234d4768587f4213Ab50Fc94862393D3"
    if not api_key:
        print("❌ 未找到OPENAI_API_KEY环境变量")
        print("请设置环境变量: export OPENAI_API_KEY='your-api-key'")
        return
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key, base_url='https://api.mixrai.com/v1')
        
        print("🚀 发送prompt到OpenAI...")
        print(f"Prompt长度: {len(PROMPT_TEMPLATE)} 字符")
        
        # 调用API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": PROMPT_TEMPLATE}],
            temperature=0.8,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        print(f"\n✅ 收到OpenAI响应:")
        print(f"响应长度: {len(content)} 字符")
        print(f"响应内容:\n{content}")
        
        # 测试解析
        results = test_parse_logic(content)
        
        # 测试索引访问
        test_index_access(results)
        
    except ImportError:
        print("❌ 未安装openai库")
        print("请运行: pip install openai")
    except Exception as e:
        print(f"❌ API调用失败: {e}")

def test_mock_responses():
    """测试模拟响应"""
    print("=== 测试模拟响应 ===")
    
    # 模拟一些可能的LLM响应
    mock_responses = [
        # 标准格式响应
        """'new_feature': 'age_bmi_ratio'
'detailed description': 'Ratio of age to BMI, which can capture age-related health patterns'
'brief description': 'Age to BMI ratio feature'
'relevant': ['age', 'bmi']""",
        
        # 格式不完整的响应
        """'new_feature': 'heart_rate_zone'
'detailed description': 'Categorize heart rate into zones based on age and gender'""",
        
        # 格式错误的响应
        """new_feature: age_bmi_ratio
detailed description: Ratio of age to BMI
brief description: Age to BMI ratio
relevant: [age, bmi]""",
        
        # 完全错误的响应
        """I will create a new feature called age_bmi_ratio.
This feature combines age and BMI information.
The relevant columns are age and BMI."""
    ]
    
    for i, response in enumerate(mock_responses):
        print(f"\n--- 测试模拟响应 {i+1} ---")
        print(f"响应类型: {'标准格式' if i == 0 else '格式不完整' if i == 1 else '格式错误' if i == 2 else '完全错误'}")
        
        results = test_parse_logic(response)
        test_index_access(results)

def main():
    """主函数"""
    print("🚀 开始测试OpenAI响应格式")
    print("=" * 60)
    
    # 测试1: 模拟响应
    test_mock_responses()
    
    # 测试2: 实际OpenAI API调用
    test_openai_api()
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("\n💡 分析结果:")
    print("1. 检查LLM响应是否包含所有必需的4个字段")
    print("2. 验证响应格式是否符合预期（单引号+冒号格式）")
    print("3. 确认索引访问是否安全")
    print("4. 找出导致'list index out of range'错误的具体原因")

if __name__ == "__main__":
    main()
