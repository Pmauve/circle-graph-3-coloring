import random
import time
import sys

from three_col_circle_code.generation.families import legacy_cli_families, run_legacy_cli_family
from three_col_circle_code.generation.constructive_circle import (
    CONSTRUCTIVE_CONFIGS,
    generate_random_circle_graph_yes_constructive as generate_random_circle_graph_yes_constructive_backend,
)
from three_col_circle_code.generation.legacy_like_circle import (
    generate_random_circle_graph_fast as generate_random_circle_graph_fast_backend,
    generate_random_circle_graph_yes_fast as generate_random_circle_graph_yes_fast_backend,
)
from three_col_circle_code.util import *

TIME_LIMIT_START = time.time()


def main():
    min_n_nodes = 0
    max_n_nodes = 0

    _generator = sys.argv[1:][0]
    _size = sys.argv[1:][1]

    if _size == "s":
        min_n_nodes = 3
        max_n_nodes = 250
    elif _size == "m":
        min_n_nodes = 250
        max_n_nodes = 750
    elif _size == "l":
        min_n_nodes = 750
        max_n_nodes = 1500
    elif _size == "xl":
        min_n_nodes = 1500
        max_n_nodes = 5000
    else:
        print('invalid size, must be s, m, l or xl')
        exit()

    n_nodes = random.randint(min_n_nodes, max_n_nodes)
    _timestamp = time.time()

    if _generator not in legacy_cli_families():
        print("Invalid argument for generator, must be " + ", ".join(legacy_cli_families()))
        exit()
    run_legacy_cli_family(family=_generator, n_nodes=n_nodes, timestamp=_timestamp)


def time_limit_reached():
    global TIME_LIMIT_START
    if time.time() - 3600 > TIME_LIMIT_START:
        print("time limit reached")
    return time.time() - 3600 > TIME_LIMIT_START


def get_random_graph(size, timestamp=0.0):
    global TIME_LIMIT_START
    graph = nx.gnp_random_graph(size, 0.5)
    while not no_clique_greater_3(graph) and not time_limit_reached():
        graph = nx.gnp_random_graph(size, 0.5)
    filename = str(no_clique_greater_3(graph)) + '_' + str(id(graph)) + '_' + str(int(timestamp))
    save_graph_json(graph, filename=filename, generator='r', size=get_size_as_string(size))
    return graph


def get_random_yes_inst(size, timestamp=0.0):
    global TIME_LIMIT_START
    graph = nx.Graph()
    if size > 0:
        graph.add_node(0, color=1)
    if size > 1:
        graph.add_node(1, color=2)
        graph.add_edge(0, 1)
    if size <= 2:
        return graph
    for i in range(2, size):
        print("new node:", i)
        searching = True
        attempts = 0
        while searching and attempts < 100 and not time_limit_reached():
            print("attempt", attempts)
            temp_graph = graph.copy()
            temp_graph.add_node(i, color=0)
            n_neighbors = random.randint(1, graph.number_of_nodes())
            print("we're gonna add", n_neighbors, "neighbors")
            for j in range(0, n_neighbors):
                neighbor = random.randint(0, graph.number_of_nodes())
                while neighbor == i or neighbor not in graph.nodes:
                    neighbor = random.randint(0, graph.number_of_nodes())
                temp_graph.add_edge(i, neighbor)
            color = get_color_for_new_node(temp_graph, i)
            attempts += 1
            no_clique = no_clique_greater_3(graph)
            connected = nx.is_connected(temp_graph)
            # print("color", color)
            # print("no 3-clique:", no_clique)
            # print("connected", connected)
            if color and no_clique and connected:
                print("added new node successfully")
                temp_graph.nodes[i]['color'] = color
                graph = temp_graph
                searching = False
    filename = str(id(graph)) + '_' + str(int(timestamp))
    save_graph_json(graph, filename=filename, generator='ry', size=get_size_as_string(size))
    return graph


def get_random_circle_graph(
    size, timestamp=0.0, save=True, rng=None, max_attempts_per_node=None, generator_name='rc'
):
    global TIME_LIMIT_START
    rng = rng or random
    arr = []
    graph = nx.Graph()
    for i in range(0, size):
        searching = True
        attempts = 0
        while searching and not time_limit_reached():
            if max_attempts_per_node is not None and attempts >= max_attempts_per_node:
                break
            temp_arr = arr.copy()
            random_insert(temp_arr, i, rng=rng)
            random_insert(temp_arr, i, rng=rng)
            temp_graph = build_graph_from_arr(temp_arr)
            if no_clique_greater_3(temp_graph) and nx.is_connected(temp_graph):
                graph = temp_graph
                arr = temp_arr
                searching = False
            attempts += 1
        if searching:
            raise RuntimeError("failed to generate random circle graph for node " + str(i))
    assign_levels(graph)
    if save:
        filename = str(id(graph)) + '_' + str(int(timestamp))
        save_graph_json(graph, filename=filename, generator=generator_name, size=get_size_as_string(size))
    return graph


def get_random_circle_graph_fast(size, timestamp=0.0, save=True, rng=None, max_attempts_per_node=None):
    graph = generate_random_circle_graph_fast_backend(
        size,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
    )
    if save:
        filename = str(id(graph)) + '_' + str(int(timestamp))
        save_graph_json(graph, filename=filename, generator='rc_fast', size=get_size_as_string(size))
    return graph


def get_random_circle_graph_yes_inst(
    size, timestamp=0.0, save=True, _filename='', rng=None, max_attempts_per_node=None
):
    global TIME_LIMIT_START
    rng = rng or random
    arr = []
    graph = nx.Graph()
    colors = dict()
    for i in range(0, size):
        searching = True
        attempts = 0
        while searching and not time_limit_reached():
            if max_attempts_per_node is not None and attempts >= max_attempts_per_node:
                break
            temp_arr = arr.copy()
            random_insert(temp_arr, i, rng=rng)
            random_insert(temp_arr, i, rng=rng)
            temp_graph = build_graph_from_arr(temp_arr)
            if len(colors) > 0:
                for key in colors.keys():
                    temp_graph.nodes[key]['color'] = colors[key]
            color = get_color_for_new_node(temp_graph, i)
            if color and no_clique_greater_3(temp_graph) and nx.is_connected(temp_graph):
                temp_graph.nodes[i]['color'] = color
                colors[i] = color
                graph = temp_graph
                arr = temp_arr
                searching = False
            attempts += 1
        if searching:
            raise RuntimeError("failed to generate random yes-instance circle graph for node " + str(i))
    assign_levels(graph)
    if save is True:
        filename = str(id(graph)) + '_' + str(int(timestamp)) if _filename == '' else _filename
        save_graph_json(graph, filename=filename, generator='rcy', size=get_size_as_string(size))
    return graph


def get_random_circle_graph_yes_fast(
    size, timestamp=0.0, save=True, _filename='', rng=None, max_attempts_per_node=None
):
    graph = generate_random_circle_graph_yes_fast_backend(
        size,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
    )
    if save is True:
        filename = str(id(graph)) + '_' + str(int(timestamp)) if _filename == '' else _filename
        save_graph_json(graph, filename=filename, generator='rcy_fast', size=get_size_as_string(size))
    return graph


def get_random_circle_graph_yes_inst_constructive(
    size, timestamp=0.0, save=True, _filename='', rng=None, max_attempts_per_node=None
):
    return _get_random_circle_graph_yes_inst_constructive_for_family(
        size,
        family="rccy",
        timestamp=timestamp,
        save=save,
        _filename=_filename,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
    )


def get_random_circle_graph_yes_inst_constructive_baseline(
    size, timestamp=0.0, save=True, _filename='', rng=None, max_attempts_per_node=None
):
    return _get_random_circle_graph_yes_inst_constructive_for_family(
        size,
        family="rccy_baseline",
        timestamp=timestamp,
        save=save,
        _filename=_filename,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
    )


def get_random_circle_graph_yes_inst_constructive_tuned(
    size, timestamp=0.0, save=True, _filename='', rng=None, max_attempts_per_node=None
):
    return _get_random_circle_graph_yes_inst_constructive_for_family(
        size,
        family="rccy_tuned",
        timestamp=timestamp,
        save=save,
        _filename=_filename,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
    )


def get_random_circle_graph_yes_inst_constructive_full_sweep_weighted_active(
    size, timestamp=0.0, save=True, _filename='', rng=None, max_attempts_per_node=None
):
    return _get_random_circle_graph_yes_inst_constructive_for_family(
        size,
        family="rccy_full_sweep_weighted_active",
        timestamp=timestamp,
        save=save,
        _filename=_filename,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
    )


def get_random_circle_graph_yes_inst_constructive_full_sweep_max_active(
    size, timestamp=0.0, save=True, _filename='', rng=None, max_attempts_per_node=None
):
    return _get_random_circle_graph_yes_inst_constructive_for_family(
        size,
        family="rccy_full_sweep_max_active",
        timestamp=timestamp,
        save=save,
        _filename=_filename,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
    )


def _get_random_circle_graph_yes_inst_constructive_for_family(
    size, *, family, timestamp=0.0, save=True, _filename='', rng=None, max_attempts_per_node=None
):
    graph = generate_random_circle_graph_yes_constructive_backend(
        size,
        rng=rng,
        config=CONSTRUCTIVE_CONFIGS[family],
        max_attempts_per_node=max_attempts_per_node,
    )
    if save is True:
        filename = str(id(graph)) + '_' + str(int(timestamp)) if _filename == '' else _filename
        save_graph_json(graph, filename=filename, generator=family, size=get_size_as_string(size))
    return graph


def random_insert(lst, item, rng=None):
    rng = rng or random
    lst.insert(rng.randint(0, len(lst)), item)


def build_cgraph_from_json(path):
    graph = read_graph_from_json(path)
    return build_cgraph_wo_array(graph)


def delete_node_and_update_cgraph(graph, node_to_delete):
    graph.remove_node(node_to_delete['label'])
    for n in graph:
        node = graph.nodes[n]
        if is_left_neighbor(node_to_delete, node):
            # shift only right by one
            node['r'] = node['r'] - 1
        elif is_right_neighbor(node_to_delete, node):
            # shift left by one, right by two
            node['l'] = node['l'] - 1
            node['r'] = node['r'] - 2
        elif encases(node_to_delete, node):
            # shift left and right by one
            node['l'] = node['l'] - 1
            node['r'] = node['r'] - 1
        elif encases(node, node_to_delete):
            node['r'] = node['r'] - 2
        elif node['l'] > node_to_delete['r']:
            node['l'] = node['l'] - 2
            node['r'] = node['r'] - 2
    new_graph = build_cgraph_wo_array(nx.create_empty_copy(graph))
    return new_graph


def build_cgraph_wo_array(graph):
    arr = [None] * (2 * len(graph.nodes()))
    for n in graph.nodes():
        node = graph.nodes[n]
        arr[node['l']] = n
        arr[node['r']] = n
    build_edges(graph, arr)
    assign_levels(graph)
    return graph


def build_graph_from_arr(arr):
    graph = nx.Graph()
    for i in arr:
        graph.add_node(i, color=-1, l=-1, r=-1, level=-1, label=i)
    for i in range(0, len(arr)):
        curr = graph.nodes[arr[i]]
        if curr['l'] < 0:
            curr['l'] = i
        else:
            curr['r'] = i
    build_edges(graph, arr)
    return graph


def encases(a, b):
    return a['l'] < b['l'] < b['r'] < a['r']


def get_color_for_new_node(graph, new_node):
    used_colors = set([graph.nodes[n]['color'] for n in nx.all_neighbors(graph, new_node)])
    remaining_colors = {1, 2, 3} - used_colors
    if len(remaining_colors) > 0:
        return remaining_colors.pop()
    else:
        return None


def no_clique_greater_3(graph):
    return max(len(c) for c in nx.find_cliques(graph)) < 4


def reset_colors(graph):
    for i in graph.nodes():
        graph.nodes[i]['color'] = -1


def get_size_as_string(size):
    if size <= 250:
        return 's'
    elif size <= 750:
        return 'm'
    elif size <= 1500:
        return 'l'
    else:
        return 'xl'


if __name__ == "main":
    main()
