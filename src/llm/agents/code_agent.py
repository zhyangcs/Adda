from src.llm.utils.llm_util import *
from src.llm.llm_dag_node import *
from src.pg.sql_utils import *
from src.llm.utils.parse_util import *
from src.llm.utils.prompt import *
import numpy as np
import pandas as pd
from src.env import *

class CodeAgent():
    def __init__(self):
        pass

    def check_self_consistency(self, all_df:list, write_set:list):
        """
        check the self-consistency of the generated code: whether the majority answer is appear larger than 2/3 of the whole answer
        """
        if len(all_df) == 0:
            return False
        # for attr in write_set:
        #     if not all([np.isclose(df[attr], all_df[0][attr]).all() for df in all_df]):
        #         return False
        result_map = {}
        for df in all_df:
            values = hash(str(df[write_set].values))
            if values not in result_map.keys():
                result_map[values] = 1
            else:
                result_map[values] += 1
        return max(result_map.values()) > 2 * len(all_df) / 3
        

    def validate_code_executable(df:pd.DataFrame, code:str):
        """
        validate the code could be executed in the given dataframe
        return: True if the code is executable, False otherwise, and the df after executing
        """
        new_df = df.copy(deep=True)
        exec_env = {'df': new_df}
        try:
            exec(code, exec_env)
            return True, exec_env['df']
        except Exception as e:
            print(termcolor.colored(f"Code Execution Error: {e}"))
            return False, df
    
    def feature_to_code(self, cur_node:LLMDAGNODE, final_op_desc = ""):
        """
        Generate the code for the current node from the NL generated from the NLAgent
        return: True if the code is generated successfully, False otherwise
        """
        print(termcolor.colored(f"[feature to code] cur_node: {cur_node.node_id}", "yellow"))
        # 1. generate the relevant code from the llm
        detail_desc = []
        for key in list(cur_node.read_set):
            if key in cur_node.column_info.keys():
                detail_desc.append(f"{key}: {cur_node.column_info[key]}")
            else:
                detail_desc.append(f"{key}: (created for intermediate steps)")
        # detail_desc = "".join([f"{key}: {value}" for key, value in cur_node.column_info.items() if key in cur_node.read_set])
        prompt_str = f"""{CONVERT_FUNCTION_PROMPT.format(output_attrs = cur_node.write_set, input_attrs = cur_node.read_set, op_desc = cur_node.operation_desc, input_desc = "".join(detail_desc))}\n"""
        # prompt_str = f"""{extractor_function_prompt.format(output_attrs = cur_node.write_set, input_attrs = cur_node.read_set, op_desc = cur_node.operation_desc, input_desc = "".join(detail_desc), final_op_desc = final_op_desc)}"""
        # print(termcolor.colored(prompt_str, "grey"))
        
        retry_times = TOTAL_RETRY_TIMES
        while retry_times > 0:
            parsed_code = parse_code(send_prompt("", prompt_str), language='python')
            print(termcolor.colored(parsed_code, "green"))
            cur_node.task_code = parsed_code

            # 2. execute the relevant code
            success, new_df = CodeAgent.validate_code_executable(cur_node.in_cur_df, parsed_code)
            if success:
                cur_node.out_cur_df = new_df
                if cur_node.op_type != OpTypeEnum.UNSUPPORT:
                    # check whether the code could be SQLization, if not, then return False
                    if not check_SQLization(parsed_code, cur_node.in_cur_df):
                        return False
                return True
            else:
                retry_times -= 1
                
        return False
    
    def generate_fixing_features(self, cur_node:LLMDAGNODE, labels:list):
        """
        from the main feature, we generate the fixing features[normalization, fillna]
        """
        print(termcolor.colored(f"[generate fixing features] cur_node: {cur_node.node_id}", "yellow"))
        df_desc = get_df_desc_prompt(cur_node.out_cur_df, 20, labels, cur_node.read_set, cur_node.task_code, cur_node.column_info)
        whole_prompt = f"{GENERATE_FIX_FEATURE_PROMPT.format(df_desc = df_desc, output_attr = cur_node.write_set)}"
        # print(termcolor.colored(whole_prompt, "grey"))
        
        retry_time = TOTAL_RETRY_TIMES
        while retry_time > 0:
            try:
                responses = send_prompt_n("", whole_prompt, 1)
                print(termcolor.colored(responses, "green"))
                for response in responses:
                    ret = parse_fix_feature(response)
                    # filter the useless head
                    ret = [pair for pair in ret if pair[0] == "No need to preprocess" or pair[0] == "Fill NaN" or pair[0] == "Normalization" or pair[0] == "Label encoding"]
                    if len(ret) == 0:
                        return True
                    else:
                        replace_map = {}
                        # do the relevant operation
                        for pair in ret:
                            op_type_str, origin_col = pair[0], pair[1]
                            if origin_col in list(cur_node.in_cur_df.columns):
                                code, new_col = CodeAgent.fixing_msg_to_code(op_type_str, origin_col) 
                                replace_map[op_type_str] = (origin_col, new_col)
                                
                                if code == "no need":
                                    return True
                                if code != "":
                                    success, new_df = CodeAgent.validate_code_executable(cur_node.out_cur_df, code)
                                    if not success:
                                        raise Exception("Error: Fixing Code execution Fail")
                                    cur_node.out_cur_df = new_df
                                    op_type = parse_str_to_OPTypeEnum(op_type_str)
                                    cur_fixing_node = LLMDAGNODE(allocate_node_id(), code, {origin_col}, {new_col}, pd.DataFrame(), pd.DataFrame(), None, "", op_type, pd.DataFrame(), -1, None, [], [], None, True, False, -1, None)
                                    cur_node.fixing_node.append(cur_fixing_node)

                        self.reformat_code(cur_node, replace_map)
                        return True
            except Exception as e:
                print(termcolor.colored(f"Error:regrenerate the code in fixing: {e}", "red"))
                retry_time -= 1
        return False
    
    def reformat_code(self, cur_node:LLMDAGNODE, replace_map:dict):
        """
        1. exec the fixing code
        2. exec the reformatted core code
        """
        print(termcolor.colored(f"[reformat code] cur_node: {cur_node.node_id}, {cur_node.task_code} {replace_map.values()}", "yellow"))
        cur_df = cur_node.in_cur_df
        for fixing_node in cur_node.fixing_node:
            success, cur_df = CodeAgent.validate_code_executable(cur_df, fixing_node.task_code)
            if not success:
                raise Exception("Error: Fixing Code execution Fail")
        
        code = cur_node.task_code
        for (origin_key, new_key) in replace_map.values():
            # only replace 'origin_key' with 'new_key' in the code
            code = code.replace(f"'{origin_key}'", f"'{new_key}'")
        success, cur_node.out_cur_df = CodeAgent.validate_code_executable(cur_df, code)
        if not success:
            raise Exception("Error: Code Reformat Fail")
        cur_node.task_code = code     
        
    def fixing_msg_to_code(op_type:str, col_name:str):
        """
        convert the fixing operation to code
        """
        if op_type == "No need to preprocess":
            return "no need", ""
        elif op_type == "Fill NaN":
            new_col_name = col_name + "_Fillna"
            return "df['%s'] = df['%s'].fillna(df['%s'].mode()[0])" %(new_col_name, col_name, col_name), new_col_name
        elif op_type == "Normalization":
            new_col_name = col_name + "_Norm"
            return """from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
df['%s'] = scaler.fit_transform(df[['%s']])""" %(new_col_name, col_name), new_col_name
        elif op_type == "Label encoding":
            new_col_name = col_name + "_Label"
            return """from sklearn.preprocessing import LabelEncoder
label_encoder = LabelEncoder()
df['%s'] = label_encoder.fit_transform(df[['%s']])""" %(new_col_name, col_name), new_col_name
        return "", ""
    
    def subtask_to_code(self, cur_node:LLMDAGNODE, final_op_desc = ""):
        """
        Generate the code for the current node from the NL generated from the NLAgent
        return: (whether self-consistency, whether all code execute successfully)
        """
        print(termcolor.colored(f"[generate subcode] cur_node: {cur_node.node_id}", "yellow"))
        # 1. generate the relevant code from the llm
        detail_desc = []
        for key in list(cur_node.read_set):
            if key in cur_node.column_info.keys():
                detail_desc.append(f"{key}: {cur_node.column_info[key]}")
            else:
                detail_desc.append(f"{key}: (created for intermediate steps)")
        prompt_str = f"""{SPLIT_CONVERT_FUNCTION_PROMPT.format(output_attrs = cur_node.write_set, input_attrs = cur_node.read_set, op_desc = cur_node.operation_desc, input_desc = "".join(detail_desc))}"""#, final_op_desc = final_op_desc)}"""
        # print(termcolor.colored(prompt_str, "grey"))
        
        retry_times = TOTAL_RETRY_TIMES
        while retry_times > 0:
            parsed_codes = [parse_code(code) for code in send_prompt_n("", prompt_str, 4)]
            print(termcolor.colored(f"{parsed_codes[0]}\n-----\n{parsed_codes[1]}\n----\n{parsed_codes[2]}\n", "green"))
            all_df = []
            for parsed_code in parsed_codes:                
                # 2. execute the relevant code
                success, new_df = CodeAgent.validate_code_executable(cur_node.in_cur_df, parsed_code)
                if success:
                    all_df.append(new_df)
                    cur_node.out_cur_df = new_df
                    cur_node.task_code = parsed_code
                else:
                    retry_times -= 1
                    break
            # 3. check for the self-consistency
            is_consistency = self.check_self_consistency(all_df, list(cur_node.write_set))
            
            
            if not success:
                retry_times -= 1
                continue
            break    
                
        return is_consistency, success