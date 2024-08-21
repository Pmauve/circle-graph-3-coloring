import csv
import os
import sys
from pathlib import Path

from three_col_circle_code.greedy.solve_greedy import start_greedy
from three_col_circle_code.sat_builder import is_three_colorable
from three_col_circle_code.timer import Timer
from three_col_circle_code.util import read_graph_from_json, verify_3coloring


def main():
    bt_timer = Timer(name="solver", text="Solving 3-SAT instance took {:0.6} seconds")
    slurm_job_id = int(os.getenv('SLURM_ARRAY_TASK_ID') if os.getenv('SLURM_ARRAY_TASK_ID') is not None else 0)
    generator = sys.argv[1:][0]
    size = sys.argv[1:][1]

    GRAPH_PATH = Path(__file__).absolute().parent.parent.parent.parent / "eval" / "graph_data"
    CSV_PATH = Path(__file__).absolute().parent.parent.parent.parent / "eval" / "csv" / "greedy" / generator / size
    graph_id = os.listdir(str(GRAPH_PATH / generator / size))[slurm_job_id].replace(".json", "")
    _graph = read_graph_from_json(GRAPH_PATH / generator / size / (graph_id + ".json"))

    if _graph is not None:
        print("found graph for slurm id", slurm_job_id, ": ", graph_id)
        bt_timer.start()
        result = start_greedy(_graph)
        elapsed_time = bt_timer.stop()
        row = [{'graph_id': graph_id,
                'graph_type': generator,
                'graph_nodes': len(_graph.nodes),
                'bt_leaves': result,
                'found_3_coloring': verify_3coloring(_graph) is True,
                'is_3_colorable': is_three_colorable(_graph)[0],
                'elapsed_time': elapsed_time
                }]
        fields = ['graph_id', 'graph_type', 'graph_nodes', 'bt_leaves', 'found_3_coloring', 'is_3_colorable',
                  'elapsed_time']
        csv_file_path = CSV_PATH / ("greedy_eval_" + graph_id + ".csv")
        if not os.path.exists(CSV_PATH):
            os.makedirs(CSV_PATH)
        with open(csv_file_path, "w", newline='') as outfile:
            writer = csv.DictWriter(outfile, delimiter=';', fieldnames=fields)
            writer.writeheader()
            writer.writerows(row)
    else:
        print("could not find graph for slurm job id", slurm_job_id, "and graph id", graph_id)


if __name__ == "__main__":
    main()
