import csv
import sys

from three_col_circle_code.custom_sat_builder import CustomSatBuilder
# from three_col_circle.sat_builder import ImportantSubgraphFormulaBuilder, is_three_colorable
from three_col_circle_code.col.main import *

_generator = sys.argv[1:][0]
_size = sys.argv[1:][1]
GRAPH_PATH = Path(
    __file__).absolute().parent.parent.parent.parent / "eval" / "graph_data" / _generator / _size
CSV_PATH = Path(
    __file__).absolute().parent.parent.parent.parent / "eval" / "csv" / "regular_bt_eval" / _generator / _size
task_index = int(os.getenv("TASK_INDEX", "0"))


def main():
    eval_regular_bt()


def eval_regular_bt():
    graph_id = os.listdir(str(GRAPH_PATH))[task_index].replace(".json", "")
    _graph = read_graph(graph_id)
    if _graph is None:
        print("error reading", GRAPH_PATH / (graph_id + ".json"))
        return
    print("found graph", graph_id)
    print(_graph)
    if len(_graph.nodes) > 200:
        print("skipping because too big anyway")
        return
    if not os.path.exists(CSV_PATH):
        os.makedirs(CSV_PATH)
    csv_file_path = CSV_PATH / ("regular_bt_eval_" + graph_id + ".csv")
    # get isg + run backtracking
    isg = get_all_important_subgraphs(_graph)
    if len(isg[FIVE_CYCLE_STR]) < 1 and len(isg[BIG_CYCLE_STR]) < 1:
        print("skipping", graph_id, "since no big cycles")
        return
    custom_sat_builder = CustomSatBuilder(_graph, isg)
    result_small_clauses = custom_sat_builder.solve_small_clauses()
    result_bt = custom_sat_builder.solve_with_regular_backtracking()
    is_assignment_sat = custom_sat_builder.verify_assignment()
    n_vars = len(custom_sat_builder.assignment)
    custom_sat_builder.print_var_assignment()
    row = [{'graph_id': graph_id,
            'graph_type': _generator,
            'graph_nodes': len(_graph.nodes),
            'bt_leaves': custom_sat_builder.leaves,
            'result_small_clauses': result_small_clauses,
            'result_bt': result_bt,
            'btt_size': custom_sat_builder.current_node + 1,
            'is_assignment_sat': is_assignment_sat,
            'n_vars': n_vars,
            'finished_in_time': custom_sat_builder.finished_in_time,
            'time_finding_contradictions': custom_sat_builder.contradiction_timer.timers["contradiction"]
            }]
    fields = ['graph_id', 'graph_type', 'graph_nodes', 'bt_leaves',
              'result_small_clauses', 'result_bt',
              'btt_size', 'is_assignment_sat', 'n_vars', 'finished_in_time', 'time_finding_contradictions']
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
    # for f in os.listdir(str(GRAPH_PATH)):
    #     _graph = fix_graph_wo_level(read_graph_from_json(GRAPH_PATH / f))
    return _graph


if __name__ == "__main__":
    main()
