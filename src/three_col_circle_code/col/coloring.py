from three_col_circle_code.util import *
from three_col_circle_code.timer import Timer

coloring_timer = Timer(name="coloring", text="Coloring took {:0.6f} seconds")


def color_with_jumping_bt_assignment(c_graph, assignment):
    color_single_level_bt(c_graph, 1, assignment)
    color_remaining_levels_bt(c_graph, assignment)


def color_single_level_bt(c_graph, level, assignment):
    curr_level = sort_by_left_endpoint(get_level(c_graph, level))
    for node in curr_level:
        if node['color'] > -1:
            continue
        color_single_level_node_bt(c_graph, node, assignment)


def color_single_level_node_bt(c_graph, node, assignment):
    left_nh = get_left_neighbors_on_level(c_graph, node, node['level'])
    extended_left_nh_ids = set()
    for left_n in left_nh:
        left_n_left_nh = get_left_neighbors_on_level(c_graph, left_n, node['level'])
        if len(left_n_left_nh) < 1:
            continue
        extended_left_nh_ids = extended_left_nh_ids.union(set(map_nodes_to_label(left_n_left_nh)))
    extended_left_nh = map_id_to_nodes(c_graph, list(extended_left_nh_ids - set(map_nodes_to_label(left_nh))))
    l_set = set(map_nodes_to_label(left_nh)).union(extended_left_nh_ids)
    if len(l_set) == 0:
        node['color'] = 0
    elif len(l_set) == 1:
        node['color'] = 1
    elif len(l_set) == 2:
        if len(left_nh) == 1:  # then extended_left_nh contains exactly one elem
            left_nh_node = left_nh[0]
            extended_left_nh_node = extended_left_nh[0]
            c_var = frozenset({node['label'], extended_left_nh_node['label']})
            c_value = assignment[c_var]
            if c_value:
                node['color'] = extended_left_nh_node['color']
            else:
                remaining_color = {0, 1, 2} - {extended_left_nh_node['color'], left_nh_node['color']}
                if len(remaining_color) > 0:
                    node['color'] = remaining_color.pop()
                else:
                    print(
                        "fail during coloring single level node, no remaining color for " + str(node['label']))
                    print(
                        "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                             [extended_left_nh_node, left_nh_node]]))
        elif len(left_nh) == 2:
            node['color'] = 2
    elif len(l_set) == 3:
        if len(left_nh) == 1:  # then extended_left_nh has size 2
            extended_left_nh_node = extended_left_nh[0]
            c_var = frozenset({node['label'], extended_left_nh_node['label']})
            c_value = assignment[c_var]
            if c_value:
                node['color'] = extended_left_nh_node['color']
            else:  # node has the same color as the other extended neighbor
                extended_left_nh_node = extended_left_nh[1]
                node['color'] = extended_left_nh_node['color']
        elif len(left_nh) == 2:  # consider position of extended neighbor
            extended_neighbor = extended_left_nh[0]
            if are_crossing_chords(extended_neighbor, left_nh[0]) and are_crossing_chords(extended_neighbor,
                                                                                          left_nh[1]):
                node['color'] = extended_neighbor['color']
            else:
                c_var = frozenset({node['label'], extended_neighbor['label']})
                c_value = assignment[c_var]
                if c_value:
                    node['color'] = extended_neighbor['color']
                else:
                    remaining_color = {0, 1, 2} - {left_nh[0]['color'], left_nh[1]['color']}
                    if len(remaining_color) > 0:
                        node['color'] = remaining_color.pop()
                    else:
                        print(
                            "fail during coloring single level node l -> r, no remaining color for " + str(
                                node['label']))
                        print(
                            "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in left_nh]))
    elif len(l_set) == 4:  # len(left_nh) == len(extended_nh) == 2
        max_extended_left_n = get_max(extended_left_nh)
        min_extended_left_n = get_min(extended_left_nh)
        if are_crossing_chords(max_extended_left_n, left_nh[0]) and are_crossing_chords(max_extended_left_n,
                                                                                        left_nh[1]):
            node['color'] = max_extended_left_n['color']
        else:
            c_var_a = frozenset({node['label'], min_extended_left_n['label']})
            c_value_a = assignment[c_var_a]
            if c_value_a:
                node['color'] = min_extended_left_n['color']
            else:
                node['color'] = max_extended_left_n['color']


def color_remaining_levels_bt(c_graph, assignment):
    level_nr = get_graph_level(c_graph)
    for i in range(1, level_nr + 1):
        level_i = get_level(c_graph, i)
        nodes_in_big_cycles = []
        for node in level_i:
            dir_enc_in_next_lvl = map_id_to_nodes(c_graph,
                                                  get_intersection_ids_from_nodes(
                                                      get_directly_encased_by(c_graph, node),
                                                      get_level(c_graph, i + 1)))
            for node_d in dir_enc_in_next_lvl:
                if node_d['color'] > -1:
                    continue
                prev_levels = [get_level(c_graph, j) for j in range(1, i + 1)]
                prev_levels_set = get_union_ids_from_nodes(*prev_levels)
                common_neighbors = get_intersection_ids_from_nodes(get_all_neighbors(c_graph, node),
                                                                   get_all_neighbors(c_graph, node_d))
                common_neighbors_on_prev_levels = prev_levels_set.intersection(common_neighbors)
                if len(common_neighbors_on_prev_levels) > 0:
                    # color node that has a neighbor in the prev lvl
                    c_var = frozenset({node['label'], node_d['label']})
                    c_value = assignment[c_var]
                    if c_value:
                        node_d['color'] = node['color']
                    else:
                        common_neighbors_colors = set()
                        for c_n in common_neighbors_on_prev_levels:
                            common_neighbors_colors.add(c_graph.nodes[c_n]['color'])
                        used_colors = {node['color']}.union(common_neighbors_colors)
                        remaining_color = {0, 1, 2} - used_colors
                        if len(remaining_color) > 0:
                            node_d['color'] = remaining_color.pop()
                        else:
                            print(
                                "fail during coloring node with neighbor on prev lvl, no remaining color for " + str(
                                    node_d['label']))
                            print(
                                "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                                     map_id_to_nodes(c_graph, common_neighbors_on_prev_levels) + [
                                                         node]]))
                else:
                    important_subgraphs = node_d['importantsubgraphs']
                    big_cycles = list(filter(lambda imp: (imp['id'].startswith("Cyc") or imp['id'].startswith(
                        "Pent")) and has_colored_node_on_prev_lvl(c_graph, imp, i + 1),
                                             important_subgraphs))
                    if len(big_cycles) > 0:
                        nodes_in_big_cycles.append(node_d)
        # color nodes in big cycles
        for node in nodes_in_big_cycles:
            if not node['color'] == -1:
                continue
            important_subgraphs = node['importantsubgraphs']
            big_cycles = list(
                filter(lambda imp: imp['id'].startswith("Cyc") or imp['id'].startswith("Pent"), important_subgraphs))
            for big_cycle in big_cycles:
                color_big_cycle_bt(c_graph, big_cycle['nodes'], assignment)
        # color remaining nodes
        level_i_plus_one = get_level(c_graph, i + 1)
        uncolored_nodes = list(filter(lambda n: n['color'] == -1, level_i_plus_one))
        if len(uncolored_nodes) < 1:
            continue
        sorted_uncolored_nodes = sort_by_left_endpoint(uncolored_nodes)
        left_to_right = False
        if has_colored_neighbor_on_same_level(c_graph, sorted_uncolored_nodes[-1]):
            left_to_right = True
        for cc in get_connected_components(c_graph.subgraph(map_nodes_to_label(uncolored_nodes))):
            color_remaining_level_like_first_level_bt(c_graph, cc, i + 1, assignment, left_to_right)


def color_big_cycle_bt(c_graph, cycle_node_ids, assignment):
    print("trying to color cycle with nodes", cycle_node_ids)
    if c_graph.nodes[cycle_node_ids[0]]['color'] == -1:
        print("something went wrong")
        print("colors:", [n['color'] for n in [c_graph.nodes[i] for i in cycle_node_ids]])
    cycle_node = c_graph.nodes[cycle_node_ids[1]]
    if cycle_node['color'] == -1:
        prev_cycle_node = c_graph.nodes[cycle_node_ids[-1]]
        c_value = assignment[frozenset({cycle_node['label'], prev_cycle_node['label']})]
        if c_value:
            cycle_node['color'] = prev_cycle_node['color']
        else:
            used_colors = {prev_cycle_node['color'], c_graph.nodes[cycle_node_ids[0]]['color']}
            remaining_color = {0, 1, 2} - used_colors
            if len(remaining_color) > 0:
                cycle_node['color'] = remaining_color.pop()
            else:
                print("fail during coloring cycles, no remaining color for " + str(cycle_node['label']))
                print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                           [prev_cycle_node, c_graph.nodes[cycle_node_ids[-1]]]]))
    print("cycle node ids:", cycle_node_ids)
    for i in range(2, len(cycle_node_ids)):
        cycle_node = c_graph.nodes[cycle_node_ids[i]]
        if not cycle_node['color'] == -1:
            continue
        prev_cycle_node = c_graph.nodes[cycle_node_ids[i - 2]]
        c_value = assignment[frozenset({cycle_node['label'], prev_cycle_node['label']})]
        if c_value:
            cycle_node['color'] = prev_cycle_node['color']
        else:
            used_colors = {prev_cycle_node['color'], c_graph.nodes[cycle_node_ids[i - 1]]['color']}
            remaining_color = {0, 1, 2} - used_colors
            if len(remaining_color) > 0:
                cycle_node['color'] = remaining_color.pop()
            else:
                print("fail during coloring cycles, no remaining color for " + str(cycle_node['label']))
                print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                           [prev_cycle_node, c_graph.nodes[cycle_node_ids[i - 1]]]]))
    for i in range(2, len(cycle_node_ids) - 1):
        cycle_node = c_graph.nodes[cycle_node_ids[i]]
        nh_on_same_lvl = map_nodes_to_label(get_all_neighbors_on_level(c_graph, cycle_node, cycle_node['level']))
        nh_on_same_lvl_without_big_cycle = set(nh_on_same_lvl) - set(cycle_node_ids)
        for neighbor_id in nh_on_same_lvl_without_big_cycle:
            neighbor = c_graph.nodes[neighbor_id]
            if not neighbor['color'] == -1:
                continue
            important_subgraphs = neighbor['importantsubgraphs']
            boxslashes = list(filter(lambda imp: imp['id'].startswith("BSq") and neighbor_id in imp['opposites'],
                                     important_subgraphs))
            if len(boxslashes) > 0:
                for boxslash in boxslashes:
                    opposites = boxslash['opposites'].copy()
                    opposites.remove(neighbor_id)
                    opposite = c_graph.nodes[opposites[0]]
                    if opposite['color'] != -1:
                        neighbor['color'] = opposite['color']
                        break
            if not neighbor['color'] == -1:
                continue
            nh = get_all_neighbors(c_graph, neighbor)
            used_colors = set([n['color'] for n in nh])
            remaining_color = {0, 1, 2} - used_colors
            if len(remaining_color) > 0:
                neighbor['color'] = remaining_color.pop()
            else:
                print("fail during coloring cycles, no remaining color for " + str(neighbor_id))
                print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in nh]))
            continue


def color_remaining_level_like_first_level_bt(c_graph, subgraph, level, assignment, left_to_right):
    sorted_subgraph = sort_by_left_endpoint(get_level(subgraph, level))
    curr_level = map_nodes_to_label(sort_by_left_endpoint(get_level(c_graph, level)))
    curr_level_subgraph = c_graph.subgraph(curr_level)
    if left_to_right:
        for node in sorted_subgraph:
            color_single_level_node_bt(curr_level_subgraph, node, assignment)
        for i in reversed(range(len(sorted_subgraph))):
            # relevant_nodes = set(map_nodes_to_label(get_level(c_graph, level))) - set(subgraph.nodes)
            permute_color_if_necessary(curr_level_subgraph, sorted_subgraph[i])
    else:
        for node in reversed(sorted_subgraph):
            color_single_level_node_right_to_left_bt(curr_level_subgraph, node, assignment)
        for i in range(len(sorted_subgraph)):
            permute_color_if_necessary(curr_level_subgraph, sorted_subgraph[i])


def color_single_level_node_right_to_left_bt(c_graph, node, assignment):
    right_nh = get_right_neighbors_on_level(c_graph, node, node['level'])
    extended_right_nh_ids = set()
    for right_n in right_nh:
        right_n_right_nh = get_right_neighbors_on_level(c_graph, right_n, node['level'])
        if len(right_n_right_nh) < 1:
            continue
        extended_right_nh_ids = extended_right_nh_ids.union(set(map_nodes_to_label(right_n_right_nh)))
    extended_right_nh = map_id_to_nodes(c_graph, list(extended_right_nh_ids - set(map_nodes_to_label(right_nh))))
    r_set = set(map_nodes_to_label(right_nh)).union(extended_right_nh_ids)
    if len(r_set) == 0:
        node['color'] = 0
    elif len(r_set) == 1:
        node['color'] = 1
    elif len(r_set) == 2:
        if len(right_nh) == 1:  # then extended_left_nh contains exactly one elem
            right_nh_node = right_nh[0]
            extended_right_nh_node = extended_right_nh[0]
            c_var = frozenset({node['label'], extended_right_nh_node['label']})
            c_value = assignment[c_var]
            if c_value:
                node['color'] = extended_right_nh_node['color']
            else:
                remaining_color = {0, 1, 2} - {extended_right_nh_node['color'], right_nh_node['color']}
                if len(remaining_color) > 0:
                    node['color'] = remaining_color.pop()
                else:
                    print(
                        "fail during coloring single level node r -> l, no remaining color for " + str(node['label']))
                    print(
                        "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                             [extended_right_nh_node, right_nh_node]]))
        elif len(right_nh) == 2:
            node['color'] = 2
    elif len(r_set) == 3:
        if len(right_nh) == 1:  # then extended_left_nh has size 2
            extended_right_nh_node = extended_right_nh[0]
            c_var = frozenset({node['label'], extended_right_nh_node['label']})
            c_value = assignment[c_var]
            if c_value:
                node['color'] = extended_right_nh_node['color']
            else:  # node has the same color as the other extended neighbor
                extended_right_nh_node = extended_right_nh[1]
                node['color'] = extended_right_nh_node['color']
        elif len(right_nh) == 2:  # consider position of extended neighbor
            extended_neighbor = extended_right_nh[0]
            if are_crossing_chords(extended_neighbor, right_nh[0]) and are_crossing_chords(extended_neighbor,
                                                                                           right_nh[1]):
                node['color'] = extended_neighbor['color']
            else:
                c_var = frozenset({node['label'], extended_neighbor['label']})
                c_value = assignment[c_var]
                if c_value:
                    node['color'] = extended_neighbor['color']
                else:
                    remaining_color = {0, 1, 2} - {right_nh[0]['color'], right_nh[1]['color']}
                    if len(remaining_color) > 0:
                        node['color'] = remaining_color.pop()
                    else:
                        print(
                            "fail during coloring single level node r -> l, no remaining color for " + str(
                                node['label']))
                        print(
                            "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in right_nh]))
    elif len(r_set) == 4:  # len(left_nh) == len(extended_nh) == 2
        max_extended_right_n = get_max(extended_right_nh)
        min_extended_right_n = get_min(extended_right_nh)
        if are_crossing_chords(max_extended_right_n, right_nh[0]) and are_crossing_chords(max_extended_right_n,
                                                                                          right_nh[1]):
            node['color'] = max_extended_right_n['color']
        else:
            c_var_a = frozenset({node['label'], min_extended_right_n['label']})
            c_value_a = assignment[c_var_a]
            if c_value_a:
                node['color'] = min_extended_right_n['color']
            else:
                node['color'] = max_extended_right_n['color']


def color_with_c(c_graph, f_builder, timed=False):
    if not f_builder.is_three_colorable:
        return
    if timed:
        coloring_timer.start()
        color_single_level(c_graph, 1, f_builder)
        color_remaining_levels(c_graph, f_builder)
        coloring_timer.stop()
    else:
        color_single_level(c_graph, 1, f_builder)
        color_remaining_levels(c_graph, f_builder)


def color_with_c_and_delete_nodes(c_graph, f_builder, timed=False):
    if not f_builder.is_three_colorable:
        return
    if timed:
        coloring_timer.start()
        node_to_delete = color_single_level_and_delete_nodes(c_graph, 1, f_builder)
        if node_to_delete is not None:
            coloring_timer.stop()
            return node_to_delete
        node_to_delete = color_remaining_levels_and_delete_nodes(c_graph, f_builder)
        coloring_timer.stop()
    else:
        node_to_delete = color_single_level_and_delete_nodes(c_graph, 1, f_builder)
        if node_to_delete is not None:
            return node_to_delete
        node_to_delete = color_remaining_levels_and_delete_nodes(c_graph, f_builder)
    return node_to_delete


def color_single_level(c_graph, level, f_builder):
    curr_level = sort_by_left_endpoint(get_level(c_graph, level))
    for node in curr_level:
        if node['color'] > -1:
            continue
        color_single_level_node(c_graph, node, f_builder)


def color_single_level_and_delete_nodes(c_graph, level, f_builder):
    curr_level = sort_by_left_endpoint(get_level(c_graph, level))
    for node in curr_level:
        if node['color'] > -1:
            continue
        node_to_delete = color_single_level_node_and_delete_node(c_graph, node, f_builder)
        if node_to_delete is not None:
            return node_to_delete


def color_single_level_node(c_graph, node, f_builder):
    left_nh = get_left_neighbors_on_level(c_graph, node, node['level'])
    extended_left_nh_ids = set()
    for left_n in left_nh:
        left_n_left_nh = get_left_neighbors_on_level(c_graph, left_n, node['level'])
        if len(left_n_left_nh) < 1:
            continue
        extended_left_nh_ids = extended_left_nh_ids.union(set(map_nodes_to_label(left_n_left_nh)))
    extended_left_nh = map_id_to_nodes(c_graph, list(extended_left_nh_ids - set(map_nodes_to_label(left_nh))))
    l_set = set(map_nodes_to_label(left_nh)).union(extended_left_nh_ids)
    if len(l_set) == 0:
        node['color'] = 0
    elif len(l_set) == 1:
        node['color'] = 1
    elif len(l_set) == 2:
        if len(left_nh) == 1:  # then extended_left_nh contains exactly one elem
            left_nh_node = left_nh[0]
            extended_left_nh_node = extended_left_nh[0]
            c_var = frozenset({node['label'], extended_left_nh_node['label']})
            c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
            if c_value:
                node['color'] = extended_left_nh_node['color']
            else:
                remaining_color = {0, 1, 2} - {extended_left_nh_node['color'], left_nh_node['color']}
                if len(remaining_color) > 0:
                    node['color'] = remaining_color.pop()
                else:
                    print(
                        "fail during coloring single level node, no remaining color for " + str(node['label']))
                    print(
                        "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                             [extended_left_nh_node, left_nh_node]]))
        elif len(left_nh) == 2:
            node['color'] = 2
    elif len(l_set) == 3:
        if len(left_nh) == 1:  # then extended_left_nh has size 2
            extended_left_nh_node = extended_left_nh[0]
            c_var = frozenset({node['label'], extended_left_nh_node['label']})
            c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
            if c_value:
                node['color'] = extended_left_nh_node['color']
            else:  # node has the same color as the other extended neighbor
                extended_left_nh_node = extended_left_nh[1]
                node['color'] = extended_left_nh_node['color']
        elif len(left_nh) == 2:  # consider position of extended neighbor
            extended_neighbor = extended_left_nh[0]
            if are_crossing_chords(extended_neighbor, left_nh[0]) and are_crossing_chords(extended_neighbor,
                                                                                          left_nh[1]):
                node['color'] = extended_neighbor['color']
            else:
                c_var = frozenset({node['label'], extended_neighbor['label']})
                c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
                if c_value:
                    node['color'] = extended_neighbor['color']
                else:
                    remaining_color = {0, 1, 2} - {left_nh[0]['color'], left_nh[1]['color']}
                    if len(remaining_color) > 0:
                        node['color'] = remaining_color.pop()
                    else:
                        print(
                            "fail during coloring single level node l -> r, no remaining color for " + str(
                                node['label']))
                        print(
                            "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in left_nh]))
    elif len(l_set) == 4:  # len(left_nh) == len(extended_nh) == 2
        max_extended_left_n = get_max(extended_left_nh)
        min_extended_left_n = get_min(extended_left_nh)
        if are_crossing_chords(max_extended_left_n, left_nh[0]) and are_crossing_chords(max_extended_left_n,
                                                                                        left_nh[1]):
            node['color'] = max_extended_left_n['color']
        else:
            c_var_a = frozenset({node['label'], min_extended_left_n['label']})
            c_value_a = f_builder.solver.get_py_value(f_builder.domain_vars[c_var_a])
            if c_value_a:
                node['color'] = min_extended_left_n['color']
            else:
                node['color'] = max_extended_left_n['color']


def color_single_level_node_and_delete_node(c_graph, node, f_builder):
    left_nh = get_left_neighbors_on_level(c_graph, node, node['level'])
    extended_left_nh_ids = set()
    for left_n in left_nh:
        left_n_left_nh = get_left_neighbors_on_level(c_graph, left_n, node['level'])
        if len(left_n_left_nh) < 1:
            continue
        extended_left_nh_ids = extended_left_nh_ids.union(set(map_nodes_to_label(left_n_left_nh)))
    extended_left_nh = map_id_to_nodes(c_graph, list(extended_left_nh_ids - set(map_nodes_to_label(left_nh))))
    l_set = set(map_nodes_to_label(left_nh)).union(extended_left_nh_ids)
    if len(l_set) == 0:
        node['color'] = 0
    elif len(l_set) == 1:
        node['color'] = 1
    elif len(l_set) == 2:
        if len(left_nh) == 1:  # then extended_left_nh contains exactly one elem
            left_nh_node = left_nh[0]
            extended_left_nh_node = extended_left_nh[0]
            c_var = frozenset({node['label'], extended_left_nh_node['label']})
            c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
            if c_value:
                node['color'] = extended_left_nh_node['color']
            else:
                remaining_color = {0, 1, 2} - {extended_left_nh_node['color'], left_nh_node['color']}
                if len(remaining_color) > 0:
                    node['color'] = remaining_color.pop()
                else:
                    print(
                        "fail during coloring single level node, no remaining color for " + str(node['label']))
                    print(
                        "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                             [extended_left_nh_node, left_nh_node]]))
                    return node['label']
        elif len(left_nh) == 2:
            node['color'] = 2
    elif len(l_set) == 3:
        if len(left_nh) == 1:  # then extended_left_nh has size 2
            extended_left_nh_node = extended_left_nh[0]
            c_var = frozenset({node['label'], extended_left_nh_node['label']})
            c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
            if c_value:
                node['color'] = extended_left_nh_node['color']
            else:  # node has the same color as the other extended neighbor
                extended_left_nh_node = extended_left_nh[1]
                node['color'] = extended_left_nh_node['color']
        elif len(left_nh) == 2:  # consider position of extended neighbor
            extended_neighbor = extended_left_nh[0]
            if are_crossing_chords(extended_neighbor, left_nh[0]) and are_crossing_chords(extended_neighbor,
                                                                                          left_nh[1]):
                node['color'] = extended_neighbor['color']
            else:
                c_var = frozenset({node['label'], extended_neighbor['label']})
                c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
                if c_value:
                    node['color'] = extended_neighbor['color']
                else:
                    remaining_color = {0, 1, 2} - {left_nh[0]['color'], left_nh[1]['color']}
                    if len(remaining_color) > 0:
                        node['color'] = remaining_color.pop()
                    else:
                        print(
                            "fail during coloring single level node l -> r, no remaining color for " + str(
                                node['label']))
                        print(
                            "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in left_nh]))
                        return node['label']
    elif len(l_set) == 4:  # len(left_nh) == len(extended_nh) == 2
        max_extended_left_n = get_max(extended_left_nh)
        min_extended_left_n = get_min(extended_left_nh)
        if are_crossing_chords(max_extended_left_n, left_nh[0]) and are_crossing_chords(max_extended_left_n,
                                                                                        left_nh[1]):
            node['color'] = max_extended_left_n['color']
        else:
            c_var_a = frozenset({node['label'], min_extended_left_n['label']})
            c_value_a = f_builder.solver.get_py_value(f_builder.domain_vars[c_var_a])
            if c_value_a:
                node['color'] = min_extended_left_n['color']
            else:
                node['color'] = max_extended_left_n['color']


def color_remaining_levels(c_graph, f_builder):
    level_nr = get_graph_level(c_graph)
    for i in range(1, level_nr + 1):
        level_i = get_level(c_graph, i)
        nodes_in_big_cycles = []
        for node in level_i:
            dir_enc_in_next_lvl = map_id_to_nodes(c_graph,
                                                  get_intersection_ids_from_nodes(
                                                      get_directly_encased_by(c_graph, node),
                                                      get_level(c_graph, i + 1)))
            for node_d in dir_enc_in_next_lvl:
                if node_d['color'] > -1:
                    continue
                prev_levels = [get_level(c_graph, j) for j in range(1, i + 1)]
                prev_levels_set = get_union_ids_from_nodes(*prev_levels)
                common_neighbors = get_intersection_ids_from_nodes(get_all_neighbors(c_graph, node),
                                                                   get_all_neighbors(c_graph, node_d))
                common_neighbors_on_prev_levels = prev_levels_set.intersection(common_neighbors)
                if len(common_neighbors_on_prev_levels) > 0:
                    # color node that has a neighbor in the prev lvl
                    c_var = frozenset({node['label'], node_d['label']})
                    c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
                    if c_value:
                        node_d['color'] = node['color']
                    else:
                        common_neighbors_colors = set()
                        for c_n in common_neighbors_on_prev_levels:
                            common_neighbors_colors.add(c_graph.nodes[c_n]['color'])
                        used_colors = {node['color']}.union(common_neighbors_colors)
                        remaining_color = {0, 1, 2} - used_colors
                        if len(remaining_color) > 0:
                            node_d['color'] = remaining_color.pop()
                        else:
                            print(
                                "fail during coloring node with neighbor on prev lvl, no remaining color for " + str(
                                    node_d['label']))
                            print(
                                "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                                     map_id_to_nodes(c_graph, common_neighbors_on_prev_levels) + [
                                                         node]]))
                else:
                    important_subgraphs = node_d['importantsubgraphs']
                    big_cycles = list(filter(lambda imp: (imp['id'].startswith("Cyc") or imp['id'].startswith(
                        "Pent")) and has_colored_node_on_prev_lvl(c_graph, imp, i + 1),
                                             important_subgraphs))
                    if len(big_cycles) > 0:
                        nodes_in_big_cycles.append(node_d)
        # color nodes in big cycles
        for node in nodes_in_big_cycles:
            if not node['color'] == -1:
                continue
            important_subgraphs = node['importantsubgraphs']
            big_cycles = list(
                filter(lambda imp: imp['id'].startswith("Cyc") or imp['id'].startswith("Pent"), important_subgraphs))
            for big_cycle in big_cycles:
                color_big_cycle(c_graph, big_cycle['nodes'], f_builder)
        # color remaining nodes
        level_i_plus_one = get_level(c_graph, i + 1)
        uncolored_nodes = list(filter(lambda n: n['color'] == -1, level_i_plus_one))
        if len(uncolored_nodes) < 1:
            continue
        sorted_uncolored_nodes = sort_by_left_endpoint(uncolored_nodes)
        left_to_right = False
        if has_colored_neighbor_on_same_level(c_graph, sorted_uncolored_nodes[-1]):
            left_to_right = True
        for cc in get_connected_components(c_graph.subgraph(map_nodes_to_label(uncolored_nodes))):
            color_remaining_level_like_first_level(c_graph, cc, i + 1, f_builder, left_to_right)


def color_remaining_levels_and_delete_nodes(c_graph, f_builder):
    level_nr = get_graph_level(c_graph)
    for i in range(1, level_nr + 1):
        level_i = get_level(c_graph, i)
        nodes_in_big_cycles = []
        for node in level_i:
            dir_enc_in_next_lvl = map_id_to_nodes(c_graph,
                                                  get_intersection_ids_from_nodes(
                                                      get_directly_encased_by(c_graph, node),
                                                      get_level(c_graph, i + 1)))
            for node_d in dir_enc_in_next_lvl:
                if node_d['color'] > -1:
                    continue
                prev_levels = [get_level(c_graph, j) for j in range(1, i + 1)]
                prev_levels_set = get_union_ids_from_nodes(*prev_levels)
                common_neighbors = get_intersection_ids_from_nodes(get_all_neighbors(c_graph, node),
                                                                   get_all_neighbors(c_graph, node_d))
                common_neighbors_on_prev_levels = prev_levels_set.intersection(common_neighbors)
                if len(common_neighbors_on_prev_levels) > 0:
                    # color node that has a neighbor in the prev lvl
                    c_var = frozenset({node['label'], node_d['label']})
                    c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
                    if c_value:
                        node_d['color'] = node['color']
                    else:
                        common_neighbors_colors = set()
                        for c_n in common_neighbors_on_prev_levels:
                            common_neighbors_colors.add(c_graph.nodes[c_n]['color'])
                        used_colors = {node['color']}.union(common_neighbors_colors)
                        remaining_color = {0, 1, 2} - used_colors
                        if len(remaining_color) > 0:
                            node_d['color'] = remaining_color.pop()
                        else:
                            print(
                                "fail during coloring node with neighbor on prev lvl, no remaining color for " + str(
                                    node_d['label']))
                            print(
                                "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                                     map_id_to_nodes(c_graph, common_neighbors_on_prev_levels) + [
                                                         node]]))
                            return node_d['label']
                else:
                    important_subgraphs = node_d['importantsubgraphs']
                    big_cycles = list(filter(lambda imp: (imp['id'].startswith("Cyc") or imp['id'].startswith(
                        "Pent")) and has_colored_node_on_prev_lvl(c_graph, imp, i + 1),
                                             important_subgraphs))
                    if len(big_cycles) > 0:
                        nodes_in_big_cycles.append(node_d)
        # color nodes in big cycles
        for node in nodes_in_big_cycles:
            if not node['color'] == -1:
                continue
            important_subgraphs = node['importantsubgraphs']
            big_cycles = list(
                filter(lambda imp: imp['id'].startswith("Cyc") or imp['id'].startswith("Pent"), important_subgraphs))
            for big_cycle in big_cycles:
                node_to_delete = color_big_cycle_and_delete_node(c_graph, big_cycle['nodes'], f_builder)
                if node_to_delete is not None:
                    return node_to_delete
        # color remaining nodes
        level_i_plus_one = get_level(c_graph, i + 1)
        uncolored_nodes = list(filter(lambda n: n['color'] == -1, level_i_plus_one))
        if len(uncolored_nodes) < 1:
            continue
        sorted_uncolored_nodes = sort_by_left_endpoint(uncolored_nodes)
        left_to_right = False
        if has_colored_neighbor_on_same_level(c_graph, sorted_uncolored_nodes[-1]):
            left_to_right = True
        for cc in get_connected_components(c_graph.subgraph(map_nodes_to_label(uncolored_nodes))):
            return color_remaining_level_like_first_level(c_graph, cc, i + 1, f_builder, left_to_right)


def has_colored_node_on_prev_lvl(c_graph, important_subgraph, level):
    for i in important_subgraph['nodes']:
        n_i = c_graph.nodes[i]
        if n_i['color'] > -1 and n_i['level'] < level:
            return True
    return False


def has_colored_neighbor_on_same_level(c_graph, node):
    neighbors_on_same_level = get_all_neighbors_on_level(c_graph, node, node['level'])
    for neighbor in neighbors_on_same_level:
        if neighbor['color'] > -1:
            return True


def color_big_cycle(c_graph, cycle_node_ids, f_builder):
    print("trying to color cycle with nodes", cycle_node_ids)
    if c_graph.nodes[cycle_node_ids[0]]['color'] == -1:
        print("something went wrong")
        print("colors:", [n['color'] for n in [c_graph.nodes[i] for i in cycle_node_ids]])
    cycle_node = c_graph.nodes[cycle_node_ids[1]]
    if cycle_node['color'] == -1:
        prev_cycle_node = c_graph.nodes[cycle_node_ids[-1]]
        c_value = f_builder.get_c_value(cycle_node['label'], prev_cycle_node['label'])
        if c_value:
            cycle_node['color'] = prev_cycle_node['color']
        else:
            used_colors = {prev_cycle_node['color'], c_graph.nodes[cycle_node_ids[0]]['color']}
            remaining_color = {0, 1, 2} - used_colors
            if len(remaining_color) > 0:
                cycle_node['color'] = remaining_color.pop()
            else:
                print("fail during coloring cycles, no remaining color for " + str(cycle_node['label']))
                print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                           [prev_cycle_node, c_graph.nodes[cycle_node_ids[-1]]]]))
    print("cycle node ids:", cycle_node_ids)
    for i in range(2, len(cycle_node_ids)):
        cycle_node = c_graph.nodes[cycle_node_ids[i]]
        if not cycle_node['color'] == -1:
            continue
        prev_cycle_node = c_graph.nodes[cycle_node_ids[i - 2]]
        c_value = f_builder.get_c_value(cycle_node['label'], prev_cycle_node['label'])
        if c_value:
            cycle_node['color'] = prev_cycle_node['color']
        else:
            used_colors = {prev_cycle_node['color'], c_graph.nodes[cycle_node_ids[i - 1]]['color']}
            remaining_color = {0, 1, 2} - used_colors
            if len(remaining_color) > 0:
                cycle_node['color'] = remaining_color.pop()
            else:
                print("fail during coloring cycles, no remaining color for " + str(cycle_node['label']))
                print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                           [prev_cycle_node, c_graph.nodes[cycle_node_ids[i - 1]]]]))
    for i in range(2, len(cycle_node_ids) - 1):
        cycle_node = c_graph.nodes[cycle_node_ids[i]]
        nh_on_same_lvl = map_nodes_to_label(get_all_neighbors_on_level(c_graph, cycle_node, cycle_node['level']))
        nh_on_same_lvl_without_big_cycle = set(nh_on_same_lvl) - set(cycle_node_ids)
        for neighbor_id in nh_on_same_lvl_without_big_cycle:
            neighbor = c_graph.nodes[neighbor_id]
            if not neighbor['color'] == -1:
                continue
            important_subgraphs = neighbor['importantsubgraphs']
            boxslashes = list(filter(lambda imp: imp['id'].startswith("BSq") and neighbor_id in imp['opposites'],
                                     important_subgraphs))
            if len(boxslashes) > 0:
                for boxslash in boxslashes:
                    opposites = boxslash['opposites'].copy()
                    opposites.remove(neighbor_id)
                    opposite = c_graph.nodes[opposites[0]]
                    if opposite['color'] != -1:
                        neighbor['color'] = opposite['color']
                        break
            if not neighbor['color'] == -1:
                continue
            nh = get_all_neighbors(c_graph, neighbor)
            used_colors = set([n['color'] for n in nh])
            remaining_color = {0, 1, 2} - used_colors
            if len(remaining_color) > 0:
                neighbor['color'] = remaining_color.pop()
            else:
                print("fail during coloring cycles, no remaining color for " + str(neighbor_id))
                print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in nh]))
            continue


def color_big_cycle_and_delete_node(c_graph, cycle_node_ids, f_builder):
    print("trying to color cycle with nodes", cycle_node_ids)
    if c_graph.nodes[cycle_node_ids[0]]['color'] == -1:
        print("something went wrong")
        print("colors:", [n['color'] for n in [c_graph.nodes[i] for i in cycle_node_ids]])
    cycle_node = c_graph.nodes[cycle_node_ids[1]]
    if cycle_node['color'] == -1:
        prev_cycle_node = c_graph.nodes[cycle_node_ids[-1]]
        c_value = f_builder.get_c_value(cycle_node['label'], prev_cycle_node['label'])
        if c_value:
            cycle_node['color'] = prev_cycle_node['color']
        else:
            used_colors = {prev_cycle_node['color'], c_graph.nodes[cycle_node_ids[0]]['color']}
            remaining_color = {0, 1, 2} - used_colors
            if len(remaining_color) > 0:
                cycle_node['color'] = remaining_color.pop()
            else:
                print("fail during coloring cycles, no remaining color for " + str(cycle_node['label']))
                print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                           [prev_cycle_node, c_graph.nodes[cycle_node_ids[-1]]]]))
                return cycle_node['label']
    print("cycle node ids:", cycle_node_ids)
    for i in range(2, len(cycle_node_ids)):
        cycle_node = c_graph.nodes[cycle_node_ids[i]]
        if not cycle_node['color'] == -1:
            continue
        prev_cycle_node = c_graph.nodes[cycle_node_ids[i - 2]]
        c_value = f_builder.get_c_value(cycle_node['label'], prev_cycle_node['label'])
        if c_value:
            cycle_node['color'] = prev_cycle_node['color']
        else:
            used_colors = {prev_cycle_node['color'], c_graph.nodes[cycle_node_ids[i - 1]]['color']}
            remaining_color = {0, 1, 2} - used_colors
            if len(remaining_color) > 0:
                cycle_node['color'] = remaining_color.pop()
            else:
                print("fail during coloring cycles, no remaining color for " + str(cycle_node['label']))
                print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                           [prev_cycle_node, c_graph.nodes[cycle_node_ids[i - 1]]]]))
                return cycle_node['label']
    for i in range(2, len(cycle_node_ids) - 1):
        cycle_node = c_graph.nodes[cycle_node_ids[i]]
        nh_on_same_lvl = map_nodes_to_label(get_all_neighbors_on_level(c_graph, cycle_node, cycle_node['level']))
        nh_on_same_lvl_without_big_cycle = set(nh_on_same_lvl) - set(cycle_node_ids)
        for neighbor_id in nh_on_same_lvl_without_big_cycle:
            neighbor = c_graph.nodes[neighbor_id]
            if not neighbor['color'] == -1:
                continue
            important_subgraphs = neighbor['importantsubgraphs']
            boxslashes = list(filter(lambda imp: imp['id'].startswith("BSq") and neighbor_id in imp['opposites'],
                                     important_subgraphs))
            if len(boxslashes) > 0:
                for boxslash in boxslashes:
                    opposites = boxslash['opposites'].copy()
                    opposites.remove(neighbor_id)
                    opposite = c_graph.nodes[opposites[0]]
                    if opposite['color'] != -1:
                        neighbor['color'] = opposite['color']
                        break
            if not neighbor['color'] == -1:
                continue
            nh = get_all_neighbors(c_graph, neighbor)
            used_colors = set([n['color'] for n in nh])
            remaining_color = {0, 1, 2} - used_colors
            if len(remaining_color) > 0:
                neighbor['color'] = remaining_color.pop()
            else:
                print("fail during coloring cycles, no remaining color for " + str(neighbor_id))
                print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in nh]))
                return neighbor['label']
            continue


def color_remaining_level_like_first_level(c_graph, subgraph, level, f_builder, left_to_right):
    sorted_subgraph = sort_by_left_endpoint(get_level(subgraph, level))
    curr_level = map_nodes_to_label(sort_by_left_endpoint(get_level(c_graph, level)))
    curr_level_subgraph = c_graph.subgraph(curr_level)
    if left_to_right:
        for node in sorted_subgraph:
            color_single_level_node(curr_level_subgraph, node, f_builder)
        for i in reversed(range(len(sorted_subgraph))):
            # relevant_nodes = set(map_nodes_to_label(get_level(c_graph, level))) - set(subgraph.nodes)
            permute_color_if_necessary(curr_level_subgraph, sorted_subgraph[i])
    else:
        for node in reversed(sorted_subgraph):
            color_single_level_node_right_to_left(curr_level_subgraph, node, f_builder)
        for i in range(len(sorted_subgraph)):
            permute_color_if_necessary(curr_level_subgraph, sorted_subgraph[i])


def color_remaining_level_like_first_level_and_delete_node(c_graph, subgraph, level, f_builder, left_to_right):
    sorted_subgraph = sort_by_left_endpoint(get_level(subgraph, level))
    curr_level = map_nodes_to_label(sort_by_left_endpoint(get_level(c_graph, level)))
    curr_level_subgraph = c_graph.subgraph(curr_level)
    if left_to_right:
        for node in sorted_subgraph:
            node_to_delete = color_single_level_node_and_delete_node(curr_level_subgraph, node, f_builder)
            if node_to_delete is not None:
                return node_to_delete
        for i in reversed(range(len(sorted_subgraph))):
            # relevant_nodes = set(map_nodes_to_label(get_level(c_graph, level))) - set(subgraph.nodes)
            node_to_delete = permute_color_if_necessary_and_delete_node(curr_level_subgraph, sorted_subgraph[i])
            if node_to_delete is not None:
                return node_to_delete
    else:
        for node in reversed(sorted_subgraph):
            node_to_delete = color_single_level_node_right_to_left_and_delete_node(curr_level_subgraph, node, f_builder)
            if node_to_delete is not None:
                return node_to_delete
        for i in range(len(sorted_subgraph)):
            node_to_delete = permute_color_if_necessary_and_delete_node(curr_level_subgraph, sorted_subgraph[i])
            if node_to_delete is not None:
                return node_to_delete


def color_single_level_node_right_to_left(c_graph, node, f_builder):
    right_nh = get_right_neighbors_on_level(c_graph, node, node['level'])
    extended_right_nh_ids = set()
    for right_n in right_nh:
        right_n_right_nh = get_right_neighbors_on_level(c_graph, right_n, node['level'])
        if len(right_n_right_nh) < 1:
            continue
        extended_right_nh_ids = extended_right_nh_ids.union(set(map_nodes_to_label(right_n_right_nh)))
    extended_right_nh = map_id_to_nodes(c_graph, list(extended_right_nh_ids - set(map_nodes_to_label(right_nh))))
    r_set = set(map_nodes_to_label(right_nh)).union(extended_right_nh_ids)
    if len(r_set) == 0:
        node['color'] = 0
    elif len(r_set) == 1:
        node['color'] = 1
    elif len(r_set) == 2:
        if len(right_nh) == 1:  # then extended_left_nh contains exactly one elem
            right_nh_node = right_nh[0]
            extended_right_nh_node = extended_right_nh[0]
            c_var = frozenset({node['label'], extended_right_nh_node['label']})
            c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
            if c_value:
                node['color'] = extended_right_nh_node['color']
            else:
                remaining_color = {0, 1, 2} - {extended_right_nh_node['color'], right_nh_node['color']}
                if len(remaining_color) > 0:
                    node['color'] = remaining_color.pop()
                else:
                    print(
                        "fail during coloring single level node r -> l, no remaining color for " + str(node['label']))
                    print(
                        "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                             [extended_right_nh_node, right_nh_node]]))
        elif len(right_nh) == 2:
            node['color'] = 2
    elif len(r_set) == 3:
        if len(right_nh) == 1:  # then extended_left_nh has size 2
            extended_right_nh_node = extended_right_nh[0]
            c_var = frozenset({node['label'], extended_right_nh_node['label']})
            c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
            if c_value:
                node['color'] = extended_right_nh_node['color']
            else:  # node has the same color as the other extended neighbor
                extended_right_nh_node = extended_right_nh[1]
                node['color'] = extended_right_nh_node['color']
        elif len(right_nh) == 2:  # consider position of extended neighbor
            extended_neighbor = extended_right_nh[0]
            if are_crossing_chords(extended_neighbor, right_nh[0]) and are_crossing_chords(extended_neighbor,
                                                                                           right_nh[1]):
                node['color'] = extended_neighbor['color']
            else:
                c_var = frozenset({node['label'], extended_neighbor['label']})
                c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
                if c_value:
                    node['color'] = extended_neighbor['color']
                else:
                    remaining_color = {0, 1, 2} - {right_nh[0]['color'], right_nh[1]['color']}
                    if len(remaining_color) > 0:
                        node['color'] = remaining_color.pop()
                    else:
                        print(
                            "fail during coloring single level node r -> l, no remaining color for " + str(
                                node['label']))
                        print(
                            "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in right_nh]))
    elif len(r_set) == 4:  # len(left_nh) == len(extended_nh) == 2
        max_extended_right_n = get_max(extended_right_nh)
        min_extended_right_n = get_min(extended_right_nh)
        if are_crossing_chords(max_extended_right_n, right_nh[0]) and are_crossing_chords(max_extended_right_n,
                                                                                          right_nh[1]):
            node['color'] = max_extended_right_n['color']
        else:
            c_var_a = frozenset({node['label'], min_extended_right_n['label']})
            c_value_a = f_builder.solver.get_py_value(f_builder.domain_vars[c_var_a])
            if c_value_a:
                node['color'] = min_extended_right_n['color']
            else:
                node['color'] = max_extended_right_n['color']


def color_single_level_node_right_to_left_and_delete_node(c_graph, node, f_builder):
    right_nh = get_right_neighbors_on_level(c_graph, node, node['level'])
    extended_right_nh_ids = set()
    for right_n in right_nh:
        right_n_right_nh = get_right_neighbors_on_level(c_graph, right_n, node['level'])
        if len(right_n_right_nh) < 1:
            continue
        extended_right_nh_ids = extended_right_nh_ids.union(set(map_nodes_to_label(right_n_right_nh)))
    extended_right_nh = map_id_to_nodes(c_graph, list(extended_right_nh_ids - set(map_nodes_to_label(right_nh))))
    r_set = set(map_nodes_to_label(right_nh)).union(extended_right_nh_ids)
    if len(r_set) == 0:
        node['color'] = 0
    elif len(r_set) == 1:
        node['color'] = 1
    elif len(r_set) == 2:
        if len(right_nh) == 1:  # then extended_left_nh contains exactly one elem
            right_nh_node = right_nh[0]
            extended_right_nh_node = extended_right_nh[0]
            c_var = frozenset({node['label'], extended_right_nh_node['label']})
            c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
            if c_value:
                node['color'] = extended_right_nh_node['color']
            else:
                remaining_color = {0, 1, 2} - {extended_right_nh_node['color'], right_nh_node['color']}
                if len(remaining_color) > 0:
                    node['color'] = remaining_color.pop()
                else:
                    print(
                        "fail during coloring single level node r -> l, no remaining color for " + str(node['label']))
                    print(
                        "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in
                                             [extended_right_nh_node, right_nh_node]]))
                    return node['label']
        elif len(right_nh) == 2:
            node['color'] = 2
    elif len(r_set) == 3:
        if len(right_nh) == 1:  # then extended_left_nh has size 2
            extended_right_nh_node = extended_right_nh[0]
            c_var = frozenset({node['label'], extended_right_nh_node['label']})
            c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
            if c_value:
                node['color'] = extended_right_nh_node['color']
            else:  # node has the same color as the other extended neighbor
                extended_right_nh_node = extended_right_nh[1]
                node['color'] = extended_right_nh_node['color']
        elif len(right_nh) == 2:  # consider position of extended neighbor
            extended_neighbor = extended_right_nh[0]
            if are_crossing_chords(extended_neighbor, right_nh[0]) and are_crossing_chords(extended_neighbor,
                                                                                           right_nh[1]):
                node['color'] = extended_neighbor['color']
            else:
                c_var = frozenset({node['label'], extended_neighbor['label']})
                c_value = f_builder.solver.get_py_value(f_builder.domain_vars[c_var])
                if c_value:
                    node['color'] = extended_neighbor['color']
                else:
                    remaining_color = {0, 1, 2} - {right_nh[0]['color'], right_nh[1]['color']}
                    if len(remaining_color) > 0:
                        node['color'] = remaining_color.pop()
                    else:
                        print(
                            "fail during coloring single level node r -> l, no remaining color for " + str(
                                node['label']))
                        print(
                            "neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in right_nh]))
                        return node['label']
    elif len(r_set) == 4:  # len(left_nh) == len(extended_nh) == 2
        max_extended_right_n = get_max(extended_right_nh)
        min_extended_right_n = get_min(extended_right_nh)
        if are_crossing_chords(max_extended_right_n, right_nh[0]) and are_crossing_chords(max_extended_right_n,
                                                                                          right_nh[1]):
            node['color'] = max_extended_right_n['color']
        else:
            c_var_a = frozenset({node['label'], min_extended_right_n['label']})
            c_value_a = f_builder.solver.get_py_value(f_builder.domain_vars[c_var_a])
            if c_value_a:
                node['color'] = min_extended_right_n['color']
            else:
                node['color'] = max_extended_right_n['color']


def permute_color_if_necessary(c_graph, node):
    nh = get_all_neighbors(c_graph, node)
    nh_colors = set([n['color'] for n in nh])
    if node['color'] in nh_colors:
        remaining_color = {0, 1, 2} - nh_colors
        if len(remaining_color) > 0:
            node['color'] = remaining_color.pop()
        else:
            print("fail during permuting, no remaining color for node " + str(node['label']))
            print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in nh]))


def permute_color_if_necessary_and_delete_node(c_graph, node):
    nh = get_all_neighbors(c_graph, node)
    nh_colors = set([n['color'] for n in nh])
    if node['color'] in nh_colors:
        remaining_color = {0, 1, 2} - nh_colors
        if len(remaining_color) > 0:
            node['color'] = remaining_color.pop()
        else:
            print("fail during permuting, no remaining color for node " + str(node['label']))
            print("neighbors: " + str([str(n['label']) + ": color " + str(n['color']) for n in nh]))
            return node['label']


# if c*(node_to_color,*) then color_a; else {0,1,2} \ used_colors
def color_by_c_value(c_value, node_to_color, color_a, used_colors):
    if c_value:
        node_to_color['color'] = color_a
    else:
        remaining_color = {0, 1, 2} - used_colors
        node_to_color['color'] = remaining_color.pop()
