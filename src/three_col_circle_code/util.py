import os
import itertools as itt
from pathlib import Path
from networkx import NetworkXNoCycle

from networkx.readwrite import json_graph
import json
import networkx as nx

TAILTRIANGLE_STR = "tailtriangle"
BOXSLASH_STR = "boxslash"
FOUR_CYCLE_STR = "4-cycle"
FIVE_CYCLE_STR = "5-cycle"
BIG_CYCLE_STR = "big cycle"

TAILTRIANGLE_ONE_LVL_ID = "TT1"
TAILTRIANGLE_TWO_LVL_ID = "TT2"


def sort_by_left_endpoint(nodes):
    return sorted(nodes, key=lambda n: n['l'])


def is_induced_subgraph_connected(graph, nodes):
    return nx.is_connected(get_induced_subgraph_from_nodes(graph, nodes))


def get_induced_subgraph_from_nodes(graph, nodes):
    return get_induced_subgraph(graph, map_nodes_to_label(nodes))


def get_induced_subgraph(graph, nodes):
    return graph.subgraph(nodes)


def get_connected_components(graph):
    result = [graph.subgraph(c) for c in nx.connected_components(graph)]
    return result


def read_graph_from_json(path):
    with open(path) as infile:
        j_graph = json.load(infile)
        graph = json_graph.node_link_graph(j_graph)
        return graph


def save_graph_json(graph, filename="sample", generator="", size="", colored=False):
    print("saving...", filename)
    print(graph)
    json_object = json.dumps(nx.node_link_data(graph))
    path = Path(__file__).absolute().parent.parent.parent / "eval" / "graph_data" / generator / size
    if colored:
        path = Path(__file__).absolute().parent.parent.parent / "eval" / "graph_data" / "colored" / generator / size
    if not os.path.exists(path):
        os.makedirs(path)
    with open(path / (filename + ".json"), "w") as outfile:
        outfile.write(json_object)
    print("saved", filename)


def fix_graph_wo_level(graph):
    fixed_graph = nx.Graph()
    for n in graph.nodes:
        node = graph.nodes[n]
        fixed_graph.add_node(n, color=-1, l=node['l'], r=node['r'], level=-1, label=n)
    if build_edges(fixed_graph) == 0:
        return None
    assign_levels(fixed_graph)
    return fixed_graph


def assign_levels(graph):
    for node in sort_by_left_endpoint(map_id_to_nodes(graph, graph.nodes)):  # find lvl 1 nodes
        encased_by = 0
        for j in graph.nodes:
            node_comp = graph.nodes[j]
            if encases(node_comp, node):
                encased_by += 1
        if encased_by == 0:
            node['level'] = 1

    for node_i in sort_by_left_endpoint(map_id_to_nodes(graph, graph.nodes)):
        max_encased_by_level = 0
        if node_i['level'] == 1:
            continue
        for j in graph.nodes:
            if j == node_i['label']:
                continue
            node_j = graph.nodes[j]
            if node_j['level'] == -1:
                continue
            if encases(node_j, node_i) and node_j['level'] > max_encased_by_level:
                max_encased_by_level = node_j['level']
        node_i['level'] = max_encased_by_level + 1


def build_edges(graph, intervals=None):
    if intervals is None:
        intervals = [None] * (len(graph.nodes) * 2)
        for node in graph.nodes:
            if graph.nodes[node]['l'] >= len(intervals) or graph.nodes[node]['r'] >= len(intervals):
                print("graph is broken")
                return 0
            intervals[graph.nodes[node]['l']] = graph.nodes[node]['label']
            intervals[graph.nodes[node]['r']] = graph.nodes[node]['label']
    for node in graph.nodes:
        l_index = graph.nodes[node]['l']
        r_index = graph.nodes[node]['r']
        track = {}
        for i in range(l_index + 1, r_index):
            track[str(intervals[i])] = 0
        for i in range(l_index + 1, r_index):
            track[str(intervals[i])] += 1
        for elem in track:
            if track[elem] == 1:
                graph.add_edge(intervals[l_index], int(elem))


def get_all_neighbors(c_graph, node):
    return map_id_to_nodes(c_graph, c_graph.neighbors(node['label']))


def get_all_neighbors_on_level(c_graph, node, level):
    return [neighbor for neighbor in get_all_neighbors(c_graph, node) if neighbor['level'] == level]


def are_neighbors(c_graph, a, b):
    return a['label'] in c_graph.neighbors(b['label'])


def verify_3coloring(graph, log_errors=True):
    for e in graph.edges():
        if graph.nodes[e[0]]['color'] == graph.nodes[e[1]]['color'] or graph.nodes[e[0]]['color'] < 0 or \
                graph.nodes[e[1]]['color'] < 0:
            if log_errors:
                print("some edges have endpoints with the same color...")
            list_edges_w_invalid_colored_endpoints(graph)
            return graph.nodes[e[0]]['label']
    return True


def extended_verify_3coloring(graph, log_errors=True):
    broken_chords = set()
    for e in graph.edges():
        if graph.nodes[e[0]]['color'] == graph.nodes[e[1]]['color']:
            if log_errors and len(broken_chords) < 1:
                print("some edges have endpoints with the same color...")
            broken_chords.add(e[0])
            broken_chords.add(e[1])
    print("broken chords: " + str(broken_chords))
    return broken_chords


def list_edges_w_invalid_colored_endpoints(graph):
    count = 0
    for e in graph.edges():
        if count > 8:
            break
        if graph.nodes[e[0]]['color'] == graph.nodes[e[1]]['color']:
            print(str(e))
            count += 1


def get_graph_level(graph):
    level_nr = 0
    for i in graph.nodes:
        node = graph.nodes[i]
        if node['level'] > level_nr:
            level_nr = node['level']
    return level_nr


def get_level(graph, lvl):
    this_level = []
    for n in graph.nodes:
        node = graph.nodes[n]
        if node['level'] == lvl:
            this_level.append(node)
    return this_level


def get_left_neighbors(graph, node):
    result = []
    for i in graph.nodes:
        node_i = graph.nodes[i]
        if is_left_neighbor(node, node_i):
            result.append(node_i)
    return result


def get_left_neighbors_on_level(graph, node, level):
    result = []
    for i in graph.nodes:
        node_i = graph.nodes[i]
        if is_left_neighbor(node, node_i) and node_i['level'] == level:
            result.append(node_i)
    return result


def is_left_neighbor(a, b):
    return b['l'] < a['l'] < b['r'] < a['r']


def get_right_neighbors(graph, node):
    result = []
    for i in graph.nodes:
        node_i = graph.nodes[i]
        if is_right_neighbor(node, node_i):
            result.append(node_i)
    return result


def get_right_neighbors_on_level(graph, node, level):
    result = []
    for i in graph.nodes:
        node_i = graph.nodes[i]
        if is_right_neighbor(node, node_i) and node_i['level'] == level:
            result.append(node_i)
    return result


def is_right_neighbor(a, b):
    return a['l'] < b['l'] < a['r'] < b['r']


def get_max(nodes):
    max_node = nodes[0]
    for node in nodes:
        if node['r'] > max_node['r']:
            max_node = node
    return max_node


def get_max_id(nodes):
    return get_max(nodes)['label']


def get_min(nodes):
    if len(nodes) < 1:
        return 0
    min_node = nodes[0]
    for node in nodes:
        if node['l'] < min_node['l']:
            min_node = node
    return min_node


def get_min_id(nodes):
    return get_min(nodes)['label']


def map_nodes_to_label(nodes):
    result = []
    for node in nodes:
        result.append(node['label'])
    return result


def map_id_to_nodes(graph, ids):
    result = []
    for i in ids:
        node = graph.nodes[i]
        result.append(node)
    return result


def get_non_adjacent(graph, node):
    neighbors = [n for n in graph.neighbors(node['label'])]
    return map_id_to_nodes(graph, graph.nodes - neighbors)


def get_directly_encased_by(graph, node):
    # chords can be on another level and still be directly encased
    encased = []
    result = []
    for i in graph.nodes():
        node_i = graph.nodes[i]
        if encases(node, node_i):
            encased.append(node_i)
    for node_e in encased:
        append = True
        for i in graph.nodes():
            node_i = graph.nodes[i]
            if encases(node, node_i) and encases(node_i, node_e):
                append = False
                break
        if append:
            result.append(node_e)
    return result


def get_encased_by(graph, node):
    encased = []
    for i in graph.nodes():
        node_i = graph.nodes[i]
        if encases(node, node_i):
            encased.append(node_i)
    return encased


def encases(a, b):
    return a['l'] < b['l'] < b['r'] < a['r']


def get_intersection_ids_from_nodes(*node_lists):
    return get_intersection(*list(map(map_nodes_to_label, node_lists)))


def get_intersection(*lists):
    intersect = []
    for list_i in lists:
        intersect += [list_i]
    return set.intersection(*map(set, intersect))


def find_all_n_pair_combinations(elements, tuple_size=2):
    pair_oder_list = itt.combinations(elements, tuple_size)
    return list(map(list, pair_oder_list))


def has_cycle(graph):
    try:
        nx.find_cycle(graph)
    except NetworkXNoCycle:
        return False
    else:
        return True


def are_crossing_chords(a, b):
    return is_left_neighbor(a, b) or is_right_neighbor(a, b)


def get_cycle_nodes_for_path(path, left_node, right_node):
    cycle_nodes = []
    skip = set()
    for j in range(0, len(path)):
        if j + 1 < len(path) and is_3_clique(path[j], left_node, path[j + 1]):
            if not are_crossing_chords(path[j], path[j + 2]):
                # if j forms a loose 3-clique at the left point of the cycle we don't need it
                skip.add(j)
            else:
                # if j already crosses j+2 we don't need j+1 anymore
                skip.add(j + 1)
        if j in skip:
            continue
        cycle_nodes.append(path[j])
        if are_crossing_chords(path[j], right_node):
            # if j already crosses right_node we're done
            break
        if j + 2 < len(path):
            if is_3_clique(path[j], path[j + 1], path[j + 2]):
                if are_crossing_chords(path[j + 1], right_node):
                    skip.add(j + 2)  # if j+1 already crosses right_node then we don't need j+2
                elif (j + 3 < len(path) and not are_crossing_chords(path[j + 1], path[j + 3])) or (
                        j + 3 >= len(path) and not are_crossing_chords(path[j + 1], right_node)):
                    skip.add(j + 1)  # if j+1 only forms loose 3-clique we don't need it
        if j + 2 + len(skip) < len(path):
            if are_crossing_chords(path[j], path[j + 2 + len(skip)]):
                if j + 4 + len(skip) < len(path) and are_crossing_chords(path[j + 2], path[j + 4]):
                    skip.add(j + 1 + len(skip))
                    skip.add(j + 2 + len(skip))  # skip increased by 1, so we add only 2 (we want j + 3)
                elif are_crossing_chords(path[j + 2], right_node):
                    skip.add(j + 1 + len(skip))
                    skip.add(j + 2 + len(skip))  # skip increased by 1, so we add only 2 (we want j + 3)
                else:
                    skip.add(j + 2 + len(skip))
    return cycle_nodes


def is_3_clique(a, b, c):
    return are_crossing_chords(a, b) and are_crossing_chords(b, c) and are_crossing_chords(a, c)


def get_union_ids_from_nodes(*node_lists):
    return get_union(*list(map(map_nodes_to_label, node_lists)))


def get_union(*lists):
    unify = []
    for list_i in lists:
        unify += [list_i]
    return set.union(*map(set, unify))
