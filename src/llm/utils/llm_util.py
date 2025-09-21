from openai import OpenAI
from openai import OpenAIError
import os
import time
from sklearn.feature_selection import mutual_info_classif
import termcolor
from networkx.drawing.nx_agraph import to_agraph
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, roc_auc_score
import lightgbm as lgb
import time
from src.env import * 
import tiktoken
from src.env import *


RETRY_TIME = 2

def send_prompt(role_prompt:str, user_prompt:str, model:str = default_model, test_speed:bool = False, temperature = 0.8):
    t1 = time.time()
    if test_speed:
        time.sleep(1)
        return
    client = OpenAI(
        base_url=openai_base_url,
        api_key=openai_api_key
    )
    messages = []
    if role_prompt != "":
        messages.append({
                "role": "system",
                "content": role_prompt,
            })

    messages.append({
                "role": "user",
                "content": user_prompt,  
    })
    
    retry_time = RETRY_TIME
    while retry_time > 0:
        try:
            print(termcolor.colored("Sending prompt to OpenAI...", "yellow"))
            completion = client.chat.completions.create(
                model = model,
                temperature = temperature,
                messages = messages,
                max_tokens = 500,
                seed=global_seed
            )
            print(termcolor.colored("Received the response successfully!", "yellow"))
            break
        except OpenAIError as e:
            print(termcolor.colored("Error: %s" % e, "red"))
            time.sleep(10)
            retry_time -= 1
            
    if retry_time == 0:
        raise Exception("Failed to send prompt to OpenAI")
    
    t2 = time.time()
    print(termcolor.colored("Time used: %s, Token Usage %d" % (t2 - t1, completion.usage.total_tokens), "yellow"))
    
    return completion.choices[0].message.content

def send_prompt_n(role_prompt:str, user_prompt:str, n:int, model:str = default_model, temperature = 0.9, test_speed:bool = False):
    t1 = time.time()
    if test_speed:
        time.sleep(1)
        return
    
    client = OpenAI(
        base_url=openai_base_url,
        api_key=openai_api_key
    )
    messages = []
    if role_prompt != "":
        messages.append({
                "role": "system",
                "content": role_prompt,
            })

    messages.append({
            "role": "user",
            "content": user_prompt,  
    })
    
    retry_time = RETRY_TIME
    while retry_time > 0:
        try:
            print(termcolor.colored("Sending prompt to OpenAI...", "yellow"))
            completion = client.chat.completions.create(
                model = model,
                temperature = temperature,
                messages = messages,
                max_tokens = 1000,
                n = n,
                seed = global_seed,
            )
            print(termcolor.colored("Received the response successfully!", "yellow"))
            break
        except OpenAIError as e:
            print(termcolor.colored("Error: %s" % e, "red"))
            time.sleep(10)
            retry_time -= 1
    
    if retry_time == 0:
        raise Exception("Failed to send prompt to OpenAI")
    
    # 确保不越界访问choices
    actual_choices = len(completion.choices)
    if actual_choices < n:
        print(termcolor.colored(f"Warning: Requested {n} responses, but only got {actual_choices}", "yellow"))
        n = actual_choices
    
    msglist = [completion.choices[i].message.content for i in range(n)]
    
    t2 = time.time()
    print(termcolor.colored("Time used: %s, Token Usage: %d" % (t2 - t1, completion.usage.total_tokens), "yellow"))
    return msglist
    
def get_score(df:pd.DataFrame, label, model):
    """
    get score in circumstance of train_test_split
    """
    innerdf = df.copy()
    label = label
    train_x, test_x, train_y, test_y = train_test_split(innerdf, label, test_size=0.2, random_state=100)
    
    train_x, val_x, train_y, val_y = train_test_split(train_x, train_y, test_size=0.2, random_state=100)
    model.fit(train_x, train_y.values.ravel(), eval_set=[(val_x, val_y.values.ravel())], callbacks=[lgb.early_stopping(50, verbose=False)])
    imp_list = [(train_x.columns[i], model.feature_importances_[i]) for i in range(len(train_x.columns))]
    imp_list = sorted(imp_list, key=lambda x: x[1], reverse=True)
    pred = pd.DataFrame(model.predict(test_x), index=test_x.index)
    score = roc_auc_score(test_y, pred)
    return score, imp_list

def prepare_df_for_train(df:pd.DataFrame, label=None):
    '''
    convert all the category, object columns in the dataframe to the numerical column
    '''
    if label is not None:
        # drop nan for df and label
        new_df, new_label = df.copy(), label.copy()
        combine = pd.concat([new_df, new_label], axis=1)
        combine.replace([float('inf'), float('-inf')], float('nan'), inplace=True)
        combine.dropna(inplace=True)
        new_df = combine.iloc[:, :-1]
        new_label = combine.iloc[:, -1]
    else:
        new_df, new_label = df.copy(), None
        
    non_numeric_columns = df.select_dtypes(exclude=np.number).columns
    for col in non_numeric_columns:
        new_df[col] = new_df[col].astype('category')
        new_df[col] = new_df[col].cat.codes
        new_df[col] = new_df[col].astype('int64')
    return new_df, new_label


def move_id_to_first(df:pd.DataFrame, id_name:str):
    """
    move the id column to the first column by reindex
    """
    columns = df.columns.tolist()
    new_order = [id_name] + [col for col in columns if col != id_name]
    return df.reindex(columns=new_order) 

def one_minus_rae(y_true, y_pred):
    """
    one minus relative absolute error
    """
    return 1-np.sum(np.abs(y_true - y_pred)) / np.sum(np.abs(y_true - np.mean(y_true)))

def token_num(text:str, model:str = "gpt-3.5-turbo"):
    """
    count the token number of a text for sending to openai
    """
    # encoding = tiktoken.get_encoding("cl100k_base")
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))
