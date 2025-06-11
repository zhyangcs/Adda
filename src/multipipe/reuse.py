import os

import termcolor

def seq_reuse_opt(pipes:list, storage_attr_num:int, num_of_record:int):
    """
    sequence reuse optimization, the pipe is reordered pipes
    """
    # for load cost, as resAttr is numerical type, so we assume as 8 bytes, and we should add for extra join cost
    # store speed is 67.3 MB/s for our machine so we set the io_cost_per_byte as 1.5e-8
    # load speed is 7000MB/s for cache
    sio_cost_per_byte = 1.5e-8
    lio_cost_per_byte = 1.5e-10
    cpu_join_cost = 1e-6
    scost = sio_cost_per_byte * num_of_record * 8
    lcost = lio_cost_per_byte * num_of_record * 8
    jcost = num_of_record * 2 * cpu_join_cost
    
    # for one attribute load by reuse, it do not need to store
    output_map = {}
    
    
    for i in range(len(pipes)):
        cur_pipe = pipes[i]
        cur_pipe.resAttr2isStore = {attr: False for attr in cur_pipe.hash2resAttr.values()}
        rep = {}
        storage = storage_attr_num
        for treehash, attr in cur_pipe.hash2resAttr.items():
            rep = 0
            # if the attribute reuse the previous attribute, then we do not need to store it
            if attr in cur_pipe.reusemap.keys():
                continue
            if storage == 0:
                break
            # check whether its more efficiency to store the attribute and reuse it comparing to computing it every time.
            for j in range(i+1, len(pipes)):
                next_pipe = pipes[j]
                if treehash in next_pipe.hash2inAttr.keys():
                    rep += 1
            if scost <= (cur_pipe.resAttr2Ti[attr]-lcost-jcost)*rep:
                cur_pipe.resAttr2isStore[attr] = True
                storage -= 1
                if storage == 0:
                    print(termcolor.colored(f"Reuse Optimization Done {output_map}", "green"))
                    return
                
                attr_pipe = []
                for j in range(i+1, len(pipes)):
                    next_pipe = pipes[j]
                    if treehash in next_pipe.hash2inAttr.keys():
                        attr_pipe.append(j)
                        new_attr = next_pipe.hash2inAttr[treehash]
                        next_pipe.reusemap[new_attr] = (i, attr)
                output_map[f"{attr}:{i}"] = attr_pipe
    print(termcolor.colored(f"Reuse Optimization Done {output_map}", "green"))