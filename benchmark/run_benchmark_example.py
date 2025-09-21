#!/usr/bin/env python3
"""
Adda基准测试使用示例
这个脚本展示了如何使用adda_benchmark_test.py进行不同规模的测试
"""

import subprocess
import sys
import os
import json
from typing import Dict, List, Tuple

# Reference data from example_result.md
TABLE4_REFERENCE = {
    # Dataset: (max_score, avg_score)
    "heart": (73.93, 68.32),
    "bank": (94.83, 90.13),
    "adult": (83.25, 76.11),
    "titanic": (84.22, 81.54),
    "diabetes": (86.68, 82.60),
    "bar_pass": (85.09, 80.32),
    "labor": (99.54, 98.16),
    "hepatitis": (98.14, 95.10),
    "bike": (99.49, 98.87),
    "abalone": (45.23, 35.73),
    "boston_house": (58.58, 55.04),
    "airfoil": (82.86, 77.65),
    "house_sale": (72.52, 69.30),
    "medical": (89.59, 88.62)
}

TABLE5_REFERENCE = {
    # Dataset: (max_score, avg_score)
    "heart": (73.94, 65.59),
    "bank": (94.57, 83.63),
    "adult": (83.26, 71.77),
    "titanic": (81.34, 73.62),
    "diabetes": (86.33, 80.66),
    "bar_pass": (85.10, 75.39),
    "labor": (99.16, 96.25),
    "hepatitis": (97.14, 95.04),
    "bike": (99.16, 98.53),
    "abalone": (40.22, 32.12),
    "boston_house": (58.58, 51.42),
    "airfoil": (77.91, 72.63),
    "house_sale": (71.51, 64.91),
    "medical": (89.11, 87.40)
}

def generate_comparison_report(results_file: str, table_type: str):
    """生成对比报告，比较benchmark结果与参考表格结果"""
    if not os.path.exists(results_file):
        print(f"警告: 结果文件 {results_file} 不存在，无法生成对比报告")
        return
    
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            local_results = json.load(f)
    except Exception as e:
        print(f"错误: 无法读取结果文件 {results_file}: {e}")
        return
    
    reference_data = TABLE4_REFERENCE if table_type == "table4" else TABLE5_REFERENCE
    table_name = "Table 4" if table_type == "table4" else "Table 5"
    
    # 生成对比报告
    report_filename = f"{table_type}_comparison_report.md"
    
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(f"# {table_name} 实验对比报告\n\n")
        f.write(f"## 实验配置\n")
        if table_type == "table4":
            f.write("- **模型**: RF, XGB, LGBM, CART, ET (5种下游算法)\n")
        else:
            f.write("- **模型**: CART, RF (2种下游算法)\n")
        f.write("- **数据集**: 14个基准数据集\n")
        f.write("- **对比**: Adda Local (本地运行) vs Adda (论文结果)\n\n")
        
        # 添加测试摘要信息
        if 'metadata' in local_results:
            metadata = local_results['metadata']
            f.write(f"## 测试摘要\n\n")
            f.write(f"- **测试时间**: {metadata.get('generation_time', 'N/A')}\n")
            f.write(f"- **原始测试记录数**: {metadata.get('total_raw_records', 'N/A')}\n")
            f.write(f"- **最大重试次数**: {metadata.get('max_retries', 'N/A')}\n\n")
        
        f.write("## 详细对比结果\n\n")
        f.write("| 数据集 | Adda最大值 | Adda Local最大值 | 最大值变化 | Adda平均值 | Adda Local平均值 | 平均值变化 |\n")
        f.write("|--------|------------|------------------|------------|------------|------------------|------------|\n")
        
        total_max_improvements = []
        total_avg_improvements = []
        
        for dataset in reference_data:
            ref_max, ref_avg = reference_data[dataset]
            
            # 从final_results中提取结果（新格式）
            local_max = local_avg = None
            if 'final_results' in local_results and dataset in local_results['final_results']:
                dataset_result = local_results['final_results'][dataset]
                local_max = dataset_result.get('max_score')
                local_avg = dataset_result.get('avg_score')
            elif 'results' in local_results:
                # 兼容旧格式
                for result in local_results['results']:
                    if result.get('dataset') == dataset and result.get('status') == 'success':
                        local_max = result.get('max_score')
                        local_avg = result.get('avg_score')
                        break
            
            if local_max is not None and local_avg is not None and local_max > 0:
                max_change = local_max - ref_max
                avg_change = local_avg - ref_avg
                max_percent = (max_change / ref_max) * 100
                avg_percent = (avg_change / ref_avg) * 100
                
                total_max_improvements.append(max_percent)
                total_avg_improvements.append(avg_percent)
                
                max_change_str = f"{max_change:+.2f} ({max_percent:+.1f}%)"
                avg_change_str = f"{avg_change:+.2f} ({avg_percent:+.1f}%)"
                
                f.write(f"| {dataset} | {ref_max:.2f} | {local_max:.2f} | {max_change_str} | {ref_avg:.2f} | {local_avg:.2f} | {avg_change_str} |\n")
            else:
                f.write(f"| {dataset} | {ref_max:.2f} | N/A | N/A | {ref_avg:.2f} | N/A | N/A |\n")
        
        # 生成总结
        f.write("\n## 总结\n\n")
        if total_max_improvements and total_avg_improvements:
            avg_max_improvement = sum(total_max_improvements) / len(total_max_improvements)
            avg_avg_improvement = sum(total_avg_improvements) / len(total_avg_improvements)
            
            successful_runs = len(total_max_improvements)
            total_datasets = len(reference_data)
            
            f.write(f"- **成功运行数据集**: {successful_runs}/{total_datasets}\n")
            f.write(f"- **最大值平均变化**: {avg_max_improvement:+.2f}%\n")
            f.write(f"- **平均值平均变化**: {avg_avg_improvement:+.2f}%\n\n")
            
            # 统计上升和下降的数据集
            max_improvements = [x for x in total_max_improvements if x > 0]
            max_declines = [x for x in total_max_improvements if x < 0]
            avg_improvements = [x for x in total_avg_improvements if x > 0]
            avg_declines = [x for x in total_avg_improvements if x < 0]
            
            f.write(f"### 最大值性能变化\n")
            f.write(f"- **提升数据集**: {len(max_improvements)}个\n")
            f.write(f"- **下降数据集**: {len(max_declines)}个\n")
            if max_improvements:
                f.write(f"- **平均提升幅度**: {sum(max_improvements)/len(max_improvements):.2f}%\n")
            if max_declines:
                f.write(f"- **平均下降幅度**: {sum(max_declines)/len(max_declines):.2f}%\n")
            
            f.write(f"\n### 平均值性能变化\n")
            f.write(f"- **提升数据集**: {len(avg_improvements)}个\n")
            f.write(f"- **下降数据集**: {len(avg_declines)}个\n")
            if avg_improvements:
                f.write(f"- **平均提升幅度**: {sum(avg_improvements)/len(avg_improvements):.2f}%\n")
            if avg_declines:
                f.write(f"- **平均下降幅度**: {sum(avg_declines)/len(avg_declines):.2f}%\n")
        else:
            f.write("- **警告**: 无法获取本地运行结果进行对比\n")
        
        # 添加详细的原始数据分析（如果可用）
        if 'raw_results' in local_results:
            raw_results = local_results['raw_results']
            total_tests = len(raw_results)
            successful_tests = len([r for r in raw_results if r.get('success', False)])
            success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
            
            f.write(f"\n## 原始测试数据统计\n\n")
            f.write(f"- **总测试次数**: {total_tests}\n")
            f.write(f"- **成功测试次数**: {successful_tests}\n")
            f.write(f"- **成功率**: {success_rate:.1f}%\n")
            
            # 按数据集统计成功率
            f.write(f"\n### 各数据集成功率\n\n")
            f.write("| 数据集 | 总尝试次数 | 成功次数 | 成功率 |\n")
            f.write("|--------|------------|----------|--------|\n")
            
            for dataset in reference_data:
                dataset_tests = [r for r in raw_results if r.get('dataset') == dataset]
                dataset_successes = [r for r in dataset_tests if r.get('success', False)]
                dataset_success_rate = (len(dataset_successes) / len(dataset_tests) * 100) if dataset_tests else 0
                
                f.write(f"| {dataset} | {len(dataset_tests)} | {len(dataset_successes)} | {dataset_success_rate:.1f}% |\n")
    
    print(f"对比报告已生成: {report_filename}")

def run_quick_test():
    """快速测试：只测试2个数据集和2个模型"""
    print("=" * 50)
    print("快速测试模式")
    print("测试数据集: heart, diabetes")
    print("测试模型: RF, XGB")
    print("重试次数: 2")
    print("=" * 50)
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"benchmark/logs/quick_test_{timestamp}.log"
    
    cmd = [
        sys.executable, "benchmark/adda_benchmark_test.py",
        "--datasets", "heart", "diabetes",
        "--models", "RF", "XGB", 
        "--max-retries", "2",
        "--single-timeout-minutes", "15",
        "--log-file", log_file,
        "--output-md", "benchmark/results/quick_test_report.md",
        "--output-json", "benchmark/results/quick_test_results.json"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print(f"日志文件: {log_file}")
    
    subprocess.run(cmd)

def run_medium_test():
    """中等测试：测试5个数据集和3个模型"""
    print("=" * 50)
    print("中等测试模式")
    print("测试数据集: heart, diabetes, titanic, adult, bank")
    print("测试模型: RF, XGB, LGBM")
    print("重试次数: 3")
    print("=" * 50)
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"benchmark/logs/medium_test_{timestamp}.log"
    
    cmd = [
        sys.executable, "benchmark/adda_benchmark_test.py",
        "--datasets", "heart", "diabetes", "titanic", "adult", "bank",
        "--models", "RF", "XGB", "LGBM",
        "--max-retries", "3",
        "--single-timeout-minutes", "20",
        "--log-file", log_file,
        "--output-md", "benchmark/results/medium_test_report.md",
        "--output-json", "benchmark/results/medium_test_results.json"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print(f"日志文件: {log_file}")
    
    subprocess.run(cmd)

def run_full_test():
    """完整测试：测试所有数据集和所有模型"""
    print("=" * 50)
    print("完整测试模式")
    print("测试数据集: 所有可用数据集")
    print("测试模型: 所有可用模型")
    print("重试次数: 3")
    print("警告：此测试可能需要数十小时完成！")
    print("=" * 50)
    
    response = input("确认要运行完整测试吗？(yes/no): ")
    if response.lower() != 'yes':
        print("测试已取消")
        return
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"benchmark/logs/full_test_{timestamp}.log"
    
    cmd = [
        sys.executable, "benchmark/adda_benchmark_test.py",
        "--max-retries", "3",
        "--single-timeout-minutes", "30",
        "--log-file", log_file,
        "--output-md", "benchmark/results/full_test_report.md",
        "--output-json", "benchmark/results/full_test_results.json"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print(f"日志文件: {log_file}")
    
    subprocess.run(cmd)

def run_custom_test():
    """自定义测试：用户指定参数"""
    print("=" * 50)
    print("自定义测试模式")
    print("=" * 50)
    
    # 显示可用选项
    available_datasets = [
        "heart", "bank", "adult", "titanic", "diabetes", "bar_pass", 
        "labor", "hepatitis", "bike", "abalone", "boston_house", 
        "airfoil", "house_sale", "medical"
    ]
    available_models = ["RF", "XGB", "LGBM", "CART", "ET"]
    
    print("可用数据集:")
    for i, dataset in enumerate(available_datasets, 1):
        print(f"  {i:2}. {dataset}")
    
    print("\n可用模型:")
    for i, model in enumerate(available_models, 1):
        print(f"  {i}. {model}")
    
    # 用户输入
    print("\n请选择要测试的数据集（用空格分隔编号，如：1 2 3）:")
    dataset_indices = input().strip().split()
    selected_datasets = []
    for idx in dataset_indices:
        try:
            selected_datasets.append(available_datasets[int(idx) - 1])
        except (ValueError, IndexError):
            print(f"无效的数据集编号: {idx}")
            return
    
    print("\n请选择要测试的模型（用空格分隔编号，如：1 2）:")
    model_indices = input().strip().split()
    selected_models = []
    for idx in model_indices:
        try:
            selected_models.append(available_models[int(idx) - 1])
        except (ValueError, IndexError):
            print(f"无效的模型编号: {idx}")
            return
    
    max_retries = input("\n最大重试次数 (默认3): ").strip()
    max_retries = int(max_retries) if max_retries else 3
    
    single_timeout = input("单次尝试超时时间(分钟，默认20): ").strip()
    single_timeout = int(single_timeout) if single_timeout else 20
    
    output_prefix = input("输出文件前缀 (默认custom_test): ").strip()
    output_prefix = output_prefix if output_prefix else "custom_test"
    
    print(f"\n配置确认:")
    print(f"  数据集: {selected_datasets}")
    print(f"  模型: {selected_models}")
    print(f"  重试次数: {max_retries}")
    print(f"  单次超时: {single_timeout}分钟")
    
    response = input("\n确认运行？(yes/no): ")
    if response.lower() != 'yes':
        print("测试已取消")
        return
    
    # 生成日志文件名
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"benchmark/logs/{output_prefix}_{timestamp}.log"
    
    cmd = [
        sys.executable, "benchmark/adda_benchmark_test.py",
        "--datasets"] + selected_datasets + [
        "--models"] + selected_models + [
        "--max-retries", str(max_retries),
        "--single-timeout-minutes", str(single_timeout),
        "--log-file", log_file,
        "--output-md", f"benchmark/results/{output_prefix}_report.md",
        "--output-json", f"benchmark/results/{output_prefix}_results.json"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print(f"日志文件: {log_file}")
    
    subprocess.run(cmd)

def run_table4_experiment():
    """Table 4实验：使用5种下游算法 (RF, XGB, LGBM, CART, ET)"""
    print("=" * 50)
    print("Table 4实验复现")
    print("使用5种下游算法: RF, XGB, LGBM, CART, ET")
    print("测试所有14个数据集")
    print("=" * 50)
    
    datasets = [
        "heart", "bank", "adult", "titanic", "diabetes", "bar_pass",
        "labor", "hepatitis", "bike", "abalone", "boston_house", 
        "airfoil", "house_sale", "medical"
    ]
    models = ["RF", "XGB", "LGBM", "CART", "ET"]
    
    response = input("确认运行Table 4实验？(yes/no): ")
    if response.lower() != 'yes':
        print("测试已取消")
        return
    
    # 生成日志文件名
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"benchmark/logs/table4_experiment_{timestamp}.log"
    
    cmd = [
        sys.executable, "benchmark/adda_benchmark_test.py",
        "--datasets"] + datasets + [
        "--models"] + models + [
        "--max-retries", "3",
        "--single-timeout-minutes", "30",
        "--log-file", log_file,
        "--output-md", "benchmark/results/table4_experiment_report.md",
        "--output-json", "benchmark/results/table4_experiment_results.json"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print(f"日志文件: {log_file}")
    print("开始执行...")
    
    subprocess.run(cmd)
    
    # 生成对比报告
    generate_comparison_report("benchmark/results/table4_experiment_results.json", "table4")

def run_table5_experiment():
    """Table 5实验：使用2种下游算法 (CART, RF)"""
    print("=" * 50)
    print("Table 5实验复现")
    print("使用2种下游算法: CART, RF")
    print("测试所有14个数据集")
    print("=" * 50)
    
    datasets = [
        "heart", "bank", "adult", "titanic", "diabetes", "bar_pass",
        "labor", "hepatitis", "bike", "abalone", "boston_house", 
        "airfoil", "house_sale", "medical"
    ]
    models = ["CART", "RF"]
    
    response = input("确认运行Table 5实验？(yes/no): ")
    if response.lower() != 'yes':
        print("测试已取消")
        return
    
    # 生成日志文件名
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"benchmark/logs/table5_experiment_{timestamp}.log"
    
    cmd = [
        sys.executable, "benchmark/adda_benchmark_test.py",
        "--datasets"] + datasets + [
        "--models"] + models + [
        "--max-retries", "3",
        "--single-timeout-minutes", "25",
        "--log-file", log_file,
        "--output-md", "benchmark/results/table5_experiment_report.md",
        "--output-json", "benchmark/results/table5_experiment_results.json"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print(f"日志文件: {log_file}")
    print("开始执行...")
    
    subprocess.run(cmd)
    
    # 生成对比报告
    generate_comparison_report("benchmark/results/table5_experiment_results.json", "table5")

def main():
    """主菜单"""
    while True:
        print("\n" + "=" * 60)
        print("Adda基准测试工具")
        print("=" * 60)
        print("请选择测试模式:")
        print("  1. 快速测试 (2个数据集, 2个模型, ~30分钟)")
        print("  2. 中等测试 (5个数据集, 3个模型, ~3小时)")
        print("  3. 完整测试 (所有数据集和模型, 数十小时)")
        print("  4. Table 4实验复现 (5种下游算法)")
        print("  5. Table 5实验复现 (2种下游算法)")
        print("  6. 自定义测试 (手动选择参数)")
        print("  7. 退出")
        
        choice = input("\n请输入选择 (1-7): ").strip()
        
        if choice == "1":
            run_quick_test()
        elif choice == "2":
            run_medium_test()
        elif choice == "3":
            run_full_test()
        elif choice == "4":
            run_table4_experiment()
        elif choice == "5":
            run_table5_experiment()
        elif choice == "6":
            run_custom_test()
        elif choice == "7":
            print("退出程序")
            break
        else:
            print("无效选择，请重试")

if __name__ == "__main__":
    # 检查必要的文件是否存在
    if not os.path.exists("benchmark/adda_benchmark_test.py"):
        print("错误: 找不到 benchmark/adda_benchmark_test.py 文件")
        print("请确保该文件在benchmark目录下")
        sys.exit(1)
    
    # 确保必要的目录存在
    os.makedirs("benchmark/logs", exist_ok=True)
    os.makedirs("benchmark/results", exist_ok=True)
    
    main()