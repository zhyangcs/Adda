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
# Assuming LLMDAGNODE is importable or defined elsewhere
# from ...llm_dag_node import LLMDAGNODE # Adjust path if necessary
from typing import Type # Use Type for hinting if direct import is problematic

# --- Configuration (Consider moving to a config file or environment variables) ---
# Replace with your actual API key and base URL if needed
# It's recommended to load these from environment variables for security.
API_KEY = 'sk-iRsNsrqqhBlIGWrvZ3QNIoUWoUI8keRQnf4RtPGhXOJm5ITR' # Placeholder - Use environment variables
BASE_URL = 'https://api.nuwaapi.com/v1' # Placeholder
MODEL = 'gpt-4o' # Or your preferred model

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
        client_coder = OpenAIChatCompletionClient(model=MODEL, base_url=BASE_URL, api_key=API_KEY)
        client_validator = OpenAIChatCompletionClient(model=MODEL, base_url=BASE_URL, api_key=API_KEY)
    except Exception as e:
        print(termcolor.colored(f"[Autogen Code Gen] Error initializing LLM clients: {e}", "red"))
        return None, False

    # Construct the prompt for the Code Proposer
    input_cols = ', '.join(list(node.read_set)) if node.read_set else 'N/A'
    output_cols = ', '.join(list(node.write_set)) if node.write_set else 'N/A'
    op_desc = node.operation_desc[0] if node.operation_desc else "Generate feature based on inputs." # Use first desc
    col_details = "\n".join([f"- {k}: {v.strip()}" for k, v in node.column_info.items() if k in node.read_set])

    code_proposer_prompt = f"""You are a Senior Python Data Scientist specializing in feature engineering code generation using Pandas and NumPy.

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
    *   The code should take columns from `df` specified in 'Input Columns Used' and generate the 'Output Column(s)'.
    *   Assign the result to `df['{output_cols}']` (or multiple columns if specified).
    *   Handle potential division by zero or log of non-positive numbers by adding small constants (e.g., `1e-9` or `1`).
    *   Handle potential missing values (NaN) appropriately (e.g., using `.fillna()` or operations that inherently handle NaNs). You can fill with 0, mean, median, or mode if it makes sense, or leave NaNs if the operation supports them. State your assumption if filling.
    *   Ensure the generated code is **self-contained** and operates directly on the `df` DataFrame. Do **NOT** include function definitions (`def ...:`), imports, or example usage. Only provide the core operational code.
3.  **Format Output**: Present **ONLY** the generated Python code block. Do **NOT** include any explanations, comments (unless essential for complex logic), or markdown formatting like ```python ... ```.

**Example Code Snippet (Do NOT copy directly, adapt to the task):**
```python
# Example 1: Simple Ratio
df['new_feature_ratio'] = df['col_a'] / (df['col_b'] + 1e-9)

# Example 2: Interaction with fillna
df['interaction_feature'] = df['col_c'].fillna(0) * df['col_d'].fillna(df['col_d'].median())

# Example 3: Log transform
df['log_feature'] = np.log(df['col_e'] + 1)
```

**Constraint Checklist & Confidence Score**:
Before finalizing, review your generated code against these criteria:
*   [ ] Code operates on a DataFrame named `df`.
*   [ ] Uses specified input columns: {input_cols}.
*   [ ] Creates specified output column(s): {output_cols}.
*   [ ] Handles potential NaNs appropriately.
*   [ ] Handles potential division by zero / invalid math operations.
*   [ ] Code is self-contained (no functions, imports).
*   [ ] Output contains ONLY the code block.

Confidence Score [1-5]: [Your Score]

Now, generate the Python code based on the task details provided above."""


    code_proposer = AssistantAgent(
        name="CodeProposer",
        model_client=client_coder,
        system_message=code_proposer_prompt,
        reflect_on_tool_use=False,
        model_client_stream=False,
    )

    # Code Validator Agent
    code_validator = AssistantAgent(
        name="CodeValidator",
        model_client=client_validator,
        system_message=f"""You are a meticulous Code Reviewer specializing in Pandas feature engineering code snippets.

**Your Task**: Review the Python code snippet provided by the CodeProposer. The code aims to create the feature(s) '{output_cols}' using input columns '{input_cols}' based on the description: "{op_desc}". The code operates on a pandas DataFrame named `df`.

**Review Criteria**:
1.  **Correctness**: Does the code accurately implement the logic described in "{op_desc}"?
2.  **Syntax**: Is the Python syntax valid?
3.  **Pandas Usage**:
    *   Does it correctly use Pandas operations?
    *   Does it reference the DataFrame `df` correctly?
    *   Does it assign the result to the specified output column(s) (`{output_cols}`)?
    *   Does it attempt dangerous inplace operations without assignment (e.g., `df.fillna(..., inplace=True)`)? Prefer non-inplace (`df['col'] = df['col'].fillna(...)`).
4.  **Error Handling**: Does the code seem robust against potential errors like division by zero, log of non-positive numbers, or unexpected NaNs? (Check for added constants or appropriate handling).
5.  **Self-Contained**: Does the code snippet avoid defining functions (`def...`) or including imports? It should be just the operational code.
6.  **Format**: Does the message contain ONLY the code, without ```python markers or extra text? (Minor surrounding text is okay, but the core should be code).

**Interaction Strategy & Output Format**:
*   **Analyze**: Carefully review the provided code snippet against the criteria.
*   **Provide Feedback**:
    *   If the code meets **all** criteria and seems correct and robust, respond **ONLY** with `APPROVE`.
    *   If the code has issues (syntax errors, logical flaws, incorrect Pandas usage, missing error handling, forbidden elements like `def` or `import`, includes ```python markers), respond **ONLY** with `REJECT` followed by:
        *   A **brief** (1-2 sentences) explanation of the main issue(s).
        *   **Specific, actionable suggestions** for fixing the code. Example: "REJECT The code divides without handling potential zeros. Suggest adding a small constant to the denominator: `df['col_b'] + 1e-9`." or "REJECT Code includes an import statement. Remove the `import pandas as pd` line." or "REJECT Code uses inplace fillna. Change to `df['output_col'] = df['input_col'].fillna(0)`." or "REJECT Code block is missing or wrapped in markdown ```python. Provide only the raw code."
*   **Conciseness**: Keep feedback brief and focused. The goal is to guide the Proposer to generate a valid, runnable snippet.

**Example Rejection Response:**
REJECT Division by zero is not handled. Add a small epsilon to the denominator like `df['col_b'] + 1e-9`. Ensure the output column name is correct.
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
