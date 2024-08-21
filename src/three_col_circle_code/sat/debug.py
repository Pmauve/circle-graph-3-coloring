from matplotlib import pyplot as plt
from networkx.drawing.nx_pydot import graphviz_layout

from three_col_circle_code.graph_generator import *
from three_col_circle_code.col.rec_tailtriangle import find_all_tailtriangles, find_tailtriangles_over_all_levels
from three_col_circle_code.col.rec_boxslash import find_all_boxslashes
from three_col_circle_code.col.rec_4cycles import find_all_four_cycles
from three_col_circle_code.col.rec_5cycles import find_all_five_cycles_like_big_cycles
from three_col_circle_code.col.rec_big_cycles import find_all_big_cycles
from three_col_circle_code.custom_sat_builder import *
from three_col_circle_code.sat_builder import is_three_colorable


def get_all_important_subgraphs(c_graph):
    for i in c_graph.nodes():
        c_graph.nodes[i]['importantsubgraphs'] = []
    return {  # TAILTRIANGLE_STR: find_all_tailtriangles(c_graph),
        TAILTRIANGLE_STR: find_all_tailtriangles(c_graph),
        BOXSLASH_STR: find_all_boxslashes(c_graph),
        FOUR_CYCLE_STR: find_all_four_cycles(c_graph),
        # FIVE_CYCLE_STR: find_all_five_cycles(c_graph),
        FIVE_CYCLE_STR: find_all_five_cycles_like_big_cycles(c_graph),
        BIG_CYCLE_STR: find_all_big_cycles(c_graph)}


def main():
    debug_backtracking()
    # bt_counterexample_maybe()
    # debug_regular_backtracking()


def debug_regular_backtracking():
    graph = build_cgraph_from_json(Path(
        __file__).absolute().parent.parent.parent.parent / "eval" / "graph_data" / "counterexampler" / "bt_min_min_counterexample_save.json")
    # graph = build_cgraph_from_json(Path(
    #     __file__).absolute().parent.parent.parent.parent / "regular_bt_debug.json")
    # nx.draw(graph, with_labels=True)
    # plt.show()
    important_subgraphs = get_all_important_subgraphs(graph)
    for i in important_subgraphs:
        for j in important_subgraphs[i]:
            if isinstance(j, str):
                print(important_subgraphs[i][j])
            else:
                print(j)
    # print("actual result:", is_three_colorable(graph))
    custom_sat_builder = CustomSatBuilder(graph, important_subgraphs)
    result = custom_sat_builder.solve_small_clauses()
    print("variable:", len(custom_sat_builder.assignment))
    print("result:", result)
    print("regular backtracking result:", custom_sat_builder.solve_with_regular_backtracking())
    custom_sat_builder.print_var_assignment()
    # pos = graphviz_layout(custom_sat_builder.bt_tree, prog="dot")
    # nx.draw(custom_sat_builder.bt_tree, pos, with_labels=True)
    # plt.show()
    print("btt size:", len(custom_sat_builder.bt_tree.nodes))
    print("leaves:", custom_sat_builder.get_btt_leaves())
    custom_sat_builder.verify_assignment()


def debug_backtracking():
    # graph = get_random_circle_graph_yes_inst(15, save=False)

    graph = build_cgraph_from_json(Path(
        __file__).absolute().parent.parent.parent.parent.parent / "try_fix_bt_min_min_counterexample_save.json")

    # graph = delete_node_and_update_cgraph(graph, graph.nodes[4])
    # print(is_counterexample(graph))
    # save_graph_json(graph, filename="test_graph_wo_4", generator="counterexampler")

    # nx.draw(graph, with_labels=True)
    # plt.show()

    # print(len(get_all_important_subgraphs(graph)[FIVE_CYCLE_STR]))

    important_subgraphs = get_all_important_subgraphs(graph)

    # while len(important_subgraphs[BIG_CYCLE_STR]) < 2:
    #     graph = get_random_circle_graph_yes_inst(15, save=False)
    #     important_subgraphs = get_all_important_subgraphs(graph)
    # save_graph_json(graph, filename="test_graph_bt_big_cycles", generator="counterexampler")
    # print("actual result:", is_three_colorable(graph))

    # nx.draw(graph, with_labels=True)
    # plt.show()

    for i in important_subgraphs:
        for j in important_subgraphs[i]:
            if isinstance(j, str):
                print(important_subgraphs[i][j])
            else:
                print(j)
    custom_sat_builder = CustomSatBuilder(graph, important_subgraphs)
    result = custom_sat_builder.solve_small_clauses()

    # pos = graphviz_layout(custom_sat_builder.implication_graph, prog="dot")
    # nx.draw(custom_sat_builder.implication_graph, pos, with_labels=True)
    # plt.show()

    # nx.draw_circular(custom_sat_builder.implication_graph, with_labels=True)
    # plt.show()

    print("small clauses:")
    custom_sat_builder.print_small_clauses()
    print("large clauses:")
    custom_sat_builder.print_large_clauses()

    # scc = list(nx.strongly_connected_components(custom_sat_builder.implication_graph))
    # for component in scc:
    #     g_component = nx.subgraph(custom_sat_builder.implication_graph, component)
    #     nx.draw(g_component, with_labels=True)
    #     plt.show()

    print("implication graph dict:", custom_sat_builder.impl_graph_dict)
    print("result:", result)
    print("backtracking result:", custom_sat_builder.solve_with_backtracking())
    print("assignments:")
    custom_sat_builder.print_var_assignment()
    # pos = graphviz_layout(custom_sat_builder.bt_tree, prog="dot")
    # nx.draw(custom_sat_builder.bt_tree, pos, with_labels=True)
    # plt.show()

    custom_sat_builder.verify_assignment()


# commented bc solver not working for eval
def bt_counterexample_maybe():
    graph = build_cgraph_from_json(Path(
        __file__).absolute().parent.parent.parent.parent.parent / "try_fix_bt_min_min_counterexample_save.json")
    visited = []
    min_counterexample = graph.copy()
    current_node = max(graph.nodes)
    # while len(visited) < len(min_counterexample.nodes) - 1:
    #     visited.append(current_node)
    #     temp_min_counterexample = min_counterexample.copy()
    #     temp_min_counterexample = delete_node_and_update_cgraph(temp_min_counterexample,
    #                                                             min_counterexample.nodes[current_node])
    #     important_subgraphs = get_all_important_subgraphs(temp_min_counterexample)
        # reference = is_three_colorable(temp_min_counterexample)[0]
        # custom_sat_builder = CustomSatBuilder(temp_min_counterexample, important_subgraphs)
        # small_clauses_result = custom_sat_builder.solve_small_clauses()
        # bt_result = custom_sat_builder.solve_with_backtracking()
        # is_counterexample = reference is True and small_clauses_result is True and bt_result is False and len(important_subgraphs[BIG_CYCLE_STR]) > 0
        # if is_counterexample:
        #     print(important_subgraphs)
        #     min_counterexample = temp_min_counterexample
        #     save_graph_json(min_counterexample, "bt_min_counterexample_save", generator="counterexampler")
        #     current_node = max(min_counterexample.nodes)
        # else:
        #     current_node = max(min_counterexample.nodes - visited)
    # print(min_counterexample)
    # nx.draw(min_counterexample, with_labels=True)
    # plt.show()


if __name__ == "__main__":
    main()
