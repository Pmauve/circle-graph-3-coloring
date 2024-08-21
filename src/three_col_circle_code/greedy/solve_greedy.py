import time

# from matplotlib import pyplot as plt
from networkx.drawing.nx_pydot import graphviz_layout

from three_col_circle_code.graph_generator import get_random_circle_graph
from three_col_circle_code.util import *

to_color = []
counter = 0
bt_tree = 0


def main():
    graph = get_random_circle_graph(size=20, save=False)
    # graph = read_graph_from_json(Path(__file__).absolute().parent.parent.parent.parent / "greedy.json")
    for n in graph.nodes:
        graph.nodes[n]['color'] = -1
    start_greedy(graph)
    print("found coloring:", verify_3coloring(graph) is True)


def start_greedy(graph):
    global to_color, bt_tree
    for n in graph.nodes:
        to_color.append(n)
    node = to_color.pop()
    if len(graph.nodes) < 2:
        bt_tree = 1
    color_greedy(graph, node)
    print("circle graph nodes:", len(graph.nodes))
    print("bt tree leaves:", bt_tree)

    return bt_tree


def color_greedy(graph, n):
    global to_color, bt_tree
    print("now coloring:", n)
    print("to color:", to_color)
    colors = {1, 2, 3}
    used_colors = set()
    for n_neighbor in nx.neighbors(graph, n):
        neighbor = graph.nodes[n_neighbor]
        used_colors.add(neighbor['color'])
    remaining_colors = colors - used_colors
    print("remaining colors for", n, ":", remaining_colors)
    if len(remaining_colors) < 1:
        print("no colors left for", n)
        bt_tree = bt_tree + 1
        return False
    for color in remaining_colors:
        graph.nodes[n]['color'] = color
        print("using color", color, "for", n)
        if len(to_color) < 1:
            bt_tree = bt_tree + 1
            return True
        next_n = to_color.pop()
        if color_greedy(graph, next_n):
            break
        # if we didn't break it means we didn't color the vertex and have to try the next color
        to_color.append(next_n)
        print("backtrack and try other color after trying node", n, "with color", color, "and couldn't color node",
              next_n)


if __name__ == "__main__":
    main()
