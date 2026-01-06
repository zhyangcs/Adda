import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import RFE
from sklearn.preprocessing import LabelEncoder
import pickle
import matplotlib

# Set non-interactive backend
matplotlib.use('Agg')

# Add project root to path
project_root = os.path.abspath(os.path.join(os.getcwd()))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import necessary modules
try:
    from src.llm.tests.test_util import task_config
    from src.env import dataset_path
    from src.pg.add_pandas_transformer import AddPandasTransformer
    # Depending on how the pipeline was saved, we might need LLMDagConstructor
    from src.llm.llm_dag_util import LLMDagConstructor
except ImportError:
    sys.path.append(os.getcwd())
    from src.llm.tests.test_util import task_config
    from src.env import dataset_path
    # Try importing from relative path if src is local
    from src.pg.add_pandas_transformer import AddPandasTransformer

def calculate_new_feature_rfe(task_name="heart", store_dir="test/store/heart_RF_Full", top_k=7):
    print(f"Calculating RFE for NEW features in: {store_dir}")
    
    # 1. Load Data
    _, target_col, task_type = task_config(task_name)
    csv_path = os.path.join(dataset_path, task_name, "train_new.csv")
    
    if not os.path.exists(csv_path):
        print(f"Error: Dataset not found at {csv_path}")
        return

    df_raw = pd.read_csv(csv_path)
    print(f"Original Dataset loaded: {df_raw.shape}")

    # 2. Load Pipeline and Generate New Features
    pkl_path = os.path.join(store_dir, "cur_states.pkl")
    if not os.path.exists(pkl_path):
        print(f"Error: Pickle file not found at {pkl_path}")
        return
        
    print("Loading pipeline state...")
    with open(pkl_path, "rb") as f:
        ctor = pickle.load(f)
        
    # We need to apply the best pipeline to the dataframe
    # Assuming ctor has 'pipes' or we can extract the best code
    # Usually ctor.pipes contains the final selected pipelines
    
    # Alternatively, we can use the 'pipes' attribute if available
    pipes = getattr(ctor, "pipes", [])
    if not pipes:
        print("No pipes found in constructor. Trying to compute best code...")
        # This might be risky if it modifies state, but let's try to see if pipes are generated
        # ctor.compute_best_code() 
        # pipes = ctor.pipes
        pass

    # If pipes are still empty, we might need to look at 'output_nodes' or similar
    # But for now, let's assume we can get the code paths from pycodes dir
    pycodes_dir = os.path.join(store_dir, "pycodes")
    pipeline_files = [f for f in os.listdir(pycodes_dir) if f.startswith("pipeline_") and f.endswith(".py")]
    
    if not pipeline_files:
        print("No pipeline files found in pycodes directory.")
        return
        
    # Sort by modification time to get the latest
    pipeline_files.sort(key=lambda x: os.path.getmtime(os.path.join(pycodes_dir, x)), reverse=True)
    best_pipeline_file = os.path.join(pycodes_dir, pipeline_files[0])
    print(f"Using pipeline file: {best_pipeline_file}")
    
    # Read the pipeline code
    with open(best_pipeline_file, "r") as f:
        code_content = f.read()
        
    # Execute the pipeline to get the transformed dataframe
    # We need to setup the execution environment
    local_scope = {
        "pd": pd,
        "np": np,
        "df": df_raw.copy(), # Inject original df
        "LabelEncoder": LabelEncoder,
        # Add other potential imports
    }
    
    try:
        print("Executing pipeline code to generate features...")
        exec(code_content, globals(), local_scope)
        df_transformed = local_scope.get("df")
        print(f"Transformed Dataset shape: {df_transformed.shape}")
    except Exception as e:
        print(f"Error executing pipeline: {e}")
        return

    # 3. Preprocessing for Modeling
    # Drop ID column if exists
    if "id" in df_transformed.columns:
        df_transformed = df_transformed.drop(columns=["id"])
        
    X = df_transformed.drop(columns=[target_col])
    y = df_transformed[target_col]

    # Handle missing values
    for col in X.columns:
        if X[col].dtype in ['int64', 'float64']:
             X[col].fillna(X[col].mean(), inplace=True)
        else:
             X[col].fillna(X[col].mode()[0] if not X[col].mode().empty else "Unknown", inplace=True)

    # Label Encode
    le = LabelEncoder()
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = le.fit_transform(X[col].astype(str))
            
    if task_type == 'classify' and y.dtype == 'object':
        y = le.fit_transform(y)

    # 4. Calculate RFE on NEW features
    print("Running RFE on transformed dataset...")
    estimator = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    
    # Select top_k features
    selector = RFE(estimator, n_features_to_select=top_k, step=1)
    selector = selector.fit(X, y)
    
    selected_mask = selector.support_
    selected_features = X.columns[selected_mask]
    
    print(f"Top {top_k} features (mixed original/new): {selected_features.tolist()}")

    # Fit model to get importances
    X_selected = X[selected_features]
    estimator.fit(X_selected, y)
    importances = estimator.feature_importances_
    
    indices = np.argsort(importances)[::-1]
    sorted_features = [selected_features[i] for i in indices]
    sorted_importances = importances[indices]

    print("Feature Importances:")
    for f, imp in zip(sorted_features, sorted_importances):
        print(f"{f}: {imp:.4f}")

    # 5. Plotting Horizontal
    plt.figure(figsize=(10, 6))
    
    # Define colors
    color_original = "#FFB90F" # Gold/Orange
    color_generated = "#4C78A8" # Blue
    
    # Identify generated features
    original_cols = set(df_raw.columns) - {target_col, "id"}
    
    bar_colors = []
    # Reverse for horizontal plot (top to bottom)
    sorted_features_rev = sorted_features[::-1]
    sorted_importances_rev = sorted_importances[::-1]
    
    for feat in sorted_features_rev:
        if feat in original_cols:
            bar_colors.append(color_original)
        else:
            bar_colors.append(color_generated)

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=color_original, label='Original Feature'),
        Patch(facecolor=color_generated, label='Generated Feature')
    ]
    
    ax = plt.gca()
    
    # Horizontal bar plot
    bars = plt.barh(sorted_features_rev, sorted_importances_rev, color=bar_colors, height=0.6, zorder=3)
    
    plt.xlabel("Importance Score", fontsize=12, fontweight='bold')
    plt.xlim(0, max(sorted_importances) * 1.15) 
    
    # Spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_color('black')
    
    # Vertical grid
    ax.xaxis.grid(True, linestyle='-', which='major', color='lightgray', alpha=0.7, zorder=0)
    
    # Remove ticks
    ax.tick_params(axis='x', length=0)
    ax.tick_params(axis='y', length=0)
    
    # Add values
    for b, v in zip(bars, sorted_importances_rev):
        plt.text(v + 0.002, b.get_y() + b.get_height() / 2, f"{v:.3f}", ha="left", va="center")
        
    plt.title(f"Top {top_k} Features (Original + Generated) by RFE", fontsize=14)
    plt.legend(handles=legend_elements, loc='lower right')
    plt.tight_layout()
    
    output_file = 'rfe_chart_new_features_h.png'
    plt.savefig(output_file, dpi=300)
    print(f"Chart saved to {output_file}")

if __name__ == "__main__":
    calculate_new_feature_rfe(task_name="heart", store_dir="test/store/heart_RF_Full", top_k=7)
