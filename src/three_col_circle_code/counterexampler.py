import sys
import time
import random

# from matplotlib import pyplot as plt

from three_col_circle_code.graph_generator import get_random_circle_graph, delete_node_and_update_cgraph
from three_col_circle_code.sat_builder import *
from three_col_circle_code.col.main import *

unsat_core_3sat = "none"
unsat_core_bt = "none"
five_cycle_backtrack_leaves = 0
big_cycle_backtrack_leaves = 0
broken_chords = set()
total_bt_leaves = 0
good_bt_leaves = 0


def main():
    # find_random_counterexample()
    # graph = read_graph_from_json(Path(__file__).absolute().parent.parent.parent / "counterexample.json")
    # nx.draw_planar(graph)
    # plt.show()
    # brute_force_all_embeddings(graph)
    find_counterexample_for_any_representation()


def find_random_counterexample():
    size = int(sys.argv[1:][0])
    done = False
    _counterexample = nx.Graph()
    while not done:
        _timestamp = time.time()
        _size = random.randint(5, size)
        print(_size)
        _counterexample = get_random_circle_graph(_size)
        counterexample_id = str(id(_counterexample)) + '_' + str(int(_timestamp))
        if is_three_colorable(_counterexample)[0]:
            continue
        i_subgraphs = get_all_important_subgraphs(_counterexample)
        # i_subgraphs = get_important_subgraphs_over_all_levels(_counterexample)
        if len(i_subgraphs[FIVE_CYCLE_STR]) > 0 or len(i_subgraphs[BIG_CYCLE_STR]) > 0 or (
                not solve_col_3sat(_counterexample, i_subgraphs) is True):
            continue
        save_graph_json(_counterexample, counterexample_id, generator="counterexampler")  # just for safety
        print("important subgraphs:", i_subgraphs)
        _counterexample = find_min_counterexample_from_counterexample(_counterexample)
        print("saving (minimal) counterexample...")
        save_graph_json(_counterexample, counterexample_id, generator="counterexampler")
        done = True
    return _counterexample


def find_min_counterexample_from_counterexample(counterexample):
    current_node = max(counterexample.nodes)
    visited = []
    min_counterexample = counterexample.copy()
    print("nodes:", min_counterexample.nodes)
    while len(visited) < len(min_counterexample.nodes) - 1:
        print("counter:", current_node)
        visited.append(current_node)
        temp_min_counterexample = min_counterexample.copy()
        temp_min_counterexample = delete_node_and_update_cgraph(temp_min_counterexample,
                                                                min_counterexample.nodes[current_node])
        if is_counterexample(temp_min_counterexample):
            min_counterexample = temp_min_counterexample
            save_graph_json(min_counterexample, "backup_c_example_save", generator="counterexampler")  # just for safety
            current_node = max(min_counterexample.nodes)
        else:
            current_node = max(min_counterexample.nodes - visited)
    return min_counterexample


def is_counterexample(counterexample):
    if is_three_colorable(counterexample)[0]:  # if the graph is 3 col, then we're not interested
        return False
    i_subgraphs = get_all_important_subgraphs(counterexample)
    print("important subgraphs:", i_subgraphs)
    if not solve_col_3sat(counterexample, i_subgraphs) is True:  # if unger doesn't claim 3 col we're not interested
        return False
    return True


def solve_col_3sat(c_graph, important_subgraphs):
    global unsat_core_3sat
    f_builder = ImportantSubgraphFormulaBuilder(c_graph, important_subgraphs)
    print("### 3 SAT ###")
    f_builder.solve_with_3_sat()
    result = f_builder.is_three_colorable
    print("Col 3-SAT colorable:", f_builder.is_three_colorable)
    return result


# Try out all possible "cutting points" and check if it's still a counterexample
# put leftmost endpoint at the right end and update all endpoints by -1
def brute_force_all_embeddings(c_graph):
    last_graph = c_graph
    for i in range(0, 2 * len(c_graph.nodes)):
        print("loop", i)
        print("nodes before shifting:", last_graph.nodes.data())
        shifted_graph = last_graph.copy()
        sorted_nodes = map_nodes_to_label(sort_by_left_endpoint(map_id_to_nodes(shifted_graph, shifted_graph.nodes)))
        print("sorted nodes:", sorted_nodes)
        shifted_node = shifted_graph.nodes[sorted_nodes[0]]
        shifted_node['l'] = (shifted_node['r'] - 1) % (2 * len(shifted_graph.nodes))
        shifted_node['r'] = (len(shifted_graph.nodes) * 2) - 1
        shifted_node['level'] = -1
        print("shifting", shifted_node)
        for n in shifted_graph.nodes:
            if n == shifted_node['label']:
                continue
            shifted_graph.nodes[n]['l'] = (shifted_graph.nodes[n]['l'] - 1) % (2 * len(shifted_graph.nodes))
            shifted_graph.nodes[n]['r'] = (shifted_graph.nodes[n]['r'] - 1) % (2 * len(shifted_graph.nodes))
            shifted_graph.nodes[n]['level'] = -1
        assign_levels(shifted_graph)
        print("nodes after shifting:",
              [{i, str(shifted_graph.nodes[i]['l']) + ", " + str(shifted_graph.nodes[i]['r'])} for i in sorted_nodes])
        if is_counterexample(shifted_graph):
            print("still a counterexample")
        else:
            print("no longer a counterexample")
            print([{i, str(shifted_graph.nodes[i]['l']) + ", " + str(shifted_graph.nodes[i]['r'])} for i in sorted_nodes])
            return False
        last_graph = shifted_graph.copy()
    return True


def find_counterexample_for_any_representation():
    done = False
    while not done:
        counterexample = find_random_counterexample()
        done = brute_force_all_embeddings(counterexample)
    print("found one")


if __name__ == "__main__":
    main()
