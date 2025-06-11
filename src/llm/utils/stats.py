import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
from sklearn.preprocessing import LabelEncoder
import termcolor


def generate_statistical_summary(
    df: pd.DataFrame,
    sample_size: int = 5000,
    target_col_name: str | None = None,
    target_col_data: pd.Series | np.ndarray | None = None
) -> str:
    """Generates an enhanced statistical summary string for the given DataFrame."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return "Input DataFrame is empty or invalid."

    summary_parts = ["--- Statistical Insights Summary ---"]
    # Ensure consistent sampling by using the DataFrame's index if target_col_data is provided
    sample_indices = df.index if len(df) <= sample_size else df.sample(n=sample_size, random_state=42).index
    df_sample = df.loc[sample_indices]

    # Align target_col_data with the sample if provided
    aligned_target_data = None
    if target_col_data is not None and target_col_name:
        try:
            # Ensure target_col_data is a pandas Series for easier indexing
            if isinstance(target_col_data, np.ndarray):
                target_col_data = pd.Series(target_col_data, index=df.index) # Assume original df index alignment

            if isinstance(target_col_data, pd.Series):
                    # Check if index types match before attempting intersection
                    if df_sample.index.dtype == target_col_data.index.dtype:
                        common_index = df_sample.index.intersection(target_col_data.index)
                        aligned_target_data = target_col_data.loc[common_index]
                        # Align df_sample as well, in case target had NaNs dropped etc.
                        df_sample = df_sample.loc[common_index]
                        if aligned_target_data.empty or df_sample.empty:
                            print(termcolor.colored("Warning: Target data or features became empty after index alignment.", "yellow"))
                            aligned_target_data = None # Reset if alignment failed
                        else:
                            print(termcolor.colored(f"Successfully aligned target data (size: {len(aligned_target_data)}) with sampled features.", "grey"))
                    else:
                        print(termcolor.colored(f"Warning: Index type mismatch between features ({df_sample.index.dtype}) and target ({target_col_data.index.dtype}). Cannot align target data.", "yellow"))
                        aligned_target_data = None
            else:
                print(termcolor.colored("Warning: target_col_data is not a Series or ndarray. Cannot align.", "yellow"))
                aligned_target_data = None
        except Exception as e:
                print(termcolor.colored(f"Error aligning target data: {e}. Proceeding without MI/LGBM.", "yellow"))
                aligned_target_data = None

    df_sample = df.sample(n=min(len(df), sample_size), random_state=42) if len(df) > sample_size else df
    numeric_cols = df_sample.select_dtypes(include=np.number).columns.tolist()
    all_cols = df_sample.columns.tolist()
    categorical_cols = df_sample.select_dtypes(include=['object', 'category']).columns.tolist()

    df_numeric_sample = df_sample[numeric_cols].copy() if numeric_cols else pd.DataFrame()

    # --- Univariate Statistics ---
    summary_parts.append("\n[Univariate Statistics]")
    # Numeric Columns
    if numeric_cols:
            summary_parts.append("Numeric Columns (Top 5 by variance shown):")
            numeric_stats = df_numeric_sample.agg(['mean', 'median', 'std', 'min', 'max', 'skew']).transpose()
            numeric_stats['nan%'] = df_numeric_sample.isnull().mean() * 100
            # Show top 5 by standard deviation (as a proxy for variance)
            top_var_cols = numeric_stats['std'].nlargest(5).index.tolist()
            stats_to_show = numeric_stats.loc[top_var_cols] if len(top_var_cols) >= 5 else numeric_stats # Show all if less than 5
            for col, stats in stats_to_show.iterrows():
                summary_parts.append(f"- '{col}': Mean={stats['mean']:.2f}, Median={stats['median']:.2f}, Std={stats['std']:.2f}, Skew={stats['skew']:.2f}, NaN={stats['nan%']:.1f}%")
    else:
            summary_parts.append("No numeric columns found.")

    # Categorical Columns
    if categorical_cols:
            summary_parts.append("\nCategorical Columns (Top 3 by unique values shown):")
            cat_stats = pd.DataFrame(index=categorical_cols)
            cat_stats['nunique'] = df_sample[categorical_cols].nunique()
            cat_stats['nan%'] = df_sample[categorical_cols].isnull().mean() * 100
            # Show top 3 by nunique
            top_nunique_cols = cat_stats['nunique'].nlargest(3).index.tolist()
            stats_to_show_cat = cat_stats.loc[top_nunique_cols] if len(top_nunique_cols) >=3 else cat_stats

            for col, stats in stats_to_show_cat.iterrows():
                top_vals = df_sample[col].value_counts(normalize=True).head(3) # Top 3 value frequencies
                top_vals_str = ", ".join([f"'{k}' ({v:.1%})" for k, v in top_vals.items()])
                summary_parts.append(f"- '{col}': Unique={int(stats['nunique'])}, TopVals=[{top_vals_str}], NaN={stats['nan%']:.1f}%")
    else:
        summary_parts.append("No categorical columns found.")


    # --- Correlation Summary ---
    if not df_numeric_sample.empty:
        try:
            # ... (Correlation logic remains the same as before) ...
            corr_matrix = df_numeric_sample.corr()
            high_corr_threshold = 0.8
            low_corr_threshold = -0.8 # For negative corr
            high_corr_pairs = []
            neg_corr_pairs = []
            processed_in_pair = set()
            for i in range(len(corr_matrix.columns)):
                for j in range(i):
                    col1, col2 = corr_matrix.columns[i], corr_matrix.columns[j]
                    # Check if correlation calculation resulted in NaN (can happen with low variance cols)
                    corr_val = corr_matrix.iloc[i, j]
                    if pd.isna(corr_val):
                        continue
                    if abs(corr_val) > high_corr_threshold:
                        if col1 not in processed_in_pair and col2 not in processed_in_pair:
                            pair = (col1, col2, corr_val)
                            if corr_val > high_corr_threshold:
                                high_corr_pairs.append(pair)
                                processed_in_pair.add(col1)
                                processed_in_pair.add(col2)
                            elif corr_val < low_corr_threshold:
                                neg_corr_pairs.append(pair)
                                processed_in_pair.add(col1)
                                processed_in_pair.add(col2)


            if high_corr_pairs:
                # Sort by absolute correlation descending for display
                high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                summary_parts.append("\n[Correlation Insights]")
                summary_parts.append(f"High Positive Correlation ( > {high_corr_threshold:.1f}):")
                for p in high_corr_pairs[:5]: # Limit displayed pairs
                        summary_parts.append(f"- '{p[0]}' & '{p[1]}': {p[2]:.2f}")
            else:
                    summary_parts.append(f"\n[Correlation Insights]\nNo strong positive correlations ( > {high_corr_threshold:.1f}) found.")

            if neg_corr_pairs:
                neg_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                summary_parts.append(f"High Negative Correlation ( < {low_corr_threshold:.1f}):")
                for p in neg_corr_pairs[:3]: # Limit displayed pairs
                        summary_parts.append(f"- '{p[0]}' & '{p[1]}': {p[2]:.2f}")
            # else: No need to explicitly state no negative corr if positive exists

        except Exception as e:
            summary_parts.append(f"\n[Correlation Insights]\nAnalysis failed: {e}")
    else:
            summary_parts.append("\n[Correlation Insights]\nNo numeric columns for analysis.")

    # --- PCA Insights (Enhanced) ---
    if not df_numeric_sample.empty:
        try:
            df_pca_input = df_numeric_sample.fillna(df_numeric_sample.median())
            if df_pca_input.empty or df_pca_input.shape[1] < 2:
                    summary_parts.append("\n[PCA Insights]\nSkipped: Not enough numeric features or data.")
            else:
                    scaler_pca = StandardScaler()
                    scaled_data_pca = scaler_pca.fit_transform(df_pca_input)
                    n_components_pca = min(5, df_pca_input.shape[1]) # Show more components
                    pca = PCA(n_components=n_components_pca, random_state=42)
                    pca.fit(scaled_data_pca)
                    variance_explained = pca.explained_variance_ratio_
                    cumulative_variance = np.cumsum(variance_explained)
                    summary_parts.append(f"\n[PCA Insights] (on {df_pca_input.shape[1]} numeric features)")
                    # summary_parts.append(f"Top {n_components_pca} components capture {cumulative_variance[-1]*100:.1f}% total variance.")
                    # Show top contributing features for each component
                    for i in range(n_components_pca):
                        component = pca.components_[i]
                        feature_loadings = pd.Series(component, index=df_pca_input.columns).abs().sort_values(ascending=False)
                        top_features = feature_loadings.head(5).index.tolist() # Show more features
                        summary_parts.append(f"- Comp. {i+1} ({variance_explained[i]*100:.1f}% var, cum: {cumulative_variance[i]*100:.1f}%) influenced by: {top_features}")
        except Exception as e:
            summary_parts.append(f"\n[PCA Insights]\nAnalysis failed: {e}")
    else:
            summary_parts.append("\n[PCA Insights]\nSkipped: No numeric columns.")


    # --- Mutual Information (MI) Insights (if target_col provided) ---
    if target_col_name and aligned_target_data is not None:
        target_type = 'unknown'
        try:
            # Prepare data for MI - handle NaNs and non-numeric types
            # X_mi = df_sample.drop(columns=[target_col_name], errors='ignore').copy() # Use df_sample aligned earlier
            X_mi = df_sample.copy() # Use df_sample aligned earlier
            y_mi = aligned_target_data.copy()
            # Basic target preprocessing
            if pd.api.types.is_numeric_dtype(y_mi):
                y_mi.fillna(y_mi.median(), inplace=True)
                target_type = 'regression'
                # Optional: Discretize target for MI if it's continuous?
                # discretizer = KBinsDiscretizer(n_bins=5, encode='ordinal', strategy='uniform')
                # y_mi = discretizer.fit_transform(y_mi.values.reshape(-1, 1)).ravel()
            elif pd.api.types.is_categorical_dtype(y_mi) or pd.api.types.is_object_dtype(y_mi):
                    y_mi.fillna(y_mi.mode()[0], inplace=True)
                    le = LabelEncoder()
                    y_mi = le.fit_transform(y_mi)
                    target_type = 'classification'
            else:
                    raise ValueError("Target column type not suitable for MI analysis.")

            # Preprocess features for MI (handle NaNs, encode categoricals)
            processed_features_mi = {}
            feature_names_mi = []
            discrete_mask_mi = []
            for col in X_mi.columns:
                if pd.api.types.is_numeric_dtype(X_mi[col]):
                    processed_features_mi[col] = X_mi[col].fillna(X_mi[col].median()).values
                    feature_names_mi.append(col)
                    discrete_mask_mi.append(False) # Continuous features
                elif pd.api.types.is_categorical_dtype(X_mi[col]) or pd.api.types.is_object_dtype(X_mi[col]):
                    filled_col = X_mi[col].fillna(X_mi[col].mode()[0])
                    le = LabelEncoder()
                    processed_features_mi[col] = le.fit_transform(filled_col).astype(int) # Ensure integer type
                    feature_names_mi.append(col)
                    discrete_mask_mi.append(True) # Discrete features
                # else: skip other types

            if not feature_names_mi:
                    summary_parts.append("\n[Mutual Information]\nSkipped: No suitable features found after preprocessing.")
            else:
                # Stack processed features into a 2D array
                X_mi_processed = np.column_stack([processed_features_mi[name] for name in feature_names_mi])

                # Calculate MI based on target type
                if target_type == 'regression':
                    mi_scores = mutual_info_regression(X_mi_processed, y_mi, discrete_features=discrete_mask_mi, random_state=42)
                elif target_type == 'classification':
                    mi_scores = mutual_info_classif(X_mi_processed, y_mi, discrete_features=discrete_mask_mi, random_state=42)
                else: # Should not happen if initial check is done
                        raise ValueError("Unknown target type for MI.")

                mi_series = pd.Series(mi_scores, index=feature_names_mi).sort_values(ascending=False)
                top_n_mi = min(10, len(mi_series)) # Show more features
                summary_parts.append(f"\n[Mutual Information] (relevance to '{target_col_name}')")
                summary_parts.append(f"Top {top_n_mi} features by MI score:")
                for feature, score in mi_series.head(top_n_mi).items():
                    summary_parts.append(f"- {feature}: {score:.3f}") # Higher score = more informative

        except Exception as e:
            summary_parts.append(f"\n[Mutual Information]\nAnalysis failed: {e}")
    elif target_col_name:
            summary_parts.append(f"\n[Mutual Information]\nSkipped: Target column '{target_col_name}' data not available or alignment failed.")
    else:
            summary_parts.append("\n[Mutual Information]\nSkipped: Target column not provided.")


    # --- 删除LightGBM相关部分 ---
    # 找到以下代码段并完全删除：
    """
        # --- Basic LGBM Feature Importance (if target_col provided) ---
        if target_col_name and aligned_target_data is not None:
            try:
                # Prepare data - Use numeric and simple categorical
                X_lgbm = df_sample.copy() # Use aligned df_sample
                y_lgbm = aligned_target_data.copy()
                lgbm_feature_names = []
                categorical_features_lgbm = []
    
                # Preprocessing
                for col in X_lgbm.columns:
                    if pd.api.types.is_numeric_dtype(X_lgbm[col]):
                        X_lgbm[col] = X_lgbm[col].fillna(X_lgbm[col].median())
                        lgbm_feature_names.append(col)
                    elif X_lgbm[col].nunique() < 20 and pd.api.types.is_object_dtype(X_lgbm[col]): # Simple categorical encoding
                            X_lgbm[col] = X_lgbm[col].fillna(X_lgbm[col].mode()[0]).astype('category')
                            lgbm_feature_names.append(col)
                            categorical_features_lgbm.append(col)
                        # else: drop other types
    
                X_lgbm = X_lgbm[lgbm_feature_names] # Keep only processed columns
    
                if X_lgbm.empty:
                    raise ValueError("No features left after preprocessing for LGBM.")
    
                # Determine task type and model
                if pd.api.types.is_numeric_dtype(y_lgbm):
                    y_lgbm = y_lgbm.fillna(y_lgbm.median())
                    lgbm_params = {'objective': 'regression_l1', 'metric': 'mae', 'n_estimators': 50, 'learning_rate': 0.05, 'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 1, 'verbose': -1, 'n_jobs': -1, 'seed': 42, 'boosting_type': 'gbdt'}
                    model = lgb.LGBMRegressor(**lgbm_params)
                else: # Assume classification
                        y_lgbm = y_lgbm.fillna(y_lgbm.mode()[0])
                        le_lgbm = LabelEncoder()
                        y_lgbm = le_lgbm.fit_transform(y_lgbm)
                        num_class = len(le_lgbm.classes_)
                        lgbm_params = {'objective': 'multiclass' if num_class > 2 else 'binary', 'metric': 'multi_logloss' if num_class > 2 else 'binary_logloss', 'n_estimators': 50, 'learning_rate': 0.05, 'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 1, 'verbose': -1, 'n_jobs': -1, 'seed': 42, 'boosting_type': 'gbdt'}
                        if num_class > 2:
                            lgbm_params['num_class'] = num_class
                        model = lgb.LGBMClassifier(**lgbm_params)
    
                # Train model
                model.fit(X_lgbm, y_lgbm, categorical_feature=[col for col in categorical_features_lgbm if col in X_lgbm.columns])
    
                # Get feature importance
                importances = pd.Series(model.feature_importances_, index=lgbm_feature_names).sort_values(ascending=False)
                top_n_lgbm = min(10, len(importances)) # Show more features
                summary_parts.append(f"\n[LGBM Importance] (predicting '{target_col_name}')")
                summary_parts.append(f"Top {top_n_lgbm} features by importance:")
                for feature, score in importances.head(top_n_lgbm).items():
                    summary_parts.append(f"- {feature}: {score}")
    
            except Exception as e:
                summary_parts.append(f"\n[LGBM Importance]\nAnalysis failed: {e}")
        elif target_col_name:
                summary_parts.append(f"\n[LGBM Importance]\nSkipped: Target column '{target_col_name}' data not available or alignment failed.")
        else:
                summary_parts.append("\n[LGBM Importance]\nSkipped: Target column not provided.")
    """
    
    # --- 增强Pearson分析 ---
    # 在现有的相关性分析部分添加：
    # --- Correlation Summary ---
    if not df_numeric_sample.empty:
        try:
            # ... existing correlation code ...
            
            # 新增分位数分析
            summary_parts.append("\n[Pearson分位数分析]")
            abs_corr = corr_matrix.abs().stack().reset_index()
            abs_corr.columns = ['Feature1', 'Feature2', 'Correlation']
            abs_corr = abs_corr[abs_corr['Feature1'] != abs_corr['Feature2']]
            
            quantiles = abs_corr['Correlation'].quantile([0.25, 0.5, 0.75])
            summary_parts.append(f"- 25%分位数: {quantiles[0.25]:.2f}")
            summary_parts.append(f"- 中位数: {quantiles[0.5]:.2f}") 
            summary_parts.append(f"- 75%分位数: {quantiles[0.75]:.2f}")

            # 新增Top Pearson特征对
            top_pairs = abs_corr.nlargest(5, 'Correlation')
            summary_parts.append("\n[Top Pearson特征对]:")
            for _, row in top_pairs.iterrows():
                summary_parts.append(f"- {row['Feature1']} & {row['Feature2']}: {row['Correlation']:.2f}")

        except Exception as e:
            summary_parts.append(f"\n[Pearson分析]\n执行失败: {e}")


    # --- K-Means Clustering Insights (Enhanced) ---
    if not df_numeric_sample.empty:
        try:
            df_kmeans_input = df_numeric_sample.fillna(df_numeric_sample.median())
            if df_kmeans_input.empty or df_kmeans_input.shape[1] < 1:
                    summary_parts.append("\n[Clustering Insights]\nSkipped: Not enough numeric features or data.")
            else:
                    scaler_kmeans = StandardScaler()
                    scaled_data_kmeans = scaler_kmeans.fit_transform(df_kmeans_input)

                    # Find optimal K using silhouette score
                    best_k = -1
                    best_score = -1.1 # Initialize below valid range
                    max_k = min(6, scaled_data_kmeans.shape[0] - 1) if scaled_data_kmeans.shape[0] > 1 else -1
                    silhouette_scores = {}

                    if max_k >= 2:
                        for k in range(2, max_k + 1):
                            try:
                                kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto') # Use 'auto' for n_init
                                labels = kmeans.fit_predict(scaled_data_kmeans)
                                # Need at least 2 unique labels for silhouette score
                                if len(np.unique(labels)) > 1:
                                    score = silhouette_score(scaled_data_kmeans, labels)
                                    silhouette_scores[k] = score
                                    if score > best_score:
                                        best_score = score
                                        best_k = k
                                else:
                                    # If only 1 cluster is formed, score is undefined, skip k
                                    print(termcolor.colored(f"Silhouette calculation skipped for k={k}: Only 1 cluster found.", "grey"))
                                    continue
                            except Exception as kmeans_e:
                                print(termcolor.colored(f"Silhouette calculation failed for k={k}: {kmeans_e}", "grey"))
                                continue

                    if best_k != -1:
                        kmeans = KMeans(n_clusters=best_k, random_state=42, n_init='auto')
                        labels = kmeans.fit_predict(scaled_data_kmeans)
                        centroids_scaled = kmeans.cluster_centers_
                        # Inverse transform centroids to original scale for interpretability
                        centroids_original = scaler_kmeans.inverse_transform(centroids_scaled)
                        centroid_df = pd.DataFrame(centroids_original, columns=df_kmeans_input.columns)
                        centroid_df_scaled = pd.DataFrame(centroids_scaled, columns=df_kmeans_input.columns) # Scaled version for variance calc

                        # Identify features with largest variance across centroids (potential separators)
                        centroid_variance = centroid_df_scaled.var(axis=0).sort_values(ascending=False)
                        top_separator_features = centroid_variance.head(5).index.tolist() # More features
                        # Identify features with smallest variance across centroids (common features)
                        least_variance_features = centroid_variance.nsmallest(3).index.tolist()

                        summary_parts.append(f"\n[Clustering Insights] (K-Means on {df_kmeans_input.shape[1]} numeric features)")
                        summary_parts.append(f"Optimal K found: {best_k} (Max Silhouette Score: {best_score:.2f})")
                        cluster_counts = pd.Series(labels).value_counts().sort_index()
                        summary_parts.append(f"Cluster sizes: {dict(cluster_counts)}")
                        summary_parts.append(f"Features varying MOST across clusters (potential separators): {top_separator_features}")
                        summary_parts.append(f"Features varying LEAST across clusters (common traits): {least_variance_features}")

                        # Show centroid means for top separating features
                        summary_parts.append("Centroid Means (Original Scale) for Top Separating Features:")
                        for cluster_i in range(best_k):
                            means = centroid_df.loc[cluster_i, top_separator_features].to_dict()
                            means_str = ", ".join([f"'{k}': {v:.2f}" for k, v in means.items()])
                            summary_parts.append(f"- Cluster {cluster_i}: {means_str}")
                    else:
                        summary_parts.append("\n[Clustering Insights]\nCould not determine optimal K or data unsuitable for K-Means.")

        except Exception as e:
            summary_parts.append(f"\n[Clustering Insights]\nAnalysis failed: {e}")
    else:
        summary_parts.append("\n[Clustering Insights]\nSkipped: No numeric columns.")

    summary_parts.append("\n--- End Summary ---")
    return "\n".join(summary_parts)

# 在文件末尾添加以下调试代码
if __name__ == '__main__':
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Generate statistical insights for CSV file')
    parser.add_argument('filepath', type=str, help='Path to CSV file')
    parser.add_argument('--sample-size', type=int, default=5000, 
                      help='Sample size for analysis (default: 5000)')
    parser.add_argument('--target-col', type=str, default=None,
                      help='Target column name for supervised analysis')
    
    args = parser.parse_args()
    
    try:
        # 读取CSV文件
        df = pd.read_csv(args.filepath)
        print(f"成功加载文件: {args.filepath} ({len(df)} 行)")
        
        # 提取目标列数据（如果指定）
        target_data = df[args.target_col] if args.target_col else None
        
        # 执行统计分析
        result = generate_statistical_summary(
            df=df,
            sample_size=args.sample_size,
            target_col_name=args.target_col,
            target_col_data=target_data
        )
        
        print("\n" + result)
        
    except FileNotFoundError:
        print(f"错误：文件 {args.filepath} 不存在")
        sys.exit(1)
    except KeyError as e:
        print(f"错误：目标列 '{args.target_col}' 不存在于文件中")
        sys.exit(1)
    except Exception as e:
        print(f"分析失败: {str(e)}")
        sys.exit(1)