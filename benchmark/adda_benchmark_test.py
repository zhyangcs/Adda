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
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pandas as pd

# 添加项目路径
project_root = os.path.abspath(os.path.dirname(__file__))
# 从benchmark目录向上找到项目根目录
if project_root.endswith("benchmark"):
    project_root = os.path.dirname(project_root)

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
                 single_timeout_minutes: int = 20,
                 log_file: Optional[str] = None):
        """
        初始化测试器
        
        Args:
            datasets: 要测试的数据集列表，None表示使用所有可用数据集
            models: 要测试的模型列表，None表示使用所有可用模型
            max_retries: 每个组合的最大重试次数
            timeout_hours: 单个测试的超时时间（小时）（已弃用，保留兼容性）
            single_timeout_minutes: 单次尝试（特征生成+模型训练）的超时时间（分钟）
            log_file: 日志文件路径，None表示使用默认路径
        """
        self.project_root = project_root
        self.test_save_path = test_save_path
        self.max_retries = max_retries
        self.timeout_seconds = timeout_hours * 3600  # 保留兼容性
        self.single_timeout_seconds = single_timeout_minutes * 60
        
        # 设置日志记录
        self._setup_logging(log_file)
        
        # 加载配置
        self.config = self._load_config()
        
        # 设置测试范围
        self.available_datasets = list(self.config['task_config'].keys())
        self.available_models = ['RF', 'XGB', 'LGBM', 'CART', 'ET']  # 常用模型
        
        self.datasets = datasets if datasets else self.available_datasets
        self.models = models if models else self.available_models
        
        # 验证输入
        self._validate_inputs()
        
        # 存储测试结果 - 重新设计数据结构
        self.raw_results = []  # 存储所有原始测试数据 (14*5*3 = 210条记录)
        self.optimized_results = {}  # 存储每个数据集&模型组合的选优结果
        self.final_results = {}  # 存储每个数据集的最终统计结果 (最大值/平均值)
        self.detailed_logs = []
        
    def _setup_logging(self, log_file: Optional[str] = None):
        """设置日志记录"""
        if log_file is None:
            # 创建默认日志文件名，直接放在benchmark/logs目录下
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"benchmark/logs/adda_benchmark_log_{timestamp}.log"
        else:
            # 如果用户指定了日志文件，确保它在benchmark/logs目录下
            if not log_file.startswith("benchmark/") and not os.path.isabs(log_file):
                log_file = os.path.join("benchmark", "logs", log_file)
        
        # 确保logs目录存在
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        self.log_file = log_file
        
        # 配置日志记录器 - 使用RotatingFileHandler避免文件锁定
        # 创建格式化器
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # 创建根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # 清除所有现有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加RotatingFileHandler (主日志文件)
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        
        # 添加实时日志文件 (用于tail -f查看)
        realtime_log = log_file.replace('.log', '_realtime.log')
        realtime_handler = logging.FileHandler(realtime_log, mode='w', encoding='utf-8')
        realtime_handler.setFormatter(formatter)
        realtime_handler.setLevel(logging.INFO)
        root_logger.addHandler(realtime_handler)
        
        self.logger = logging.getLogger(__name__)
        self.realtime_log_file = realtime_log
        self.logger.info(f"开始Adda基准测试，主日志文件: {log_file}")
        self.logger.info(f"实时日志文件: {realtime_log}")
        
        # 打印实时查看命令提示
        print(f"💡 实时查看日志命令: tail -f {realtime_log}")
        print(f"📁 完整日志文件: {log_file}")
    
    
    def _log_only(self, message: str, level: str = "info"):
        """只记录到日志文件，不打印到控制台"""
        if level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        elif level == "debug":
            self.logger.debug(message)
    
    def _log_and_print(self, message: str, level: str = "info"):
        """同时记录日志和打印到控制台（用于重要信息）"""
        print(message)
        self._log_only(message, level)
        
    def _load_config(self) -> Dict:
        """加载项目配置文件"""
        # 从benchmark目录向上找到项目根目录
        if self.project_root.endswith("benchmark"):
            project_root = os.path.dirname(self.project_root)
        else:
            project_root = self.project_root
            
        config_path = os.path.join(project_root, "src", "llm", "tests", "config.yaml")
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
        
        self._log_and_print(f"测试配置:")
        self._log_and_print(f"  数据集: {self.datasets}")
        self._log_and_print(f"  模型: {self.models}")
        self._log_and_print(f"  最大重试次数: {self.max_retries}")
        self._log_and_print(f"  单次尝试超时时间: {self.single_timeout_seconds/60:.1f}分钟")
        self._log_and_print(f"  总体超时时间: {self.timeout_seconds/3600:.1f}小时")
        self._log_and_print(f"  日志文件: {self.log_file}")
    
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
    
    def _run_command_with_logging(self, cmd: List[str], command_type: str, timeout_seconds: int) -> Tuple[bool, Optional[str], str]:
        """运行命令并实时记录输出到日志"""
        # 控制台显示精简信息
        print(f"    执行{command_type}...")
        self._log_only(f"    执行{command_type}: {' '.join(cmd)}")
        self._log_only(f"    超时设置: {timeout_seconds/60:.1f}分钟")
        
        start_time = time.time()
        output_lines = []
        
        try:
            # 从benchmark目录向上找到项目根目录作为工作目录
            if self.project_root.endswith("benchmark"):
                working_dir = os.path.dirname(self.project_root)
            else:
                working_dir = self.project_root
                
            # 使用Popen来实时捕获输出
            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 实时读取并记录输出到日志文件
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    output_lines.append(line)
                    # 只记录到日志文件，不显示在控制台
                    self._log_only(f"    [{command_type}] {line}")
                    
                # 检查超时
                if time.time() - start_time > timeout_seconds:
                    process.kill()
                    elapsed_time = time.time() - start_time
                    print(f"    {command_type}超时！({elapsed_time/60:.1f}分钟)")
                    self._log_only(f"    {command_type}超时！({elapsed_time/60:.1f}分钟 > {timeout_seconds/60:.1f}分钟)", "warning")
                    return False, None, f"超时，耗时{elapsed_time/60:.1f}分钟"
            
            # 等待进程完成
            process.wait()
            elapsed_time = time.time() - start_time
            
            full_output = '\n'.join(output_lines)
            
            if process.returncode == 0:
                print(f"    {command_type}成功 ({elapsed_time/60:.1f}分钟)")
                self._log_only(f"    {command_type}成功，耗时: {elapsed_time/60:.2f}分钟")
                return True, full_output, ""
            else:
                print(f"    {command_type}失败 (返回码: {process.returncode})")
                self._log_only(f"    {command_type}失败，返回码: {process.returncode}，耗时: {elapsed_time/60:.2f}分钟", "error")
                return False, full_output, f"返回码: {process.returncode}"
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"{command_type}异常 (耗时{elapsed_time/60:.2f}分钟): {e}"
            print(f"    {command_type}异常")
            self._log_only(f"    {error_msg}", "error")
            return False, None, error_msg

    def _run_test_util(self, dataset: str, model: str) -> bool:
        """运行test_util.py进行特征生成"""
        # 从benchmark目录向上找到项目根目录
        if self.project_root.endswith("benchmark"):
            project_root = os.path.dirname(self.project_root)
        else:
            project_root = self.project_root
            
        cmd = [
            sys.executable,
            os.path.join(project_root, "src", "llm", "tests", "test_util.py"),
            "--task_name", dataset,
            "--model_type", model
        ]
        
        success, output, error = self._run_command_with_logging(cmd, "特征生成", self.single_timeout_seconds)
        return success

    def _run_multimodel_type(self, dataset: str, model: str) -> Optional[float]:
        """运行run_multimodel_type.py进行模型训练和评估"""
        # 从benchmark目录向上找到项目根目录
        if self.project_root.endswith("benchmark"):
            project_root = os.path.dirname(self.project_root)
        else:
            project_root = self.project_root
            
        cmd = [
            sys.executable,
            os.path.join(project_root, "src", "run_multimodel_type.py"),
            "--task_name", dataset,
            "--model_type", model
        ]
        
        success, output, error = self._run_command_with_logging(cmd, "模型训练", self.single_timeout_seconds)
        
        if success and output:
            # 解析输出中的分数
            score = self._parse_score_from_output(output)
            if score is not None:
                print(f"    得分: {score:.4f}")
                self._log_only(f"    模型训练成功，得分: {score:.4f}")
                return score
            else:
                print(f"    无法解析得分")
                self._log_only("    模型训练成功，但无法解析得分", "warning")
                self._log_only("    输出内容预览:")
                preview = output[:500] + "..." if len(output) > 500 else output
                self._log_only(f"    {preview}")
                return None
        else:
            print(f"    模型训练失败")
            self._log_only(f"    模型训练失败: {error}", "error")
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
    
    def _test_single_combination(self, dataset: str, model: str) -> Tuple[List[Dict], float]:
        """测试单个数据集-模型组合，收集所有重试的原始数据"""
        print(f"\n测试组合: {dataset} + {model}")
        self._log_only(f"\n测试组合: {dataset} + {model}")
        
        combination_raw_results = []
        best_score = 0.0
        
        for retry in range(1, self.max_retries + 1):
            print(f"  第 {retry}/{self.max_retries} 次尝试")
            self._log_only(f"  第 {retry}/{self.max_retries} 次尝试")
            
            # 记录开始时间
            start_time = time.time()
            
            # 执行特征生成
            feature_success = self._run_test_util(dataset, model)
            feature_time = time.time() - start_time
            
            # 执行模型训练和评估
            model_start_time = time.time()
            score = None
            if feature_success:
                score = self._run_multimodel_type(dataset, model)
            model_time = time.time() - model_start_time
            
            # 创建原始结果记录
            raw_result = {
                'dataset': dataset,
                'model': model,
                'retry': retry,
                'feature_generation_success': feature_success,
                'feature_generation_time': feature_time,
                'model_training_time': model_time,
                'score': score,
                'success': score is not None,
                'timestamp': datetime.now().isoformat(),
                'total_time': feature_time + model_time
            }
            
            # 添加到原始结果列表
            combination_raw_results.append(raw_result)
            self.raw_results.append(raw_result)
            
            if score is not None:
                # 立即重命名结果目录
                self._rename_result_dir_immediately(dataset, model, retry, score)
                
                if score > best_score:
                    best_score = score
                    print(f"    ✓ 新的最佳得分: {best_score:.4f}")
                else:
                    print(f"    ✓ 第 {retry} 次尝试完成")
                
                self._log_only(f"    第 {retry} 次尝试成功，得分: {score:.4f}")
                if score > best_score:
                    self._log_only(f"    新的最佳得分: {best_score:.4f}")
            else:
                print(f"    ✗ 第 {retry} 次尝试失败")
                self._log_only(f"    第 {retry} 次尝试失败")
            
            # 记录详细日志
            self.detailed_logs.append({
                'dataset': dataset,
                'model': model,
                'retry': retry,
                'score': score,
                'success': score is not None,
                'timestamp': datetime.now().isoformat()
            })
        
        return combination_raw_results, best_score
    
    def _optimize_combination_results(self):
        """对每个数据集&模型组合的结果进行选优"""
        print("\n正在对结果进行选优...")
        self._log_only("\n正在对结果进行选优...")
        
        # 按数据集和模型分组
        for dataset in self.datasets:
            if dataset not in self.optimized_results:
                self.optimized_results[dataset] = {}
            
            for model in self.models:
                # 获取该组合的所有成功结果
                combination_results = [
                    r for r in self.raw_results 
                    if r['dataset'] == dataset and r['model'] == model and r['success']
                ]
                
                if combination_results:
                    # 选择最高分数
                    best_result = max(combination_results, key=lambda x: x['score'])
                    best_score = best_result['score']
                    
                    # 计算统计信息
                    all_scores = [r['score'] for r in combination_results]
                    avg_score = sum(all_scores) / len(all_scores)
                    
                    self.optimized_results[dataset][model] = {
                        'best_score': best_score,
                        'average_score_across_retries': avg_score,
                        'total_attempts': len([r for r in self.raw_results 
                                             if r['dataset'] == dataset and r['model'] == model]),
                        'successful_attempts': len(combination_results),
                        'all_scores': all_scores,
                        'best_result_details': best_result
                    }
                    
                    self._log_only(f"  {dataset} + {model}: 最佳 {best_score:.4f}, 平均 {avg_score:.4f} ({len(combination_results)}次成功)")
                else:
                    self.optimized_results[dataset][model] = {
                        'best_score': 0.0,
                        'average_score_across_retries': 0.0,
                        'total_attempts': len([r for r in self.raw_results 
                                             if r['dataset'] == dataset and r['model'] == model]),
                        'successful_attempts': 0,
                        'all_scores': [],
                        'best_result_details': None
                    }
                    self._log_only(f"  {dataset} + {model}: 无成功结果")
    
    def _calculate_final_dataset_statistics(self):
        """计算每个数据集的最大值和平均值"""
        print("正在计算最终数据集统计...")
        self._log_only("\n正在计算数据集统计...")
        
        for dataset in self.datasets:
            if dataset not in self.final_results:
                self.final_results[dataset] = {}
            
            # 获取该数据集下所有模型的选优结果
            model_best_scores = []
            for model in self.models:
                if model in self.optimized_results[dataset]:
                    best_score = self.optimized_results[dataset][model]['best_score']
                    if best_score > 0:  # 只包含成功的结果
                        model_best_scores.append(best_score)
            
            if model_best_scores:
                max_score = max(model_best_scores)
                avg_score = sum(model_best_scores) / len(model_best_scores)
                
                self.final_results[dataset] = {
                    'max_score': max_score,
                    'avg_score': avg_score,
                    'successful_models': len(model_best_scores),
                    'total_models': len(self.models),
                    'model_scores': {
                        model: self.optimized_results[dataset][model]['best_score']
                        for model in self.models
                        if model in self.optimized_results[dataset]
                    }
                }
                
                print(f"  {dataset}: 最大值 {max_score:.4f}, 平均值 {avg_score:.4f}")
                self._log_only(f"  {dataset}: 最大值 {max_score:.4f}, 平均值 {avg_score:.4f} ({len(model_best_scores)}/{len(self.models)}模型成功)")
            else:
                self.final_results[dataset] = {
                    'max_score': 0.0,
                    'avg_score': 0.0,
                    'successful_models': 0,
                    'total_models': len(self.models),
                    'model_scores': {}
                }
                print(f"  {dataset}: 所有模型均失败")
                self._log_only(f"  {dataset}: 所有模型均失败")

    def run_benchmark(self):
        """运行完整的基准测试"""
        print("=" * 60)
        print("开始Adda基准测试")
        print("=" * 60)
        self._log_only("=" * 60)
        self._log_only("开始Adda基准测试")
        self._log_only("=" * 60)
        
        start_time = time.time()
        total_combinations = len(self.datasets) * len(self.models)
        current_combination = 0
        
        for dataset in self.datasets:
            for model in self.models:
                current_combination += 1
                print(f"\n进度: {current_combination}/{total_combinations}")
                self._log_only(f"\n进度: {current_combination}/{total_combinations}")
                
                try:
                    combination_raw_results, best_score = self._test_single_combination(dataset, model)
                    print(f"组合 {dataset}+{model} 完成，最佳得分: {best_score:.4f}")
                    self._log_only(f"组合 {dataset}+{model} 完成，最佳得分: {best_score:.4f}")
                    
                except KeyboardInterrupt:
                    print("\n用户中断测试")
                    self._log_only("\n用户中断测试", "warning")
                    break
                except Exception as e:
                    print(f"测试组合 {dataset}+{model} 时发生异常: {e}")
                    self._log_only(f"测试组合 {dataset}+{model} 时发生异常: {e}", "error")
                    # 即使异常也要记录原始数据
                    for retry in range(1, self.max_retries + 1):
                        self.raw_results.append({
                            'dataset': dataset,
                            'model': model,
                            'retry': retry,
                            'feature_generation_success': False,
                            'feature_generation_time': 0,
                            'model_training_time': 0,
                            'score': None,
                            'success': False,
                            'timestamp': datetime.now().isoformat(),
                            'total_time': 0,
                            'error': str(e)
                        })
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n原始数据收集完成，总耗时: {total_time/3600:.2f}小时")
        print(f"收集到 {len(self.raw_results)} 条原始测试记录")
        self._log_only(f"\n原始数据收集完成，总耗时: {total_time/3600:.2f}小时")
        self._log_only(f"收集到 {len(self.raw_results)} 条原始测试记录")
        
        # 进行选优处理
        self._optimize_combination_results()
        
        # 计算最终统计
        self._calculate_final_dataset_statistics()
        
        print(f"\n基准测试完成！")
        self._log_only(f"\n基准测试完成！")
        
    def generate_markdown_report(self, output_file: str = "adda_benchmark_report.md"):
        """生成markdown测试报告"""
        # 确保输出文件在benchmark/results目录下
        if not output_file.startswith("benchmark/") and not os.path.isabs(output_file):
            output_file = os.path.join("benchmark", "results", output_file)
        
        # 确保results目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
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
            f"**原始测试记录数**: {len(self.raw_results)}",
            "",
            "## 最终结果汇总 (每数据集的最大值/平均值)",
            ""
        ])
        
        # 最终结果表格
        header = ["数据集", "最大值", "平均值", "成功模型数", "总模型数"]
        report_lines.append("| " + " | ".join(header) + " |")
        report_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        
        for dataset in self.datasets:
            if dataset in self.final_results:
                result = self.final_results[dataset]
                row = [
                    dataset,
                    f"{result['max_score']:.4f}",
                    f"{result['avg_score']:.4f}",
                    str(result['successful_models']),
                    str(result['total_models'])
                ]
                report_lines.append("| " + " | ".join(row) + " |")
        
        report_lines.extend([
            "",
            "## 每个数据集&模型组合的选优结果",
            ""
        ])
        
        # 数据集&模型组合结果表格
        header = ["数据集", "模型", "选优得分", "重试平均分", "成功次数", "总尝试次数", "所有得分"]
        report_lines.append("| " + " | ".join(header) + " |")
        report_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        
        for dataset in self.datasets:
            for model in self.models:
                if dataset in self.optimized_results and model in self.optimized_results[dataset]:
                    result = self.optimized_results[dataset][model]
                    
                    scores_str = ", ".join([f"{s:.4f}" for s in result['all_scores']]) if result['all_scores'] else "无"
                    
                    row = [
                        dataset,
                        model,
                        f"{result['best_score']:.4f}",
                        f"{result['average_score_across_retries']:.4f}",
                        str(result['successful_attempts']),
                        str(result['total_attempts']),
                        scores_str
                    ]
                    report_lines.append("| " + " | ".join(row) + " |")
        
        report_lines.extend([
            "",
            "## 原始测试数据",
            ""
        ])
        
        # 原始数据表格
        header = ["数据集", "模型", "重试次数", "特征生成", "得分", "成功", "时间戳"]
        report_lines.append("| " + " | ".join(header) + " |")
        report_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        
        for raw_result in self.raw_results:
            score_str = f"{raw_result['score']:.4f}" if raw_result['score'] is not None else "失败"
            success_str = "✓" if raw_result['success'] else "✗"
            feature_str = "✓" if raw_result['feature_generation_success'] else "✗"
            timestamp = datetime.fromisoformat(raw_result['timestamp']).strftime('%H:%M:%S')
            
            row = [
                raw_result['dataset'],
                raw_result['model'],
                str(raw_result['retry']),
                feature_str,
                score_str,
                success_str,
                timestamp
            ]
            report_lines.append("| " + " | ".join(row) + " |")
        
        # 统计信息
        total_tests = len(self.raw_results)
        successful_tests = len([r for r in self.raw_results if r['success']])
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        report_lines.extend([
            "",
            "## 统计信息",
            "",
            f"- **总测试次数**: {total_tests}",
            f"- **成功测试次数**: {successful_tests}",
            f"- **成功率**: {success_rate:.1f}%",
            ""
        ])
        
        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        print(f"测试报告已生成: {output_file}")
    
    def save_results_json(self, output_file: str = "adda_benchmark_results.json"):
        """保存结果为JSON格式"""
        # 确保输出文件在benchmark/results目录下
        if not output_file.startswith("benchmark/") and not os.path.isabs(output_file):
            output_file = os.path.join("benchmark", "results", output_file)
        
        # 确保results目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        results_data = {
            'metadata': {
                'datasets': self.datasets,
                'models': self.models,
                'max_retries': self.max_retries,
                'generation_time': datetime.now().isoformat(),
                'total_raw_records': len(self.raw_results)
            },
            'raw_results': self.raw_results,  # 所有原始测试数据
            'optimized_results': self.optimized_results,  # 每个数据集&模型组合的选优结果
            'final_results': self.final_results,  # 每个数据集的最大值/平均值
            'detailed_logs': self.detailed_logs,
            # 为了兼容比较脚本，添加旧格式的results字段
            'results': [
                {
                    'dataset': dataset,
                    'max_score': self.final_results[dataset]['max_score'],
                    'avg_score': self.final_results[dataset]['avg_score'],
                    'status': 'success' if self.final_results[dataset]['max_score'] > 0 else 'failed'
                }
                for dataset in self.datasets
                if dataset in self.final_results
            ]
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
    parser.add_argument("--log-file", default=None,
                       help="日志文件路径（默认：自动生成到benchmark/logs/目录）")
    parser.add_argument("--output-md", default="benchmark/results/adda_benchmark_report.md",
                       help="输出的markdown报告文件名")
    parser.add_argument("--output-json", default="benchmark/results/adda_benchmark_results.json",
                       help="输出的JSON结果文件名")
    
    args = parser.parse_args()
    
    # 创建测试器
    try:
        tester = AddaBenchmarkTester(
            datasets=args.datasets,
            models=args.models,
            max_retries=args.max_retries,
            timeout_hours=args.timeout_hours,
            single_timeout_minutes=args.single_timeout_minutes,
            log_file=args.log_file
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