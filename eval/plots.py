import csv
import json
from pathlib import Path
from networkx.readwrite import json_graph

import pandas as pd
import os
import seaborn as sns
import matplotlib.pyplot as plt


def main():
    plot_regular_bt()
    plot_jumping_bt()


def plot_from_file():
    CSV_PATH = Path(__file__).absolute().parent
    filename = "regular_bt_eval.csv"
    df = pd.read_csv(CSV_PATH / filename, sep=';')
    print(df)
    sns.scatterplot(x="graph_nodes", y="bt_leaves", data=df, hue="finished_in_time")
    plt.show()


def plot_regular_bt():
    generators_to_merge = ['rcy']
    sizes_to_merge = ['s', 'm']
    files_to_merge = []
    for generator in generators_to_merge:
        for size in sizes_to_merge:
            CSV_PATH = Path(__file__).absolute().parent / "csv" / "regular_bt_eval" / generator / size
            if not os.path.exists(CSV_PATH):
                continue
            files_to_merge = files_to_merge + [CSV_PATH / f for f in os.listdir(str(CSV_PATH))]
    df = pd.concat((pd.read_csv(f, sep=';') for f in files_to_merge), ignore_index=True)
    save_df_to_csv(df, "regular_bt_eval.csv")
    print(df)
    df["bin"] = pd.cut(df["graph_nodes"], 20)
    g = df.groupby("bin")["finished_in_time"]
    p = g.sum() / g.count() * 100
    p = p.reset_index()
    p["bin"] = p["bin"].apply(lambda b: b.mid)
    sns.lineplot(x="bin", y="finished_in_time", data=p)
    plt.xlabel('number of vertices')
    plt.ylabel('% of instances finished in time')
    # plt.show()
    plt.ioff()
    plt.savefig("eval_bt_perc_finished.pdf")
    plt.close()


def plot_jumping_bt():
    generators_to_merge = ['rcy']
    sizes_to_merge = ['s', 'm']
    files_to_merge = []
    for generator in generators_to_merge:
        for size in sizes_to_merge:
            CSV_PATH = Path(__file__).absolute().parent / "csv" / "jumping_bt_eval" / generator / size
            if not os.path.exists(CSV_PATH):
                continue
            files_to_merge = files_to_merge + [CSV_PATH / f for f in os.listdir(str(CSV_PATH))]
    df = pd.concat((pd.read_csv(f, sep=';') for f in files_to_merge), ignore_index=True).sort_values("result_bt")
    print(df)
    save_df_to_csv(df, "jumping_bt_eval.csv")
    sns.scatterplot(x="graph_nodes", y="bt_leaves", data=df, hue="result_bt")
    plt.xlabel('number of vertices')
    plt.ylabel('number of backtracking leaves')
    # plt.show()
    plt.ioff()
    plt.savefig("eval_bt_jumping.pdf")
    plt.close()


def plot_density():
    generators_to_merge = ['rcy']
    sizes_to_merge = ['s', 'm']
    graphs_to_eval = []
    CSV_PATH = Path(__file__).absolute().parent / "jumping_bt_eval.csv"
    ids = pd.read_csv(CSV_PATH, sep=';')["graph_id"]
    for generator in generators_to_merge:
        for size in sizes_to_merge:
            GRAPH_PATH = Path(__file__).absolute().parent / "graph_data" / generator / size
            for graph_id in ids:
                if not graph_id + ".json" in os.listdir(str(GRAPH_PATH)):
                    continue
                with open(GRAPH_PATH / (graph_id + ".json")) as infile:
                    j_graph = json.load(infile)
                    graph = json_graph.node_link_graph(j_graph)
                    graphs_to_eval.append(graph)
    print(len(graphs_to_eval))
    with open(Path(__file__).absolute().parent / "graph_meta_eval.csv", "w", newline='') as outfile:
        fields = ['edges', 'nodes', 'density']
        writer = csv.DictWriter(outfile, delimiter=';', fieldnames=fields)
        writer.writeheader()
        for graph in graphs_to_eval:
            row = [{'edges': len(graph.edges),
                    'nodes': len(graph.nodes),
                    'density': (len(graph.edges) / len(graph.nodes))}]
            writer.writerows(row)
    df = pd.read_csv(Path(__file__).absolute().parent / "graph_meta_eval.csv", sep=';')
    sns.histplot(data=df, x="density", kde=True)
    print(df)
    plt.show()


def plot_val_bt_limited():
    generators_to_merge = ['rcy']
    sizes_to_merge = ['s', 'm']
    files_to_merge = []
    for generator in generators_to_merge:
        for size in sizes_to_merge:
            CSV_PATH = Path(__file__).absolute().parent / "csv" / "val_bt_eval_w_limit" / generator / size
            if not os.path.exists(CSV_PATH):
                continue
            files_to_merge = files_to_merge + [CSV_PATH / f for f in os.listdir(str(CSV_PATH))]
    df = pd.concat((pd.read_csv(f, sep=';') for f in files_to_merge), ignore_index=True)
    print(df)
    save_df_to_csv(df, "val_bt_eval.csv")
    sns.scatterplot(x="graph_nodes", y="bt_leaves", data=df, hue="is_three_colorable")
    plt.show()


def plot_coloring_eval():
    generators_to_merge = ['rcy']
    sizes_to_merge = ['s', 'm']
    files_to_merge = []
    for generator in generators_to_merge:
        for size in sizes_to_merge:
            CSV_PATH = Path(__file__).absolute().parent / "csv" / "eval_coloring" / generator / size
            if not os.path.exists(CSV_PATH):
                continue
            files_to_merge = files_to_merge + [CSV_PATH / f for f in os.listdir(str(CSV_PATH))]
    df = pd.concat((pd.read_csv(f, sep=';') for f in files_to_merge), ignore_index=True)
    print(df)
    valid_colorings = sum(df['is_valid_coloring'] == True)
    print("valid colorings:", valid_colorings)
    all_colorings = df.shape[0]
    save_df_to_csv(df, "val_bt_eval.csv")
    print("percentage of correct colorings:", (valid_colorings / all_colorings) * 100)


def plot_val_bt_eval():
    generators_to_merge = ['rcy']
    sizes_to_merge = ['s', 'm', 'l', 'xl']
    files_to_merge = []
    for generator in generators_to_merge:
        for size in sizes_to_merge:
            CSV_PATH = Path(__file__).absolute().parent / "csv" / "val_bt_eval" / generator / size
            if not os.path.exists(CSV_PATH):
                continue
            files_to_merge = files_to_merge + [CSV_PATH / f for f in os.listdir(str(CSV_PATH))]
    df = pd.concat((pd.read_csv(f, sep=';') for f in files_to_merge), ignore_index=True)
    print(df)
    save_df_to_csv(df, "val_bt_eval.csv")
    sns.scatterplot(x="graph_nodes", y="bt_leaves", data=df, hue="is_three_colorable")
    plt.show()


def plot_bt_eval():
    generators_to_merge = ['rcy', 'rc', 'ma']
    sizes_to_merge = ['s', 'm', 'l', 'xl', 'c', 'rc']
    files_to_merge = []
    for generator in generators_to_merge:
        for size in sizes_to_merge:
            CSV_PATH = Path(__file__).absolute().parent / "csv" / "bt_eval" / generator / size
            if not os.path.exists(CSV_PATH):
                continue
            files_to_merge = files_to_merge + [CSV_PATH / f for f in os.listdir(str(CSV_PATH))]
    df = pd.concat((pd.read_csv(f, sep=';') for f in files_to_merge), ignore_index=True)
    print(df)
    save_df_to_csv(df, "bt_eval.csv")
    sns.scatterplot(x="graph_nodes", y="bt_leaves", data=df, hue="is_three_colorable")
    plt.show()


def plot_greedy_bt():
    generators_to_merge = ['rc', 'rcy']
    sizes_to_merge = ['m', 'l']
    files_to_merge = []
    for generator in generators_to_merge:
        for size in sizes_to_merge:
            CSV_PATH = Path(__file__).absolute().parent / "csv" / "greedy" / generator / size
            files_to_merge = files_to_merge + [CSV_PATH / f for f in os.listdir(str(CSV_PATH))]
    df = pd.concat((pd.read_csv(f, sep=';') for f in files_to_merge), ignore_index=True).sort_values(by=['bt_leaves'],
                                                                                                     ascending=False)
    print(df)
    sns.scatterplot(x="graph_nodes", y="bt_leaves", data=df, hue="graph_type")
    plt.show()


def plot_sat_running_time():
    generators_to_merge = ['ry', 'rcy', 'rc']
    sizes_to_merge = ['s', 'm', 'l', 'xl']
    files_to_merge = []
    for generator in generators_to_merge:
        for size in sizes_to_merge:
            CSV_PATH = Path(__file__).absolute().parent / "csv" / generator / size
            if not os.path.exists(CSV_PATH):
                continue
            files_to_merge = files_to_merge + [CSV_PATH / f for f in os.listdir(str(CSV_PATH))]
    df = pd.concat((pd.read_csv(f, sep=';') for f in files_to_merge), ignore_index=True)
    print(df)
    # save_df_to_csv(df, "rc_s.csv")
    sns.scatterplot(x="graph_nodes", y="elapsed_time", data=df, hue="graph_type")
    plt.show()


def save_df_to_csv(dataframe, filename):
    dataframe.to_csv(filename, encoding='utf-8', index=False, sep=';')


# if __name__ == "main":
main()
