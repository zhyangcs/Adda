from src.llm.utils.llm_util import *
from src.llm.utils.prompt import *
from src.llm.llm_dag_node import *
from src.llm.utils.code_metrics import *
from src.pg.func_utils import *
from src.llm.agents.code_agent import *
from collections import deque
import numpy as np
import networkx as nx
import pandas as pd

class DivideAgent():
    def __init__(self, token_limit:int = 800):
        self.code_tree = nx.DiGraph()
        self.root_node = None
        self.node_map = dict()
        self.token_limit = token_limit
    
    def divide_code(self, cur_node:LLMDAGNODE, check_code_complexity:bool = True):
        """
        Check whether the current node should be split
        If so, we recursively divide the node to the subtask and conquer the subtask
        """
        self.root_node = cur_node
        pre_node_list = [self.root_node]
        cur_node_list = []
        while True:
            for cur_node in pre_node_list:
                if not check_code_complexity or whether_code_complex(cur_node.task_code, cur_node.column_info.keys()) == True:
                    if not self.recur_divide(cur_node):
                        return None, False
            else:
                cur_node_list = self.flat_node(pre_node_list)
            try:
                if not check_code_complexity or self.Exec_Same(pre_node_list, cur_node_list):
                    break
            except Exception as e:
                print(termcolor.colored(f"Error in Exec_Same: {e}", "red"))
                return self.combine_nodes(pre_node_list), True
            pre_node_list = cur_node_list
            cur_node_list = []
        return self.combine_nodes(cur_node_list), True
        
    def flat_node(self, node_list):
        """
        flatten the node_list considering the expansion in self.node_map[flat multinested array to one nest array]
        """    
        node_queue = deque()
        flat_node_list = []
        for node in node_list:
            node_queue.append(node)
        while len(node_queue) > 0:
            cur_node = node_queue.popleft()
            if cur_node in self.node_map.keys():
                for node in reversed(self.node_map[cur_node]):
                    node_queue.appendleft(node)
                    # node_list.append(node)
            else:
                flat_node_list.append(cur_node)
                print(cur_node.task_code)
        return flat_node_list
    
    def Exec_Same(self, pre_node_list, cur_node_list):
        """
        Check whether the pre_node_list and cur_node_list are the same
        """
        pre_combined_node, _ = self.combine_nodes(pre_node_list)
        print("finish combining pre")
        cur_combined_node, _ = self.combine_nodes(cur_node_list)
        if cur_combined_node == None:
            raise Exception("new node is not executable, so we should abandon or rollback")
        write_list = list(self.root_node.write_set)
        return pre_combined_node!=None and cur_combined_node!=None and np.isclose(pre_combined_node.out_cur_df[write_list], cur_combined_node.out_cur_df[write_list]).all()
        
        
    def combine_nodes(self, node_list) -> (LLMDAGNODE, bool):
        """
        Combine all of the intermediate node to generate the combined node
        """
        code_list = []
        column_info = node_list[0].column_info
        read_set, write_set = set(), set()
        operation_desc_list = []
        for node in node_list:
            code_list.append(node.task_code)
            for key in node.column_info.keys() - column_info.keys():
                column_info[key] = node.column_info[key]
            read_set, write_set = read_set.union(node.read_set), write_set.union(node.write_set)
            if type(node.operation_desc) == str:
                operation_desc_list.append(node.operation_desc)
            elif type(node.operation_desc) == list:
                operation_desc_list += node.operation_desc


        combined_code = "\n".join(code_list)
        print(termcolor.colored(f"Combined Code: {combined_code}", "yellow"))

        # 添加超时机制防止长时间阻塞
        import signal
        import threading

        exec_env = get_script_scope("")
        exec_env = {'df': node_list[0].in_cur_df.copy(deep=True)}

        # 用于存储执行结果和异常
        exec_result = {'success': False, 'result': None, 'exception': None}

        def execute_with_timeout():
            """在单独线程中执行代码以避免阻塞"""
            try:
                exec(combined_code, exec_env)
                exec_result['success'] = True
                exec_result['result'] = exec_env['df']
            except Exception as e:
                exec_result['exception'] = e

        try:
            # 使用线程执行代码，设置30秒超时
            exec_thread = threading.Thread(target=execute_with_timeout)
            exec_thread.daemon = True  # 设为守护线程
            exec_thread.start()

            # 等待执行完成，最多30秒
            exec_thread.join(timeout=30.0)

            if exec_thread.is_alive():
                # 超时了，强制返回错误
                print(termcolor.colored("Code execution timeout (30s), skipping combination", "red"))
                return None, False

            if exec_result['exception']:
                raise exec_result['exception']

            whole_operation_desc = "\n".join(operation_desc_list)
            return LLMDAGNODE(allocate_node_id(), combined_code, read_set, write_set, node_list[0].in_cur_df, exec_result['result'], column_info, whole_operation_desc, OpTypeEnum.UNSUPPORT, pd.DataFrame(), -1, "", [], [], None, True, False, 0.0), True

        except Exception as e:
            print(termcolor.colored(f"Error in combining nodes: {e}", "red"))
            return None, False
        
    def recur_divide(self, cur_node:LLMDAGNODE):
        """
        Divide the operation description into subtask: return whether could execute the code of node
        """
        print(termcolor.colored(f"[Split Task] cur_node: {cur_node.node_id}", "yellow"))
        data_desc = f"/* {get_column_info(cur_node.column_info, token_limit=self.token_limit, attr_imp_list=None)} */"
        output_feature = list(cur_node.write_set)[0]
        prompt_str = SPLIT_PROMPT.format(input_features = data_desc, procedure_desc=cur_node.operation_desc, output_feature = output_feature)
        
        retry_time = DIVIDE_RETRY_TIMES
        # print(termcolor.colored(prompt_str, "grey"))
        responses = send_prompt_n("", prompt_str, 1, temperature=0.7)
        # get the response which has the max len
        response = min(responses, key=len)
        index = responses.index(response)
        print(termcolor.colored(f"{responses} [[{index}]]\n {response}", "green"))
        while retry_time > 0:
            try:
                response = response.replace("variable", "attribute")
                _, step_nodes, could_exec = self.task_to_subtask(cur_node, response, cur_node.operation_desc)
                if not could_exec:
                    return False
                
                self.node_map[cur_node] = step_nodes
                # break the loop after fininshing the task
                break
            except Exception as e:
                print(termcolor.colored(f"Error in subtasks: {e}", "red"))    
                retry_time -= 1
        return True
                
    def task_to_subtask(self, cur_node:LLMDAGNODE, subtask:str, origin_desc:str = ""):
        """
        Parse the formular of 
        {Intermediate_Step_i : {input variables_i} : {output variables_i}: {intermediate description_i}}
        """
        step_nodes = []
        cur_df = cur_node.in_cur_df.copy(deep = True)
        cur_column_info = cur_node.column_info
        steps = subtask.split("<END_INTER_STEP>")[:-1]
        could_exec = True
        origin_code_complexity = get_code_complexity(cur_node.task_code)
        
        code_agent = CodeAgent()
        if whether_code_complex(cur_node.task_code, cur_node.column_info.keys()):
            for idx, step in enumerate(steps):
                step_list = step.split("|")
                if len(step_list) != 4:
                    raise Exception("Exception for one steps more than 4 comma")
                step_list = [step_info.strip("\{\} \n").split(":")[-1] for step_info in step_list]
                rel_cols, output_cols = parse_string_to_list(step_list[1]), parse_string_to_list(step_list[2])
                for output_col in output_cols - cur_column_info.keys():
                    cur_column_info[output_col] = output_col + ": (created in previous step) " + step_list[3] + "\n"
                print(step_list)
                
                step_node = LLMDAGNODE(allocate_node_id(), "", set(rel_cols), set(output_cols), cur_df.copy(deep=True), pd.DataFrame(), cur_column_info, step_list[3], OpTypeEnum.BINARY, pd.DataFrame(), -1, "", [], [], None, True, False, 0.0)
                
                self_consist, could_exec = code_agent.subtask_to_code(step_node, origin_desc)
                print(f"Step{idx} self-consistency: {self_consist}")
                # if exec fail, then we should further divide the node
                # but should notice: if divide is useless, we do not do it(complexity do not fall off)
                if not could_exec or not self_consist and origin_code_complexity > get_code_complexity(step_node.task_code):
                    divide_agent = self.__class__()
                    step_node, could_exec = divide_agent.divide_code(step_node, False)

                cur_df = step_node.out_cur_df.copy(deep = True)
                step_nodes.append(step_node)
                
            return cur_df, step_nodes, could_exec
        else:
            # if the node is not complex, then the spliting may lead to the error semantic of code execution, so we generate the code at once
            full_op_desc = ""
            for idx, step in enumerate(steps):
                step_list = step.split("|")
                full_op_desc += step_list[3] + "\n"
            full_op_desc = full_op_desc.replace("variable", "attribute")
            step_node = LLMDAGNODE(allocate_node_id(), "", cur_node.read_set, cur_node.write_set, cur_df.copy(deep=True), pd.DataFrame(), cur_column_info, full_op_desc, OpTypeEnum.BINARY, pd.DataFrame(), -1, "", [], [], None, True, False, 0.0)
            self_consist, could_exec = code_agent.subtask_to_code(step_node, origin_desc)
            if not could_exec or not self_consist:
                return cur_node.out_cur_df, [cur_node], could_exec
            return step_node.out_cur_df, [step_node], could_exec
