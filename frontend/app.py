from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import io

from adda_connector import AddaConnector

# 导入LLMDagConstructor以支持端到端初始化
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.llm.llm_dag_util import LLMDagConstructor
from src.env import test_save_path, dataset_path

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
    """
    真正的端到端自动化特征工程和ML训练流程
    一次点击完成：根节点初始化 + 节点拓展(astar_k_step) + ML训练
    不依赖check format按钮，完全独立执行
    相当于完整执行 test_util.py + run_multimodel_type.py
    """
    try:
        # 获取请求参数（与start_task完全相同的参数）
        task_description = request.form.get('taskDescription') if request.form.get('taskDescription') else None
        if not task_description:
            # 也支持JSON格式
            data = json.loads(request.data) if request.data else {}
            task_description = data.get('taskDescription', '')

        if not task_description:
            return jsonify({"status": "fail", "message": "缺少必要参数：taskDescription"})

        dataset = request.form.get('dataset') if request.form.get('dataset') else None
        if not dataset:
            data = json.loads(request.data) if request.data else {}
            dataset = data.get('dataset', 'heart')

        model = request.form.get('model') if request.form.get('model') else None
        if not model:
            data = json.loads(request.data) if request.data else {}
            model = data.get('model_type', 'RF')  # 支持model_type或model参数

        # 可选参数
        data = json.loads(request.data) if request.data else {}
        max_search_depth = data.get('max_search_depth', 3)  # 最大搜索深度，默认3
        use_performance_test = data.get('use_performance_test', True)  # 是否执行性能测试

        print(f"Starting end-to-end execution: dataset={dataset}, model={model}, depth={max_search_depth}")

        # ===== 完整的任务初始化（复制start_task的逻辑） =====

        # 1. 从test_util导入任务配置
        from src.llm.tests.test_util import task_config
        task_name, target_col, task_type = task_config(dataset.lower())

        # 2. 导入并分割数据集
        from src.pg.import_table import importTable_with_split
        from src.env import get_conn
        importTable_with_split(
            os.path.join(dataset_path, task_name, "train_new.csv"),
            f"{task_name}_src_tb",
            target_col,
            get_conn(),
            False,
            task_type
        )

        # 3. 读取数据信息
        from src.llm.tests.test_util import read_data_info
        data_agenda, desc, csv_path = read_data_info(task_name)

        # 4. 创建新的LLMDagConstructor（强制新建，避免旧状态干扰）
        import os
        import shutil
        import heapq

        # 清理旧状态
        task_path = os.path.join(test_save_path, task_name)
        if os.path.exists(task_path):
            shutil.rmtree(task_path)

        # 初始化LLMDagConstructor
        adda.llm_dag_constructor = LLMDagConstructor(
            task_type=task_type,
            eval_model_type="RF",  # 硬编码为RF（与start_task保持一致）
            beam_limit=1,
            do_feature_selection=False,
            high_order_num=5,
            token_limit=128000
        )

        # 5. 设置A*搜索参数
        adda.llm_dag_constructor.search_type = "ASTAR"
        import src.llm.llm_dag_node
        src.llm.llm_dag_node.global_node_id = adda.llm_dag_constructor.node_id

        # 6. 初始化任务参数
        adda.llm_dag_constructor.init_task_params(data_agenda, desc, target_col, f"{task_name}_src_tb", csv_path, False, task_name)

        # 7. 初始化优先队列
        adda.llm_dag_constructor.cur_states = []
        heapq.heappush(adda.llm_dag_constructor.cur_states, adda.llm_dag_constructor.root)
        adda.llm_dag_constructor.pre_states = adda.llm_dag_constructor.cur_states.copy()
        adda.llm_dag_constructor.cur_states = adda.llm_dag_constructor.pre_states

        # 8. 设置计数器
        adda.count_idx = 0
        adda.llm_dag_constructor.pre_idx = 0

        # 9. 更新LLM模型配置
        from src.env import update_llm_model
        if model:
            update_llm_model(model)

        print(f"Task initialized successfully: {task_name}")

        # ===== 执行A*搜索 =====

        print(f"Starting A* search with max depth: {max_search_depth}")

        # 直接调用astar_k_step执行多步搜索
        try:
            adda.llm_dag_constructor.astar_k_step(
                step_num=max_search_depth,
                data_agenda=data_agenda,
                data_desc=desc,
                target_col=target_col,
                tb_name=f"{task_name}_src_tb",
                csv_path=csv_path,
                do_unfinished=False,  # 强制执行新的搜索
                task_name=task_name
            )

            print(f"A* search completed with {max_search_depth} steps")

        except Exception as search_error:
            print(f"A* search error: {search_error}")
            return jsonify({
                "status": "fail",
                "message": f"A*搜索失败: {str(search_error)}"
            })

        # 保存状态（为SQL生成做准备）
        import pickle
        from src.env import proj_path
        with open(os.path.join(proj_path, "src", "cur_states.pkl"), "wb") as f:
            pickle.dump(adda.llm_dag_constructor, f)

        # 获取当前树结构
        tree_structure = adda._convert_dag_to_tree()

        # 检查是否完成搜索
        is_finished = adda.llm_dag_constructor.finish

        # 初始化返回数据
        response_data = {
            "status": "success",
            "tree": tree_structure,
            "finished": is_finished,
            "search_depth": max_search_depth,
            "message": f"端到端执行完成！搜索深度: {max_search_depth}"
        }

        # ===== 执行性能测试 =====

        if use_performance_test and is_finished:
            try:
                print("Starting performance testing...")
                performance_result = adda._run_multimodal_performance(
                    model_type=model,
                    task_name=task_name
                )

                if performance_result.get("success", False):
                    # 性能测试成功
                    auc = performance_result.get("auc", 0.0)
                    exec_time = performance_result.get("execution_time", 0.0)

                    response_data.update({
                        "performance_metrics": {
                            "auc": auc,
                            "execution_time": exec_time,
                            "model_type": performance_result.get("model_type", model),
                            "task_name": performance_result.get("task_name", task_name),
                            "task_type": performance_result.get("task_type", task_type),
                            "row_num": performance_result.get("row_num", 0),
                            "col_num": performance_result.get("col_num", 0),
                            "method": performance_result.get("method", "in_database_ml")
                        },
                        "sql_code": performance_result.get("sql_code", {}),
                        "sql_file_paths": performance_result.get("sql_file_paths", {}),
                        "training_result": {
                            "success": True,
                            "message": f"端到端流程完成！AUC: {auc:.4f}, 耗时: {exec_time:.2f}s",
                            "model_type": model,
                            "method": "in_database_ml"
                        }
                    })

                    # 添加成功通知
                    notifications.append({
                        "notice_description": f"🎉 端到端流程完成！AUC: {auc:.4f}, 搜索深度: {max_search_depth}, 耗时: {exec_time:.2f}s",
                        "notice_type": "success"
                    })
                else:
                    # 性能测试失败
                    error_msg = performance_result.get("error", "未知错误")
                    response_data.update({
                        "performance_metrics": {
                            "auc": 0.0,
                            "execution_time": 0.0,
                            "model_type": model,
                            "method": "error",
                            "error": error_msg
                        },
                        "training_result": {
                            "success": False,
                            "message": f"性能测试失败: {error_msg}",
                            "model_type": model,
                            "method": "error"
                        }
                    })

                    # 添加警告通知
                    notifications.append({
                        "notice_description": f"特征搜索完成，但性能测试失败: {error_msg}",
                        "notice_type": "warning"
                    })

            except Exception as perf_error:
                # 性能测试异常
                error_msg = f"性能测试异常: {str(perf_error)}"
                response_data.update({
                    "performance_metrics": {
                        "auc": 0.0,
                        "execution_time": 0.0,
                        "model_type": model,
                        "method": "exception",
                        "error": error_msg
                    },
                    "training_result": {
                        "success": False,
                        "message": error_msg,
                        "model_type": model,
                        "method": "exception"
                    }
                })

                # 添加错误通知
                notifications.append({
                    "notice_description": f"特征搜索完成，但性能测试异常: {error_msg}",
                    "notice_type": "error"
                })

        # 如果没有执行性能测试或搜索未完成，添加相应的状态信息
        if not use_performance_test:
            notifications.append({
                "notice_description": f"特征搜索完成！搜索深度: {max_search_depth}，未执行性能测试",
                "notice_type": "info"
            })
        elif not is_finished:
            notifications.append({
                "notice_description": f"特征搜索执行了 {max_search_depth} 步，但尚未完成最佳特征选择",
                "notice_type": "info"
            })

        return jsonify(response_data)

    except Exception as e:
        # 记录详细错误信息
        import traceback
        error_details = traceback.format_exc()
        print(f"Auto step error: {error_details}")

        # 添加错误通知
        notifications.append({
            "notice_description": f"端到端执行失败: {str(e)}",
            "notice_type": "error"
        })

        return jsonify({
            "status": "fail",
            "message": str(e),
            "error_details": error_details
        })


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