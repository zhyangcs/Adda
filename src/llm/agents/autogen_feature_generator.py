import asyncio
import re
import termcolor
import src.env # Import env
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import CancellationToken
import traceback

# --- Configuration (Consider moving to a config file or environment variables) ---
# Replace with your actual API key and base URL if needed
# It's recommended to load these from environment variables or a dedicated config.
# We will use src.env now.
MODEL = 'gpt-4o' # Or your preferred model, could also be in src.env

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
        client1 = OpenAIChatCompletionClient(model=MODEL, base_url=src.env.openai_base_url, api_key=src.env.openai_api_key)
        client2 = OpenAIChatCompletionClient(model=MODEL, base_url=src.env.openai_base_url, api_key=src.env.openai_api_key)
    except Exception as e:
        print(termcolor.colored(f"[Autogen] Error initializing LLM clients: {e}", "red"))
        return []

    # Pre-extract target column to avoid backslash issue in f-string
    try:
        target_column = prompt.split('Target column: ')[1].split('\n')[0] if 'Target column: ' in prompt else 'N/A'
    except IndexError:
        target_column = 'N/A' # Handle cases where split might fail unexpectedly

    # --- Updated Feature Proposer Prompt (Simplified + Enhanced Guidance) ---
    feature_proposer_original_system_message = f'''You are a **Principal Feature Engineering Specialist**.
Your goal is to engineer **{{n}} impactful and diverse features** based on the provided data description, statistical summary, and global plan to maximize downstream ML model performance ({target_column} is the target variable).

**Input Context Sections**:
1.  `/* Data description... */`: Basic column info.
2.  `/* Advanced Statistics Summary... */`: Insights from the CURRENT data sample (Correlation, PCA, MI, Importance, Clustering).
3.  `/* Overall Feature Strategy/Plan... */`: High-level guidance generated at the start.

**Key Requirements & Process**:

1.  **Analysis**: Interpret ALL input context sections.
2.  **Leverage Statistical Insights & Global Plan (CRITICAL!)**:
    *   Use the **Statistical Summary** for detailed tactical decisions (e.g., how to handle specific correlations).
    *   Use the **Global Plan** for strategic direction (e.g., prioritizing certain feature types).
    *   **DO NOT** propose features that re-run analyses (PCA, K-Means, etc.).
3.  **Thinking Process & Planning**: Document in `<thinking>...</thinking>`:
    *   **Start with Your Plan**: Briefly outline your 2-3 step plan for this round, explicitly stating how it aligns with or refines the **Global Plan** based on the **current Statistical Summary**. (e.g., "Global plan suggests interactions. Current stats show high MI for X. Plan: 1. Create interactions with X. 2. Address high corr(Y, Z). 3. Advanced feature.").
    *   **Hypothesis Generation**: Link hypotheses to *both* the Global Plan and the Statistical Summary where applicable.
    *   **Justify "Why"**: Justify *each* feature, referencing supporting evidence from the Global Plan AND/OR relevant sections of the Statistical Summary ([Correlation Insights], [PCA Insights], etc.).
    *   **Advanced & Multi-Step Features**: Aim for these if justified by analysis and plan.
4.  **Output Format (Strict!)**: AFTER `</thinking>`, provide **ONLY** the {{n}} feature blocks in the required format. NO markdown code blocks.

    **Required Feature Block Format (Pay EXTREME attention to separators!)**:
    'new_feature': ['feature_name']
    'detailed description': 'Rationale [referencing Global Plan item #... and/or Stats Summary e.g., "[MI] score for X"]... Calculation: [Inline LaTeX Formula]'
    'brief description': 'A short summary...'
    'relevant': ['col_a', 'col_b', ...]

    **CRITICAL**: Each feature block **MUST** be separated from the next by **exactly ONE newline character** followed immediately by `'new_feature'`.
    Example (Correct Separation):
    ```
    'new_feature': ['feat1']
    'detailed description': '...'
    'brief description': '...'
    'relevant': ['a']
    'new_feature': ['feat2']
    'detailed description': '...'
    'brief description': '...'
    'relevant': ['b']
    ```
    **DO NOT** add extra empty lines or whitespace between blocks.

 Now, generate the thinking process (incorporating the global plan) and the {{n}} strictly formatted feature blocks.
 '''

    # Use the updated prompt directly
    proposer_system_message = feature_proposer_original_system_message

    # --- Create Agents --- (Ensure the correct system message is used)
    feature_proposer = AssistantAgent(
        name="FeatureProposer",
        model_client=client1,
        system_message=proposer_system_message,
        reflect_on_tool_use=False,
        model_client_stream=False,
    )

    # FeatureExpert now acts as an Adaptive Domain Expert
    # --- Updated Feature Expert Prompt ---
    feature_expert_system_message = f"""You are an **Adaptive Domain Expert** focused on guiding feature generation within a specific domain.

**Your Process**:
1.  **Identify Domain & Adopt Persona**: Analyze the prompt (including data description), identify the relevant domain, and adopt the persona of an expert in that field. State your thinking process within `<expert_thinking>`.
2.  **Domain Brainstorming**: Within `<expert_thinking>`, brainstorm concepts and potential features relevant *specifically* to the identified domain.
3.  **Evaluate Proposals**: Assess proposed features based on:
    *   **Domain Relevance**: Is the feature meaningful and logical within the context of the domain?
    *   **Format Compliance**: Does the proposal adhere strictly to the required output format?
4.  **Synthesize & Provide Feedback**: Combine domain evaluation and format check results.

**Interaction Strategy & Output Format**:
*   **Thinking Output**: Start your response **ONLY** with `<expert_thinking>...</expert_thinking>`. Include your assumed persona and domain-specific reasoning.
*   **Feedback Output**: Immediately follow `</expert_thinking>` with the evaluation verdict:
    *   **If proposals are domain-relevant AND correctly formatted**: Respond **ONLY** with `APPROVE`.
    *   **Otherwise (Default)**: Respond **ONLY** with `REJECT` followed by **constructive, actionable feedback**:
        *   **Specific Critique (1-2 sentences max)**: Clearly state the *main reason* for rejection, focusing on domain logic flaws or format errors (e.g., "From an automotive perspective, combining 'tire_pressure' and 'engine_temp' this way lacks physical meaning.", "Format Error: 'new_feature' list is missing quotes.").
        *   **Actionable Suggestion (Crucial!)**: Provide **concrete suggestions for improvement based on domain knowledge or format correction**. Examples:
            *   "Consider calculating the 'load_factor' based on 'weight' and 'capacity' which is standard in logistics."
            *   "Ensure all elements in the 'relevant' list are enclosed in single or double quotes."
            *   "From a [Domain] perspective, a better way to capture [Concept] would be [Alternative Formula/Columns] because [Domain Reason]."
*   **Goal**: Your feedback should guide the Proposer towards domain-appropriate and correctly formatted features.
*   **Conciseness**: Keep feedback brief but actionable.
*   **Format Focus**: Prioritize format correctness. Reject if the format is incorrect, even if the content seems promising.

**Example Constructive Rejection (Domain Focus):**
<expert_thinking>
Domain: E-commerce. Persona: Retail Analyst. The proposal tries to combine 'click_rate' and 'purchase_frequency'. While related, a simple sum isn't meaningful for predicting customer lifetime value.
</expert_thinking>
REJECT Combining 'click_rate' and 'purchase_frequency' directly doesn't capture user behavior well. Consider a ratio like 'purchase_frequency / click_rate' (handling division by zero) or interaction terms with 'time_on_site'.

**Example Constructive Rejection (Format Focus):**
<expert_thinking>
Domain: Healthcare. Persona: Medical Data Analyst. Proposal looks reasonable conceptually. Checking format...
</expert_thinking>
REJECT Format Error: The 'detailed description' value must be a single string enclosed in quotes, not a list.
"""

    feature_expert = AssistantAgent(
        name="FeatureExpert",
        model_client=client2,
        system_message=feature_expert_system_message,
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
    retries = 5 # Allow for retries if formatting fails
    for attempt in range(retries):
        try:
            # Use the full prompt from nl_agent as the task
            final_result: TaskResult = await team.run(task=prompt) # Corrected call

            # Check based on termination condition and messages, not status
            if final_result and final_result.messages and "APPROVE" in final_result.messages[-1].content:
                proposer_message = final_result.messages[-2].content # Validator is last, proposer before that

                # Extract individual feature blocks
                # This regex assumes each feature block starts with 'new_feature'
                # and captures everything until the next 'new_feature' (allowing for variable whitespace/newlines)
                # or end of string.
                # It relies heavily on the Proposer agent following instructions.
                feature_blocks = re.findall(r"('new_feature'.*?)(?=\s*\n+\s*'new_feature'|\Z)", proposer_message, re.DOTALL)

                # Relax condition: accept if at least one block is found
                if len(feature_blocks) > 0:
                    generated_features = [block.strip() for block in feature_blocks]
                    print(termcolor.colored(f"[Autogen] Successfully extracted {len(generated_features)} features (requested {n}).", "green"))
                    break # Success
                else:
                    print(termcolor.colored(f"[Autogen] Warning: Could not extract any feature blocks (requested {n}). Content:\n{proposer_message}", "yellow"))
                    # Continue to retry if possible

            else:
                # Log failure without using .status
                stop_reason = getattr(final_result, 'stop_reason', 'Unknown') # Safely get stop_reason
                last_message_content = final_result.messages[-1].content if final_result and final_result.messages else 'N/A'
                print(termcolor.colored(f"[Autogen] Attempt {attempt+1} failed. Stop reason: {stop_reason}. Last message: {last_message_content}", "yellow"))
                # Let it retry

        except Exception as e:
            print(termcolor.colored(f"[Autogen] Error during Autogen run (Attempt {attempt+1}): {e}", "red"))
            traceback.print_exc()
            # Let it retry

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