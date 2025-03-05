import networkx as nx
import dataclasses
from src.pg.op_type import *

@dataclasses.dataclass
class PIPE():
    hash2resAttr: dict = dataclasses.field(default_factory=dict)
    hash2inAttr: dict = dataclasses.field(default_factory=dict)
    resAttr2isStore: dict = dataclasses.field(default_factory=dict)
    resAttr2Ti: dict = dataclasses.field(default_factory=dict)
    reusemap: dict = dataclasses.field(default_factory=dict)
    attr2OpTypeEnum: dict = dataclasses.field(default_factory=dict)
    code_path: str = ""
    pipe_id: int = -1
    
    def intersect(self, other):
        """
        intersection of two PIPEDAGNODE
        # Q: how to check whether two candidate feature is equal?
        # A: we prehash the op_tree to str_seq, and compare two seqs
        """
        return len(set(self.hash2inAttr.values()) & set(other.hash2resAttr.values()))
    
    def get_pipe_str(self) -> str:
        """
        print the store and reuse information for the pipe
        """
        pipe_str = str(self.resAttr2isStore) + "\n" + str(self.reusemap) + "\n" + str(self.code_path)

        return pipe_str

    
class PIPEDAGNODE():
    node_id: int
    

if __name__ == "__main__":
    pipes = [PIPE()] * 5
    print(pipes)