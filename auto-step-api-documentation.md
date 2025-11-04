# Auto-Step API 接口文档

## 概述

`/auto-step/` 接口是 Adda 系统的端到端特征工程自动化接口，用于一键完成从数据导入到模型训练的完整流程。

## 接口信息

- **接口地址**: `/auto-step/`
- **请求方法**: `POST`
- **内容类型**: `multipart/form-data` 或 `application/json`
- **超时时间**: 10分钟（端到端流程可能需要较长时间）

## 请求参数

### 表单格式 (multipart/form-data)

| 参数名 | 类型 | 必填 | 描述 | 示例值 |
|--------|------|------|------|--------|
| taskDescription | string | 是 | 任务描述，说明特征工程的目标 | "预测心脏病患者的风险" |
| dataset | string | 是 | 数据集名称 | "Heart" |
| model | string | 是 | LLM模型名称 | "Openai-gpt4o" |
| max_search_depth | integer | 否 | A*搜索的最大深度，默认2 | 2 |
| use_performance_test | boolean | 否 | 是否执行性能测试，默认true | true |
| comparison_methods | string | 否 | 要对比的方法，JSON数组格式，默认["Adda", "AutoFeat"] | `["Adda", "AutoFeat"]` |

### JSON格式 (application/json)

```json
{
  "taskDescription": "预测心脏病患者的风险",
  "dataset": "Heart",
  "model": "Openai-gpt4o",
  "max_search_depth": 2,
  "use_performance_test": true,
  "comparison_methods": ["Adda", "AutoFeat"]
}
```

### comparison_methods 参数说明

`comparison_methods` 参数指定要在性能对比中包含的方法。可选值包括：

- **"Adda"** - 本系统的特征工程方法
- **"AutoFeat"** - AutoFeat自动化特征工程方法
- **"FeatureTools"** - FeatureTools特征合成方法
- **"DeepFeatureSynthesis"** - 深度特征合成方法
- **"Baseline"** - 基线方法（使用原始特征）

**默认值**: `["Adda", "AutoFeat"]`

**注意**: 当前版本暂不支持前端用户选择功能，使用默认方法列表。未来版本将支持用户在前端界面选择对比方法。

## 响应格式

### 成功响应

```json
{
  "status": "success",
  "message": "端到端执行完成！搜索深度: 2",
  "data": {
    // === 特征信息 (支持 FeatureInfoPanel) ===
    "featureInfo": {
      "description": "生成的特征描述文本...",
      "pythonCode": "import pandas as pd\nimport numpy as np\n...",
      "sqlCode": "SELECT age_group, chol_risk_ratio FROM heart_data WHERE..."
    },

    // === 性能对比数据 (支持 PerformanceComparisonChart) ===
    "performanceData": {
      "methods": ["Adda", "AutoFeat"],
      "auc": [0.89, 0.82],
      "f1": [0.87, 0.80],
      "accuracy": [0.88, 0.81],
      "precision": [0.86, 0.79],
      "recall": [0.88, 0.81]
    },

    // === 时间分析数据 (支持 TimeComparisonChart) ===
    "timeData": {
      "methods": ["Adda", "AutoFeat"],
      "totalTime": [120, 180],
      "trainingTime": [45, 120],
      "preprocessingTime": [30, 25],
      "featureGenerationTime": [35, 25],
      "evaluationTime": [10, 10]
    },

    // === 特征重要性数据 (支持 FeatureImportancePanel) ===
    "importanceData": {
      "shap": [
        {"feature": "age_group", "importance": 0.24},
        {"feature": "chol_risk_ratio", "importance": 0.18},
        {"feature": "heart_rate_reserve", "importance": 0.15}
      ],
      "ig": [
        {"feature": "age_group", "importance": 0.31},
        {"feature": "chol_risk_ratio", "importance": 0.22}
      ],
      "rfe": [
        {"feature": "age_group", "importance": 0.28},
        {"feature": "risk_score", "importance": 0.20}
      ],
      "fi": [
        {"feature": "age_group", "importance": 0.26},
        {"feature": "chol_risk_ratio", "importance": 0.19}
      ]
    },

    // === 其他系统字段 ===
    "status": "success",
    "tree": "...", // JSON格式的特征树结构
    "finished": true,
    "search_depth": 2,
    "performance_metrics": {
      "auc": 0.89,
      "execution_time": 120.5,
      "model_type": "RF",
      "method": "in_database_ml"
    },
    "sql_code": {
      "feature_generation": "SELECT ...",
      "model_training": "SELECT ...",
      "prediction": "SELECT ..."
    },
    "best_features": {
      "success": true,
      "feature_count": 5
    },
    "training_result": {
      "success": true,
      "message": "端到端流程完成！AUC: 0.8900"
    }
  }
}
```

### 错误响应

```json
{
  "status": "fail",
  "message": "任务描述不能为空",
  "error_details": "Missing required parameter: taskDescription"
}
```

## 数据结构说明

### featureInfo (特征信息)

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| description | string | 否 | Markdown格式的特征描述 |
| pythonCode | string | 否 | Python特征工程代码 |
| sqlCode | string | 否 | SQL特征生成代码 |

### performanceData (性能对比)

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| methods | string[] | 否 | 方法名称数组 |
| auc | number[] | 否 | AUC值数组 (0-1) |
| f1 | number[] | 否 | F1分数数组 (0-1) |
| accuracy | number[] | 否 | 准确率数组 (0-1) |
| precision | number[] | 否 | 精确率数组 (0-1) |
| recall | number[] | 否 | 召回率数组 (0-1) |

**注意**: `methods`数组长度必须与所有性能指标数组长度相同。

### timeData (时间分析)

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| methods | string[] | 否 | 方法名称数组 |
| totalTime | number[] | 否 | 总耗时数组 (秒) |
| trainingTime | number[] | 否 | 训练耗时数组 (秒) |
| preprocessingTime | number[] | 否 | 预处理耗时数组 (秒) |
| featureGenerationTime | number[] | 否 | 特征生成耗时数组 (秒) |
| evaluationTime | number[] | 否 | 评估耗时数组 (秒) |

### importanceData (特征重要性)

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| shap | FeatureImportanceItem[] | 否 | SHAP重要性数据 |
| ig | FeatureImportanceItem[] | 否 | Integrated Gradients重要性数据 |
| rfe | FeatureImportanceItem[] | 否 | RFE重要性数据 |
| fi | FeatureImportanceItem[] | 否 | 特征重要性数据 |

#### FeatureImportanceItem

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| feature | string | 是 | 特征名称 |
| importance | number | 是 | 重要性分数 (0-1) |

## 前端组件支持

该接口的数据结构完全支持以下前端组件：

1. **FeatureInfoPanel**: 显示特征描述、Python代码、SQL代码
2. **PerformanceComparisonChart**: 显示多方法性能对比柱状图
3. **TimeComparisonChart**: 显示多方法时间对比图
4. **FeatureImportancePanel**: 显示4种方法的特征重要性分析

## 空数据处理

所有数据字段都是可选的，前端组件能够优雅地处理空数据：

- 如果`featureInfo`为空，显示"No data available"
- 如果`performanceData`为空，显示空图表和"N/A"统计
- 如果`timeData`为空，显示空图表和时间占位符
- 如果`importanceData`为空，显示空的特征重要性图表

## 错误码说明

| 错误情况 | HTTP状态码 | 响应message |
|----------|------------|-------------|
| 缺少taskDescription | 400 | "缺少必要参数：taskDescription" |
| 无效的dataset | 400 | "无效的数据集名称" |
| 无效的model | 400 | "无效的模型名称" |
| A*搜索失败 | 500 | "A*搜索失败: [具体错误]" |
| 性能测试失败 | 500 | "性能测试失败: [具体错误]" |
| 系统内部错误 | 500 | "端到端执行失败: [具体错误]" |
| 执行超时 | 408 | "端到端执行超时" |

## 使用示例

### cURL 示例

```bash
curl -X POST http://localhost:5000/auto-step/ \
  -F "taskDescription=预测心脏病患者的风险" \
  -F "dataset=Heart" \
  -F "model=Openai-gpt4o" \
  -F "max_search_depth=2" \
  -F "use_performance_test=true" \
  -F "comparison_methods=[\"Adda\", \"AutoFeat\"]"
```

### JavaScript 示例

```javascript
const formData = new FormData();
formData.append('taskDescription', '预测心脏病患者的风险');
formData.append('dataset', 'Heart');
formData.append('model', 'Openai-gpt4o');
formData.append('max_search_depth', '2');
formData.append('use_performance_test', 'true');
formData.append('comparison_methods', JSON.stringify(["Adda", "AutoFeat"]));

const response = await fetch('/auto-step/', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log(result);
```

### JSON请求示例

```javascript
const requestData = {
  taskDescription: '预测心脏病患者的风险',
  dataset: 'Heart',
  model: 'Openai-gpt4o',
  max_search_depth: 2,
  use_performance_test: true,
  comparison_methods: ["Adda", "AutoFeat"]
};

const response = await fetch('/auto-step/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(requestData)
});

const result = await response.json();
console.log(result);
```

### Vue.js 示例

```javascript
// 在Vue组件中使用
const runEndToEndExecution = async () => {
  try {
    const response = await apiService.runAutoPipeline({
      description: '预测心脏病患者的风险',
      dataset: 'Heart',
      model: 'Openai-gpt4o',
      // 注意：当前版本使用默认对比方法 ["Adda", "AutoFeat"]，前端暂不提供选择功能
      comparison_methods: ["Adda", "AutoFeat"]
    });

    if (response.status === 'success') {
      // 数据将自动存储在taskStore.autoStepData中
      // 前端组件会自动更新显示
      console.log('端到端执行完成:', response.data);
    }
  } catch (error) {
    console.error('执行失败:', error);
  }
};
```

## 注意事项

1. **超时处理**: 端到端流程可能需要几分钟，建议设置合理的超时时间
2. **数据验证**: 所有传入参数都会在服务端进行验证
3. **资源清理**: 每次执行都会清理之前的任务状态，确保数据一致性
4. **错误处理**: 建议前端实现完善的错误处理和用户提示
5. **进度显示**: 由于是长时间运行的任务，建议前端显示进度和状态信息

## 版本信息

- **接口版本**: v1.0
- **最后更新**: 2025-01-31
- **兼容性**: 支持前端EndToEndContent.vue组件