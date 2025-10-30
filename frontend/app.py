from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import io

from adda_connector import AddaConnector

app = Flask(__name__)

# 创建Adda系统连接器实例
adda = AddaConnector()

# 存储临时通知信息
notifications = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check-format/', methods=['POST'])
def check_format():
    task_description = request.form.get('taskDescription')
    dataset = request.form.get('dataset')
    model = request.form.get('model')
    
    try:
        success, message, tree_data = adda.start_task(task_description, dataset, model)
        
        from src.env import update_llm_model
        if model:
            update_llm_model(model)
        
        if success:
            notifications.append({
                "notice_description": f"任务启动成功: {task_description[:30]}..., 数据集: {dataset}, 模型: {model}",
                "notice_type": "success"
            })
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"status": "fail", "message": message})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/get-treejson/', methods=['POST'])
def get_tree_json():
    try:
        if adda.current_tree:
            return jsonify({"status": "success", "json": adda.current_tree})
        else:
            return jsonify({"status": "fail", "message": "没有活动任务，请先启动任务"})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/next-step/', methods=['POST'])
def next_step():
    try:
        success, message, updated_tree = adda.next_step()
        
        if success:
            notifications.append({
                "notice_description": message,
                "notice_type": "success"
            })
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"status": "fail", "message": message})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/test-performance/', methods=['POST'])
def test_performance():
    """
    测试选定节点的性能
    支持新的参数：模型类型、是否使用in-database ML
    """
    try:
        data = json.loads(request.data)
        selected_node_ids = data.get('selectedNodeIds', [])

        # 获取可选参数
        model_type = data.get('modelType', 'RF')  # 默认使用随机森林
        use_in_db_ml = data.get('useInDbMl', True)  # 默认使用in-database ML

        # 获取任务配置信息
        task_type = adda.llm_dag_constructor.task_type if adda.llm_dag_constructor else "unknown"

        if not selected_node_ids:
            return jsonify({
                "status": "fail",
                "message": "没有选择特征",
                "details": "请至少选择一个节点进行性能测试"
            })

        # 调用增强的test_performance方法
        success, result, performance_info = adda.test_performance(
            selected_node_ids,
            model_type=model_type,
            use_in_db_ml=use_in_db_ml
        )

        if success:
            # 构建通知消息
            node_desc = f"节点 {selected_node_ids}" if len(selected_node_ids) > 1 else f"节点 {selected_node_ids[0]}"

            notifications.append({
                "notice_description": f"{node_desc} 性能测试完成: {result}",
                "notice_type": "success"
            })

            # 构建响应数据
            response_data = {
                "status": "success",
                "message": result,
                "performance_info": performance_info,
                "selected_nodes": selected_node_ids,
                "model_type": model_type,
                "method": "in_database_ml" if use_in_db_ml else "simulation"
            }

            # 如果是in-database ML，添加SQL代码信息
            if use_in_db_ml and performance_info and "sql_code" in performance_info:
                response_data["sql_code"] = performance_info["sql_code"]
                response_data["sql_file_paths"] = performance_info.get("sql_file_paths", {})

            return jsonify(response_data)
        else:
            return jsonify({
                "status": "fail",
                "message": result,
                "selected_nodes": selected_node_ids,
                "model_type": model_type
            })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": f"性能测试失败: {str(e)}",
            "error_details": str(e)
        })

@app.route('/gen-model/', methods=['POST'])
def gen_model():
    try:
        data = json.loads(request.data)
        selected_node_ids = data.get('selectedNodeIds', [])
        
        # if not selected_node_ids:
        #     return jsonify({"status": "fail", "message": "没有选择特征"})
        # TODO: 可能gen_model有更复杂的逻辑，比如需要选择特征，或者需要选择模型，这里暂时先这样处理
        
        if not adda.llm_dag_constructor:
            return jsonify({"status": "fail", "message": "任务未初始化，请先点击Check Format"})
        
        success, message, model_bytes = adda.generate_model(selected_node_ids)
        
        if success:
            notifications.append({
                "notice_description": f"使用特征 {selected_node_ids} 生成模型成功",
                "notice_type": "success"
            })
            
            # 创建内存文件并返回模型文件
            model_io = io.BytesIO(model_bytes)
            model_io.seek(0)
            
            return send_file(
                model_io,
                mimetype='application/octet-stream',
                as_attachment=True,
                download_name='model.pkl'
            )
        else:
            return jsonify({"status": "fail", "message": message})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/stop-task/', methods=['POST'])
def stop_task():
    try:
        success, message = adda.stop_task()
        return jsonify({"status": "success" if success else "fail", "message": message})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/clear-task/', methods=['POST'])
def clear_task():
    try:
        success, message = adda.clear_task()
        return jsonify({"status": "success" if success else "fail", "message": message})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/auto-step/', methods=['POST'])
def auto_step():
    try:
        if not adda.llm_dag_constructor or adda.llm_dag_constructor.finish:
            return jsonify({"status": "fail", "message": "任务未启动或已完成"})
            
        # 单步执行（正确方式）
        for i in range(3):  # 分步执行避免清空状态 TODO: 这里的循环实际无用
            adda.llm_dag_constructor.astar_one_step(i)
        
        return jsonify({
            "status": "success",
            "tree": adda._convert_dag_to_tree(),
            "finished": adda.llm_dag_constructor.finish
        })
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

# 添加获取通知列表的接口（如果前端需要）
@app.route('/get-notifications/', methods=['GET'])
def get_notifications():
    return jsonify({"notifications": notifications})

@app.route('/check-task-status/', methods=['POST'])
def check_task_status():
    try:
        if not hasattr(adda, 'llm_dag_constructor') or adda.llm_dag_constructor is None:
            return jsonify({
                "status": "fail",
                "message": "请先点击Check Format按钮初始化任务"
            })
        return jsonify({"status": "success", "initialized": True})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/train-node-model/', methods=['POST'])
def train_node_model():
    """
    对指定节点进行in-DB ML模型训练
    接收参数:
    - node_id: 节点ID
    - dataset: 数据集类型 (如: heart, diabetes, titanic等)
    - model_type: 模型类型 (RF/XGB/LightGBM等)
    """
    try:
        data = json.loads(request.data)
        node_id = data.get('node_id')
        dataset = data.get('dataset')
        model_type = data.get('model_type', 'RF')

        if not node_id:
            return jsonify({"status": "fail", "message": "缺少node_id参数"})

        if not dataset:
            return jsonify({"status": "fail", "message": "缺少dataset参数"})

        if not model_type:
            return jsonify({"status": "fail", "message": "缺少model_type参数"})

        # 调用核心训练逻辑
        success, result, performance_metrics = adda.train_on_single_node(
            node_id=node_id,
            task_name=dataset,  # 使用dataset作为task_name
            model_type=model_type,
            dataset_path=None   # 内部会根据dataset构建路径
        )

        if success:
            notifications.append({
                "notice_description": f"节点 {node_id} 使用模型 {model_type} 训练成功",
                "notice_type": "success"
            })

            return jsonify({
                "status": "success",
                "message": f"节点 {node_id} 训练成功",
                "result": result,
                "performance_metrics": performance_metrics
            })
        else:
            return jsonify({"status": "fail", "message": result})

    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000) 