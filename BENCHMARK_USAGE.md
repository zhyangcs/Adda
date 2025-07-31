# Adda基准测试工具使用指南

## 概述

这套基准测试工具可以自动化测试Adda在不同数据集和机器学习模型组合下的性能表现。工具包括两个主要脚本：

- `adda_benchmark_test.py`: 核心测试框架
- `run_benchmark_example.py`: 交互式测试启动器

## 功能特性

### 🎯 核心功能
- **自动化测试**: 自动运行`test_util.py`和`run_multimodel_type.py`
- **重试机制**: 每个数据集-模型组合可以重试多次，保留最高分数
- **智能目录管理**: 自动处理重试时的目录冲突，备份之前的结果
- **详细报告**: 生成markdown和JSON格式的详细测试报告
- **进度跟踪**: 实时显示测试进度和结果

### 📊 支持的数据集
根据`config.yaml`配置，支持以下数据集：

**分类任务**:
- `heart`: 心脏病风险预测
- `bank`: 银行营销响应预测  
- `adult`: 收入水平预测
- `titanic`: 泰坦尼克号生存预测
- `diabetes`: 糖尿病诊断
- `bar_pass`: 律师资格考试通过预测
- `labor`: 劳工状态预测
- `hepatitis`: 肝炎诊断

**回归任务**:
- `bike`: 自行车租赁需求预测
- `abalone`: 鲍鱼年龄预测
- `boston_house`: 波士顿房价预测
- `airfoil`: 机翼噪音预测
- `house_sale`: 房屋销售价格预测
- `medical`: 医疗费用预测

### 🤖 支持的模型
- `RF`: Random Forest (随机森林)
- `XGB`: XGBoost
- `LGBM`: LightGBM
- `DT`: Decision Tree (决策树)
- `ET`: Extra Trees (极端随机树)

## 快速开始

### 方法1: 使用交互式启动器 (推荐)

```bash
python run_benchmark_example.py
```

启动后会看到菜单：
```
============================================================
Adda基准测试工具
============================================================
请选择测试模式:
  1. 快速测试 (2个数据集, 2个模型, ~30分钟)
  2. 中等测试 (5个数据集, 3个模型, ~3小时)
  3. 完整测试 (所有数据集和模型, 数十小时)
  4. 自定义测试 (手动选择参数)
  5. 退出
```

### 方法2: 直接使用核心脚本

#### 快速测试示例
```bash
python adda_benchmark_test.py \
    --datasets heart diabetes \
    --models RF XGB \
    --max-retries 2 \
    --timeout-hours 1.0 \
    --output-md quick_test_report.md
```

#### 完整测试示例
```bash
python adda_benchmark_test.py \
    --max-retries 3 \
    --timeout-hours 3.0 \
    --output-md full_benchmark_report.md \
    --output-json full_benchmark_results.json
```

## 详细参数说明

### 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--datasets` | 列表 | 所有数据集 | 要测试的数据集列表 |
| `--models` | 列表 | 所有模型 | 要测试的模型列表 |
| `--max-retries` | 整数 | 3 | 每个组合的最大重试次数 |
| `--timeout-hours` | 浮点数 | 2.0 | 单个测试的超时时间(小时) |
| `--output-md` | 字符串 | adda_benchmark_report.md | 输出的markdown报告文件 |
| `--output-json` | 字符串 | adda_benchmark_results.json | 输出的JSON结果文件 |

### 使用示例

#### 1. 测试特定数据集
```bash
python adda_benchmark_test.py --datasets heart bank adult
```

#### 2. 测试特定模型
```bash
python adda_benchmark_test.py --models RF XGB --datasets heart diabetes
```

#### 3. 调整重试次数
```bash
python adda_benchmark_test.py --max-retries 5 --datasets heart
```

#### 4. 设置超时时间
```bash
python adda_benchmark_test.py --timeout-hours 0.5 --datasets diabetes
```

## 输出报告说明

### Markdown报告格式

生成的markdown报告包含以下部分：

#### 1. 详细测试结果表格
| 数据集 | 模型 | 最佳得分 | 平均得分 | 尝试次数 | 所有得分 |
|--------|------|----------|----------|----------|----------|
| heart | RF | 0.8532 | 0.8401 | 3 | 0.8532, 0.8314, 0.8357 |

#### 2. 按数据集汇总
| 数据集 | 最高得分 | 平均得分 | 模型数量 |
|--------|----------|----------|----------|
| heart | 0.8532 | 0.8123 | 5 |

#### 3. 按模型汇总  
| 模型 | 最高得分 | 平均得分 | 数据集数量 |
|------|----------|----------|------------|
| RF | 0.8532 | 0.7845 | 14 |

#### 4. 详细执行日志
| 时间 | 数据集 | 模型 | 尝试次数 | 得分 |
|------|--------|------|----------|------|
| 14:23:15 | heart | RF | 1 | 0.8314 |

### JSON结果格式

```json
{
  "metadata": {
    "datasets": ["heart", "diabetes"],
    "models": ["RF", "XGB"],
    "max_retries": 3,
    "generation_time": "2024-01-15T14:30:00"
  },
  "results": {
    "heart": {
      "RF": {
        "best_score": 0.8532,
        "all_scores": [0.8532, 0.8314, 0.8357],
        "num_attempts": 3,
        "average_score": 0.8401
      }
    }
  },
  "detailed_logs": [...]
}
```

## 重试机制和目录管理

### 重试逻辑
1. 每个数据集-模型组合最多重试`max_retries`次
2. 保留所有尝试中的最高分数
3. 如果某次尝试失败，会继续下一次尝试

### 目录冲突处理
当进行重试时，工具会自动处理目录冲突：

1. **检测冲突**: 检查`test/store/{dataset}_{model}_Full`目录是否存在
2. **备份重命名**: 将已存在的目录重命名为：
   ```
   {dataset}_{model}_Full_retry{N}_score{score}_{timestamp}
   ```
3. **创建新目录**: 为当前尝试创建干净的工作目录

### 示例目录结构
```
test/store/
├── heart_RF_Full/                           # 当前最佳结果
├── heart_RF_Full_retry1_score0.8314_20240115_142315/  # 第1次尝试备份
├── heart_RF_Full_retry2_score0.8357_20240115_143022/  # 第2次尝试备份
└── ...
```

## 性能评估指标

- **分类任务**: 使用AUC (Area Under ROC Curve)
- **回归任务**: 使用1-RAE (1 - Relative Absolute Error)

分数越高表示性能越好。

## 注意事项和最佳实践

### ⚠️ 重要注意事项

1. **时间消耗**: 完整测试可能需要数十小时，建议先进行快速测试
2. **资源需求**: 确保有足够的磁盘空间存储多次尝试的结果
3. **数据库连接**: 确保PostgreSQL服务正常运行
4. **API配额**: 注意OpenAI API的使用配额和费用

### 💡 最佳实践

1. **逐步测试**: 从快速测试开始，逐步扩大测试范围
2. **合理设置超时**: 根据数据集大小调整超时时间
3. **监控进度**: 使用`tail -f`监控日志文件
4. **备份结果**: 定期备份重要的测试结果

### 📝 测试建议

#### 快速验证 (10-30分钟)
```bash
python adda_benchmark_test.py \
    --datasets heart diabetes \
    --models RF XGB \
    --max-retries 1 \
    --timeout-hours 0.5
```

#### 中等规模测试 (2-4小时)
```bash
python adda_benchmark_test.py \
    --datasets heart diabetes titanic adult bank \
    --models RF XGB LGBM \
    --max-retries 2 \
    --timeout-hours 1.0
```

#### 论文复现级别测试 (数十小时)
```bash
python adda_benchmark_test.py \
    --max-retries 3 \
    --timeout-hours 3.0
```

## 故障排除

### 常见问题

1. **特征生成失败**
   - 检查数据集文件是否存在
   - 确认PostgreSQL连接正常
   - 检查OpenAI API配置

2. **模型训练失败** 
   - 检查生成的特征文件
   - 确认模型类型正确
   - 查看详细错误日志

3. **超时问题**
   - 增加`--timeout-hours`参数
   - 检查系统资源使用情况
   - 考虑减少测试规模

4. **目录权限问题**
   - 确保对`test/store`目录有写权限
   - 检查磁盘空间是否充足

### 调试技巧

1. **查看详细日志**:
   ```bash
   python adda_benchmark_test.py --datasets heart --models RF 2>&1 | tee debug.log
   ```

2. **单独测试组件**:
   ```bash
   # 测试特征生成
   python src/llm/tests/test_util.py --task_name heart --model_type RF
   
   # 测试模型训练
   python src/run_multimodel_type.py --task_name heart --model_type RF
   ```

3. **检查配置**:
   ```bash
   python -c "from src.env import *; print(f'Project path: {proj_path}')"
   ```

## 扩展和自定义

### 添加新数据集
1. 在`src/llm/tests/config.yaml`中添加配置
2. 将数据文件放入`dataset/task/{dataset_name}/`目录
3. 更新测试脚本中的`available_datasets`列表

### 添加新模型
1. 确保模型在Adda中已实现
2. 更新测试脚本中的`available_models`列表
3. 测试新模型的兼容性

### 自定义评估指标
修改`_parse_score_from_output`方法以支持新的输出格式。

---

## 联系和支持

如有问题或建议，请参考项目的原始README文档或联系项目维护者。