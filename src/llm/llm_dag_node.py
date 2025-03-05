import pandas as pd
import time
import dataclasses
from src.pg.op_type import *
from src.llm.utils.parse_util import *
import torch
import threading

@dataclasses.dataclass
class LLMDAGNODE():
    node_id: int
    task_code: str # -1 means we do not need the code
    read_set: set[str]
    write_set: set[str]
    in_cur_df: pd.DataFrame
    out_cur_df: pd.DataFrame
    column_info: dict[str, str]
    operation_desc: str
    op_type: OpTypeEnum
    scores: pd.DataFrame
    final_score: float
    whole_code: str
    fixing_node: list
    
    drop_attrs: list  
    exec_time: time.time
    alive: bool = True
    finished: bool = False
    utility: float = 0.0
    attr_imp_order: list = None
    attr_embs: torch.Tensor = None
    def __hash__(self):
        return hash(self.node_id)
    
    def __copy__(self):
        return LLMDAGNODE(self.node_id, self.task_code, self.read_set.copy(), self.write_set.copy(), self.in_cur_df.copy(), self.out_cur_df.copy(), self.column_info.copy(), self.operation_desc, self.op_type, self.scores.copy(), self.final_score, self.whole_code, self.fixing_node.copy(), self.drop_attrs.copy(), None, self.alive, self.finished, self.utility, self.attr_imp_order, self.attr_embs.clone().detach())
    
    def __lt__(self, other):
        return self.utility > other.utility

    def node_importance(self):
        return self.utility

global_node_id = 0            
lock = threading.Lock()
def allocate_node_id():
    global global_node_id
    
    with lock:
        global_node_id += 1
    return global_node_id
    