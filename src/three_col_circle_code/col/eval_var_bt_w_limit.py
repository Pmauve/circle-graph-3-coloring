import csv
import sys
import time

from three_col_circle_code.sat_builder import ImportantSubgraphFormulaBuilder, is_three_colorable
from three_col_circle_code.col.main import *


def main():
    _generator = sys.argv[1:][0]
    _size = sys.argv[1:][1]
    slurm_job_id = int(os.getenv('SLURM_ARRAY_TASK_ID') if os.getenv('SLURM_ARRAY_TASK_ID') else 0)
    GRAPH_PATH = Path(
        __file__).absolute().parent.parent.parent.parent / "eval" / "graph_data" / _generator / _size
    CSV_PATH = Path(
        __file__).absolute().parent.parent.parent.parent / "eval" / "csv" / "val_bt_eval_w_limit" / _generator / _size
    graph_id = os.listdir(str(GRAPH_PATH))[slurm_job_id].replace(".json", "")
    csv_file_path = CSV_PATH / ("bt_eval_limited_" + graph_id + ".csv")
    _graph = fix_graph_wo_level(read_graph_from_json(GRAPH_PATH / (graph_id + ".json")))
    # for f in os.listdir(str(GRAPH_PATH)):
    #     _graph = fix_graph_wo_level(read_graph_from_json(GRAPH_PATH / f))
    if _graph is None:
        print("error reading", GRAPH_PATH / (graph_id + ".json"))
        return
    # graph_id = f.replace(".json", "")
    print("found graph", graph_id)
    print(_graph)
    # get isg + run backtracking
    isg = get_all_important_subgraphs(_graph)
    if len(isg[FIVE_CYCLE_STR]) < 1 and len(isg[BIG_CYCLE_STR]) < 1:
        print("skipping", graph_id, "since no big cycles")
        return
    sat_builder = ImportantSubgraphFormulaBuilder(_graph, isg)
    is_colorable = is_three_colorable(_graph)
    sat_builder.solve_with_backtracking_values()
    if not sat_builder.time_limit_reached():
        print("finished eval within 15 minutes, no need to evaluate")
        return
    row = [{'graph_id': graph_id,
            'graph_type': _generator,
            'graph_nodes': len(_graph.nodes),
            'nr_bc': len(isg[FIVE_CYCLE_STR]) + len(isg[BIG_CYCLE_STR]),
            'bt_leaves': sat_builder.get_val_bt_leaves(),
            'is_three_colorable': is_colorable[0]
            }]
    fields = ['graph_id', 'graph_type', 'graph_nodes', 'nr_bc', 'bt_leaves', 'is_three_colorable']
    if not os.path.exists(CSV_PATH):
        os.makedirs(CSV_PATH)
    with open(csv_file_path, "w", newline='') as outfile:
        writer = csv.DictWriter(outfile, delimiter=';', fieldnames=fields)
        writer.writeheader()
        writer.writerows(row)


if __name__ == "__main__":
    main()
