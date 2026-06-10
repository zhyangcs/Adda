from src.pg.sql_utils import *
from src.pg.import_table import *
from src.pg.compile_utils import *
from src.pg.func_utils import *
from src.env import *

# The Default value in the postgresql.conf
cpu_operator_cost = 0.0025 
cpu_tuple_cost = 0.01  
io_cost_per_byte = 1/(8*1024) 
work_mem = 512 * 1024 * 1024
cost_estimation_table = "cost_est_tb"

estimate_template = """
explain analyze with cte_1 as(
    select * from {cost_estimation_table} limit {row_num}
) {core_sql};
"""

def acquire_alpha_for_wrapper(num_of_attr: int, row_num)->float:
    """
    register an function for testing the speed of udf for wrapper and unwrapper for the udf
    cost of select: (row_num * cpu_tuple_cost) + (row_num * table_width * io_cost_per_byte)
    cost of udf: (row_num * cpu_tuple_cost) + (row_num * table_width * io_cost_per_byte) * alpha
    alpha = ((cost of udf - cost of select) / (row_num * table_width *io_cost_per_byte)) + 1 
            ≈ ((cost of udf - cost of select) / cost of select) + 1 = cost of udf / cost of select
    """
    row_num = min(row_num, 10000)
    compile_udf(os.path.join(udf_path, "code", "udf_nothing.cpp"), os.path.join(udf_path, "lib", "udf_nothing.so"))
    csv_path = os.path.join(test_save_path, "test_udf.csv")
    udf_name = "do_nothing"
    tb_name = cost_estimation_table
    reg_udf = f"""CREATE OR REPLACE FUNCTION {udf_name}(input test_udf_param[]) RETURNS test_udf_param[]
AS '{udf_path}/lib/udf_nothing.so', 'udf_nothing'
LANGUAGE C STRICT;\n"""
    
    # generate an df for the testing with num_of_attr attributes, with all of its attributes are int
    df = pd.DataFrame(columns=["attr%d" % (i) for i in range(num_of_attr)])
    for col in df.columns:
        df[col] = df[col].astype('float')
    last_col = f"attr{num_of_attr-1}"
    df[last_col] = df[last_col].astype('object')
    
    largedf = generate_fake_data(df, row_num)
    largedf.to_csv(csv_path, index=False)
    
    conn = get_conn()
    csv2tb(csv_path, tb_name, conn)
    type_sql, in_attr = df_to_sqltype(df, "test_udf_param")
    call_udf = """
explain analyze with cte as(
    SELECT %s(array(SELECT row(%s)::test_udf_param FROM %s)) as tmp
) select (unnest(tmp)).* from cte;    
    """ % (udf_name, ", ".join(in_attr), tb_name)
    print(call_udf)
    
    # test the avg alpha
    alpha_ret = 0
    udf_time_ret = 0 
    retest_time = 5
    for i in range(retest_time):
        # 1. testing the speed of the udf
        udf_tlist = exec_sqls([type_sql, reg_udf, call_udf], conn)
        
        # 2. testing the speed not has the wrapper
        noudf_tlist = exec_sqls(["explain analyze SELECT * from %s;" %(tb_name)], conn)
        
        # print(udf_tlist, noudf_tlist, num_of_attr)
        alpha_ret += udf_tlist[-1] / noudf_tlist[-1]
        udf_time_ret += udf_tlist[-1]
    return alpha_ret / retest_time, udf_time_ret / retest_time
    
def estimate_hash_join_cost(df1:pd.DataFrame, df2:pd.DataFrame):
    table1_width = pd_to_width(df1)
    table2_width = pd_to_width(df2)
    # memory_needed = table1_rows * table1_width

    # # if memory_needed > work_mem:
    # #     io_cost = (memory_needed - work_mem) * io_cost_per_byte
    # # else:
    # #     io_cost = 0
    # io_cost = memory_needed * io_cost_per_byte # cost of data flow
    # cpu_cost = ((table1_rows + table2_rows) * cpu_operator_cost) + ((table1_rows + table2_rows) * cpu_tuple_cost)
    
    memory_needed = table1_width
    io_cost = memory_needed * io_cost_per_byte # cost of data flow
    cpu_cost = (2 * cpu_operator_cost) + (2 * cpu_tuple_cost)
    total_cost = cpu_cost + io_cost

    return total_cost

def estimate_udf_cost(df:pd.DataFrame):
    """
    estimate the cost of the udf (the final cost should multiply with row_count)
    """
    alpha, _ = acquire_alpha_for_wrapper(df.shape[1], df.shape[0])
    
    table_width = pd_to_width(df)
    # cpu_cost = table_rows * cpu_tuple_cost
    # io_cost = table_rows * table_width * io_cost_per_byte
    cpu_cost = cpu_tuple_cost
    io_cost = table_width * io_cost_per_byte
    
    total_cost = (cpu_cost + io_cost) * alpha
    return total_cost

def pd_to_width(df:pd.DataFrame) -> int:
    """
    compute the store bytes for a tuple in pg 
    """
    width = 0
    for col in df.columns:
        if df[col].dtype == 'int64':
            width += 8
        elif df[col].dtype == 'float64':
            width += 8
        elif df[col].dtype == 'bool':
            width += 1
        elif df[col].dtype == 'object' or df[col].dtype == 'category':
            width += 100
        else:
            raise Exception("Not support the type: %s" % (df[col].dtype))
    return width

def construct_fake_df(num_of_attr:int):
    df = pd.DataFrame(columns=["attr%d" % (i) for i in range(num_of_attr)])
    for col in df.columns:
        df[col] = df[col].astype('float')
    df['attr10'] = df['attr10'].astype('object')
    # insert 1000000(10^6) rows
    largedf = generate_fake_data(df, 1000000)
    importTable_df(largedf, cost_estimation_table, get_conn())

def estimate_operator(row_num:int, num_of_attr:int):
    sqls_map = dict()
    
    # we could straightly use the alpha to estimate this two cost(not considering the inner computation)
    # alpha * (time of straight select)
    _, udf_time = acquire_alpha_for_wrapper(num_of_attr, row_num)
    sqls_map[OpTypeEnum.DISCRETIZE] = udf_time
    sqls_map[OpTypeEnum.APPLY] = udf_time
    
    sqls_map[OpTypeEnum.NUMERIZE] = estimate_numerize(row_num, f"attr{num_of_attr-1}")
    sqls_map[OpTypeEnum.FILLNA] = estimate_fillna(row_num)
    sqls_map[OpTypeEnum.BINARY] = estimate_binary(row_num)
    sqls_map[OpTypeEnum.NORMALIZE] = estimate_normalize(row_num)

    print(termcolor.colored(f"The estimated cost of the operator: {sqls_map}", "green"))
    return sqls_map

def estimate_normalize(row_num):
    # do numerize with attr0
    core_sql = ", cte_2 as (SELECT (attr0 - AVG(attr0) OVER()) / STDDEV(attr0) OVER() as attr0_normalize, * from cte_1) select * from cte_2;"
    return exec_sqls([estimate_template.format(cost_estimation_table = cost_estimation_table, row_num = row_num, core_sql = core_sql)], get_conn())[0]

def estimate_fillna(row_num):
    core_sql = ", cte_2 as (SELECT (CASE WHEN attr0 IS NULL THEN (SELECT attr0 FROM cte_1 WHERE attr0 IS NOT NULL GROUP BY attr0 ORDER BY COUNT(*) DESC LIMIT 1) ELSE attr0 END) AS attr0_Fillna, * FROM cte_1) select * from cte_2"
    return exec_sqls([estimate_template.format(cost_estimation_table = cost_estimation_table, row_num = row_num, core_sql = core_sql)], get_conn())[0]

def estimate_binary(row_num):
    # just sample an sql doing several binary operations
    core_sql = ", cte_2 as (SELECT (attr0 + attr1) as attr0_add_attr1, (attr0 - attr1) as attr0_sub_attr1, (attr0 * attr1) as attr0_mul_attr1, (attr0 / attr1) as attr0_div_attr1, * FROM cte_1) select * from cte_2"
    return exec_sqls([estimate_template.format(cost_estimation_table = cost_estimation_table, row_num = row_num, core_sql = core_sql)], get_conn())[0]

def estimate_numerize(row_num, col_name:str):
    # just sample the 'a', b, c, d, e
    core_sql = f", cte_2 as (SELECT (CASE WHEN {col_name} = 'a' THEN 1 WHEN {col_name} = 'b' THEN 2 WHEN {col_name} = 'c' THEN 3 WHEN {col_name} = 'd' THEN 4 WHEN {col_name} = 'e' THEN 5 ELSE 0 END) as attr0_numerize, * FROM cte_1) select * from cte_2"
    return exec_sqls([estimate_template.format(cost_estimation_table = cost_estimation_table, row_num = row_num, core_sql = core_sql)], get_conn())[0]