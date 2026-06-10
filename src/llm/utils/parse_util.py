import re
import os
import pandas as pd
import numpy as np
from src.pg.op_type import *
from src.pg.import_table import *
import termcolor
from src.llm.utils.llm_util import *

def parse_string_to_list(cur_str:str):
    cur_str = cur_str.strip()
    if cur_str.endswith('.'):
        cur_str = cur_str[:-1]
    return list(map(lambda x: x.strip("'").strip('"'), list(cur_str.split(", "))))

def remove_quote(s:str):
    return s.strip("'").strip('"')
    
def get_df_desc_prompt(df1:pd.DataFrame, head_num:int, label, expect_cols, code:str, column_info):
    samples = ""
    if df1 is None:
        return f"""The dataframe of the task `df` is loaded and in memory. Columns are also named attributes.
Columns in `df` (true feature dtypes listed here, categoricals encoded as int):
Now we try to execute the following function to generate a new feature:
```python
{code}
```
"""
    df = df1.copy()
    if label is not None:
        df = pd.concat([df, label], axis = 1)
    df_ = df.head(head_num)
    valid_cols = [i for i in expect_cols if i in df.columns]
    for i in valid_cols:
        # show the list of values
        nan_freq = "%s" % float("%.2g" % (df[i].isna().mean() * 100))
        if df[i].dtype in [int, float, 'int64', 'float64']:
            skewness = "%s" % float("%.2g" % (df[i].skew()))
            skewness += "%"
        else:
            skewness = "NaN"
        unique_num = "%s" %(df[i].nunique())
        s = df_[i].tolist()
        if str(df[i].dtype) == "float64":
            s = [round(sample, 2) for sample in s]
        samples += (
            f"{df_[i].name} ({df[i].dtype}): NaN-freq [{nan_freq}%], Skewness [{skewness}], unique num [{unique_num}], Samples {s}\n"
        )
    relevant_cols = []
    for i in valid_cols:
        if i in column_info:
            relevant_cols.append(column_info[i])
    relevant_cols_str = "".join(relevant_cols)
    return f"""The dataframe of the task `df` is loaded and in memory. Columns are also named attributes.
Columns in `df` (true feature dtypes listed here, categoricals encoded as int):
Now we try to execute the following function to generate a new feature:
```python
{code}
```
Here is some information of the original columns:
{relevant_cols_str}
{samples}"""

def get_column_info(column_info, token_limit, attr_imp_list=None):
    prompt_template = """The dataframe of the task `df` is loaded and in memory. Columns are also named attributes.
Columns in `df` (true feature dtypes listed here, categoricals encoded as int):
For each attribute, the following information is provided:
{column_info_str}"""
    column_info_str = ""
    cur_token_num = token_num(prompt_template)
    appear_attr = set()
    
    # if one do not give the importance order, then we use the origin order 
    if attr_imp_list == None:
        attr_imp_list = list(column_info.keys())
        
    print(termcolor.colored(f"Current attributes includes {attr_imp_list}", "yellow"))
    for idx, attr in enumerate(attr_imp_list):
        if cur_token_num > token_limit:
            break
        if attr == 'id' or attr not in column_info:
            # skip the id and fixing feature
            continue
        # column_info_str += column_info[attr]
        appear_attr.add(attr)
        cur_token_num += token_num(column_info[attr])

    # maintain the origin order!!
    for attr_name, attr_str in column_info.items():
        if attr_name in appear_attr:
            column_info_str += attr_str
        
    print(termcolor.colored(f"Current attributes includes {attr_imp_list[:idx]}, exclude {attr_imp_list[idx:]}", "yellow"))
    return prompt_template.format(column_info_str = column_info_str)

def parse_code(code: str, language:str = 'python'):
    '''
    parse code from the format of ```python\n ``` 
    '''
    if language == 'c++':
        language = 'c\+\+'
    pattern = r"```%s\n(.*?)\n```" % (language)
    
    match = re.search(pattern, code, re.DOTALL)
    if match:
        code = match.group(1)
        return code
    else:
        return code
    
def parse_fix_feature(content:str):
    '''
    parse the fix_feature from the content
    '''
    feature_list = content.split(",")
    pattern = r"""^(.*?):(.*?)$"""
    ret = []
    for feature in feature_list:
        match = re.search(pattern, feature)
        if match:
            attr = match.group(2).strip()
            if attr.startswith("'") and attr.endswith("'"):
                attr = attr[1:-1].strip()
            pair = (match.group(1), attr)
            ret.append(pair)
    return ret

def parse_str_to_OPTypeEnum(type_str:str):
    if type_str == "Normalization":
        return OpTypeEnum.NORMALIZE
    elif type_str == "Fillna":
        return OpTypeEnum.FILLNA
    elif type_str == "Unary operation":
        return OpTypeEnum.DISCRETIZE
    elif type_str == "Label encoding":
        return OpTypeEnum.NUMERIZE
    
    
if __name__ == "__main__":
    s = "s''sfd'"
    print(remove_quote(s))
