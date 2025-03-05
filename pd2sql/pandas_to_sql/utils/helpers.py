import pandas as pd
import termcolor


## Types
def convert_df_type(col_type):
    if pd.api.types.is_bool_dtype(col_type): return 'BOOL'
    elif pd.api.types.is_integer_dtype(col_type): return 'INT'
    elif pd.api.types.is_numeric_dtype(col_type): return 'FLOAT'
    elif pd.api.types.is_string_dtype(col_type): return 'VARCHAR'
    elif pd.api.types.is_datetime64_any_dtype(col_type): return 'DATETIME'
    elif pd.api.types.is_categorical_dtype(col_type): return 'VARCHAR'
    else: raise Exception(f"could not convert column type. got: {str(col_type)}")


def create_schema_from_df(df):        
    schema = {}
    for col_name, col_type in df.dtypes.items():
        # print(col_name, col_type)
        schema[col_name] = convert_df_type(col_type)
    return schema