from src.llm.utils.llm_util import *
from src.llm.llm_dag_node import *
from src.llm.utils.prompt import *
from src.llm.agent_status_wrapper import agent_status_wrapper

class NLAgent():
    normal_feature_pre_list = ["new_feature", "detailed description", "brief description", "relevant"]
    high_order_feature_pre_list = ["new_feature", "detailed description", "brief description", "relevant"]
    
    def __init__(self, eval_model_type, status_wrapper=None):
        self.eval_model_type = eval_model_type
        self.status_wrapper = status_wrapper or agent_status_wrapper

    @staticmethod
    def _truncate_text(text: str, max_chars: int = 150) -> str:
        if text is None:
            return text
        text = str(text)
        if "```" in text:
            return text
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "...(truncated)"
    
    @staticmethod
    def parse_nl_comma(content, pre_list):    
        """
        Parse natural language response with enhanced error handling
        """
        print(termcolor.colored(f"=== 开始解析响应 ===", "blue"))
        print(termcolor.colored(f"期望字段: {pre_list}", "blue"))
        print(termcolor.colored(f"响应内容:\n{content}", "blue"))
        
        # 按行分割，查找包含冒号的行
        content_lines_with_end = [line + "^" for line in content.split("\n") if line != "" and ":" in line]
        
        print(termcolor.colored(f"找到的带冒号行数: {len(content_lines_with_end)}", "blue"))
        print(termcolor.colored(f"期望行数: {len(pre_list)}", "blue"))
        
        if len(content_lines_with_end) != len(pre_list):
            print(termcolor.colored(f"警告: 行数不匹配！期望{len(pre_list)}行，实际{len(content_lines_with_end)}行", "yellow"))
            print(termcolor.colored("内容预览:", "yellow"))
            for i, line in enumerate(content_lines_with_end):
                print(termcolor.colored(f"  Line {i+1}: {line}", "yellow"))
            
            # 如果行数不匹配，尝试继续解析可用的行
            if len(content_lines_with_end) < len(pre_list):
                print(termcolor.colored("尝试解析可用的行...", "yellow"))
                # 填充缺失的行
                while len(content_lines_with_end) < len(pre_list):
                    content_lines_with_end.append("")
            else:
                # 如果行数过多，截取前几行
                print(termcolor.colored("截取到期望的行数...", "yellow"))
                content_lines_with_end = content_lines_with_end[:len(pre_list)]
        
        res = []
        successful_parses = 0
        
        try:
            for i in range(len(pre_list)):
                print(termcolor.colored(f"\n--- 解析字段 {i+1}: {pre_list[i]} ---", "blue"))
                
                if i < len(content_lines_with_end) and content_lines_with_end[i]:
                    print(termcolor.colored(f"行内容: {content_lines_with_end[i]}", "blue"))
                    
                    try:
                        parsed = NLAgent.parse_one_comma(content_lines_with_end[i], pre_list[i])
                        res.append(parsed)
                        successful_parses += 1
                        print(termcolor.colored(f"✅ 成功解析: {parsed}", "green"))
                    except Exception as e:
                        print(termcolor.colored(f"❌ 解析失败: {e}", "red"))
                        res.append("")  # 添加空值保持列表长度
                else:
                    print(termcolor.colored(f"❌ 缺少内容", "yellow"))
                    res.append("")  # 添加空值保持列表长度
            
            print(termcolor.colored(f"\n=== 解析完成: {successful_parses}/{len(pre_list)} 字段成功 ===", "blue"))
            print(termcolor.colored(f"最终结果: {res}", "blue"))
            
            # 如果所有字段都解析失败，返回空字符串
            if successful_parses == 0:
                print(termcolor.colored("所有字段都解析失败，返回空结果", "red"))
                return ""
            
            return res
            
        except Exception as e:
            print(termcolor.colored(f"解析过程中发生严重错误: {e}", "red"))
            return ""
        
    @staticmethod
    def parse_one_comma(content, prefix):
        """
        The format could be 'prefix': content or 'content', or 'prefix': ['content1', 'content2']
        Enhanced to handle multiple format variations
        """
        print(termcolor.colored(f"  尝试解析字段: {prefix}", "blue"))
        print(termcolor.colored(f"  行内容: {content}", "blue"))
        
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
        
        # 尝试多种正则表达式模式，从严格到宽松
        patterns = [
            # 严格格式：'field': value 或 "field": value
            r"""['"]?([^'":]+)['"]?\s*:\s*(.*)\^""",
            r"""['"]?([^'":]+)['"]?\s*:\s*(.*)""",
            # 宽松格式：field: value 或 field : value
            r"""([^:]+)\s*:\s*(.*)""",
        ]
        
        for i, pattern in enumerate(patterns):
            print(termcolor.colored(f"  尝试模式 {i+1}: {pattern}", "blue"))
            try:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    print(termcolor.colored(f"  ✅ 模式 {i+1} 匹配成功", "green"))
                    print(termcolor.colored(f"  组1: '{match.group(1)}'", "green"))
                    print(termcolor.colored(f"  组2: '{match.group(2)}'", "green"))
                    
                    # 验证匹配的字段名是否与期望的prefix匹配
                    field_name = match.group(1).strip().strip("'").strip('"')
                    if field_name == prefix:
                        print(termcolor.colored(f"  ✅ 字段名匹配: {field_name} == {prefix}", "green"))
                        result = get_ans(match)
                        print(termcolor.colored(f"  ✅ 解析结果: {result}", "green"))
                        return result
                    # 如果第一个组不匹配，尝试第二个组
                    elif match.group(2) and match.group(2).strip():
                        # 检查第二个组是否包含prefix
                        if prefix in match.group(2):
                            print(termcolor.colored(f"  ✅ 在组2中找到prefix: {prefix}", "green"))
                            # 重新构造匹配对象
                            result = get_ans(match)
                            print(termcolor.colored(f"  ✅ 解析结果: {result}", "green"))
                            return result
                    else:
                        print(termcolor.colored(f"  ❌ 字段名不匹配: {field_name} != {prefix}", "yellow"))
                else:
                    print(termcolor.colored(f"  ❌ 模式 {i+1} 匹配失败", "yellow"))
            except Exception as e:
                print(termcolor.colored(f"  ❌ 模式 {i+1} 执行异常: {e}", "red"))
                continue
        
        # 如果所有正则表达式都失败，尝试简单的冒号分割作为最后的备选方案
        print(termcolor.colored(f"  尝试备选方案: 冒号分割", "blue"))
        try:
            if ':' in content:
                parts = content.split(':', 1)
                if len(parts) == 2:
                    field_part = parts[0].strip().strip("'").strip('"')
                    value_part = parts[1].strip().strip("^").strip()
                    
                    print(termcolor.colored(f"  分割结果: field='{field_part}', value='{value_part}'", "blue"))
                    
                    # 检查字段名是否匹配
                    if field_part == prefix:
                        print(termcolor.colored(f"  ✅ 备选方案成功: 字段名匹配", "green"))
                        return value_part
                    # 或者检查值部分是否包含prefix
                    elif prefix in value_part:
                        print(termcolor.colored(f"  ✅ 备选方案成功: 值包含prefix", "green"))
                        return value_part
                    else:
                        print(termcolor.colored(f"  ❌ 备选方案失败: 字段名和值都不匹配", "yellow"))
        except Exception as e:
            print(termcolor.colored(f"  ❌ 备选方案异常: {e}", "red"))
        
        # 如果所有方法都失败，记录详细信息并抛出异常
        print(termcolor.colored(f"  ❌ 所有解析方法都失败", "red"))
        print(termcolor.colored(f"  内容: '{content}'", "red"))
        print(termcolor.colored(f"  期望字段: '{prefix}'", "red"))
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
        """
        将任务描述转换为特征节点
        
        参数:
            cur_node: 当前节点
            send_num: 需要生成的特征数量
            target_col: 目标列名
            cur_step_idx: 当前特征生成阶数
            high_order_num: 高阶特征的最大阶数
            token_limit: LLM的token限制
            example_prompt: 示例提示词
        """
        print(termcolor.colored(f"[task to features] cur_node: {cur_node.node_id}", "yellow"))
        next_state = []  # 存储生成的新节点

        if self.status_wrapper:
            self.status_wrapper.send_agent_status({
                "type": "agent_status",
                "agent": "mainagent",
                "status": "working",
                "work_type": "nl_agent",
                "details": {
                    "node_id": cur_node.node_id,
                    "step_index": cur_step_idx,
                    "requested": send_num
                }
            })
            self.status_wrapper.send_agent_thinking({
                "type": "agent_thinking",
                "agent": "mainagent",
                "thinking": self._truncate_text(f"NLAgent: preparing prompts for node {cur_node.node_id}.")
            })
            
        while True:
            try:
                # TODO: 1. 添加一个使用LLM Agent的Planner；2.使用该Planner为每次特征节点生成提供不同的指导
                high_order = False
                print(termcolor.colored(f"[generate feature] cur_node: {cur_node.node_id}", "yellow"))
                
                # 根据当前阶数选择不同的提示词模板
                if cur_step_idx < high_order_num:
                    # 在前几步生成高阶特征
                    prompt_template = NEXT_STEP_FREE
                    high_order = True
                    send_num = 3
                elif cur_step_idx % 2 == 1 and cur_step_idx < 4:
                    # 在特定步骤使用格式化提示词
                    prompt_template = NEXT_STEP_FORMAT
                else:
                    # 其他情况使用简化提示词
                    prompt_template = NEXT_STEP_FORMAT_SHRINK
                
                # 获取数据描述，考虑token限制
                df_desc = get_column_info(cur_node.column_info, token_limit - token_num(prompt_template), cur_node.attr_imp_order)
                data_desc = f"/* Data description: {df_desc} */"    
                whole_prompt = f"{prompt_template.format(data_desc = data_desc, y_attr = target_col, memory_info=example_prompt, model_type = self.eval_model_type)}"

                # 如果经过global_planner处理，加上global_planner的建议
                if cur_node.planner_suggest != "":
                    whole_prompt += f"/* user suggestion: {cur_node.planner_suggest} */"

                print(termcolor.colored(whole_prompt, "white"))
                
                # 发送提示词到LLM获取响应
                print(termcolor.colored("🚀 准备调用send_prompt_n...", "yellow"))
                responses = send_prompt_n("", whole_prompt, n = 3 if high_order else send_num * 2)
                print(termcolor.colored(f"✅ send_prompt_n调用完成，返回类型: {type(responses)}", "yellow"))
                print(termcolor.colored(f"✅ responses长度: {len(responses) if responses else 'None'}", "yellow"))
                print(termcolor.colored(f"✅ responses内容: {responses}", "yellow"))
                
                print(termcolor.colored("=== API原始回答 ===", "cyan"))
                for i, response in enumerate(responses):
                    print(termcolor.colored(f"响应 {i+1}:", "cyan"))
                    print(termcolor.colored(response, "cyan"))
                    print(termcolor.colored("---", "cyan"))
                print(termcolor.colored(responses, "green"))
                
                # 处理每个响应
                cur_attr_set = set()  # 记录已生成的特征名
                for i, response in enumerate(responses):
                    print(termcolor.colored(f"处理响应 {i+1}", "magenta"))
                    # 解析自然语言响应
                    parsed_response = NLAgent.parse_nl_comma(response, NLAgent.high_order_feature_pre_list if high_order else NLAgent.normal_feature_pre_list)
                    print(termcolor.colored(f"解析结果: {parsed_response}", "magenta"))
                    
                    if parsed_response != "":
                        # 解析操作类型、输出属性、操作描述等
                        op_type, out_attr, operation_desc, operation_desc_brief, rel_cols = (OpTypeEnum.UNSUPPORT if high_order else (OpTypeEnum.BINARY if "UNARY" not in parsed_response[0] else OpTypeEnum.DISCRETIZE)), parse_string_to_list(parsed_response[-4]), parsed_response[-3], parsed_response[-2], parse_string_to_list(parsed_response[-1])
                        
                        # 检查响应是否有效
                        if NLAgent.check_nl_response(rel_cols, parsed_response[1], cur_node, cur_attr_set):
                            print(out_attr, cur_attr_set, set(cur_node.column_info.keys()), cur_attr_set.union(set(cur_node.column_info.keys())))
                            cur_attr_set.add(*out_attr)     
                            
                            # 创建新节点
                            next_node = LLMDAGNODE(allocate_node_id(), "", set(), set(), cur_node.out_cur_df.copy(deep=True), pd.DataFrame(), cur_node.column_info.copy(), "", op_type, pd.DataFrame(), -1, cur_node.whole_code, [], [], None, cur_node.alive, False, cur_node.utility, None, cur_node.attr_embs.clone().detach())
                            
                            # 填充节点信息
                            next_node.op_type = op_type
                            next_node.operation_desc = operation_desc
                            next_node.write_set = set(out_attr)
                            next_node.read_set = set(rel_cols) - next_node.write_set
                            operation_desc_brief = operation_desc_brief
                            
                            # 更新列信息
                            for attr in next_node.write_set - set(next_node.column_info.keys()):
                                next_node.column_info[attr] = attr + ": (created in previous step) " + operation_desc_brief + "\n"
                            
                            next_state.append(next_node)
                            if self.status_wrapper:
                                out_attr_list = list(out_attr) if not isinstance(out_attr, list) else out_attr
                                self.status_wrapper.send_agent_thinking({
                                    "type": "agent_thinking",
                                    "agent": "mainagent",
                                    "thinking": self._truncate_text(
                                        f"NLAgent: feature {', '.join(out_attr_list)} -> {operation_desc_brief}"
                                    )
                                })
                        else:
                            print(termcolor.colored(f"响应验证失败", "red"))
                    else:
                        print(termcolor.colored(f"解析失败，跳过此响应", "red"))
                    
                    # 如果生成足够数量的特征，返回结果
                    if len(next_state) >= send_num:
                        if self.status_wrapper:
                            self.status_wrapper.send_agent_status({
                                "type": "agent_status",
                                "agent": "mainagent",
                                "status": "completed",
                                "work_type": "nl_agent",
                                "details": {
                                    "node_id": cur_node.node_id,
                                    "step_index": cur_step_idx,
                                    "generated": len(next_state)
                                }
                            })
                            self.status_wrapper.send_agent_thinking({
                                "type": "agent_thinking",
                                "agent": "mainagent",
                                "thinking": self._truncate_text(f"NLAgent: generated {len(next_state)} descriptions for node {cur_node.node_id}.")
                            })
                        return next_state
                        
                if len(next_state) == 0:
                    # 如果没有有效响应，抛出异常
                    raise Exception("Error: no valid response")
            except Exception as e:
                print(termcolor.colored(f"❌ 发生异常: {e}", "red"))
                print(termcolor.colored(f"❌ 异常类型: {type(e).__name__}", "red"))
                import traceback
                print(termcolor.colored(f"❌ 异常堆栈:\n{traceback.format_exc()}", "red"))
                print(termcolor.colored("Error:regrenerate the op_type", "red"))
                # 移除无效的ConnectionRefusedError
                continue
