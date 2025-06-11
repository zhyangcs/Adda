from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat

# 创建思维链工具
async def get_next_step(current_step: int) -> str:
    steps = [
        "第一步：分析问题关键信息",
        "第二步：考虑用户具体需求",
        "第三步：设计初步行程",
        "第四步：评估可行性",
        "第五步：优化行程安排",
        "第六步：补充细节",
        "第七步：检查完整性",
        "第八步：总结最终计划"
    ]
    return steps[current_step]

# 创建助手
assistant = AssistantAgent(
    name="cot_assistant",
    system_message="你是一个使用思维链的旅游规划助手。请按照提示完成每个步骤。",
    tools=[get_next_step]
)

# 创建终止条件
termination = TextMentionTermination("完成所有步骤")

# 创建团队
team = RoundRobinGroupChat(
    [assistant],
    max_turns=len(steps),
    termination_condition=termination
)