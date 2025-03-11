import os
import sys

# 获取项目根目录并添加到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.llm.llm_dag_util import *
from src.pg.sql_utils import *
from src.pg.import_table import *
from src.pg.python_polish import *
from src.pg.func_utils import *
# from src.pg
import argparse
import termcolor
import pickle
import warnings
from src.llm.tests.test_util import * 
from src.env import *

def parse_args():
    args = argparse.ArgumentParser()
    args.add_argument('--do_pygen', type = bool, default = True) # only when this is False, then the code_path is meaningful
    args.add_argument('--task_name', type = str, default = "")
    
    args.add_argument('--do_feature_selection', type = bool, default = False)
    # ---------------------
    args.add_argument('--do_multipipe_opt', type = bool, default = False)
    args.add_argument('--storage_attr_num', type = int, default = 3)
    # ---------------------
    args.add_argument('--do_sql_opt', type = bool, default = False)
    args.add_argument('--id_col', type = str, default = 'id')
    # ---------------------
    # could reuse the previous pipelines to test
    args.add_argument('--reload', type = bool, default = True)
    
    args.add_argument('--model_type', type = str, default = "RF")
    args.add_argument('--use_py_train_pred', type = bool, default = True)
    args = args.parse_args()
    
    assert args.task_name != ""
    task_name, target_col, task_type = task_config(args.task_name)
    args.target_col = target_col
    args.task_type = task_type
    return args

if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    auc_answer_list = []    
    task_time = []
    args = parse_args()
    dir_path = os.path.join(test_save_path, args.task_name)
    postfix = f"_{args.model_type}_Full"
    
    
    # rename the dir to task_name
    origin_name = os.path.join(test_save_path, f"{args.task_name}{postfix}")
    exec_name = os.path.join(test_save_path, args.task_name)
    os.rename(origin_name, exec_name)
    conn = get_conn()
    
    # get the version
    csvpath = os.path.join(dataset_path, args.task_name, "train_new.csv")
    last_pipector_path = os.path.join(test_save_path, args.task_name, "cur_states.pkl")
    pycodepath = os.path.join(test_save_path, args.task_name, "pycodes")
    
    df = pd.read_csv(csvpath)
    db_tb_name = f"{args.task_name}_src_tb"
    row_num, col_num = df.shape[0] - int(df.shape[0]/5), df.shape[1]
    os.makedirs(pycodepath, exist_ok=True)
    
    
    # 1. python pipelines generation
    with open(last_pipector_path, "rb") as f:
        pipeCtor = pickle.load(f)
    pipeCtor.tb_name = db_tb_name

    # 2. SQL generation
    #----------------------api version 2-------------------------
    pipes = pipeCtor.pipes
    polisher = PythonPolisher(db_tb_name, args.target_col, "df", pipes, dir_path, 2, col_num, pipeCtor, id_col = args.id_col, total_num=row_num, do_optimize=2, task_type=args.task_type, use_py_train_pred=args.use_py_train_pred, model_type=args.model_type)
    polisher.polish_code()
    if args.do_multipipe_opt:
        # pipeCtor.multipipe_tree_ctor(polisher.nodeid2OpTypeEnum)
        polisher.multi_pipe_schedule_v2(args.storage_attr_num, row_num)
    
    auc_answer = polisher.generate_sql()
    speed_record = polisher.speed_record
    task_time.append(speed_record["sql"][0])
    print(termcolor.colored(f"Final valid and test score: {auc_answer}", "yellow"))

    
    # check the correctness of feature
    check_same_df = False
    if check_same_df:
        polisher.check_feature_correctness()
    
    print(termcolor.colored("finish generating sql and udf", "green"))
    
    # rename the task_name to original name
    os.rename(exec_name, origin_name)
    print(termcolor.colored(f"Final valid and test score: {auc_answer_list}", "yellow"))
    print(f"Task [{args.task_name}] execution time: {task_time}, mean time: {sum(task_time)/len(task_time)}")
    print(f"Task [{args.task_name}] with model type [{args.model_type}]: {auc_answer}")
        