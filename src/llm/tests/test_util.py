import os
import sys

# 获取项目根目录并添加到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入所需的库和模块
# from src.llm.llm_dag_util import *  # 导入LLM DAG工具
# from src.llm.agents.autogen_code_generator import *  # 导入AutoGen代码生成器

# from src.llm.llm_dag_util_autogen import *  # 导入LLM DAG工具 # 更改此项选择DAG节点生成是否使用AutoGen
from src.llm.llm_dag_util import *
# from src.llm.llm_dag_util_planner import *
# from src.llm.llm_dag_util_gp import *
# from src.llm.llm_dag_util_gp_dys import *
# from src.llm.llm_dag_util_resample import *  # 导入重采样版本

from src.pg.func_utils import *     # 导入PostgreSQL功能工具
import sys
import pickle
# 导入各种机器学习模型
# from sklearn.linear_model import LogisticRegression
# from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
# from sklearn.neighbors import KNeighborsClassifier
# from sklearn.tree import DecisionTreeClassifier, plot_tree
# from sklearn.naive_bayes import GaussianNB
# from sklearn.svm import SVC
# from xgboost import XGBClassifier
# from lightgbm import LGBMClassifier
# from sklearn.ensemble import RandomForestClassifier
from src.env import *                # 导入环境变量
from src.llm.utils.common_utils import *  # 导入通用工具
import argparse                      # 用于解析命令行参数


def task_config(task_name:str):
    """
    从YAML配置文件获取任务配置信息
    参数:
        task_name: 任务名称
    返回:
        task_name: 任务名称
        target_col: 目标列名
        task_type: 任务类型(分类或回归)
    """
    with open(os.path.join(proj_path, "src", "llm", "tests", "config.yaml"), "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config['task_config'][task_name]['task_name'], config['task_config'][task_name]['target_col'], config['task_config'][task_name]['task_type']

def method_config(method_config:str):
    """
    从YAML配置文件获取方法配置信息
    参数:
        method_config: 方法配置名称
    返回:
        need_preprocess: 是否需要预处理的布尔值
    """
    with open(os.path.join(proj_path, "src", "llm", "tests", "config.yaml"), "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config['method_config'][method_config]['need_preprocess']


class TestDir():
    """
    测试目录类，用于测试Adda系统的特征工程功能
    """
    def __init__(self, dir_name:str, task_type:str, target_col:str, model_type:str="CART"):
        """
        初始化测试目录
        参数:
            dir_name: 目录名(通常是数据集名称)
            task_type: 任务类型(分类或回归)
            target_col: 目标列名
            model_type: 评估模型类型，默认为CART
        """
        self.dir_name = dir_name
        self.task_type = task_type
        self.target_col = target_col
        self.model_type = model_type
    
    def test_astar_step(self, step_num, force_new:bool, high_order_num:int = 0, postfix:str = "", token_limit:int = 128000):
        """
        测试Adda的A*搜索特征生成步骤
        参数:
            step_num: 执行的步骤数
            force_new: 是否强制创建新模型(不恢复之前的状态)
            high_order_num: 高阶特征数量
            postfix: 保存路径的后缀
            token_limit: LLM的token限制
        返回:
            ctor: LLMDagConstructor实例
        """
        # 读取数据信息(获取数据特征描述、任务描述和CSV路径)
        data_agenda, desc, csv_path = read_data_info(self.dir_name)
        unfinished = False
        
        states_path = os.path.join(proj_path, "src", "cur_states.pkl")
        task_path = os.path.join(test_save_path, self.dir_name)
        if os.path.exists(states_path) and not force_new:
            # 如果有未完成的模型且不强制创建新模型，则加载之前的状态
            print("reload the unfinished model")
            ctor = pickle.load(open(states_path, "rb"))
            unfinished = True
        else: 
            # 否则清空目录内容并创建新的LLMDagConstructor
            os.system(f"rm -rf {task_path}")
            ctor = LLMDagConstructor(self.task_type, beam_limit=1, eval_model_type=self.model_type, do_feature_selection=False, high_order_num=high_order_num, token_limit=token_limit)
        
        # 执行A*搜索特征生成步骤
        ctor.astar_k_step(step_num, data_agenda = data_agenda, data_desc=desc, target_col=self.target_col, tb_name=f"{self.dir_name}_src_tb_train", task_name = self.dir_name, do_unfinished=unfinished)
        
        # 输出最佳代码
        print(ctor.get_best_code())
        # 保存当前状态
        with open(os.path.join(task_path, "cur_states.pkl"), "wb") as f:
            pickle.dump(ctor, f)
            
        # 复制目录并添加后缀，然后删除原目录
        os.system(f"cp -r {task_path} {task_path}_{postfix}")
        os.system(f"rm -rf {task_path}")

        return ctor
    
if __name__ == "__main__": 
    
    # 解析命令行参数
    args = argparse.ArgumentParser()
    args.add_argument('--task_name', type = str, default = "heart")   # 默认任务名为heart
    args.add_argument('--model_type', type = str, default = "RF")     # 默认模型类型为随机森林
    args.add_argument('--iter_num', type=int, default=10)            # 默认迭代次数为10
    args.add_argument('--complex_num', type=int, default=5)          # 默认复杂度为5
    args = args.parse_args()
    assert args.task_name != ""
    
    # 获取任务配置
    task_name, target_col, task_type = task_config(args.task_name)

    # 导入数据表并分割为训练集和测试集
    importTable_with_split(os.path.join(dataset_path, task_name, "train_new.csv"), f"{task_name}_src_tb", target_col, get_conn(), False, task_type)
    t_map = {}
    
    # 创建测试任务实例
    cur_task = TestDir(task_name, task_type, target_col, args.model_type)

    # 记录开始时间
    startt = time.time()
    # 执行A*搜索特征生成
    cur_task.test_astar_step(args.iter_num, True, args.complex_num, f"{args.model_type}_Full")
    # 记录结束时间
    endt = time.time()

    # 计算执行时间
    t_map[args.model_type] = endt - startt
            
    # 输出执行时间
    print(f"Current time map of Adda execution is ", t_map)