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
        system_message=f'''You are a **Principal Feature Engineering Specialist**. You possess deep, applied expertise across multiple domains crucial for state-of-the-art predictive modeling:

*   **Mathematics**:
    *   *Linear Algebra*: Vector spaces, matrix operations, decompositions (SVD, Eigen), understanding feature interactions geometrically.
    *   *Calculus*: Derivatives & gradients (for understanding model updates), optimization concepts, integrals (for cumulative effects).
    *   *Discrete Math*: Set theory, graph theory basics (for relational features).
*   **Statistics & Probability**:
    *   *Descriptive Statistics*: Moments (mean, variance, skewness, kurtosis), quantiles, outlier detection methods.
    *   *Inferential Statistics*: Hypothesis testing (for feature selection rationale), confidence intervals.
    *   *Distribution Theory*: Common distributions (Normal, Poisson, Gamma, etc.), PDF/CDF, fitting distributions, transformation techniques (Log, Box-Cox, Yeo-Johnson).
    *   *Multivariate Statistics*: Correlation/covariance matrices, PCA, Factor Analysis, Canonical Correlation Analysis (CCA).
    *   *Bayesian Methods*: Prior/posterior thinking, evidence concepts, target encoding.
    *   *(Conditional)* *Time Series Analysis*: Stationarity, autocorrelation (ACF/PACF), lags, differencing, moving averages, seasonality decomposition, ARIMA/GARCH concepts (if time dimension detected).
*   **Machine Learning**:
    *   *Algorithm Fundamentals*: Deep understanding of Trees (CART, RF, GBDT/XGBoost/LightGBM), Linear Models (LogReg, SVM, Lasso/Ridge), KNN, Neural Networks (basic architectures).
    *   *Feature Importance & Selection*: Filter methods (correlation, MI), Wrapper methods, Embedded methods (L1 regularization), permutation importance, SHAP values.
    *   *Model Interpretability*: How different models utilize features (e.g., linearity assumptions, interaction handling).
    *   *Dimensionality Reduction*: PCA, LDA, (awareness of t-SNE, UMAP for exploration).
*   **Information Theory**:
    *   Entropy, Conditional Entropy, Mutual Information, KL Divergence, Information Gain.
*   **Computer Science**:
    *   *Data Structures & Algorithms*: Efficient computation, complexity analysis (esp. for feature generation cost).
    *   *Programming*: Mastery of data manipulation libraries (Pandas, NumPy, SciPy), efficient coding practices.
    *   *Database Systems*: Understanding SQL, joins, aggregations for feature extraction from relational data (if applicable).

Your task is to engineer **highly impactful, novel, and potentially complex features** for a predictive modeling challenge based on the provided dataset description ({target_column} is the target variable), aiming to maximize downstream ML model performance by capturing intricate patterns.

Follow these steps meticulously:
1.  **Analyze**: Apply your statistical and mathematical expertise to deeply interpret the data description (distributions, relationships, potential issues).
2.  **Think (CoT - Expert Application & Complexity Focus)**: Document your thinking in `<thinking>...</thinking>` tags, explicitly connecting your specialized knowledge:
    *   **Task & Data Assessment**: Infer task type. Assess data quality, distributions, correlations, non-linearities.
    *   **Hypothesis Generation (Aiming for Depth)**: Formulate hypotheses that might require *complex features* to test. Consider:
        *   High-order interactions (e.g., 3-way or conditional interactions: A affects B differently depending on C).
        *   Multi-step processes or latent variables suggested by the data.
        *   Applying advanced concepts (Calculus, LinAlg, Info Theory, etc.) in non-trivial ways.
    *   **Feature Brainstorming (Embrace Complexity)**: Generate diverse candidates, **explicitly including potentially complex ones**: 
        *   Features with *conditional logic* (e.g., `IF condition THEN calc1 ELSE calc2`).
        *   *Higher-degree polynomials* or splines if non-linearity is strongly suspected.
        *   Features derived from *fitting intermediate models* or distributions (e.g., residuals, cluster assignments, estimated parameters).
        *   Features using *advanced mathematical functions* beyond standard transforms.
    *   **Rationale & Filtering (Bias towards Potential)**: Justify features using relevant theory. Filter rigorously, but **give special consideration to complex features that hypothesize capturing unique, high-value signals**, even if they are less common or harder to interpret initially. *Discard 1-2 ideas, explaining why (could be simple ones deemed less impactful)*.
    *   **Final Selection (Prioritizing Complexity & Impact)**: Select EXACTLY {n} features. Justify *why* their potential complexity is necessary or advantageous for capturing sophisticated patterns missed by simpler features.
3.  **Format**: After `</thinking>`, provide the {{n}} formatted feature blocks. **Crucially**:
    *   The `detailed description` for EACH feature **MUST** include:
        *   A clear explanation of the concept and rationale.
        *   **An explicit calculation method expressed using LaTeX math syntax, preferably inline** (e.g., `$\log(col_A + 1)$`, `\( \frac{{col_A}}{{col_B + \epsilon}} \)` , `\(\mathbb{{I}}(col_C > T)\)` for indicator functions). Ensure LaTeX is valid. Do **NOT** use pseudocode or plain text descriptions for the formula.
    *   **Strict Formatting**: Adhere *exactly* to the following structure for each feature block, using single quotes for keys and values (unless the value is a list of strings for 'relevant').
    *   **NO CODE BLOCKS**: Absolutely **NO** markdown code blocks (using three backticks like ```) are allowed within any part of the formatted feature blocks (the lines starting with 'new_feature', 'detailed description', etc.).

    **Required Format Example**:
    'new_feature': ['feature_name']
    'detailed description': 'Rationale... Calculation: [Inline LaTeX Formula]'
    'brief description': 'A short summary...'
    'relevant': ['col_a', 'col_b', ...]

**Output Structure Requirements**:
1.  Start with `<thinking>`.
2.  Detail thinking, emphasizing complexity and justification.
3.  Follow with {n} formatted feature blocks adhering strictly to the formatting rules (LaTeX formula, no code blocks).
4.  NO other text.
''',
        reflect_on_tool_use=False,
        model_client_stream=False,
    )

    # FeatureExpert now acts as an Adaptive Domain Expert
    feature_expert = AssistantAgent(
        name="FeatureExpert",
        model_client=client2,
        system_message=f"""You are an Adaptive Domain Expert and Senior Data Scientist focused on guiding feature generation.

**Your Process**:
1.  **Identify Domain & Adopt Persona**: Analyze prompt, identify domain, adopt expert persona. State in `<expert_thinking>`.
2.  **Domain Brainstorming**: Within `<expert_thinking>`, brainstorm domain-specific feature concepts based on your expert persona.
3.  **Evaluate Proposals**: Briefly assess proposed features based on Domain Relevance, DS Validity, and Innovation.
4.  **Synthesize & Provide Feedback**: Combine domain and DS evaluation.

**Interaction Strategy & Output Format**:
*   **Thinking Output**: Start response **ONLY** with `<expert_thinking>...</expert_thinking>`, including persona, domain reasoning, and domain brainstorming.
*   **Feedback Output**: Immediately follow `</expert_thinking>` with the evaluation verdict:
    *   **First Review**: **Default to REJECT**. Respond **ONLY** with `REJECT` followed by:
        *   A **brief** critique of the Proposer's features (1-2 sentences max).
        *   **1-2 specific, actionable feature suggestions** derived from your domain expertise (stated in `<expert_thinking>`). Use directive language. Example: "Based on my [Domain] expertise, I suggest you create a feature '[Feature Concept]' calculated as [Formula/Columns] because [Brief Rationale]." or "A better approach would be to calculate [Feature Concept] using [Columns], as this reflects [Domain Principle]."
    *   **Second Review**: If proposals significantly improved based on your specific suggestions, respond **ONLY** with `APPROVE`. Otherwise, respond **ONLY** with `REJECT` and concise final feedback (can include one final concrete suggestion if needed).
    *   **Third Review (or later)**: If proposals show reasonable effort or are minimally acceptable, respond **ONLY** with `APPROVE`. Otherwise, respond **ONLY** with `REJECT` and a very brief final note.
*   **Conciseness**: Keep all feedback sections (critique and suggestions) concise to minimize token usage.
*   **Format Focus**: Ignore minor proposer format issues.

**Example Response Structure (First Review):**
<expert_thinking>
Domain: Marine Biology (Abalone). Persona: Marine Biologist.
Brainstorming: Energy reserves (viscera/shucked ratios), Shell density (shell_weight/volume proxy), growth efficiency (meat gain per unit size?).
Evaluation: Prop Feat 1 (ratio) okay but basic. Prop Feat 2 (poly) lacks bio justification.
</expert_thinking>
REJECT Proposer's Feature 2 is biologically unfounded. Based on my expertise, I suggest you create a feature 'energy_reserve_ratio' calculated as `viscera_weight / shucked_weight` to better capture physiological state. Also consider 'shell_density_proxy' using `shell_weight / (length * diameter * height)`.
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