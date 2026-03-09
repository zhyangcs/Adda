import ast
import sys
from src.pg.check_transformer import CheckTransformer
from src.pg.add_pandas_transformer import AddPandasTransformer
from inspect import cleandoc
import pandas as pd
from src.pg.sql_utils import get_conn, next_cte_name
from src.pg.py_to_udf import Py2Udf
from src.pg.sql_reformat import SQLFormater
from src.pg.func_utils import *
from src.pg.op_type import OpType, OpTypeEnum
from src.pg.py_to_sql import Py2Sql
from src.pg.add_parent_transformer import AddParentTransformer
from src.pg.dag_util import *
import copy
from src.env import *

class PythonPolisher:
    script_scope = {}

    def __init__(self, table_name_prefix: str, target_col, variable_name: str, pipes, dir_path, extra_step, attr_num, pipeCtor, id_col: str = "id", total_num: int = 1000, do_optimize: int = 0, task_type:str = "classify", use_py_train_pred:bool = False, model_type:str = "CART"):
        """
        0: do all optimization
        1: not do operator combination
        2: not do udf split
        3. not do cte combination
        """
        self.df_name = variable_name
        self.tb_prefix = table_name_prefix
        self.total_num = total_num
        self.include_train = False
        self.include_predict = False
        self.id_col = id_col
        self.target_col = target_col
        self.do_optimize = do_optimize
        self.task_type = task_type
        self.use_py_train_pred = use_py_train_pred
        self.model_type = model_type
        
        self.pipes = pipes
        self.extra_step = extra_step
        self.dir_path = dir_path
        self.attr_num = attr_num
        self.DagCons = []
        self.import_codes = []
        self.pipeCtor = pipeCtor
        self.speed_record = {"sql": [], "pd_train": [], "combine_op": [], "sql_num": []}
        
        self.nodeid2OpTypeEnum = dict()
        self.topk_record = dict()
    
    def check_code(self, code: str, node_id: int, script_scope) -> bool:
        """
        NOTE: this is the demo version of checking, just to running the whole pipeline
        check rule: if code contains function of library instead of the pandas, or contains the apply function in pandas, then check fail
        """
        addparenttransformer = AddParentTransformer()
        print(code + "\n ------------ \n")
        checktransformer = CheckTransformer(script_scope)
        cur_ast = ast.parse(code)
        
        # print(ast.dump(cur_ast, indent=4))
        
        # first add the relation betweent parent and the child, then do the visit
        # print(code)
        addparenttransformer.visit(cur_ast)
        checktransformer.visit(cur_ast)
        
        self.nodeid2OpTypeEnum[node_id] = checktransformer.op_type.op_type
        
        return copy.copy(checktransformer.op_type)

    def add_code_fill_pandas(self, code: str) -> str:
        """
        visit the ast to find all the attributes which pandas indexed, and readd the missing attribute
        why? because the inspect.module need all of the attr
        """
        add_pandas_transformer = AddPandasTransformer(self.df_name)
        cur_ast = ast.parse(code)
        # print(ast.dump(cur_ast, indent=4))
        add_pandas_transformer.visit(cur_ast)
        attrs = add_pandas_transformer.get_attrs()
        add_code = cleandoc("""
        column_to_add = [%s]
        for col in column_to_add:
            if col not in %s.columns:
                %s[col] = 1
        """ % (','.join(list(map(lambda x: "'"+x+"'", attrs))), self.df_name, self.df_name))
        # print(attrs)
        whole_code = code + '\n' + add_code
        return '\n'.join(attr_to_lower_case(whole_code.split("\n"), attrs)), attrs

    def get_finally_df(self, python_path) -> pd.DataFrame:
        """
        exec the original code and get the finally variable
        """
        full_code = get_python_code(python_path)
        total_namespace = {}
        exec(''.join(full_code), total_namespace)
        return total_namespace[self.df_name]   
    

    def polish_code(self) -> str:
        """
        polish the code
        extra step: 0 do nothing, 1 train the model, 2 predict from the model
        """
        # 安全检查：确保所有pipes都有有效的code_path
        for idx, pipe in enumerate(self.pipes):
            if pipe is None:
                print(f"Warning: Pipe {idx} is None, skipping")
                continue

            if not hasattr(pipe, 'code_path') or not pipe.code_path:
                print(f"Warning: Pipe {idx} has no valid code_path, skipping")
                self.pipes[idx] = None  # 标记为无效
                continue

            if not os.path.exists(pipe.code_path):
                print(f"Warning: Code path {pipe.code_path} does not exist for pipe {idx}, skipping")
                self.pipes[idx] = None  # 标记为无效
                continue

        # 过滤掉None pipes
        self.pipes = [pipe for pipe in self.pipes if pipe is not None]
        self.DagCons = [dc for dc in self.DagCons if dc is not None]

        if not self.pipes:
            raise Exception("没有有效的特征管道可用于代码优化。所有管道都无效或不存在。")

        for idx, pipe in enumerate(self.pipes):
            try:
                origin_exec_namespace = {}
                new_exec_namespace = {}

                # 0. do some reformat to the origin code
                shorten_var(pipe.code_path, self.df_name)
                add_type_change_drop(pipe.code_path, self.df_name, self.extra_step)
                full_code = get_python_code(pipe.code_path)
                code_for_script_scope, rel_attrs = self.add_code_fill_pandas(''.join(full_code))
                full_code = attr_to_lower_case(full_code, rel_attrs)
                
                import_code = grab_import(full_code)
                self.script_scope = get_script_scope(code_for_script_scope)

                # 1. check the code for the udf block
                pre_code, code_block, node_id_list, high_order_idxs = split_code_for_comment(full_code, "# task desc: ", self.tb_prefix, self.df_name)

                print("len of code block", len(code_block))
                print(code_block)

                # 2. check the code
                # op_list = list(map(lambda x, y: self.check_code(x, y), code_block, node_id_list))
                op_list = []
                check_script_scope = get_script_scope(pre_code)
                for cidx, (code, node_id) in enumerate(zip(code_block, node_id_list)):
                    # could_sqlization = check_SQLization(code, check_df)
                    # op_type = self.check_code(code, self.script_scope) if could_sqlization else OpType(OpTypeEnum.UNSUPPORT)
                    try:
                        check_df_wrapper(code, check_script_scope)
                        is_binary = True
                    except Exception as e:
                        is_binary = False
                    if "drop" not in code:
                        exec(code, check_script_scope)
                    op_type = self.check_code(code, node_id, check_script_scope)
                    if "drop" in code:
                        exec(code, check_script_scope)
                    if not is_binary and op_type.op_type == OpTypeEnum.BINARY:
                        op_type.op_type = OpTypeEnum.UNSUPPORT
                    
                    op_list.append(op_type)
                    self.nodeid2OpTypeEnum[node_id] = op_type.op_type
                    print(termcolor.colored("op_type: %s" % (op_type.op_type), "yellow"))
                    
                if self.do_optimize != 1:
                    pre_op_num = len(op_list)
                    op_list, code_block = combine_code_block(op_list, code_block)
                    post_op_num = len(op_list)
                    self.speed_record['combine_op'].append((pre_op_num, post_op_num))
                
                # 2.2 optimize the pipeline
                do_cte_combine = (self.do_optimize != 3)
                DagCons = DagConstructor(self.df_name, self.model_type, pre_code, code_block, op_list, self.tb_prefix, self.target_col, self.id_col, pipe, self.task_type, do_cte_combine=do_cte_combine, use_py_train_pred=self.use_py_train_pred)
                # set the msg for reuse in this step
                DagCons.construct_pipeline()
                
                self.DagCons.append(DagCons)
                self.import_codes.append(import_code)
            except Exception as e:
                print(f"error pipe: {e}")
                # delete the current pipe as it could not be parsed
                self.pipes[idx] = None
                self.DagCons.append(None)
    
    def generate_sql(self):
        """
        generate sql, validate all the feature sets, choose one
        """
        # check to be shrink
        self.pipes = list(filter(lambda x: x is not None, self.pipes))
        self.DagCons = list(filter(lambda x: x is not None, self.DagCons))
        
        # set the reuse info & print the pipe info
        for i in range(len(self.pipes)):
            self.DagCons[i].set_reuse_info()
            print(f"pipe_{i}: {self.pipes[i].get_pipe_str()}")
        # 1. generate the pipelines and choose the best one
        for idx, pipe in enumerate(self.pipes):
            if self.do_optimize != 2:
                self.DagCons[idx].optimize_pipeline()
                
            if not self.use_py_train_pred:
                # create the relevant dir
                dir_path = os.path.join(self.dir_path, f"pipe_valid_{idx}")
                udf_file_path = os.path.join(dir_path, "spudf.sql")
                sql_file_path = os.path.join(dir_path, "spsql.sql")
                sql_files = [udf_file_path, sql_file_path]
                init_files([dir_path], sql_files)
                self.DagCons[idx].bfs_dag(PipeTypeEnum.VALIDATE, sql_file_path, udf_file_path, self.import_codes[idx], self.total_num)
                try:
                    self.print_exec_time(sql_files, pipe, False)
                except Exception as e:
                    # pipeline would fail because of handling the doulble division or some corner case
                    print(f"pipeline error during execution: {e}, we drop the pipeline")
                    self.pipes[idx] = None
                    self.DagCons[idx] = None
            
        # 2. generate the model of the best pipeline 
        scores = []
        if not self.use_py_train_pred:   
            for idx, pipe in enumerate(self.pipes):
                if pipe == None:
                    continue
                cursor = get_conn().cursor()
                cursor.execute(f"SELECT data FROM {self.tb_prefix}{str(pipe.pipe_id)} limit 1")
                scores.append(cursor.fetchone()[0])
                
            if len(scores) == 0:
                return [], [], []
            best_pipe_idx = scores.index(max(scores))
        else:
            cursor = get_conn().cursor()
            # delete_sql = f"delete from model_table where tb_name = '{self.tb_prefix}' and model_type = '{self.model_type}'"
            delete_sql = f"""
            DO $$ 
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'model_table') THEN
                    DELETE FROM model_table WHERE tb_name = '{self.tb_prefix}' AND model_type = '{self.model_type}';
                END IF;
            END $$;
            """
            print(delete_sql)
            cursor.execute(delete_sql)
            scores = [0] * len(self.pipes)
            best_pipe_idx = [i for i in range(len(self.pipes))]

        print(termcolor.colored(f"All Score is {scores}, best pipe idx: {best_pipe_idx}", "yellow"))
        # currently we get all the result for experiments
        auc_result = []
        for best_pipe_idx in range(len(self.pipes)):
            if self.pipes[best_pipe_idx] == None:
                continue
            dir_path = os.path.join(self.dir_path, f"pipe_train_{best_pipe_idx}")
            sql_file_path = os.path.join(dir_path, "spsql.sql")
            udf_file_path = os.path.join(dir_path, "spudf.sql")
            sql_files = [udf_file_path, sql_file_path]
            init_files([dir_path], sql_files)
            # clear the reuse msg of pipe
            self.DagCons[best_pipe_idx].bfs_dag(PipeTypeEnum.TRAIN, sql_file_path, udf_file_path, self.import_codes[best_pipe_idx], self.total_num, reuse=False)
            self.print_exec_time(sql_files, self.pipes[best_pipe_idx], True)
            self.speed_record['sql_num'].append(self.DagCons[best_pipe_idx].total_sql_num)

            # 3. do prediction
            dir_path = os.path.join(self.dir_path, f"pipe_predict_{best_pipe_idx}")
            sql_file_path = os.path.join(dir_path, "spsql.sql")
            udf_file_path = os.path.join(dir_path, "spudf.sql")
            sql_files = [udf_file_path, sql_file_path]
            init_files([dir_path], sql_files)
            self.DagCons[best_pipe_idx].bfs_dag(PipeTypeEnum.PREDICT, sql_file_path, udf_file_path, self.import_codes[best_pipe_idx], self.total_num)
            self.print_exec_time(sql_files, self.pipes[best_pipe_idx])
            
            # 4. get the final roc_auc answer
            auc_result.append(self.get_final_auc(best_pipe_idx))
            
            print(termcolor.colored(f"Final valid and test score: {auc_result[-1]}", "yellow"))
            break
        
        # test the topk records
        if not scores:
            return [], [], 0.0
            
        return scores, auc_result, auc_result[scores.index(max(scores))] 
    
    def generate_topk(self):
        # check to be shrink
        self.pipes = list(filter(lambda x: x is not None, self.pipes))
        self.DagCons = list(filter(lambda x: x is not None, self.DagCons))
        
        # set the reuse info & print the pipe info
        for i in range(len(self.pipes)):
            self.DagCons[i].set_reuse_info()
            print(f"pipe_{i}: {self.pipes[i].get_pipe_str()}")
        # 1. generate the pipelines and choose the best one
        for idx, pipe in enumerate(self.pipes):
            if self.do_optimize != 2:
                self.DagCons[idx].optimize_pipeline()

            # create the relevant dir
            dir_path = os.path.join(self.dir_path, f"pipe_valid_{idx}")
            udf_file_path = os.path.join(dir_path, "spudf.sql")
            sql_file_path = os.path.join(dir_path, "spsql.sql")
            
            sql_files = [udf_file_path, sql_file_path]
            init_files([dir_path], sql_files)
            self.DagCons[idx].bfs_dag(PipeTypeEnum.VALIDATE, sql_file_path, udf_file_path, self.import_codes[idx], self.total_num)
            try:
                self.print_exec_time(sql_files, pipe, False)
            except Exception as e:
                # pipeline would fail because of handling the doulble division or some corner case
                print(f"pipeline error during execution: {e}, we drop the pipeline")
                self.pipes[idx] = None
                self.DagCons[idx] = None
            
        # 2. generate the model of the best pipeline 
        scores = []
        for idx, pipe in enumerate(self.pipes):
            if pipe == None:
                continue
            cursor = get_conn().cursor()
            cursor.execute("SELECT data FROM %s limit 1" % (f"{self.tb_prefix}{str(pipe.pipe_id)}"))
            scores.append(cursor.fetchone()[0])
            
        best_pipe_idx = scores.index(max(scores))
        # currently we get all the result for experiments
        auc_result = []
        for best_pipe_idx in range(len(self.pipes)):
            if self.pipes[best_pipe_idx] == None:
                continue
            print(termcolor.colored(f"All Score is {scores}, best pipe idx: {best_pipe_idx}", "yellow"))
            dir_path = os.path.join(self.dir_path, f"pipe_train_{best_pipe_idx}")
            sql_file_path = os.path.join(dir_path, "spsql.sql")
            udf_file_path = os.path.join(dir_path, "spudf.sql")
            sql_files = [udf_file_path, sql_file_path]
            init_files([dir_path], sql_files)
            # clear the reuse msg of pipe
            self.DagCons[best_pipe_idx].bfs_dag(PipeTypeEnum.TRAIN, sql_file_path, udf_file_path, self.import_codes[best_pipe_idx], self.total_num, reuse=False)
            self.print_exec_time(sql_files, self.pipes[best_pipe_idx], True)
            self.speed_record['sql_num'].append(self.DagCons[best_pipe_idx].total_sql_num)

            # 3. do prediction
            dir_path = os.path.join(self.dir_path, f"pipe_predict_{best_pipe_idx}")
            sql_file_path = os.path.join(dir_path, "spsql.sql")
            udf_file_path = os.path.join(dir_path, "spudf.sql")
            sql_files = [udf_file_path, sql_file_path]
            init_files([dir_path], sql_files)
            self.DagCons[best_pipe_idx].bfs_dag(PipeTypeEnum.PREDICT, sql_file_path, udf_file_path, self.import_codes[best_pipe_idx], self.total_num)
            # self.print_exec_time(sql_files, self.pipes[best_pipe_idx])
            
            # 4. get the final roc_auc answer
            auc_result.append(self.get_final_auc(best_pipe_idx))
        
        # test the topk records for 1~6
        for k in range(1, len(scores)+1):
            index = scores[:k].index(max(scores[:k]))
            self.topk_record[k] = auc_result[index]
        return self.topk_record
        
    def generate_sql_simple(self, do_opt:bool=False):
        """
        Simply generate the corresponding sqls without execution
        """
        self.pipes = list(filter(lambda x: x is not None, self.pipes))
        self.DagCons = list(filter(lambda x: x is not None, self.DagCons))
        
        for idx in range(len(self.pipes)):
            if do_opt:
                self.DagCons[idx].optimize_pipeline()
            self.DagCons[idx].bfs_dag(PipeTypeEnum.NOTHING, os.path.join(self.dir_path, "spsql/sql"), os.path.join(self.dir_path, "spudf.sql"), self.import_codes[idx], self.total_num, concrete_time=True)
        
    def print_exec_time(self, sql_files, pipe, add_to_record:bool = False):
        # print the relevant msg
        print(termcolor.colored("-------------------pipe_"+str(pipe.pipe_id)+"-------------------", "grey"))
        conn = get_conn()
        repeat_time = 1 if add_to_record == False else 2
        # use this to warm up some necessary library
        exec_several_times(exec_sql_files, repeat_time, sql_files, conn)
        sql_time = exec_several_times(exec_sql_files, repeat_time, sql_files, conn)
        # python_time = exec_several_times(self.get_exec_time_include_train, 1, pipe.code_path)
        print("sql time: ", sql_time)
        
        # print("pd time with train: ", python_time)
        if add_to_record:
            self.speed_record["sql"].append(sql_time)
            # self.speed_record["pd_train"].append(python_time)
        # print("pd time with output: ", exec_several_times(self.get_exec_time_except_train, 1, pipe.code_path))
        # print("pd time without output: ", exec_several_times(self.get_exec_time_without_output, 1, pipe.code_path))
        print(termcolor.colored("-----------------------------------------------", "grey"))
        
    def get_exec_time_include_train(self, python_path):
        if self.target_col is None:
            raise Exception("target_col is None")
        code = get_reformatted_code(get_python_code(python_path), self.df_name, self.tb_prefix, self.target_col, task_type=self.task_type)
        with open(python_path[:-3]+"_new.py", 'w') as f:
            f.write("".join(code))
        return exec_time("".join(code))
    
    def get_exec_time_except_train(self, python_path):
        python_code = get_reformatted_code(get_python_code(python_path), self.df_name, self.tb_prefix, self.target_col, 0, False)
        output_path = os.path.join(test_save_path, "combined_new.csv")
        add_code = '\n' + cleandoc(f"""
        {self.df_name}.to_csv('{output_path}', index=False)
        """) + '\n'
        return exec_time("".join(python_code)+add_code)

    def get_exec_time_without_output(self, python_path):
        python_code = get_reformatted_code(get_python_code(python_path), self.df_name, self.tb_prefix, self.target_col, 0, False)
        # print(python_code)
        return exec_time("".join(python_code))
    
    def get_precise_staged_time(self, python_path, is_train:bool = False):
        python_code = get_reformatted_code(get_python_code(python_path), self.df_name, self.tb_prefix, self.target_col, 0, False)
        # python_code = self.get_exec_time_without_output(python_path)
        if is_train:
            output_path = os.path.join(test_save_path, "model.pkl")
            add_code = '\n' + cleandoc(f"""
            import lightgbm as lgb
            import pickle
            model = lgb.LGBMRegressor()
            y = {self.df_name}['{self.target_col}']
            X = {self.df_name}.drop(columns=['{self.target_col}'])
            model.fit(X, y)
            pickle.dump(model, open('{output_path}', 'wb'))
            """)+ '\n'
        else:
            output_path = os.path.join(test_save_path, "combined_new.csv")
            add_code = '\n' + cleandoc(f"""
            {self.df_name}.to_csv('{output_path}', index=False)
            """) + '\n'
        python_code.append(add_code)
        point_code = add_break_point(python_code)
        return get_staged_exec_time("".join(point_code))
    
    def get_precise_staged_time_sql(self, udfpath, sqlpath, noopsqlpath, conn):
        full_time, noop_time, load_time = 0, 0, 0
        for i in range(10):
            # full execution
            sqlfiles = [udfpath, sqlpath]
            full_time += exec_sql_files(sqlfiles, conn)
            
            # noop execution
            sqlfiles = [udfpath, noopsqlpath]
            noop_time += exec_sql_files(sqlfiles, conn)
            
            # load time
            sql = "EXPLAIN ANALYZE SELECT * FROM %s" % (self.tb_prefix)
            load_time += exec_sqls([sql], conn)[0]
        full_time, noop_time, load_time = full_time/10, noop_time/10, load_time/10
        
        return [load_time, noop_time - load_time, full_time - noop_time]

    def check_feature_correctness(self):
        for idx, pipe in enumerate(self.pipes):
            dir_path = f"{self.dir_path}/pipe_{idx}"
            # 1. grab the df from the sql by exec the spsql_notrain.sql
            conn = get_conn()
            udf_path = "%s/spudf.sql" % (dir_path)
            no_train_sql_path = "%s/spsql_notrain.sql" % (dir_path)
            sqlfiles = [udf_path, no_train_sql_path]
            exec_sql_files(sqlfiles, conn)
            
            df_sql = pd.read_sql("SELECT * FROM %s" % (f"{self.tb_prefix}{idx}_notrain"), conn)
            
            # 2. grab the df from the python by exec the python code
            python_path = pipe.code_path
            df_python = self.get_finally_df(python_path)
            
            print(termcolor.colored(f"differnt col is: {check_similar(df_sql, df_python)}", "red"))

    def get_final_auc(self, idx):
        df_sql = pd.read_sql(f"SELECT * FROM {self.tb_prefix}{idx}predict", get_conn())

        return df_sql['data'][0]