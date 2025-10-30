#!/usr/bin/env python3
# start_and_test.py
"""
启动Flask服务器并测试单节点训练接口的脚本
"""

import subprocess
import time
import requests
import json
import sys
import os

def check_flask_server_running():
    """检查Flask服务器是否在运行"""
    try:
        response = requests.get("http://localhost:5000/", timeout=5)
        return response.status_code == 200
    except:
        return False

def start_flask_server():
    """启动Flask服务器"""
    print("🚀 启动Flask服务器...")
    try:
        # 启动Flask应用
        process = subprocess.Popen([
            sys.executable, "app.py"
        ], cwd=os.path.dirname(__file__))

        # 等待服务器启动
        for i in range(10):  # 最多等待10秒
            time.sleep(1)
            if check_flask_server_running():
                print(f"✅ Flask服务器已启动 (PID: {process.pid})")
                return process
            print(f"⏳ 等待服务器启动... ({i+1}/10)")

        print("❌ Flask服务器启动超时")
        process.terminate()
        return None

    except Exception as e:
        print(f"❌ 启动Flask服务器失败: {str(e)}")
        return None

def test_train_node_model():
    """测试单节点训练接口"""
    print("\n🧪 测试单节点训练接口...")

    # API端点
    url = "http://localhost:5000/train-node-model/"

    # 测试数据
    test_data = {
        "node_id": "1",     # 测试根节点
        "dataset": "heart", # 使用heart数据集类型
        "model_type": "RF"  # 随机森林模型
    }

    try:
        print("发送POST请求到:", url)
        print("请求数据:", json.dumps(test_data, indent=2))

        response = requests.post(url, json=test_data, timeout=60)

        print(f"响应状态码: {response.status_code}")

        try:
            result = response.json()
            print(f"响应内容: {json.dumps(result, indent=2)}")

            if result.get("status") == "success":
                print("✅ 测试成功!")
                print(f"性能指标: {result.get('performance_metrics')}")
                return True
            else:
                print(f"❌ 测试失败: {result.get('message')}")
                return False
        except json.JSONDecodeError:
            print(f"响应内容（非JSON）: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("❌ 请求超时 - 训练可能需要更长时间")
        return False
    except Exception as e:
        print(f"❌ 测试出错: {str(e)}")
        return False

def main():
    """主函数"""
    print("=== 单节点训练接口测试 ===\n")

    # 1. 检查Flask服务器是否已运行
    print("1. 检查Flask服务器状态...")
    if check_flask_server_running():
        print("✅ Flask服务器已在运行")
        flask_process = None
    else:
        print("🔄 Flask服务器未运行，尝试启动...")
        flask_process = start_flask_server()

        if not flask_process:
            print("\n💥 无法启动Flask服务器，请检查:")
            print("   - 是否在frontend目录下")
            print("   - 依赖是否已安装 (pip install flask)")
            print("   - 端口5000是否被占用")
            sys.exit(1)

    # 2. 测试API接口
    print("\n2. 测试单节点训练接口...")
    success = test_train_node_model()

    # 3. 输出结果
    if success:
        print("\n🎉 所有测试通过!")
        print("单节点训练接口工作正常，可以供autofe-frontend调用。")
    else:
        print("\n💥 测试失败")
        print("可能的原因:")
        print("   - PostgreSQL数据库未启动")
        print("   - 数据集文件不存在")
        print("   - 环境配置问题")
        print("   - 依赖模块缺失")

    # 4. 清理
    if flask_process:
        print(f"\n🛑 停止Flask服务器 (PID: {flask_process.pid})...")
        flask_process.terminate()
        flask_process.wait()

if __name__ == "__main__":
    main()