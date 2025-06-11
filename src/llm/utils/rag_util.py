from src.llm.llm_dag_node import *
import networkx as nx
from src.llm.utils.prompt import *

def normalize_score(scores:list):
    if len(scores) == 0:
        return []
    elif max(scores) == min(scores):
        return [1 for _ in scores]
    else:
        return [(score - min(scores))/(max(scores) - min(scores)) for score in scores]

def topKSimilarNodes(node:LLMDAGNODE, dag:nx.DiGraph, K:int):
    """
    Find the top K similar nodes to the given node
    """
    all_nodes = list(dag.nodes)
    # remove the root(do not have the predecesor)
    roots = [node for node in all_nodes if len(list(dag.predecessors(node))) == 0]
    print(roots)
    for root in roots:
        all_nodes.remove(root)
        
    node_simantic_sim = [semantic_similarity(node, x) for x in all_nodes]
    node_struct_sim = [structure_similarity_simple(node, x) for x in all_nodes]
    node_simantic_sim = normalize_score(node_simantic_sim)
    node_struct_sim = normalize_score(node_struct_sim)
    node_sim = [node_simantic_sim[i] + node_struct_sim[i] for i in range(len(all_nodes))]
    topk_index = sorted(range(len(node_sim)), key=lambda i: node_sim[i], reverse=True)[:K]
    for i in topk_index:
        print(f"Node {node.node_id} and Node {all_nodes[i].node_id} have similarity {node_struct_sim[i]}, {node_simantic_sim[i]}")
    return [all_nodes[i] for i in topk_index]

def jaccard_similarity(node1:LLMDAGNODE, node2:LLMDAGNODE, dag:nx.DiGraph):
    """
    Compute the similarity of two node by their input attributes
    """
    # parent_node1 = dag.predecessors(node1)[0]
    parent_node2 = list(dag.predecessors(node2))[0]
    attr1 = set(node1.column_info.keys())
    attr2 = set(parent_node2.column_info.keys())
    return len(attr1.intersection(attr2)) / len(attr1.union(attr2))

def nodes2example(nodes:list[LLMDAGNODE], dag:nx.DiGraph):
    """
    Convert a node to a example
    """
    node_ids = [node.node_id for node in nodes]
    print("Nodes for Example are: ", node_ids)
    whole_str = f"Here are {len(nodes)} examples, each illustrating the impact (increase/decrease) on the overall performance of a model after adding a new feature to a dataframe. These examples aim to provide guidance on generating new features.\n"
    for idx, node in enumerate(nodes):
        parent_node = list(dag.predecessors(node))[0]
        score_pa, score_ch = parent_node.final_score, node.final_score
        new_feature = node.column_info.keys() - parent_node.column_info.keys()
        if score_pa > score_ch:
            performance_result = f"decrease {100*(score_pa - score_ch)}%"
        else: 
            performance_result = f"increase {100*(score_ch - score_pa)}%"
        original_feature = parent_node.column_info.keys()
        original_feature_str = "[ " + ", ".join(original_feature) + "]"
        whole_str += f"Memory {idx}: {SINGLE_EXAMPLE.format(new_feature=new_feature, original_feature = original_feature_str, performance_result = performance_result)}\n"
    return whole_str

def RAG_similarity(node1:LLMDAGNODE, node2:LLMDAGNODE, dag:nx.DiGraph):
    """
    Compute the similarity of two nodes by their RAG
    """
    sem_sim = semantic_similarity(node1, node2)
    struct_sim = structure_similarity_simple(node1, node2)
    print(f"Node[{node1.node_id}|{node2.node_id}] Semantic Similarity: {sem_sim}, Structure Similarity: {struct_sim}")
    return sem_sim * struct_sim


def semantic_similarity(node1:LLMDAGNODE, node2:LLMDAGNODE):
    """
    Compute the semantic similarity of two nodes
    """
    assert node1.attr_embs.shape[-1] == node2.attr_embs.shape[-1]
    scores = node1.attr_embs @ node2.attr_embs.T
    return scores.mean()

def structure_similarity_simple(node1:LLMDAGNODE, node2:LLMDAGNODE):
    """
    Compute the structure similarity of two nodes
    Here we just compute the number of common attributes used in the new attributes
    """
    assert max(len(node1.read_set), len(node2.read_set)) > 0
    overlapping_attr = set(node1.read_set).intersection(set(node2.read_set))
    return len(overlapping_attr) / max(len(node1.read_set), len(node2.read_set))


