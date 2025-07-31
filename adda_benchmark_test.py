#!/usr/bin/env python3
"""
Adda自动化基准测试脚本
功能：
1. 自动测试多个数据集和模型组合
2. 支持重试机制，保留最高分数
3. 智能处理目录冲突
4. 生成详细的markdown测试报告
"""

import os
import sys
import subprocess
import yaml
import json
import time
import shutil
import re
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pandas as pd

# 添加项目路径
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.env import test_save_path

class AddaBenchmarkTester:
    """Adda基准测试器"""
    
    def __init__(self, 
                 datasets: Optional[List[str]] = None,
                 models: Optional[List[str]] = None,
                 max_retries: int = 3,
                 timeout_hours: int = 2,
                 single_timeout_minutes: int = 20):
        """
        初始化测试器
        
        Args:
            datasets: 要测试的数据集列表，None表示使用所有可用数据集
            models: 要测试的模型列表，None表示使用所有可用模型
            max_retries: 每个组合的最大重试次数
            timeout_hours: 单个测试的超时时间（小时）（已弃用，保留兼容性）
            single_timeout_minutes: 单次尝试（特征生成+模型训练）的超时时间（分钟）
        """
        self.project_root = project_root
        self.test_save_path = test_save_path
        self.max_retries = max_retries
        self.timeout_seconds = timeout_hours * 3600  # 保留兼容性
        self.single_timeout_seconds = single_timeout_minutes * 60
        
        # 加载配置
        self.config = self._load_config()
        
        # 设置测试范围
        self.available_datasets = list(self.config['task_config'].keys())
        self.available_models = ['RF', 'XGB', 'LGBM', 'CART', 'ET']  # 常用模型
        
        self.datasets = datasets if datasets else self.available_datasets
        self.models = models if models else self.available_models
        
        # 验证输入
        self._validate_inputs()
        
        # 存储测试结果
        self.results = {}
        self.detailed_logs = []
        
    def _load_config(self) -> Dict:
        """加载项目配置文件"""
        config_path = os.path.join(self.project_root, "src", "llm", "tests", "config.yaml")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise FileNotFoundError(f"无法加载配置文件 {config_path}: {e}")
    
    def _validate_inputs(self):
        """验证输入参数"""
        invalid_datasets = [d for d in self.datasets if d not in self.available_datasets]
        if invalid_datasets:
            raise ValueError(f"无效的数据集: {invalid_datasets}. 可用数据集: {self.available_datasets}")
        
        print(f"测试配置:")
        print(f"  数据集: {self.datasets}")
        print(f"  模型: {self.models}")
        print(f"  最大重试次数: {self.max_retries}")
        print(f"  单次尝试超时时间: {self.single_timeout_seconds/60:.1f}分钟")
        print(f"  总体超时时间: {self.timeout_seconds/3600:.1f}小时")
    
    def _get_existing_result_dirs(self, dataset: str, model: str) -> List[str]:
        """获取已存在的结果目录"""
        pattern = f"{dataset}_{model}_Full"
        base_dir = os.path.join(self.test_save_path, pattern)
        
        existing_dirs = []
        if os.path.exists(base_dir):
            existing_dirs.append(base_dir)
        
        # 查找带重试编号的目录
        for item in os.listdir(self.test_save_path):
            if item.startswith(f"{pattern}_retry"):
                existing_dirs.append(os.path.join(self.test_save_path, item))
        
        return existing_dirs
    
    def _backup_existing_dir(self, dataset: str, model: str, retry_num: int, previous_score: Optional[float] = None):
        """备份已存在的目录"""
        base_pattern = f"{dataset}_{model}_Full"
        base_dir = os.path.join(self.test_save_path, base_pattern)
        
        if os.path.exists(base_dir):
            # 创建备份目录名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if previous_score is not None:
                backup_name = f"{base_pattern}_retry{retry_num-1}_score{previous_score:.4f}_{timestamp}"
            else:
                backup_name = f"{base_pattern}_retry{retry_num-1}_{timestamp}"
            
            backup_dir = os.path.join(self.test_save_path, backup_name)
            
            try:
                shutil.move(base_dir, backup_dir)
                print(f"  备份目录: {base_dir} -> {backup_dir}")
                return backup_dir
            except Exception as e:
                print(f"  警告: 备份目录失败: {e}")
                return None
        return None
    
    def _rename_result_dir_immediately(self, dataset: str, model: str, retry_num: int, score: float):
        """每次尝试完成后立即重命名结果目录"""
        base_pattern = f"{dataset}_{model}_Full"
        base_dir = os.path.join(self.test_save_path, base_pattern)
        
        if os.path.exists(base_dir):
            # 创建新的目录名（包含尝试次数和分数）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{base_pattern}_retry{retry_num}_score{score:.4f}_{timestamp}"
            new_dir = os.path.join(self.test_save_path, new_name)
            
            try:
                shutil.move(base_dir, new_dir)
                print(f"    结果目录已重命名: {base_dir} -> {new_dir}")
                return new_dir
            except Exception as e:
                print(f"    警告: 重命名结果目录失败: {e}")
                return None
        else:
            print(f"    警告: 未找到结果目录 {base_dir}")
            return None
    
    def _run_test_util(self, dataset: str, model: str) -> bool:
        """运行test_util.py进行特征生成"""
        cmd = [
            sys.executable,
            "src/llm/tests/test_util.py",
            "--task_name", dataset,
            "--model_type", model
        ]
        
        print(f"    执行特征生成: {' '.join(cmd)}")
        print(f"    超时设置: {self.single_timeout_seconds/60:.1f}分钟")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                timeout=self.single_timeout_seconds,  # 使用单次尝试超时
                capture_output=True,
                text=True
            )
            
            elapsed_time = time.time() - start_time
            print(f"    特征生成耗时: {elapsed_time/60:.2f}分钟")
            
            if result.returncode == 0:
                print("    特征生成成功")
                return True
            else:
                print(f"    特征生成失败，返回码: {result.returncode}")
                if result.stderr:
                    print(f"    错误信息: {result.stderr}")
                if result.stdout:
                    print(f"    输出信息: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            elapsed_time = time.time() - start_time
            print(f"    特征生成超时！({elapsed_time/60:.1f}分钟 > {self.single_timeout_seconds/60:.1f}分钟)")
            print(f"    可能原因: 1) 数据处理卡死 2) 文件锁冲突 3) 内存不足 4) API调用卡住")
            return False
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"    特征生成异常 (耗时{elapsed_time/60:.2f}分钟): {e}")
            return False
    
    def _run_multimodel_type(self, dataset: str, model: str) -> Optional[float]:
        """运行run_multimodel_type.py进行模型训练和评估"""
        cmd = [
            sys.executable,
            "src/run_multimodel_type.py",
            "--task_name", dataset,
            "--model_type", model
        ]
        
        print(f"    执行模型训练: {' '.join(cmd)}")
        print(f"    超时设置: {self.single_timeout_seconds/60:.1f}分钟")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                timeout=self.single_timeout_seconds,  # 使用单次尝试超时
                capture_output=True,
                text=True
            )
            
            elapsed_time = time.time() - start_time
            print(f"    模型训练耗时: {elapsed_time/60:.2f}分钟")
            
            if result.returncode == 0:
                # 解析输出中的分数
                score = self._parse_score_from_output(result.stdout)
                if score is not None:
                    print(f"    模型训练成功，得分: {score:.4f}")
                    return score
                else:
                    print("    模型训练成功，但无法解析得分")
                    print("    输出内容预览:")
                    preview = result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout
                    print(f"    {preview}")
                    return None
            else:
                print(f"    模型训练失败，返回码: {result.returncode}")
                if result.stderr:
                    print(f"    错误信息: {result.stderr}")
                if result.stdout:
                    print(f"    输出信息: {result.stdout}")
                return None
                
        except subprocess.TimeoutExpired:
            elapsed_time = time.time() - start_time
            print(f"    模型训练超时！({elapsed_time/60:.1f}分钟 > {self.single_timeout_seconds/60:.1f}分钟)")
            print(f"    可能原因: 1) 模型训练时间过长 2) 数据量太大 3) 计算资源不足")
            return None
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"    模型训练异常 (耗时{elapsed_time/60:.2f}分钟): {e}")
            return None
    
    def _parse_score_from_output(self, output: str) -> Optional[float]:
        """从输出中解析得分"""
        # 查找类似 "Final valid and test score: [0.8532]" 的模式
        patterns = [
            r"Final valid and test score:\s*\[?([0-9]+\.?[0-9]*)\]?",
            r"Final valid and test score:\s*([0-9]+\.?[0-9]*)",
            r"Task.*with model type.*:\s*([0-9]+\.?[0-9]*)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    def _test_single_combination(self, dataset: str, model: str) -> Tuple[float, List[float]]:
        """测试单个数据集-模型组合，支持重试"""
        print(f"\n测试组合: {dataset} + {model}")
        
        best_score = 0.0
        all_scores = []
        
        for retry in range(1, self.max_retries + 1):
            print(f"  第 {retry}/{self.max_retries} 次尝试")
            
            # # 如果不是第一次尝试，备份已存在的目录
            # if retry > 1:
            #     previous_score = all_scores[-1] if all_scores else None
            #     self._backup_existing_dir(dataset, model, retry, previous_score)
            
            # 执行特征生成
            if not self._run_test_util(dataset, model):
                print(f"    第 {retry} 次尝试失败：特征生成失败")
                continue
            
            # 执行模型训练和评估
            score = self._run_multimodel_type(dataset, model)
            if score is None:
                print(f"    第 {retry} 次尝试失败：模型训练失败")
                continue
            
            # 立即重命名结果目录
            self._rename_result_dir_immediately(dataset, model, retry, score)
            
            all_scores.append(score)
            
            if score > best_score:
                best_score = score
                print(f"    新的最佳得分: {best_score:.4f}")
            
            # 记录详细日志
            self.detailed_logs.append({
                'dataset': dataset,
                'model': model,
                'retry': retry,
                'score': score,
                'timestamp': datetime.now().isoformat()
            })
            
            print(f"    第 {retry} 次尝试完成，得分: {score:.4f}")
        
        return best_score, all_scores
    
    def run_benchmark(self):
        """运行完整的基准测试"""
        print("=" * 60)
        print("开始Adda基准测试")
        print("=" * 60)
        
        start_time = time.time()
        total_combinations = len(self.datasets) * len(self.models)
        current_combination = 0
        
        for dataset in self.datasets:
            if dataset not in self.results:
                self.results[dataset] = {}
            
            for model in self.models:
                current_combination += 1
                print(f"\n进度: {current_combination}/{total_combinations}")
                
                try:
                    best_score, all_scores = self._test_single_combination(dataset, model)
                    
                    self.results[dataset][model] = {
                        'best_score': best_score,
                        'all_scores': all_scores,
                        'num_attempts': len(all_scores),
                        'average_score': sum(all_scores) / len(all_scores) if all_scores else 0.0
                    }
                    
                except KeyboardInterrupt:
                    print("\n用户中断测试")
                    break
                except Exception as e:
                    print(f"测试组合 {dataset}+{model} 时发生异常: {e}")
                    self.results[dataset][model] = {
                        'best_score': 0.0,
                        'all_scores': [],
                        'num_attempts': 0,
                        'average_score': 0.0,
                        'error': str(e)
                    }
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n基准测试完成，总耗时: {total_time/3600:.2f}小时")
        
    def generate_markdown_report(self, output_file: str = "adda_benchmark_report.md"):
        """生成markdown测试报告"""
        print(f"\n生成测试报告: {output_file}")
        
        report_lines = []
        
        # 报告头部
        report_lines.extend([
            "# Adda基准测试报告",
            "",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**测试数据集**: {', '.join(self.datasets)}",
            f"**测试模型**: {', '.join(self.models)}",
            f"**最大重试次数**: {self.max_retries}",
            "",
            "## 详细测试结果",
            ""
        ])
        
        # 构建详细结果表格
        header = ["数据集", "模型", "最佳得分", "平均得分", "尝试次数", "所有得分"]
        report_lines.append("| " + " | ".join(header) + " |")
        report_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        
        for dataset in self.datasets:
            for model in self.models:
                if dataset in self.results and model in self.results[dataset]:
                    result = self.results[dataset][model]
                    
                    if 'error' in result:
                        scores_str = f"错误: {result['error']}"
                        best_score = "N/A"
                        avg_score = "N/A"
                        attempts = "0"
                    else:
                        best_score = f"{result['best_score']:.4f}"
                        avg_score = f"{result['average_score']:.4f}"
                        attempts = str(result['num_attempts'])
                        scores_str = ", ".join([f"{s:.4f}" for s in result['all_scores']])
                    
                    row = [dataset, model, best_score, avg_score, attempts, scores_str]
                    report_lines.append("| " + " | ".join(row) + " |")
                else:
                    row = [dataset, model, "未测试", "未测试", "0", "N/A"]
                    report_lines.append("| " + " | ".join(row) + " |")
        
        report_lines.append("")
        
        # 添加汇总统计
        report_lines.extend([
            "## 汇总统计",
            ""
        ])
        
        # 按数据集汇总
        report_lines.extend([
            "### 按数据集汇总",
            ""
        ])
        
        dataset_header = ["数据集", "最高得分", "平均得分", "模型数量"]
        report_lines.append("| " + " | ".join(dataset_header) + " |")
        report_lines.append("| " + " | ".join(["---"] * len(dataset_header)) + " |")
        
        for dataset in self.datasets:
            if dataset in self.results:
                valid_results = [r for r in self.results[dataset].values() if 'error' not in r and r['best_score'] > 0]
                if valid_results:
                    max_score = max(r['best_score'] for r in valid_results)
                    avg_score = sum(r['average_score'] for r in valid_results) / len(valid_results)
                    model_count = len(valid_results)
                    
                    row = [dataset, f"{max_score:.4f}", f"{avg_score:.4f}", str(model_count)]
                    report_lines.append("| " + " | ".join(row) + " |")
        
        report_lines.append("")
        
        # 按模型汇总
        report_lines.extend([
            "### 按模型汇总",
            ""
        ])
        
        model_header = ["模型", "最高得分", "平均得分", "数据集数量"]
        report_lines.append("| " + " | ".join(model_header) + " |")
        report_lines.append("| " + " | ".join(["---"] * len(model_header)) + " |")
        
        for model in self.models:
            valid_results = []
            for dataset in self.datasets:
                if dataset in self.results and model in self.results[dataset]:
                    result = self.results[dataset][model]
                    if 'error' not in result and result['best_score'] > 0:
                        valid_results.append(result)
            
            if valid_results:
                max_score = max(r['best_score'] for r in valid_results)
                avg_score = sum(r['average_score'] for r in valid_results) / len(valid_results)
                dataset_count = len(valid_results)
                
                row = [model, f"{max_score:.4f}", f"{avg_score:.4f}", str(dataset_count)]
                report_lines.append("| " + " | ".join(row) + " |")
        
        report_lines.append("")
        
        # 添加详细日志
        if self.detailed_logs:
            report_lines.extend([
                "## 详细执行日志",
                ""
            ])
            
            log_header = ["时间", "数据集", "模型", "尝试次数", "得分"]
            report_lines.append("| " + " | ".join(log_header) + " |")
            report_lines.append("| " + " | ".join(["---"] * len(log_header)) + " |")
            
            for log in self.detailed_logs:
                timestamp = datetime.fromisoformat(log['timestamp']).strftime('%H:%M:%S')
                row = [
                    timestamp,
                    log['dataset'],
                    log['model'],
                    str(log['retry']),
                    f"{log['score']:.4f}"
                ]
                report_lines.append("| " + " | ".join(row) + " |")
        
        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        print(f"测试报告已生成: {output_file}")
    
    def save_results_json(self, output_file: str = "adda_benchmark_results.json"):
        """保存结果为JSON格式"""
        results_data = {
            'metadata': {
                'datasets': self.datasets,
                'models': self.models,
                'max_retries': self.max_retries,
                'generation_time': datetime.now().isoformat()
            },
            'results': self.results,
            'detailed_logs': self.detailed_logs
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"详细结果已保存: {output_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Adda自动化基准测试脚本")
    
    parser.add_argument("--datasets", nargs="*", 
                       help="要测试的数据集列表（默认：所有可用数据集）")
    parser.add_argument("--models", nargs="*", 
                       choices=['RF', 'XGB', 'LGBM', 'CART', 'ET'],
                       help="要测试的模型列表（默认：所有可用模型）")
    parser.add_argument("--max-retries", type=int, default=3,
                       help="每个组合的最大重试次数（默认：3）")
    parser.add_argument("--timeout-hours", type=float, default=2.0,
                       help="总体超时时间（小时）（默认：2.0，已弃用）")
    parser.add_argument("--single-timeout-minutes", type=int, default=20,
                       help="单次尝试超时时间（分钟）（默认：20）")
    parser.add_argument("--output-md", default="adda_benchmark_report.md",
                       help="输出的markdown报告文件名")
    parser.add_argument("--output-json", default="adda_benchmark_results.json",
                       help="输出的JSON结果文件名")
    
    args = parser.parse_args()
    
    # 创建测试器
    try:
        tester = AddaBenchmarkTester(
            datasets=args.datasets,
            models=args.models,
            max_retries=args.max_retries,
            timeout_hours=args.timeout_hours,
            single_timeout_minutes=args.single_timeout_minutes
        )
        
        # 运行基准测试
        tester.run_benchmark()
        
        # 生成报告
        tester.generate_markdown_report(args.output_md)
        tester.save_results_json(args.output_json)
        
        print("\n" + "="*60)
        print("基准测试完成！")
        print(f"Markdown报告: {args.output_md}")
        print(f"JSON结果: {args.output_json}")
        print("="*60)
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()