import asyncio
import re
import termcolor
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
        
        
    def task_to_desc(self, cur_node:LLMDAGNODE, send_num:int, target_col:str, cur_step_idx:int = 0, high_order_num:int = 2, token_limit:int = 800, example_prompt:str="", stats_summary:str="", global_plan:str=""):
        print(termcolor.colored(f"[task to features] cur_node: {cur_node.node_id}", "yellow"))
        next_state = []
        max_retries = 3
        retry_count = 0

        high_order = cur_step_idx < high_order_num

        while retry_count < max_retries:
            retry_count += 1
            print(termcolor.colored(f"Attempt {retry_count}/{max_retries} to generate features for node {cur_node.node_id}", "blue"))
            try:
                if cur_step_idx < high_order_num:
                    prompt_template = NEXT_STEP_FREE
                elif cur_step_idx % 2 == 1 and cur_step_idx < 4:
                    prompt_template = NEXT_STEP_FORMAT
                else:
                    prompt_template = NEXT_STEP_FORMAT_SHRINK
                
                fixed_prompt_tokens = token_num(prompt_template.format(data_desc="", y_attr="", memory_info="", model_type=""))
                summary_tokens = token_num(stats_summary)
                example_tokens = token_num(example_prompt)
                plan_tokens = token_num(global_plan)
                available_for_desc = token_limit - fixed_prompt_tokens - summary_tokens - example_tokens - plan_tokens - 150
                df_desc = get_column_info(cur_node.column_info, max(200, available_for_desc), cur_node.attr_imp_order)
                data_desc = f"/* Data description:\n{df_desc}\n*/"
                
                advanced_stats_section = ""
                if stats_summary:
                     advanced_stats_section = f"\n\n/*\nAdvanced Statistics Summary (based on CURRENT data sample):\n{stats_summary}\n*/"

                global_plan_section = ""
                if global_plan:
                    global_plan_section = f"\n\n/*\nOverall Feature Strategy/Plan:\n{global_plan}\n*/"

                whole_prompt = f"{prompt_template.format(data_desc = data_desc, y_attr = target_col, memory_info=example_prompt, model_type = self.eval_model_type)}{advanced_stats_section}{global_plan_section}"
                print(termcolor.colored(f"Prompt Token Estimate: ~{token_num(whole_prompt)} / {token_limit}", "grey"))
                if token_num(whole_prompt) > token_limit:
                     print(termcolor.colored("Warning: Estimated prompt tokens exceed limit.", "yellow"))

                num_to_generate = send_num
                responses = asyncio.run(generate_features_autogen(whole_prompt, n=num_to_generate))
                print(termcolor.colored(f"Autogen Raw Responses (Attempt {retry_count}): {responses}", "green"))
                
                cur_attr_set = set()
                for response_block in responses:
                    if response_block is None or not isinstance(response_block, str) or response_block.strip() == "":
                        print(termcolor.colored("Warning: Encountered None or invalid response block in list, skipping.", "magenta"))
                        continue

                    feature_dict = {}
                    lines = response_block.strip().split('\n')
                    try:
                        for line in lines:
                            line = line.strip()
                            if ':' not in line:
                                continue

                            key_str, value_str = line.split(':', 1)
                            key = key_str.strip().strip("'\"")

                            value_str = value_str.strip()
                            value = None

                            if value_str.startswith('[') and value_str.endswith(']'):
                                elements = re.findall(r"['\"]([^'\"]+)['\"]", value_str)
                                value = [elem.strip() for elem in elements]
                                if key == 'new_feature':
                                    value = [prefix_check(v) for v in value]
                            else:
                                value = value_str.strip().strip("'\"")

                            feature_dict[key] = value

                        out_attr = feature_dict.get('new_feature')
                        operation_desc = feature_dict.get('detailed description')
                        operation_desc_brief = feature_dict.get('brief description')
                        rel_cols = feature_dict.get('relevant')

                        if not out_attr or not isinstance(out_attr, list):
                            print(termcolor.colored(f"Warning: Missing or invalid 'new_feature' list in block: {response_block}", "yellow"))
                            continue
                        if not operation_desc or not isinstance(operation_desc, str):
                            print(termcolor.colored(f"Warning: Missing or invalid 'detailed description' string in block: {response_block}", "yellow"))
                            continue
                        if not operation_desc_brief or not isinstance(operation_desc_brief, str):
                             print(termcolor.colored(f"Warning: Missing or invalid 'brief description' string in block: {response_block}", "yellow"))
                             continue
                        if not rel_cols or not isinstance(rel_cols, list):
                            print(termcolor.colored(f"Warning: Missing or invalid 'relevant' list in block: {response_block}", "yellow"))
                            continue

                        op_type = OpTypeEnum.UNSUPPORT if high_order else OpTypeEnum.APPLY

                        if NLAgent.check_nl_response(rel_cols, out_attr[0], cur_node, cur_attr_set):
                            print(f"Valid response parsed: {out_attr}")
                            cur_attr_set.add(*out_attr)

                            next_node = LLMDAGNODE(allocate_node_id(), "", set(), set(), None, None, cur_node.column_info.copy(), "", op_type, pd.DataFrame(), -1, "", [], [], None, cur_node.alive, False, cur_node.utility, None, cur_node.attr_embs.clone().detach() if cur_node.attr_embs is not None else None)

                            next_node.operation_desc = [operation_desc]
                            next_node.operation_desc_brief = operation_desc_brief
                            next_node.write_set = set(out_attr)
                            next_node.read_set = set(rel_cols) - next_node.write_set
                            for attr in next_node.write_set:
                                if attr not in next_node.column_info:
                                    next_node.column_info[attr] = f"{attr}: (Created) {operation_desc_brief}\n"

                            next_state.append(next_node)
                        else:
                             print(termcolor.colored(f"Warning: Failed nl_response check for output '{out_attr[0]}' or relevant columns {rel_cols}", "yellow"))

                    except Exception as parse_error:
                         print(termcolor.colored(f"Error parsing feature block: '{response_block}'. Error: {parse_error}", "red"))
                         import traceback
                         traceback.print_exc()
                         continue

                if len(next_state) < num_to_generate:
                     print(termcolor.colored(f"Warning: Attempt {retry_count} generated only {len(next_state)}/{num_to_generate} valid features.", "yellow"))

                if len(next_state) >= num_to_generate:
                    print(termcolor.colored(f"Collected {len(next_state)} valid features, returning.", "green"))
                    return next_state

            except Exception as e:
                print(termcolor.colored(f"Error in task_to_desc outer loop (Attempt {retry_count}): {e}", "red"))
                import traceback
                traceback.print_exc()

        print(termcolor.colored(f"Failed to generate sufficient valid features after {max_retries} attempts. Returning {len(next_state)} features found.", "red"))
        return next_state