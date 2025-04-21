import asyncio
import re
import termcolor
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import CancellationToken

# --- Configuration (Consider moving to a config file or environment variables) ---
# Replace with your actual API key and base URL if needed
# It's recommended to load these from environment variables for security.
API_KEY = 'sk-G1u7gDgwUgvcwGpAeQ7vhRm2chKRhsj7lvTPlyFze6ZHyxD3' # Placeholder - Use environment variables
BASE_URL = 'https://api.nuwaapi.com/v1' # Placeholder
MODEL = 'gpt-4o' # Or your preferred model

# It's good practice to reuse clients if possible, but creating new ones per call is simpler for now.
# For better performance/resource management, consider initializing clients once outside this function.

# --- Autogen Agent Definitions ---

async def generate_features_autogen(prompt: str, n: int) -> list[str]:
    """
    Generates feature suggestions using an Autogen team.

    Args:
        prompt: The detailed prompt containing data description, target, etc.
        n: The desired number of feature suggestions.

    Returns:
        A list of strings, where each string is a potential feature description
        formatted for parse_nl_comma. Returns empty list on failure.
    """
    print(termcolor.colored(f"[Autogen] Generating {n} feature suggestions...", "blue"))

    # Initialize clients for this run
    # Using separate clients as in the demo, though one might suffice
    try:
        client1 = OpenAIChatCompletionClient(model=MODEL, base_url=BASE_URL, api_key=API_KEY)
        client2 = OpenAIChatCompletionClient(model=MODEL, base_url=BASE_URL, api_key=API_KEY)
    except Exception as e:
        print(termcolor.colored(f"[Autogen] Error initializing LLM clients: {e}", "red"))
        return []

    # Pre-extract target column to avoid backslash issue in f-string
    try:
        target_column = prompt.split('Target column: ')[1].split('\n')[0] if 'Target column: ' in prompt else 'N/A'
    except IndexError:
        target_column = 'N/A' # Handle cases where split might fail unexpectedly

    feature_proposer = AssistantAgent(
        name="FeatureProposer",
        model_client=client1,
        system_message=f'''You are a Feature Engineer. Your goal is to propose new features based on the provided context.

Follow these steps:
1.  **Analyze**: Carefully read the data description (columns, types, statistics, samples), the target variable ({target_column}), and any existing features or memory provided in the prompt.
2.  **Think (CoT)**: Explicitly write down your thinking process within `<thinking>...</thinking>` tags. This MUST include:
    - Your analysis of the data and target variable.
    - Brainstorming potential new features (consider interactions, non-linear transformations, aggregations, encodings).
    - Your reasoning for why each brainstormed feature might be useful or relevant for the target.
    - The process and justification for selecting the final {n} features from your brainstormed list.
3.  **Format**: After the closing `</thinking>` tag, format EACH of the final {n} selected features STRICTLY as follows, with each field on a new line, enclosed in single quotes:
    'new_feature': ['feature_name']
    'detailed description': 'Detailed explanation of how the feature is derived and why it might be useful (reflecting your thinking process).'
    'brief description': 'A short summary or name for the feature.'
    'relevant': ['col_a', 'col_b', ...]

**Constraint Checklist & Confidence Score**: Not required for this task.

**Example Output Structure for n=1:**
<thinking>
*   **Analysis**: The data includes columns X (numeric, skewed) and Y (categorical). The target is Z (binary). Existing features: [W].
*   **Brainstorming**:
    *   Feature A: `log(X)` to handle skewness. Potentially useful for linear models.
    *   Feature B: Interaction `X * (Y=='category1')`. Might capture conditional effects.
    *   Feature C: One-hot encoding of Y. Standard practice for categorical features.
*   **Rationale & Selection**: Feature A seems directly useful given the skewness noted in X. Feature B is interesting but perhaps less general than encoding Y. Feature C (encoding) is standard but might be handled later. Selected Feature A for its direct relevance to data properties.
</thinking>
'new_feature': ['log_X']
'detailed description': 'Logarithmic transformation of column X (log(X)) to address skewness observed in the data description. This can help improve performance for models sensitive to feature distributions.'
'brief description': 'Log transform of X'
'relevant': ['X']

**Final Output Structure Requirements**:
1.  Start your entire response with the `<thinking>` tag.
2.  Provide your detailed thinking process inside the `<thinking>...</thinking>` tags.
3.  Immediately after the closing `</thinking>` tag, provide the {n} requested feature blocks formatted exactly as specified.
4.  There should be NO text or introductory/concluding remarks outside the `<thinking>` block and the subsequent feature blocks.
''',
        reflect_on_tool_use=False,
        model_client_stream=False, # Streaming might complicate result parsing
    )

    # Renamed validator to expert, focusing on quality and providing feedback.
    feature_expert = AssistantAgent(
        name="FeatureExpert",
        model_client=client2,
        system_message=f"""You are a Senior Data Scientist acting as a Feature Expert.
Evaluate the feature proposals provided by the FeatureProposer based on the original prompt's context (data description, target variable).

**Primary Goal**: Assess the **quality, relevance, novelty, and potential value** of the proposed features for the task.

**Evaluation Criteria**:
1.  **Relevance & Potential Impact**: Is the feature likely useful for the target? Is the rationale sound?
2.  **Novelty**: Is it genuinely new or trivial?
3.  **Correctness (Conceptual)**: Is the idea sensible and derivable?
4.  **Clarity**: Is the description understandable?

**Interaction Strategy**:
*   **Focus on Substance**: Prioritize the *ideas* behind the features over strict adherence to the proposer's output format. Only REJECT based on format if it's completely unintelligible.
*   **Constructive Feedback (Max 2 Rounds)**: If features are weak/problematic, provide specific, actionable feedback to guide improvement. Aim to give detailed feedback for **at most two rounds** of interaction.
*   **Lower Bar After Feedback**: After providing feedback once or twice, if the proposer has made reasonable attempts to address your points, **lower your standards for approval**. Approve the features if they are minimally viable or show improvement, even if not perfect.

**Your Response**:
-   **First/Second Review**: If ALL {n} features are high quality, respond ONLY with 'APPROVE'. If ANY are problematic, respond with 'REJECT' and provide detailed constructive feedback as described above.
-   **Third Review (or later)**: If you have already provided feedback in previous rounds, critically assess if the proposer has incorporated the feedback reasonably. If yes, or if the features are now at least marginally useful, respond ONLY with 'APPROVE'. Otherwise, you can REJECT one last time with final concise feedback.
""",
        reflect_on_tool_use=False,
        model_client_stream=False,
    )

    # Terminate when the expert approves
    termination_condition = TextMentionTermination("APPROVE")

    team = RoundRobinGroupChat(
        [feature_proposer, feature_expert], # Use the new expert agent
        termination_condition=termination_condition
    )

    generated_features = []
    retries = 2 # Allow for retries if formatting fails
    for attempt in range(retries):
        try:
            # Use the full prompt from nl_agent as the task
            final_result: TaskResult = await team.run(task=prompt) # Corrected call

            # Check based on termination condition and messages, not status
            if final_result and final_result.messages and "APPROVE" in final_result.messages[-1].content:
                proposer_message = final_result.messages[-2].content # Validator is last, proposer before that

                # Extract individual feature blocks
                # This regex assumes each feature block starts with 'new_feature'
                # and captures everything until the next 'new_feature' or end of string.
                # It relies heavily on the Proposer agent following instructions.
                feature_blocks = re.findall(r"('new_feature'.*?)(?=\n'new_feature'|\Z)", proposer_message, re.DOTALL)

                if len(feature_blocks) == n:
                    generated_features = [block.strip() for block in feature_blocks]
                    print(termcolor.colored(f"[Autogen] Successfully generated {len(generated_features)} features.", "green"))
                    break # Success
                else:
                    print(termcolor.colored(f"[Autogen] Warning: Extracted {len(feature_blocks)} blocks, expected {n}. Content:\n{proposer_message}", "yellow"))
                    # Continue to retry if possible

            else:
                # Log failure without using .status
                stop_reason = getattr(final_result, 'stop_reason', 'Unknown') # Safely get stop_reason
                last_message_content = final_result.messages[-1].content if final_result and final_result.messages else 'N/A'
                print(termcolor.colored(f"[Autogen] Attempt {attempt+1} failed. Stop reason: {stop_reason}. Last message: {last_message_content}", "yellow"))
                # Let it retry

        except Exception as e:
            print(termcolor.colored(f"[Autogen] Error during Autogen run (Attempt {attempt+1}): {e}", "red"))
            # Let it retry

        # Reset team state for retry if needed (or create a new team instance)
        await team.reset() # Resetting might help clear bad states

    # --- Log the full conversation --- 
    if 'final_result' in locals() and final_result and final_result.messages:
        print(termcolor.colored("\n--- Autogen Conversation History ---", "cyan"))
        for msg in final_result.messages:
            source = getattr(msg, 'source', 'Unknown') # Get source agent name safely
            content = getattr(msg, 'content', '')
            print(termcolor.colored(f"[{source}]:", "yellow"))
            print(content)
        print(termcolor.colored("--- End Autogen Conversation History ---", "cyan"))

    # Close clients after use
    try:
        await client1.close()
        await client2.close()
    except Exception as e:
        print(termcolor.colored(f"[Autogen] Error closing LLM clients: {e}", "red"))


    if not generated_features:
         print(termcolor.colored(f"[Autogen] Failed to generate valid features after {retries} attempts.", "red"))

    return generated_features

# Example standalone test (optional)
async def _test():
    test_prompt = """
/* Data description:
Column 'age' (int64): NaN Frequency=0.0%, Skewness=0.5, Unique Values=50, Samples=[25, 47, 30, 52, 19]
Column 'salary' (float64): NaN Frequency=10.0%, Skewness=1.2, Unique Values=150, Samples=[50000.0, 60000.0, 45000.0, 75000.0, 52000.0]
Column 'department' (object): NaN Frequency=0.0%, Skewness=nan, Unique Values=5, Samples=['HR', 'Engineering', 'Sales', 'Engineering', 'Sales']
*/
Target column: 'salary'
Existing features: ['age', 'salary', 'department']
Propose new features based on this.
"""
    results = await generate_features_autogen(test_prompt, n=2)
    print("\n--- Autogen Results ---")
    if results:
        for i, res in enumerate(results):
            print(f"Feature {i+1}:\n{res}\n")
    else:
        print("No features generated.")
    print("-----------------------")

if __name__ == "__main__":
     # To run the test: python -m src.llm.agents.autogen_feature_generator
     # Ensure you are in the root directory ('autofe') or adjust path.
     # Note: Running asyncio directly might require adjustments based on your environment.
     # Consider using a dedicated test runner if needed.
     asyncio.run(_test()) # Commented out by default
     pass 