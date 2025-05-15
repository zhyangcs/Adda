import sys
import os
# 将项目根目录添加到模块搜索路径（/home/ubuntu/autofe）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 新增：显式导入env模块
from src import env

import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.agents.web_surfer import MultimodalWebSurfer
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
from src.llm.utils.prompt import *
from src.llm.utils.common_utils import *
import termcolor
import re

class MagenticPlanner:
    """使用Magentic-One团队实现的特征工程计划生成器"""
    
    def __init__(self, model_client: OpenAIChatCompletionClient):
        """
        参数:
            model_client: OpenAI模型客户端（需提前初始化）
        """
        self.model_client = model_client
        
        # 数据分析师（负责基础特征处理+特征选择）
        self.data_analyst = AssistantAgent(
            name="DataAnalyst",
            model_client=model_client,
            system_message="""你是统计报告分析师，职责包括：
1. 解读单变量统计：分析特征方差/偏度/缺失率，识别需要特殊处理的特征
2. 解析相关性分析：识别强相关特征对，提出剔除冗余特征建议
3. 解构降维结果：根据PCA成分推荐特征组合策略
4. 评估特征重要性：基于互信息评分确定优先级"""
        )
        
        # 特征工程师（负责特征构造+业务适配）
        self.feature_engineer = AssistantAgent(
            name="FeatureEngineer",
            model_client=model_client,
            system_message="""你是特征工程实施专家，职责包括：
1. 特征构造：对时间序列字段分解年/月/日/星期并构造时间间隔；对连续数值特征分箱、生成多项式/交互项；组合分类与数值特征生成交叉特征。
2. 业务适配：根据场景构造时序行为特征、多维度关联特征。"""
        )

        # 网络搜索代理（新增针对性搜索提示词）
        self.web_surfer = MultimodalWebSurfer(
            name="WebSurfer",
            model_client=model_client
        )

        # 团队任务提示词新增协作要求
        self.team = MagenticOneGroupChat(
            # participants=[self.data_analyst, self.feature_engineer, self.web_surfer],
            participants=[self.data_analyst, self.feature_engineer],
            model_client=model_client
        )

    async def generate_plan(self, data_context: str) -> str:
        """
        生成特征工程计划的核心方法
        
        参数:
            data_context: 包含数据描述、目标列和统计摘要的上下文信息
            
        返回:
            生成的计划文本（要点列表）
        """
        print(termcolor.colored("[Magentic Planner] 开始生成特征工程计划...", "blue"))
        try:
            # 使用Magentic-One团队执行任务，并获取返回的消息
            response = await self.team.run(task=data_context)
            # 假设返回值包含最终消息（具体根据Autogen API调整）
            last_message = response.strip() if isinstance(response, str) else ""
            # 清理可能的Markdown符号
            cleaned_plan = re.sub(r'^[\*\-\+] ', '', last_message, flags=re.MULTILINE).strip()
            print(termcolor.colored(f"[Magentic Planner] 生成计划:\n{cleaned_plan}", "green"))
            return cleaned_plan
        except Exception as e:
            print(termcolor.colored(f"[Magentic Planner] 计划生成失败: {e}", "red"))
            return ""
        
def get_system_prompt() -> str:
        """团队任务提示词"""
        return f"""你们是**实战型特征工程规划团队**，负责为ML任务制定符合Kaggle竞赛级标准的特征工程战略计划。

### 核心任务（基于Kaggle特征工程方法论）
基于输入上下文，生成3-5个**可落地的特征工程战略要点**，需覆盖以下维度：

#### 一、基础特征处理（数据质量保障）
- 缺失值处理：根据缺失率和业务含义，选择均值/中位数填充、模型预测填充或新增缺失标记特征。
- 分类编码：低基数分类变量（如性别信息）用One-Hot编码；对高基数特征（如考试分数）用目标编码。

#### 二、特征构造（价值挖掘）
- 时间序列：若存在datetime列（如隐含时间字段），分解年/月/日/星期，并构造时间间隔（如"注册至今天数"）、节假日标记。
- 数值增强：对连续特征（如年龄）进行分箱（等频/等距）；对偏态特征生成log/sqrt变换；构造平方项、交互项。
- 特征交叉：组合分类与数值特征；计算空间特征（如经纬度距离，若有）。

#### 三、特征选择（效率优化）
- 过滤式：用方差选择（过滤低方差特征）、皮尔逊相关系数。

#### 四、场景适配（业务落地）
- 若为金融风控场景，重点构造时序行为特征、多维度关联特征。

### 输出要求
每个要点需包含：
`[优先级] [具体操作方向（方法论对应模块）] - 依据：[输入上下文数据特征+业务场景]`

### 团队讨论要求：
- 要求你们在讨论时对话尽量简短，只讲要点。

### 团队分工：
- 数据分析师（DataAnalyst）：负责基础特征处理+特征选择
- 特征工程师（FeatureEngineer）：负责特征构造+业务适配

回答示例：
1. 高优先级 缺失值处理（基础特征处理） - 依据：glucose列缺失率12%（输入上下文），且与目标列tenyearchd存在弱相关性（MI=0.15），建议用KNN模型预测填充并新增"glucose_missing"标记特征。
2. 中优先级 数值特征增强（特征构造） - 依据：sysbp（收缩压）偏度=1.8（输入上下文），属于右偏分布，建议生成log(sysbp+1)变换特征；同时构造sysbp*diabp（舒张压）交互项捕捉血压联合影响。
3. 低优先级 特征选择（过滤式） - 依据：totchol（总胆固醇）与ldl（若有）相关系数0.89（假设输入上下文），建议保留totchol并剔除ldl以降低冗余。

输入信息如下：
"""

async def debug_magentic_planner():
    """单独调试方法（使用Console显示流式对话过程）"""
    # 初始化模型客户端（从环境变量获取配置）
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-2024-08-06",
        base_url=env.openai_base_url,
        api_key=env.openai_api_key
    )
    
    # 模拟初始数据上下文（实际使用时替换为真实数据）
    sample_context = """
The "Framingham" heart disease dataset includes over 4,240 records,16 columns and 15 attributes. The goal of the dataset is to predict whether the patient has 10-year risk of future (CHD) coronary heart disease  
target col: tenyearchd    

The attributes are:
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
tenyearchd: 10 year risk of coronary heart disease CHD (binary: “1” means “Yes” “0” means “No”)

统计信息报告：
--- Statistical Insights Summary ---

[Univariate Statistics]
Numeric Columns (Top 5 by variance shown):
- 'id': Mean=1828.50, Median=1828.50, Std=1055.54, Skew=0.00, NaN=0.0%
- 'totchol': Mean=236.87, Median=234.00, Std=44.10, Skew=0.66, NaN=0.0%
- 'glucose': Mean=81.86, Median=78.00, Std=23.91, Skew=6.28, NaN=0.0%
- 'sysbp': Mean=132.37, Median=128.00, Std=22.09, Skew=1.16, NaN=0.0%
- 'heartrate': Mean=75.73, Median=75.00, Std=11.98, Skew=0.67, NaN=0.0%
No categorical columns found.

[Correlation Insights]
No strong positive correlations ( > 0.8) found.

[PCA Insights] (on 17 numeric features)
- Comp. 1 (19.4% var, cum: 19.4%) influenced by: ['sysbp', 'diabp', 'prevalenthyp', 'age', 'bmi']
- Comp. 2 (11.2% var, cum: 30.7%) influenced by: ['cigsperday', 'currentsmoker', 'gender', 'tenyearchd', 'diabp']
- Comp. 3 (9.3% var, cum: 40.0%) influenced by: ['diabetes', 'glucose', 'diabp', 'prevalenthyp', 'sysbp']
- Comp. 4 (6.8% var, cum: 46.8%) influenced by: ['heartrate', 'tenyearchd', 'gender', 'age', 'prevalentstroke']
- Comp. 5 (6.4% var, cum: 53.2%) influenced by: ['totchol', 'id', 'age', 'education', 'prevalentstroke']

[Mutual Information] (relevance to 'tenyearchd')
Top 10 features by MI score:
- tenyearchd: 0.423
- currentsmoker: 0.036
- diabp: 0.035
- sysbp: 0.021
- age: 0.020
- glucose: 0.018
- bpmeds: 0.015
- prevalenthyp: 0.014
- bmi: 0.012
- diabetes: 0.012

[Pearson分位数分析]
- 25%分位数: 0.03
- 中位数: 0.06
- 75%分位数: 0.13

[Top Pearson特征对]:
- sysbp & diabp: 0.79
- diabp & sysbp: 0.79
- currentsmoker & cigsperday: 0.77
- cigsperday & currentsmoker: 0.77
- prevalenthyp & sysbp: 0.70

[Clustering Insights] (K-Means on 17 numeric features)
Optimal K found: 2 (Max Silhouette Score: 0.20)
Cluster sizes: {0: np.int64(2480), 1: np.int64(1176)}
Features varying MOST across clusters (potential separators): ['prevalenthyp', 'sysbp', 'diabp', 'age', 'bmi']
Features varying LEAST across clusters (common traits): ['gender', 'id', 'prevalentstroke']
Centroid Means (Original Scale) for Top Separating Features:
- Cluster 0: 'prevalenthyp': 0.02, 'sysbp': 121.33, 'diabp': 77.58, 'age': 47.45, 'bmi': 24.83
- Cluster 1: 'prevalenthyp': 0.93, 'sysbp': 155.64, 'diabp': 94.16, 'age': 53.99, 'bmi': 27.79

--- End Summary ---
    """
    
    # 初始化计划生成器并获取团队实例
    planner = MagenticPlanner(model_client)
    # 使用Console显示流式对话过程（关键修改）
    result = await Console(planner.team.run_stream(task=get_system_prompt() + sample_context))
    print("最终结果：", result.messages[-1].content)

if __name__ == "__main__":
    asyncio.run(debug_magentic_planner())