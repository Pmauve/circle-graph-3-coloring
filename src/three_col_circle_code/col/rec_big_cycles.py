from three_col_circle_code.util import *


def find_all_big_cycles(c_graph):
    all_big_cycles = {
        **find_all_big_cycles_with_min_max_node(c_graph), **find_all_big_cycles_with_direct_encasing(c_graph)}
    return all_big_cycles


def find_all_big_cycles_with_min_max_node(c_graph):
    cycles = {}
    for i in c_graph.nodes:
        node_i = c_graph.nodes[i]
        dir_enc = set(map_nodes_to_label(get_directly_encased_by(c_graph, node_i)))
        n_level = set(map_nodes_to_label(get_level(c_graph, node_i['level'] + 1)))
        n_level_and_dir_enc = sort_by_left_endpoint(map_id_to_nodes(c_graph, dir_enc.intersection(n_level)))
        if len(n_level_and_dir_enc) < 3 or not is_induced_subgraph_connected(c_graph, n_level_and_dir_enc):
            continue
        max_nodes = [None] * len(n_level_and_dir_enc)  # g
        min_nodes = [None] * len(n_level_and_dir_enc)  # h
        for j in range(1, len(n_level_and_dir_enc)):
            l_nh_to_intersect = set(map_nodes_to_label(get_left_neighbors(c_graph, n_level_and_dir_enc[j - 1]))) - set(
                map_nodes_to_label(get_left_neighbors(c_graph, n_level_and_dir_enc[j])))
            find_max = set.intersection(
                *map(set, [l_nh_to_intersect] + [map_nodes_to_label(get_left_neighbors(c_graph, node_i))]))
            if len(find_max) > 0:
                max_nodes[j - 1] = get_max_id(map_id_to_nodes(c_graph, find_max))
            r_nh_to_intersect = set(map_nodes_to_label(get_right_neighbors(c_graph, n_level_and_dir_enc[j]))) - set(
                map_nodes_to_label(get_right_neighbors(c_graph, n_level_and_dir_enc[j - 1])))
            find_min = set.intersection(
                *map(set, [r_nh_to_intersect] + [map_nodes_to_label(get_right_neighbors(c_graph, node_i))]))
            if len(find_min) > 0:
                min_nodes[j] = get_min_id(map_id_to_nodes(c_graph, find_min))
        for p in range(0, len(n_level_and_dir_enc)):
            append = False
            if max_nodes[p] is None:
                continue
            for q in range(1, len(min_nodes)):
                if not p + 1 < q:
                    continue
                if min_nodes[q] is None:
                    continue
                for k in range(p + 1, q):
                    if not max_nodes[k] is None or not min_nodes[k] is None:
                        append = False
                        break
                    append = True
                if not append:
                    continue
                cycle_path = []
                for k in range(p, min(len(n_level_and_dir_enc), q + 1)):
                    cycle_path.append(n_level_and_dir_enc[k])
                dir_enc_subgraph = get_induced_subgraph_from_nodes(c_graph, cycle_path)
                result = [node_i, c_graph.nodes[max_nodes[p]]]
                if has_cycle(dir_enc_subgraph):
                    n_level_and_dir_enc = get_cycle_nodes_for_path(cycle_path, c_graph.nodes[max_nodes[p]],
                                                       c_graph.nodes[min_nodes[q]])
                    for k in range(len(n_level_and_dir_enc)):
                        result.append(n_level_and_dir_enc[k])
                else:
                    for k in range(p, min(len(n_level_and_dir_enc), q + 1)):
                        result.append(n_level_and_dir_enc[k])
                result.append(c_graph.nodes[min_nodes[q]])
                if len(result) < 6:
                    continue
                cycle = {"id": f"Cyc1-{len(cycles)}",
                         "nodes": map_nodes_to_label(result)}
                cycles[f"Cyc1-{len(cycles)}"] = cycle
                for n in result:
                    n['importantsubgraphs'].append(cycle)
    return cycles


def find_all_big_cycles_with_direct_encasing(c_graph):
    cycles = {}
    for i in c_graph.nodes():
        node_i = c_graph.nodes[i]
        dir_enc = set(map_nodes_to_label(get_directly_encased_by(c_graph, node_i)))
        n_level = set(map_nodes_to_label(get_level(c_graph, node_i['level'] + 1)))
        n_level_and_dir_enc = sort_by_left_endpoint(map_id_to_nodes(c_graph, dir_enc.intersection(n_level))) # U(i)
        if len(n_level_and_dir_enc) < 3 or not is_induced_subgraph_connected(c_graph, n_level_and_dir_enc):
            continue
        max_nodes = [None] * len(n_level_and_dir_enc)
        min_nodes = [None] * len(n_level_and_dir_enc)
        for j in range(1, len(n_level_and_dir_enc)):
            r_nh_to_intersect_for_max = set(map_nodes_to_label(get_right_neighbors(c_graph, n_level_and_dir_enc[j - 1]))) - set(
                map_nodes_to_label(get_right_neighbors(c_graph, n_level_and_dir_enc[j])))
            find_max = set.intersection(
                *map(set, [r_nh_to_intersect_for_max] + [map_nodes_to_label(get_right_neighbors(c_graph, node_i))]))
            if len(find_max) > 0:
                max_nodes[j - 1] = get_max_id(map_id_to_nodes(c_graph, find_max))
            r_nh_to_intersect_for_min = set(map_nodes_to_label(get_right_neighbors(c_graph, n_level_and_dir_enc[j]))) - set(
                map_nodes_to_label(get_right_neighbors(c_graph, n_level_and_dir_enc[j - 1])))
            find_min = set.intersection(
                *map(set, [r_nh_to_intersect_for_min] + [map_nodes_to_label(get_right_neighbors(c_graph, node_i))]))
            if len(find_min) > 0:
                min_nodes[j] = get_min_id(map_id_to_nodes(c_graph, find_min))
        for p in range(0, len(n_level_and_dir_enc)):
            append = False
            if max_nodes[p] is None:
                continue
            for q in range(1, len(min_nodes)):
                if not p + 1 < q:
                    continue
                if min_nodes[q] is None or min_nodes[q] == max_nodes[p] or min_nodes[q] not in map_nodes_to_label(
                        get_directly_encased_by(c_graph, c_graph.nodes[max_nodes[p]])):
                    continue
                for k in range(p + 1, q):
                    if not max_nodes[k] is None or not min_nodes[k] is None:
                        append = False
                        break
                    append = True
                if not append:
                    continue
                cycle_path = []
                for k in range(p, min(len(n_level_and_dir_enc), q + 1)):
                    cycle_path.append(n_level_and_dir_enc[k])
                dir_enc_subgraph = get_induced_subgraph_from_nodes(c_graph, cycle_path)
                result = [node_i, c_graph.nodes[max_nodes[p]]]
                if has_cycle(dir_enc_subgraph):
                    n_level_and_dir_enc = get_cycle_nodes_for_path(cycle_path, c_graph.nodes[max_nodes[p]],
                                                       c_graph.nodes[min_nodes[q]])
                    for k in range(len(n_level_and_dir_enc)):
                        result.append(n_level_and_dir_enc[k])
                else:
                    for k in range(p, min(len(n_level_and_dir_enc), q + 1)):
                        result.append(n_level_and_dir_enc[k])
                result.append(c_graph.nodes[min_nodes[q]])
                if len(result) < 6:
                    continue
                cycle = {"id": f"Cyc2-{len(cycles)}",
                         "nodes": map_nodes_to_label(result)}
                cycles[f"Cyc2-{len(cycles)}"] = cycle
                for n in result:
                    n['importantsubgraphs'].append(cycle)
    return cycles
