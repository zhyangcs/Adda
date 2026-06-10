import ast
import copy
from src.pg.sql_utils import get_conn, next_cte_name
from src.pg.op_type import *

class SQLFormater():
    
    def sqls_to_ctes(origin_table_name:str, sql_file_path: str, need_create: bool) -> str:
        """
        convert each sql to the format of 
        `with tbname as (sql),`
        """
        with open(sql_file_path, 'r') as f:
            sqls = f.readlines()
        with open(sql_file_path, 'w') as f:
            ctes = []
            table_name = origin_table_name
            drop_tables = []
            
            def sql_to_cte(sql: str) -> str:
                nonlocal table_name, drop_tables
                table_name = next_cte_name(table_name)
                # drop_tables.append(table_name)
                sql_without_seal = sql[:-2]
                return "%s as (\n    %s\n),\n" % (table_name, sql_without_seal)
            
            ctes = list(map(sql_to_cte, sqls[0:-1]))
            table_name = next_cte_name(table_name)
            drop_tables.append(table_name)
            if len(sqls) > 1:  
                # delete the `,` of the last cte and add `with` to the first cte
                ctes[-1] = ctes[-1][:-2] + "\n"
                ctes[0] = "with " + ctes[0]

            if need_create:
                ctes.insert(0, "CREATE TABLE %s AS \n" %(table_name))
            ctes.append(sqls[-1])
            
            for dtable in drop_tables:
                f.write("drop table if exists %s;\n" % (dtable))
            for cte in ctes:
                f.write(cte)
        
        return table_name
                
    def sqls_reformat(origin_table_name:str, sql_file_path: str) -> str:
        """
        convert each sql to the format of 
        `CREATE TABLE tbname as sql`
        and add the drop sqls
        return the last table name after execution
        """
        with open(sql_file_path, 'r') as f:
            sqls = f.readlines()
        with open(sql_file_path, 'w') as f:
            table_name = origin_table_name
            for sql in sqls:
                table_name = next_cte_name(table_name)
                f.write("drop table if exists %s;\n" % (table_name))
                if sql.startswith("SELECT"):
                    sql = "CREATE TABLE %s AS %s" % (table_name, sql)
                f.write(sql)
                    
        return table_name

    def sql_reformat_from_pair(extra_step, tb_sql_pair:list, stored_attrs:list, tb_name:str, id_col:str, get_output:bool = True, force_notrain:bool = False) -> str:
        """
        if the insert model is true, then the final pair store the insert sql
        """
        if extra_step != PipeTypeEnum.NOTHING and extra_step != PipeTypeEnum.VALIDATE:
            tb_name = tb_name + str(extra_step)
        if get_output:
            if not force_notrain:
                full_sql = "DROP Table if exists %s;\n" % (tb_name) 
                full_sql += "CREATE TABLE %s as\n" % (tb_name)
            else:
                full_sql = "DROP Table if exists %s;\n" % (tb_name + "_notrain") 
                full_sql += "CREATE TABLE %s as\n" % (tb_name + "_notrain")
        else:
            full_sql = "EXPLAIN ANALYZE "
        full_sql += "with "
        
        if force_notrain:
            # check the train_tb exist in the sql_pair, if exists, drop the following pair
            for i, (tb, sql) in enumerate(tb_sql_pair):
                if tb.startswith("train"):
                    tb_sql_pair = tb_sql_pair[:i]
                    break
        
        for (tb, sql) in tb_sql_pair:
            full_sql += "%s as (\n  %s\n),\n" % (tb, sql)
        
        if extra_step == PipeTypeEnum.NOTHING:
            full_sql = full_sql[:-2] + "select * from %s\n" % (tb_sql_pair[-1][0])
        else:
            last_tb = tb_sql_pair[-1][0]
            stored_attrs_str = 'data'
            limit = ""
            if len(stored_attrs) > 0:
                # if some attr need to be stored, then id should be stored for further combination
                stored_attrs.append(id_col)
                stored_attrs_str = stored_attrs_str + ', ' + ', '.join(list(map(lambda x: last_tb + "." + x, stored_attrs)))
            elif extra_step == PipeTypeEnum.NOTHING:
                stored_attrs = "*"
                limit = ""
            else: 
                limit = "limit 1"
            full_sql = full_sql[:-2] + "select %s from %s %s" % (stored_attrs_str, last_tb, limit)
        return full_sql
    
    def sqls_reformat_from_pair(extra_step, tb_sql_pair:list, stored_attrs:list, tb_name:str, id_col:str, get_output:bool = True, force_notrain:bool = False) -> str:
        """
        if the insert model is true, then the final pair store the insert sql
        """
        if extra_step != PipeTypeEnum.NOTHING and extra_step != PipeTypeEnum.VALIDATE:
            tb_name = tb_name + str(extra_step)
       
        last_tb = tb_sql_pair[-1][0]
        last_sql = "select data from %s limit 1" % (last_tb)
        tb_sql_pair.append((tb_name, last_sql))
        full_sql = ""
        for (tb, sql) in tb_sql_pair:
            full_sql += "DROP Table if exists %s;\n" % (tb)
            full_sql += "CREATE TABLE %s as\n" % (tb)
            full_sql += "(\n%s\n);" % (sql)
        
        print("fullsql: \n", full_sql)
        return full_sql
    
    def sqls_reformat_from_pair_py(extra_step, tb_sql_pair, stored_attrs:list, tb_name:str, id_col:str, get_output:bool = True, force_notrain:bool = False, model_type:str = "LGBM"):
        """
        if the insert model is true, then the final pair store the insert sql
        """
        if extra_step != PipeTypeEnum.NOTHING and extra_step != PipeTypeEnum.VALIDATE:
            tb_name = tb_name + str(extra_step)
            
            
        full_sql = "DROP Table if exists %s;\n" % (tb_name) 
        if extra_step != PipeTypeEnum.TRAIN:
            full_sql += "CREATE TABLE %s as\n" % (tb_name)
        full_sql += "with "
        
        if extra_step != PipeTypeEnum.TRAIN:
            for (tb, sql) in tb_sql_pair:
                full_sql += "%s as (\n  %s\n),\n" % (tb, sql)
            
            if extra_step == PipeTypeEnum.NOTHING:
                full_sql = full_sql[:-2] + "select * from %s\n" % (tb_sql_pair[-1][0])
            else:
                last_tb = tb_sql_pair[-1][0]
                stored_attrs_str = 'data'
                limit = ""
                if len(stored_attrs) > 0:
                    # if some attr need to be stored, then id should be stored for further combination
                    stored_attrs.append(id_col)
                    stored_attrs_str = stored_attrs_str + ', ' + ', '.join(list(map(lambda x: last_tb + "." + x, stored_attrs)))
                elif extra_step == PipeTypeEnum.NOTHING:
                    stored_attrs = "*"
                    limit = ""
                else: 
                    limit = "limit 1"
                full_sql = full_sql[:-2] + "select %s from %s %s" % (stored_attrs_str, last_tb, limit)
        else:
            for (tb, sql) in tb_sql_pair[:-1]:
                full_sql += "%s as (\n  %s\n),\n" % (tb, sql)
            full_sql = full_sql[:-2] + tb_sql_pair[-1][1]
        return full_sql