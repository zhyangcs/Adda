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
    import threading
    import concurrent.futures
    
    def call_with_timeout(timeout_seconds):
        """带超时的API调用函数"""
        client = OpenAI(
            base_url=openai_base_url,
            api_key=openai_api_key,
            timeout=min(timeout_seconds, 30.0)  # 设置OpenAI客户端超时
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
        
        completion = client.chat.completions.create(
            model = model,
            temperature = temperature,
            messages = messages,
            max_tokens = 500,
            seed=global_seed
        )
        
        return completion
    
    t1 = time.time()
    if test_speed:
        time.sleep(1)
        return
    
    retry_time = RETRY_TIME
    success = False
    completion = None
    
    while retry_time > 0 and not success:
        try:
            print(termcolor.colored("Sending prompt to OpenAI...", "yellow"))
            
            # 使用线程池实现超时
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(call_with_timeout, 30)
                try:
                    completion = future.result(timeout=30)  # 30秒超时
                    print(termcolor.colored("Received the response successfully!", "yellow"))
                    success = True
                except concurrent.futures.TimeoutError:
                    print(termcolor.colored("Timeout error", "red"))
                    future.cancel()  # 取消任务
                    retry_time -= 1
                    if retry_time > 0:
                        print(termcolor.colored("Retrying in 5 seconds...", "yellow"))
                        time.sleep(5)
                    continue
                
        except OpenAIError as e:
            print(termcolor.colored("OpenAI Error: %s" % e, "red"))
            retry_time -= 1
            if retry_time > 0:
                print(termcolor.colored("Retrying in 10 seconds...", "yellow"))
                time.sleep(10)
                
        except Exception as e:
            print(termcolor.colored(f"Unexpected error: {e}", "red"))
            retry_time -= 1
            if retry_time > 0:
                time.sleep(5)
    
    if not success:
        print(termcolor.colored("Failed to send prompt to OpenAI after all retries", "red"))
        return None
    
    t2 = time.time()
    print(termcolor.colored("Time used: %s, Token Usage %d" % (t2 - t1, completion.usage.total_tokens), "yellow"))
    
    return completion.choices[0].message.content

def send_prompt_n(role_prompt:str, user_prompt:str, n:int, model:str = default_model, temperature = 0.9, test_speed:bool = False):
    """
    发送提示并获取 n 个响应
    由于某些 API（如 DeepSeek）不支持 n > 1 参数，这里采用并行调用的方式
    """
    import concurrent.futures

    def single_api_call(index):
        """单次API调用函数，返回 (index, response_text, tokens) 或 (index, None, 0)"""
        client = OpenAI(
            base_url=openai_base_url,
            api_key=openai_api_key,
            timeout=30.0
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
                print(termcolor.colored(f"Sending prompt {index+1}/{n} to OpenAI...", "yellow"))
                
                completion = client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    messages=messages,
                    max_tokens=1000,
                    seed=global_seed + index,  # 使用不同的seed获取不同响应
                )
                
                print(termcolor.colored(f"Received response {index+1}/{n} successfully!", "yellow"))
                return (index, completion.choices[0].message.content, completion.usage.total_tokens)
                
            except OpenAIError as e:
                print(termcolor.colored(f"OpenAI Error for request {index+1}/{n}: {e}", "red"))
                retry_time -= 1
                if retry_time > 0:
                    print(termcolor.colored(f"Retrying request {index+1}/{n} in 10 seconds...", "yellow"))
                    time.sleep(10)
                    
            except Exception as e:
                print(termcolor.colored(f"Unexpected error for request {index+1}/{n}: {e}", "red"))
                retry_time -= 1
                if retry_time > 0:
                    time.sleep(5)
        
        print(termcolor.colored(f"Failed to get response {index+1}/{n} after all retries", "red"))
        return (index, None, 0)

    t1 = time.time()
    if test_speed:
        time.sleep(1)
        return []

    # 并行调用多个API请求
    msglist = [None] * n
    total_tokens = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(n, 5)) as executor:
        # 提交所有任务
        futures = [executor.submit(single_api_call, i) for i in range(n)]
        
        # 收集结果
        for future in concurrent.futures.as_completed(futures):
            try:
                index, response, tokens = future.result()
                if response is not None:
                    msglist[index] = response
                    total_tokens += tokens
            except Exception as e:
                print(termcolor.colored(f"Error collecting result: {e}", "red"))
    
    # 过滤掉失败的请求
    msglist = [msg for msg in msglist if msg is not None]
    
    t2 = time.time()
    successful_count = len(msglist)
    print(termcolor.colored(
        f"Time used: {t2 - t1:.2f}s, Total Token Usage: {total_tokens}, "
        f"Responses: {successful_count}/{n}", 
        "yellow"
    ))
    
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

def token_num(text:str, model:str = default_model):
    """
    count the token number of a text for sending to openai
    """
    try:
        # 尝试使用模型特定的tokenizer
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # 如果无法识别模型（如deepseek-chat），使用通用的cl100k_base编码
        # 这是GPT-4使用的编码，与DeepSeek兼容
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))
