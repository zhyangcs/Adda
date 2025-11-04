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
# Assuming LLMDAGNODE is importable or defined elsewhere
# from ...llm_dag_node import LLMDAGNODE # Adjust path if necessary
from typing import Type # Use Type for hinting if direct import is problematic

# --- Configuration (Consider moving to a config file or environment variables) ---
# Recommend loading these from environment variables or a config file.
MODEL = src.env.default_model # Use default model from environment configuration

# Placeholder for LLMDAGNODE if not directly imported
# Used for type hinting only
LLMDAGNODE = Type['LLMDAGNODE_Placeholder']
class LLMDAGNODE_Placeholder: # Define a placeholder class
    node_id: int
    operation_desc: list[str]
    column_info: dict
    read_set: set[str]
    write_set: set[str]
    # Add other relevant attributes if needed by prompts

# --- Autogen Agent Definitions ---

async def generate_code_autogen(node: LLMDAGNODE) -> tuple[str | None, bool]:
    """
    Generates and validates Python code for feature engineering using an Autogen team.

    Args:
        node: An LLMDAGNODE instance containing the task description, input/output columns, etc.

    Returns:
        A tuple containing:
        - The generated and validated Python code string, or None if failed.
        - A boolean indicating success (True) or failure (False).
    """
    print(termcolor.colored(f"[Autogen Code Gen] Generating code for node {node.node_id}...", "blue"))

    # Initialize clients for this run
    try:
        client_coder = OpenAIChatCompletionClient(model=MODEL, base_url=src.env.openai_base_url, api_key=src.env.openai_api_key)
        client_validator = OpenAIChatCompletionClient(model=MODEL, base_url=src.env.openai_base_url, api_key=src.env.openai_api_key)
    except Exception as e:
        print(termcolor.colored(f"[Autogen Code Gen] Error initializing LLM clients: {e}", "red"))
        return None, False

    # Construct the prompt for the Code Proposer
    input_cols = ', '.join(list(node.read_set)) if node.read_set else 'N/A'
    output_cols = ', '.join(list(node.write_set)) if node.write_set else 'N/A'
    op_desc = node.operation_desc[0] if node.operation_desc else "Generate feature based on inputs." # Use first desc
    col_details = "\n".join([f"- {k}: {v.strip()}" for k, v in node.column_info.items() if k in node.read_set])

    # --- Updated Code Proposer Prompt ---
    code_proposer_prompt = f"""You are a Senior Python Data Scientist specializing in generating **pure, executable Python code snippets** for feature engineering using Pandas and NumPy.

**Task**: Generate Python code for a feature engineering step based on the provided description and data context.

**Input Data Context**:
The input pandas DataFrame is named `df`.
Relevant input columns and their descriptions:
{col_details if col_details else 'N/A'}

**Input Columns Used**: {input_cols}
**Output Column(s) to Generate**: {output_cols}
**Feature Description**: {op_desc}

**Instructions**:
1.  **Analyze**: Understand the feature description, input columns, and expected output column(s).
2.  **Generate Code**: Write clean, efficient, and correct Python code using **Pandas** and **NumPy** operations on the DataFrame `df`.
    *   The code must operate directly on the `df` DataFrame.
    *   Assign the result to `df['{output_cols}']` (or multiple columns if specified).
    *   Handle potential division by zero or log of non-positive numbers appropriately (e.g., add `1e-9` or `1`).
    *   Handle potential missing values (NaN) appropriately (e.g., using `.fillna()` before the operation if needed). State necessary assumptions if filling NaNs.
    *   Ensure the generated code is **self-contained operational code ONLY**. Do **NOT** include function definitions (`def ...:`), imports (`import ...`), example usage, or any surrounding text or explanation. Standard Python comments (`# ...`) are acceptable if necessary for clarity.
3.  **Format Output (CRITICAL!)**:
    *   Your entire response **MUST** consist **ONLY** of the raw Python code snippet.
    *   **ABSOLUTELY NO** introductory phrases (like "Here is the code:"), concluding remarks, or markdown formatting (like ```python ... ```) are allowed.
    *   The first line of your response must be the first line of the code, and the last line must be the last line of the code.

**Example of CORRECT Output Format:**
```python
# Calculate feature A
df['feature_A'] = df['input_col1'] / (df['input_col2'].fillna(0) + 1e-9)
# Calculate feature B based on A
df['feature_B'] = np.log(df['feature_A'] + 1)
```

**Example of INCORRECT Output Format:**
```text
Here is the Python code you requested:
```python
df['feature_A'] = df['input_col1'] / (df['input_col2'].fillna(0) + 1e-9)
```
This code calculates feature A.
```

Now, generate the **pure Python code snippet** based on the task details provided above.
"""

    code_proposer = AssistantAgent(
        name="CodeProposer",
        model_client=client_coder,
        system_message=code_proposer_prompt, # Use updated prompt
        reflect_on_tool_use=False,
        model_client_stream=False,
    )

    # --- Updated Code Validator Prompt ---
    code_validator = AssistantAgent(
        name="CodeValidator",
        model_client=client_validator,
        system_message=f"""You are a **hyper-vigilant** Code Reviewer specializing in Pandas feature engineering code snippets. You must enforce strict formatting rules.

**Your Task**: Review the Python code snippet provided by the CodeProposer. The code aims to create the feature(s) '{output_cols}' using input columns '{input_cols}' based on the description: "{op_desc}". It must operate on a pandas DataFrame named `df`.

**Review Criteria (All MUST Pass for APPROVE)**:
1.  **Correctness**: Does the code accurately implement the logic described in "{op_desc}"?
2.  **Syntax**: Is the Python syntax valid?
3.  **Pandas Usage**: Correct Pandas/NumPy operations? Correct `df` reference? Correct output assignment to `{output_cols}`? No unsafe inplace operations?
4.  **Error Handling**: Robust against division by zero, invalid math ops, NaNs?
5.  **Self-Contained**: Avoids `def`, `import`, example usage?
6.  **Format (Strict Check!)**:
    *   Does the *entire* message consist **ONLY** of raw Python code (standard Python comments `#...` are allowed)?
    *   Are there **NO** surrounding text, explanations, greetings, sign-offs?
    *   Are there **NO** markdown markers like ```python or ```?

**Interaction Strategy & Output Format**:
*   **Analyze**: Carefully review the snippet against ALL criteria, paying special attention to the **Format** (Criterion 6).
*   **Provide Feedback**:
    *   If **ALL** criteria are met, respond **ONLY** with `APPROVE`.
    *   If **ANY** criterion fails (especially Format!), respond **ONLY** with `REJECT` followed by:
        *   A **brief** explanation focusing on the **most critical** issue(s).
        *   **Specific, actionable suggestions** for fixing.
    *   **Format Rejection Examples**:
        *   "REJECT Response includes introductory text before the code. Remove 'Here is the code:'."
        *   "REJECT Response uses markdown code fences (```python). Remove the fences."
        *   "REJECT Response includes explanatory text after the code. Remove all text following the last line of code."
*   **Conciseness**: Keep feedback brief.

**Example Rejection (Format Issue):**
REJECT Response includes markdown code fences. Remove the ```python and ``` markers.
""",
        reflect_on_tool_use=False,
        model_client_stream=False,
    )

    # Terminate when the validator approves
    termination_condition = TextMentionTermination("APPROVE")

    team = RoundRobinGroupChat(
        [code_proposer, code_validator],
        termination_condition=termination_condition
    )

    generated_code: str | None = None
    autogen_success: bool = False
    retries = 2 # Allow for retries

    # Construct the initial task message for the team
    task_prompt = f"""Generate Python code for node {node.node_id}.
Input Columns: {input_cols}
Output Column(s): {output_cols}
Description: {op_desc}
Column Details:
{col_details if col_details else 'N/A'}"""

    for attempt in range(retries):
        try:
            final_result: TaskResult = await team.run(task=task_prompt) # Limit turns

            # Check if terminated by APPROVE and messages exist
            if final_result and final_result.messages and "APPROVE" in final_result.messages[-1].content:
                # Validator is last, proposer is second to last
                proposer_message = final_result.messages[-2].content

                # --- Code Extraction Logic ---
                # Try to extract code block, robustly handling optional markdown
                code_match = re.search(r"```python\s*([\s\S]+?)\s*```", proposer_message)
                if code_match:
                    extracted_code = code_match.group(1).strip()
                    print(termcolor.colored(f"[Autogen Code Gen] Extracted code using markdown pattern.", "cyan"))
                else:
                    # If no markdown, assume the whole message (after filtering instructions) is code
                    print(termcolor.colored(f"[Autogen Code Gen] No markdown found, attempting fallback extraction.", "yellow"))
                    full_message = proposer_message.strip()
                    # Filter out known instruction lines more robustly
                    lines = full_message.split('\\n')
                    potential_code_lines = [
                        line for line in lines
                        if not line.strip().startswith("Confidence Score") and
                           not line.strip().startswith("*   [ ]") and
                           not line.strip().startswith("Constraint Checklist") and
                           line.strip() # Keep non-empty lines
                    ]
                    extracted_code = "\\n".join(potential_code_lines).strip()

                    # Add a basic check: if it's empty or just 'APPROVE' etc., it's likely not code.
                    if not extracted_code or extracted_code.upper() in ["APPROVE", "REJECT"]:
                         print(termcolor.colored(f"[Autogen Code Gen] Fallback extraction resulted in empty or non-code content. Proposer message was:\\n{proposer_message}", "red"))
                         extracted_code = None # Indicate failure to extract valid code
                    elif extracted_code == proposer_message.strip():
                         print(termcolor.colored(f"[Autogen Code Gen] Extracted code using fallback (filtered message).", "cyan"))
                    else:
                         print(termcolor.colored(f"[Autogen Code Gen] Extracted code using fallback (entire message).", "cyan"))


                if extracted_code:
                    generated_code = extracted_code
                    autogen_success = True
                    print(termcolor.colored(f"[Autogen Code Gen] Successfully generated and validated code for node {node.node_id}.", "green"))
                    # print(termcolor.colored(f"--- Generated Code ---\n{generated_code}\n---------------------", "green"))
                    break # Success
                else:
                    print(termcolor.colored(f"[Autogen Code Gen] Warning: Could not extract code from proposer message on attempt {attempt+1}. Content:\n{proposer_message}", "yellow"))
                    # Continue to retry if possible

            else:
                # Log failure reason
                stop_reason = getattr(final_result, 'stop_reason', 'Unknown')
                last_message_content = final_result.messages[-1].content if final_result and final_result.messages else 'N/A'
                print(termcolor.colored(f"[Autogen Code Gen] Attempt {attempt+1} failed. Stop reason: {stop_reason}. Last message: {last_message_content}", "yellow"))
                # Let it retry

        except Exception as e:
            print(termcolor.colored(f"[Autogen Code Gen] Error during Autogen run (Attempt {attempt+1}): {e}", "red"))
            import traceback
            traceback.print_exc()
            # Let it retry

        # Reset team state for retry
        await team.reset()

    # --- Log the full conversation ---
    if 'final_result' in locals() and final_result and final_result.messages:
        print(termcolor.colored("\n--- Autogen Code Gen Conversation History ---", "cyan"))
        for msg in final_result.messages:
             # Use agent name directly if available
             source = getattr(msg, 'name', getattr(msg, 'source', 'Unknown')) # Prefer 'name' attribute
             content = getattr(msg, 'content', '')
             print(termcolor.colored(f"[{source}]:", "yellow"))
             print(content)
        print(termcolor.colored("--- End Autogen Code Gen Conversation History ---", "cyan"))


    # Close clients after use
    try:
        await client_coder.close()
        await client_validator.close()
    except Exception as e:
        print(termcolor.colored(f"[Autogen Code Gen] Error closing LLM clients: {e}", "red"))

    if not autogen_success:
         print(termcolor.colored(f"[Autogen Code Gen] Failed to generate valid code for node {node.node_id} after {retries} attempts.", "red"))

    return generated_code, autogen_success

# Example standalone test (optional - requires defining a mock LLMDAGNODE)
async def _test():
    class MockLLMDAGNODE:
        def __init__(self):
            self.node_id = 998 # Changed ID for clarity
            # More complex description likely leading to multi-line code
            self.operation_desc = [
                "Calculate a weighted risk score: "
                "If 'age' > 50, score = (log('bmi' + 1) * 2) + ('sysbp' / 100). "
                "Otherwise, score = (log('bmi' + 1) * 1) + ('sysbp' / 120). "
                "Handle potential NaNs in 'bmi' and 'sysbp' by filling with their respective means."
            ]
            self.column_info = {
                "age": "Column 'age' (int64): Age of patient.",
                "bmi": "Column 'bmi' (float64): Body mass index, may contain NaNs.",
                "sysbp": "Column 'sysbp' (float64): Systolic blood pressure, may contain NaNs."
            }
            self.read_set = {"age", "bmi", "sysbp"}
            self.write_set = {"risk_score_weighted"} # Changed output name

    test_node = MockLLMDAGNODE()
    # We expect generate_code_autogen to handle extraction correctly now,
    # regardless of whether the LLM uses markdown fences or not.
    code, success = await generate_code_autogen(test_node)

    print("\n--- Autogen Code Gen Test Results ---")
    if success and code:
        print(f"Success: True")
        print(f"Generated Code:\n{code}")
        # Simple check for multi-line structure (adjust as needed)
        if '\n' in code:
            print(termcolor.colored("Test Info: Generated code appears multi-line.", "blue"))
        else:
            print(termcolor.colored("Test Info: Generated code appears single-line.", "blue"))
    else:
        print(f"Success: False")
        print(f"Generated Code: {code}")
    print("-------------------------------------")

if __name__ == "__main__":
     # To run the test: python -m src.llm.agents.autogen_code_generator
     # Ensure you are in the root directory ('autofe') or adjust path.
     # Note: Running asyncio directly might require adjustments based on your environment.
     # Ensure API keys/endpoints are correctly configured.
     asyncio.run(_test()) # Commented out by default
     pass
