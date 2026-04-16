import csv
import sys

from three_col_circle_code.generation.families import legacy_cli_families
from three_col_circle_code.sat.baseline import LEGACY_PYSMT_MSAT, solve_3color_baseline
from three_col_circle_code.util import *


slurm_job_id = int(os.getenv('SLURM_ARRAY_TASK_ID') if os.getenv('SLURM_ARRAY_TASK_ID') is not None else 0)


def main():
    global slurm_job_id
    generator = sys.argv[1:][0]
    size = sys.argv[1:][1]
    backend = sys.argv[1:][2] if len(sys.argv[1:]) > 2 else LEGACY_PYSMT_MSAT
    if generator not in legacy_cli_families():
        print("invalid generator, must be " + ", ".join(legacy_cli_families()))
        exit()
    if size not in ['s', 'm', 'l', 'xl']:
        print("invalid size, must be s, m, l or xl")
        exit()

    GRAPH_PATH = Path(__file__).absolute().parent.parent.parent.parent / "eval" / "graph_data"
    CSV_PATH = Path(__file__).absolute().parent.parent.parent.parent / "eval" / "csv" / generator / size
    graph_id = os.listdir(str(GRAPH_PATH / generator / size))[slurm_job_id].replace(".json", "")
    _graph = read_graph_from_json(GRAPH_PATH / generator / size / (graph_id + ".json"))

    if _graph is not None:
        print("found graph for slurm id", slurm_job_id, ": ", graph_id)
        print(_graph)
        # run solver
        result = solve_3color_baseline(_graph, backend=backend)
        row = [{'graph_id': graph_id,
                'graph_type': generator,
                'graph_nodes': len(_graph.nodes),
                'is_3_colorable': result.is_sat,
                'elapsed_time': result.elapsed_time
                }]
        fields = ['graph_id', 'graph_type', 'graph_nodes', 'is_3_colorable', 'elapsed_time']
        csv_file_path = CSV_PATH / ("eval_" + graph_id + ".csv")
        if not os.path.exists(CSV_PATH):
            os.makedirs(CSV_PATH)
        with open(csv_file_path, "w", newline='') as outfile:
            writer = csv.DictWriter(outfile, delimiter=';', fieldnames=fields)
            writer.writeheader()
            writer.writerows(row)
    else:
        print("could not find graph for slurm job id", slurm_job_id, "and graph id", graph_id)


if __name__ == "main":
    main()
