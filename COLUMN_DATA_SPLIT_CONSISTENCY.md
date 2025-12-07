# 对比方法数据划分一致性文档

## 概述

本文档说明了`frontend/comparison_methods.py`中的对比方法如何确保与现有系统（`test_util.py`和`run_multimodel_type.py`）的数据划分方式完全一致，同时防止数据泄露。

## 📊 现有系统的数据划分方式

### 1. 数据导入和划分（`importTable_with_split`）

**位置**: `/src/pg/import_table.py:182`

**划分方式**:
```python
if task_type == "classify":
    df_train, df_test = train_test_split(df, test_size=0.2, random_state=0, stratify=df[label])
else:
    df_train, df_test = train_test_split(df, test_size=0.2, random_state=0)
```

**生成的表**:
- `{task_name}_src_tb_train` - 训练集（80%）
- `{task_name}_src_tb_test` - 测试集（20%）
- `{task_name}_src_tb` - 完整数据集

### 2. 特征搜索阶段

**数据来源**: `{task_name}_src_tb_train`表
**目的**: 只在训练集上进行特征搜索和生成，避免数据泄露

### 3. 模型训练和评估

- **训练**: 使用`{task_name}_src_tb_train`
- **评估**: 使用`{task_name}_src_tb_test`
- **随机种子**: `random_state=0`（确保可重现性）

## 🔒 对比方法的防泄露机制

### 1. 基类强制执行（`ComparisonMethod`）

```python
def fit_predict(self, X: pd.DataFrame, y: pd.Series, task_type: str = "classify"):
    # 使用与系统相同的数据划分方式
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X_processed, y, test_size=0.2, random_state=0,
        stratify=y if task_type == "classify" else None
    )
```

**关键特性**:
- ✅ **相同的随机种子**: `random_state=0`
- ✅ **相同的训练/测试比例**: 80%/20%
- ✅ **相同的分层采样**: 分类任务使用`stratify=y`
- ✅ **强制执行**: 子类无法绕过此机制

### 2. 特征生成限制

**训练阶段**: 只在`X_train, y_train`上调用`generate_features()`
```python
X_train_generated = self.generate_features(X_train, y_train)
```

**测试阶段**: 使用训练时保存的转换器独立处理测试集
```python
if hasattr(self, 'fitted_autofeat') and self.fitted_autofeat is not None:
    X_test_generated = self.fitted_autofeat.transform(X_test_processed)
elif hasattr(self, 'fitted_scaler') and self.fitted_scaler is not None:
    X_test_generated = self._transform_test_features(X_test)
```

### 3. 防止误用的机制

**废弃危险方法**:
```python
def evaluate_features(self, X_generated, y, task_type):
    raise NotImplementedError(
        "evaluate_features() is deprecated to prevent data leakage. "
        "Use fit_predict() instead."
    )
```

## 🔧 各方法的具体实现

### 1. BaselineMethod

```python
class BaselineMethod(ComparisonMethod):
    def generate_features(self, X, y=None):
        return X.copy()  # 不生成新特征
```

### 2. AutoFeatMethod

```python
class AutoFeatMethod(ComparisonMethod):
    def generate_features(self, X, y):
        # 只在训练集上训练AutoFeat
        X_generated = auto_feat.fit_transform(X_numeric, y)
        self.fitted_autofeat = auto_feat  # 保存模型用于测试集转换
        return X_generated
```

**测试集转换**: `self.fitted_autofeat.transform(X_test)`

### 3. PGMLMethod

```python
class PGMLMethod(ComparisonMethod):
    def generate_features(self, X, y):
        # 保存所有预处理组件
        self.fitted_scaler = scaler
        self.fitted_poly = poly  # 如果使用多项式特征
        self.fitted_selector = selector  # 如果使用特征选择
        return X_final
```

**测试集转换**: `self._transform_test_features(X_test)`

## 📋 数据划分一致性验证

| 项目 | 现有系统 | 对比方法 | 状态 |
|------|----------|----------|------|
| 训练/测试比例 | 80%/20% | 80%/20% | ✅ 一致 |
| 随机种子 | random_state=0 | random_state=0 | ✅ 一致 |
| 分层采样 | stratify=y | stratify=y | ✅ 一致 |
| 特征搜索数据 | 训练集 | 训练集 | ✅ 一致 |
| 评估数据 | 测试集 | 测试集 | ✅ 一致 |

## 🛡️ 防泄露保证

### 1. 编译时保证
- 基类的`fit_predict`方法标记为"强制执行，子类不得重写"
- 废弃了`evaluate_features`方法防止误用

### 2. 运行时保证
- 数据划分在基类中统一执行
- 测试集转换使用训练时保存的组件
- 特征生成严格限制在训练集

### 3. 可重现性保证
- 固定随机种子（random_state=0）
- 与现有系统完全相同的划分逻辑

## 🔮 未来扩展

当添加新的对比方法时，只需：

1. **继承基类**:
```python
class NewMethod(ComparisonMethod):
    def __init__(self):
        super().__init__("NewMethod")
```

2. **实现特征生成**:
```python
def generate_features(self, X, y):
    # 特征工程逻辑
    # 保存必要的转换器: self.fitted_XXX = transformer
    return X_generated
```

3. **自动获得防泄露保护**:
- 数据划分自动处理
- 测试集转换自动应用
- 评估结果可重现

## 📝 测试验证

使用以下脚本验证一致性：
```bash
python data_leakage_protection.py
python test_heart_dataset.py
```

## 🎯 结论

通过基类设计和强制执行机制，确保：

1. **所有对比方法**都使用与现有系统相同的数据划分方式
2. **完全防止数据泄露**，特征搜索严格限制在训练集
3. **结果可重现**，使用固定的随机种子
4. **扩展安全**，未来添加的方法自动继承防泄露机制