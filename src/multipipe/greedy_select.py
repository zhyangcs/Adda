from src.multipipe import *

sio_cost_per_byte = 1.5e-8
lio_cost_per_byte = 1.5e-10
cpu_join_cost = 1e-6
scost, lcost, jcost = 0, 0, 0    
res_pipe = []

def multipipe_whole(pipes:list, storage_attr:int, num_of_record:int):
    """
    the whole process of greedy algorithm
    """
    global scost, lcost, jcost, res_pipe
    scost = sio_cost_per_byte * num_of_record * 8
    lcost = lio_cost_per_byte * num_of_record * 8
    jcost = num_of_record * 2 * cpu_join_cost
    O, M = [], []
    res_pipe = [i for i in range(len(pipes))]
    while len(res_pipe) > 0:
        n = max_time_saving(pipes, res_pipe, M)
        res_pipe.remove(n)
        O = O + [n]
        if storage_attr != 0:
            M1 = greedy_materialize(n, storage_attr, pipes, M)
            M, storage_attr = M + M1, storage_attr - len(M1)
    return O
        
def max_time_saving(pipes:list, res_pipe:list, M:list):
    """
    compute the time could be saved when set each pipe to the first
    """
    time_save_map = {}
    for pipeid in res_pipe:
        t_save = 0
        cur_pipe = pipes[pipeid]
        for treehash, res_attr in cur_pipe.hash2resAttr.items():
            if res_attr not in M:
                # compute the reuse time [rep_{Ai}]
                rep = 0
                for otherpipeid in res_pipe:
                    if otherpipeid != pipeid:
                        if treehash in pipes[otherpipeid].hash2inAttr.keys():
                            rep += 1
        if scost <= (cur_pipe.resAttr2Ti[res_attr] - lcost - jcost) * rep:
            t_save += ((cur_pipe.resAttr2Ti[res_attr] - lcost - jcost) * rep - scost)
        
        time_save_map[pipeid] = t_save
    # return the pipeid of the largest time saving
    return max(time_save_map, key=time_save_map.get)

def greedy_materialize(pipeid, storage_budget:int, pipes:list, M:list):
    """
    materialize all the attributes leads to the accelerate until the budget is used up
    """
    global res_pipe
    M1 = []
    cur_pipe = pipes[pipeid]
    for treehash, res_attr in pipes[pipeid].hash2resAttr.items():
        if res_attr not in M:
            rep = 0
            for otherpipeid in range(len(pipes)):
                if otherpipeid != pipeid:
                    if treehash in pipes[otherpipeid].hash2inAttr.keys():
                        rep += 1
            if scost <= (pipes[pipeid].resAttr2Ti[res_attr] - lcost - jcost) * rep:
                cur_pipe.resAttr2isStore[res_attr] = True
                M1.append(res_attr)
                storage_budget -= 1
                # set the reuse for the following pipes if All_Set use the attribute
                for otherpipeid in res_pipe:
                    next_pipe = pipes[otherpipeid]
                    if treehash in next_pipe.hash2inAttr.keys():
                        new_attr = next_pipe.hash2inAttr[treehash]
                        next_pipe.reusemap[new_attr] = (pipeid, res_attr)     
                if storage_budget <= 0:
                    return M1
    return M1