import sys
import os
# 将项目根目录添加到模块搜索路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src import env
import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.agents.web_surfer import MultimodalWebSurfer
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
import termcolor
import re
from datetime import datetime

class Planner:
    """增强版特征工程规划器，基于Magentic-One架构"""
    
    def __init__(self, model_client: OpenAIChatCompletionClient):
        """
        参数:
            model_client: OpenAI模型客户端
        """
        self.model_client = model_client
        self.memo = []  # 存储备忘录
        
        # Surfer
        self.surfer = MultimodalWebSurfer(
            name="Surfer",
            model_client=model_client,
            description="网络搜索专家，负责获取外部知识和最佳实践"
        )
        
        # Thinker
        self.thinker = AssistantAgent(
            name="Thinker",
            model_client=model_client,
            description="深度思考专家，负责分析问题本质和提出创新方案",
            system_message=
                """你是深度思考专家，职责包括：
                1. 分析问题本质和核心矛盾
                2. 提出创新性的特征工程方案
                3. 评估方案的潜在风险和收益
                4. 提供多角度的思考视角"""
        )
        
        # 初始化团队
        self.team = MagenticOneGroupChat(
            participants=[
                self.surfer,
                self.thinker
            ],
            model_client=model_client
        )
    
    def build_task_prompt(self, data_context: str) -> str:
        """构建任务提示词"""
        return f"""你们是**特征工程规划团队**，负责为ML任务制定高质量的特征工程计划。

### 团队角色
1. Surfer: 网络搜索专家，负责获取外部知识和最佳实践
2. Thinker: 深度思考专家，负责创新方案

### 当前任务
基于以下数据上下文，生成特征工程计划：

{data_context}

### 输出要求
你的输出必须包含两个部分，用"---MEMO---"分隔：

1. 特征工程计划部分：
   - 生成3-5个高质量的特征工程战略要点
   - 每个要点需包含：
     * [优先级] [具体操作方向]
     * 实施建议
     * 预期效果
     * 潜在风险

2. 备忘录部分（在"---MEMO---"之后）：
   - 记录本次特征工程的关键决策
   - 记录成功/失败的经验教训
   - 记录需要后续关注的问题
   - 记录外部知识参考

### 团队讨论要求：
- 要求你们在讨论时对话尽量简短，只讲要点
- Surfer需要提供相关的外部最佳实践
- Thinker需要提供创新性的思考
"""

    def parse_response(self, response: str) -> tuple[str, str]:
        """
        解析响应，分离特征工程计划和备忘录
        
        参数:
            response: 原始响应文本
            
        返回:
            (feature_plan, memo): 特征工程计划和备忘录的元组
        """
        # 使用正则表达式分离两部分
        parts = re.split(r'---MEMO---', response, maxsplit=1)
        
        if len(parts) != 2:
            print(termcolor.colored("警告：响应格式不符合要求，无法分离备忘录", "yellow"))
            return response.strip(), ""
        
        feature_plan = parts[0].strip()
        memo = parts[1].strip()
        
        # 更新备忘录
        self.memo.append({
            "timestamp": datetime.now().isoformat(),
            "content": memo
        })
        
        return feature_plan, memo
    
    async def generate_plan(self, data_context: str) -> str:
        """
        生成特征工程计划
        
        参数:
            data_context: 包含数据描述、目标列和统计摘要的上下文信息
            
        返回:
            生成的计划文本
        """
        print(termcolor.colored("[Planner] 开始生成特征工程计划...", "blue"))
        try:
            # 构建任务提示词
            task_prompt = self.build_task_prompt(data_context)
            
            # 使用团队执行任务
            response = await self.team.run(task=task_prompt)
            
            # 处理响应
            last_message = response.strip() if isinstance(response, str) else ""
            
            # 分离特征工程计划和备忘录
            feature_plan, memo = self.parse_response(last_message)
            
            print(termcolor.colored(f"[Planner] 生成计划:\n{feature_plan}", "green"))
            print(termcolor.colored(f"[Planner] 备忘录:\n{memo}", "blue"))
            
            return feature_plan
            
        except Exception as e:
            print(termcolor.colored(f"[Planner] 计划生成失败: {e}", "red"))
            return ""

async def debug_planner():
    """调试方法"""
    # 初始化模型客户端
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-2024-08-06",
        base_url=env.openai_base_url,
        api_key=env.openai_api_key
    )
    
    # 模拟数据上下文
    sample_data_context = """
    /* Data description: The dataframe of the task `df` is loaded and in memory. Columns are also named attributes.
    Columns in `df` (true feature dtypes listed here, categoricals encoded as int):
    For each attribute, the following information is provided:
    gender: male or female (Integer, 1-yes, 0-no),
    age: Age of the patient (Integer),
    education: the education level of the patient (Categorical-Integer),
    currentsmoker: whether or not the patient is a current smoker (Integer, 1-yes, 0-no),
    cigsperday: the number of cigarettes that the person smoked on average in one day(Integer),
    bpmeds: whether or not the patient was on blood pressure medication (Integer, 1-yes, 0-no),
    prevalentstroke: whether or not the patient had previously had a stroke (Integer, 1-yes, 0-no),
    prevalenthyp: whether or not the patient was hypertensive (Integer, 1-yes, 0-no),
    diabetes: whether or not the patient had diabetes (Integer, 1-yes, 0-no),
    totchol: total cholesterol level (RealNumber),
    sysbp: systolic blood pressure (RealNumber),
    diabp: diastolic blood pressure (RealNumber),
    bmi: Body Mass Index (RealNumber),
    heartrate: heart rate (RealNumber),
    glucose: glucose level (RealNumber),
    tenyearchd: 10 year risk of coronary heart disease CHD (binary: "1" means "Yes" "0" means "No") (target column)
    cardio_risk_index: (created in previous step) An index assessing cardiac risk based on smoking, glucose levels, cholesterol, and BMI.
    mean_sysbp_smokers_50_plus: (created in previous step) Calculate the mean value of systolic blood pressure (sysbp) for patients aged 50 and above who are current smokers. Filter the dataframe to include only rows where age is 50 or greater and currentsmoker is 1 (yes). Compute the mean of sysbp in this filtered dataset and store it in the attribute mean_sysbp_smokers_50_plus.
    mean_glucose_hyp_diabetes: (created in previous step) Calculate the mean value of glucose levels for all hypertensive patients who have diabetes. Filter the dataframe to include only rows where prevalenthyp is 1 (yes) and diabetes is 1 (yes). Compute the mean of glucose in this filtered dataset and store it in the attribute mean_glucose_hyp_diabetes.
    mean_totchol_male_no_bpmeds: (created in previous step) Calculate the mean value of total cholesterol (totchol) for male patients not on blood pressure medication. Filter the dataframe to include only rows where gender is 1 (male) and bpmeds is 0 (no). Compute the mean of totchol in this filtered dataset and store it in the attribute mean_totchol_male_no_bpmeds.
    mean_bmi_female_60_plus: (created in previous step) Calculate the average BMI (body mass index) of female patients aged 60 or older. Filter the dataframe to include only rows where gender is 0 (female) and age is 60 or greater. Compute the mean of bmi in this filtered dataset and store it in the attribute mean_bmi_female_60_plus.
    */ 
    
    
    Here are 3 examples, each illustrating the impact (increase/decrease) on the overall performance of a model after adding a new feature to a dataframe. These examples aim to provide guidance on generating new features.
    Memory 0: By Add Feature `{'mean_bmi_female_60_plus', 'mean_glucose_hyp_diabetes', 'mean_sysbp_smokers_50_plus', 'cardio_risk_index', 'mean_totchol_male_no_bpmeds'}` into original dataframe with attributes [ gender, age, education, currentsmoker, cigsperday, bpmeds, prevalentstroke, prevalenthyp, diabetes, totchol, sysbp, diabp, bmi, heartrate, glucose, tenyearchd], the prediction performance of model decrease 0.015103513580483341%.
    Memory 1: By Add Feature `{'risk_factor_score'}` into original dataframe with attributes [ gender, age, education, currentsmoker, cigsperday, bpmeds, prevalentstroke, prevalenthyp, diabetes, totchol, sysbp, diabp, bmi, heartrate, glucose, tenyearchd], the prediction performance of model decrease 2.244910782649223%.
    Memory 2: By Add Feature `{'cardio_risk_index'}` into original dataframe with attributes [ gender, age, education, currentsmoker, cigsperday, bpmeds, prevalentstroke, prevalenthyp, diabetes, totchol, sysbp, diabp, bmi, heartrate, glucose, tenyearchd], the prediction performance of model decrease 32.93675998979105%.
    """
    
    # 初始化规划器
    planner = Planner(model_client)
    
    # 使用Console显示流式对话过程
    result = await Console(planner.team.run_stream(task=planner.build_task_prompt(sample_data_context)))
    print("最终结果：", result.messages[-1].content)

if __name__ == "__main__":
    asyncio.run(debug_planner())
