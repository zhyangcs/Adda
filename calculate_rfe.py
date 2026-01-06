import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import RFE
from sklearn.preprocessing import LabelEncoder
import matplotlib

# Set non-interactive backend
matplotlib.use('Agg')

# Add project root to path
project_root = os.path.abspath(os.path.join(os.getcwd()))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import necessary modules from the project
try:
    from src.llm.tests.test_util import task_config
    from src.env import dataset_path
except ImportError:
    # If src is not found, try to assume we are in project root
    sys.path.append(os.getcwd())
    from src.llm.tests.test_util import task_config
    from src.env import dataset_path

def calculate_rfe_and_plot(task_name="heart", top_k=7):
    print(f"Calculating RFE for task: {task_name}")
    
    # 1. Load Data
    _, target_col, task_type = task_config(task_name)
    csv_path = os.path.join(dataset_path, task_name, "train_new.csv")
    
    if not os.path.exists(csv_path):
        print(f"Error: Dataset not found at {csv_path}")
        return

    df = pd.read_csv(csv_path)
    print(f"Dataset loaded: {df.shape}")

    # 2. Preprocessing (Basic handling for RFE)
    # Drop ID column if exists
    if "id" in df.columns:
        df = df.drop(columns=["id"])
        
    X = df.drop(columns=[target_col])
    y = df[target_col]

    # Handle missing values (Simple imputation)
    # Numeric cols: mean, Categorical cols: mode
    for col in X.columns:
        if X[col].dtype in ['int64', 'float64']:
             X[col].fillna(X[col].mean(), inplace=True)
        else:
             X[col].fillna(X[col].mode()[0], inplace=True)

    # Label Encode Categorical Columns
    le = LabelEncoder()
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = le.fit_transform(X[col].astype(str))
            
    # Also encode target if it's classification
    if task_type == 'classify' and y.dtype == 'object':
        y = le.fit_transform(y)

    # 3. Calculate RFE
    print("Running RFE...")
    # Use RandomForest as estimator (consistent with RF_Full)
    estimator = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    
    # RFE requires specifying the number of features to select, 
    # but here we want ranking/importance for all or top K.
    # scikit-learn's RFE ranks features. 
    # To get "values", we can look at feature importances of the underlying estimator 
    # or just use the ranking (1 is best).
    # However, user asked for "RFE values" likely implying importance scores derived from RFE process 
    # or just the feature importances from the model used in RFE.
    # Typically RFE gives rankings. Recursive Feature Elimination with Cross-Validation (RFECV) gives scores.
    # Let's stick to standard RFE as referenced in paper_metrics_simplified (implied context)
    # Usually we use feature_importances_ from the estimator fitted on selected features, 
    # OR we can just use the estimator's feature importances directly as a proxy if step=1.
    
    # Let's perform RFE to select top_k features, but to get a bar chart of "values",
    # we usually plot the Feature Importances of the model trained on these features 
    # OR we plot the importances of all features. 
    # Let's simulate the logic often used: Fit model -> Get Importances.
    # RFE specifically:
    selector = RFE(estimator, n_features_to_select=top_k, step=1)
    selector = selector.fit(X, y)
    
    # Get selected features
    selected_mask = selector.support_
    selected_features = X.columns[selected_mask]
    ranking = selector.ranking_
    
    print(f"Top {top_k} selected features by RFE: {selected_features.tolist()}")

    # To plot "RFE values", we can use the feature importances of the estimator 
    # trained on the reduced set, OR the importances from a full model run (which RFE uses iteratively).
    # A common visualization for RFE is actually the Feature Importances of the final selected set.
    
    # Fit estimator on selected features to get their relative importance for the plot
    X_selected = X[selected_features]
    estimator.fit(X_selected, y)
    importances = estimator.feature_importances_
    
    # Sort for plotting
    indices = np.argsort(importances)[::-1]
    sorted_features = [selected_features[i] for i in indices]
    sorted_importances = importances[indices]

    print("Feature Importances of Selected Features:")
    for f, imp in zip(sorted_features, sorted_importances):
        print(f"{f}: {imp:.4f}")

    # 4. Plotting
    plt.figure(figsize=(10, 6))
    
    # Style settings from previous context (gold/orange color, no top/right spines)
    bar_color = "#FFB90F"
    ax = plt.gca()
    
    bars = plt.bar(sorted_features, sorted_importances, color=bar_color, width=0.6, zorder=3)
    
    # Y-axis
    plt.ylabel("Importance Score", fontsize=12, fontweight='bold')
    # Dynamic ylim
    plt.ylim(0, max(sorted_importances) * 1.1) 
    
    # Spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False) # Hide Y axis line as requested before
    ax.spines['bottom'].set_color('black')
    
    # Grid
    ax.yaxis.grid(True, linestyle='-', which='major', color='lightgray', alpha=0.7, zorder=0)
    
    # X-axis labels
    plt.xticks(rotation=45, ha='right') # Rotate if names are long
    ax.tick_params(axis='x', length=0)
    ax.tick_params(axis='y', length=0)
    
    # Add values on top of bars
    for b, v in zip(bars, sorted_importances):
        plt.text(b.get_x() + b.get_width() / 2, v + 0.005, f"{v:.3f}", ha="center", va="bottom")
        
    plt.title(f"Top {top_k} Features by RFE (Heart Dataset)", fontsize=14)
    plt.tight_layout()
    
    output_file = 'rfe_chart.png'
    plt.savefig(output_file, dpi=300)
    print(f"Chart saved to {output_file}")

if __name__ == "__main__":
    calculate_rfe_and_plot(task_name="heart", top_k=7)

