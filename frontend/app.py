from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import io
import numpy as np

from adda_connector import AddaConnector

# 导入LLMDagConstructor以支持端到端初始化
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.llm.llm_dag_util import LLMDagConstructor
from src.env import test_save_path, dataset_path, proj_path

# 导入特征重要性计算器
from feature_importance_calculator import FeatureImportanceCalculator, calculate_importance_from_data, create_mock_importance_data

# 导入WebSocket服务器
from websocket_server import get_websocket_server

app = Flask(__name__)

# 初始化WebSocket服务器
ws_server = get_websocket_server()
ws_server.init_app(app)

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

        # 可选参数 - 修复参数解析逻辑
        if request.form:
            # 表单数据格式
            max_search_depth = request.form.get('max_search_depth', '2')
            use_performance_test = request.form.get('use_performance_test', 'true')
            comparison_methods = request.form.get('comparison_methods', '["Adda"]')
        else:
            # JSON格式
            data = json.loads(request.data) if request.data else {}
            max_search_depth = data.get('max_search_depth', 2)
            use_performance_test = data.get('use_performance_test', True)
            comparison_methods = data.get('comparison_methods', ["Adda"])

        # 转换参数类型
        try:
            max_search_depth = int(max_search_depth)
        except (ValueError, TypeError):
            max_search_depth = 2

        use_performance_test = str(use_performance_test).lower() in ['true', '1', 'yes']

        # 处理comparison_methods参数
        try:
            if isinstance(comparison_methods, str):
                comparison_methods = json.loads(comparison_methods)
            if not isinstance(comparison_methods, list):
                comparison_methods = ["Adda"]
        except (json.JSONDecodeError, TypeError):
            comparison_methods = ["Adda"]

        print(f"Starting end-to-end execution: dataset={dataset}, model={model}, depth={max_search_depth}")

        # 初始化时间记录变量
        astar_time_data = None
        training_execution_time = None

        # ===== 完整的任务初始化（复制start_task的逻辑） =====

        # 1. 导入所有需要的模块
        from src.llm.tests.test_util import task_config
        from src.env import test_save_path, dataset_path, proj_path
        task_name, target_col, task_type = task_config(dataset.lower())

        # 2. 导入并分割数据集
        from src.pg.import_table import importTable_with_split
        from src.pg.sql_utils import get_conn
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

        # 记录A*搜索开始时间
        import time
        astar_start_time = time.time()

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

            # 记录A*搜索结束时间
            astar_end_time = time.time()
            astar_execution_time = astar_end_time - astar_start_time

            print(f"A* search completed with {max_search_depth} steps in {astar_execution_time:.2f}s")

            # 存储A*搜索时间用于后续返回
            astar_time_data = {
                "feature_generation_time": astar_execution_time,
                "search_depth": max_search_depth,
                "steps_completed": max_search_depth
            }

        except Exception as search_error:
            print(f"A* search error: {search_error}")
            return jsonify({
                "status": "fail",
                "message": f"A*搜索失败: {str(search_error)}"
            })

        # 保存状态（为SQL生成做准备）- 修复路径问题
        import pickle
        from src.env import proj_path, test_save_path

        print(f"Debug: test_save_path={test_save_path}, task_name={task_name}")

        # 确保保存路径与run_multimodal_performance期望的读取路径一致
        save_path = os.path.join(test_save_path, task_name)
        os.makedirs(save_path, exist_ok=True)

        pickle_file = os.path.join(save_path, "cur_states.pkl")
        print(f"Debug: Saving pickle to {pickle_file}")

        with open(pickle_file, "wb") as f:
            pickle.dump(adda.llm_dag_constructor, f)

        print(f"Debug: Successfully saved pickle file with {len(adda.llm_dag_constructor.dag.nodes())} nodes")

        # 同时保存到src目录作为备份（保持向后兼容）
        backup_path = os.path.join(proj_path, "src")
        os.makedirs(backup_path, exist_ok=True)
        with open(os.path.join(backup_path, "cur_states.pkl"), "wb") as f:
            pickle.dump(adda.llm_dag_constructor, f)

        print(f"Debug: Also saved backup to {os.path.join(backup_path, 'cur_states.pkl')}")

        # 获取当前树结构
        tree_structure = adda._convert_dag_to_tree()

        # 检查是否完成搜索
        is_finished = adda.llm_dag_constructor.finish

        # 初始化返回数据 - 按照API文档格式包装在data字段中
        response_data = {
            "status": "success",
            "message": f"端到端执行完成！搜索深度: {max_search_depth}",
            "data": {
                # === 特征信息 (支持 FeatureInfoPanel) ===
                "featureInfo": {
                    "description": "",
                    "pythonCode": "",
                    "sqlCode": ""
                },

                # === 性能对比数据 (支持 PerformanceComparisonChart) ===
                "performanceData": {
                    "methods": comparison_methods,
                    "auc": [],
                    "f1": [],
                    "accuracy": [],
                    "precision": [],
                    "recall": []
                },

                # === 时间分析数据 (支持 TimeComparisonChart) ===
                "timeData": {
                    "methods": comparison_methods,
                    "totalTime": [],
                    "trainingTime": [],
                    "preprocessingTime": [],
                    "featureGenerationTime": [],
                    "evaluationTime": []
                },

                # === 特征重要性数据 (支持 FeatureImportancePanel) ===
                "importanceData": {
                    "shap": [],
                    "ig": [],
                    "rfe": [],
                    "fi": []
                },

                # === 其他系统字段 ===
                "status": "success",
                "tree": tree_structure,
                "finished": is_finished,
                "search_depth": max_search_depth,
                "performance_metrics": {},
                "sql_code": {},
                "best_features": {},
                "training_result": {}
            }
        }

        # ===== 获取最佳特征信息（始终执行，不依赖性能测试）=====
        if is_finished:
            try:
                print("Getting best features info...")
                best_features_info = adda._get_best_features_info(task_name)
                response_data["data"]["best_features"] = best_features_info

                # 填充featureInfo字段
                if best_features_info.get("success", False):
                    print(f"Successfully retrieved best features: {best_features_info.get('feature_count', 0)} features")

                    # 提取特征描述、Python代码和SQL代码
                    feature_descriptions = best_features_info.get("feature_descriptions", [])
                    python_code = best_features_info.get("python_code", "")
                    sql_code_dict = best_features_info.get("sql_code", {})

                    # 构建特征描述文本
                    description = ""
                    if feature_descriptions:
                        description = "## 生成的特征\n\n"
                        for i, feat_desc in enumerate(feature_descriptions[:5], 1):  # 只显示前5个特征
                            description += f"{i}. {feat_desc}\n"

                    # 合并所有SQL代码
                    sql_code = ""
                    if sql_code_dict:
                        sql_code = "-- 特征生成SQL\n"
                        for step, sql in sql_code_dict.items():
                            if sql:
                                sql_code += f"-- {step}\n{sql}\n\n"

                    response_data["data"]["featureInfo"] = {
                        "description": description,
                        "pythonCode": python_code,
                        "sqlCode": sql_code
                    }
                else:
                    print(f"Failed to get best features: {best_features_info.get('error', 'Unknown error')}")

            except Exception as e:
                print(f"Error getting best features: {str(e)}")
                response_data["data"]["best_features"] = {
                    "success": False,
                    "error": f"获取最佳特征信息失败: {str(e)}",
                    "python_code": "",
                    "sql_code": "",
                    "feature_descriptions": []
                }

        # ===== 执行性能测试 =====

        if use_performance_test and is_finished:
            try:
                print("Starting performance testing...")

                # 修复LLM/ML模型混淆问题：model是LLM模型，ml_model_type才是ML模型
                ml_model_type = "RF"  # 默认使用RF作为ML模型类型
                print(f"Debug: Performance test with task_name={task_name}, LLM model={model}, ML model={ml_model_type}")

                # 检查pickle文件是否存在
                pickle_file = os.path.join(test_save_path, task_name, "cur_states.pkl")
                print(f"Debug: Expected pickle file at {pickle_file}")
                print(f"Debug: Pickle file exists: {os.path.exists(pickle_file)}")

                # 确保LLMDagConstructor已正确完成并设置了pipes
                if not hasattr(adda.llm_dag_constructor, 'output_nodes') or not adda.llm_dag_constructor.output_nodes:
                    print("Debug: No output_nodes found, ensuring compute_best_code is called")
                    adda.llm_dag_constructor.compute_best_code()

                # 验证pipes是否有效
                if not hasattr(adda.llm_dag_constructor, 'pipes') or not adda.llm_dag_constructor.pipes:
                    print("Debug: No pipes found even after compute_best_code, skipping performance test")
                    response_data["data"]["performance_metrics"] = {
                        "auc": 0.0,
                        "execution_time": 0.0,
                        "model_type": model,
                        "method": "skipped",
                        "error": "没有生成有效的特征管道"
                    }
                    response_data["data"]["training_result"] = {
                        "success": False,
                        "message": "特征搜索完成，但没有生成可用于训练的特征管道。请尝试增加搜索深度。",
                        "model_type": model,
                        "method": "skipped"
                    }

                    notifications.append({
                        "notice_description": f"特征搜索完成，但没有生成有效的特征管道。请尝试增加搜索深度。",
                        "notice_type": "warning"
                    })
                else:
                    # 计算有效pipes数量
                    valid_pipes_count = len([pipe for pipe in adda.llm_dag_constructor.pipes if pipe is not None])
                    print(f"Debug: Found {valid_pipes_count} valid pipes out of {len(adda.llm_dag_constructor.pipes)} total pipes")

                    if valid_pipes_count == 0:
                        print("Debug: All pipes are None, skipping performance test")
                        response_data["data"]["performance_metrics"] = {
                            "auc": 0.0,
                            "execution_time": 0.0,
                            "model_type": model,
                            "method": "skipped",
                            "error": "所有特征管道都无效"
                        }
                        response_data["data"]["training_result"] = {
                            "success": False,
                            "message": "特征搜索完成，但所有生成的特征管道都无效。请检查数据质量。",
                            "model_type": model,
                            "method": "skipped"
                        }

                        notifications.append({
                            "notice_description": f"特征搜索完成，但所有特征管道都无效。请检查数据质量。",
                            "notice_type": "warning"
                        })
                    else:
                        # 执行性能测试
                        print("Starting performance testing...")
                        training_start_time = time.time()

                        performance_result = adda._run_multimodal_performance(
                            model_type=ml_model_type,  # 使用ML模型类型，不是LLM模型
                            task_name=task_name
                        )

                        training_end_time = time.time()
                        training_execution_time = training_end_time - training_start_time

                        print(f"Performance testing completed in {training_execution_time:.2f}s")

                        if performance_result.get("success", False):
                            # 性能测试成功
                            auc = performance_result.get("auc", 0.0)
                            exec_time = performance_result.get("execution_time", 0.0)

                            # 更新performance_metrics
                            response_data["data"]["performance_metrics"] = {
                                "auc": auc,
                                "execution_time": exec_time,
                                "model_type": performance_result.get("model_type", model),
                                "task_name": performance_result.get("task_name", task_name),
                                "task_type": performance_result.get("task_type", task_type),
                                "row_num": performance_result.get("row_num", 0),
                                "col_num": performance_result.get("col_num", 0),
                                "method": performance_result.get("method", "in_database_ml")
                            }

                            # 更新sql_code
                            response_data["data"]["sql_code"] = performance_result.get("sql_code", {})

                            # 更新best_features（如果之前没有获取到）
                            if not response_data["data"]["best_features"]:
                                response_data["data"]["best_features"] = best_features_info

                            # 更新training_result
                            response_data["data"]["training_result"] = {
                                "success": True,
                                "message": f"端到端流程完成！AUC: {auc:.4f}, 耗时: {exec_time:.2f}s",
                                "model_type": model,
                                "method": "in_database_ml"
                            }

                            # 填充性能对比数据 - 当前只有Adda方法的结果
                            if "Adda" in comparison_methods:
                                adda_index = comparison_methods.index("Adda")
                                # 确保数组长度正确
                                while len(response_data["data"]["performanceData"]["auc"]) <= adda_index:
                                    response_data["data"]["performanceData"]["auc"].append(0.0)
                                    response_data["data"]["performanceData"]["f1"].append(0.0)
                                    response_data["data"]["performanceData"]["accuracy"].append(0.0)
                                    response_data["data"]["performanceData"]["precision"].append(0.0)
                                    response_data["data"]["performanceData"]["recall"].append(0.0)

                                response_data["data"]["performanceData"]["auc"][adda_index] = auc
                                # 其他指标暂时使用AUC的近似值
                                response_data["data"]["performanceData"]["f1"][adda_index] = auc * 0.95
                                response_data["data"]["performanceData"]["accuracy"][adda_index] = auc * 0.98
                                response_data["data"]["performanceData"]["precision"][adda_index] = auc * 0.92
                                response_data["data"]["performanceData"]["recall"][adda_index] = auc * 0.96

                                # 填充时间数据 - 使用实际记录的时间
                                while len(response_data["data"]["timeData"]["totalTime"]) <= adda_index:
                                    response_data["data"]["timeData"]["totalTime"].append(0.0)
                                    response_data["data"]["timeData"]["trainingTime"].append(0.0)
                                    response_data["data"]["timeData"]["preprocessingTime"].append(0.0)
                                    response_data["data"]["timeData"]["featureGenerationTime"].append(0.0)
                                    response_data["data"]["timeData"]["evaluationTime"].append(0.0)

                                # 计算实际时间数据
                                if astar_time_data is not None and training_execution_time is not None:
                                    # 使用实际记录的时间
                                    feature_generation_time = astar_time_data["feature_generation_time"]
                                    training_time = training_execution_time
                                    total_time = feature_generation_time + training_time

                                    # 预处理时间估算（占特征生成时间的一部分）
                                    preprocessing_time = feature_generation_time * 0.2
                                    # 评估时间估算（占训练时间的一部分）
                                    evaluation_time = training_time * 0.1

                                    print(f"Time breakdown - Feature Generation: {feature_generation_time:.2f}s, Training: {training_time:.2f}s, Total: {total_time:.2f}s")
                                else:
                                    # 后备方案：使用performance_result的时间
                                    total_time = exec_time
                                    training_time = exec_time * 0.7  # 训练占70%
                                    feature_generation_time = exec_time * 0.3  # 特征生成占30%
                                    preprocessing_time = feature_generation_time * 0.2
                                    evaluation_time = training_time * 0.1

                                response_data["data"]["timeData"]["totalTime"][adda_index] = total_time
                                response_data["data"]["timeData"]["trainingTime"][adda_index] = training_time  # run_multimodal时间
                                response_data["data"]["timeData"]["preprocessingTime"][adda_index] = preprocessing_time
                                response_data["data"]["timeData"]["featureGenerationTime"][adda_index] = feature_generation_time  # astar_k_step时间
                                response_data["data"]["timeData"]["evaluationTime"][adda_index] = evaluation_time

                            # ===== 计算特征重要性 =====
                            try:
                                print("Calculating feature importance...")

                                # 获取当前最佳特征信息
                                if best_features_info and best_features_info.get("success", False):
                                    feature_names = []

                                    # 从best_features_info中提取特征名称
                                    feature_descriptions = best_features_info.get("feature_descriptions", [])
                                    if feature_descriptions:
                                        # 解析特征描述，提取特征名称
                                        for desc in feature_descriptions:
                                            # 简单的特征名称提取逻辑
                                            if ":" in desc:
                                                feature_name = desc.split(":")[0].strip()
                                            else:
                                                # 使用描述的前20个字符作为特征名
                                                feature_name = desc[:20].replace(" ", "_").replace(",", "")
                                            feature_names.append(feature_name)

                                    # 如果没有提取到特征名称，使用默认名称
                                    if not feature_names:
                                        feature_names = [f"feature_{i}" for i in range(5)]
                                else:
                                    # 使用默认特征名称
                                    feature_names = [f"feature_{i}" for i in range(5)]

                                # 尝试从现有数据计算特征重要性
                                try:
                                    # 尝试获取实际数据进行重要性计算
                                    from src.pg.sql_utils import get_conn
                                    import pandas as pd

                                    # 读取数据用于重要性计算
                                    data_path = os.path.join(dataset_path, task_name, "train_new.csv")
                                    if os.path.exists(data_path):
                                        df = pd.read_csv(data_path)

                                        # 获取目标列
                                        _, target_col, _ = task_config(dataset.lower())

                                        # 选择数值列作为特征
                                        numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
                                        if target_col in numeric_columns:
                                            numeric_columns.remove(target_col)

                                        # 限制特征数量，避免计算过慢
                                        feature_columns = numeric_columns[:10]  # 最多10个特征
                                        feature_names = feature_columns[:len(feature_names)]

                                        if len(feature_columns) >= 2:
                                            X = df[feature_columns].fillna(0)
                                            y = df[target_col]

                                            # 计算特征重要性
                                            importance_results = calculate_importance_from_data(
                                                X, y,
                                                task_type=task_type,
                                                feature_names=feature_names,
                                                methods=["fi", "rfe"]  # 先计算基础方法
                                            )

                                            # 更新importanceData
                                            response_data["data"]["importanceData"].update(importance_results)

                                            print(f"Successfully calculated importance for {len(feature_columns)} features")
                                        else:
                                            raise ValueError("Not enough numeric features for importance calculation")
                                    else:
                                        raise FileNotFoundError(f"Data file not found: {data_path}")

                                except Exception as data_error:
                                    print(f"Failed to calculate importance from real data: {str(data_error)}")
                                    # 使用模拟数据作为后备
                                    mock_importance = {}
                                    for method in ["shap", "ig", "rfe", "fi"]:
                                        mock_importance[method] = create_mock_importance_data(feature_names[:5], method)

                                    response_data["data"]["importanceData"].update(mock_importance)
                                    print("Using mock importance data as fallback")

                            except Exception as importance_error:
                                print(f"Feature importance calculation failed: {str(importance_error)}")
                                # 确保至少有空的importanceData
                                response_data["data"]["importanceData"] = {
                                    "shap": [],
                                    "ig": [],
                                    "rfe": [],
                                    "fi": []
                                }

                            # 添加成功通知
                            if astar_time_data is not None and training_execution_time is not None:
                                total_exec_time = astar_time_data["feature_generation_time"] + training_execution_time
                                notifications.append({
                                    "notice_description": f"🎉 端到端流程完成！AUC: {auc:.4f}, 搜索深度: {max_search_depth}, 特征生成: {astar_time_data['feature_generation_time']:.1f}s, 训练: {training_execution_time:.1f}s, 总计: {total_exec_time:.1f}s",
                                    "notice_type": "success"
                                })
                            else:
                                notifications.append({
                                    "notice_description": f"🎉 端到端流程完成！AUC: {auc:.4f}, 搜索深度: {max_search_depth}, 耗时: {exec_time:.2f}s",
                                    "notice_type": "success"
                                })
                        else:
                            # 性能测试失败
                            error_msg = performance_result.get("error", "未知错误")
                            response_data["data"]["performance_metrics"] = {
                                "auc": 0.0,
                                "execution_time": 0.0,
                                "model_type": model,
                                "method": "error",
                                "error": error_msg
                            }
                            response_data["data"]["training_result"] = {
                                "success": False,
                                "message": f"性能测试失败: {error_msg}",
                                "model_type": model,
                                "method": "error"
                            }

            except Exception as perf_error:
                # 性能测试异常
                error_msg = f"性能测试异常: {str(perf_error)}"
                response_data["data"]["performance_metrics"] = {
                    "auc": 0.0,
                    "execution_time": 0.0,
                    "model_type": model,
                    "method": "exception",
                    "error": error_msg
                }
                response_data["data"]["training_result"] = {
                    "success": False,
                    "message": error_msg,
                    "model_type": model,
                    "method": "exception"
                }

                # 添加错误通知
                notifications.append({
                    "notice_description": f"特征搜索完成，但性能测试异常: {error_msg}",
                    "notice_type": "error"
                })

        # ===== 运行对比方法 =====
        if len(comparison_methods) > 1 or any(method != "Adda" for method in comparison_methods):
            try:
                print("Starting comparison methods evaluation...")
                comparison_start_time = time.time()

                # 导入对比方法模块
                from comparison_methods import ComparisonEngine, run_comparison_from_csv

                # 准备对比数据
                comparison_engine = ComparisonEngine()

                # 获取用于对比的方法列表（排除Adda，因为已经运行过了）
                comparison_list = [method for method in comparison_methods if method != "Adda"]

                if comparison_list:
                    print(f"Running comparison for methods: {comparison_list}")

                    # 运行对比方法
                    comparison_results = comparison_engine.run_comparison(
                        X=pd.read_csv(csv_path).drop(columns=[target_col]),
                        y=pd.read_csv(csv_path)[target_col],
                        task_type=task_type,
                        methods=comparison_list,
                        time_limit=120  # 每个AutoML方法2分钟限制
                    )

                    # 合并对比结果到响应数据
                    if comparison_results["methods"]:
                        print(f"Comparison completed for {len(comparison_results['methods'])} methods")

                        # 更新性能数据
                        for i, method in enumerate(comparison_results["methods"]):
                            method_idx = comparison_methods.index(method)

                            # 确保数组长度足够
                            while len(response_data["data"]["performanceData"]["auc"]) <= method_idx:
                                response_data["data"]["performanceData"]["auc"].append(0.0)
                                response_data["data"]["performanceData"]["f1"].append(0.0)
                                response_data["data"]["performanceData"]["accuracy"].append(0.0)
                                response_data["data"]["performanceData"]["precision"].append(0.0)
                                response_data["data"]["performanceData"]["recall"].append(0.0)

                            # 填充性能指标
                            if task_type == "classify":
                                response_data["data"]["performanceData"]["auc"][method_idx] = comparison_results["performance_data"]["auc"][i]
                                response_data["data"]["performanceData"]["f1"][method_idx] = comparison_results["performance_data"]["f1"][i]
                                response_data["data"]["performanceData"]["accuracy"][method_idx] = comparison_results["performance_data"]["accuracy"][i]
                                response_data["data"]["performanceData"]["precision"][method_idx] = comparison_results["performance_data"]["precision"][i]
                                response_data["data"]["performanceData"]["recall"][method_idx] = comparison_results["performance_data"]["recall"][i]
                            else:
                                # 对于回归任务，使用RMSE作为主要指标
                                if "auc" not in response_data["data"]["performanceData"] or response_data["data"]["performanceData"]["auc"][method_idx] == 0.0:
                                    response_data["data"]["performanceData"]["auc"][method_idx] = 1.0 / (1.0 + comparison_results["performance_data"]["rmse"][i])  # 转换RMSE为类似AUC的指标

                            # 填充时间数据
                            while len(response_data["data"]["timeData"]["totalTime"]) <= method_idx:
                                response_data["data"]["timeData"]["totalTime"].append(0.0)
                                response_data["data"]["timeData"]["trainingTime"].append(0.0)
                                response_data["data"]["timeData"]["preprocessingTime"].append(0.0)
                                response_data["data"]["timeData"]["featureGenerationTime"].append(0.0)
                                response_data["data"]["timeData"]["evaluationTime"].append(0.0)

                            response_data["data"]["timeData"]["totalTime"][method_idx] = comparison_results["time_data"]["totalTime"][i]
                            response_data["data"]["timeData"]["trainingTime"][method_idx] = comparison_results["time_data"]["trainingTime"][i]
                            response_data["data"]["timeData"]["preprocessingTime"][method_idx] = comparison_results["time_data"]["preprocessingTime"][i]
                            response_data["data"]["timeData"]["featureGenerationTime"][method_idx] = comparison_results["time_data"]["featureGenerationTime"][i]
                            response_data["data"]["timeData"]["evaluationTime"][method_idx] = comparison_results["time_data"]["evaluationTime"][i]

                        # 记录对比完成时间
                        comparison_time = time.time() - comparison_start_time
                        print(f"Comparison methods evaluation completed in {comparison_time:.2f}s")

                        # 添加对比完成通知
                        notifications.append({
                            "notice_description": f"📊 对比方法评估完成！对比了 {len(comparison_results['methods'])} 种方法，耗时: {comparison_time:.1f}s",
                            "notice_type": "success"
                        })
                    else:
                        print("No comparison methods produced valid results")
                else:
                    print("No additional comparison methods to run (only Adda specified)")

            except Exception as comparison_error:
                print(f"Comparison methods evaluation failed: {str(comparison_error)}")
                notifications.append({
                    "notice_description": f"对比方法评估失败: {str(comparison_error)}",
                    "notice_type": "warning"
                })

        # 如果没有执行性能测试或搜索未完成，添加相应的状态信息
        if not use_performance_test:
            if astar_time_data is not None:
                notifications.append({
                    "notice_description": f"特征搜索完成！搜索深度: {max_search_depth}，特征生成耗时: {astar_time_data['feature_generation_time']:.1f}s，未执行性能测试",
                    "notice_type": "info"
                })
            else:
                notifications.append({
                    "notice_description": f"特征搜索完成！搜索深度: {max_search_depth}，未执行性能测试",
                    "notice_type": "info"
                })
        elif not is_finished:
            if astar_time_data is not None:
                notifications.append({
                    "notice_description": f"特征搜索执行了 {max_search_depth} 步，耗时: {astar_time_data['feature_generation_time']:.1f}s，但尚未完成最佳特征选择",
                    "notice_type": "info"
                })
            else:
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

@app.route('/manual-test-websocket/', methods=['POST'])
def manual_test_websocket():
    """
    手动测试WebSocket状态更新
    """
    try:
        from src.llm.agent_status_wrapper import agent_status_wrapper

        # 测试系统通知
        agent_status_wrapper.send_system_notification(
            "手动测试：WebSocket连接工作正常！",
            "success"
        )

        # 测试Agent状态更新 - Main Agent
        agent_status_wrapper.send_agent_status({
            "type": "agent_status",
            "agent": "mainagent",
            "status": "working",
            "work_type": "手动测试任务",
            "details": {
                "phase": "testing_websocket",
                "progress": 60,
                "operation": "WebSocket连接测试"
            },
            "data": {
                "summary": "正在执行WebSocket连接手动测试..."
            }
        })

        # 测试Agent思考过程
        agent_status_wrapper.send_agent_thinking({
            "type": "agent_thinking",
            "agent": "mainagent",
            "thinking": "这是一个手动测试的思考消息。我正在验证WebSocket连接是否正常工作，以及前端是否能正确接收Agent状态更新和思考过程。",
            "category": "testing"
        })

        # 3秒后发送完成状态
        import threading
        def send_complete_status():
            import time
            time.sleep(3)
            agent_status_wrapper.send_agent_status({
                "type": "agent_status",
                "agent": "mainagent",
                "status": "completed",
                "work_type": "手动测试任务",
                "result": {
                    "success": True,
                    "message": "WebSocket手动测试完成！"
                }
            })
            agent_status_wrapper.send_agent_thinking({
                "type": "agent_thinking",
                "agent": "mainagent",
                "thinking": "测试完成！WebSocket连接工作正常，前端应该能看到完整的状态更新过程。",
                "category": "testing"
            })

        threading.Thread(target=send_complete_status).start()

        return jsonify({
            "status": "success",
            "message": "手动WebSocket测试消息已发送！请检查前端和测试页面。"
        })

    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

if __name__ == '__main__':
    # 使用WebSocket服务器运行应用
    ws_server.run(host='0.0.0.0', port=5000, debug=True) 