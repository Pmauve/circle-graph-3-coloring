import csv
import sys

from three_col_circle_code.col.coloring import color_with_jumping_bt_assignment
# from three_col_circle.sat_builder import ImportantSubgraphFormulaBuilder, is_three_colorable
from three_col_circle_code.col.main import *
from three_col_circle_code.custom_sat_builder import CustomSatBuilder

_generator = sys.argv[1:][0]
_size = sys.argv[1:][1]
GRAPH_PATH = Path(
    __file__).absolute().parent.parent.parent.parent / "eval" / "graph_data" / _generator / _size
CSV_PATH = Path(
    __file__).absolute().parent.parent.parent.parent / "eval" / "csv" / "jumping_bt_eval" / _generator / _size


def main():
    for file in os.listdir(GRAPH_PATH):
        graph_id = file.replace(".json", "")
        eval_jump_bt(graph_id)


def eval_jump_bt(graph_id):
    _graph = read_graph(graph_id)
    if _graph is None:
        print("error reading", GRAPH_PATH / (graph_id + ".json"))
        return
    print("found graph", graph_id)
    print(_graph)
    if not os.path.exists(CSV_PATH):
        os.makedirs(CSV_PATH)
    csv_file_path = CSV_PATH / ("jumping_bt_eval_" + graph_id + ".csv")
    # get important subgraphs + run backtracking
    isg = get_all_important_subgraphs(_graph)
    if len(isg[FIVE_CYCLE_STR]) < 1 and len(isg[BIG_CYCLE_STR]) < 1:
        print("skipping", graph_id, "since no big cycles")
        return
    custom_sat_builder = CustomSatBuilder(_graph, isg)
    result_small_clauses = custom_sat_builder.solve_small_clauses()
    result_bt = custom_sat_builder.solve_with_backtracking()
    btt_size = len(custom_sat_builder.bt_tree.nodes)
    is_assignment_sat = custom_sat_builder.verify_assignment()
    n_vars = len(custom_sat_builder.assignment)
    custom_sat_builder.print_var_assignment()
    is_valid_coloring = None
    if is_assignment_sat:
        color_with_jumping_bt_assignment(_graph, custom_sat_builder.assignment)
        is_valid_coloring = verify_3coloring(_graph) is True
    row = [{'graph_id': graph_id,
            'graph_type': _generator,
            'graph_nodes': len(_graph.nodes),
            'bt_leaves': custom_sat_builder.get_btt_leaves(),
            'result_small_clauses': result_small_clauses,
            'result_bt': result_bt,
            'btt_size': btt_size,
            'is_assignment_sat': is_assignment_sat,
            'n_vars': n_vars,
            'n_cycles': len(isg[FIVE_CYCLE_STR]) + len(isg[BIG_CYCLE_STR]),
            'finished_in_time': custom_sat_builder.finished_in_time,
            'is_valid_coloring': is_valid_coloring,
            'time_finding_contradictions': custom_sat_builder.contradiction_timer.timers["contradiction"]
            }]
    fields = ['graph_id', 'graph_type', 'graph_nodes', 'bt_leaves',
              'result_small_clauses', 'result_bt',
              'btt_size', 'is_assignment_sat', 'n_vars', 'n_cycles', 'finished_in_time',
              'is_valid_coloring', 'time_finding_contradictions']
    print(row)
    with open(csv_file_path, "w", newline='') as outfile:
        writer = csv.DictWriter(outfile, delimiter=';', fieldnames=fields)
        writer.writeheader()
        writer.writerows(row)


def read_graph(graph_id):
    csv_file_path = CSV_PATH / ("bt_eval_" + graph_id + ".csv")
    if os.path.exists(csv_file_path):
        print("already evaluated", graph_id)
        return
    _graph = fix_graph_wo_level(read_graph_from_json(GRAPH_PATH / (graph_id + ".json")))
    return _graph


if __name__ == "__main__":
    main()
