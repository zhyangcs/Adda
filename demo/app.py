from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import requests
import io
import pickle

# 配置
BACKEND_URL = "http://localhost:8000"  # 后端服务地址，根据实际情况修改

app = Flask(__name__)

# 临时存储树结构数据
tree_data = {
    "root_id": 1,
    "parent_child_relations": [[1, 2], [1, 3], [2, 4], [2, 5], [3, 6]],
    "node_info": [
        {"node_id": 1, "feature_name": "Root", "task_code": "root", "op_type": "root", "operation_desc": "Root node"},
        {"node_id": 2, "feature_name": "Age", "task_code": "age", "op_type": "basic", "operation_desc": "Passenger age"},
        {"node_id": 3, "feature_name": "Sex", "task_code": "sex", "op_type": "basic", "operation_desc": "Passenger gender"},
        {"node_id": 4, "feature_name": "Age^2", "task_code": "age_squared", "op_type": "transform", "operation_desc": "Age squared"},
        {"node_id": 5, "feature_name": "Age Group", "task_code": "age_group", "op_type": "category", "operation_desc": "Age categorized"},
        {"node_id": 6, "feature_name": "Gender Code", "task_code": "gender_code", "op_type": "encoding", "operation_desc": "Gender encoded"}
    ],
    "cur_selected_idx": []
}

# 存储临时通知信息
notifications = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check-format/', methods=['POST'])
def check_format():
    # 从请求中获取表单数据
    task_description = request.form.get('taskDescription')
    dataset = request.form.get('dataset')
    model = request.form.get('model')
    
    try:
        # 这里可以添加实际的格式检查逻辑，或者转发请求到后端
        # 例如：response = requests.post(f"{BACKEND_URL}/check-format/", data=request.form)
        
        # 示例：模拟成功响应
        if task_description and dataset and model:
            notifications.append({
                "notice_description": f"Task: {task_description[:30]}..., Dataset: {dataset}, Model: {model}",
                "notice_type": "success"
            })
            return jsonify({"status": "success", "message": "Format check passed"})
        else:
            return jsonify({"status": "fail", "message": "Missing required fields"})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/get-treejson/', methods=['POST'])
def get_tree_json():
    try:
        # 实际项目中，这里应该从后端获取真实数据
        # 例如：response = requests.post(f"{BACKEND_URL}/get-tree-json/")
        # tree_data = response.json()
        
        # 模拟成功响应
        notifications.append({
            "notice_description": "Retrieved tree structure successfully",
            "notice_type": "success"
        })
        return jsonify({"status": "success", "json": tree_data})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/next-step/', methods=['POST'])
def next_step():
    try:
        # 实际项目中，这里应该向后端发送请求
        # 例如：response = requests.post(f"{BACKEND_URL}/next-step/")
        
        # 模拟后端处理：添加新节点到树
        new_node_id = len(tree_data["node_info"]) + 1
        parent_id = tree_data["node_info"][-1]["node_id"]
        
        tree_data["node_info"].append({
            "node_id": new_node_id,
            "feature_name": f"Feature {new_node_id}",
            "task_code": f"feature_{new_node_id}",
            "op_type": "generated",
            "operation_desc": f"Generated feature {new_node_id}"
        })
        
        tree_data["parent_child_relations"].append([parent_id, new_node_id])
        
        notifications.append({
            "notice_description": f"Generated new feature (ID: {new_node_id})",
            "notice_type": "success"
        })
        
        return jsonify({"status": "success", "message": "Next step completed"})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/test-performance/', methods=['POST'])
def test_performance():
    try:
        # 获取请求中的已选节点IDs
        data = json.loads(request.data)
        selected_node_ids = data.get('selectedNodeIds', [])
        
        if not selected_node_ids:
            return jsonify({"status": "fail", "message": "No features selected"})
        
        # 实际项目中，这里应该向后端发送请求
        # 例如：response = requests.post(f"{BACKEND_URL}/test-performance/", json=data)
        
        # 模拟性能评估结果
        performance = 0.85 + (len(selected_node_ids) * 0.01)
        if performance > 0.95:
            performance = 0.95
            
        result = f"{performance:.4f}"
        
        notifications.append({
            "notice_description": f"Performance of nodes {selected_node_ids}: {result}",
            "notice_type": "success"
        })
        
        return jsonify({"status": "success", "message": result})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/gen-model/', methods=['POST'])
def gen_model():
    try:
        # 获取请求中的已选节点IDs
        data = json.loads(request.data)
        selected_node_ids = data.get('selectedNodeIds', [])
        
        if not selected_node_ids:
            return jsonify({"status": "fail", "message": "No features selected"})
        
        # 实际项目中，这里应该向后端发送请求并获取模型文件
        # 例如：response = requests.post(f"{BACKEND_URL}/gen-model/", json=data, stream=True)
        
        # 模拟生成模型
        class DummyModel:
            def predict(self, X):
                return [1] * len(X)
                
        model = DummyModel()
        
        # 创建内存文件并序列化模型
        model_bytes = io.BytesIO()
        pickle.dump(model, model_bytes)
        model_bytes.seek(0)
        
        notifications.append({
            "notice_description": f"Generated model with features {selected_node_ids}",
            "notice_type": "success"
        })
        
        # 返回序列化的模型文件供下载
        return send_file(
            model_bytes,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='model.pkl'
        )
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000) 