import pandas as pd
from io import StringIO
import re
import csv
import os
from src.env import *
from sklearn.model_selection import train_test_split
from src.pg.sql_utils import get_conn
import psycopg2
from src.pg.func_utils import *


def dropTable(tbname: str, conn):
    # drop table if exists
    cur = conn.cursor()
    cur.execute("drop table if exists " + tbname + ";")
    cur.close()
    conn.commit()

def replace_with_rules(csvpath:str) -> str:
    """
    replace the file with the rules, and return the new file path
    """
    # change the na to nan
    new_csv_path = csvpath[:-4] + "_new.csv"
    with open(csvpath, "r") as f:
        new_file = open(new_csv_path, "w+")
        lines = f.readlines()
        new_file.write(lines[0])
        for line in lines[1:]:
            line = line.replace('NA', 'nan')
            line = line.replace('?','')
            line = line.replace("'", '__apos__')
            # line = line.replace('"', '__quot__')
            new_file.write(line)
        new_file.close()
    return new_csv_path

def replace_with_simple_fill(csvpath:str):
    """
    replace the file with simply filling the missing value
    """
    df = pd.read_csv(csvpath)
    for col in df.columns:
        if df[col].dtype == 'int64' or df[col].dtype == 'float64':
            df[col].fillna(df[col].mean(), inplace=True)
        else:
            df[col].fillna(df[col].mode()[0], inplace=True)
    df.to_csv(csvpath, index = False)
    

def importTable(csvpath: str, tbname: str, conn, use_quote:bool = True):
    """
    if conn is None, then just clean the data[replace the NA with nan]
    else then import the cleaned data to the database
    """
    new_csv_path = replace_with_rules(csvpath)
    # replace_with_simple_fill(new_csv_path)

    if conn == None:
        return
    else:
        # create table
        csv2tb(new_csv_path, tbname, conn, use_quote)


def csv2tb(csvpath: str, tbname: str, conn, use_quote:bool = True, pgml_path=""):
    
    dropTable(tbname, conn)
    
    varchar_col = []
    while True:
        try:
            df = pd.read_csv(csvpath)
            sql = "create table " + tbname + "( \n"
            for col in df.columns:
                if use_quote:
                    sql += '"' + col + '" '
                else:
                    sql += col + " "
                if col.lower() in varchar_col:
                    sql += "VARCHAR(100)"
                else:
                    # print(str(df[col].dtype))
                    if str(df[col].dtype).startswith('int'):
                        sql += "BIGINT"
                    elif str(df[col].dtype).startswith('float'):
                        sql += "Float8"
                    elif str(df[col].dtype).startswith('bool'):
                        sql += "BOOLEAN"
                    else:
                        sql += "VARCHAR(100)"
                sql += "," if col != df.columns[-1] else "\n"
            sql += ");\n" 
            
            cursor = conn.cursor()
            print(sql)
            cursor.execute(sql)
            if pgml_path != "":
                csvpath = pgml_path
            print("copy " + tbname + " from '" + csvpath +
                "' with csv header delimiter ','  encoding 'UTF8'")
            cursor.execute("copy " + tbname + " from '" + csvpath +
                        "' with csv header delimiter ','  encoding 'UTF8'")
            conn.commit()
            break

        except psycopg2.Error as e:
            print(e)
            col = re.search(r'column (.*?):', str(e)).group(1)
            # print("An error occurred: ", e)
            # print(col)
            varchar_col.append(col.lower())
            conn.rollback()
            # break
    
def prefix_check(cur_pre: str):
    if bool(re.search(r'^\d', cur_pre)):
        cur_pre = "number_" + cur_pre
    cur_pre = cur_pre.replace(" ", "")
    # cur_pre = cur_pre.replace(".", "_point_")
    cur_pre = cur_pre.replace("(", "_leftb_")
    cur_pre = cur_pre.replace(")", "_rightb_")
    cur_pre = cur_pre.replace("&", "_and_")
    cur_pre = cur_pre.replace("-", "_")
    cur_pre = cur_pre.replace("[", "_leftbb_")
    cur_pre = cur_pre.replace("]", "_rightbb_")
    cur_pre = cur_pre.replace(",", "_comma_")
    cur_pre = cur_pre.replace("'", "_apos_")
    cur_pre = cur_pre.replace('"', "_quot_")
    cur_pre = cur_pre.replace(":", "_colon_")
    cur_pre = cur_pre.replace("/", "_slash_")
    cur_pre = cur_pre.replace("*", "_star_")
    cur_pre = cur_pre.replace("+", "_add_")
    return cur_pre

def convert_to_float(path: str, outpath:str) -> None:
    """
    convert the data type to float
    """
    df = pd.read_csv(path)
    for col in df.columns:
        if df[col].dtype != 'object' and df[col].dtype != 'category':
            df[col] = df[col].astype(float)
    df.to_csv(outpath, index=False)

def prefix_check_df(df: pd.DataFrame):
    """
    prefix check for the dataframe
    """
    for col in df.columns:
        df.rename(columns={col: prefix_check(col)}, inplace=True)
    return df

def add_id(csv_path:str):
    """
    add the id column to the csv file
    """
    df = pd.read_csv(csv_path)
    df.insert(0, "id", range(1, len(df)+1))
    df.to_csv(csv_path[:-4] + "_addid.csv", index=False)

def importTable_df(df: pd.DataFrame, tbname: str, conn, use_quote:bool = True, pgml=False):
    """
    if conn is None, then just clean the data[replace the NA with nan]
    else then import the cleaned data to the database
    """
    if conn == None:
        return
    else:
        # create table
        df = prefix_check_df(df)
        tmp_path = os.path.join(proj_path, "temp.csv")
        df.to_csv(tmp_path, index=False)
        if pgml:
            csv2tb(tmp_path, tbname, conn, use_quote=False, pgml_path="/home/postgresml/data/temp.csv")
        else:
            csv2tb(tmp_path, tbname, conn, use_quote)
        # drop the table
        os.system(f"rm {tmp_path}")
        
def importTable_with_split(csvpath:str, tbname:str, label:str, conn, use_quote:bool = True, task_type = "classify", pgml=False):
    df = pd.read_csv(csvpath)
    if pgml:
        print(termcolor.colored("pgml is True, the csv file should be the pgml file", "red"))
        df = data_preprocess(df)
    df = prefix_check_df(df)
    print(df.info())
    # df_train, df_test = df.iloc[:int(len(df)*0.8)], df.iloc[int(len(df)*0.8):]
    if task_type == "classify":
        df_train, df_test = train_test_split(df, test_size=0.2, random_state=0, stratify=df[label])
    else:
        df_train, df_test = train_test_split(df, test_size=0.2, random_state=0)
    importTable_df(df_train, tbname + "_train", conn, use_quote, pgml)
    importTable_df(df_test, tbname + "_test", conn, use_quote, pgml)
    importTable_df(df, tbname, conn, use_quote, pgml)
    return len(df_train), len(df_test)
