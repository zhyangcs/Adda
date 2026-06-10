import os
import pandas as pd
import psycopg2
from pandas.testing import assert_frame_equal
import time
import threading
from inspect import cleandoc
import termcolor
from src.pg.add_parent_transformer import *
from src.pg.check_transformer import *
from src.pg.func_utils import *
from src.env import *

def exec_sql_files(sqlfiles: list[str], conn) -> time:
    cursor = conn.cursor()
    for sqlfile in sqlfiles:
        with open(sqlfile, 'r') as f:
            sql = f.read()
            # print(sql)
            if sql != "":
                t1 = time.time()
                cursor.execute(sql)
                # conn.commit()
                t2 = time.time()
                lastt = t2 - t1
    cursor.close()
    conn.commit()
    return lastt

def exec_several_times(func, times:int, *args):
    wholet = 0
    for i in range(times):
        wholet += func(*args)
    return wholet/times
    
def exec_sql_file_parallel(sqlfiles: list[str]) -> time:
    threads = []
    sqls = []
    connpool = [get_conn() for i in range(len(sqlfiles))]
    ts = []
    for sqlfile in sqlfiles:
        with open(sqlfile, 'r') as f:
            sql = f.read()
            if sql != "":
                sqls.append(sql)
    def exec_sql_file(sql, conn, seq):
        t1 = time.time()
        cursor = conn.cursor()
        cursor.execute(sql)
        t2 = time.time()
        cursor.close()
        conn.commit()
        ts.append(t2 - t1)
        print("thread %d finished %f" % (seq, t2-t1))
        return 
    
    for idx, (sql, conn) in enumerate(zip(sqls, connpool)):
        t = threading.Thread(target=exec_sql_file, args=(sql, conn, idx))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
      
    return max(ts)

def exec_sql_file_parallel_ck(sqls: list[str]) -> time:
    threads = []
    # sqls = []
    connpool = [get_conn_ck() for i in range(len(sqls))]
    ts = []
    # for sqlfile in sqlfiles:
    #     with open(sqlfile, 'r') as f:
    #         sql = f.read()
    #         if sql != "":
    #             sqls.append(sql)
    def exec_sql_file(sql, client, seq):
        t1 = time.time()
        client.execute(sql)
        t2 = time.time()
        ts.append(t2 - t1)
        print("thread %d finished %f" % (seq, t2-t1))
        return 
    
    for idx, (sql, conn) in enumerate(zip(sqls, connpool)):
        t = threading.Thread(target=exec_sql_file, args=(sql, conn, idx))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
      
    return max(ts)

def exec_sqls(sqls: list[str], conn) -> list:
    tlist = []
    cursor = conn.cursor()
    for sql in sqls:
        # print(termcolor.colored(sql, "green"))
        if sql != "":
            t1 = time.time()
            cursor.execute(sql)
            t2 = time.time()
            tlist.append(t2-t1)
    cursor.close()
    conn.commit()
    return tlist


def get_df_from_table(table_name: str, conn) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM %s" % (table_name), conn)
    return df


def check_same_df(df1: pd.DataFrame, df2: pd.DataFrame, var: str) -> bool:
    if df1.shape != df2.shape:
        return False
    if set(df1.columns) != set(df2.columns):
        return False

    # return df1.equals(df2)
    for col in df1.columns:
        if df1[col].dtype != df2[col].dtype:
            print(col, df1[col].dtype, df2[col].dtype)
    # convert the bool type to object in df1 and df2
    for col in df1.columns:
        if df1[col].dtype == 'object':
            df1[col] = df1[col].astype('str')
    for col in df2.columns:
        if df2[col].dtype == 'object':
            df2[col] = df2[col].astype('str')

    columns_order = list(df1.columns)
    df1 = df1[columns_order].sort_values(
        by=list(df1.columns)).reset_index(drop=True)
    df2 = df2[columns_order].sort_values(
        by=list(df1.columns)).reset_index(drop=True)

    # if find the placeholder, just skip it
    # for col in df1.columns:
    #     for i in range(len(df1[col])):
    #         if df1[col][i] == var:
    #             df1[col][i] = df2[col][i]

    assert_frame_equal(df1, df2, check_dtype=False, check_exact=False)
    print("pass the assert in the check_same_df")
    return True


def get_conn() -> psycopg2.extensions.connection:
    """
    just for the convience of the testing
    """
    conn = psycopg2.connect(
        dbname=pg_db,
        user=pg_user,
        password=pg_password,
        host=pg_host,
        port=pg_port,
    )
    return conn

def get_conn_pgml():
    conn = psycopg2.connect(dbname="postgresml", user="postgresml", port=5433)
    return conn


def next_cte_name(table_name: str) -> str:
    """
    make a rule for the generation of cte: 
    * original_name --> cte0 --> cte1 --> ...
    """
    if not table_name.startswith("cte"):
        return "cte0"
    return "cte" + str(int(table_name[3:]) + 1)

def get_exec_plan(sql: str, conn) -> str:
    """
    get the exec plan of the sql
    """
    cursor = conn.cursor()
    cursor.execute("EXPLAIN ANALYZE" + sql)
    rows = cursor.fetchall()
    cursor.close()
    return rows[0][0]

def check_code(code:str, script_scope):
    """
    NOTE: this is the demo version of checking, just to running the whole pipeline
    check rule: if code contains function of library instead of the pandas, or contains the apply function in pandas, then check fail
    """
    addparenttransformer = AddParentTransformer()
    checktransformer = CheckTransformer(self_copy(script_scope))
    
    cur_ast = ast.parse(code)
    addparenttransformer.visit(cur_ast)
    checktransformer.visit(cur_ast)
    
    return copy.copy(checktransformer.op_type)

def check_df_wrapper(code:str, script_scope):
    """
    check whether the binary code could be execute on the pandas to sql without exception
    """
    new_code = wrapper_code_for_pd2sql(code, "tmp", "tmp", "df", "id")
    exec(new_code, self_copy(script_scope))
    # if no exception happen, then return
    return 

def check_SQLization(code:str, df:pd.DataFrame):
    """
    1. could be parse to one of the type
    2. if parse to binary, then could be execute without exception
    """
    try:
        script_scope = get_script_scope("")
        script_scope["df"] = df
        # if op_type.op_type == OpTypeEnum.BINARY:
        check_df_wrapper(code, script_scope)
        # print(termcolor.colored(f"Check pass: {op_type.op_type}", "green"))
        is_binary = True
    except Exception as e:
        is_binary = False
    try:        
        op_type = check_code(code, script_scope)
        is_other = op_type.op_type != OpTypeEnum.BINARY
    except Exception as e:
        is_other = False
    
    print(termcolor.colored(f"SQLization Check pass: {is_binary} and {is_other}", "green"))
    return is_binary or is_other

def wrapper_code_for_pd2sql(code:str, in_table:str, out_var:str, var:str, id_col:str):
    """
    wrap the code with the pandas_to_sql library to generate the sql from the wrapper variable
    """
    new_code = "from pandas_to_sql import wrap_df\n"
    new_code += ("%s = wrap_df(%s, '%s', '%s')\n" % (var, var, in_table, id_col)) + code
    new_code += "\n" + cleandoc("""
%s = %s.get_sql_string()\n
    """ % (out_var, var))
    # self.cur_table_name = self.next_cte_name(self.cur_table_name)
    # print(new_code)
    return new_code

def type_to_GetDatumFunc(type_name: str) -> str:
    """
    convert the type name to the GetDatumFunc
    """
    if type_name == "int":
        return "Int4GetDatum"
    elif type_name == "int64":
        return "Int8GetDatum"
    elif type_name == "float":
        return "Float4GetDatum"
    elif type_name == "double":
        return "Float8GetDatum"
    elif type_name == "bool":
        return "BoolGetDatum"
    elif type_name == "str":
        return "CStringGetDatum"
    else:
        raise Exception("unknown type name %s" % (type_name))
    
def type_to_FromDatumFunc(type_name: str) -> str:
    """
    convert the type name to the FromDatumFunc
    """
    if type_name == "int":
        return "DatumGetInt32"
    elif type_name == "int64":
        return "DatumGetInt64"
    elif type_name == "float":
        return "DatumGetFloat4"
    elif type_name == "double":
        return "DatumGetFloat8"
    elif type_name == "bool":
        return "DatumGetBool"
    elif type_name == "str":
        return "DatumGetCString"
    else:
        raise Exception("unknown type name %s" % (type_name))

def df_to_sqltype(df:pd.DataFrame, typename:str, target_col = None, id_col = None) -> (str, list[str]):
    """
    convert the pandas dataframe to the postgresql data type
    """
    attr_names = []
    drop_sql = "DROP TYPE IF EXISTS %s cascade;\n" % (typename)
    type_sql = "CREATE TYPE %s AS (\n" % (typename)
    cols = df.columns.tolist()
    print(cols)
    # set the target col to the end of the cols
    if target_col != None: 
        if type(target_col) == str:
            if target_col in cols:
                cols.remove(target_col)
                cols = cols + [target_col]
        elif type(target_col) == list:
            for col in target_col:
                if col in cols:
                    cols.remove(col)
                    cols = cols + [col]
    # set the id col to the begin of the cols
    if id_col != None:
        if id_col in cols:
            cols.remove(id_col)
            cols = [id_col] + cols
    for col in cols:
        type_sql += "    %s %s,\n" % (col, pd_to_sqltype(df[col]))
        attr_names.append(col)
    type_sql = type_sql[:-2] + "\n);\n"
    return drop_sql + type_sql, attr_names

def pd_to_sqltype(series:pd.Series) -> str:
    """
    convert the pandas series to the postgresql data type
    """
    if series.dtype == 'int64':
        return 'int8'
    elif series.dtype == 'float64':
        return 'float8'
    elif series.dtype == 'bool':
        return 'bool'
    elif series.dtype == 'object' or series.dtype == 'category':
        return 'text'
    else:
        raise Exception("Not support the type: %s" % (series.dtype))


def get_for_category_col(tb_name:str, attr_name:str, conn) -> list:
    """
    get all the distinct value from the attribute in table
    """
    sql = "SELECT DISTINCT %s FROM %s" % (attr_name, tb_name)
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
        return list(map(lambda x: x[0], rows))
    except psycopg2.Error as e:
        print("Maybe the table do not have this attribute")
        print("Error occur when execute the sql: %s for %s" % (sql, e))
    
    return []
    
    