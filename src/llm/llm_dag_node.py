import pandas as pd
import time
import dataclasses
from src.pg.op_type import *
from src.llm.utils.parse_util import *
import torch
import threading

@dataclasses.dataclass
class LLMDAGNODE():
    """
    LLM驱动的特征工程DAG节点数据结构
    
    该数据结构用于表示特征工程过程中的一个节点，包含了特征生成所需的所有信息
    以及节点在DAG中的状态信息。
    """
    
    # 节点唯一标识符
    node_id: int
    
    # 特征生成代码，-1表示不需要代码
    task_code: str
    
    # 该节点读取的列集合（输入特征）
    read_set: set[str]
    
    # 该节点写入的列集合（输出特征）
    write_set: set[str]
    
    # 节点输入数据框
    in_cur_df: pd.DataFrame
    
    # 节点输出数据框
    out_cur_df: pd.DataFrame
    
    # 列信息字典，存储列名到列描述的映射
    column_info: dict[str, str]
    
    # 节点操作的自然语言描述
    operation_desc: str
    
    # 操作类型枚举值
    op_type: OpTypeEnum
    
    # 节点评估分数数据框
    scores: pd.DataFrame
    
    # 节点的最终评估分数
    final_score: float
    
    # 完整的特征生成代码
    whole_code: str
    
    # 修复节点列表，用于存储需要修复的节点
    fixing_node: list
    
    # 需要删除的属性列表
    drop_attrs: list
    
    # 节点执行时间
    exec_time: time.time
    
    # 节点是否存活（用于异步执行）
    alive: bool = True
    
    # 节点是否已完成执行
    finished: bool = False
    
    # 节点的效用值（用于A*搜索）
    utility: float = 0.0
    
    # 属性重要性排序列表
    attr_imp_order: list = None
    
    # 属性嵌入向量（用于相似度计算）
    attr_embs: torch.Tensor = None

    # planner给出的拓展建议
    planner_suggest: str = ""

    def __hash__(self):
        """哈希函数，用于在集合和字典中使用节点"""
        return hash(self.node_id)
    
    def __copy__(self):
        """深拷贝方法，用于复制节点"""
        return LLMDAGNODE(
            self.node_id, 
            self.task_code, 
            self.read_set.copy(), 
            self.write_set.copy(), 
            self.in_cur_df.copy(), 
            self.out_cur_df.copy(), 
            self.column_info.copy(), 
            self.operation_desc, 
            self.op_type, 
            self.scores.copy(), 
            self.final_score, 
            self.whole_code, 
            self.fixing_node.copy(), 
            self.drop_attrs.copy(), 
            None, 
            self.alive, 
            self.finished, 
            self.utility, 
            self.attr_imp_order, 
            self.attr_embs.clone().detach()
        )
    
    def __lt__(self, other):
        """小于比较方法，用于优先队列排序（基于utility值）"""
        return self.utility > other.utility

    def node_importance(self):
        """获取节点重要性（基于utility值）"""
        return self.utility

global_node_id = 0            
lock = threading.Lock()
def allocate_node_id():
    global global_node_id
    
    with lock:
        global_node_id += 1
    return global_node_id
    