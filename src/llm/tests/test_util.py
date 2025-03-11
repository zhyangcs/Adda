import os
import sys

# 获取项目根目录并添加到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.llm.llm_dag_util import *
from src.pg.func_utils import *
import sys
import pickle
from sklearn.linear_model import LogisticRegression
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier, plot_tree
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from src.env import *
from src.llm.utils.common_utils import *
import argparse


def task_config(task_name:str):
    """
    get task config from the yaml file
    """
    with open(os.path.join(proj_path, "src", "llm", "tests", "config.yaml"), "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config['task_config'][task_name]['task_name'], config['task_config'][task_name]['target_col'], config['task_config'][task_name]['task_type']

def method_config(method_config:str):
    """
    get method config from the yaml file
    """
    with open(os.path.join(proj_path, "src", "llm", "tests", "config.yaml"), "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config['method_config'][method_config]['need_preprocess']


class TestDir():
    def __init__(self, dir_name:str, task_type:str, target_col:str, model_type:str="CART"):
        self.dir_name = dir_name
        self.task_type = task_type
        self.target_col = target_col
        self.model_type = model_type
    
    def test_astar_step(self, step_num, force_new:bool, high_order_num:int = 0, postfix:str = "", token_limit:int = 128000):
        # setting the logging file : projpath/test/sh/store/{self.dir_name}/log.txt
        data_agenda, desc, csv_path = read_data_info(self.dir_name)
        unfinished = False
        
        states_path = os.path.join(proj_path, "src", "cur_states.pkl")
        task_path = os.path.join(test_save_path, self.dir_name)
        if os.path.exists(states_path) and not force_new:
            print("reload the unfinished model")
            ctor = pickle.load(open(states_path, "rb"))
            unfinished = True
        else: 
            # clear the content in the dir
            os.system(f"rm -rf {task_path}")
            ctor = LLMDagConstructor(self.task_type, beam_limit=1, eval_model_type=self.model_type, do_feature_selection=False, high_order_num=high_order_num, token_limit=token_limit)
        ctor.astar_k_step(step_num, data_agenda = data_agenda, data_desc=desc, target_col=self.target_col, tb_name=f"{self.dir_name}_src_tb_train", task_name = self.dir_name, do_unfinished=unfinished)
        
        
        print(ctor.get_best_code())
        with open(os.path.join(task_path, "cur_states.pkl"), "wb") as f:
            pickle.dump(ctor, f)
            
        # copy the dir to dir_seed
        os.system(f"cp -r {task_path} {task_path}_{postfix}")
        os.system(f"rm -rf {task_path}")

        return ctor
    
if __name__ == "__main__": 
    args = argparse.ArgumentParser()
    args.add_argument('--task_name', type = str, default = "heart")
    args.add_argument('--model_type', type = str, default = "RF")
    args.add_argument('--iter_num', type=int, default=10)
    args.add_argument('--complex_num', type=int, default=5)
    args = args.parse_args()
    assert args.task_name != ""
    
    task_name, target_col, task_type = task_config(args.task_name)
    importTable_with_split(os.path.join(dataset_path, task_name, "train_new.csv"), f"{task_name}_src_tb", target_col, get_conn(), False, task_type)
    t_map = {}
    cur_task = TestDir(task_name, task_type, target_col, args.model_type)
    startt = time.time()
    cur_task.test_astar_step(args.iter_num, True, args.complex_num, f"{args.model_type}_Full")
    endt = time.time()
    t_map[args.model_type] = endt - startt
            
    print(f"Current time map of Adda execution is ", t_map)