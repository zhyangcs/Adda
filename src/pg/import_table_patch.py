import pandas as pd
import psycopg2
import os
import re
import numpy as np

def csv2tb_with_insert(csvpath: str, tbname: str, conn, use_quote:bool = True, pgml_path=""):
    """
    使用INSERT语句替代COPY命令的数据导入函数
    """
    df = pd.read_csv(csvpath)
    
    # 处理列名
    for col in df.columns:
        if bool(re.search(r'^\d', col)):
            new_col = "number_" + col
        else:
            new_col = col
        new_col = new_col.replace(" ", "")
        new_col = new_col.replace("(", "_leftb_")
        new_col = new_col.replace(")", "_rightb_")
        new_col = new_col.replace("&", "_and_")
        new_col = new_col.replace("-", "_")
        new_col = new_col.replace("[", "_leftbb_")
        new_col = new_col.replace("]", "_rightbb_")
        new_col = new_col.replace(",", "_comma_")
        new_col = new_col.replace("'", "_apos_")
        new_col = new_col.replace('"', "_quot_")
        new_col = new_col.replace(":", "_colon_")
        new_col = new_col.replace("/", "_slash_")
        new_col = new_col.replace("*", "_star_")
        new_col = new_col.replace("+", "_add_")
        df.rename(columns={col: new_col}, inplace=True)
    
    # 创建表结构
    sql = f"CREATE TABLE IF NOT EXISTS {tbname} (\n"
    varchar_col = []
    
    for col in df.columns:
        sql += col + " "
        if str(df[col].dtype).startswith('int'):
            sql += "BIGINT"
        elif str(df[col].dtype).startswith('float'):
            sql += "Float8"
        elif str(df[col].dtype).startswith('bool'):
            sql += "BOOLEAN"
        else:
            sql += "VARCHAR(100)"
            varchar_col.append(col.lower())
        sql += "," if col != df.columns[-1] else "\n"
    sql += ");\n"
    
    cursor = conn.cursor()
    print(sql)
    cursor.execute(sql)
    
    # 使用INSERT语句插入数据
    print(f"使用INSERT语句向表 {tbname} 插入 {len(df)} 行数据...")
    
    # 准备INSERT语句
    columns = ', '.join(df.columns)
    placeholders = ', '.join(['%s'] * len(df.columns))
    insert_sql = f"INSERT INTO {tbname} ({columns}) VALUES ({placeholders})"
    
    # 批量插入数据
    batch_size = 1000
    for i in range(0, len(df), batch_size):
        batch_df = df.iloc[i:i+batch_size]
        # 处理numpy数据类型，转换为Python原生类型
        values = []
        for _, row in batch_df.iterrows():
            row_values = []
            for val in row:
                if pd.isna(val):
                    row_values.append(None)
                elif isinstance(val, (np.integer, np.floating)):
                    row_values.append(val.item())
                else:
                    row_values.append(val)
            values.append(tuple(row_values))
        cursor.executemany(insert_sql, values)
        print(f"已插入 {min(i+batch_size, len(df))}/{len(df)} 行")
    
    conn.commit()
    print(f"数据导入完成，共插入 {len(df)} 行数据")

def importTable_df_with_insert(df: pd.DataFrame, tbname: str, conn, use_quote:bool = True, pgml=False):
    """
    使用INSERT语句的DataFrame导入函数
    """
    if conn == None:
        return
    else:
        # 处理列名
        for col in df.columns:
            if bool(re.search(r'^\d', col)):
                new_col = "number_" + col
            else:
                new_col = col
            new_col = new_col.replace(" ", "")
            new_col = new_col.replace("(", "_leftb_")
            new_col = new_col.replace(")", "_rightb_")
            new_col = new_col.replace("&", "_and_")
            new_col = new_col.replace("-", "_")
            new_col = new_col.replace("[", "_leftbb_")
            new_col = new_col.replace("]", "_rightbb_")
            new_col = new_col.replace(",", "_comma_")
            new_col = new_col.replace("'", "_apos_")
            new_col = new_col.replace('"', "_quot_")
            new_col = new_col.replace(":", "_colon_")
            new_col = new_col.replace("/", "_slash_")
            new_col = new_col.replace("*", "_star_")
            new_col = new_col.replace("+", "_add_")
            df.rename(columns={col: new_col}, inplace=True)
        
        # 直接使用INSERT语句，不需要临时文件
        print(f"使用INSERT语句向表 {tbname} 插入 {len(df)} 行数据...")
        
        # 创建表结构
        sql = f"CREATE TABLE IF NOT EXISTS {tbname} (\n"
        varchar_col = []
        
        for col in df.columns:
            sql += col + " "
            if str(df[col].dtype).startswith('int'):
                sql += "BIGINT"
            elif str(df[col].dtype).startswith('float'):
                sql += "Float8"
            elif str(df[col].dtype).startswith('bool'):
                sql += "BOOLEAN"
            else:
                sql += "VARCHAR(100)"
                varchar_col.append(col.lower())
            sql += "," if col != df.columns[-1] else "\n"
        sql += ");\n"
        
        cursor = conn.cursor()
        print(sql)
        cursor.execute(sql)
        
        # 准备INSERT语句
        columns = ', '.join(df.columns)
        placeholders = ', '.join(['%s'] * len(df.columns))
        insert_sql = f"INSERT INTO {tbname} ({columns}) VALUES ({placeholders})"
        
        # 批量插入数据
        batch_size = 1000
        for i in range(0, len(df), batch_size):
            batch_df = df.iloc[i:i+batch_size]
            # 处理numpy数据类型，转换为Python原生类型
            values = []
            for _, row in batch_df.iterrows():
                row_values = []
                for val in row:
                    if pd.isna(val):
                        row_values.append(None)
                    elif isinstance(val, (np.integer, np.floating)):
                        row_values.append(val.item())
                    else:
                        row_values.append(val)
                values.append(tuple(row_values))
            cursor.executemany(insert_sql, values)
            print(f"已插入 {min(i+batch_size, len(df))}/{len(df)} 行")
        
        conn.commit()
        print(f"数据导入完成，共插入 {len(df)} 行数据") 