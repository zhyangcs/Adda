from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool
import asyncio
import json # Added for potentially parsing results
import re

from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import ExternalTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import CancellationToken

openai_client = OpenAIChatCompletionClient(
    model='gpt-4o',
    base_url='https://api.nuwaapi.com/v1',
    api_key='sk-YIkcYQ4PqHhKPyJf7sE8NQALxRwRrix2VXglnXOpkkheP7dY'
    )

openai_client2 = OpenAIChatCompletionClient(
    model='gpt-4o',
    base_url='https://api.nuwaapi.com/v1',
    api_key='sk-YIkcYQ4PqHhKPyJf7sE8NQALxRwRrix2VXglnXOpkkheP7dY'
    )

# deepseek_client = OpenAIChatCompletionClient(
#     model='deepseek-reasoner',
#     base_url='https://tbnx.plus7.plus/v1',
#     api_key='sk-rSDtptEgBmIW5YME094CTMI18YkP6BPP4glifiMPlv5IKxqO',
#     model_info={
#         "name": "deepseek-reasoner",
#         "max_tokens": 4096,
#         "context_length": 4096,
#         "input_cost_per_token": 0.000001,
#         "output_cost_per_token": 0.000002,
#         "supports_function_calling": True,
#         "supports_vision": False,
#         "supports_streaming": True,
#         "vision": False,
#         "function_calling": True,
#         "json_output": True,
#         "family": "unknown",
#         "structured_output": True
#     }
# )

# deepseek_client2 = OpenAIChatCompletionClient(
#     model='deepseek-reasoner',
#     base_url='https://tbnx.plus7.plus/v1',
#     api_key='sk-rSDtptEgBmIW5YME094CTMI18YkP6BPP4glifiMPlv5IKxqO',
#     model_info={
#         "name": "deepseek-reasoner",
#         "max_tokens": 4096,
#         "context_length": 4096,
#         "input_cost_per_token": 0.000001,
#         "output_cost_per_token": 0.000002,
#         "supports_function_calling": True,
#         "supports_vision": False,
#         "supports_streaming": True,
#         "vision": False,
#         "function_calling": True,
#         "json_output": True,
#         "family": "unknown",
#         "structured_output": True
#     }
# )


# Define a simple function tool that the agent can use.
# For this example, we use a fake weather tool for demonstration purposes.
async def get_weather(city: str) -> str:
    """Get the weather for a given city."""
    return f"The weather in {city} is 73 degrees and Sunny."


async def get_weather_online(city: str) -> str:
    """Get the weather for a given city online."""
    return f"return the weather for a given city online."

web_search_tool = FunctionTool(get_weather_online, description="search the weather for a given city online")


# Define the Feature Engineer Agent
feature_engineer = AssistantAgent(
    name="feature_engineer",
    model_client=openai_client2,
    system_message="""You are a Feature Engineer. Your goal is to propose new features based on the provided dataframe description.
Analyze the column names, data types, sample values, and statistics.
Propose ONE new feature definition using Python code that operates on a pandas DataFrame named `df`.
The code should define a new column. For example: `df['new_feature'] = df['col_a'] * df['col_b']`.
Explain the rationale behind the new feature.
Output ONLY the Python code snippet for creating the new feature within ```python ... ``` blocks.""",
    reflect_on_tool_use=False, # No tools needed for this agent yet
    model_client_stream=True,
)

# Define the Feature Validator Agent
feature_validator = AssistantAgent(
    name="feature_validator",
    model_client=openai_client,
    system_message="""You are a Feature Validator. Evaluate the feature proposed by the Feature Engineer.
Consider the following:
1.  **Relevance**: Is the new feature likely to be useful for a downstream machine learning task (e.g., prediction, classification)?
2.  **Correctness**: Is the Python code syntactically correct and likely to execute without errors given the input dataframe structure?
3.  **Novelty**: Is the feature genuinely new or just a simple restatement of an existing one?
4.  **Rationale**: Is the explanation provided by the engineer sound?

Based on your evaluation, respond with:
-   'APPROVE' if the feature is good.
-   'REJECT' followed by specific reasons and suggestions for improvement if the feature is not good.
Do not approve trivial features like simple copies or constant values.""",
    reflect_on_tool_use=False, # No tools needed for this agent
    model_client_stream=True,
)

# Define the termination condition
text_termination = TextMentionTermination("APPROVE")

# Define the team
team = RoundRobinGroupChat([feature_engineer, feature_validator], termination_condition=text_termination)

# Function to run the feature engineering process
async def run_feature_engineering(dataframe_description: str) -> str | None:
    """
    Runs the feature engineering Autogen team.

    Args:
        dataframe_description: A string describing the dataframe (columns, types, stats, samples).

    Returns:
        The generated Python code snippet for the new feature if approved, otherwise None.
    """
    task_prompt = f"""Here is the description of the dataframe `df`:
{dataframe_description}

Based on this information, please propose a new feature."""

    # Use run instead of run_stream if we want the final result directly
    # Need to adjust how results are captured if using run_stream outside Console
    final_result : TaskResult = await team.run(task=task_prompt)

    if final_result.status == "completed" and final_result.messages and "APPROVE" in final_result.messages[-1].content:
        # Try to extract the python code from the feature_engineer's last message
        # This assumes the engineer's message is the second to last (before validator's APPROVE)
        # And that the engineer followed the output format instruction
        engineer_message = final_result.messages[-2].content # Assuming validator is last
        code_match = re.search(r"```python\n(.*?)\n```", engineer_message, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        else:
            # Fallback or error handling if code block not found
            print("Warning: Could not extract Python code from the engineer's message.")
            return None # Or potentially return the engineer's full message
    else:
        print(f"Feature engineering did not complete successfully or was not approved. Status: {final_result.status}")
        # You might want to log final_result.summary or final_result.messages[-1].content for debugging
        return None

# Example usage (optional, can be removed or kept for direct testing)
async def main() -> None:
    # Example dataframe description (replace with actual dynamic description)
    example_desc = """Columns:
- age (int64): NaN-freq [0.0%], Skewness [0.5], unique num [50], Samples [25, 47, 30, 52, 19]
- salary (float64): NaN-freq [10.0%], Skewness [1.2], unique num [150], Samples [50000.0, 60000.0, 45000.0, 75000.0, 52000.0]
- department (object): NaN-freq [0.0%], Skewness [NaN], unique num [5], Samples ['HR', 'Engineering', 'Sales', 'Engineering', 'Sales']
- years_experience (int64): NaN-freq [0.0%], Skewness [0.8], unique num [20], Samples [2, 20, 5, 25, 1]
"""
    generated_code = await run_feature_engineering(example_desc)

    if generated_code:
        print("\n--- Generated Feature Code ---")
        print(generated_code)
        print("----------------------------")
    else:
        print("\nNo feature code was approved.")

    # Close the connection to the model client.
    # Ensure these clients are defined correctly earlier in the script
    if 'openai_client' in globals() and openai_client:
        await openai_client.close()
    if 'openai_client2' in globals() and openai_client2:
        await openai_client2.close()

# Main execution block
if __name__ == "__main__":
    # NOTE: if running this inside a Python script you'll need to use asyncio.run(main()).
    # We keep the main guard but the primary use will be calling run_feature_engineering from elsewhere.
    # Consider adding command-line argument parsing here if needed for standalone testing.
    # asyncio.run(main()) # Comment out or remove if not needed for direct execution
    pass # Keep the file runnable, but default action is nothing when imported