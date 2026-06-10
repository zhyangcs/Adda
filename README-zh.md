# Adda

在这个仓库中，我们介绍了Adda，一个由智能体协作支持的自动化特征工程工具。

<div style="text-align: center;">
<img src="./img/overview.png" alt="概览图" width="70%">
</div>

## 项目目录结构

```
autofe/
├── src/                          # 源代码目录
│   ├── llm/                      # LLM相关模块
│   │   ├── agents/               # AI智能体
│   │   ├── tests/                # 测试工具
│   │   └── utils/                # 工具函数
│   ├── clib/                     # C++库组件
│   └── env.py                    # 环境配置
├── benchmark/                    # 基准测试工具
│   ├── adda_benchmark_test.py    # 核心基准测试框架
│   ├── run_benchmark_example.py  # 交互式测试启动器
│   ├── test_openai_simple.py     # 简单OpenAI测试
│   ├── test_openai_prompt.py     # 完整OpenAI测试
│   ├── watch_logs.py            # 日志监控工具
│   ├── logs/                     # 基准测试日志
│   └── results/                  # 基准测试结果
├── dataset/                      # 数据集存储
├── test/                         # 测试结果和输出
├── frontend/                     # 前端组件
├── pd2sql/                       # Pandas到SQL转换
├── img/                          # 图片和图表
├── logs/                         # 日志文件
├── report/                       # 生成的报告
├── requirements.txt              # Python依赖
├── README.md                     # 英文文档
└── README-zh.md                  # 中文文档
```

## 前置条件

### 1. 安装Python库
```sh
pip install -r requirements.txt
```
您应该根据您的GPU安装合适的`torch`版本。

### 2. 安装C++库
您应该在服务器上安装`armadillo`和`postgres database`。

### 3. 配置环境变量
在`src/env.py`中您可以设置项目的可配置变量，特别是`openai_api_key`和`rag_model_id_or_path`。

### 4. 配置pl/python环境
如果使用conda环境，可能出现pl/python3使用的解释器和conda下的python解释器不一致的情况。这时候，使用如下指令：

```bash
# 一般的安装指令
/usr/bin/python3 -m pip install pandas scikit-learn xgboost lightgbm

# 或者
sudo -u pip install pandas scikit-learn xgboost lightgbm

# 如果是root用户
su - postgres -c "pip install pandas scikit-learn xgboost lightgbm"
```

## 代码执行示例

### 0. 启动PostgreSQL服务

#### 使用系统安装的PostgreSQL
```bash
service postgresql start
```

#### 使用conda环境安装的PostgreSQL
如果通过conda安装的PostgreSQL，启动方式如下：

1. **激活Conda环境**
首先，确保您已经激活了安装PostgreSQL的Conda环境：
```bash
# 假设您的环境名为autofe
conda activate autofe
```

2. **初始化数据库（仅首次使用）**
```bash
# 创建数据目录
mkdir -p ~/conda_postgres_data

# 初始化数据库
initdb -D ~/conda_postgres_data
```

3. **启动PostgreSQL服务**
使用`pg_ctl`命令启动服务：
```bash
# -D 指定数据目录
# -l 指定日志文件路径，这对于排查问题非常有用
pg_ctl -D ~/conda_postgres_data -l ~/conda_postgres_logfile start
```

如果成功，您会看到：
```
waiting for server to start.... done
server started
```

4. **检查服务状态**
```bash
# 检查服务器是否正在运行
pg_ctl -D ~/conda_postgres_data status
```

5. **停止PostgreSQL服务**
```bash
# 安全地停止服务
pg_ctl -D ~/conda_postgres_data stop
```

6. **重启服务**
如果您修改了配置文件，重启服务：
```bash
# 重启服务以应用新配置
pg_ctl -D ~/conda_postgres_data restart
```

7. **基本使用**
```bash
# 连接到数据库（先检查日志文件中的端口）
psql -p 5431 -d postgres  # 使用日志文件中的实际端口

# 创建新数据库
createdb your_database_name

# 连接到指定数据库
psql -p 5431 -d your_database_name
```

**注意事项：**
- **使用`pg_ctl`前务必先激活Conda环境**
- 确保conda环境已激活
- 如果遇到权限问题，可能需要设置环境变量 `PGDATA=~/conda_postgres_data`
- 日志文件会记录在 `~/conda_postgres_logfile` 中，可用于排查问题
- **重要：conda安装的PostgreSQL可能使用非标准端口（如5431而不是5432）**
- 如果psql连接失败，请检查日志文件中的端口信息，然后使用 `psql -p 端口号` 连接
- 例如：`psql -p 5431 -d postgres` 而不是 `psql`
- 核心命令是`pg_ctl start`，但一定要记得先**激活Conda环境**并用**`-D`**参数指定正确的数据目录

### 1. 下载必要数据
您可以从 https://drive.google.com/file/d/1qTUpAEn25_-9CUEnk1IgCsvQMkn62R-Z/view?usp=sharing 下载数据，并解压到项目的./data目录中。

### 2. 特征生成
包括将原始CSV导入到PostgreSQL，然后进行特征工程。您可以指定task_name和model_type：
```python
python src/llm/tests/test_util.py --task_name heart --model_type RF
```

### 3. 数据库内计算
```python
python src/run_multimodel_type.py --task_name heart --model_type RF
```
通过这个命令您可以在终端中看到预测分数。

## 待办事项：
- [ ] 支持更便捷的训练和预测管道
- [ ] 支持更多C++版本的下游算法（目前是lightgbm）

## 测试和调试

### OpenAI Prompt 响应格式测试

这个测试脚本用于分析使用与 `nl_agent.py` 中相同的prompt调用OpenAI API得到的结果格式，帮助找出导致 "list index out of range Error:regrenerate the op_type" 错误的原因。

#### 问题分析

根据错误信息和代码分析，问题出现在 `nl_agent.py` 的第130行：

```python
op_type, out_attr, operation_desc, operation_desc_brief, rel_cols = (
    OpTypeEnum.UNSUPPORT if high_order else (OpTypeEnum.BINARY if "UNARY" not in parsed_response[0] else OpTypeEnum.DISCRETIZE)), 
    parse_string_to_list(parsed_response[-4]),  # 可能越界
    parsed_response[-3],                        # 可能越界
    parsed_response[-2],                        # 可能越界
    parse_string_to_list(parsed_response[-1])   # 可能越界
)
```

#### 测试脚本说明

1. **`test_openai_simple.py` (推荐使用)**
   - **功能**: 简化的测试脚本，快速验证LLM响应格式
   - **特点**: 轻量级，易于理解和调试
   - **用途**: 快速定位问题

2. **`test_openai_prompt.py`**
   - **功能**: 完整的测试脚本，包含更多测试场景
   - **特点**: 功能全面，包含详细的解析逻辑模拟
   - **用途**: 深入分析和调试

#### 使用方法

**环境准备:**
```bash
# 安装依赖
pip install openai

# 设置环境变量
export OPENAI_API_KEY='your-api-key-here'
# 或者使用自定义的OpenAI兼容API
export OPENAI_BASE_URL='https://your-api-endpoint.com/v1'
```

**运行测试:**
```bash
# 快速测试 (推荐)
python test_openai_simple.py

# 完整测试
python test_openai_prompt.py
```

#### 测试内容

1. **模拟响应测试**
   - ✅ **标准格式**: 包含所有4个必需字段
   - ⚠️ **格式不完整**: 缺少某些字段
   - ❌ **格式错误**: 格式不符合预期
   - ❌ **完全错误**: 完全不相关的响应

2. **解析逻辑测试**
   - `parse_nl_comma()` 方法
   - `parse_one_comma()` 方法
   - 正则表达式匹配
   - 字段提取和清理

3. **索引访问测试**
   - 访问 `parsed_response[-4]`
   - 访问 `parsed_response[-3]`
   - 访问 `parsed_response[-2]`
   - 访问 `parsed_response[-1]`

4. **实际API调用测试**
   - 发送相同的prompt
   - 分析实际响应格式
   - 测试解析逻辑

#### 预期输出格式

LLM应该返回以下格式的响应：

```
'new_feature': 'feature_name'
'detailed description': 'detailed description of the feature'
'brief description': 'brief description'
'relevant': ['col1', 'col2', 'col3']
```

#### 问题诊断

**常见问题:**

1. **行数不匹配**
   - 期望4行，实际少于4行
   - 原因：LLM没有按照要求格式输出

2. **正则匹配失败**
   - 响应格式不符合 `'field': value` 的格式
   - 原因：LLM使用了不同的格式

3. **索引越界**
   - 尝试访问 `parsed_response[-4]` 但列表长度不足4
   - 原因：解析失败导致返回空列表

**解决方案:**

1. **改进prompt**
   - 更明确地要求输出格式
   - 添加示例和格式说明

2. **增强解析逻辑**
   - 添加响应格式验证
   - 实现重试机制

3. **安全索引访问**
   - 在访问前检查列表长度
   - 使用条件表达式避免越界

#### 调试建议

1. **先运行模拟测试**，了解解析逻辑
2. **检查环境变量**，确保API配置正确
3. **观察实际API响应**，分析格式问题
4. **对比期望和实际**，找出差异点

#### 相关文件

- `src/llm/agents/nl_agent.py`: 原始代码文件
- `src/llm/utils/prompt.py`: Prompt模板定义
- `src/llm/utils/llm_util.py`: LLM工具函数

#### 注意事项

- 测试脚本会消耗OpenAI API配额
- 建议先使用模拟测试验证逻辑
- 保存成功的响应格式作为参考
- 根据测试结果调整原始代码的解析逻辑

## 基准测试

### Adda基准测试工具使用指南

这套基准测试工具可以自动化测试Adda在不同数据集和机器学习模型组合下的性能表现。工具包括两个主要脚本：

- `benchmark/adda_benchmark_test.py`: 核心测试框架
- `benchmark/run_benchmark_example.py`: 交互式测试启动器

#### 功能特性

**🎯 核心功能**
- **自动化测试**: 自动运行`test_util.py`和`run_multimodel_type.py`
- **重试机制**: 每个数据集-模型组合可以重试多次，保留最高分数
- **智能目录管理**: 自动处理重试时的目录冲突，备份之前的结果
- **详细报告**: 生成markdown和JSON格式的详细测试报告
- **进度跟踪**: 实时显示测试进度和结果

**📊 支持的数据集**
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

**🤖 支持的模型**
- `RF`: Random Forest (随机森林)
- `XGB`: XGBoost
- `LGBM`: LightGBM
- `CART`: Decision Tree (决策树)
- `ET`: Extra Trees (极端随机树)

#### 快速开始

**方法1: 使用交互式启动器 (推荐)**

```bash
python benchmark/run_benchmark_example.py
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

**方法2: 直接使用核心脚本**

**快速测试示例**
```bash
python benchmark/adda_benchmark_test.py \
    --datasets heart diabetes \
    --models RF XGB \
    --max-retries 2 \
    --timeout-hours 1.0 \
    --output-md quick_test_report.md
```

**完整测试示例**
```bash
python benchmark/adda_benchmark_test.py \
    --max-retries 3 \
    --timeout-hours 3.0 \
    --output-md full_benchmark_report.md \
    --output-json full_benchmark_results.json
```

#### 详细参数说明

**命令行参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--datasets` | 列表 | 所有数据集 | 要测试的数据集列表 |
| `--models` | 列表 | 所有模型 | 要测试的模型列表 |
| `--max-retries` | 整数 | 3 | 每个组合的最大重试次数 |
| `--timeout-hours` | 浮点数 | 2.0 | 单个测试的超时时间(小时) |
| `--output-md` | 字符串 | adda_benchmark_report.md | 输出的markdown报告文件 |
| `--output-json` | 字符串 | adda_benchmark_results.json | 输出的JSON结果文件 |

**使用示例**

1. **测试特定数据集**
```bash
python benchmark/adda_benchmark_test.py --datasets heart bank adult
```

2. **测试特定模型**
```bash
python benchmark/adda_benchmark_test.py --models RF XGB --datasets heart diabetes
```

3. **调整重试次数**
```bash
python benchmark/adda_benchmark_test.py --max-retries 5 --datasets heart
```

4. **设置超时时间**
```bash
python benchmark/adda_benchmark_test.py --timeout-hours 0.5 --datasets diabetes
```

#### 输出报告说明

**Markdown报告格式**

生成的markdown报告包含以下部分：

1. **详细测试结果表格**
| 数据集 | 模型 | 最佳得分 | 平均得分 | 尝试次数 | 所有得分 |
|--------|------|----------|----------|----------|----------|
| heart | RF | 0.8532 | 0.8401 | 3 | 0.8532, 0.8314, 0.8357 |

2. **按数据集汇总**
| 数据集 | 最高得分 | 平均得分 | 模型数量 |
|--------|----------|----------|----------|
| heart | 0.8532 | 0.8123 | 5 |

3. **按模型汇总**  
| 模型 | 最高得分 | 平均得分 | 数据集数量 |
|------|----------|----------|------------|
| RF | 0.8532 | 0.7845 | 14 |

4. **详细执行日志**
| 时间 | 数据集 | 模型 | 尝试次数 | 得分 |
|------|--------|------|----------|------|
| 14:23:15 | heart | RF | 1 | 0.8314 |

**JSON结果格式**

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

#### 重试机制和目录管理

**重试逻辑**
1. 每个数据集-模型组合最多重试`max_retries`次
2. 保留所有尝试中的最高分数
3. 如果某次尝试失败，会继续下一次尝试

**目录冲突处理**
当进行重试时，工具会自动处理目录冲突：

1. **检测冲突**: 检查`test/store/{dataset}_{model}_Full`目录是否存在
2. **备份重命名**: 将已存在的目录重命名为：
   ```
   {dataset}_{model}_Full_retry{N}_score{score}_{timestamp}
   ```
3. **创建新目录**: 为当前尝试创建干净的工作目录

**示例目录结构**
```
test/store/
├── heart_RF_Full/                           # 当前最佳结果
├── heart_RF_Full_retry1_score0.8314_20240115_142315/  # 第1次尝试备份
├── heart_RF_Full_retry2_score0.8357_20240115_143022/  # 第2次尝试备份
└── ...
```

#### 性能评估指标

- **分类任务**: 使用AUC (Area Under ROC Curve)
- **回归任务**: 使用1-RAE (1 - Relative Absolute Error)

分数越高表示性能越好。

#### 注意事项和最佳实践

**⚠️ 重要注意事项**

1. **时间消耗**: 完整测试可能需要数十小时，建议先进行快速测试
2. **资源需求**: 确保有足够的磁盘空间存储多次尝试的结果
3. **数据库连接**: 确保PostgreSQL服务正常运行
4. **API配额**: 注意OpenAI API的使用配额和费用

**💡 最佳实践**

1. **逐步测试**: 从快速测试开始，逐步扩大测试范围
2. **合理设置超时**: 根据数据集大小调整超时时间
3. **监控进度**: 使用`tail -f`监控日志文件
4. **备份结果**: 定期备份重要的测试结果

**📝 测试建议**

**快速验证 (10-30分钟)**
```bash
python benchmark/adda_benchmark_test.py \
    --datasets heart diabetes \
    --models RF XGB \
    --max-retries 1 \
    --timeout-hours 0.5
```

**中等规模测试 (2-4小时)**
```bash
python benchmark/adda_benchmark_test.py \
    --datasets heart diabetes titanic adult bank \
    --models RF XGB LGBM \
    --max-retries 2 \
    --timeout-hours 1.0
```

**论文复现级别测试 (数十小时)**
```bash
python benchmark/adda_benchmark_test.py \
    --max-retries 3 \
    --timeout-hours 3.0
```

#### 故障排除

**常见问题**

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

**调试技巧**

1. **查看详细日志**:
   ```bash
   python benchmark/adda_benchmark_test.py --datasets heart --models RF 2>&1 | tee debug.log
   ```

2. **实时监控日志**:
   ```bash
   # 监控最新的实时日志
   python benchmark/watch_logs.py
   
   # 列出所有可用的日志文件
   python benchmark/watch_logs.py --list
   
   # 监控指定的日志文件
   python benchmark/watch_logs.py --file logs/specific.log
   
   # 显示最后20行并实时监控
   python benchmark/watch_logs.py --lines 20
   
   # 使用Python实现监控（备用方案）
   python benchmark/watch_logs.py --python
   ```

3. **单独测试组件**:
   ```bash
   # 测试特征生成
   python src/llm/tests/test_util.py --task_name heart --model_type RF
   
   # 测试模型训练
   python src/run_multimodel_type.py --task_name heart --model_type RF
   ```

4. **检查配置**:
   ```bash
   python -c "from src.env import *; print(f'Project path: {proj_path}')"
   ```

#### 日志监控工具

**watch_logs.py** 是一个强大的实时日志查看器，提供以下功能：

**基本用法**:
```bash
# 监控最新的实时日志
python benchmark/watch_logs.py

# 列出所有可用的日志文件
python benchmark/watch_logs.py --list

# 监控指定的日志文件
python benchmark/watch_logs.py --file logs/specific.log

# 显示最后20行并实时监控
python benchmark/watch_logs.py --lines 20

# 使用Python实现监控（备用方案）
python benchmark/watch_logs.py --python
```

**高级功能**:
- **自动检测最新日志**: 自动找到最新的日志文件
- **彩色输出**: 根据日志级别显示不同颜色
- **多种监控模式**: 支持tail -f和Python实现两种方式
- **灵活的文件选择**: 支持模式匹配和指定文件

**参数说明**:
- `--file, -f`: 指定要监控的日志文件
- `--lines, -n`: 显示最后几行 (默认: 10)
- `--list, -l`: 列出所有可用的日志文件
- `--pattern, -p`: 日志文件匹配模式 (默认: *realtime.log)
- `--python`: 使用Python实现监控（备用方案）

**输出文件位置**:
- 所有基准测试的日志文件保存在 `benchmark/logs/` 目录
- 所有基准测试的结果文件保存在 `benchmark/results/` 目录
- 测试报告和JSON结果文件会自动创建在 `benchmark/results/` 目录下

#### 扩展和自定义

**添加新数据集**
1. 在`src/llm/tests/config.yaml`中添加配置
2. 将数据文件放入`dataset/task/{dataset_name}/`目录
3. 更新测试脚本中的`available_datasets`列表

**添加新模型**
1. 确保模型在Adda中已实现
2. 更新测试脚本中的`available_models`列表
3. 测试新模型的兼容性

**自定义评估指标**
修改`_parse_score_from_output`方法以支持新的输出格式。

## 注意事项
* 要添加新数据集，您应该遵循train_new.csv、data_agenda.txt和desc.txt的格式，并更新./src/llm/tests/config.yaml

* pd2sql基于另一个仓库 https://github.com/AmirPupko/pandas-to-sql 进行了修改
