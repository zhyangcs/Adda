import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

def plot_static_rfe():
    features = [
        "aggregated_risk_interaction_score",
        "cardio_metabolic_risk_index",
        "diabp",
        "totchol_Fillna",
        "bmi",
        "age",
        "sysbp"
    ]
    
    importances = [
        0.1817,
        0.1486,
        0.1453,
        0.1426,
        0.1335,
        0.1298,
        0.1185
    ]
    
    feature_types = [
        "Generated",
        "Generated",
        "Original",
        "Generated",
        "Original",
        "Original",
        "Original"
    ]

    # 创建 Figure
    fig = plt.figure(figsize=(10, 6))
    
    color_original = "#FFB90F"
    color_generated = "#4C78A8"
    
    features_rev = features[::-1]
    importances_rev = importances[::-1]
    types_rev = feature_types[::-1]
    
    bar_colors = []
    for t in types_rev:
        if t == "Original":
            bar_colors.append(color_original)
        else:
            bar_colors.append(color_generated)
            
    ax = plt.gca()
    bars = plt.barh(features_rev, importances_rev, color=bar_colors, height=0.6, zorder=3)
    
    # 移除 Axes 级别的 xlabel，改用 Figure 级别的 text
    # plt.xlabel("Importance Score", fontsize=12, fontweight='bold', labelpad=10)
    
    plt.xlim(0, max(importances) * 1.15) 
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_color('black')
    
    ax.xaxis.grid(True, linestyle='-', which='major', color='lightgray', alpha=0.7, zorder=0)
    ax.tick_params(axis='x', length=0)
    ax.tick_params(axis='y', length=0)
    
    for b, v in zip(bars, importances_rev):
        plt.text(v + 0.002, b.get_y() + b.get_height() / 2, f"{v:.4f}", ha="left", va="center")
        
    legend_elements = [
        Patch(facecolor=color_original, label='Original Feature'),
        Patch(facecolor=color_generated, label='Generated Feature')
    ]
    plt.legend(handles=legend_elements, loc='lower right')
    
    # 调整布局，为 Figure text 留出空间
    # rect=[left, bottom, right, top]
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    
    # 使用 fig.text 强制在整个画布居中显示标题和底部标签
    # x=0.5 表示水平正中
    fig.text(0.5, 0.96, "Top 7 Features (Original + Generated) by RFE", 
             ha='center', va='top', fontsize=14)
             
    fig.text(0.5, 0.02, "Importance Score", 
             ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    output_file = 'rfe_chart_static.png'
    plt.savefig(output_file, dpi=300)
    print(f"Chart saved to {output_file}")

if __name__ == "__main__":
    plot_static_rfe()
