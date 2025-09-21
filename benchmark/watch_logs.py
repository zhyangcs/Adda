#!/usr/bin/env python3
"""
实时日志查看器
功能：
1. 自动检测最新的日志文件
2. 实时显示日志内容
3. 支持彩色输出
4. 支持多种查看模式
"""

import os
import sys
import glob
import time
import subprocess
import argparse
from pathlib import Path
from typing import Optional, List

class LogWatcher:
    """日志观察器"""
    
    def __init__(self):
        # 检查当前是否在benchmark目录下
        current_dir = os.path.basename(os.getcwd())
        if current_dir == "benchmark":
            self.logs_dir = "logs"
        else:
            self.logs_dir = "benchmark/logs"
        self.colors = {
            'INFO': '\033[32m',     # 绿色
            'WARNING': '\033[33m',  # 黄色
            'ERROR': '\033[31m',    # 红色
            'DEBUG': '\033[36m',    # 青色
            'RESET': '\033[0m'      # 重置
        }
    
    def find_latest_log(self, pattern: str = "*realtime.log") -> Optional[str]:
        """查找最新的日志文件"""
        if not os.path.exists(self.logs_dir):
            print(f"❌ 日志目录 {self.logs_dir} 不存在")
            return None
        
        log_files = glob.glob(os.path.join(self.logs_dir, pattern))
        if not log_files:
            print(f"❌ 在 {self.logs_dir} 中未找到匹配 '{pattern}' 的日志文件")
            return None
        
        # 按修改时间排序，返回最新的
        latest_file = max(log_files, key=os.path.getmtime)
        return latest_file
    
    def list_logs(self):
        """列出所有可用的日志文件"""
        if not os.path.exists(self.logs_dir):
            print(f"❌ 日志目录 {self.logs_dir} 不存在")
            return
        
        log_files = glob.glob(os.path.join(self.logs_dir, "*.log"))
        if not log_files:
            print(f"❌ 在 {self.logs_dir} 中未找到日志文件")
            return
        
        print("📋 可用的日志文件:")
        for i, log_file in enumerate(sorted(log_files, key=os.path.getmtime, reverse=True)):
            size = os.path.getsize(log_file)
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(log_file)))
            print(f"  {i+1}. {os.path.basename(log_file)} ({size} bytes, {mtime})")
    
    def watch_with_tail(self, log_file: str, lines: int = 10):
        """使用tail -f监控日志文件"""
        if not os.path.exists(log_file):
            print(f"❌ 日志文件 {log_file} 不存在")
            return
        
        print(f"🔍 正在监控日志文件: {log_file}")
        print(f"💡 按 Ctrl+C 停止监控")
        print("-" * 60)
        
        try:
            # 使用subprocess调用tail -f
            process = subprocess.Popen(
                ['tail', '-f', '-n', str(lines), log_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # 实时读取输出
            for line in process.stdout:
                self._colorize_output(line.rstrip())
                
        except KeyboardInterrupt:
            print(f"\n✅ 停止监控日志文件")
            process.terminate()
        except Exception as e:
            print(f"❌ 监控日志时出错: {e}")
    
    def _colorize_output(self, line: str):
        """给日志输出添加颜色"""
        colored_line = line
        for level, color in self.colors.items():
            if level == 'RESET':
                continue
            if f" - {level} - " in line:
                colored_line = line.replace(f" - {level} - ", f" - {color}{level}{self.colors['RESET']} - ")
                break
        print(colored_line)
    
    def watch_python(self, log_file: str, lines: int = 10):
        """使用Python实现的文件监控（备用方案）"""
        if not os.path.exists(log_file):
            print(f"❌ 日志文件 {log_file} 不存在")
            return
        
        print(f"🔍 正在监控日志文件: {log_file}")
        print(f"💡 按 Ctrl+C 停止监控")
        print("-" * 60)
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                # 先显示最后几行
                f.seek(0, 2)  # 移到文件末尾
                file_size = f.tell()
                
                # 读取最后几行
                lines_read = 0
                position = file_size
                while lines_read < lines and position > 0:
                    position -= 1
                    f.seek(position)
                    if f.read(1) == '\n':
                        lines_read += 1
                
                if position > 0:
                    f.seek(position + 1)
                else:
                    f.seek(0)
                
                for line in f:
                    self._colorize_output(line.rstrip())
                
                # 实时监控新内容
                while True:
                    line = f.readline()
                    if line:
                        self._colorize_output(line.rstrip())
                    else:
                        time.sleep(0.1)  # 短暂等待
                        
        except KeyboardInterrupt:
            print(f"\n✅ 停止监控日志文件")
        except Exception as e:
            print(f"❌ 监控日志时出错: {e}")

def main():
    parser = argparse.ArgumentParser(description="实时日志查看器")
    parser.add_argument('--file', '-f', help="指定要监控的日志文件")
    parser.add_argument('--lines', '-n', type=int, default=10, help="显示最后几行 (默认: 10)")
    parser.add_argument('--list', '-l', action='store_true', help="列出所有可用的日志文件")
    parser.add_argument('--pattern', '-p', default="*realtime.log", help="日志文件匹配模式 (默认: *realtime.log)")
    parser.add_argument('--python', action='store_true', help="使用Python实现监控（备用方案）")
    
    args = parser.parse_args()
    
    watcher = LogWatcher()
    
    if args.list:
        watcher.list_logs()
        return
    
    # 确定要监控的日志文件
    log_file = args.file
    if not log_file:
        log_file = watcher.find_latest_log(args.pattern)
        if not log_file:
            return
    
    # 开始监控
    if args.python:
        watcher.watch_python(log_file, args.lines)
    else:
        watcher.watch_with_tail(log_file, args.lines)

if __name__ == "__main__":
    main()