#!/usr/bin/env python3
"""
Adda基准测试使用示例
这个脚本展示了如何使用adda_benchmark_test.py进行不同规模的测试
"""

import subprocess
import sys
import os

def run_quick_test():
    """快速测试：只测试2个数据集和2个模型"""
    print("=" * 50)
    print("快速测试模式")
    print("测试数据集: heart, diabetes")
    print("测试模型: RF, XGB")
    print("重试次数: 2")
    print("=" * 50)
    
    cmd = [
        sys.executable, "adda_benchmark_test.py",
        "--datasets", "heart", "diabetes",
        "--models", "RF", "XGB", 
        "--max-retries", "2",
        "--timeout-hours", "1.0",
        "--output-md", "quick_test_report.md",
        "--output-json", "quick_test_results.json"
    ]
    
    subprocess.run(cmd)

def run_medium_test():
    """中等测试：测试5个数据集和3个模型"""
    print("=" * 50)
    print("中等测试模式")
    print("测试数据集: heart, diabetes, titanic, adult, bank")
    print("测试模型: RF, XGB, LGBM")
    print("重试次数: 3")
    print("=" * 50)
    
    cmd = [
        sys.executable, "adda_benchmark_test.py",
        "--datasets", "heart", "diabetes", "titanic", "adult", "bank",
        "--models", "RF", "XGB", "LGBM",
        "--max-retries", "3",
        "--timeout-hours", "2.0",
        "--output-md", "medium_test_report.md",
        "--output-json", "medium_test_results.json"
    ]
    
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
    
    cmd = [
        sys.executable, "adda_benchmark_test.py",
        "--max-retries", "3",
        "--timeout-hours", "3.0",
        "--output-md", "full_test_report.md",
        "--output-json", "full_test_results.json"
    ]
    
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
    available_models = ["RF", "XGB", "LGBM", "DT", "ET"]
    
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
    
    timeout_hours = input("超时时间(小时，默认2.0): ").strip()
    timeout_hours = float(timeout_hours) if timeout_hours else 2.0
    
    output_prefix = input("输出文件前缀 (默认custom_test): ").strip()
    output_prefix = output_prefix if output_prefix else "custom_test"
    
    print(f"\n配置确认:")
    print(f"  数据集: {selected_datasets}")
    print(f"  模型: {selected_models}")
    print(f"  重试次数: {max_retries}")
    print(f"  超时时间: {timeout_hours}小时")
    
    response = input("\n确认运行？(yes/no): ")
    if response.lower() != 'yes':
        print("测试已取消")
        return
    
    cmd = [
        sys.executable, "adda_benchmark_test.py",
        "--datasets"] + selected_datasets + [
        "--models"] + selected_models + [
        "--max-retries", str(max_retries),
        "--timeout-hours", str(timeout_hours),
        "--output-md", f"{output_prefix}_report.md",
        "--output-json", f"{output_prefix}_results.json"
    ]
    
    subprocess.run(cmd)

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
        print("  4. 自定义测试 (手动选择参数)")
        print("  5. 退出")
        
        choice = input("\n请输入选择 (1-5): ").strip()
        
        if choice == "1":
            run_quick_test()
        elif choice == "2":
            run_medium_test()
        elif choice == "3":
            run_full_test()
        elif choice == "4":
            run_custom_test()
        elif choice == "5":
            print("退出程序")
            break
        else:
            print("无效选择，请重试")

if __name__ == "__main__":
    # 检查必要的文件是否存在
    if not os.path.exists("adda_benchmark_test.py"):
        print("错误: 找不到 adda_benchmark_test.py 文件")
        print("请确保该文件在当前目录下")
        sys.exit(1)
    
    main()