import os
from src.pg.sql_utils import *
import pandas as pd
from src.pg.func_utils import *
from src.pg.import_table import *
import re
from src.template.temp_udfc import *
from src.pg.compile_utils import *
from src.env import *
from src.llm.utils.common_utils import *
import time

prefix_sep = '''
RETURNS text[] AS $$
    import pandas as pd
    from decimal import Decimal

    data = plpy.execute("SELECT * FROM %s" % (plpy.quote_ident(table_name)))
    listdata = []
    for outter in data:
        cur = {}
        for k, v in outter.items():
            if isinstance(v, Decimal):
                cur[k] = float(v)
            else:
                cur[k] = v
        listdata.append(cur)
'''

postfix_sep = '''
$$ LANGUAGE plpython3u;\n
'''

postfix_com = '''
    output = df.to_dict(orient='records')
    return output
$$ LANGUAGE plpython3u;\n
'''

prefix_warm = '''
CREATE OR REPLACE FUNCTION warm_udf() RETURNS void AS $$
'''

class Py2Udf():
    
    
    # although more general, but somehow sacrifice the performance
    def convert_for_train_py(in_df:pd.DataFrame, target_col:str, cur_table_name:str, model_name:str, task_type:str, id_col:str, import_code:list, model_type:str, tb_name:str):
        """
        convert the training data to the udf
        """
        sql_type = f'drop function if exists train_input cascade;\n'
        tmp, in_attrs = df_to_sqltype(in_df, 'train_input', target_col = target_col, id_col = id_col)
        # in_attrs.remove(target_col)
        sql_type += tmp
        
        print("------------------", in_attrs, model_type)
        udf_template = f"""CREATE OR REPLACE FUNCTION {model_type}_train(input train_input[]) 
RETURNS text AS $$
    {"    ".join(import_code)}
    import pandas as pd
    import os
    import pickle
    import numpy as np
    import time
    # from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, plot_tree
    {modeltype2importcode(model_type, task_type)}
    df = pd.DataFrame(input, columns = [{','.join(list(map(lambda x: "'"+x+"'", in_attrs)))}])
    
    # fillnan
    df = df.replace([np.inf, -np.inf], np.nan)
    df.fillna(0, inplace=True)
    model = {modeltype2class(model_type, task_type)}(random_state=42)
    train_y = df['{target_col}']
    train_x = df.drop(columns=['{target_col}'])
    model.fit(train_x, train_y)
    # get id of model
    cur_models = os.listdir('{model_store_path}')
    cur_id = max([int(model[:-4].split('_')[-1]) for model in cur_models]) + 1 if cur_models else 0
    # cur_id = int(time.time() * 1000) + os.getpid()
    
    model_name = f"{model_name}_{model_type}_{{cur_id}}.pkl"
    model_path = os.path.join('{model_store_path}', model_name)
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    return model_path
$$ LANGUAGE plpython3u;"""
        print(termcolor.colored(udf_template, "yellow"))

        cte1 = "tmp_res_store"
        call_udf1 = f"select {model_type}_train(array(select row({','.join(in_attrs)})::train_input from {cur_table_name})) as model_path"
        # call_udf2 = f"insert into model_table(tb_name, model_type, path) select '{model_name}', '{model_type}', model_path from {cte1} limit 1"
        call_udf2 = f"insert into model_table(tb_name, model_type, path) select '{model_name}', '{model_type}', model_path from {cte1} limit 1"
        return sql_type + udf_template, (call_udf1, call_udf2), (cte1, "")


    
    def convert_for_predict_py(in_df:pd.DataFrame, target_col:str, cur_table_name:str, model_name:str, task_type:str, id_col:str, import_code:list, model_type:str):
        """
        convert the predict data to the udf
        """
        sql_type = f'drop function if exists predict_input cascade;\n'
        tmp, in_attrs = df_to_sqltype(in_df, 'predict_input', target_col = target_col, id_col = id_col)
        sql_type += tmp
        print("------------------", in_attrs)
        
        
        udf_template = f"""CREATE OR REPLACE FUNCTION {model_type}_predict(input predict_input[], model_path text) 
RETURNS float AS $$
    {"    ".join(import_code)}
    import os
    import pickle
    from sklearn.metrics import roc_auc_score
    import numpy as np
    {modeltype2importcode(model_type, task_type)}
    df = pd.DataFrame(input, columns = [{','.join(list(map(lambda x: "'"+x+"'", in_attrs)))}])
    # fillnan
    df = df.replace([np.inf, -np.inf], np.nan)
    df.fillna(0, inplace=True)

    
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
        
    y_true = df['{target_col}']
    X_test = df.drop(columns=['{target_col}'])
    
    if '{task_type}' == 'classify':
        y_pred = model.predict_proba(X_test)[:, 1]
        return float(roc_auc_score(y_true, y_pred))
    else:
        y_pred = model.predict(X_test)
        return float(1-np.sum(np.abs(y_true - y_pred))/np.sum(np.abs(y_true - np.mean(y_true))))
$$ LANGUAGE plpython3u;"""
        print(termcolor.colored(udf_template, "yellow"))

        cte1 = "tmp_res_store"
        
        call_udf1 = f"select {model_type}_predict(array(select row({','.join(in_attrs)})::predict_input from {cur_table_name}), (select path from model_table where tb_name = '{model_name}' and model_type = '{model_type}' limit 1)) as output"
        call_udf2 = f"select output as data from {cte1} limit 1"
        return sql_type + udf_template, (call_udf1, call_udf2), (cte1, "")

    def convert_for_final_op_py(df:pd.DataFrame, target_col:str, id_col:str, cur_table_name:str, op:PipeTypeEnum, task_type:str, import_code:list, tb_name:str, model_type:str):
        """
        task type: classify or regression
        """
        if op == PipeTypeEnum.TRAIN:
            return Py2Udf.convert_for_train_py(df, target_col, cur_table_name, tb_name, task_type, id_col, import_code, model_type, tb_name)
        elif op == PipeTypeEnum.PREDICT:
            return Py2Udf.convert_for_predict_py(df, target_col, cur_table_name, tb_name, task_type, id_col, import_code, model_type)    

    def convert_for_combined_exec(in_df:pd.DataFrame, out_df:pd.DataFrame, cur_table_name:str, var:str, code:str, seq:int, import_code: list[str]):
        """
        generate the relavant postgres pl/python udf from a python code, which used for the combination execution
        """
        sql_type = 'drop function if exists udf_%s cascade;\n' % (str(seq))
        tmp, in_attrs = df_to_sqltype(in_df, 'cur_input_'+str(seq))
        sql_type += tmp
        tmp, out_attrs = df_to_sqltype(out_df, 'cur_output_'+str(seq))
        sql_type += tmp
        for in_attr in in_attrs:
            code = code.replace(f"'{in_attr}'", f"'{in_attr.lower()}'")
        in_attrs = list(map(lambda x: x.lower(), in_attrs))

        # Start building the UDF string
        udf = f"CREATE OR REPLACE FUNCTION udf_{seq} (input cur_input_{seq}[])\n"
        udf += f"RETURNS cur_output_{seq}[] AS $$\n"

        # Add imports with proper indentation
        if import_code:
            udf += "    " + "\n    ".join(import_code) + "\n"
        udf += "    import pandas as pd\n"
        udf += "    import numpy as np\n"

        # Add UDF body lines, ensuring 4-space indentation
        udf_lines = []
        # Correct f-string for DataFrame creation
        udf_lines.append(f"    {var} = pd.DataFrame(input, columns=[{','.join(map(repr, in_attrs))}])")

        # --- Add NaN handling before user code ---
        udf_lines.append("    # Replace inf/nan before processing")
        udf_lines.append(f"    {var}.replace([np.inf, -np.inf], np.nan, inplace=True)")
        # -----------------------------------------

        # --- Insert user code ---
        user_code_lines = [f"    {line}" for line in code.strip().split('\n')]
        udf_lines.extend(user_code_lines)
        # -----------------------

        # --- Add NaN handling before returning ---
        udf_lines.append("    # Replace inf/nan before returning")
        udf_lines.append(f"    {var}.replace([np.inf, -np.inf], np.nan, inplace=True)")
        udf_lines.append(f"    {var}.fillna(0, inplace=True)") # Fill remaining NaNs with 0
        # --- Explicitly convert integer columns ---
        udf_lines.append("    # Ensure integer columns are truly integer type before returning")
        # Infer integer columns based on the output type definition (heuristic)
        # A more robust way would involve passing type info, but this handles common cases.
        for col in out_attrs: # out_attrs contains the names of columns in the output type
            # Heuristic: if the column name suggests it's an ID, label, or survived status, try converting
            if col.endswith('_id') or col == 'id' or col.endswith('_label') or col == 'survived' or col.endswith('pclass'): # Added pclass as it's often treated as int/category
                 # Check if column exists before trying to convert
                 udf_lines.append(f"    if '{col}' in {var}.columns:")
                 udf_lines.append(f"        try:")
                 udf_lines.append(f"            {var}['{col}'] = {var}['{col}'].astype(np.int64)")
                 udf_lines.append(f"        except ValueError as e:") # Handle potential errors if conversion fails
                 udf_lines.append(f"            plpy.warning(f'Could not convert column {{col}} to int64: {{e}}')")

        # ---------------------------------------

        # Final assembly:
        udf += "\n".join(udf_lines) + "\n"
        udf += postfix_com # Append the postfix directly

        # Define call statements
        cte1 = f"tmp_res_store_{seq}"
        # Correct column joining for call_udf1
        call_udf1 = f"select udf_{seq}(array(select row({','.join(in_attrs)})::cur_input_{seq} from {cur_table_name})) as row1"
        call_udf2 = f"select (unnest(row1)).* from {cte1}"

        return sql_type + udf, (call_udf1, call_udf2), (cte1, "")
    
    def get_udf_from_template(func_code:str) -> str:
        func_name, origin_type, new_type = Py2Udf.parse_func_code(func_code)
        FromDatumFunc = type_to_FromDatumFunc(origin_type)
        GetDatumFunc = type_to_GetDatumFunc(new_type)
        cur_udfc = TEMP_UDFC.format(function_body=func_code, function_name=func_name, origin_type = origin_type, new_type = new_type, FromDatumFunc=FromDatumFunc, GetDatumFunc=GetDatumFunc)
        return cur_udfc
    
    def convert_for_c_function(in_df:pd.DataFrame, out_df:pd.DataFrame, cur_table_name:str, apply_func_code:str, target_col:str, seq:int):
        """
        automatically generate the apply function of the c function
        """
        # 1. generate the c function from the template and the apply function, then use g++ to compile to the so file
        # func_name, origin_type, new_type = Py2Udf.parse_func_code(apply_func_code)
        # FromDatumFunc = type_to_FromDatumFunc(origin_type)
        # GetDatumFunc = type_to_GetDatumFunc(new_type)
        # cur_udf = TEMP_UDFC.format(function_body=apply_func_code, function_name=func_name, origin_type = origin_type, new_type = new_type, FromDatumFunc=FromDatumFunc, GetDatumFunc=GetDatumFunc)
        cur_udf = Py2Udf.get_udf_from_template(apply_func_code)
        
        c_code_path = os.path.join(udf_path, 'code', f'udfc_{str(seq)}.cpp')
        c_lib_path = os.path.join(udf_path, 'lib', f'udfc_{str(seq)}.so')
        
        udf_name = "udfc_%s" %(str(seq))
        with open(c_code_path, 'w') as f:
            f.write(cur_udf)
        
        compile_udf(code_path=c_code_path, lib_path=c_lib_path)
        print("generate the udf: %s in %s" %(udf_name, c_lib_path))
        
        # 2. register the function and calling the function
        reg_udf = """
CREATE OR REPLACE FUNCTION %s(input udf_input_%d[]) RETURNS udf_output_%d[]
AS '%s', 'udf_ctemplate' LANGUAGE C STRICT;
        """ %(udf_name, seq, seq, c_lib_path)
        
        sql_type = ''
        tmp, in_attrs = df_to_sqltype(in_df, 'udf_input_%d' %(seq), target_col = target_col)
        sql_type += tmp
        
        tmp, out_attrs = df_to_sqltype(out_df, 'udf_output_%d' %(seq), target_col = target_col)
        sql_type += tmp
        
        udf_tb = "udf_tb_%d" %(seq)
        call_udf = "select (%s(array(select row(%s)::udf_input_%d from %s))) as udf" %(udf_name, ','.join(in_attrs), seq, cur_table_name)
        call_udf2 = "select (unnest(udf)).* from %s" %(udf_tb)
        
        return sql_type + reg_udf, (call_udf, call_udf2), (udf_tb, "")
        
    def parse_func_code(func_code:str):
        """
        parse the cpp function code: return (function_name, original_type, new_type)
        example: 
            int64* is_alone(int64* arr, int arrlen) --> (is_alone, int64, int64)
        """
        pattern = r'\s*(\w+)\s*\*?\s*(\w+)\s*\(([^)]*)\)'
        match = re.search(pattern, func_code)

        if match:
            original_type, function_name, _ = match.groups()
            return function_name, original_type, original_type
        else:
            return None
        
    
    def convert_for_train(df:pd.DataFrame, target_col:str, cur_table_name:str, model_name:str, task_type:str, id_col:str):      
        udf_name = "lightgbm_" + task_type  
        lgb_so_path = os.path.join(udf_path, 'lib', 'udf_lightgbm.so')
        reg_udf = f"""
CREATE OR REPLACE FUNCTION lightgbm_classification(input train_input[], num_class int) RETURNS int4
AS '{lgb_so_path}', 'lightgbm_classify'
LANGUAGE C STRICT;\n
CREATE OR REPLACE FUNCTION lightgbm_regression(input train_input[]) RETURNS int4
AS '{lgb_so_path}', 'lightgbm_regress'
LANGUAGE C STRICT;\n
        """
        sql_type = 'drop type if exists train_input cascade;\n'
        tmp, in_attrs = df_to_sqltype(df, 'train_input', target_col=target_col, id_col = id_col)
        # in order to set the target column in the last column
        print(in_attrs, target_col)
        in_attrs.remove(target_col)
        
        # in_attrs = list(map(lambda x: '"'+x+'"', in_attrs))
        
        sql_type += tmp
        call_tb = "train_tb"
        second_param = ''
        if task_type == 'classify':
            second_param = ', (select count(distinct(%s))::int from %s)' %(target_col, cur_table_name)
        call_udf = "select (%s(array(select row(%s)::train_input from %s)%s)) as model_data\n" %(udf_name, ','.join(in_attrs) + ', ' + target_col , cur_table_name, second_param)
        # select_sql = "insert into models (name, data) select '%s', model from " %(model_name)
        select_sql = "select %s.*, (select model_data from %s limit 1) as model_data, '%s' as model_name from %s" %(cur_table_name, call_tb, model_name, cur_table_name)
        
        return sql_type + reg_udf, (call_udf, select_sql), (call_tb, "")

    
        
    
    def convert_for_final_op(df:pd.DataFrame, target_col:str, id_col:str, cur_table_name:str, op:PipeTypeEnum, task_type:str):
        """
        task type: classify or regression
        """
        udf_name = f"lgb_{task_type}_{str(op)}"
        lgb_so_path = os.path.join(udf_path, 'lib', 'udf_lightgbm.so')
        reg_udf = f"""
CREATE OR REPLACE FUNCTION {udf_name}(input train_input[], num_class int) RETURNS float4
AS '{lgb_so_path}', '{udf_name}'
LANGUAGE C STRICT;\n
        """
        sql_type = 'drop type if exists train_input cascade;\n'
        tmp, in_attrs = df_to_sqltype(df, 'train_input', target_col=target_col, id_col = id_col)
        in_attrs.remove(target_col)
        
        sql_type += tmp
        call_tb = f"{str(op)}_tb"
        if task_type == "classify" and op != PipeTypeEnum.PREDICT:
            second_param = ', (select count(distinct(%s))::int from %s)' %(target_col, cur_table_name)
        else:
            # currently just for fast testing
            second_param = ', 0'
        call_udf = f"select ({udf_name}(array(select row({','.join(in_attrs) + ', ' + target_col})::train_input from {cur_table_name}){second_param})) as data\n"
        select_sql = f"select {cur_table_name}.*, (select data from {call_tb} limit 1) as data from {cur_table_name}"
        
        return sql_type + reg_udf, (call_udf, select_sql), (call_tb, "")

    def convert_for_predict(df:pd.DataFrame, model_name:str, cur_table_name:str, udf_name:str, target_col:str, id_col:str, seq:int):
        lgb_so_path = os.path.join(udf_path, 'lib', 'udf_lightgbm.so')
        reg_udf = f"""
CREATE OR REPLACE FUNCTION {udf_name}(input predict_input_{str(seq)}[], model_string text) RETURNS predict_output_{str(seq)}[]
AS '{lgb_so_path}', 'lightgbm_predict'
LANGUAGE C STRICT;\n"""
        
        sql_type = 'drop type if exists predict_input cascade;\n'
        tmp, in_attrs = df_to_sqltype(df, 'predict_input_' %(seq), id_col = id_col)
        sql_type += tmp
        
        df_out = pd.DataFrame(columns=[id_col, target_col]).astype(int)
        tmp, out_attrs = df_to_sqltype(df_out, 'predict_output_' %(seq), id_col = id_col)
        sql_type += tmp
        
        predict_tb = "predict_tb"
        call_udf = "select (%s(array(select row(%s)::predict_input_%s from %s), (select path from model_table where tb_name = '%s' and model_type = '%s'))) as predict\n" %(udf_name, ','.join(in_attrs), seq, cur_table_name, model_name, model_type)
        call_udf2 = "select (unnest(predict)).* from %s" %(predict_tb)
        
        return sql_type + reg_udf, (call_udf, call_udf2), (predict_tb, "")
        
    def convert_for_discrete(in_df:pd.DataFrame, out_df:pd.DataFrame, cur_table_name:str, rel_col:str, target_col:str, labels:list[str], seq:int, type:str):
        discrete_so_path = os.path.join(udf_path, 'lib', 'udf_discrete.so')
        reg_udf_cut = f"""
CREATE OR REPLACE FUNCTION discrete_cut(input cut_input_{str(seq)}[], labels text[]) RETURNS cut_output_{str(seq)}[]
AS '{discrete_so_path}', 'discrete_cut'
LANGUAGE C STRICT;"""
        reg_udf_qcut = f"""
CREATE OR REPLACE FUNCTION discrete_qcut(input cut_input_{str(seq)}[], labels text[]) RETURNS cut_output_{str(seq)}[]
AS '{discrete_so_path}', 'discrete_qcut'
LANGUAGE C STRICT;"""
        
        udf_name = "discrete_cut" if type == DiscretizeTypeEnum.CUT else "discrete_qcut"
        sql_type = ''
        tmp, in_attrs = df_to_sqltype(in_df, 'cut_input_%s' %(seq), target_col=rel_col)
        sql_type += tmp
        
        tmp, out_attrs = df_to_sqltype(out_df, 'cut_output_%s' %(seq), target_col=[rel_col,target_col])
        sql_type += tmp
        
        tmp_tb_name = "tmp_discrete_" + str(seq)
        call_udf = "select (%s(array(select row(%s)::cut_input_%s from %s), ARRAY[%s])) as cut" %(udf_name, ','.join(in_attrs), str(seq), cur_table_name, ','.join(list(map(lambda x: "'"+str(x)+"'", labels))))
        call_udf2 = "select (unnest(cut)).* from %s" %(tmp_tb_name)
        
        if type == DiscretizeTypeEnum.CUT:
            return sql_type + reg_udf_cut, (call_udf, call_udf2), (tmp_tb_name, "")    
        else:
            return sql_type + reg_udf_qcut, (call_udf, call_udf2), (tmp_tb_name, "")
    
    def set_warmup_udf(udf_file_path:str, import_code:list[str]) -> None:
        """
        set the warm up udf
        """
        with open(udf_file_path, 'a') as f:
            f.write(prefix_warm)
            f.write('    ' + '\n    '.join(import_code))
            f.write(postfix_sep)
            f.write("SELECT warm_udf();\n")
        