# 重采样版本 LLM DAG 构造器

这是基于 `llm_dag_util_gp.py` 的简单重采样版本，主要特性：

## 主要功能

### 1. 分层采样
- **启用方法**: `use_stratified_sampling=True`
- **作用**: 保持训练数据中的类别分布比例
- **适用场景**: 分类任务，特别是类别不平衡的数据集

### 2. 定期动态重采样
- **参数**: `resample_interval=n`
- **作用**: 每执行n步A*搜索后，重新采样数据
- **优势**: 减少采样偏差，提高特征稳定性

## 使用方法

### 基本使用
```python
from src.llm.llm_dag_util_resample import LLMDagConstructor

# 创建构造器
constructor = LLMDagConstructor(
    task_type="classify",
    eval_model_type="RF",
    use_stratified_sampling=True,  # 启用分层采样
    sample_ratio=0.25,            # 采样25%的数据
    resample_interval=5           # 每5步重采样一次
)

# 正常使用A*搜索
constructor.astar_k_step(
    step_num=20,
    data_agenda=data_agenda,
    data_desc=data_desc,
    target_col="target",
    tb_name="dataset_name_src_tb_train",
    task_name="experiment_name"
)
```

### 参数说明
- `use_stratified_sampling`: 是否使用分层采样 (默认: True)
- `sample_ratio`: 采样比例，0.0-1.0 (默认: 0.25)
- `resample_interval`: 重采样间隔，设为0禁用动态重采样 (默认: 5)

## 与原版本的比较

| 特性 | 原版本 | 重采样版本 |
|------|--------|------------|
| 数据采样 | 固定采样 | 分层/动态重采样 |
| 类别平衡 | 可能不平衡 | 保持分布 |
| 计算开销 | 较低 | 中等(重采样时) |
| 适用场景 | 一般任务 | 类别不平衡任务 |

## 输出信息

运行时会显示重采样相关信息：
```
Stratified sampling: (731, 17) from (2924, 17)
Resampling data at step 3 (interval: 3)
Random sampling: (731, 17) from (2924, 17)
```

## 注意事项

1. **内存使用**: 需要保存完整数据集用于重采样
2. **计算时间**: 重采样会增加额外计算开销
3. **随机性**: 不同采样可能影响特征生成结果
4. **目标列**: 分层采样需要正确的目标列名

## 测试

运行测试脚本验证功能：
```bash
python test_resampling.py
```

查看使用示例：
```bash
python example_resampling_usage.py
```