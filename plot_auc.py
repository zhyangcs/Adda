import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

labels = ["adda", "caafe", "madlib"]
values = [73.93, 72.55, 55.53]

plt.figure(figsize=(6, 4))
ax = plt.gca()

# 样式调整：三种不同颜色
# 蓝色, 橙色, 绿色
bar_colors = ["#4C78A8", "#F58518", "#54A24B"] 
bars = plt.bar(labels, values, color=bar_colors, width=0.6, zorder=3)

# Y轴设置
plt.ylabel("AUC", fontsize=12, fontweight='bold')
plt.ylim(0, 100)

# 去掉上、右、左边框，只保留底部
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_visible(False) # 不需要Y轴轴线
ax.spines['bottom'].set_color('black')

# 添加水平网格
ax.yaxis.grid(True, linestyle='-', which='major', color='lightgray', alpha=0.7, zorder=0)

# X轴标签水平
plt.xticks(rotation=0)
ax.tick_params(axis='x', length=0) # 去掉X轴刻度短线

# 去掉Y轴刻度短线，但保留数字 (length=0)
ax.tick_params(axis='y', length=0)

plt.tick_params(axis='both', which='major', labelsize=10)

plt.tight_layout()
output_file = 'auc_chart_styled.png'
plt.savefig(output_file, dpi=300)
print(f"Chart saved to {output_file}")
