# Mock ADDA Backend

模拟ADDA自动化特征工程系统的后端服务，提供与真实系统完全一致的API接口，用于前端开发和测试。

## 功能特性

### 🔄 完全兼容的API接口
- 与真实ADDA系统100%兼容的API端点
- 相同的请求参数格式和响应数据结构
- 支持FormData和JSON两种请求格式
- 完整的错误处理机制

### 🎭 逼真的Mock数据
- 多种数据集支持（Titanic, Heart, Bank, Diabetes, Bike, House）
- 动态生成的特征树结构
- 模拟的性能指标和SQL代码生成
- 渐进式的执行状态变化

### ⚡ 交互功能
- 模拟真实的异步执行延迟
- 支持多步骤的渐进式数据更新
- 节点选择和批量操作
- 实时通知系统

## 快速开始

### 1. 安装依赖

```bash
cd /home/lizhenyu/projects/autofe/mock-backend
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python app.py
```

服务将在 `http://localhost:5001` 启动。

### 3. 验证服务

访问健康检查端点：
```bash
curl http://localhost:5001/health
```

查看所有可用API：
```bash
curl http://localhost:5001/
```

## API端点

### 任务管理
- `POST /check-format/` - 初始化特征工程任务
- `POST /get-treejson/` - 获取特征树结构
- `POST /next-step/` - 执行下一步特征生成
- `POST /auto-step/` - 端到端自动化执行

### 性能测试
- `POST /test-performance/` - 测试选定节点性能
- `POST /gen-model/` - 生成并下载模型文件

### 任务控制
- `POST /stop-task/` - 停止当前任务
- `POST /clear-task/` - 清除任务状态
- `POST /check-task-status/` - 检查任务状态

### 通知系统
- `GET /get-notifications/` - 获取系统通知

### 系统
- `GET /health` - 健康检查
- `GET /` - 服务信息

## 使用示例

### 1. 初始化任务

```bash
curl -X POST http://localhost:5001/check-format/ \
  -H "Content-Type: application/json" \
  -d '{
    "taskDescription": "预测心脏病风险",
    "dataset": "2",
    "model": "1"
  }'
```

### 2. 端到端执行

```bash
curl -X POST http://localhost:5001/auto-step/ \
  -H "Content-Type: application/json" \
  -d '{
    "taskDescription": "预测心脏病风险",
    "dataset": "Heart",
    "model_type": "RF",
    "max_search_depth": 2,
    "use_performance_test": true
  }'
```

### 3. 获取特征树

```bash
curl -X POST http://localhost:5001/get-treejson/ \
  -H "Content-Type: application/json"
```

## 数据结构

### 特征树JSON结构

```json
{
  "root_id": "1",
  "parent_child_relations": [["1", "2"], ["1", "3"]],
  "node_info": [
    {
      "node_id": "1",
      "feature_name": "All original features",
      "task_code": "# Root node",
      "op_type": "root",
      "score": 0.0,
      "exec_time": 0.0,
      "operation_desc": "特征树根节点"
    }
  ],
  "cur_selected_idx": ["2", "3"]
}
```

### 性能测试结果

```json
{
  "status": "success",
  "performance_info": {
    "score": 0.85,
    "metric": "AUC",
    "selected_nodes": ["2", "3"],
    "in_db_ml": true,
    "node_count": 2,
    "method": "RF (In-Database)"
  },
  "sql_code": {
    "training_sql": "CREATE TABLE training_features AS...",
    "prediction_sql": "SELECT id, predict_random_forest...",
    "udf_sql": "CREATE OR REPLACE FUNCTION...",
    "all_sql": "-- 完整的ML流程"
  }
}
```

## 配置选项

### 环境变量

- `DEBUG` - 调试模式 (默认: True)
- `HOST` - 服务主机 (默认: localhost)
- `PORT` - 服务端口 (默认: 5001)

### 模拟延迟配置

在 `config.py` 中可以调整各种操作的模拟延迟：

```python
SIMULATION_DELAYS = {
    'check_format': 1.0,
    'get_treejson': 0.5,
    'next_step': 8.0,
    'auto_step': 12.0,
    'test_performance': 3.0,
    'gen_model': 2.0
}
```

## 与真实系统对比

| 特性 | 真实ADDA系统 | Mock后端 |
|------|-------------|----------|
| API接口 | ✅ 完整 | ✅ 完全兼容 |
| 数据格式 | ✅ 真实数据 | ✅ 模拟数据 |
| 执行时间 | 几分钟到几小时 | 几秒到几分钟 |
| LLM调用 | ✅ 真实API | ❌ 无需调用 |
| 数据库操作 | ✅ PostgreSQL | ❌ 内存模拟 |
| 成本 | 消耗tokens | 完全免费 |

## 开发说明

### 目录结构

```
mock-backend/
├── app.py                 # Flask应用主文件
├── config.py             # 配置文件
├── requirements.txt      # Python依赖
├── README.md            # 说明文档
├── data/                # Mock数据
│   ├── __init__.py
│   └── mock_data.py     # 数据生成器
├── routes/              # API路由
│   └── __init__.py
├── services/            # 业务逻辑
│   └── __init__.py
└── templates/           # 模板文件
```

### 扩展功能

如果需要添加新的Mock数据或修改API行为，主要编辑以下文件：

1. `config.py` - 添加配置选项
2. `data/mock_data.py` - 修改Mock数据生成逻辑
3. `app.py` - 添加新的API端点

## 故障排除

### 端口冲突
如果5001端口被占用，修改 `config.py` 中的PORT配置。

### CORS问题
确保前端URL在 `config.py` 的 `CORS_ORIGINS` 列表中。

### 性能问题
调整 `config.py` 中的 `SIMULATION_DELAYS` 来减少模拟延迟。

## 许可证

此Mock后端仅用于开发和测试目的。