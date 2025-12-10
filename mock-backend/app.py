"""
Mock ADDA Backend Server
模拟ADDA自动化特征工程系统的后端服务
提供与真实系统完全一致的API接口，用于前端开发和测试
"""

import os
import json
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.serving import WSGIRequestHandler

# 导入配置和模块
from config import DEBUG, HOST, PORT, CORS_ORIGINS, SIMULATION_DELAYS
from data.mock_data import mock_generator

# 创建Flask应用
app = Flask(__name__)

# 配置CORS（与真实后端保持一致：全局允许，支持凭据）
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# 全局变量存储当前任务状态
current_task_id = None
execution_thread = None


@app.before_request
def log_request_info():
    """记录请求信息"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {request.method} {request.path}")
    print(f"Current task_id: {current_task_id}")
    if request.is_json:
        try:
            json_data = request.get_json()
            if json_data:  # 只有在有数据时才打印
                print(f"Request JSON: {json_data}")
        except Exception:
            pass  # 静默处理JSON解析错误
    elif request.form:
        print(f"Request Form: {dict(request.form)}")


def simulate_delay(operation: str):
    """模拟操作延迟"""
    delay = SIMULATION_DELAYS.get(operation, 1.0)
    time.sleep(delay)


# ==================== 任务相关API ====================

@app.route('/check-format/', methods=['POST'])
def check_format():
    """初始化特征工程任务"""
    global current_task_id

    try:
        # 获取表单数据
        if request.is_json:
            data = request.get_json()
            task_description = data.get('taskDescription', '')
            dataset_id = data.get('dataset', '')
            model_id = data.get('model', '')
        else:
            task_description = request.form.get('taskDescription', '')
            dataset_id = request.form.get('dataset', '')
            model_id = request.form.get('model', '')

        if not all([task_description, dataset_id, model_id]):
            return jsonify({
                'status': 'fail',
                'message': 'Missing required parameters: taskDescription, dataset, model'
            }), 400

        # 模拟初始化延迟
        simulate_delay('check_format')

        # 创建任务
        task_id = mock_generator.create_task(task_description, dataset_id, model_id)
        current_task_id = task_id

        return jsonify({
            'status': 'success',
            'message': f"Task initialized successfully: {task_description[:50]}..."
        })

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'Initialization failed: {str(e)}'
        }), 500


@app.route('/get-treejson/', methods=['POST'])
def get_treejson():
    """获取特征树结构数据"""
    global current_task_id

    try:
        # 获取请求数据（可以为空），安全地处理空请求体
        data = None
        content_length = request.content_length or 0

        if content_length > 0:
            try:
                if request.is_json:
                    data = request.get_json()
                elif request.form:
                    data = dict(request.form)
            except Exception:
                data = None

        if not current_task_id:
            return jsonify({
                'status': 'fail',
                'message': '尚未初始化任务'
            }), 400

        # 模拟数据获取延迟
        simulate_delay('get_treejson')

        # 生成特征树数据
        tree_result = mock_generator.generate_jsontree(current_task_id)

        return jsonify(tree_result)

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'获取特征树失败: {str(e)}'
        }), 500


@app.route('/next-step/', methods=['POST'])
def next_step():
    """执行下一步特征生成"""
    global current_task_id

    try:
        # 获取请求数据（可以为空），安全地处理空请求体
        data = None
        content_length = request.content_length or 0

        if content_length > 0:
            try:
                if request.is_json:
                    data = request.get_json()
                elif request.form:
                    data = dict(request.form)
            except Exception:
                data = None

        # 如果没有任务ID，自动创建一个默认任务
        if not current_task_id:
            task_description = "Auto-generated task for next-step"
            dataset_id = "2"  # Heart
            model_id = "2"   # Openai-gpt4o

            task_id = mock_generator.create_task(task_description, dataset_id, model_id)
            current_task_id = task_id
            print(f"Auto-created task: {task_id}")

        # 模拟长时间运行的特征生成过程
        simulate_delay('next_step')

        # 扩展特征树：选择一个节点，生成3个子节点
        expand_result = mock_generator.expand_tree(current_task_id)

        print(f"expand_result: {expand_result}")

        if expand_result['status'] == 'fail':
            return jsonify(expand_result), 400

        # 获取更新后的特征树
        tree_result = mock_generator.generate_jsontree(current_task_id)

        # 更新任务步骤
        if current_task_id in mock_generator.tasks:
            mock_generator.tasks[current_task_id]['current_step'] += 1

        # 添加通知
        mock_generator.add_notification(expand_result['message'], 'success')

        return jsonify({
            'status': 'success',
            'message': expand_result['message'],
            'json': tree_result['json']
        })

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'特征生成失败: {str(e)}'
        }), 500


@app.route('/auto-step/', methods=['POST'])
def auto_step():
    """独立端到端自动化特征工程和ML训练"""
    try:
        # 获取请求数据
        if request.is_json:
            data = request.get_json()
            task_description = data.get('taskDescription', '')
            dataset = data.get('dataset', '')
            model_type = data.get('model_type', 'RF')
            max_search_depth = data.get('max_search_depth', 2)
            use_performance_test = data.get('use_performance_test', True)
        else:
            task_description = request.form.get('taskDescription', '')
            dataset = request.form.get('dataset', '')
            model_type = request.form.get('model_type', 'RF')
            max_search_depth = int(request.form.get('max_search_depth', 2))
            use_performance_test = request.form.get('use_performance_test', 'true').lower() == 'true'

        if not all([task_description, dataset]):
            return jsonify({
                'status': 'fail',
                'message': 'Missing required parameters: taskDescription, dataset'
            }), 400

        # 模拟端到端执行延迟
        simulate_delay('auto_step')

        # 生成完整结果
        result = mock_generator.generate_auto_step_result(
            task_description, dataset, model_type, max_search_depth
        )

        # 添加端到端页面展示数据（与真实后端返回结构保持一致）
        e2e_data = mock_generator.get_all_e2e_data()
        importance_data = e2e_data.get('data', {}).get('importanceData', {})

        response_data = {
            'status': 'success',
            'message': result.get('message', 'End-to-end execution completed'),
            'data': {
                # 前端需要的可视化数据块
                **(e2e_data.get('data', {})),
                # 显式包含 shap/ig/rfe/fi/paperMetrics，避免被覆盖或缺失
                'importanceData': importance_data,
                # 其他与真实后端对齐的字段
                'status': result.get('status', 'success'),
                'tree': result.get('tree'),
                'finished': result.get('finished', True),
                'search_depth': result.get('search_depth'),
                'performance_metrics': result.get('performance_metrics'),
                'sql_code': result.get('sql_code'),
                'best_features': result.get('best_features'),
                'training_result': result.get('training_result')
            }
        }

        # 添加通知
        mock_generator.add_notification(
            f"End-to-end automated execution completed, model AUC: {result['performance_metrics']['auc']:.4f}",
            'success'
        )

        return jsonify(response_data)

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'End-to-end execution failed: {str(e)}'
        }), 500


# ==================== 性能测试API ====================

@app.route('/test-performance/', methods=['POST'])
def test_performance():
    """测试选定节点的性能"""
    try:
        data = request.get_json()
        selected_node_ids = data.get('selectedNodeIds', [])
        model_type = data.get('modelType', 'RF')
        use_in_db_ml = data.get('useInDbMl', True)

        if not selected_node_ids:
            return jsonify({
                'status': 'fail',
                'message': 'Please select nodes to test'
            }), 400

        # 模拟性能测试延迟
        simulate_delay('test_performance')

        # 生成性能测试结果
        result = mock_generator.generate_performance_metrics(
            current_task_id, selected_node_ids, model_type, use_in_db_ml
        )

        # 添加通知
        mock_generator.add_notification(
            f"Performance test completed, AUC: {result['performance_info']['score']:.4f}",
            'success'
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'性能测试失败: {str(e)}'
        }), 500


@app.route('/gen-model/', methods=['POST'])
def gen_model():
    """生成并下载模型文件"""
    try:
        data = request.get_json()
        selected_node_ids = data.get('selectedNodeIds', [])

        if not selected_node_ids:
            return jsonify({
                'status': 'fail',
                'message': '请选择要生成模型的节点'
            }), 400

        # 模拟模型生成延迟
        simulate_delay('gen_model')

        # 创建一个虚拟的模型文件
        model_content = f"""
# Mock ADDA Model File
# Generated on: {datetime.now().isoformat()}
# Selected Nodes: {selected_node_ids}
# Model Type: RF
# Features: {len(selected_node_ids)}

import pickle
import json

model_info = {{
    'model_type': 'RandomForest',
    'features': {selected_node_ids},
    'performance': {{
        'auc': 0.85,
        'accuracy': 0.82,
        'precision': 0.80,
        'recall': 0.78
    }},
    'created_at': '{datetime.now().isoformat()}'
}}

# 这是一个mock模型文件，用于前端测试
# 实际的模型训练需要在真实ADDA系统中进行
print("Mock model loaded successfully!")
print(f"Model info: {{json.dumps(model_info, indent=2)}}")
"""

        # 保存临时文件
        temp_file = '/tmp/mock_model.pkl'
        with open(temp_file, 'w') as f:
            f.write(model_content)

        # 添加通知
        mock_generator.add_notification("Model file generated successfully", 'success')

        return send_file(
            temp_file,
            as_attachment=True,
            download_name='model.pkl',
            mimetype='application/octet-stream'
        )

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'模型生成失败: {str(e)}'
        }), 500


# ==================== 任务控制API ====================

@app.route('/stop-task/', methods=['POST'])
def stop_task():
    """停止当前任务"""
    global current_task_id, execution_thread

    try:
        if not current_task_id:
            return jsonify({
                'status': 'fail',
                'message': '没有正在运行的任务'
            }), 400

        result = mock_generator.stop_task(current_task_id)

        # 停止执行线程（如果存在）
        if execution_thread and execution_thread.is_alive():
            # 这里可以添加线程停止逻辑
            pass

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'停止任务失败: {str(e)}'
        }), 500


@app.route('/clear-task/', methods=['POST'])
def clear_task():
    """清除任务状态"""
    global current_task_id, execution_thread

    try:
        if current_task_id:
            result = mock_generator.clear_task(current_task_id)
            current_task_id = None
            execution_thread = None
        else:
            result = {'status': 'success', 'message': '没有任务需要清除'}

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'清除任务失败: {str(e)}'
        }), 500


@app.route('/check-task-status/', methods=['POST'])
def check_task_status():
    """检查任务初始化状态"""
    global current_task_id

    try:
        # 获取请求数据（可以为空），安全地处理空请求体
        data = None
        content_length = request.content_length or 0

        if content_length > 0:
            try:
                if request.is_json:
                    data = request.get_json()
                elif request.form:
                    data = dict(request.form)
            except Exception:
                # 如果解析失败，忽略错误，继续处理
                data = None

        if not current_task_id:
            return jsonify({
                'status': 'success',
                'initialized': False,
                'message': '尚未初始化任务'
            })

        result = mock_generator.get_task_status(current_task_id)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'检查任务状态失败: {str(e)}'
        }), 500


# ==================== 通知系统API ====================

@app.route('/get-notifications/', methods=['GET'])
def get_notifications():
    """获取系统通知列表"""
    try:
        result = mock_generator.get_notifications()
        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'fail',
            'message': f'获取通知失败: {str(e)}'
        }), 500


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify({
        'status': 'fail',
        'message': 'API端点不存在'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    return jsonify({
        'status': 'fail',
        'message': '服务器内部错误'
    }), 500


@app.errorhandler(400)
def bad_request(error):
    """400错误处理"""
    return jsonify({
        'status': 'fail',
        'message': '请求参数错误'
    }), 400


# ==================== 健康检查 ====================

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'Mock ADDA Backend',
        'version': '1.0.0'
    })


@app.route('/', methods=['GET'])
def index():
    """根端点"""
    return jsonify({
        'service': 'Mock ADDA Backend',
        'description': '模拟ADDA自动化特征工程系统的后端服务',
        'version': '1.0.0',
        'endpoints': [
            'POST /check-format/ - 初始化任务',
            'POST /get-treejson/ - 获取特征树',
            'POST /next-step/ - 执行下一步',
            'POST /auto-step/ - 端到端执行',
            'POST /test-performance/ - 性能测试',
            'POST /gen-model/ - 生成模型',
            'POST /stop-task/ - 停止任务',
            'POST /clear-task/ - 清除任务',
            'POST /check-task-status/ - 检查状态',
            'GET /get-notifications/ - 获取通知',
            'GET /health - 健康检查'
        ]
    })


def main():
    """启动Flask应用"""
    print("启动Mock ADDA后端服务...")
    print(f"服务地址: http://{HOST}:{PORT}")
    print("健康检查: http://{}:{}/health".format(HOST, PORT))
    print("API文档: http://{}:{}/".format(HOST, PORT))
    print("=" * 50)

    # 禁用IPv6以避免端口冲突
    WSGIRequestHandler.protocol_version = "HTTP/1.1"

    app.run(
        host=HOST,
        port=PORT,
        debug=DEBUG,
        threaded=True
    )


if __name__ == '__main__':
    main()