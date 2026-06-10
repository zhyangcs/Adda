import networkx as nx
from src.multipipe.multi_utils import *

def ctor_reorder_graph(pipes:list[PIPE]):
    multi_dag = nx.DiGraph()
    for i in range(len(pipes)):
        multi_dag.add_node(i)
        for j in range(len(pipes)):
            multi_dag.add_edge(i, j, weight=pipes[i].intersect(pipes[j]))
    return multi_dag

def greedy_reorder_opt(multi_dag:nx.DiGraph):
    """
    greedy reorder optimization
    """
    o1, o2 = [], []
    while multi_dag.number_of_nodes() > 0:
        out_degree = dict(multi_dag.out_degree(weight='weight'))
        rm_nodes = []
        for node in multi_dag.nodes():
            if out_degree[node] == 0:
                o2 = o2 + [node]
                rm_nodes.append(node)
        multi_dag.remove_nodes_from(rm_nodes)
        in_degree = dict(multi_dag.in_degree(weight='weight'))
        rm_nodes = []
        for node in multi_dag.nodes():
            if in_degree[node] == 0:
                o1 = o1 + [node]
                rm_nodes.append(node)
        multi_dag.remove_nodes_from(rm_nodes)
        
        if multi_dag.number_of_nodes() == 0:
            break
        
        in_degree, out_degree = dict(multi_dag.in_degree(weight='weight')), dict(multi_dag.out_degree(weight='weight'))
        max_delta = -1
        max_node = None
        for node in multi_dag.nodes():
            if abs(in_degree[node] - out_degree[node]) > max_delta:
                max_delta = abs(in_degree[node] - out_degree[node])
                max_node = node
        multi_dag.remove_node(max_node)
        if out_degree[max_node] > in_degree[max_node]:
            o1 = o1 + [max_node]
        else:
            o2 = o2 + [max_node]
    return o1 + o2
            
    
if __name__ == "__main__":
    dag = nx.DiGraph()
    for i in range(5):
        dag.add_node(i)
    for i in range(5):
        for j in range(5):
            if i != j:
                dag.add_edge(i, j, weight=2*i+j)
    order = greedy_reorder_opt(dag)
    print(order)