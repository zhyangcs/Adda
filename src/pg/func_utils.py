from inspect import cleandoc
import time
import pandas as pd
import random
import numpy as np
from src.pg.op_type import *
import copy
import sys
import io
import re
import ast
import termcolor
from src.pg.add_pandas_transformer import *
import shutil
from src.env import *

def attr_to_lower_case(code_list: list, attrs: list) -> str:
    """
    convert the attribute name of pandas to lower case
    """
    new_code_list = []
    for code in code_list:
        for attr in attrs:
            code = code.replace(f"{attr}", f"{attr.lower()}")
        new_code_list.append(code)
    return new_code_list

def get_python_code(python_path: str) -> list[str]:
    """
    get python code from the path or straightly return the code
    """
    if python_path.startswith('/'):
        with open(python_path, 'r') as f:
            python_code = f.readlines()
        return python_code
    else:
        return python_path
    
def get_script_scope(python_code: str):
    """
    for a python code, exec it and get the relevant script scope
    """
    str_code = cleandoc("""
    import inspect
    from pandas_to_sql import wrap_df
    import pandas as pd
    import numpy as np
    from sklearn.preprocessing import LabelEncoder
    from sklearn.preprocessing import StandardScaler
    """) + '\n' + python_code
    script_scope = {}
    exec(str_code, script_scope)
    return script_scope 
    
def grab_import(code: list[str]) -> list[str]:
    """
    grab the import code from the python code
    """
    import_list = []
    for line in code:
        if line.startswith('import') or line.startswith('from'):
            import_list.append(line)
    return import_list    

def split_code_for_comment(python_code: list[str], split_start:str, tb_name:str, var_name:str) -> (str, list[str]):
    """
    split the code by the `# task desc: ` notation 
    """
    pattern = r"# task desc: node\[(\d+)\]"
    pattern_high_order = r"# task desc: node\[(\d+)\]:\[UNSUPPORT\]"
    code_block = []
    node_id_list = [] # store the relevant nodeid or None
    high_order_idx = []
    cur_code = ''
    for line in python_code:
        if line.startswith(split_start):
            match = re.search(pattern, line)
            match_high_order = re.search(pattern_high_order, line)
            if match_high_order:
                node_id_list.append(int(match_high_order.group(1)))
                high_order_idx.append(len(code_block))
            elif match:
                node_id_list.append(int(match.group(1)))
            else:
                node_id_list.append(None)
                
            if cur_code != '':
                code_block.append(cur_code)
                cur_code = ''
                
        if not line.startswith('#') and not line == '\n':
            cur_code += line
    if cur_code != '':
        code_block.append(cur_code)
    
    if not code_block:
        # Handle empty code case
        pre_code = cleandoc("""
        import inspect
        from pandas_to_sql import wrap_df
        from src.pg.df_wrapper import DataFrameWrapper
        """)
        return pre_code, [], [], []

    pre_code = cleandoc("""
    import inspect
    from pandas_to_sql import wrap_df
    from src.pg.df_wrapper import DataFrameWrapper
    """) + '\n' + code_block[0]
        
    return pre_code, code_block[1:], node_id_list, high_order_idx

def combine_code_block(op_list: list[OpType], code_block: list[str]) -> (list[bool], list[str]):
    """
    combine the code block of Easy and Unsupport
    """
    new_op_list = []
    new_code_block = []
    cur_code = code_block[0]
    pre_op = op_list[0]
    startidx = -1
    for idx, (cur_op, code) in enumerate(zip(op_list[1:], code_block[1:])):
        if cur_op.op_type == pre_op.op_type and (cur_op.op_type in EASY_OF_TYPE or cur_op.op_type == OpTypeEnum.FILLNA):
            cur_code += code
        else:
            new_code_block.append(cur_code)
            
            if pre_op.op_type == OpTypeEnum.FILLNA:
                # combine the op_list of the fillna
                fillna_list = []
                for op in op_list[startidx+1:idx+1]:
                    fillna_list.append(op.parameters["fillna_type"])
                    
                new_op = OpType(OpTypeEnum.FILLNA)
                new_op.parameters["fillna_type"] = fillna_list
                new_op_list.append(new_op)    
            else:
                new_op_list.append(pre_op)
            cur_code = code
            pre_op = cur_op
            startidx = idx
    if cur_code != '':
        new_op_list.append(pre_op)
        new_code_block.append(cur_code)
    return new_op_list, new_code_block

def add_train_part(op_list: list[OpType], code_block: list[str]) -> (list[bool], list[str]):
    """
    add the train part for the code block
    """
    op_list.append(OpType(OpTypeEnum.TRAIN))
    code_block.append("")
    return op_list, code_block

def add_predict_part(op_list: list[OpType], code_block: list[str]) -> (list[bool], list[str]):
    """
    add the predict part for the code block
    """
    op_list.append(OpType(OpTypeEnum.PREDICT))
    code_block.append("")
    return op_list, code_block

def exec_time(code:str) -> time:
    """
    exec the code and return the exec time
    """
    start_time = time.time()
    print(termcolor.colored(code, 'green'))
    exec(code)
    end_time = time.time()
    return end_time - start_time

def get_staged_exec_time(code:str) -> list:
    """
    return list of [load_time, computation_time, output_time] 
    """
    captured_ouput = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured_ouput
    
    start_time = time.time()
    exec(code)
    end_time = time.time()
    
    sys.stdout = original_stdout
    # print(captured_ouput, end_time-start_time)
    # extract the time from the captured output
    # 'load time:  1.4493296146392822\noutput time:  4.362600564956665\n'
    output_str = captured_ouput.getvalue()
    load_match = re.search(r'load time:  (.*)', output_str)
    if load_match:
        load_time = float(load_match.group(1))
    output_match = re.search(r'output time:  (.*)', output_str)
    if output_match:
        output_time = float(output_match.group(1))
        
    return [load_time, end_time - start_time - load_time - output_time, output_time]


def generate_fake_data_file(in_csv_file:str, out_csv_file:str, num_of_record:int) -> None:
    """
    generate `num_of_record` fake data from the `in_csv_file` and save it to the `out_csv_file`
    """
    temp_df = pd.read_csv(in_csv_file)
    new_df = pd.DataFrame.from_records([{} for _ in range(num_of_record)])
    for col in temp_df.columns:
        if temp_df[col].dtype == 'int64':
            new_df[col] = np.random.randint(1, 6, num_of_record)
        elif temp_df[col].dtype == 'float64':
            new_df[col] = np.random.randn(num_of_record)
        elif temp_df[col].dtype == 'bool':
            new_df[col] = np.random.randn(num_of_record) > 0
        elif temp_df[col].dtype == 'object':
            new_df[col] = pd._testing.rands_array(10, num_of_record)
            
    new_df.to_csv(out_csv_file, index=False)
    
def generate_fake_data(df: pd.DataFrame, num_of_record:int) -> pd.DataFrame:
    """
    generate `num_of_record` fake data same to the attr of df
    """
    ret = pd.DataFrame.from_records([{} for _ in range(num_of_record)])
    for col in df.columns:
        if df[col].dtype == 'int64':
            ret[col] = np.random.randint(1, 6, num_of_record)
        elif df[col].dtype == 'float64':
            ret[col] = np.random.randn(num_of_record)
        elif df[col].dtype == 'bool':
            ret[col] = np.random.randn(num_of_record) > 0
        elif df[col].dtype == 'object':
            enum_list = ['a', 'b', 'c', 'd', 'e']
            ret[col] = [enum_list[random.randint(0, 4)] for _ in range(num_of_record)]
    
    return ret
            
def get_diff_attr(in_df: pd.DataFrame, out_df: pd.DataFrame) -> list[str]:
    """
    find all columns in both in_df and out_df, whose value is not same (which means the function change the value of the column)
    """
    diff_attr = []
    for col in out_df.columns:
        if col in in_df.columns:
            if not in_df[col].equals(out_df[col]):
                diff_attr.append(col)
        else:
            diff_attr.append(col)
    return diff_attr

def grab_attr_from_node(slice) -> list:
    # print(ast.dump(slice, indent = 4))
    if hasattr(slice, 'value'):
        return [slice.value]
    elif hasattr(slice, 'elts'):
        ret_list = []
        for ele in slice.elts:
            if hasattr(ele, 'value'):
                ret_list.append(ele.value)
            elif hasattr(ele, 'func'):
                ret_list.append(0x7FFFFFFF)
        return ret_list
    return []

def add_type_change_drop(python_path: str, var: str, extra_step):
    with open(python_path, 'r') as f:
        python_code = f.readlines()
        
    with open(python_path, 'w') as f:
        cur_ns = {}
        exec(''.join(python_code), cur_ns)
        df = cur_ns.get(var)
        # for each column in the df, we change the bool or int --> float, and drop the column which is not float
        python_code.append("\n# task desc: change the type of the column and drop the column not necessary\n")
        label_encoder_cols = []
        for col in df.columns:
            if df[col].dtype == 'bool' or df[col].dtype == 'int':
                python_code.append("if '%s' in %s.columns:\n" %(col, var))
                python_code.append("    %s['%s'] = %s['%s'].astype(float)\n" %(var, col, var, col))
            elif df[col].dtype == 'object' or df[col].dtype == 'category':
                # python_code.append("%s.drop('%s')\n" %(var, col))
                label_encoder_cols.append(col)
        
        # python_code.append("from sklearn.preprocessing import LabelEncoder\n")
        # python_code.append("label_encoder = LabelEncoder()\n")
        for col in label_encoder_cols:
            if extra_step != 0:
                # the label attribute may generated in the df
                if f"{col}_Label" not in df.columns:
                    python_code.append("# task desc: label encode the column %s\n" %col)
                    python_code.append("%s['%s'] = label_encoder.fit_transform(%s['%s'])\n" %(var, f"{col}_Label", var, col))
                python_code.append("# task desc: drop column\n")
                python_code.append("if '%s' in %s.columns:\n" %(col, var))
                python_code.append("    %s = %s.drop(columns = ['%s'])\n" %(var, var, col))
        # python_code.append("%s = %s.drop(columns = [%s])\n" %(var, var, ",".join(drop_cols)))
        python_code.append("\n")
        f.write(''.join(python_code))
    return

def shorten_var(code_path:str, df_name:str):
    # copy the file to _old.py
    shutil.copy(code_path, code_path.replace('.py', '_old.py'))
    with open(code_path, 'r') as f:
        code = f.readlines()
    full_code = ''.join(code)
    addpandastransformer = AddPandasTransformer(df_name)
    tree = ast.parse(full_code)
    addpandastransformer.visit(tree)
    attrs = addpandastransformer.get_attrs()
    replace_map = dict()
    for attr in attrs:
        if len(attr)> 50:
            # replace rule: replace each word between '_' with prefix [abab_baba-->a_b]
            word_list = attr.split('_')
            new_attr = '_'.join([word[0] for word in word_list])
            postfix = 0
            while f"{new_attr}_{postfix}" in replace_map:
                postfix += 1
            replace_map[f"{new_attr}_{postfix}"] = attr
    for new_attr, old_attr in replace_map.items():
        full_code = full_code.replace(f"'{old_attr}'", f"'{new_attr}'")
    with open(code_path, 'w') as f:
        f.write(full_code)
            

def self_copy(self_map: dict) -> dict:
    """
    deep copy the element in the self_map if they could, else do the normal ref  
    """
    new_dict = {}
    for key, value in self_map.items():
        try:
            new_dict[key] = copy.deepcopy(value)
        except TypeError:
            new_dict[key] = value
    return new_dict

def get_reformatted_code(code: list[str], var_name: str, table_name: str, target_col: str, limit:int=0, add_train:bool=True, task_type:str = "classify")->list[str]:
    """
    1. change the read_csv to read_sql from the `table_name`
    2. add the train of the model
    """
    limit_str = ''
    if limit != 0:
        limit_str = ' limit %d' %limit
    formatted_code = []
    for line in code:
        if 'read_csv' in line:
            formatted_code.append("import psycopg2\n")
            formatted_code.append(f"conn = psycopg2.connect(dbname='{pg_db}', user='{pg_user}', port={pg_port})\n")
            formatted_code.append("%s = pd.read_sql('select * from %s %s', conn)\n" %(var_name, f"{table_name}_train", limit_str))
        elif 'read_sql' in line:
            # delete the limit sequence
            formatted_code.append("%s = pd.read_sql('select * from %s %s', conn)\n" %(var_name, f"{table_name}_train", limit_str))
        else:
            formatted_code.append(line)
    
    if add_train:
        formatted_code.append("import lightgbm as lgb\n")
        formatted_code.append("y = %s['%s']\n" %(var_name, target_col))
        formatted_code.append("X = %s.drop(columns = ['%s'])\n" %(var_name, target_col))
        formatted_code.append("params = {'n_estimators': 100, 'seed': 42, 'num_threads': 1}\n")
        if task_type == "classify":
            formatted_code.append("gbm = lgb.LGBMClassifier(**params)\n")
        else:
            formatted_code.append("gbm = lgb.LGBMRegressor(**params)\n")
        formatted_code.append("gbm.fit(X, y)\n")
        formatted_code.append("import pickle\n")
        formatted_code.append(f"with open('{test_save_path}/tmp_model.pkl', 'wb') as f:\n")
        formatted_code.append("    pickle.dump(gbm, f)\n")
    
    return formatted_code
            
def add_break_point(python_code: list[str]) -> list[str]:
    """
    add time estimation for loading data[read_sql] and output data[to_csv]
    """
    formatted_code = ["import time\n"]
    for line in python_code:
        if 'read_sql' in line:
            formatted_code.append("load_start = time.time()\n")
            formatted_code.append(line)
            formatted_code.append("load_end = time.time()\n")
            formatted_code.append("print('load time: ', load_end - load_start)\n")
        elif 'to_csv' in line or 'dump' in line:
            formatted_code.append("output_start = time.time()\n")
            formatted_code.append(line)
            formatted_code.append("output_end = time.time()\n")
            formatted_code.append("print('output time: ', output_end - output_start)\n")
        else:
            formatted_code.append(line)
    print(termcolor.colored("".join(formatted_code), 'green'))
    return formatted_code
    
def substitute_cur_df(script_scope: dict, var_name:str, do:bool = False, k:int = 10)->None:
    """
    substitute the current df with the head k records
    """
    if do:
        df = script_scope.get(var_name)
        if df is not None:
            script_scope[var_name] = df.head(k)
    return

def get_sample_for_category_col(df: pd.DataFrame, col: str) -> list[str]:
    """
    get the sample for the category column
    """
    return list(map(lambda x: str(x), list(df[col].unique())))

def data_preprocess(data):
    if type(data) == list:
        ret = []
        for d in data:
            ret.append(data_preprocess(d))
        return ret
    
    data_df = copy.deepcopy(data)
    print(data_df)
    # inf to nan
    data_df = data_df.replace([np.inf, -np.inf], np.nan)
    # fillna for the float and int
    for c in data_df.columns:
        if data_df[c].dtype != 'int64' and data_df[c].dtype != 'float64':
            data_df[c] = data_df[c].astype(object)
            data_df[c], _  = pd.factorize(data_df[c])
        else:
            data_df[c] = data_df[c].fillna(data_df[c].mean())
    data_df = data_df.fillna(0)
    return data_df


def delete_drop(code:str):
    code_list = code.split("\n")
    code_list = list(filter(lambda x: "drop" not in x, code_list))
    return "\n".join(code_list)

def check_similar(df1: pd.DataFrame, df2: pd.DataFrame) -> list[str]:
    """
    check whether the two dataframe are similar
    """
    # convert the column name to lower case
    df1.columns = df1.columns.str.lower()
    df2.columns = df2.columns.str.lower()
    # check same for str, check similar for float and int
    diff_col = []
    for col in df1.columns:
        if df1[col].dtype == 'object':
            if not df1[col].equals(df2[col]):
                diff_col.append(col)
        else:
            if not np.allclose(df1[col], df2[col], atol=0.2, rtol=0.1):
                diff_col.append(col)
    
    return diff_col

def read_data_info(dir_name:str):
    root_path = os.path.join(dataset_path, dir_name)
    with open(os.path.join(root_path, "data_agenda.txt"), "r") as f:
        data_agenda = f.readlines()
    with open(os.path.join(root_path, "desc.txt"), "r") as f:
        desc = f.readlines()
    
    return data_agenda, desc, os.path.join(root_path, f"train_new.csv")


def init_files(dirs:list, files:list):
    for cur_dir in dirs:
        if not os.path.exists(cur_dir):
            os.makedirs(cur_dir, exist_ok=True)
    for cur_file in files:
        with open(cur_file, 'w') as f:
            f.write("")
            
