#!/usr/bin/env python3
"""
从AutoFE生成的UDF SQL文件中提取新生成特征的定义
"""

import re
import os
import argparse

def extract_new_features_from_udf(udf_file_path):
    """
    从UDF SQL文件中提取新生成特征的定义
    """
    if not os.path.exists(udf_file_path):
        print(f"文件不存在: {udf_file_path}")
        return []

    with open(udf_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 使用正则表达式匹配特征定义模式
    # 匹配 df['feature_name'] = ... 的模式
    feature_pattern = r"df\['([^']+)'\]\s*=\s*(.+?)(?=\s*#|\s*$|\n\s*(?:df\[|import|#|return))"
    matches = re.findall(feature_pattern, content, re.MULTILINE | re.DOTALL)

    new_features = []

    for feature_name, feature_def in matches:
        # 跳过ID列的类型转换，这些不是新特征
        if 'astype' in feature_def:
            continue

        # 跳过一些明显不是新特征的操作
        if feature_name in ['id'] or 'fillna' in feature_def:
            continue

        new_features.append({
            'name': feature_name,
            'definition': feature_def.strip()
        })

    return new_features

def extract_new_features_from_sql(sql_file_path):
    """
    从SQL文件中通过比较输入输出列来推断新特征
    """
    if not os.path.exists(sql_file_path):
        print(f"文件不存在: {sql_file_path}")
        return []

    with open(sql_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取所有CREATE TYPE定义中的列名
    type_pattern = r"CREATE TYPE \w+ AS \((.*?)\);"
    type_matches = re.findall(type_pattern, content, re.DOTALL)

    all_columns = set()
    for type_def in type_matches:
        columns = [col.strip().split()[0] for col in type_def.split(',\n') if col.strip()]
        all_columns.update(columns)

    # 这里简化处理，实际应用中需要更复杂的逻辑来区分原始特征和新特征
    return list(all_columns)

def main():
    parser = argparse.ArgumentParser(description='提取AutoFE生成的新特征定义')
    parser.add_argument('--udf_file', type=str, help='UDF SQL文件路径')
    parser.add_argument('--sql_file', type=str, help='主SQL文件路径')
    parser.add_argument('--output', type=str, help='输出文件路径')

    args = parser.parse_args()

    new_features = []

    # 从UDF文件提取
    if args.udf_file:
        udf_features = extract_new_features_from_udf(args.udf_file)
        new_features.extend(udf_features)
        print(f"从UDF文件提取到 {len(udf_features)} 个新特征")

    # 输出结果
    if new_features:
        output_lines = []
        output_lines.append("# AutoFE生成的新特征定义\n")

        for i, feature in enumerate(new_features, 1):
            output_lines.append(f"## 特征 {i}: {feature['name']}")
            output_lines.append("```python")
            output_lines.append(f"df['{feature['name']}'] = {feature['definition']}")
            output_lines.append("```\n")

        result = "\n".join(output_lines)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"结果已保存到: {args.output}")
        else:
            print(result)
    else:
        print("未找到新特征定义")

if __name__ == "__main__":
    main()