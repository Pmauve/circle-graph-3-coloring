from three_col_circle_code.util import *


def find_all_boxslashes(c_graph):
    all_five_cycles = find_all_boxslashes_within_one_level(c_graph) + find_all_boxslashes_within_two_levels(c_graph)
    return all_five_cycles


def find_boxslashes_over_all_levels(c_graph):
    boxslashes = []
    boxslashes_set = set()
    for i in c_graph.nodes:
        node_i = c_graph.nodes[i]
        r_neighbors = get_right_neighbors(c_graph, node_i)
        for r_neighbor in r_neighbors:
            find_r = [map_nodes_to_label(get_left_neighbors(c_graph, node_i))] + [
                map_nodes_to_label(get_left_neighbors(c_graph, r_neighbor))]
            find_r = set.intersection(*map(set, find_r))  # find shared max right neighbor
            find_l = [map_nodes_to_label(get_right_neighbors(c_graph, node_i))] + [
                map_nodes_to_label(get_right_neighbors(c_graph, r_neighbor))]
            find_l = set.intersection(*map(set, find_l))  # find shared min left neighbor
            if len(find_r) < 1 or len(find_l) < 1:
                continue
            for node_l in map_id_to_nodes(c_graph, find_r):
                for node_r in map_id_to_nodes(c_graph, find_l):
                    result = [node_i, r_neighbor, node_l, node_r]
                    boxslash = {"id": f"BSq1-{len(boxslashes)}",
                                "opposites": [node_r['label'], node_l['label']],
                                "nodes": map_nodes_to_label(result)}
                    boxslashes.append(boxslash)
                    for n in result:
                        n['importantsubgraphs'].append(boxslash)
    level_nr = get_graph_level(c_graph)
    exclude_level = get_level(c_graph, level_nr)
    for i in c_graph.nodes - map_nodes_to_label(exclude_level):
        node_i = c_graph.nodes[i]  # s
        encased = get_encased_by(c_graph, node_i)
        for node_e in encased:  # s'
            nh_i = map_nodes_to_label(get_all_neighbors(c_graph, node_i))
            nh_e = map_nodes_to_label(get_all_neighbors(c_graph, node_e))
            intersection = set.intersection(*map(set, [nh_i] + [nh_e]))
            if len(intersection) < 1:
                continue
            for int_a in intersection:
                for int_b in intersection - {int_a}:
                    curr_boxslash = frozenset({i, node_e['label'], int_a, int_b})
                    node_int_a = c_graph.nodes[int_a]
                    node_int_b = c_graph.nodes[int_b]
                    if are_crossing_chords(node_int_a, node_int_b) and not (curr_boxslash in boxslashes_set):
                        result = [node_i, node_e, node_int_a, node_int_b]
                        boxslash = {"id": f"BSq2-{len(boxslashes)}",
                                    "opposites": [node_i['label'], node_e['label']],
                                    "nodes": map_nodes_to_label(result)}
                        boxslashes.append(boxslash)
                        for n in result:
                            n['importantsubgraphs'].append(boxslash)
                        boxslashes_set.add(curr_boxslash)
    return boxslashes


# Diss: Typ 3b
def find_all_boxslashes_within_one_level(c_graph):
    boxslashes = []
    for i in c_graph.nodes:
        node_i = c_graph.nodes[i]
        r_neighbors = get_right_neighbors(c_graph, node_i)
        for r_neighbor in r_neighbors:
            find_max = [map_nodes_to_label(get_left_neighbors(c_graph, node_i))] + [
                map_nodes_to_label(get_left_neighbors(c_graph, r_neighbor))]
            find_max = set.intersection(*map(set, find_max))  # find shared max right neighbor
            find_min = [map_nodes_to_label(get_right_neighbors(c_graph, node_i))] + [
                map_nodes_to_label(get_right_neighbors(c_graph, r_neighbor))]
            find_min = set.intersection(*map(set, find_min))  # find shared min left neighbor
            if len(find_max) > 0 and len(find_min) > 0:
                max_node = get_max(map_id_to_nodes(c_graph, find_max))  # u
                min_node = get_min(map_id_to_nodes(c_graph, find_min))  # u'
                result = [node_i, r_neighbor, max_node, min_node]
                boxslash = {"id": f"BSq1-{len(boxslashes)}",
                            "opposites": [min_node['label'], max_node['label']],
                            "nodes": map_nodes_to_label(result)}
                boxslashes.append(boxslash)
                for n in result:
                    n['importantsubgraphs'].append(boxslash)
    return boxslashes


# Diss: Typ 3a
def find_all_boxslashes_within_two_levels(c_graph):
    boxslashes = []
    boxslashes_set = set()
    level_nr = get_graph_level(c_graph)
    exclude_level = get_level(c_graph, level_nr)
    for i in c_graph.nodes - map_nodes_to_label(exclude_level):
        node_i = c_graph.nodes[i]  # s
        dir_encased = get_directly_encased_by(c_graph, node_i)
        for node_e in dir_encased:  # s'
            nh_i = map_nodes_to_label(get_all_neighbors(c_graph, node_i))
            nh_e = map_nodes_to_label(get_all_neighbors(c_graph, node_e))
            intersection = set.intersection(*map(set, [nh_i] + [nh_e]))
            if len(intersection) < 1:
                continue
            for int_a in intersection:
                for int_b in intersection - {int_a}:
                    curr_boxslash = frozenset({i, node_e['label'], int_a, int_b})
                    node_int_a = c_graph.nodes[int_a]
                    node_int_b = c_graph.nodes[int_b]
                    if are_crossing_chords(node_int_a, node_int_b) and not (curr_boxslash in boxslashes_set):
                        result = [node_i, node_e, node_int_a, node_int_b]
                        boxslash = {"id": f"BSq2-{len(boxslashes)}",
                                    "opposites": [node_i['label'], node_e['label']],
                                    "nodes": map_nodes_to_label(result)}
                        boxslashes.append(boxslash)
                        for n in result:
                            n['importantsubgraphs'].append(boxslash)
                        boxslashes_set.add(curr_boxslash)
    return boxslashes
