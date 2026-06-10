# frontend/train_node_model.py
"""
基于run_multimodel_type.py逻辑的单节点in-DB ML训练模块
完全复用原有的SQL生成和数据库训练流程
"""

import os
import sys
import warnings
import termcolor
import pickle
import pandas as pd

# 获取项目根目录并添加到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.llm.llm_dag_util import *
from src.pg.sql_utils import *
from src.pg.import_table import *
from src.pg.python_polish import *
from src.pg.func_utils import *
from src.llm.tests.test_util import *
from src.env import *
from multi_node_combiner import MultiNodeFeatureCombiner


class NodeModelTrainer:
    """单节点和多节点in-DB ML训练器"""

    def __init__(self):
        self.conn = None
        self.cursor = None

    def _get_database_connection(self):
        """获取数据库连接"""
        if not self.conn:
            self.conn = get_conn()
            self.cursor = self.conn.cursor()
        return self.conn, self.cursor

    def _validate_node_exists(self, node_id, llm_dag_constructor):
        """验证节点是否存在"""
        if not llm_dag_constructor:
            return False, "任务未初始化"

        # 检查节点是否存在于DAG中 - 修复：使用正确的DAG结构
        try:
            # 通过DAG查找节点
            for node in llm_dag_constructor.dag.nodes():
                if hasattr(node, 'node_id') and str(node.node_id) == str(node_id):
                    return True, ""

            # 如果没找到，返回错误
            return False, f"节点ID {node_id} 不存在"
        except Exception as e:
            return False, f"DAG构造器状态异常: {str(e)}"

    def _setup_task_config(self, task_name, model_type, custom_dataset_path=None):
        """设置任务配置"""
        try:
            # 获取任务配置
            if task_name:
                actual_task_name, target_col, task_type = task_config(task_name)
            else:
                # 如果没有指定task_name，使用默认配置
                actual_task_name = "heart"  # 默认数据集
                target_col = "tenyearchd"   # 默认目标列
                task_type = "classify"      # 默认任务类型

            # 构建数据集路径（与run_multimodel_type.py保持一致）
            # 如果指定了custom_dataset_path，使用它；否则根据task_name构建标准路径
            if custom_dataset_path:
                csvpath = custom_dataset_path
            else:
                # 使用标准的dataset/task/路径结构
                csvpath = os.path.join(dataset_path, actual_task_name, "train_new.csv")

            # 检查数据文件是否存在
            if not os.path.exists(csvpath):
                return False, f"数据文件不存在: {csvpath}，请确认数据集 '{actual_task_name}' 已准备"

            return True, {
                "task_name": actual_task_name,
                "target_col": target_col,
                "task_type": task_type,
                "csvpath": csvpath,
                "model_type": model_type
            }
        except Exception as e:
            return False, f"任务配置失败: {str(e)}"

    def _prepare_pipeline_for_node(self, llm_dag_constructor, node_id, task_name):
        """为指定节点准备pipeline"""
        try:
            # 尝试加载pickle文件中的pipeline constructor（与run_multimodel_type.py保持一致）
            last_pipector_path = os.path.join(test_save_path, task_name, "cur_states.pkl")

            if os.path.exists(last_pipector_path):
                with open(last_pipector_path, "rb") as f:
                    pipeCtor = pickle.load(f)
                return True, pipeCtor
            else:
                # 如果没有pickle文件，尝试从DAG构造器获取pipeline信息
                if hasattr(llm_dag_constructor, 'pipes') and llm_dag_constructor.pipes:
                    # 创建一个模拟的pipeCtor对象
                    pipeCtor = type('MockPipeCtor', (), {
                        'tb_name': None,  # 将在后面设置
                        'pipes': llm_dag_constructor.pipes
                    })()
                    return True, pipeCtor
                else:
                    return False, "未找到有效的特征转换步骤。请先点击'Next Step'按钮生成特征节点，然后选择生成的特征节点（非根节点）进行测试。根节点仅包含原始数据，无法直接用于模型训练。"
        except Exception as e:
            return False, f"准备pipeline失败: {str(e)}"

    def train_on_single_node(self, node_id, llm_dag_constructor, task_name=None, model_type="RF", dataset_path=None):
        """
        在单个节点上训练in-DB ML模型
        完全复用run_multimodel_type.py的逻辑
        """
        warnings.filterwarnings("ignore")

        try:
            # 1. 验证输入参数
            success, msg = self._validate_node_exists(node_id, llm_dag_constructor)
            if not success:
                return False, msg, None

            # 2. 设置任务配置
            success, config = self._setup_task_config(task_name, model_type, dataset_path)
            if not success:
                return False, config, None

            actual_task_name = config["task_name"]
            target_col = config["target_col"]
            task_type = config["task_type"]
            csvpath = config["csvpath"]

            # 3. 准备pipeline
            success, pipeCtor = self._prepare_pipeline_for_node(llm_dag_constructor, node_id, actual_task_name)
            if not success:
                return False, pipeCtor, None

            pipes = pipeCtor.pipes

            # 4. 设置数据库连接和数据
            conn, cursor = self._get_database_connection()

            # 读取数据并设置表名
            df = pd.read_csv(csvpath)
            db_tb_name = f"{actual_task_name}_src_tb"
            row_num, col_num = df.shape[0] - int(df.shape[0]/5), df.shape[1]

            # 设置目录路径
            dir_path = os.path.join(test_save_path, actual_task_name)
            postfix = f"_{model_type}_Full"

            # 重命名目录（复制run_multimodel_type.py的逻辑）
            origin_name = os.path.join(test_save_path, f"{actual_task_name}{postfix}")
            exec_name = os.path.join(test_save_path, actual_task_name)

            # 确保目录存在
            if os.path.exists(origin_name):
                os.rename(origin_name, exec_name)

            # 创建Python代码目录
            pycodepath = os.path.join(test_save_path, actual_task_name, "pycodes")
            os.makedirs(pycodepath, exist_ok=True)

            # 5. 设置pipeCtor的表名
            pipeCtor.tb_name = db_tb_name

            # 6. 创建PythonPolisher并执行SQL生成（完全复制run_multimodel_type.py逻辑）
            polisher = PythonPolisher(
                db_tb_name, target_col, "df", pipes, dir_path, 2, col_num, pipeCtor,
                id_col='id', total_num=row_num, do_optimize=2, task_type=task_type,
                use_py_train_pred=True, model_type=model_type
            )

            # 执行代码优化
            polisher.polish_code()

            # 7. 创建model_table并清理旧模型（复制run_multimodel_type.py逻辑）
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS model_table (
                tb_name TEXT,
                model_type TEXT,
                path TEXT UNIQUE,
                version SERIAL,
                PRIMARY KEY (tb_name, model_type, version)
            );
            """
            cursor.execute(create_table_sql)

            # 清理旧模型
            cursor.execute(f"""
                DELETE FROM model_table
                WHERE tb_name = '{db_tb_name}'
                AND model_type = '{model_type}'
            """)
            os.system(f"rm -f {model_store_path}/{db_tb_name}_{model_type}_*.pkl")
            conn.commit()

            # 8. 生成SQL并执行训练（核心步骤）
            scores, auc_answer, final_auc = polisher.generate_sql()
            speed_record = polisher.speed_record

            # 9. 读取生成的SQL文件
            sql_code = self._read_generated_sql_files(dir_path, 0)  # 第一个pipeline

            # 10. 恢复目录名称
            if os.path.exists(exec_name):
                os.rename(exec_name, origin_name)

            # 11. 准备返回结果
            performance_metrics = {
                "auc": auc_answer,
                "execution_time": speed_record.get("sql", [0])[0] if speed_record else 0,
                "model_type": model_type,
                "task_name": actual_task_name,
                "node_id": node_id,
                "sql_code": sql_code
            }

            result_info = {
                "model_table": db_tb_name,
                "target_column": target_col,
                "task_type": task_type,
                "sql_files_generated": True,
                "sql_code": sql_code,
                "sql_file_paths": self._get_sql_file_paths(dir_path, 0)
            }

            print(termcolor.colored(f"Node {node_id} training completed. Final AUC: {auc_answer}", "yellow"))

            return True, result_info, performance_metrics

        except Exception as e:
            # 确保在出错时恢复目录名称
            try:
                if 'exec_name' in locals() and 'origin_name' in locals():
                    if os.path.exists(exec_name):
                        os.rename(exec_name, origin_name)
            except:
                pass

            error_msg = f"节点 {node_id} 训练失败: {str(e)}"
            print(termcolor.colored(error_msg, "red"))
            return False, error_msg, None

        finally:
            # 确保关闭数据库连接
            if self.conn:
                self.conn.close()
                self.conn = None
                self.cursor = None

    def _validate_multiple_nodes(self, selected_node_ids, llm_dag_constructor):
        """验证多个节点是否存在"""
        if not llm_dag_constructor:
            return False, "任务未初始化"

        if not selected_node_ids:
            return False, "没有选择任何节点"

        # 检查所有节点是否存在于DAG中 - 修复：使用正确的DAG结构
        try:
            existing_node_ids = set()
            for node in llm_dag_constructor.dag.nodes():
                if hasattr(node, 'node_id'):
                    existing_node_ids.add(str(node.node_id))

            invalid_nodes = [nid for nid in selected_node_ids if str(nid) not in existing_node_ids]
            if invalid_nodes:
                return False, f"节点ID {invalid_nodes} 不存在"
        except Exception as e:
            return False, f"DAG构造器状态异常: {str(e)}"

        return True, ""

    def train_on_multiple_nodes(self, selected_node_ids, llm_dag_constructor, task_name=None, model_type="RF", dataset_path=None):
        """
        在多个选择的节点上训练in-DB ML模型
        使用MultiNodeFeatureCombiner组合多个节点的特征
        """
        warnings.filterwarnings("ignore")

        try:
            # 1. 验证输入参数
            success, msg = self._validate_multiple_nodes(selected_node_ids, llm_dag_constructor)
            if not success:
                return False, msg, None

            # 2. 设置任务配置
            success, config = self._setup_task_config(task_name, model_type, dataset_path)
            if not success:
                return False, config, None

            actual_task_name = config["task_name"]
            target_col = config["target_col"]
            task_type = config["task_type"]
            csvpath = config["csvpath"]

            # 3. 使用MultiNodeFeatureCombiner组合特征
            db_tb_name = f"{actual_task_name}_src_tb"
            combiner = MultiNodeFeatureCombiner(llm_dag_constructor, db_tb_name, target_col)

            # 组合多个节点的特征代码
            success, error_msg, combined_code = combiner.combine_feature_codes(selected_node_ids)
            if not success:
                return False, f"特征组合失败: {error_msg}", None

            # 4. 准备pipeline（为多节点场景创建自定义pipeline）
            success, pipeCtor = self._prepare_pipeline_for_multiple_nodes(combined_code, actual_task_name)
            if not success:
                return False, pipeCtor, None

            pipes = pipeCtor.pipes

            # 5. 设置数据库连接和数据
            conn, cursor = self._get_database_connection()

            # 读取数据并设置表名
            df = pd.read_csv(csvpath)
            row_num, col_num = df.shape[0] - int(df.shape[0]/5), df.shape[1]

            # 设置目录路径
            dir_path = os.path.join(test_save_path, actual_task_name)
            postfix = f"_{model_type}_Multi_Node_Full"

            # 重命名目录（为多节点训练创建唯一标识）
            origin_name = os.path.join(test_save_path, f"{actual_task_name}{postfix}")
            exec_name = os.path.join(test_save_path, actual_task_name)

            # 确保目录存在
            if os.path.exists(origin_name):
                os.rename(origin_name, exec_name)

            # 创建Python代码目录
            pycodepath = os.path.join(test_save_path, actual_task_name, "pycodes")
            os.makedirs(pycodepath, exist_ok=True)

            # 6. 保存组合后的特征代码
            combined_code_file = os.path.join(pycodepath, f"combined_features_nodes_{'_'.join(map(str, selected_node_ids))}.py")
            with open(combined_code_file, 'w') as f:
                f.write(combined_code)

            # 7. 设置pipeCtor的表名
            pipeCtor.tb_name = db_tb_name

            # 8. 创建PythonPolisher并执行SQL生成
            polisher = PythonPolisher(
                db_tb_name, target_col, "df", pipes, dir_path, 2, col_num, pipeCtor,
                id_col='id', total_num=row_num, do_optimize=2, task_type=task_type,
                use_py_train_pred=True, model_type=model_type
            )

            # 执行代码优化
            polisher.polish_code()

            # 9. 创建model_table并清理旧模型
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS model_table (
                tb_name TEXT,
                model_type TEXT,
                path TEXT UNIQUE,
                version SERIAL,
                PRIMARY KEY (tb_name, model_type, version)
            );
            """
            cursor.execute(create_table_sql)

            # 为多节点组合创建唯一的模型标识
            model_identifier = f"{db_tb_name}_multi_nodes_{'_'.join(map(str, selected_node_ids))}"

            # 清理旧模型
            cursor.execute(f"""
                DELETE FROM model_table
                WHERE tb_name = '{model_identifier}'
                AND model_type = '{model_type}'
            """)
            os.system(f"rm -f {model_store_path}/{model_identifier}_{model_type}_*.pkl")
            conn.commit()

            # 10. 生成SQL并执行训练
            scores, auc_answer, final_auc = polisher.generate_sql()
            speed_record = polisher.speed_record

            # 11. 读取生成的SQL文件
            sql_code = self._read_generated_sql_files(dir_path, 0)  # 第一个pipeline

            # 12. 恢复目录名称
            if os.path.exists(exec_name):
                os.rename(exec_name, origin_name)

            # 13. 准备返回结果
            performance_metrics = {
                "auc": auc_answer,
                "execution_time": speed_record.get("sql", [0])[0] if speed_record else 0,
                "model_type": model_type,
                "task_name": actual_task_name,
                "selected_node_ids": selected_node_ids,
                "feature_combination": True,
                "sql_code": sql_code
            }

            result_info = {
                "model_table": model_identifier,
                "target_column": target_col,
                "task_type": task_type,
                "sql_files_generated": True,
                "combined_features_code": combined_code_file,
                "node_count": len(selected_node_ids),
                "sql_code": sql_code,
                "sql_file_paths": self._get_sql_file_paths(dir_path, 0)
            }

            # 获取特征组合信息
            feature_info = combiner.get_combined_feature_info(selected_node_ids)
            result_info["feature_info"] = feature_info

            print(termcolor.colored(f"Multi-node training completed. Nodes: {selected_node_ids}. Final AUC: {auc_answer}", "yellow"))

            return True, result_info, performance_metrics

        except Exception as e:
            # 确保在出错时恢复目录名称
            try:
                if 'exec_name' in locals() and 'origin_name' in locals():
                    if os.path.exists(exec_name):
                        os.rename(exec_name, origin_name)
            except:
                pass

            error_msg = f"多节点训练失败: {str(e)}"
            print(termcolor.colored(error_msg, "red"))
            return False, error_msg, None

        finally:
            # 清理临时文件（多节点训练）
            if 'pipeCtor' in locals() and hasattr(pipeCtor, 'temp_dir'):
                try:
                    import shutil
                    shutil.rmtree(pipeCtor.temp_dir, ignore_errors=True)
                except Exception as cleanup_error:
                    print(f"Warning: Failed to cleanup temp directory {pipeCtor.temp_dir}: {cleanup_error}")

            # 确保关闭数据库连接
            if self.conn:
                self.conn.close()
                self.conn = None
                self.cursor = None

    def _prepare_pipeline_for_multiple_nodes(self, combined_code, task_name):
        """为多节点组合准备pipeline"""
        try:
            # 导入PIPE类
            from src.llm.utils.common_utils import PIPE

            # 为多节点组合创建临时目录和文件
            import tempfile
            import uuid

            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix=f"multi_node_{task_name}_")

            # 生成唯一的文件名
            unique_id = str(uuid.uuid4())[:8]
            code_filename = f"multi_node_features_{unique_id}.py"
            code_file_path = os.path.join(temp_dir, code_filename)

            # 将组合代码保存到文件中
            with open(code_file_path, 'w') as f:
                f.write(combined_code)

            # 创建一个模拟的PIPE对象
            multi_node_pipe = PIPE()
            multi_node_pipe.code_path = code_file_path  # 设置为文件路径，而不是代码内容
            multi_node_pipe.pipe_id = 0  # 设置一个默认的pipe ID

            # 创建一个模拟的pipeCtor对象，用于多节点特征组合
            pipeCtor = type('MultiNodePipeCtor', (), {
                'tb_name': None,  # 将在后面设置
                'pipes': [multi_node_pipe],  # 使用正确的PIPE对象
                'is_multi_node': True,
                'temp_dir': temp_dir  # 保存临时目录路径，用于后续清理
            })()

            return True, pipeCtor

        except Exception as e:
            return False, f"准备多节点pipeline失败: {str(e)}"

    def _read_generated_sql_files(self, dir_path: str, pipe_idx: int) -> dict:
        """
        读取生成的SQL文件内容

        Args:
            dir_path: SQL文件所在目录
            pipe_idx: pipeline索引

        Returns:
            包含各种SQL代码的字典
        """
        sql_code = {
            "training_sql": "",
            "prediction_sql": "",
            "udf_sql": "",
            "all_sql": ""
        }

        try:
            # 训练SQL文件
            train_sql_path = os.path.join(dir_path, f"pipe_train_{pipe_idx}", "spsql.sql")
            if os.path.exists(train_sql_path):
                with open(train_sql_path, 'r', encoding='utf-8') as f:
                    sql_code["training_sql"] = f.read()

            # 预测SQL文件
            predict_sql_path = os.path.join(dir_path, f"pipe_predict_{pipe_idx}", "spsql.sql")
            if os.path.exists(predict_sql_path):
                with open(predict_sql_path, 'r', encoding='utf-8') as f:
                    sql_code["prediction_sql"] = f.read()

            # UDF SQL文件
            udf_sql_path = os.path.join(dir_path, f"pipe_train_{pipe_idx}", "spudf.sql")
            if os.path.exists(udf_sql_path):
                with open(udf_sql_path, 'r', encoding='utf-8') as f:
                    sql_code["udf_sql"] = f.read()

            # 组合所有SQL
            sql_code["all_sql"] = (
                "-- UDF Functions --\n" + sql_code["udf_sql"] + "\n\n" +
                "-- Training SQL --\n" + sql_code["training_sql"] + "\n\n" +
                "-- Prediction SQL --\n" + sql_code["prediction_sql"]
            )

        except Exception as e:
            print(f"Warning: Failed to read SQL files: {e}")

        return sql_code

    def _get_sql_file_paths(self, dir_path: str, pipe_idx: int) -> dict:
        """
        获取生成的SQL文件路径

        Args:
            dir_path: SQL文件所在目录
            pipe_idx: pipeline索引

        Returns:
            包含各种SQL文件路径的字典
        """
        file_paths = {
            "training_sql_path": "",
            "prediction_sql_path": "",
            "udf_sql_path": ""
        }

        try:
            file_paths["training_sql_path"] = os.path.join(dir_path, f"pipe_train_{pipe_idx}", "spsql.sql")
            file_paths["prediction_sql_path"] = os.path.join(dir_path, f"pipe_predict_{pipe_idx}", "spsql.sql")
            file_paths["udf_sql_path"] = os.path.join(dir_path, f"pipe_train_{pipe_idx}", "spudf.sql")
        except Exception as e:
            print(f"Warning: Failed to get SQL file paths: {e}")

        return file_paths