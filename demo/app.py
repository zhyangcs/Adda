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
    try:
        data = json.loads(request.data)
        selected_node_ids = data.get('selectedNodeIds', [])
        
        # 获取任务配置信息
        task_type = adda.llm_dag_constructor.task_type if adda.llm_dag_constructor else "unknown"
        
        if not selected_node_ids:
            return jsonify({"status": "fail", "message": "没有选择特征"})
        
        success, result, _ = adda.test_performance(selected_node_ids)
        
        if success:
            notifications.append({
                "notice_description": f"节点 {selected_node_ids} 的性能: {result}",
                "notice_type": "success"
            })
            return jsonify({"status": "success", "message": result})
        else:
            return jsonify({"status": "fail", "message": result})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

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

if __name__ == '__main__':
    app.run(debug=True, port=5000) 