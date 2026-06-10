import inspect
import random
from src.pg.sql_utils import *
from src.pg.func_utils import *
from src.pg.op_type import *

class Py2Sql():
    def generate_encode_table(encode_table_name: str, old_column_name: str, new_column_name: str, categories: list[str]) -> None:
        create_table_sql = """drop table if exists %s;
        create table %s (%s varchar(255), %s int8);
        """ % (encode_table_name, encode_table_name, old_column_name, new_column_name)
        insert_sql = """insert into %s values """ % (encode_table_name)
        for idx, category in enumerate(categories):
            insert_sql += """('%s', %d),""" % (category, idx)
        insert_sql = insert_sql[:-1] + ';'

        conn = get_conn()
        # print(create_table_sql, insert_sql)
        exec_sqls([create_table_sql, insert_sql], conn)
    
    def generate_ohencode_table(encode_table_name: str, old_column_name: str, categories: list[str]) -> None:
        create_table_sql = 'drop table if exists %s;' % (encode_table_name)
        create_table_sql += 'create table %s (%s varchar(255)' % (encode_table_name, old_column_name)
        for category in categories:
            create_table_sql += ', %s_%s Bool' % (old_column_name, category)
        create_table_sql += ');'
        insert_sql = """insert into %s values """ % (encode_table_name)
        for category in categories:
            insert_sql += """('%s',""" % (category)
            for category2 in categories:
                if category == category2:
                    insert_sql += """True,"""
                else:
                    insert_sql += """False,"""
            insert_sql = insert_sql[:-1] + '),'
        insert_sql = insert_sql[:-1] + ';'
        
        conn = get_conn()
        # print(create_table_sql, insert_sql)
        exec_sqls([create_table_sql, insert_sql], conn)
        
    def generate_discretize_table(discrete_table_name: str, old_column_name: str, new_column_name:str, labels: list[str]) -> None:
        create_table_sql = 'drop table if exists %s;' % (discrete_table_name)
        create_table_sql += 'create table %s (%s varchar(255), %s int4);' % (discrete_table_name, new_column_name, old_column_name)
        insert_sql = 'insert into %s values ' % (discrete_table_name)
        for idx, label in enumerate(labels):
            insert_sql += """('%s', %d),""" % (label, idx+1)
        insert_sql = insert_sql[:-1] + ';'
        
        conn = get_conn()
        # print(create_table_sql, insert_sql)
        exec_sqls([create_table_sql, insert_sql], conn)
    
    
    def label_encode(encode_table_name: str, origin_table_name: str, old_column_name: str, new_column_name: str, categories: list[str]) -> str:
        """
        one hot encode the column by join the encode table and origin table
        """
        # do emulate first
        Py2Sql.generate_encode_table(
            encode_table_name, old_column_name, new_column_name, categories)
        # if need change the output of the column, then could use the senmatic of
        # select encode_table_name.old_column_name, encode_table_name.new_column_name as xxx , origin_table_name.* from xxxxx;
        sql = """select %s.%s, %s.* from %s JOIN %s ON %s.%s = %s.%s""" % (
            encode_table_name, new_column_name, origin_table_name, encode_table_name, origin_table_name, encode_table_name, old_column_name, origin_table_name, old_column_name)
        return sql
    
    def label_encode_by_update(origin_table_name: str, old_column_name: str, new_column_name:str, categories: list[str]) -> str:
        """
        label encoder impl by the update keyword
        """
        caselist = []
        for idx, category in enumerate(categories):
            caselist.append("WHEN %s = '%s' THEN %d" % (old_column_name, category, idx))
        
        sql = "SELECT CASE %s END AS %s, * FROM %s" % (" ".join(caselist), new_column_name, origin_table_name)
        return sql

    def normalization(type:NormTypeEnum ,origin_table_name:str, column_names:list[str], new_column_names:list[str], seq:int) -> str:
        """
        normalization the column by the normalization method: v --> (v-avg)/stddev
        example: SELECT (complications - AVG(complications) OVER ()) / STDDEV(complications) OVER () AS complications FROM test;
        """
        sql = "SELECT"
        percent_sql = ""
        percent_tb = ""
        if type == NormTypeEnum.STANDARD:
            for column_name, new_column_name in zip(column_names, new_column_names):
                sql += """ (%s - AVG(%s) OVER ()) / STDDEV(%s) OVER () AS %s,  """ % (column_name, column_name, column_name, new_column_name)
            sql += """ * FROM %s""" % (origin_table_name)
        
        elif type == NormTypeEnum.MINMAX:
            for column_name, new_column_name in zip(column_names, new_column_names):
                sql += """ (%s - MIN(%s) OVER ()) / (MAX(%s) OVER () - MIN(%s) OVER ()) AS %s,  """ % (column_name, column_name, column_name, column_name, new_column_name)
            sql += """ * FROM %s""" % (origin_table_name)
        
        elif type == NormTypeEnum.ROBUST:
            percent_sql = "SELECT"
            percent_tb = "percent_tb" + str(seq)
            for column_name, new_column_name in zip(column_names, new_column_names):
                percent_sql += " PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY %s) AS %s_25, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY %s) AS %s_50, PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY %s) AS %s_75, " % (column_name, column_name, column_name, column_name, column_name, column_name)
                sql += """ ((%s.%s - %s.%s_50)/(%s.%s_75 - %s.%s_25)) AS %s,  """ % (origin_table_name, column_name, percent_tb, column_name, percent_tb, column_name, percent_tb, column_name, new_column_name)
            percent_sql = percent_sql[:-2] + " FROM %s" % (origin_table_name)
            sql += """ * FROM %s, %s""" % (origin_table_name, percent_tb)
        
        return sql, percent_sql, percent_tb
    
    def one_hot_encode(encode_table_name: str, origin_table_name: str, old_column_name: str, categories: list[str]) -> str:
        """
        one hot encode the column by join the encode table and origin table
        """
        # do emulate first
        new_column_names = []
        for category in categories:
            new_column_names.append("onehot_" + category)
        Py2Sql.generate_ohencode_table(
            encode_table_name, old_column_name, categories)
        # if need change the output of the column, then could use the senmatic of
        # select encode_table_name.old_column_name, encode_table_name.new_column_name as xxx , origin_table_name.* from xxxxx;
        sql = """select """
        for category in categories:
            sql += """%s.%s, """ % (encode_table_name, old_column_name + "_" + category)
        
        sql += """%s.* from %s JOIN %s ON %s.%s = %s.%s""" % (
            origin_table_name, encode_table_name, origin_table_name, encode_table_name, old_column_name, origin_table_name, old_column_name)
        return sql

    def one_hot_by_update(origin_table_name: str, old_column_name: str, categories: list[str]) -> str:
        """
        one hot encode the column by doing the update by case when
        """
        caselist = []
        for category in categories:
            print(type(category), category)
            new_column_name = old_column_name + "_" + category
            caselist.append("CASE WHEN %s = '%s' THEN True ELSE False END AS %s" % (old_column_name, category, new_column_name))
        sql = "SELECT %s, * FROM %s" % (", ".join(caselist), origin_table_name)
        return sql
    
    def discretize_qcut(origin_table_name: str, old_column_name: str, new_column_name: str, labels: list[str], num_of_record: int, seq: int) -> str:
        """
        discretize the values in the column_name into kbins, each bins has similar number of values, 
        then set the value with the labels to the new_column_name
        (SELECT income
        FROM small_test
        ORDER BY income DESC
        LIMIT 1 OFFSET 20)
        UNION
        (SELECT income
        FROM small_test
        ORDER BY income DESC
        LIMIT 1 OFFSET 40);
        
        then
        
        SELECT cte_5.*, (SELECT COUNT(*) FROM bound_tb_1 WHERE cte_5.Age_fillna >= bound_tb_1.Age_fillna) AS exceed_num_ FROM cte_5;

        """
        
        kbins = len(labels)
        boundary = list(range(0, num_of_record, num_of_record // kbins))
        bound_sql = ""
        bound_table_name = "bound_tb_"+str(seq)
        for idx in range(len(boundary) - 1):
            bound_sql += """(SELECT %s FROM %s ORDER BY %s DESC LIMIT 1 OFFSET %d) UNION""" % (old_column_name, origin_table_name, old_column_name, boundary[idx])
        bound_sql = bound_sql[:-6] + "\n"
        
        exceed_table_name = "exceed_tb_"+str(seq)
        pos_sql = "SELECT %s.*, (SELECT COUNT(*) FROM %s WHERE %s.%s >= %s.%s) AS exceed_num_%d FROM %s" % (origin_table_name, bound_table_name, origin_table_name, old_column_name, bound_table_name, old_column_name, seq, origin_table_name)
        # pos_sql = "SELECT %s.*, (SELECT COUNT(*) from %s) as exceed_num_%d from %s join %s on %s.%s >= %s.%s\n" % (origin_table_name, bound_table_name, seq, origin_table_name, bound_table_name, origin_table_name, old_column_name, bound_table_name, old_column_name)

        discrete_table_name = "discrete_tb_"+str(seq)
        Py2Sql.generate_discretize_table(discrete_table_name, "exceed_num_"+str(seq), new_column_name, labels)
        combine_sql = """select %s.%s, %s.* from %s JOIN %s ON %s.exceed_num_%d = %s.exceed_num_%d\n""" % (
            discrete_table_name, new_column_name, exceed_table_name, discrete_table_name, exceed_table_name, discrete_table_name, seq, exceed_table_name, seq)
        
        return (bound_sql, pos_sql, combine_sql), (bound_table_name, exceed_table_name, "")
    
    def discretize_cut(origin_table_name: str, old_column_name: str, new_column_name: str, labels: list[str], seq: int) -> str:
        """
        WITH min_max AS (
            SELECT 
                MIN(income) AS min_value,
                MAX(income) AS max_value,
                generate_series(1, 10-1) AS n
            FROM small_test
        ) SELECT 
            min_value + n * (max_value - min_value) / 10 AS income
        FROM 
            min_max;
        """
        kbins = len(labels)
        minmax_tb = "minmax_tb_" + str(seq)
        minmax_sql = "SELECT MIN(%s) AS min_value, MAX(%s) AS max_value, generate_series(0, %d - 1) as n FROM %s" % (old_column_name, old_column_name, kbins, origin_table_name)
        bound_tb = "bound_tb_" + str(seq)
        bound_sql = "SELECT min_value + n * (max_value - min_value) / %d AS %s FROM %s" % (kbins, old_column_name, minmax_tb)
        
        exceed_tb = "exceed_tb_" + str(seq)
        pos_sql = "SELECT %s.*, (SELECT COUNT(*) FROM %s WHERE %s.%s >= %s.%s) AS exceed_num_%d FROM %s" % (origin_table_name, bound_tb, origin_table_name, old_column_name, bound_tb, old_column_name, seq, origin_table_name)
        # pos_sql = "SELECT %s.*, (SELECT COUNT(*) from %s) as exceed_num_%d from %s join %s on %s.%s >= %s.%s\n" % (origin_table_name, bound_tb, seq, origin_table_name, bound_tb, origin_table_name, old_column_name, bound_tb, old_column_name)
        
        discrete_table_name = "discrete_tb_" + str(seq)
        Py2Sql.generate_discretize_table(discrete_table_name, "exceed_num_"+str(seq), new_column_name, labels)
        combine_sql = "select %s.%s, %s.* from %s JOIN %s ON %s.exceed_num_%d = %s.exceed_num_%d\n" % (
            discrete_table_name, new_column_name, exceed_tb, discrete_table_name, exceed_tb, discrete_table_name, seq, exceed_tb, seq)
        
        return (minmax_sql, bound_sql, pos_sql, combine_sql), (minmax_tb, bound_tb, exceed_tb, "")
    
    def join(src_tb_names:list[str], src_tb_attrs:list[list[str]], join_attr:str):
        """
        join the tbs with the join attr
        """
        sql = "SELECT "
        for tb_name, tb_attrs in zip(src_tb_names, src_tb_attrs):
            for attr in tb_attrs:
                if attr != join_attr:
                    sql += "%s.%s as %s, " % (tb_name, attr, attr)
        sql += "%s.%s as %s" % (src_tb_names[0], join_attr, join_attr)       
        sql += f" FROM %s JOIN %s ON %s.%s = %s.%s" % (src_tb_names[0], src_tb_names[1], src_tb_names[0], join_attr, src_tb_names[1], join_attr)
        return sql
    
    def fillna_by_update_original(fill_type: FillnaType, src_tb_name: str, src_col_name:str):
        """
        fillna with the certain type of fill_type
        """
        if fill_type.fill_type == FillnaTypeEnum.MEAN:
            sql = "UPDATE %s SET %s = (SELECT AVG(%s) FROM %s WHERE %s IS NOT NULL) WHERE %s is NULL" % (src_tb_name, src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name)
        elif fill_type.fill_type == FillnaTypeEnum.MEDIAN:
            sql = "UPDATE %s SET %s = (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY %s) FROM %s WHERE %s IS NOT NULL) WHERE %s is NULL" % (src_tb_name, src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name)
        elif fill_type.fill_type == FillnaTypeEnum.MAX:
            sql = "UPDATE %s SET %s = (SELECT MAX(%s) FROM %s WHERE %s IS NOT NULL) WHERE %s is NULL" % (src_tb_name, src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name)
        elif fill_type.fill_type == FillnaTypeEnum.MIN:
            sql = "UPDATE %s SET %s = (SELECT MIN(%s) FROM %s WHERE %s IS NOT NULL) WHERE %s is NULL" % (src_tb_name, src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name)
        elif fill_type.fill_type == FillnaTypeEnum.MODE:
            sql = "UPDATE %s SET %s = (SELECT %s FROM %s WHERE %s IS NOT NULL GROUP BY %s ORDER BY COUNT(*) DESC LIMIT 1) WHERE %s is NULL" % (src_tb_name, src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name, src_col_name)
        elif fill_type.fill_type == FillnaTypeEnum.CONSTANT:
            sql = "UPDATE %s SET %s = %s WHERE %s is NULL" % (src_tb_name, src_col_name, fill_type.constant, src_col_name)
        else:
            raise Exception("Unsupport fill type")
        return sql
    
    def fillna_by_select(fill_type_list: list[FillnaType], src_tb_name: str, src_col_name_list:list[str], target_col_name_list:list[str]):
        """
        fillna with the certain type of fill_type
        """
        sql = "SELECT "
        if len(src_col_name_list) != len(fill_type_list):
            print("some column maybe not operate")
            src_col_name_list = src_col_name_list + [src_col_name_list[-1]] * (len(fill_type_list) - len(src_col_name_list))
            
        for fill_type, src_col_name, target_col_name in zip(fill_type_list, src_col_name_list, target_col_name_list):
            if fill_type.fill_type == FillnaTypeEnum.MEAN:
                sql += "(CASE WHEN %s IS NULL THEN (SELECT AVG(%s) FROM %s WHERE %s IS NOT NULL) ELSE %s END) AS %s, " % (src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name, target_col_name)
            elif fill_type.fill_type == FillnaTypeEnum.MEDIAN:
                sql += "(CASE WHEN %s IS NULL THEN (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY %s) FROM %s WHERE %s IS NOT NULL) ELSE %s END) AS %s, " % (src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name, target_col_name)
            elif fill_type.fill_type == FillnaTypeEnum.MAX:
                sql += "(CASE WHEN %s IS NULL THEN (SELECT MAX(%s) FROM %s WHERE %s IS NOT NULL) ELSE %s END) AS %s, " % (src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name, target_col_name)
            elif fill_type.fill_type == FillnaTypeEnum.MIN:
                sql += "(CASE WHEN %s IS NULL THEN (SELECT MIN(%s) FROM %s WHERE %s IS NOT NULL) ELSE %s END) AS %s, " % (src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name, target_col_name)
            elif fill_type.fill_type == FillnaTypeEnum.MODE:
                sql += "(CASE WHEN %s IS NULL THEN (SELECT %s FROM %s WHERE %s IS NOT NULL GROUP BY %s ORDER BY COUNT(*) DESC LIMIT 1) ELSE %s END) AS %s, " % (src_col_name, src_col_name, src_tb_name, src_col_name, src_col_name, src_col_name, target_col_name)
            elif fill_type.fill_type == FillnaTypeEnum.CONSTANT:
                sql += "(CASE WHEN %s IS NULL THEN %s ELSE %s END) AS %s, " % (src_col_name, fill_type.constant, src_col_name, target_col_name)
            else:
                raise Exception("Unsupport fill type", fill_type)
        sql = sql+ "* FROM %s" % (src_tb_name)
        return sql

    def reuse(src_tb_name: str, src_col_name:str, target_col_name:str, pre_cte:str, id_col:str):
        """
        reuse the certain column
        SELECT pre_cte.*, src_tb_name.src_col_name AS target_col_name FROM src_tb_name JOIN pre_cte on src_tb_name.id_col = pre_cte.id_col;
        """
        sql = "SELECT %s.*, %s.%s AS %s FROM %s JOIN %s on %s.%s = %s.%s" % (pre_cte, src_tb_name, src_col_name, target_col_name, src_tb_name, pre_cte, src_tb_name, id_col, pre_cte, id_col)
        return sql