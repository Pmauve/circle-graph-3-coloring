from three_col_circle_code.col.rec_tailtriangle import find_all_tailtriangles, find_tailtriangles_over_all_levels
from three_col_circle_code.col.rec_boxslash import find_all_boxslashes, find_boxslashes_over_all_levels
from three_col_circle_code.col.rec_4cycles import find_all_four_cycles, find_four_cycles_over_all_levels
from three_col_circle_code.col.rec_5cycles import find_all_five_cycles_like_big_cycles
from three_col_circle_code.col.rec_big_cycles import find_all_big_cycles
from three_col_circle_code.util import *


def main():
    print("main")


def get_all_important_subgraphs(c_graph):
    for i in c_graph.nodes():
        c_graph.nodes[i]['importantsubgraphs'] = []
    return {TAILTRIANGLE_STR: find_all_tailtriangles(c_graph),
            BOXSLASH_STR: find_all_boxslashes(c_graph),
            FOUR_CYCLE_STR: find_all_four_cycles(c_graph),
            # FIVE_CYCLE_STR: find_all_five_cycles(c_graph),
            FIVE_CYCLE_STR: find_all_five_cycles_like_big_cycles(c_graph),
            BIG_CYCLE_STR: find_all_big_cycles(c_graph)}


def get_important_subgraphs_over_all_levels(c_graph):
    for i in c_graph.nodes():
        c_graph.nodes[i]['importantsubgraphs'] = []
    return {TAILTRIANGLE_STR: find_tailtriangles_over_all_levels(c_graph),
            BOXSLASH_STR: find_boxslashes_over_all_levels(c_graph),
            FOUR_CYCLE_STR: find_four_cycles_over_all_levels(c_graph),
            FIVE_CYCLE_STR: find_all_five_cycles_like_big_cycles(c_graph),
            BIG_CYCLE_STR: find_all_big_cycles(c_graph)}


if __name__ == "__main__":
    main()
