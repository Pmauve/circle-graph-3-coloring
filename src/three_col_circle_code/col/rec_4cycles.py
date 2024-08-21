from three_col_circle_code.util import *


def find_all_four_cycles(c_graph):
    all_four_cycles = find_all_double_encased_four_cycles(c_graph) + find_all_four_cycles_with_min_max_chord(c_graph)
    return all_four_cycles


def find_four_cycles_over_all_levels(c_graph):
    all_four_cycles = find_double_encased_four_cycles_over_all_levels(
        c_graph) + find_four_cycles_with_min_max_chord_over_all_levels(c_graph)
    return all_four_cycles


def find_double_encased_four_cycles_over_all_levels(c_graph):
    fcycles = []
    for i in c_graph.nodes:
        node_i = c_graph.nodes[i]  # s
        r_neighborhood = get_right_neighbors(c_graph, node_i)  # get all right neighbors of i
        dir_encased_i = get_encased_by(c_graph, node_i)  # get all chords directly encased by i
        for node_r in r_neighborhood:  # t
            encased_r = get_encased_by(c_graph, node_r)  # get all chords directly encased by r
            for node_enc_i in dir_encased_i:  # s'
                if not are_crossing_chords(node_r, node_enc_i):
                    continue
                node_enc_i_r_nh = get_right_neighbors(c_graph, node_enc_i)
                # must be a right neighbor of the chords dir enc_i AND dir enc_r
                intersection = get_intersection_ids_from_nodes(node_enc_i_r_nh, encased_r, r_neighborhood)
                if len(intersection) < 1:
                    continue
                for intsec in intersection:  # t'
                    node_int = c_graph.nodes[intsec]
                    result = [node_i, node_enc_i, node_r, node_int]
                    fcycle = {"id": f"Sq1-{len(fcycles)}",
                              "opposites1": [node_i['label'], node_enc_i['label']],
                              "opposites2": [node_r['label'], node_int['label']],
                              "nodes": map_nodes_to_label(result)}
                    fcycles.append(fcycle)
                    for n in result:
                        n['importantsubgraphs'].append(fcycle)
    return fcycles


# Diss: 4a
def find_all_double_encased_four_cycles(c_graph):
    fcycles = []
    for i in c_graph.nodes:
        node_i = c_graph.nodes[i]  # s
        r_neighborhood = get_right_neighbors(c_graph, node_i)  # get all right neighbors of i
        dir_encased_i = get_directly_encased_by(c_graph, node_i)  # get all chords directly encased by i
        for node_r in r_neighborhood:  # t
            dir_encased_r = get_directly_encased_by(c_graph, node_r)  # get all chords directly encased by r
            for node_enc_i in dir_encased_i:  # s'
                if not are_crossing_chords(node_r, node_enc_i):
                    continue
                node_enc_i_r_nh = get_right_neighbors(c_graph, node_enc_i)
                # must be a right neighbor of the chords dir enc_i AND dir enc_r
                intersection = get_intersection_ids_from_nodes(node_enc_i_r_nh, dir_encased_r, r_neighborhood)
                if len(intersection) < 1:
                    continue
                for intsec in intersection:  # t'
                    node_int = c_graph.nodes[intsec]
                    result = [node_i, node_enc_i, node_r, node_int]
                    fcycle = {"id": f"Sq1-{len(fcycles)}",
                              "opposites1": [node_i['label'], node_enc_i['label']],
                              "opposites2": [node_r['label'], node_int['label']],
                              "nodes": map_nodes_to_label(result)}
                    fcycles.append(fcycle)
                    for n in result:
                        n['importantsubgraphs'].append(fcycle)
    return fcycles


def find_four_cycles_with_min_max_chord_over_all_levels(c_graph):
    fcycles = []
    for i in c_graph.nodes:
        node_i = c_graph.nodes[i]  # s
        encased_i = get_encased_by(c_graph, node_i)  # get all chords directly encased by i
        for node_enc in encased_i:  # s'
            left_nh_i = get_left_neighbors(c_graph, node_i)
            right_nh_i = get_right_neighbors(c_graph, node_i)
            left_nh_enc = get_left_neighbors(c_graph, node_enc)
            right_nh_enc = get_right_neighbors(c_graph, node_enc)
            find_left = get_intersection_ids_from_nodes(left_nh_i, left_nh_enc)
            find_right = get_intersection_ids_from_nodes(right_nh_i, right_nh_enc)
            if len(find_left) < 1 or len(find_right) < 1:
                continue
            for n_r in find_right:
                node_r = c_graph.nodes[n_r]
                for n_l in find_left:
                    node_l = c_graph.nodes[n_l]
                    if are_crossing_chords(node_r, node_l):
                        continue
                    result = [node_r, node_i, node_enc, node_l]
                    fcycle = {"id": f"Sq2-{len(fcycles)}",
                              "opposites1": [node_i['label'], node_enc['label']],
                              "opposites2": [node_l['label'], node_r['label']],
                              "nodes": map_nodes_to_label(result)}
                    fcycles.append(fcycle)
                    for n in result:
                        n['importantsubgraphs'].append(fcycle)
    return fcycles


# Diss: 4b
def find_all_four_cycles_with_min_max_chord(c_graph):
    fcycles = []
    for i in c_graph.nodes:
        node_i = c_graph.nodes[i]  # s
        dir_encased_i = get_directly_encased_by(c_graph, node_i)  # get all chords directly encased by i
        for node_enc in dir_encased_i:  # s'
            left_nh_i = get_left_neighbors(c_graph, node_i)
            right_nh_i = get_right_neighbors(c_graph, node_i)
            left_nh_enc = get_left_neighbors(c_graph, node_enc)
            right_nh_enc = get_right_neighbors(c_graph, node_enc)
            # find_max = set.intersection(*map(set, left_nh_i + left_nh_enc))
            find_max = get_intersection_ids_from_nodes(left_nh_i, left_nh_enc)
            # find_min = set.intersection(*map(set, right_nh_i + right_nh_enc))
            find_min = get_intersection_ids_from_nodes(right_nh_i, right_nh_enc)
            if len(find_max) < 1 or len(find_min) < 1:
                continue
            max_node = c_graph.nodes[max(find_max)]  # x
            min_node = c_graph.nodes[min(find_min)]  # y
            if are_crossing_chords(max_node, min_node):
                continue
            result = [max_node, node_i, node_enc, min_node]
            fcycle = {"id": f"Sq2-{len(fcycles)}",
                      "opposites1": [node_i['label'], node_enc['label']],
                      "opposites2": [min_node['label'], max_node['label']],
                      "nodes": map_nodes_to_label(result)}
            fcycles.append(fcycle)
            for n in result:
                n['importantsubgraphs'].append(fcycle)
    return fcycles
