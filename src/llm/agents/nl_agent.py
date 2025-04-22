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
        
        
    def task_to_desc(self, cur_node:LLMDAGNODE, send_num:int, target_col:str, cur_step_idx:int = 0, high_order_num:int = 2, token_limit:int = 800, example_prompt:str="", stats_summary:str=""):
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
                
                # Estimate tokens used by static parts + summary + examples
                fixed_prompt_tokens = token_num(prompt_template.format(data_desc="", y_attr="", memory_info="", model_type=""))
                summary_tokens = token_num(stats_summary)
                example_tokens = token_num(example_prompt)
                # Allocate remaining tokens to basic data description, leaving some buffer
                available_for_desc = token_limit - fixed_prompt_tokens - summary_tokens - example_tokens - 150 # Add buffer
                df_desc = get_column_info(cur_node.column_info, max(200, available_for_desc), cur_node.attr_imp_order) # Ensure minimum desc token count
                data_desc = f"/* Data description:\\n{df_desc}\\n*/"
                
                # Construct the advanced stats section (if available)
                advanced_stats_section = ""
                if stats_summary:
                     advanced_stats_section = f"\\n\\n/*\\nAdvanced Statistics Summary (based on data sample):\\n{stats_summary}\\n*/"
                
                # Combine all parts for the final prompt
                whole_prompt = f"{prompt_template.format(data_desc = data_desc, y_attr = target_col, memory_info=example_prompt, model_type = self.eval_model_type)}{advanced_stats_section}" # Append stats summary
                print(termcolor.colored(f"Prompt Token Estimate: ~{token_num(whole_prompt)} / {token_limit}", "grey"))
                if token_num(whole_prompt) > token_limit:
                     print(termcolor.colored("Warning: Estimated prompt tokens exceed limit. Content may be truncated by LLM.", "yellow"))
                
                # Call Autogen Feature Generator
                # num_to_generate = send_num # Request 'send_num' valid features eventually
                num_to_generate = 1
                # The generate_features_autogen itself handles retries if it fails internally
                responses = asyncio.run(generate_features_autogen(whole_prompt, n=num_to_generate)) # generate_features_autogen internally aims for n
                print(termcolor.colored(f"Autogen Raw Responses: {responses}", "green"))
                
                cur_attr_set = set()
                for response in responses:
                    if response is None or not isinstance(response, str) or response.strip() == "":
                        print(termcolor.colored("Warning: Encountered None or invalid response in list, skipping.", "magenta"))
                        continue

                    try: # Add try-except around parsing individual responses
                        parsed_response = NLAgent.parse_nl_comma(response, NLAgent.high_order_feature_pre_list if high_order else NLAgent.normal_feature_pre_list)

                        if parsed_response and len(parsed_response) >= 4: # Ensure enough parts after parsing
                            # Determine op_type based on high_order flag, not content
                            op_type = OpTypeEnum.UNSUPPORT if high_order else OpTypeEnum.COMBINE # Default to COMBINE if not high_order

                            # Map parsed parts correctly (assuming standard order)
                            out_attr = parse_string_to_list(parsed_response[0]) # 'new_feature' expected first
                            operation_desc = parsed_response[1] # 'detailed description'
                            operation_desc_brief = parsed_response[2] # 'brief description'
                            rel_cols = parse_string_to_list(parsed_response[3]) # 'relevant'

                            if NLAgent.check_nl_response(rel_cols, out_attr[0], cur_node, cur_attr_set): # Check using the first output attr name
                                print(f"Valid response parsed: {out_attr}")
                                cur_attr_set.add(*out_attr)

                                # Create the node (without out_cur_df, which will be computed later)
                                next_node = LLMDAGNODE(allocate_node_id(), "", set(), set(), None, None, cur_node.column_info.copy(), "", op_type, pd.DataFrame(), -1, "", [], [], None, cur_node.alive, False, cur_node.utility, None, cur_node.attr_embs.clone().detach() if cur_node.attr_embs is not None else None)

                                # Fill node details
                                next_node.operation_desc = [operation_desc] # Store as list
                                next_node.write_set = set(out_attr)
                                next_node.read_set = set(rel_cols) - next_node.write_set
                                # Add new column info based on brief description
                                for attr in next_node.write_set:
                                    if attr not in next_node.column_info: # Avoid overwriting if somehow exists
                                        next_node.column_info[attr] = f"{attr}: (Created) {operation_desc_brief}\\n"

                                next_state.append(next_node)
                        else:
                            print(termcolor.colored(f"Warning: Failed to parse response or not enough parts: {response}", "yellow"))

                    except Exception as parse_error:
                         print(termcolor.colored(f"Error parsing response: '{response}'. Error: {parse_error}", "red"))
                         continue # Skip this response

                    if len(next_state) >= send_num:
                        print(termcolor.colored(f"Collected {len(next_state)} valid features, returning.", "green"))
                        return next_state # Exit outer loop once enough valid features are collected

                # If loop finishes without reaching send_num valid features
                if not next_state:
                    print(termcolor.colored("Autogen failed to generate any valid features after processing responses.", "red"))
                    # No need to raise Exception("Error: no valid response") here,
                    # just return the empty list, A* search will handle it.
                    return next_state
                else:
                     print(termcolor.colored(f"Autogen generated {len(next_state)} valid features (less than requested {send_num}), returning.", "yellow"))
                     return next_state # Return the valid ones found

            except Exception as e:
                print(termcolor.colored(f"Error in task_to_desc outer loop: {e}", "red"))
                import traceback
                traceback.print_exc()
                # Prevent infinite loops in case of unexpected errors
                return next_state # Return whatever was collected so far (likely empty)