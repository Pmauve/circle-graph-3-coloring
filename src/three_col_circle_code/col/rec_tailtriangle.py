# Input: Circle graph with no clique lager than 3
# Output: List of important subgraphs G_tailtriangle
from three_col_circle_code.util import *


def find_all_tailtriangles(c_graph):
    all_tailtriangles = find_all_tailtriangles_within_one_level(c_graph) + find_all_tailtriangles_within_two_levels(
        c_graph)
    return all_tailtriangles


def find_tailtriangles_over_all_levels(c_graph):
    tailtriangles = []
    tailtriangles_set = set()
    for i in c_graph.nodes:
        node_i = c_graph.nodes[i]
        i_not_nh = get_non_adjacent(c_graph, node_i)  # get all non-adj vertices
        i_right_nh = get_right_neighbors(c_graph, node_i)
        for node_r in i_right_nh + [node_i]:  # s'
            r_not_nh = get_non_adjacent(c_graph, node_r)
            # we want to find all tailtriangles over any number of levels
            intersection = get_intersection_ids_from_nodes(i_not_nh, r_not_nh)  # T'
            if len(intersection) < 1:
                continue
            intersection_list = list(intersection)
            all_subsets = find_all_n_pair_combinations(intersection_list) + [[int_node] for int_node in
                                                                             intersection_list]
            for subset in all_subsets:
                if len(subset) == 1 and subset[0] in {node_i['label'], node_r['label']}:
                    continue
                if len({node_i['label'], node_r['label']}) == 1 and node_i['label'] in subset:
                    continue
                neighborhoods = []
                # T U T' -> different from Diss, we only look at the resp. subsets
                for node in [node_i, node_r] + map_id_to_nodes(c_graph, subset):
                    neighborhoods.append(get_all_neighbors(c_graph, node))
                centers = get_intersection_ids_from_nodes(*neighborhoods)
                if len(centers) < 1:
                    continue
                for c in centers:
                    center = c_graph.nodes[c]
                    result_ids = frozenset({center['label'], node_i['label'], node_r['label']}.union(subset))
                    if result_ids in tailtriangles_set:
                        continue
                    if len({node_i['label'], node_r['label']}) == 1 and len(subset) == 2:
                        result = [center, node_i] + map_id_to_nodes(c_graph, subset)
                        tailtriangle = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                        "nodes": list(result_ids),
                                        "left_nh": [node_i['label']],
                                        "right_nh": subset}
                        tailtriangles.append(tailtriangle)
                        for n in result:
                            n['importantsubgraphs'].append(tailtriangle)
                        tailtriangles_set.add(result_ids)
                    elif len({node_i['label'], node_r['label']}) == 2 and len(subset) == 1:
                        result = [center, node_i, node_r] + map_id_to_nodes(c_graph, subset)
                        tailtriangle = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                        "nodes": list(result_ids),
                                        "left_nh": subset,
                                        "right_nh": [node_i['label'], node_r['label']]}
                        tailtriangles.append(tailtriangle)
                        for n in result:
                            n['importantsubgraphs'].append(tailtriangle)
                        tailtriangles_set.add(result_ids)
                    elif len({node_i['label'], node_r['label']}) == 2 and len(subset) == 2:
                        result_1 = [center, node_i, node_r] + map_id_to_nodes(c_graph, [subset[0]])
                        result_2 = [center, node_i, node_r] + map_id_to_nodes(c_graph, [subset[1]])
                        result_3 = [center, node_i] + map_id_to_nodes(c_graph, subset)
                        result_4 = [center, node_r] + map_id_to_nodes(c_graph, subset)
                        tailtriangle_1 = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                          "nodes": map_nodes_to_label(result_1),
                                          "left_nh": [subset[0]],
                                          "right_nh": [node_i['label'], node_r['label']]}
                        tailtriangles.append(tailtriangle_1)
                        tailtriangle_2 = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                          "nodes": map_nodes_to_label(result_2),
                                          "left_nh": [subset[1]],
                                          "right_nh": [node_i['label'], node_r['label']]}
                        tailtriangles.append(tailtriangle_2)
                        tailtriangle_3 = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                          "nodes": map_nodes_to_label(result_3),
                                          "left_nh": [node_i['label']],
                                          "right_nh": subset}
                        tailtriangles.append(tailtriangle_3)
                        tailtriangle_4 = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                          "nodes": map_nodes_to_label(result_4),
                                          "left_nh": [node_r['label']],
                                          "right_nh": subset}
                        tailtriangles.append(tailtriangle_4)
                        for n in result_1:
                            n['importantsubgraphs'].append(tailtriangle_1)
                        for n in result_2:
                            n['importantsubgraphs'].append(tailtriangle_2)
                        for n in result_3:
                            n['importantsubgraphs'].append(tailtriangle_3)
                        for n in result_4:
                            n['importantsubgraphs'].append(tailtriangle_4)
                        tailtriangles_set.add(result_ids)
                        tailtriangles_set.add(frozenset(map_nodes_to_label(result_1)))
                        tailtriangles_set.add(frozenset(map_nodes_to_label(result_2)))
                        tailtriangles_set.add(frozenset(map_nodes_to_label(result_3)))
                        tailtriangles_set.add(frozenset(map_nodes_to_label(result_4)))
    return tailtriangles


# Diss: Typ 2a - 2d
def find_all_tailtriangles_within_one_level(c_graph):
    tailtriangles = []
    level_nr = get_graph_level(c_graph)
    for lev in range(1, level_nr + 1):
        this_level = get_level(c_graph, lev)
        for node in this_level:
            # for lev_left_nh in range(1, level_nr + 1):
            left_nh = get_left_neighbors_on_level(c_graph, node, lev)
            # for lev_right_nh in range(1, level_nr + 1):
            right_nh = get_right_neighbors_on_level(c_graph, node, lev)
            if len(left_nh) < 1 or len(right_nh) < 1:
                continue
            if are_neighbors(c_graph, get_max(left_nh), get_min(right_nh)):
                continue
            if len(left_nh) == 1 and len(right_nh) == 2:
                result = [node] + left_nh + right_nh
                tailtriangle = {"id": f"{TAILTRIANGLE_ONE_LVL_ID}-{len(tailtriangles)}",
                                "nodes": map_nodes_to_label(result),
                                "left_nh": map_nodes_to_label(left_nh),
                                "right_nh": map_nodes_to_label(right_nh)}
                tailtriangles.append(tailtriangle)
                for n in result:
                    n['importantsubgraphs'].append(tailtriangle)
            if len(left_nh) == 2 and len(right_nh) == 1:
                result = [node] + right_nh + left_nh
                tailtriangle = {"id": f"{TAILTRIANGLE_ONE_LVL_ID}-{len(tailtriangles)}",
                                "nodes": map_nodes_to_label(result),
                                "left_nh": map_nodes_to_label(right_nh),
                                "right_nh": map_nodes_to_label(left_nh)}
                tailtriangles.append(tailtriangle)
                for n in result:
                    n['importantsubgraphs'].append(tailtriangle)
            if len(left_nh) == 2 and len(right_nh) == 2:
                result_1 = [node] + [left_nh[0]] + right_nh
                tailtriangle_1 = {"id": f"{TAILTRIANGLE_ONE_LVL_ID}-{len(tailtriangles)}",
                                  "nodes": map_nodes_to_label(result_1),
                                  "left_nh": map_nodes_to_label([left_nh[0]]),
                                  "right_nh": map_nodes_to_label(right_nh)}
                tailtriangles.append(tailtriangle_1)
                for n in result_1:
                    n['importantsubgraphs'].append(tailtriangle_1)
                result_2 = [node] + [left_nh[1]] + right_nh
                tailtriangle_2 = {"id": f"{TAILTRIANGLE_ONE_LVL_ID}-{len(tailtriangles)}",
                                  "nodes": map_nodes_to_label(result_2),
                                  "left_nh": map_nodes_to_label([left_nh[1]]),
                                  "right_nh": map_nodes_to_label(right_nh)}
                tailtriangles.append(tailtriangle_2)
                for n in result_2:
                    n['importantsubgraphs'].append(tailtriangle_2)
                result_3 = [node] + left_nh + [right_nh[0]]
                tailtriangle_3 = {"id": f"{TAILTRIANGLE_ONE_LVL_ID}-{len(tailtriangles)}",
                                  "nodes": map_nodes_to_label(result_3),
                                  "left_nh": map_nodes_to_label([right_nh[0]]),
                                  "right_nh": map_nodes_to_label(left_nh)}
                tailtriangles.append(tailtriangle_3)
                for n in result_3:
                    n['importantsubgraphs'].append(tailtriangle_3)
                result_4 = [node] + left_nh + [right_nh[1]]
                tailtriangle_4 = {"id": f"{TAILTRIANGLE_ONE_LVL_ID}-{len(tailtriangles)}",
                                  "nodes": map_nodes_to_label(result_4),
                                  "left_nh": map_nodes_to_label([right_nh[1]]),
                                  "right_nh": map_nodes_to_label(left_nh)}
                tailtriangles.append(tailtriangle_4)
                for n in result_4:
                    n['importantsubgraphs'].append(tailtriangle_4)
    return tailtriangles


# Diss: Typ 2a' - 2d'
def find_all_tailtriangles_within_two_levels(c_graph):
    tailtriangles = []
    tailtriangles_set = set()
    lvl = get_graph_level(c_graph)
    for level in range(1, lvl):
        curr_l = get_level(c_graph, level)
        next_l = get_level(c_graph, level + 1)
        for node_i in curr_l:
            dir_enc_i = get_directly_encased_by(c_graph, node_i)
            i_right_nh = get_right_neighbors_on_level(c_graph, node_i, node_i['level'])
            for node_r in i_right_nh + [node_i]:  # s'
                dir_enc_r = get_directly_encased_by(c_graph, node_r)
                # from paper: doesn't have to be only in next level, only directly enc
                intersection = get_intersection_ids_from_nodes(dir_enc_i, dir_enc_r)  # T'
                if len(intersection) < 1:
                    continue
                intersection_list = list(intersection)
                all_subsets = find_all_n_pair_combinations(intersection_list) + [[int_node] for int_node in
                                                                                 intersection_list]
                for subset in all_subsets:
                    neighborhoods = []
                    # T U T' -> different from Diss, we only look at the resp. subsets
                    for node in [node_i, node_r] + map_id_to_nodes(c_graph, subset):
                        neighborhoods.append(get_all_neighbors(c_graph, node))
                    find_min = get_intersection_ids_from_nodes(*neighborhoods)
                    if len(find_min) < 1:
                        continue
                    min_node = get_min(map_id_to_nodes(c_graph, find_min))
                    result_ids = frozenset({min_node['label'], node_i['label'], node_r['label']}.union(subset))
                    if result_ids in tailtriangles_set:
                        continue
                    if len({node_i['label'], node_r['label']}) == 1 and len(subset) == 2:
                        result = [min_node, node_i] + map_id_to_nodes(c_graph, subset)
                        tailtriangle = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                        "nodes": list(result_ids),
                                        "left_nh": [node_i['label']],
                                        "right_nh": subset}
                        tailtriangles.append(tailtriangle)
                        for n in result:
                            n['importantsubgraphs'].append(tailtriangle)
                        tailtriangles_set.add(result_ids)
                    elif len({node_i['label'], node_r['label']}) == 2 and len(subset) == 1:
                        result = [min_node, node_i, node_r] + map_id_to_nodes(c_graph, subset)
                        tailtriangle = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                        "nodes": list(result_ids),
                                        "left_nh": subset,
                                        "right_nh": [node_i['label'], node_r['label']]}
                        tailtriangles.append(tailtriangle)
                        for n in result:
                            n['importantsubgraphs'].append(tailtriangle)
                        tailtriangles_set.add(result_ids)
                    elif len({node_i['label'], node_r['label']}) == 2 and len(subset) == 2:
                        result_1 = [min_node, node_i, node_r] + map_id_to_nodes(c_graph, [subset[0]])
                        result_2 = [min_node, node_i, node_r] + map_id_to_nodes(c_graph, [subset[1]])
                        result_3 = [min_node, node_i] + map_id_to_nodes(c_graph, subset)
                        result_4 = [min_node, node_r] + map_id_to_nodes(c_graph, subset)
                        tailtriangle_1 = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                          "nodes": map_nodes_to_label(result_1),
                                          "left_nh": [subset[0]],
                                          "right_nh": [node_i['label'], node_r['label']]}
                        tailtriangles.append(tailtriangle_1)
                        tailtriangle_2 = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                          "nodes": map_nodes_to_label(result_2),
                                          "left_nh": [subset[1]],
                                          "right_nh": [node_i['label'], node_r['label']]}
                        tailtriangles.append(tailtriangle_2)
                        tailtriangle_3 = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                          "nodes": map_nodes_to_label(result_3),
                                          "left_nh": [node_i['label']],
                                          "right_nh": subset}
                        tailtriangles.append(tailtriangle_3)
                        tailtriangle_4 = {"id": f"{TAILTRIANGLE_TWO_LVL_ID}-{len(tailtriangles)}",
                                          "nodes": map_nodes_to_label(result_4),
                                          "left_nh": [node_r['label']],
                                          "right_nh": subset}
                        tailtriangles.append(tailtriangle_4)
                        for n in result_1:
                            n['importantsubgraphs'].append(tailtriangle_1)
                        for n in result_2:
                            n['importantsubgraphs'].append(tailtriangle_2)
                        for n in result_3:
                            n['importantsubgraphs'].append(tailtriangle_3)
                        for n in result_4:
                            n['importantsubgraphs'].append(tailtriangle_4)
                        tailtriangles_set.add(result_ids)
                        tailtriangles_set.add(frozenset(map_nodes_to_label(result_1)))
                        tailtriangles_set.add(frozenset(map_nodes_to_label(result_2)))
                        tailtriangles_set.add(frozenset(map_nodes_to_label(result_3)))
                        tailtriangles_set.add(frozenset(map_nodes_to_label(result_4)))
    return tailtriangles
