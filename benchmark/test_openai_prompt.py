#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：使用与nl_agent.py中相同的prompt调用OpenAI API
用于分析LLM响应格式，找出导致"list index out of range"错误的原因
"""

import os
import sys
import json
import re
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 模拟prompt模板（从src/llm/utils/prompt.py中提取）
NEXT_STEP_FREE = """{data_desc} 
In this task, you should generate a meaningful new feature for predicting Outcome using open-world knowledge and the attribute set.
The downstream {model_type} machine learning model will be trained on the new feature you generate.
Think what High-order statistics feature could be generated in the field of current task using the given attributes.
You could use operator like add, subtract, multiply, divide, and, or, not, shift, etc, or some popular data processing method as bucketization, normalization, numerization, or apply some function to the attribute to generate the new feature.
Moreover, you could use some condition description to generate the feature more accurate, such as 'male', who drink alcohol more than 3, who do not have the diabetes, etc.

Here is one High-order Feature Example in other domain: we compute the cvhi by compute the standard normalized value of diabp, double of the mean of bmi who do not have the diabetes but using blood pressure medication, 
the half value of the mean value of person's systolic blood pressure whose glucose level is bigger than 13, the mean value of the sysbp, and the mean value of the summation of totchol and age.
then we sum all of the variable mentioned above with the factor of 0.5, 2, 0.5, 1, and 1 respectively, and finally divide by the bmi to be named as the parameter of tmp1.
we then compute the average value of the bmi of male who smoking 2~5 cigarettes each day, and divide by the logarithm of the summation of ones's diastolic blood pressure who do not had stroke, and multiply the result to the tmp1 as final result.

{memory_info}
Output format:
'new_feature': the name of the new feature.
'detailed description': a description of the new feature.
'brief description': a brief description of the new feature.
'relevant': a list of relevant columns used to extract the feature (excluding attribute {y_attr}).
except the four lines above, do not generate other useless msg, including the operation type or ```json wrapped.
notice: do not generate the same feature we have generated before !!!
"""

NEXT_STEP_FORMAT = """{data_desc} 
In this task, you should generate a meaningful new feature for predicting Outcome using open-world knowledge and the attribute set.
The downstream {model_type} machine learning model will be trained on the new feature you generate.
You can try to prioritize attributes that are less frequently used, if you have multiple choices at the same time.
you should execute one of the following operations to generate a new feature:
an Multiple-Elements operation: use +,-,*,/,&,|,!,>>,<< and some arithmetic operator to transform **several input features** to **one new feature**. you should generate the feature which is meaningful to the real world instead of randomly arithmetic combination of several features.
an Unary-Elements operation: use discretization or apply a custom function to transform **one input feature** to **one new feature**. 

{memory_info}
Output format:
'new_feature': the name of the new feature.
'detailed description': a description of the new feature.
'brief description': a brief description of the new feature.
'relevant': a list of relevant columns used to extract the feature (excluding attribute {y_attr}).
except the four lines above, do not generate other useless msg, including the operation type.
notice: do not generate the same feature we have generated before !!!
Moreover, do not use the target_col({y_attr}) to be the relevant column for generating the new feature.
"""

NEXT_STEP_FORMAT_SHRINK = """{data_desc} 
In this task, you should generate a meaningful new feature for predicting Outcome using open-world knowledge and the attribute set.
The downstream {model_type} machine learning model will be trained on the new feature you generate.
You can try to prioritize attributes that are less frequently used, if you have multiple choices at the same time.
you should execute one of the following operations to generate a new feature:
an Multiple-Elements operation: use +,-,*,/,&,|,!,>>,<< and some arithmetic operator to transform **several input features** to **one new feature**. you should generate the feature which is meaningful to the real world instead of randomly arithmetic combination of several features.

{memory_info}
Output format:
'new_feature': the name of the new feature.
'detailed description': a description of the new feature.
'brief description': a brief description of the new feature.
'relevant': a list of relevant columns used to extract the feature (excluding attribute {y_attr}).
except the four lines above, do not generate other useless msg, including the operation type.
notice: do not generate the same feature we have generated before !!!
"""

# 模拟数据描述
SAMPLE_DATA_DESC = """/* Data description: 
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
*/"""

class MockNLAgent:
    """模拟NLAgent类，用于测试prompt解析逻辑"""
    
    normal_feature_pre_list = ["new_feature", "detailed description", "brief description", "relevant"]
    high_order_feature_pre_list = ["new_feature", "detailed description", "brief description", "relevant"]
    
    @staticmethod
    def parse_nl_comma(content: str, pre_list: List[str]) -> List[str]:
        """模拟parse_nl_comma方法的逻辑"""
        print(f"\n=== 解析响应内容 ===")
        print(f"期望格式: {pre_list}")
        print(f"响应内容:\n{content}")
        
        # 按行分割，查找包含冒号的行
        content_lines_with_end = [line + "^" for line in content.split("\n") if line != "" and ":" in line]
        print(f"找到的带冒号行数: {len(content_lines_with_end)}")
        print(f"期望行数: {len(pre_list)}")
        
        if len(content_lines_with_end) != len(pre_list):
            print(f"❌ 错误: 行数不匹配！期望{len(pre_list)}行，实际{len(content_lines_with_end)}行")
            return ""
        
        res = []
        try:
            for i, line in enumerate(content_lines_with_end):
                print(f"\n--- 解析第{i+1}行 ---")
                print(f"行内容: {line}")
                print(f"期望前缀: {pre_list[i]}")
                
                # 模拟parse_one_comma的逻辑
                parsed = MockNLAgent.parse_one_comma(line, pre_list[i])
                res.append(parsed)
                print(f"解析结果: {parsed}")
        except Exception as e:
            print(f"❌ 解析异常: {e}")
            return ""
        
        print(f"\n=== 最终解析结果 ===")
        print(f"结果列表: {res}")
        print(f"结果长度: {len(res)}")
        return res
    
    @staticmethod
    def parse_one_comma(content: str, prefix: str) -> str:
        """模拟parse_one_comma方法的逻辑"""
        # 使用正则表达式匹配格式
        pattern1 = r"""'(.*)':(.*)\^"""
        pattern2 = r'"(.*)":(.*)\^'
        
        match1 = re.search(pattern1, content, re.DOTALL)
        match2 = re.search(pattern2, content, re.DOTALL)
        
        if match1:
            match = match1
        elif match2:
            match = match2
        else:
            print(f"❌ 正则匹配失败: {content}")
            raise ValueError(f"match failed content {content}, regenerating the code")
        
        # 提取匹配的内容
        if match.group(1) == prefix:
            ans = match.group(2).strip()
        else:
            ans = match.group(1).strip()
        
        # 处理方括号
        if ans.startswith("[") and ans.endswith("]"):
            ans = ans[1:-1]
        
        # 清理引号和逗号
        ans = ans.strip(",").strip("'").strip('"').strip()
        
        print(f"提取的内容: {ans}")
        return ans

def test_prompt_templates():
    """测试不同的prompt模板"""
    print("=== 测试Prompt模板 ===")
    
    # 测试参数
    test_params = {
        'data_desc': SAMPLE_DATA_DESC,
        'y_attr': 'target',
        'memory_info': 'No previous features generated.',
        'model_type': 'RandomForest'
    }
    
    templates = [
        ("NEXT_STEP_FREE", NEXT_STEP_FREE),
        ("NEXT_STEP_FORMAT", NEXT_STEP_FORMAT),
        ("NEXT_STEP_FORMAT_SHRINK", NEXT_STEP_FORMAT_SHRINK)
    ]
    
    for name, template in templates:
        print(f"\n--- {name} ---")
        try:
            formatted_prompt = template.format(**test_params)
            print(f"格式化后的prompt长度: {len(formatted_prompt)} 字符")
            print(f"Prompt预览 (前500字符):\n{formatted_prompt[:500]}...")
        except Exception as e:
            print(f"❌ 格式化失败: {e}")

def test_parse_logic():
    """测试解析逻辑"""
    print("\n=== 测试解析逻辑 ===")
    
    # 模拟一些可能的LLM响应
    test_responses = [
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
    
    agent = MockNLAgent()
    
    for i, response in enumerate(test_responses):
        print(f"\n--- 测试响应 {i+1} ---")
        print(f"响应类型: {'标准格式' if i == 0 else '格式不完整' if i == 1 else '格式错误' if i == 2 else '完全错误'}")
        
        try:
            # 使用normal_feature_pre_list进行解析
            result = agent.parse_nl_comma(response, agent.normal_feature_pre_list)
            
            if result:
                print(f"✅ 解析成功，结果: {result}")
                
                # 测试索引访问（模拟原始代码中的问题）
                try:
                    if len(result) >= 4:
                        op_type = "BINARY" if "UNARY" not in result[0] else "DISCRETIZE"
                        out_attr = result[-4] if len(result) > 3 else ""
                        operation_desc = result[-3] if len(result) > 2 else ""
                        operation_desc_brief = result[-2] if len(result) > 1 else ""
                        rel_cols = result[-1] if len(result) > 0 else ""
                        
                        print(f"✅ 索引访问成功:")
                        print(f"  op_type: {op_type}")
                        print(f"  out_attr: {out_attr}")
                        print(f"  operation_desc: {operation_desc}")
                        print(f"  operation_desc_brief: {operation_desc_brief}")
                        print(f"  rel_cols: {rel_cols}")
                    else:
                        print(f"❌ 结果长度不足4个元素，无法进行索引访问")
                except IndexError as e:
                    print(f"❌ 索引访问失败: {e}")
            else:
                print(f"❌ 解析失败，返回空结果")
                
        except Exception as e:
            print(f"❌ 解析异常: {e}")

def test_openai_api_simulation():
    """模拟OpenAI API调用（需要实际的API密钥）"""
    print("\n=== 模拟OpenAI API调用 ===")
    
    # 检查是否有OpenAI API配置
    # api_key = os.getenv('OPENAI_API_KEY')
    # base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    api_key = "sk-XFOqa14voF6GcmRF234d4768587f4213Ab50Fc94862393D3"
    base_url = 'https://api.mixrai.com/v1/chat'
    
    if not api_key:
        print("⚠️  未找到OPENAI_API_KEY环境变量，跳过实际API调用")
        print("请设置环境变量后重新运行")
        return
    
    try:
        from openai import OpenAI
        
        client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        
        # 构建测试prompt
        test_prompt = NEXT_STEP_FORMAT.format(
            data_desc=SAMPLE_DATA_DESC,
            y_attr='target',
            memory_info='No previous features generated.',
            model_type='RandomForest'
        )
        
        print("发送prompt到OpenAI...")
        print(f"Prompt长度: {len(test_prompt)} 字符")
        
        # 调用API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # 使用较便宜的模型进行测试
            messages=[
                {"role": "user", "content": test_prompt}
            ],
            temperature=0.8,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        print(f"\n✅ 收到OpenAI响应:")
        print(f"响应长度: {len(content)} 字符")
        print(f"响应内容:\n{content}")
        
        # 测试解析逻辑
        print(f"\n--- 测试解析OpenAI响应 ---")
        agent = MockNLAgent()
        result = agent.parse_nl_comma(content, agent.normal_feature_pre_list)
        
        if result:
            print(f"✅ 解析成功，结果: {result}")
        else:
            print(f"❌ 解析失败")
            
    except ImportError:
        print("❌ 未安装openai库，请运行: pip install openai")
    except Exception as e:
        print(f"❌ API调用失败: {e}")

def main():
    """主函数"""
    print("🚀 开始测试OpenAI Prompt响应格式")
    print("=" * 60)
    
    # 测试1: Prompt模板
    test_prompt_templates()
    
    # 测试2: 解析逻辑
    test_parse_logic()
    
    # 测试3: 模拟OpenAI API调用
    test_openai_api_simulation()
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("\n💡 建议:")
    print("1. 检查LLM响应格式是否符合预期")
    print("2. 确保响应包含所有必需的字段")
    print("3. 考虑在解析前添加响应格式验证")
    print("4. 实现重试机制处理格式错误的响应")

if __name__ == "__main__":
    main()
