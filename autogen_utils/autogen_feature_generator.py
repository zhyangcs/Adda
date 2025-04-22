from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
# import asyncio # No longer needed
import re

# --- Client Configuration --- 
# Reuse the client configuration from the original demo
# Make sure API keys and endpoints are correctly set
openai_client = OpenAIChatCompletionClient(
    model='gpt-4o', # Or your preferred model
    base_url='https://api.nuwaapi.com/v1', # Replace if necessary
    api_key='sk-F6l6kc8Xlqb6FlP8ll0cST1GmXB5uSIDZIYyGvL0W2mdkg0F' # Replace with your key or use environment variables
)

# --- Define the NL Feature Describer Agent --- 
nl_feature_describer = AssistantAgent(
    name="nl_feature_describer",
    model_client=openai_client,
    system_message="""You are an expert data scientist assistant. 
Your task is to generate a *single* meaningful new feature description based on the provided data context and instructions in the user prompt.
Use your open-world knowledge and the provided attribute set.

**Crucially, your output MUST strictly follow the format requested in the user prompt.**
This usually looks like:
'new_feature': 'name_of_feature',
'detailed description': 'how to calculate it step-by-step',
'brief description': 'short summary of what it represents',
'relevant': ['list_of_input_columns']

**Do NOT include any extra text, explanations, greetings, or markdown formatting (like ```json) around your response.** 
Just output the required key-value pairs directly.""",
    reflect_on_tool_use=False, 
    model_client_stream=False, # Set to False to get the full response at once
)

# --- Function to Run the Autogen Agent (Synchronously) --- 
def run_autogen_feature_description(feature_prompt: str) -> str:
    """
    Runs the nl_feature_describer agent with the given prompt synchronously.

    Args:
        feature_prompt: The prompt string containing data description, task instructions,
                         and desired output format (usually from NLAgent).

    Returns:
        The raw text response from the agent, intended for parsing by NLAgent.
        Returns an empty string if the agent fails or returns no content.
    """
    try:
        # Initiate a synchronous chat with the agent.
        # Use the standard initiate_chat method.
        chat_result = nl_feature_describer.initiate_chat(
            recipient=nl_feature_describer, # Chat with itself effectively
            message=feature_prompt,
            max_turns=1 # Expecting just one response from the agent
        )

        # Extract the last message content
        if chat_result and chat_result.chat_history and len(chat_result.chat_history) > 0:
            last_message = chat_result.chat_history[-1]
            content = last_message.get('content', '')
            # Simple cleaning: remove potential ```json fences if the agent adds them despite instructions
            content = re.sub(r'^```(json|\s)*', '', content, flags=re.IGNORECASE).strip()
            content = re.sub(r'```$', '', content).strip()
            return content
        else:
            print("Warning: Autogen chat did not produce a result or history.")
            return "" # Return empty string on failure

    except Exception as e:
        print(f"Error running Autogen feature description agent: {e}")
        return "" # Return empty string on exception

# --- Example Usage (for testing this script directly) --- 
def main() -> None: # Changed to synchronous main
    # Example prompt similar to what NLAgent might generate
    example_prompt = """/* Data description: 
Column 'age': (int64) ... 
Column 'salary': (float64) ...
 */
In this task, you should generate a meaningful new feature for predicting 'target_variable' using open-world knowledge and the attribute set.
The downstream gpt-4 machine learning model will be trained on the new feature you generate.

Output format:
'new_feature': the name of the new feature.
'detailed description': a description of the new feature.
'brief description': a brief description of the new feature.
'relevant': a list of relevant columns used to extract the feature (excluding attribute target_variable).
except the four lines above, do not generate other useless msg.
notice: do not generate the same feature we have generated before !!!
"""
    print("--- Running Autogen Feature Describer --- ")
    description = run_autogen_feature_description(example_prompt)
    print("\n--- Generated Feature Description --- ")
    print(description)
    print("-------------------------------------")

    # Close the client if needed (depends on how the client handles connections)
    # await openai_client.close() # Cannot await in sync function

if __name__ == "__main__":
    # main() # Run the synchronous main directly
    pass