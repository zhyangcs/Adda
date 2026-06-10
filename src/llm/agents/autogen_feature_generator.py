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
API_KEY = 'sk-F6l6kc8Xlqb6FlP8ll0cST1GmXB5uSIDZIYyGvL0W2mdkg0F' # Placeholder - Use environment variables
BASE_URL = 'https://api.nuwaapi.com/v1' # Placeholder
MODEL = src.env.default_model # Use default model from environment configuration

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

    # --- Updated Feature Proposer Prompt ---
    # Start with the existing detailed system message for FeatureProposer
    feature_proposer_original_system_message = f'''You are a **Principal Feature Engineering Specialist**. You possess deep, applied expertise across multiple domains crucial for state-of-the-art predictive modeling:

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

Your task is to engineer **highly impactful, novel, and mathematically sophisticated features** for a predictive modeling challenge based on the provided dataset description ({target_column} is the target variable), aiming to maximize downstream ML model performance. **Performance is measured by 1-RAE (for regression tasks) or AUC (for classification tasks).**

**Mandatory Requirement**: In EVERY set of {{n}} features you propose, **at least ONE feature MUST utilize mathematical/statistical operations considered advanced in a data science context**, going beyond simple arithmetic (+, -, *, /), basic exponentiation/logarithms, and simple polynomials (like x^2). Examples of acceptable operations include (but are not limited to): fitting statistical distributions and using parameters, advanced linear algebra (matrix decompositions, eigenvectors), calculus concepts (numerical derivatives/integrals), information-theoretic measures, multi-scale analysis (e.g., wavelets, varying window statistics), or complex conditional logic based on multiple variables.

Follow these steps meticulously:
1.  **Analyze**: Apply your expertise to deeply interpret the data descriptions (`/* Data description: ... */`) AND the statistical insights summary (`/* Advanced Statistics Summary: ... */` if provided). Assess data quality, correlations, potential latent structures (from PCA), feature importance hints (from Ridge), and potential segmentation (from Clustering).
2.  **Think (CoT - Expert Application, Advanced Math & Diversity Focus)**: Document your thinking in `<thinking>...</thinking>` tags:
    *   **Task & Data Assessment**: State inferred task type (Regression/Classification) and the corresponding optimization metric (1-RAE/AUC). Detail findings on data quality (outliers, missingness, multimodality) and how they might influence feature design.
    *   **Hypothesis Generation (Informed by Stats & Multi-Step Focus)**: Formulate hypotheses leveraging insights from the *Statistical Insights Summary*. Explicitly mention how the summary informs your ideas (e.g., "High correlation between A and B suggests exploring their ratio..."). Consider multi-step features (e.g., calculate an intermediate value then transform it). For instance, first calculate `ratio = A / B`, then `log_ratio = log(ratio + 1)`.
    *   **Feature Brainstorming (Informed, Multi-Step & Advanced)**: Generate diverse candidates, prioritizing those informed by the statistical summary, potentially involving multiple calculation steps, and including advanced operations as required.
    *   **Rationale & Filtering (Justify with Stats & Multi-Step)**: Justify features using theory and *explicitly reference the statistical summary* where applicable (e.g., "Proposed due to low correlation reported..."). Explain the value of multi-step calculations if used. Filter rigorously.
    *   **Final Selection & Justification (Informed by Stats & Advanced Check)**: Select EXACTLY {n} features. Justify the selection based on potential impact, novelty, diversity, handling of data issues, AND how they leverage insights from the statistical summary. Explicitly identify the advanced operation feature.
3.  **Format**: After `</thinking>`, provide the {{n}} formatted feature blocks. Remember the strict formatting rules: specific keys, **LaTeX math only** for calculations, **NO markdown code blocks**. Review the required format example carefully.

**Required Format Example**:
'new_feature': ['feature_name']
'detailed description': 'Rationale addressing [Data Issue]... Calculation: [Inline LaTeX Formula]'
'brief description': 'A short summary...'
'relevant': ['col_a', 'col_b', ...]

**Output Structure Requirements**:
1.  Start with `<thinking>`.
2.  Detail thinking, linking explicitly to statistical insights and justifying multi-step features.
3.  Follow with {n} strictly formatted feature blocks (NO ``` code blocks!).
4.  Constraint Check: Ensure advanced operations are used.
5.  NO other text.
'''

    # Detailed guidance on using the statistical summary
    stats_guidance = """

**Leveraging Statistical Insights (CRITICAL REMINDER!)**:
Check for the `--- Statistical Insights Summary ---` section in the prompt. **USE the INSIGHTS to GUIDE your feature IDEAS, DO NOT generate features that RE-RUN the analyses (PCA, MI, LGBM, KMeans).**

Potential insights in the summary include:
*   `[Correlation Insights]`: Highlights pairs of features with strong linear correlation.
    *   **How to Use**: If A & B correlate highly, consider `A-B`, `A/(B+eps)`, or interactions with *other* features. Avoid redundant features like `A+B`. Justify based on the correlation.
*   `[PCA Insights]`: Shows variance explained by top components and lists the *original features* that most strongly influence each component.
    *   **How to Use**: If Comp. 1 explains significant variance and is strongly influenced by 'length' and 'width', it suggests a latent 'size' factor. Propose features *inspired* by this, like `area = length * width` or `aspect_ratio = length / width`. Mention the link to the component's influencing features in `<thinking>`. **DO NOT propose a 'PCA component feature'.**
*   `[Mutual Information]`: Ranks features by their Mutual Information score with the target variable, indicating potential non-linear relevance.
    *   **How to Use**: Features high on this list are likely informative, even if not linearly correlated or selected by Ridge. Prioritize using these features in interactions or non-linear transformations (e.g., `log(high_mi_feature + 1)`, `high_mi_feature * category`). Justify using the MI score.
*   `[LGBM Importance]`: Ranks features based on their importance in a simple LightGBM model predicting the target.
    *   **How to Use**: This provides a model-based view of importance. Similar to MI, prioritize using high-ranking features in interactions and transformations. Consider combining insights from MI and LGBM importance.
*   `[Clustering Insights]`: Reports the optimal number of clusters (K) found via K-Means, cluster sizes, and the *original features* whose average values differ most significantly across these clusters.
    *   **How to Use**: This suggests data segments and what defines them. If 'feature_X' and 'feature_Y' distinguish the clusters, propose features related to these, possibly conditional on cluster membership (e.g., create interactions like `feature_X * feature_Z` only for samples likely belonging to a specific cluster profile described by the varying features). Explain the connection to the cluster-separating features. **DO NOT generate code for K-Means.**
*   **AHP/Other Notes**: Methods like AHP require subjective inputs and are **not** automatically calculated. Focus on the provided summary sections.

**Action**: ALWAYS check for the `--- Statistical Insights Summary ---` section. Explicitly reference its findings (e.g., "PCA Comp. 1 loadings suggest...", "MI ranks FeatureX highly...", "Clustering insights show FeatureY separates clusters...") in your `<thinking>` block to explain *why* you are proposing certain features and how the insights guided your strategy. Combine these insights with the basic column descriptions (`/* Data description: ... */`) for robust feature engineering.

**Multi-Step Feature Encouragement**: Think beyond single operations. Can you combine steps logically? Examples:
*   Calculate a ratio, then take its logarithm: `ratio = A/B`, `log_ratio = log(ratio+1)`
*   Calculate a difference, then interact it: `diff = A-B`, `diff_X_cat = diff * (category == 'X')`
*   Aggregate a value, then normalize it by another: `sum_A_by_cat = sum(A) group by cat`, `norm_sum_A = sum_A_by_cat / count(A) group by cat` (conceptual example)

Justify the multi-step approach in your rationale within the feature's detailed description.
"""

    proposer_system_message = feature_proposer_original_system_message + stats_guidance

    # --- Create Agents --- (Ensure the correct system message is used)
    feature_proposer = AssistantAgent(
        name="FeatureProposer",
        model_client=client1,
        system_message=proposer_system_message,
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