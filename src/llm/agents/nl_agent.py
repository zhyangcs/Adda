import asyncio
from src.llm.utils.llm_util import *
from src.llm.llm_dag_node import *
from src.llm.utils.prompt import *
from .autogen_feature_generator import generate_features_autogen

class NLAgent():
    normal_feature_pre_list = ["new_feature", "detailed description", "brief description", "relevant"]
    high_order_feature_pre_list = ["new_feature", "detailed description", "brief description", "relevant"]
    
    def __init__(self, eval_model_type):
        self.eval_model_type = eval_model_type
    
    def parse_nl_comma(content, pre_list):    
        content_lines_with_end = [line + "^" for line in content.split("\n") if line != "" and ":" in line]
        if len(content_lines_with_end) != len(pre_list):
            print(termcolor.colored(f"Error: the length of content_lines_with_end {len(content_lines_with_end)} is not equal to the length of pre_list {len(pre_list)}", "red"))
            return ""
        res = []
        try:
            for i in range(len(content_lines_with_end)):
                res.append(NLAgent.parse_one_comma(content_lines_with_end[i], pre_list[i]))
        except Exception as e:
            print(termcolor.colored(f"Error: {e}", "red"))
            return ""
        return res
        
    def parse_one_comma(content, prefix):
        """
        The format could be 'prefix': content or 'content', or 'prefix': ['content1', 'content2']
        """
        def get_ans(match):
            if match.group(1) == prefix:
                ans = match.group(2).strip()
            else:
                ans = match.group(1).strip()
            if ans.startswith("[") and ans.endswith("]"):
                ans = ans[1:-1]
            ans = ans.strip(",").strip("'").strip('"')
            if prefix == 'new_feature':
                ans1 = prefix_check(ans)
                print(termcolor.colored(f"new_feature: [{ans1}] from [{ans}]", "yellow"))
                ans = ans1
            return ans.strip()
        pattern = r"""'(.*)':(.*)\^"""
        pattern2 = r'"(.*)":(.*)\^'
        match = re.search(pattern, content, re.DOTALL)
        match2 = re.search(pattern2, content, re.DOTALL)
        if match:
            return get_ans(match)
        elif match2:
            return get_ans(match2)
        else:
            raise ValueError(f"match failed content {content}, regenerating the code")
    
    def check_nl_response(rel_attrs:list, out_attr:str, cur_node:LLMDAGNODE, appear_attrs:list):
        """
        Check two condition for guarantee the validity of the response:
        1. all of the relevant columns in the column_info
        2. the output attribute not appear in the column_info
        """
        all_relevant_contained = all(element in list(cur_node.column_info.keys()) for element in rel_attrs)
        if not all_relevant_contained:
            for element in rel_attrs:
                if element not in list(cur_node.column_info.keys()):
                    print(termcolor.colored(f"CheckNLResponse: {element} not in {cur_node.column_info.keys()}", "yellow"))
        # print(termcolor.colored(f"CheckNLResponse: rel_attrs: {rel_attrs}, all_relevant_contained: {all_relevant_contained}, cur_node column {cur_node.column_info.keys()}", "yellow"))
        out_not_appear = out_attr not in appear_attrs.union(set(cur_node.column_info.keys()))
        print(termcolor.colored(f"CheckNLResponse: all_relevant_contained: {all_relevant_contained}, out_not_appear: {out_not_appear}", "yellow"))
        return all_relevant_contained and out_not_appear    
    
    def get_raw_desc(self, cur_node):
        df_desc = get_column_info(cur_node.column_info, 800, cur_node.attr_imp_order)
        data_desc = f"/* Data description: {df_desc} */"
        whole_prompt = f"{RAW_PROMPT.format(data_desc = data_desc)}"
        return whole_prompt
        
        
    def task_to_desc(self, cur_node:LLMDAGNODE, send_num:int, target_col:str, cur_step_idx:int = 0, high_order_num:int = 2, token_limit:int = 800, example_prompt:str=""):
        print(termcolor.colored(f"[task to features] cur_node: {cur_node.node_id}", "yellow"))
        next_state = []
            
        while True:
            try:
                high_order = False
                print(termcolor.colored(f"[generate feature] cur_node: {cur_node.node_id}", "yellow"))
                
                if cur_step_idx < high_order_num:
                    # we only generate high-order feature for first several step
                    prompt_template = NEXT_STEP_FREE
                    high_order = True
                    send_num = 3
                elif cur_step_idx % 2 == 1 and cur_step_idx < 4:
                    prompt_template = NEXT_STEP_FORMAT
                else:
                    prompt_template = NEXT_STEP_FORMAT_SHRINK
                
                df_desc = get_column_info(cur_node.column_info, token_limit - token_num(prompt_template), cur_node.attr_imp_order)
                data_desc = f"/* Data description: {df_desc} */"    
                whole_prompt = f"{prompt_template.format(data_desc = data_desc, y_attr = target_col, memory_info=example_prompt, model_type = self.eval_model_type)}"
                
                # print(termcolor.colored(f"{whole_prompt}\n Total token: {token_num(whole_prompt)}, Current Token Limitation {token_limit}", "grey"))
                
                # ---------------------------------------------------------------------------------
                # # high_order_model = "gpt-4-turbo"
                # num_to_generate = 3 if high_order else send_num * 2
                num_to_generate = 3
                responses = asyncio.run(generate_features_autogen(whole_prompt, n=num_to_generate))
                print(termcolor.colored(responses, "green"))
                
                # high_order_model = "gpt-4-turbo"
                # responses = send_prompt_n("", whole_prompt, n = 3 if high_order else send_num * 2)
                # print(termcolor.colored(responses, "green"))
                # ---------------------------------------------------------------------------------
                
                cur_attr_set = set()
                for response in responses:
                    # Defensive check: Skip if response is None to prevent AttributeError
                    if response is None:
                        print(termcolor.colored("Warning: Encountered None in responses list, skipping.", "magenta"))
                        continue 
                        
                    parsed_response = NLAgent.parse_nl_comma(response, NLAgent.high_order_feature_pre_list if high_order else NLAgent.normal_feature_pre_list)
                    
                    if parsed_response != "":
                        op_type, out_attr, operation_desc, operation_desc_brief, rel_cols = (OpTypeEnum.UNSUPPORT if high_order else (OpTypeEnum.BINARY if "UNARY" not in parsed_response[0] else OpTypeEnum.DISCRETIZE)), parse_string_to_list(parsed_response[-4]), parsed_response[-3], parsed_response[-2], parse_string_to_list(parsed_response[-1])
                        
                        
                        if NLAgent.check_nl_response(rel_cols, parsed_response[1], cur_node, cur_attr_set):
                            print(out_attr, cur_attr_set, set(cur_node.column_info.keys()), cur_attr_set.union(set(cur_node.column_info.keys())))
                            cur_attr_set.add(*out_attr)     
                            
                            next_node = LLMDAGNODE(allocate_node_id(), "", set(), set(), cur_node.out_cur_df.copy(deep=True), pd.DataFrame(), cur_node.column_info.copy(), "", op_type, pd.DataFrame(), -1, cur_node.whole_code, [], [], None, cur_node.alive, False, cur_node.utility, None, cur_node.attr_embs.clone().detach())
                            
                            # fill the node with the relevant information
                            next_node.op_type = op_type
                            next_node.operation_desc = operation_desc
                            next_node.write_set = set(out_attr)
                            next_node.read_set = set(rel_cols) - next_node.write_set
                            operation_desc_brief = operation_desc_brief
                            for attr in next_node.write_set - set(next_node.column_info.keys()):
                                next_node.column_info[attr] = attr + ": (created in previous step) " + operation_desc_brief + "\n"
                            
                            next_state.append(next_node)
                    
                    if len(next_state) >= send_num:
                        return next_state
                        
                if len(next_state) == 0:
                    # no valid responses
                    raise Exception("Error: no valid response")
            except Exception as e:
                print(e, termcolor.colored(f"Error during feature generation loop: {e}", "red"))
                # If Autogen failed to produce valid responses after retries,
                # break the loop and return the empty next_state.
                if "Error: no valid response" in str(e):
                    print(termcolor.colored("Stopping due to Autogen failing to generate valid responses.", "red"))
                    return next_state # Return empty state instead of looping infinitely
                # For other unexpected errors, maybe still return or re-raise depending on desired behavior
                # For now, we'll also return to prevent hangs.
                print(termcolor.colored("Stopping due to unexpected error.", "red"))
                return next_state # Return empty state