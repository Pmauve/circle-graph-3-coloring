import csv
import sys

from three_col_circle_code.sat_builder import is_three_colorable
from three_col_circle_code.util import *


slurm_job_id = int(os.getenv('SLURM_ARRAY_TASK_ID') if os.getenv('SLURM_ARRAY_TASK_ID') is not None else 0)
generator = sys.argv[1:][0]
size = sys.argv[1:][1]


def main():
    global slurm_job_id, generator, size
    if generator not in ['r', 'ry', 'rc', 'rcy']:
        print("invalid generator, must be r, ry, rc or rcy")
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
        result = is_three_colorable(_graph)
        row = [{'graph_id': graph_id,
                'graph_type': generator,
                'graph_nodes': len(_graph.nodes),
                'is_3_colorable': result[0],
                'elapsed_time': result[1]
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
