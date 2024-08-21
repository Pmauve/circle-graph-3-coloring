import csv
import sys

from three_col_circle_code.sat_builder import ImportantSubgraphFormulaBuilder, is_three_colorable
from three_col_circle_code.col.main import *
from three_col_circle_code.col.coloring import *


_generator = sys.argv[1:][0]
_size = sys.argv[1:][1]
slurm_job_id = int(os.getenv('SLURM_ARRAY_TASK_ID')if os.getenv('SLURM_ARRAY_TASK_ID') is not None else 0)
GRAPH_PATH = Path(
        __file__).absolute().parent.parent.parent.parent / "eval" / "graph_data" / _generator / _size
CSV_PATH = Path(
    __file__).absolute().parent.parent.parent.parent / "eval" / "csv" / "eval_coloring" / _generator / _size


def main():
    eval_coloring_w_solver()


def eval_coloring_w_solver():
    graph_id = os.listdir(str(GRAPH_PATH))[slurm_job_id].replace(".json", "")
    _graph = fix_graph_wo_level(read_graph_from_json(GRAPH_PATH / (graph_id + ".json")))
    if _graph is None:
        print("error reading", GRAPH_PATH / (graph_id + ".json"))
        return
    print("found graph", graph_id)
    print(_graph)
    isg = get_all_important_subgraphs(_graph)
    sat_builder = ImportantSubgraphFormulaBuilder(_graph, isg)
    is_colorable = is_three_colorable(_graph)
    sat_builder.solve_small_subgraphs()
    for assertion in sat_builder.clauses_for_five_and_big_cycles():
        sat_builder.solver.add_assertion(assertion)
    sat_builder.solve_sat(sat_builder.solver)
    color_with_c(_graph, sat_builder)
    is_valid_coloring = verify_3coloring(_graph) is True
    save_graph_json(_graph, filename=(graph_id + "_colored"), generator=_generator, size=_size, colored=True)
    row = [{'graph_id': graph_id,
            'graph_type': _generator,
            'graph_nodes': len(_graph.nodes),
            'is_three_colorable': is_colorable[0],
            'is_valid_coloring': is_valid_coloring
            }]
    fields = ['graph_id', 'graph_type', 'graph_nodes', 'is_three_colorable', 'is_valid_coloring']
    csv_file_path = CSV_PATH / ("col_eval_" + graph_id + ".csv")
    if not os.path.exists(CSV_PATH):
        os.makedirs(CSV_PATH)
    with open(csv_file_path, "w", newline='') as outfile:
        writer = csv.DictWriter(outfile, delimiter=';', fieldnames=fields)
        writer.writeheader()
        writer.writerows(row)


if __name__ == "__main__":
    main()
