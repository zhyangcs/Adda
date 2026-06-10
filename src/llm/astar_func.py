import pandas as pd
from src.env import *
import src.env

def monte_carlo_like_heuristic_func(child_num, total_node_num, eval_val):
    """
    use the UCB function to determine the node utility
    """
    exploration = src.env.alpha * math.sqrt(math.log(total_node_num) / child_num)
    exploitation = eval_val
    print(f"Current alpha: {src.env.alpha} exploitation: {exploitation}, exploration: {exploration}")
    return exploitation + exploration