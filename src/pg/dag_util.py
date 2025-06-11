from src.pg.op_type import *
from src.pg.sql_utils import *
import dataclasses
import networkx as nx
import re
import matplotlib.pyplot as plt
from inspect import cleandoc
from networkx.drawing.nx_agraph import to_agraph
import copy
from src.pg.py_to_sql import Py2Sql
from src.pg.py_to_udf import Py2Udf
from src.pg.sql_reformat import SQLFormater
from src.pg.func_utils import *
from termcolor import colored
from src.pg.cost_estimate import *
from src.llm.llm_dag_util import *

@dataclasses.dataclass
class DagNode():
    node_id: int # start from 0
    code_ref_id: str # -1 means we do not need the code
    read_set: set[str]
    write_set: set[str]
    in_attr: set[str]
    out_attr: set[str]
    op_type: OpType
    cte_name: str = ""
    script_scope: dict = dataclasses.field(default_factory=dict)
    reuse:bool = False
    
    def __hash__(self):
        return hash(self.cte_name)
    
    def __copy__(self):
        return DagNode(self.node_id, self.code_ref_id, self.read_set.copy(), self.write_set.copy(), self.in_attr.copy(), self.out_attr.copy(), self.op_type, self.cte_name, self_copy(self.script_scope), self.reuse)
    

class DagConstructor():
    func2idmap = {}
    id2funcmap = {}
    funcidseq = 0 
    nodeidseq = 0
    
    @staticmethod
    def allocate_nodeid():
        DagConstructor.nodeidseq += 1
        return DagConstructor.nodeidseq
    @staticmethod
    def get_cur_nodeid():
        return DagConstructor.nodeidseq
        
    def __init__(self, var_name:str, model_type:str, pre_code: str, code_block:list[str], op_list:list[OpType], tb_name:str, target_col:str, id_col:str, pipe, task_type:str, do_cte_combine:bool, use_py_train_pred:bool) -> None:
        self.var_name = var_name
        self.model_type = model_type
        self.pre_code = pre_code
        self.code_block = code_block.copy()
        self.op_list = op_list.copy()
        self.Dag = nx.DiGraph()
        self.id2node = {}
        self.tb_name = tb_name
        self.target_col = target_col
        self.id_col = id_col
        self.pipe = pipe # reusemap [attr -> (tb_name, stored_attr)]
        self.task_type = task_type
        self.do_cte_combine = do_cte_combine
        self.use_py_train_pred = use_py_train_pred
    
    @staticmethod
    def add_dfwrapper(code, var_name):
        new_code = cleandoc(f"""
{var_name} = DataFrameWrapper({var_name}, set(), set())
{code}
        """)
        return new_code
    
    def get_effective_df_attr(self, pre_code: str, code_block: list[str]) -> list[list[str]]:
        cur_script_scope = {}
        exec(pre_code, cur_script_scope)
        substitute_cur_df(cur_script_scope, self.var_name)

        effective_attr = []
        for code in code_block:
            pre_df = cur_script_scope.get(self.var_name).copy()
            exec(code, cur_script_scope)
            pos_df = cur_script_scope.get(self.var_name)
            effective_attr.append(get_diff_attr(pre_df, pos_df))
        
        return effective_attr
    
    @staticmethod
    def get_list_from_column_str(column_str: str, script_scope: map) -> list[str]:
        cols = []
        if column_str != "":
            if column_str.startswith("'"):
                cols = column_str[1:-1].replace("'", "").split(',')
            else:
                cols = script_scope.get(column_str)
                if isinstance(cols, str):
                    cols = [cols]
        return cols

    @staticmethod
    def insert_funccode_and_return_id(code: str) -> int:
        if code not in DagConstructor.func2idmap.keys():
            DagConstructor.func2idmap[code] = DagConstructor.funcidseq
            DagConstructor.id2funcmap[DagConstructor.funcidseq] = code
            DagConstructor.funcidseq += 1
            return DagConstructor.funcidseq - 1
        else:
            return DagConstructor.func2idmap[code]
        
    @staticmethod
    def get_cur_cte_name():
        return "cte_" + str(DagConstructor.get_cur_nodeid())
    
    @staticmethod
    def update_script_scope_by_pre_node(cur_node:DagNode, pre_node:DagNode):
        """
        update the script scope by the pre node
        """
        script_scope = self_copy(pre_node.script_scope)
        code_ref = DagConstructor.id2funcmap[pre_node.code_ref_id]
        print(code_ref)
        exec(code_ref, script_scope)
        cur_node.script_scope = script_scope
        
    def construct_pipeline(self):
        t1 = time.time()
        
        script_scope = {}
        exec(self.pre_code, script_scope)
        substitute_cur_df(script_scope, self.var_name)
        
        # used as the fail path for fetching the effective attributes
        effective_attrs = self.get_effective_df_attr(self.pre_code, self.code_block)

        dummy_head = DagNode(DagConstructor.allocate_nodeid(), -1, set(), set(), set(), set(), OpType(OpTypeEnum.START), self.tb_name, self_copy(script_scope), False)
        self.id2node[DagConstructor.get_cur_nodeid()] = dummy_head
        self.Dag.add_node(dummy_head)
        
        for index, (op, code) in enumerate(zip(self.op_list, self.code_block)):
            # check whether the code could not be wrapper [such as pd.get_dummies]
            new_script_scope = self_copy(script_scope)
            node_script_scope = self_copy(script_scope)
            in_attr = set(script_scope.get(self.var_name).columns.tolist()).copy()
            exec(code, script_scope)
            out_attr = set(script_scope.get(self.var_name).columns.tolist()).copy()
            
            curcodeid = self.insert_funccode_and_return_id(code)
            
            # if len(effective_attrs[index]) != 0:
            #     isreuse = True
            #     for ele in effective_attrs[index]:
            #         if ele not in self.pipe.reusemap.keys():
            #             isreuse = False
            #     if isreuse:
            #         op.op_type = OpTypeEnum.REUSE 
                
            if "get_dummies" in code:
                match = re.search(r"columns=\[.*?\]", code)
                print(match.group(0)[9:-1])
                collist = DagConstructor.get_list_from_column_str(match.group(0)[9:-1], script_scope)
                # we just get the columns parameters in the code, although it may be not accurate
                self.id2node[DagConstructor.get_cur_nodeid()] = DagNode(DagConstructor.allocate_nodeid(), curcodeid, set(collist), set(effective_attrs[index]), set(in_attr), set(out_attr), copy.deepcopy(op), DagConstructor.get_cur_cte_name(), self_copy(node_script_scope), False)
                self.Dag.add_node(self.id2node[DagConstructor.get_cur_nodeid()])
                
            else:
                # Fetch the read and write set by the df wrapper, if raise an Exception, then we failover to default(read_set=all, write_set=all delta)
                try:
                    exec(self.add_dfwrapper(code, self.var_name), new_script_scope)
                    # get the read and write set
                    df_wrapper = new_script_scope[self.var_name]
                    read_set, write_set = df_wrapper.read_set, df_wrapper.write_set
                except Exception as e:
                    read_set, write_set = set(in_attr), set(out_attr - in_attr)
                self.id2node[DagConstructor.get_cur_nodeid()] = DagNode(DagConstructor.allocate_nodeid(), curcodeid, read_set, write_set, set(in_attr), set(out_attr), copy.deepcopy(op), DagConstructor.get_cur_cte_name(), self_copy(node_script_scope.copy()), False)
                self.Dag.add_node(self.id2node[DagConstructor.get_cur_nodeid()])

                # the node of train do not set the op_type for ele
                for ele in list(write_set):
                    self.pipe.attr2OpTypeEnum[ele] = op.op_type
                # if one input and type is unsupport, then use the apply method
                # if len(read_set) == 1 and op.op_type == OpTypeEnum.UNSUPPORT:
                #     self.id2node[DagConstructor.get_cur_nodeid()].op_type.op_type = OpTypeEnum.APPLY
            
            
            self.Dag.add_edge(self.id2node[DagConstructor.get_cur_nodeid()-1], self.id2node[DagConstructor.get_cur_nodeid()])
            
        dummy_tail = DagNode(DagConstructor.allocate_nodeid(), -1, set(), set(), set(), set(), OpType(OpTypeEnum.END), self.tb_name, self_copy(script_scope), False)
        self.id2node[DagConstructor.get_cur_nodeid()] = dummy_tail
        self.Dag.add_node(dummy_tail)  
        self.Dag.add_edge(self.id2node[DagConstructor.get_cur_nodeid()-1], self.id2node[DagConstructor.get_cur_nodeid()])
        
        self.final_script_scope = self_copy(script_scope) 
        t2 = time.time()
        print("total time:", t2-t1)
        
    def set_reuse_info(self):
        # for each node in dag, check whether in the reuse map of the current pipe
        for node in self.Dag.nodes:
            if len(list(node.write_set)) != 1:
                continue
            for attr in list(node.write_set):
                if attr in self.pipe.reusemap.keys():
                    # node.op_type.op_type = OpTypeEnum.REUSE
                    node.reuse = True
    
    def cost_estimation(self):
        """
        estimate the cost of each one node
        """
        pass
    
    def whether_split(self, cur_node:DagNode) -> bool:
        """
        whether the pipeline could be split
        """
        # compute the cost wasting in join and less cost in split
        cur_df = cur_node.script_scope[self.var_name].copy()
        origin_udf_cost = estimate_udf_cost(cur_df)
        # split the df to two part
        columns = cur_df.columns.tolist()
        # pre process the read set
        print(colored(f"Current readset: {cur_node.read_set}, procedured writeset {cur_node.write_set}, columns {columns}", "red"))
        cur_node.read_set = cur_node.read_set - (cur_node.write_set - set(columns))

        if len(cur_node.read_set) == 0 or len(cur_node.read_set) == len(columns):
            return False
        
        branch1_df = cur_df[list(cur_node.read_set)]
        branch2_df = cur_df[list(set(columns) - cur_node.read_set)]
        new_udf_cost = estimate_udf_cost(branch1_df)
        join_cost = estimate_hash_join_cost(branch1_df, branch2_df)
        
        print(colored(f"origin_udf_cost: {origin_udf_cost}, new_udf_cost: {new_udf_cost}, join_cost: {join_cost}", "red"))
        
        return new_udf_cost - origin_udf_cost + join_cost < 0
    
    def create_select_node(self, var_name:str, attrs:list[str], script_scope:dict) ->DagNode:
        """
        create an dag node that represent the selection of the attribute
        """
        listattrs = ",".join([f'"{attr}"' for attr in attrs])
        code_ref = cleandoc(f"""
        {var_name} = {var_name}[[{listattrs}]]
        """)
        code_ref_id = self.insert_funccode_and_return_id(code_ref)
        return DagNode(DagConstructor.allocate_nodeid(), code_ref_id, set(attrs), set(attrs), set(attrs), set(attrs), OpType(OpTypeEnum.BINARY), DagConstructor.get_cur_cte_name(), script_scope, False)
    
    def create_join_node(self, node1:DagNode, node2:DagNode) -> DagNode:
        """
        create a join node that represent the join of the two nodes
        """
        parameters = {"node1_attrs": node1.out_attr, "node2_attrs": node2.out_attr}
        return DagNode(DagConstructor.allocate_nodeid(), -1, set(), set(), node1.out_attr.union(node2.out_attr), node1.out_attr.union(node2.out_attr), OpType(OpTypeEnum.JOIN, parameters=parameters), DagConstructor.get_cur_cte_name(), {}, False)
        
    def split_path(self, start_node:DagNode, end_node:DagNode):
        """
        split the path of the pipeline
        """
        cur_node = list(self.Dag.successors(start_node))[0]
        # path1 store the udfpath, path2 store the remain path
        path1 = nx.DiGraph()
        path1_start = self.create_select_node(self.var_name, cur_node.read_set | {self.id_col}, self_copy(cur_node.script_scope))
        path1_pre = path1_start
        path1.add_node(path1_start)
        including_attr1 = cur_node.read_set.union(cur_node.write_set)
        
        path2 = nx.DiGraph()
        path2_start = self.create_select_node(self.var_name, (cur_node.in_attr - cur_node.read_set) | {self.id_col}, self_copy(cur_node.script_scope))
        path2_pre = path2_start
        path2.add_node(path2_start)
        including_attr2 = path2_start.out_attr
        
        while cur_node != end_node:
            if cur_node.write_set.intersection(including_attr1) == set() and cur_node.read_set.intersection(including_attr1) == set():
                # add the node to the path2
                including_attr2 = including_attr2.union(cur_node.write_set)
                new_cur_node = copy.copy(cur_node)
                new_cur_node.in_attr = cur_node.out_attr
                new_cur_node.out_attr = including_attr2
                path2.add_node(new_cur_node)
                path2.add_edge(path2_pre, new_cur_node)
                DagConstructor.update_script_scope_by_pre_node(new_cur_node, path2_pre)
                path2_pre = new_cur_node
            else:
                # add the node to the path1
                including_attr1 = including_attr1.union(cur_node.write_set)
                new_cur_node = copy.copy(cur_node)
                new_cur_node.in_attr = cur_node.out_attr
                new_cur_node.out_attr = including_attr1
                path1.add_node(new_cur_node)
                path1.add_edge(path1_pre, new_cur_node)
                DagConstructor.update_script_scope_by_pre_node(new_cur_node, path1_pre)
                path1_pre = new_cur_node
            
            tmp_node = list(self.Dag.successors(cur_node))[0]
            self.Dag.remove_node(cur_node)
            cur_node = tmp_node
        
        # add the path1 and path2 to the original dag
        self.Dag.add_nodes_from(path1.nodes(data=True))
        self.Dag.add_edges_from(path1.edges(data=True))
        self.Dag.add_nodes_from(path2.nodes(data=True))
        self.Dag.add_edges_from(path2.edges(data=True))
        
        self.Dag.add_edge(start_node, path1_start)
        self.Dag.add_edge(start_node, path2_start)
        join_node = self.create_join_node(path1_pre, path2_pre)
        self.Dag.add_edge(path1_pre, join_node)
        self.Dag.add_edge(path2_pre, join_node)
        self.Dag.add_edge(join_node, end_node)
                            
    
    def optimize_pipeline(self):
        """
        optimize the original sequencial pipeline
        """
        # grab all the starting nodes
        cur_node = [node for node in self.Dag.nodes if len(list(self.Dag.predecessors(node))) == 0][0]
        
        while True:   
            if cur_node.op_type.op_type == OpTypeEnum.TRAIN or len(list(self.Dag.successors(cur_node))) == 0:
                break
            
            # elif cur_node.op_type.op_type == OpTypeEnum.UNSUPPORT and self.whether_split():
            elif cur_node.op_type.op_type in UDF_OP_TYPE and self.whether_split(cur_node):
                print(colored("Yes! choose to Split for the node of %s, code %s" %(cur_node.cte_name, self.id2funcmap[cur_node.code_ref_id]), "grey"))
                # when the type of node is type, we should first estimate whether here is need to split the node
                including_attrs = cur_node.read_set.union(cur_node.write_set)
                start_node = list(self.Dag.predecessors(cur_node))[0]
                end_node = list(self.Dag.successors(cur_node))[0]
                while True:
                    if end_node.op_type.op_type == OpTypeEnum.END:
                        break
                    elif end_node.read_set in including_attrs or (end_node.read_set.intersection(including_attrs) == set() and end_node.write_set.intersection(including_attrs) == set()):
                        # two case 
                        #   1. the current path could include the next node
                        #   2. the current path has no common attribute to the next path
                        including_attrs = including_attrs.union(end_node.write_set)
                        end_node = list(self.Dag.successors(end_node))[0]
                    else:
                        break
                self.split_path(start_node, end_node)
                cur_node = end_node
                
            else:
                cur_node = list(self.Dag.successors(cur_node))[0]
                

    def bfs_dag(self, extra_step, sql_file: str, udf_file: str, import_code, seq, reuse=True, concrete_time=False):
        """
        bfs the dag, and using the script_scope and the cte_name to generate the relevant sql code
        1. the src table is the predecessor of the node
        2. the dst table is the cte_name
        """
        self.set_reuse_info()
        seq = {
            OpTypeEnum.BINARY: 0,
            OpTypeEnum.UNARY: 0,
            OpTypeEnum.NUMERIZE: 0,
            OpTypeEnum.NORMALIZE: 0,
            OpTypeEnum.GET_DUMMIES: 0,
            OpTypeEnum.DISCRETIZE: 0,
            OpTypeEnum.TRAIN: 0,
            OpTypeEnum.UNSUPPORT: 0,
            OpTypeEnum.START: 0,
            OpTypeEnum.JOIN: 0,
            OpTypeEnum.FILLNA: 0,
            OpTypeEnum.PREDICT: 0,
            OpTypeEnum.VALIDATE: 0,
            OpTypeEnum.APPLY: 0,
            OpTypeEnum.DROP: 0,
            OpTypeEnum.REUSE: 0,
            OpTypeEnum.END: 0
        }
        
        
        dummy_head = [node for node in self.Dag.nodes if len(list(self.Dag.predecessors(node))) == 0][0]
        # dummy_head.cte_name = f"{dummy_head.cte_name}_{str(extra_step)}"

        # head = [node for node in self.Dag.nodes if len(list(self.Dag.predecessors(node))) == 0][0]
        processed_node = set()
        queue = [dummy_head]
        
        sql_pair = []
        udfs = []
        model_name = f"model_{self.tb_name}_{self.pipe.pipe_id}"
        conn = get_conn()
        while len(queue) != 0:
            cur_node = queue.pop(0)
            if cur_node in processed_node:
                continue
            
            predecessors = list(self.Dag.predecessors(cur_node))
            pred_visited = True
            for pre_node in predecessors:
                if pre_node not in processed_node:
                    pred_visited = False
            if not pred_visited:
                continue
            
            #-----------------generate the sql code-----------------
            seq[cur_node.op_type.op_type] += 1
            if cur_node.op_type.op_type != OpTypeEnum.START:
                pre_nodes = list(self.Dag.predecessors(cur_node))
                pre_cte = pre_nodes[0].cte_name
                if pre_cte == self.tb_name:
                    op_str = "test" if extra_step == PipeTypeEnum.PREDICT else "train"
                    pre_cte = f"{pre_cte}_{op_str}"
                        
                if cur_node.script_scope != {}:
                    in_df = cur_node.script_scope[self.var_name].copy()
                
                if reuse and cur_node.reuse:
                    target_col = list(cur_node.write_set)[0]
                    tb_name, stored_attr = self.pipe.reusemap[target_col]
                    cur_sql = Py2Sql.reuse(self.tb_name + str(tb_name), stored_attr, target_col, pre_cte, self.id_col)
                    sql_pair.append((cur_node.cte_name, cur_sql))
                    
                elif cur_node.op_type.op_type in EASY_OF_TYPE:
                    print("--------------------------------")
                    print(self.id2funcmap[cur_node.code_ref_id])
                    print("--------------------------------")
                    # exec(wrapper_code_for_pd2sql(delete_drop(self.id2funcmap[cur_node.code_ref_id]), pre_cte, "tmp", self.var_name, self.id_col), cur_node.script_scope)
                    new_script_scope = self_copy(cur_node.script_scope)
                    exec(wrapper_code_for_pd2sql(self.id2funcmap[cur_node.code_ref_id], pre_cte, "tmp", self.var_name, self.id_col), new_script_scope)
                    sql_var = copy.copy(new_script_scope["tmp"])
                    sql_pair.append((cur_node.cte_name, sql_var))
                    
                elif cur_node.op_type.op_type == OpTypeEnum.NUMERIZE:
                    # sampling the distinct value in database, if could not then sampling the partial data
                    cate_col = get_for_category_col(self.tb_name, list(cur_node.read_set)[0], conn)
                    if cate_col == []:
                        print(termcolor.colored("Fallback to sampling the column", "red"))
                        cate_col = get_sample_for_category_col(in_df, list(cur_node.read_set)[0])
                    # cur_sql = Py2Sql.label_encode("encode_table_"+str(seq[cur_node.op_type.op_type]), pre_cte, cur_node.op_type.relevant_cols[0], cur_node.op_type.target_cols[0], cate_col)
                    cur_sql = Py2Sql.label_encode_by_update(pre_cte, list(cur_node.read_set)[0], list(cur_node.write_set)[0], cate_col)
                    sql_pair.append((cur_node.cte_name, cur_sql))
                    
                elif cur_node.op_type.op_type == OpTypeEnum.NORMALIZE:
                    cur_sql, percent_sql, percent_tb = Py2Sql.normalization(cur_node.op_type.parameters["scaler_type"], pre_cte, list(cur_node.read_set), list(cur_node.write_set), seq[cur_node.op_type.op_type])
                    if percent_sql != "":   
                        sql_pair.append((percent_tb, percent_sql))
                    sql_pair.append((cur_node.cte_name, cur_sql))
                    
                elif cur_node.op_type.op_type == OpTypeEnum.GET_DUMMIES:
                    # cur_sql = Py2Sql.one_hot_encode("ohencode_table_"+str(seq[cur_node.op_type.op_type]), pre_cte, cur_node.op_type.relevant_cols[0], get_sample_for_category_col(in_df, cur_node.op_type.relevant_cols[0]))
                    cate_col = get_for_category_col(self.tb_name, cur_node.op_type.relevant_cols[0], conn)
                    if cate_col == []:
                        cate_col = get_sample_for_category_col(in_df, cur_node.op_type.relevant_cols[0])
                    cur_sql = Py2Sql.one_hot_by_update(pre_cte, cur_node.op_type.relevant_cols[0], cate_col)
                    sql_pair.append((cur_node.cte_name, cur_sql))
                    
                elif cur_node.op_type.op_type == OpTypeEnum.DISCRETIZE:
                    # if cur_node.op_type.parameters["discretize_type"] == DiscretizeTypeEnum.QCUT:
                    #     (bound_sql, exceed_sql, cur_sql), (bound_table, exceed_table, _) = Py2Sql.discretize_qcut(pre_cte, cur_node.op_type.relevant_cols[0], cur_node.op_type.target_cols[0], cur_node.op_type.label_cols, total_num, seq[cur_node.op_type.op_type])
                    # elif cur_node.op_type.parameters["discretize_type"] == DiscretizeTypeEnum.CUT:
                    #     (minmax_sql, bound_sql, exceed_sql, cur_sql), (minmax_table, bound_table, exceed_table, _) = Py2Sql.discretize_cut(pre_cte, cur_node.op_type.relevant_cols[0], cur_node.op_type.target_cols[0], cur_node.op_type.label_cols, seq[cur_node.op_type.op_type])
                    #     sql_pair.append((minmax_table, minmax_sql))
                    
                    # sql_pair.append((bound_table, bound_sql))
                    # sql_pair.append((exceed_table, exceed_sql))
                    # sql_pair.append((cur_node.cte_name, cur_sql))    
                    code = self.id2funcmap[cur_node.code_ref_id]  
                    new_script_scope = self_copy(cur_node.script_scope)
                    exec(code, new_script_scope)   
                    out_df = new_script_scope[self.var_name].copy()  

                    cur_udf, (call_sql1, call_sql2), (call_tb, _) = Py2Udf.convert_for_discrete(in_df, out_df, pre_cte, list(cur_node.read_set)[0], list(cur_node.write_set)[0], cur_node.op_type.label_cols, seq[cur_node.op_type.op_type], cur_node.op_type.parameters["discretize_type"])
                    udfs.append(cur_udf)
                    sql_pair.append((call_tb, call_sql1))
                    sql_pair.append((cur_node.cte_name, call_sql2))
                    
                elif cur_node.op_type.op_type == OpTypeEnum.JOIN:
                    assert(len(pre_nodes) == 2)
                    pre_ctes = list(map(lambda x: x.cte_name, pre_nodes))
                    pre_attrs = [cur_node.op_type.parameters["node1_attrs"], cur_node.op_type.parameters["node2_attrs"]]
                    cur_sql = Py2Sql.join(pre_ctes, pre_attrs, self.id_col)
                    sql_pair.append((cur_node.cte_name, cur_sql))
                    
                elif cur_node.op_type.op_type == OpTypeEnum.FILLNA:
                    fillna_type_list = cur_node.op_type.parameters["fillna_type"]
                    if isinstance(fillna_type_list, FillnaType):
                        fillna_type_list = [fillna_type_list]
                    cur_sql = Py2Sql.fillna_by_select(fillna_type_list, pre_cte, list(cur_node.read_set), list(cur_node.write_set))
                    sql_pair.append((cur_node.cte_name, cur_sql))
                    
                elif cur_node.op_type.op_type == OpTypeEnum.UNSUPPORT:
                    code = self.id2funcmap[cur_node.code_ref_id]  
                    new_script_scope = self_copy(cur_node.script_scope)
                    exec(code, new_script_scope)   
                    
                    out_df = new_script_scope[self.var_name].copy()               
                    cur_udf, (cur_sql1, cur_sql2), (cte1, _) = Py2Udf.convert_for_combined_exec(in_df, out_df, pre_cte, self.var_name, code, seq[cur_node.op_type.op_type], import_code)
                    udfs.append(cur_udf)
                    sql_pair.append((cte1, cur_sql1))
                    sql_pair.append((cur_node.cte_name, cur_sql2))
                    print(termcolor.colored(f"Unsupport add the {cur_sql1} {cur_sql2}", "yellow"))
                
                elif cur_node.op_type.op_type == OpTypeEnum.TRAIN:
                    if self.use_py_train_pred:
                        print(termcolor.colored("Use the python train and predict", "red"))
                        cur_udf, (call_sql1, call_sql2), (call_tb, _) = Py2Udf.convert_for_train_py(in_df, self.target_col, pre_cte, model_name, self.task_type, self.id_col, import_code, self.model_type)
                    else:
                        cur_udf, (call_sql1, call_sql2), (call_tb, _) = Py2Udf.convert_for_train(in_df, self.target_col, pre_cte, model_name, self.task_type, self.id_col)
                    udfs.append(cur_udf)
                    sql_pair.append((call_tb, call_sql1))
                    sql_pair.append((cur_node.cte_name, call_sql2))
                
                elif cur_node.op_type.op_type == OpTypeEnum.PREDICT:
                    cur_udf, (call_sql, call_sql2), (predict_tb, _) = Py2Udf.convert_for_predict(in_df, model_name, pre_cte, "lightgbm_predict", self.target_col, self.id_col, seq[cur_node.op_type.op_type])
                    udfs.append(cur_udf)
                    sql_pair.append((predict_tb, call_sql))
                    sql_pair.append((cur_node.cte_name, call_sql2))

                elif cur_node.op_type.op_type == OpTypeEnum.APPLY:
                    # currently only support unary input
                    if len(list(cur_node.read_set)) != 1:
                        sql_pair.append((cur_node.cte_name, "SELECT *, " + list(cur_node.read_set)[0] + " AS " + list(cur_node.write_set)[0] + " FROM " + pre_cte))
                    else:
                        pycode = self.id2funcmap[cur_node.code_ref_id]  
                        exec(pycode, cur_node.script_scope)   
                        
                        ccode = LLMDagConstructor.python2c_code(pycode, list(cur_node.read_set)[0], list(cur_node.write_set)[0])
                        out_df = cur_node.script_scope[self.var_name].copy()   
                        cur_udf, (call_sql, call_sql2), (apply_tb, _) = Py2Udf.convert_for_c_function(in_df, out_df, pre_cte, ccode, list(cur_node.write_set)[0], seq[cur_node.op_type.op_type])
                        udfs.append(cur_udf)
                        sql_pair.append((apply_tb, call_sql))
                        sql_pair.append((cur_node.cte_name, call_sql2))
                else:
                    # currently cut for the train part / end part
                    pass
            #-------------------------------------------------------
            processed_node.add(cur_node)
            queue.extend(list(self.Dag.successors(cur_node)))
        
        if extra_step != PipeTypeEnum.NOTHING:
            # finish executing the dag, we finally add (train/validate/predict) part
            # we should step back the cur_node[currently is END]
            cur_node = list(self.Dag.predecessors(cur_node))[0]
            in_df = self.final_script_scope[self.var_name].copy()
            cur_cte = cur_node.cte_name
            final_tb = f"final_{str(extra_step)}"
            if self.use_py_train_pred:
                cur_udf, (call_sql1, call_sql2), (call_tb, _) = Py2Udf.convert_for_final_op_py(in_df, self.target_col, self.id_col, cur_cte, extra_step, self.task_type, import_code, self.tb_name, self.model_type)
            else:
                cur_udf, (call_sql1, call_sql2), (call_tb, _) = Py2Udf.convert_for_final_op(in_df, self.target_col, self.id_col, cur_cte, extra_step, self.task_type)
            udfs.append(cur_udf)
            sql_pair.append((call_tb, call_sql1))
            sql_pair.append((final_tb, call_sql2))
            
        self.total_sql_num = len(sql_pair)
            
        # finally we construct the whole sql
        with open(sql_file, "w") as f:
            stored_attr = [attr for attr in self.pipe.resAttr2isStore.keys() if self.pipe.resAttr2isStore[attr] == True]
            tb_name = self.tb_name + str(self.pipe.pipe_id)
            if self.do_cte_combine:
                if self.use_py_train_pred:
                    f.write(SQLFormater.sqls_reformat_from_pair_py(extra_step, sql_pair, stored_attr, tb_name, self.id_col, False, model_type=self.model_type))
                else:
                    f.write(SQLFormater.sql_reformat_from_pair(extra_step, sql_pair, stored_attr, tb_name, self.id_col))
            else:
                f.write(SQLFormater.sqls_reformat_from_pair(extra_step, sql_pair, stored_attr, tb_name, self.id_col))

            
            if concrete_time:
                with open(sql_file[:-4]+"_noop.sql", "w") as f_noop:
                    f_noop.write(SQLFormater.sql_reformat_from_pair(extra_step, sql_pair, stored_attr, tb_name, self.id_col, False))
                with open(sql_file[:-4]+"_notrain.sql", "w") as f_notrain:
                    f_notrain.write(SQLFormater.sql_reformat_from_pair(0, sql_pair, stored_attr, tb_name, self.id_col, True, True))
        with open(udf_file, "w") as f:
            for udf in udfs:
                f.write(udf + "\n") 
            
    # def assign_cte_name(node: DagNode):
    #     """
    #     assign the cte name for the node
    #     """
    #     node.cte_name = node