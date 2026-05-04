import inspect
import time
from pprint import pprint

import networkx as nx
from pysmt.shortcuts import Symbol, And, Or, Not, Solver, EqualsOrIff, Implies, get_model, get_unsat_core

from three_col_circle_code.timer import Timer
from three_col_circle_code.util import *

solver_timer = Timer(name="solver", text="Solving 3-SAT instance took {:0.6} seconds", logger=None)

computing_c_timer = Timer(name="computing_cl", text="Computing clauses for c* took {:0.6f} seconds")
solving_c_timer = Timer(name="solving_c", text="Solving SAT for c^* took {:0.6f} seconds")
five_cycle_bt_timer = Timer(name="five_cycle_backtrack", text="Backtracking 5-cycles took {:0.6f} seconds")
big_cycle_bt_timer = Timer(name="big_cycle_backtrack", text="Backtracking big cycles took {:0.6f} seconds")


def is_three_colorable(graph):
    global solver_timer
    clauses = []
    variables = dict()
    variable_names = []
    for n in graph.nodes:
        n_r_string = str(n) + 'r'
        variable_names.append(n_r_string)
        n_r = Symbol(n_r_string)
        n_b_string = str(n) + 'b'
        variable_names.append(n_b_string)
        n_b = Symbol(n_b_string)
        n_g_string = str(n) + 'g'
        variable_names.append(n_g_string)
        n_g = Symbol(n_g_string)
        variables[n_r_string] = n_r
        variables[n_b_string] = n_b
        variables[n_g_string] = n_g
        must_have_a_color = Or(n_r, n_b, n_g)
        clauses.append(must_have_a_color)
    for e in graph.edges:
        u = e[0]
        v = e[1]
        u_r = variables[str(u) + 'r']
        v_r = variables[str(v) + 'r']
        must_not_be_both_red = Or(Not(u_r), Not(v_r))
        clauses.append(must_not_be_both_red)
        u_b = variables[str(u) + 'b']
        v_b = variables[str(v) + 'b']
        must_not_be_both_blue = Or(Not(u_b), Not(v_b))
        clauses.append(must_not_be_both_blue)
        u_g = variables[str(u) + 'g']
        v_g = variables[str(v) + 'g']
        must_not_be_both_green = Or(Not(u_g), Not(v_g))
        clauses.append(must_not_be_both_green)
    formula = And(*clauses)
    solver = Solver(name="msat")
    solver.add_assertion(formula)
    solver_timer.start()
    can_solve = solver.solve()
    elapsed_time = solver_timer.stop()
    if can_solve:
        # print("we have a solution")
        partial_model = [EqualsOrIff(variables[c], solver.get_value(variables[c])) for c in
                         variable_names]
        # print("partial model: " + str(partial_model))
    else:
        # print("we have no solution")
        # print("unsat core:", get_unsat_core(clauses))
        pass
    return can_solve, elapsed_time


class ImportantSubgraphFormulaBuilder:
    c_graph = nx.Graph()
    wc_bt_tree = nx.Graph()
    c_domain = set()  # contains frozensets of two node labels
    domain_vars = dict()  # maps frozensets to formula symbols
    important_subgraph_vars = set()  # keep track which c* values are relevant for coloring important subgraphs
    btt_important_subgraph_vars = set()
    solver = Solver(name="msat")
    btt_solver = Solver(name="msat")
    tailtriangles = []
    boxslashes = []
    four_cycles = []
    five_cycles = []
    big_cycles = []
    five_cycle_backtrack_was_success = False
    big_cycle_backtrack_was_success = False
    five_cycle_backtrack_leaves = 0
    big_cycle_backtrack_leaves = 0

    tailtriangle_clauses = set()
    boxslash_clauses = set()
    four_cycle_clauses = set()
    five_cycle_cnf_clauses = set()
    big_cycle_clauses = set()
    is_three_colorable = False
    formula = {}

    big_cycle_var_keys = set()
    to_assign = []
    assigned = []
    sat_graph = nx.DiGraph()
    sat_graph_dict = dict()
    var_not = frozenset({'not'})
    hull_solver = Solver(name="msat")
    bc_clause_solver = Solver(name="msat")
    value_bt_tree = nx.Graph()

    val_bt_timelimit_start = 0

    def __init__(self, c_graph, important_subgraphs):
        self.c_graph = c_graph
        self.sat_graph = nx.DiGraph()
        self.sat_graph_dict = dict()
        self.get_c_domain()
        self.tailtriangles = important_subgraphs.get(TAILTRIANGLE_STR)
        self.boxslashes = important_subgraphs.get(BOXSLASH_STR)
        self.four_cycles = important_subgraphs.get(FOUR_CYCLE_STR)
        self.five_cycles = important_subgraphs.get(FIVE_CYCLE_STR)
        self.big_cycles = important_subgraphs.get(BIG_CYCLE_STR)
        computing_c_timer.start()
        self.tailtriangle_clauses = self.clauses_for_tailtriangle()
        self.boxslash_clauses = self.clauses_for_boxslash()
        self.four_cycle_clauses = self.clauses_for_4cycle()
        self.five_cycle_cnf_clauses = self.cnf_clauses_for_5cycle()
        self.five_cycle_dnf_clauses = self.dnf_clauses_for_5cycle()
        computing_c_timer.stop()
        self.solver.reset_assertions()
        self.btt_solver.reset_assertions()
        self.hull_solver.reset_assertions()
        self.bc_clause_solver.reset_assertions()
        self.is_three_colorable = False
        self.formula = {}
        self.five_cycle_backtrack_was_success = False
        self.big_cycle_backtrack_was_success = False
        self.five_cycle_backtrack_leaves = 0
        self.big_cycle_backtrack_leaves = 0
        self.big_cycle_var_keys = set()
        self.to_assign = []
        self.assigned = []

    def get_val_bt_leaves(self):
        leaves = 0
        if len(self.value_bt_tree.nodes) == 1:
            return 1
        for i in self.value_bt_tree.nodes:
            if i == 0:
                continue
            if len(list(nx.neighbors(self.value_bt_tree, i))) == 1:
                leaves = leaves + 1
        return leaves

    def solve_with_backtracking_values(self):
        self.big_cycle_clauses = self.clauses_for_five_and_big_cycles()
        self.solve_small_subgraphs()
        # compute implications for big cycles
        implications = self.get_implications()
        implication_asserts = []
        # print("sat graph:", self.sat_graph.nodes.data())
        for i in implications:
            # print("var:", i)
            # print("implications:")
            for implies in implications[i]:
                implication = self.sat_graph.nodes[implies]['c_var']
                var = self.domain_vars[i.difference(self.var_not)]
                if len(self.var_not.intersection(i)) > 0:
                    var = Not(var)
                # print(implication)
                implication_asserts.append(Implies(var, implication))
        # print("implication asserts:", implication_asserts)
        for i in implication_asserts:
            self.hull_solver.add_assertion(i)
        self.hull_solver.solve()
        # backtrack over each value assignment for each variable
        self.to_assign = [e for e in self.get_c_vars_for_big_cycles()]
        # print("to assign:", self.to_assign)
        root = len(self.value_bt_tree.nodes)
        if len(self.to_assign) < 1:
            self.value_bt_tree.add_node(root, var="root")
            print("no variables to assign")
            return
        print("starting variable backtracking...")
        self.value_bt_tree.add_node(root, var="root")
        self.val_bt_timelimit_start = time.time()
        return self.backtrack_values(root)

    def get_implications(self):
        # for each variable of big cycle find all reachable variables in sat_graph
        big_cycle_vars = self.get_c_vars_for_big_cycles()
        # print("finding implications for", len(self.big_cycle_var_keys), "keys")
        implications = dict()
        for key in self.big_cycle_var_keys:
            implications_for_bc_vars = [i for i in nx.descendants(self.sat_graph, self.sat_graph_dict[key]) if
                                        self.sat_graph.nodes[i]['c_var'] in big_cycle_vars]
            # print(key, implications_for_bc_vars)
            if len(implications_for_bc_vars) < 1:
                continue
            implications[key] = implications_for_bc_vars
        # print("implications:", implications)
        return implications

    def backtrack_values(self, parent):
        # we fix the first variable value, see if we find a contradiction
        # either in 2SAT or in one of the 3SAT clauses
        current_value = self.to_assign.pop()
        current_node = len(self.value_bt_tree.nodes)
        self.value_bt_tree.add_node(current_node, times_assigned=0, var=current_value)
        self.value_bt_tree.add_edge(parent, current_node)
        print("current node:", current_node)
        old_asserts_hull = self.hull_solver.assertions.copy()
        # print("old assertions:", old_asserts_hull)
        new_asserts_hull = self.hull_solver.assertions.copy()
        new_asserts_hull.append(current_value)
        # print("new assertions:", new_asserts_hull)
        print("current value:", current_value)
        self.important_subgraph_vars.add(current_value)
        self.hull_solver.reset_assertions()
        for assertion in new_asserts_hull:
            self.hull_solver.add_assertion(assertion)
        unsat_bc_clause = self.find_unsat_core_with_bc_clause()
        is_valid_for_hull = self.hull_solver.solve()
        if self.time_limit_reached():
            print("reached the time limit, stopping ...")
            return is_valid_for_hull
        if len(self.to_assign) < 1:
            # we have assigned all variables
            # return if we still have a solution
            print("reached last variable")
            print("returning l.225:", is_valid_for_hull is True)
            return is_valid_for_hull is True
        if is_valid_for_hull is True and unsat_bc_clause is None:
            print("is valid right away")
            self.assigned.append(current_value)
            is_valid_for_hull = self.backtrack_values(current_node)
            if self.time_limit_reached():
                print("reached the time limit, stopping ...")
                return is_valid_for_hull
        if is_valid_for_hull is True and unsat_bc_clause is not None:
            # we're still trying True, but we found an unsat core
            # print("we are looking for a variable in this clause:", unsat_bc_clause)
            if current_value in unsat_bc_clause:
                print("variable is in clause, need to try the other assignment")
                is_valid_for_hull = False
            else:
                print(current_value, "not in there")
                for assertion in old_asserts_hull:
                    self.hull_solver.add_assertion(assertion)
                if parent == 0:
                    # we are at the first value and have nothing to backtrack yet, so try the other value
                    is_valid_for_hull = False
                else:
                    self.to_assign.append(current_value)
                    # print("returning unsat_bc_clause l.288:", unsat_bc_clause)
                    return unsat_bc_clause
        if is_valid_for_hull is False:
            # try False
            print("the first assignment is no solution - hull is unsat")
            self.hull_solver.reset_assertions()
            new_asserts_hull = old_asserts_hull
            new_asserts_hull.append(Not(current_value))
            for assertion in new_asserts_hull:
                self.hull_solver.add_assertion(assertion)
            current_node = len(self.value_bt_tree.nodes)
            self.value_bt_tree.add_node(current_node, times_assigned=0, var=Not(current_value))
            self.value_bt_tree.add_edge(parent, current_node)
            is_valid_for_hull = self.hull_solver.solve()
            unsat_bc_clause = self.find_unsat_core_with_bc_clause()
            if unsat_bc_clause is not None:
                # print("this clause was found:", unsat_bc_clause)
                # print("cannot assign a new value for !", current_value, "backtrack")
                # backtrack to a variable that resolves the contradiction
                # go back in the tree and put nodes on the stack until we find the node that resolves the contradiction
                self.hull_solver.reset_assertions()
                self.to_assign.append(current_value)
                for assertion in old_asserts_hull:
                    self.hull_solver.add_assertion(assertion)
                # print("returning l.252:", unsat_bc_clause)
                return unsat_bc_clause
            if is_valid_for_hull is True:
                self.assigned.append(current_value)
                is_valid_for_hull = self.backtrack_values(current_node)
                if self.time_limit_reached():
                    print("reached the time limit, stopping ...")
                    return is_valid_for_hull
            if type(is_valid_for_hull) is not bool:
                looking_for_clause = is_valid_for_hull
                # print("we are looking for a variable in this clause:", looking_for_clause)
                # print("cannot assign a new value for !", current_value, "backtrack")
                self.hull_solver.reset_assertions()
                for assertion in old_asserts_hull:
                    self.hull_solver.add_assertion(assertion)
                # print("returning l.264:", looking_for_clause)
                self.to_assign.append(current_value)
                return looking_for_clause
            if is_valid_for_hull is False:
                # print("the last assignment is no solution - hull is", is_valid_for_hull)
                self.to_assign.append(current_value)
                self.hull_solver.reset_assertions()
                for assertion in old_asserts_hull:
                    self.hull_solver.add_assertion(assertion)
                print("returning False l.272:", False)
                return False
        print("done")
        # print("returning l.291:", is_valid_for_hull is True)
        return is_valid_for_hull is True

    def time_limit_reached(self):
        return time.time() - 900 > self.val_bt_timelimit_start

    def find_unsat_core_with_bc_clause(self):
        all_assertions = self.hull_solver.assertions.copy()
        for clause in self.big_cycle_clauses:
            self.bc_clause_solver.add_assertion(And(*all_assertions, clause))
            # print("checking:", self.bc_clause_solver.assertions)
            is_sat = self.bc_clause_solver.solve()
            # print("is clause still valid:", is_sat)
            self.bc_clause_solver.reset_assertions()
            if is_sat is False:
                unsat_core = get_unsat_core(set(all_assertions) | {clause})
                print(str(unsat_core))
                return unsat_core
            all_assertions.append(clause)

    def get_c_vars_for_big_cycles(self):
        big_cycle_vars = set()
        for key in self.five_cycles:
            big_cycle_vars = big_cycle_vars.union(self.get_c_vars_for_big_cycle(self.five_cycles[key]))
        for key in self.big_cycles:
            big_cycle_vars = big_cycle_vars.union(self.get_c_vars_for_big_cycle(self.big_cycles[key]))
        return big_cycle_vars

    def solve_with_3_sat(self):
        computing_c_timer.start()
        self.big_cycle_clauses = self.clauses_for_big_cycles()
        computing_c_timer.stop()
        self.formula = And(*self.tailtriangle_clauses, *self.boxslash_clauses, *self.four_cycle_clauses,
                           *self.five_cycle_cnf_clauses, *self.five_cycle_dnf_clauses,
                           *self.big_cycle_clauses).simplify()
        self.solver.add_assertion(self.formula)
        self.solve_sat(self.solver)
        if not self.is_three_colorable:
            print("c* values: " + str([v for v in self.domain_vars.values()]))
            print("Sat formula: " + str(self.formula))

    def solve_small_subgraphs(self):
        print("solving small subgraphs...")
        self.formula = And(*self.tailtriangle_clauses, *self.boxslash_clauses, *self.four_cycle_clauses,
                           *self.five_cycle_cnf_clauses).simplify()
        self.solver.add_assertion(self.formula)
        self.solve_sat(self.solver)

    def solve_with_backtracking(self):
        print("start backtracking")
        self.bt_setup()
        self.backtrack_5_cycles_assignments()
        self.wc_bt_tree.add_node(0, cycle_id="root", is_valid=True, is_leaf=False)
        if len(self.big_cycles) < 1:
            self.wc_bt_tree.nodes[0]['is_leaf'] = True
        if self.is_three_colorable:
            print("yay 3 colorable, building entire backtracking tree for big cycles")
            root = self.get_big_cycle_with_min_free_vars()
            if root is not None:
                self.btt_important_subgraph_vars = self.important_subgraph_vars.copy()
                assertions = self.solver.assertions.copy()
                for assertion in assertions:
                    self.btt_solver.add_assertion(assertion)
                self.solve_sat(self.btt_solver, False)
                self.backtrack_all(root, 0)
            print("backtracking big cylces...")
            self.backtrack_big_cycle_c_assignments()

    # def get_entire_bt_tree(self):
    #     global wc_bt_tree
    #     wc_bt_tree.add_node(0, cycle_id="root", is_valid=True, is_leaf=False)
    #     if len(self.big_cycles) < 1:
    #         wc_bt_tree.nodes[0]['is_leaf'] = True
    #         return wc_bt_tree
    #     self.bt_setup()
    #     if not self.is_three_colorable:
    #         return wc_bt_tree
    #     root = self.get_big_cycle_with_min_free_vars()
    #     if root is None:
    #         return wc_bt_tree
    #     self.backtrack_all(root, 0)
    #     return wc_bt_tree

    def bt_setup(self):
        print("starting setup...")
        # We want to make sure that backtracking doesn't fail bc we chose a bad 2SAT solution,
        # so we use the 2SAT solution the 3SAT formula gives us
        three_sat_solver = Solver(name="msat")
        three_sat_formula = And(*self.tailtriangle_clauses, *self.boxslash_clauses, *self.four_cycle_clauses,
                                *self.five_cycle_cnf_clauses, *self.clauses_for_big_cycles()).simplify()
        three_sat_solver.add_assertion(three_sat_formula)
        self.solve_sat(three_sat_solver, False)
        self.formula = And(*self.tailtriangle_clauses, *self.boxslash_clauses, *self.four_cycle_clauses,
                           *self.five_cycle_cnf_clauses).simplify()
        # self.formula = And(*self.tailtriangle_clauses, *self.boxslash_clauses, *self.four_cycle_clauses,
        #                    *self.five_cycle_cnf_clauses).simplify()
        # self.solve_sat(three_sat_solver, False)
        for var in self.important_subgraph_vars:
            if three_sat_solver.get_py_value(var):
                self.solver.add_assertion(var)
            else:
                self.solver.add_assertion(Not(var))
        self.solver.add_assertion(self.formula)
        # print("Sat formula: " + str(self.formula))
        # print("c* values: " + str([v for v in self.domain_vars.values()]))
        self.solve_sat(self.solver)

    def backtrack_5_cycles_assignments(self):
        if len(self.five_cycles) < 1:
            self.five_cycle_backtrack_was_success = True
        else:
            five_cycle_bt_timer.start()
            self.five_cycle_backtrack_was_success = self.backtrack_5cycles(0)
            five_cycle_bt_timer.stop()
            if not self.five_cycle_backtrack_was_success:
                print(
                    "failed 5-cycle backtracking, number of leaves: " + str(self.five_cycle_backtrack_leaves))
            else:
                self.get_partial_model(self.solver)

    def backtrack_5cycles(self, five_cycle_index):
        bit_counter = 0
        var_vals = format(bit_counter, 'b')
        key_list = list(self.five_cycles.keys())
        five_cycle = self.five_cycles[key_list[five_cycle_index]]
        print("currently looking for assignment for " + five_cycle['id'])
        nodes = five_cycle['nodes']
        print(nodes)
        c_values = [frozenset({nodes[0], nodes[2]}), frozenset({nodes[1], nodes[3]}),
                    frozenset({nodes[2], nodes[4]}), frozenset({nodes[3], nodes[0]}),
                    frozenset({nodes[4], nodes[1]})]
        print(c_values)
        is_valid = False
        stop = False
        while not stop:
            print("####")
            print("debugging solver")
            old_asserts = self.solver.assertions.copy()
            new_asserts = self.solver.assertions.copy()
            print("  try finding assignment")
            for i, val in enumerate(reversed(var_vals)):
                if int(val) == 1:
                    new_asserts.append(self.domain_vars[c_values[i]])
                else:
                    new_asserts.append(Not(self.domain_vars[c_values[i]]))
            print("  bit string: " + var_vals)
            self.solver.reset_assertions()
            for assertion in new_asserts:
                self.solver.add_assertion(assertion)
            print(self.solver.solve())
            print("####")
            is_valid = self.solver.solve() and self.is_valid_important_cycle_c_assignment(nodes)
            # logging.debug("  old asserts: " + str(old_asserts))
            # logging.debug("  current asserts: " + str(new_asserts))
            # logging.debug("  solvable and valid: " + str(is_valid))
            if not is_valid and len(var_vals) <= 5:
                self.solver.reset_assertions()
                for assertion in old_asserts:
                    self.solver.add_assertion(assertion)
                self.solver.solve()
                self.five_cycle_backtrack_leaves += 1  # add a leaf for a unsat assignment
                bit_counter += 1
                var_vals = format(bit_counter, 'b')
                stop = len(var_vals) > 5
                continue
            five_cycle_index += 1
            if five_cycle_index < len(self.five_cycles):
                print("  next circle: " + str(self.five_cycles[key_list[five_cycle_index]]))
                is_valid = is_valid and self.backtrack_5cycles(five_cycle_index)
            else:
                self.five_cycle_backtrack_leaves += 1  # reached the last 5cycle, add a leaf
            bit_counter += 1
            var_vals = format(bit_counter, 'b')
            stop = is_valid or len(var_vals) > 5
        print("we reached the end. The result for " + str(five_cycle['id']) + " is " + str(is_valid))
        return is_valid

    def backtrack_all(self, big_cycles_free_vars, parent):
        print("building worst-case backtracking tree")
        print("currently looking for assignment for " + str(big_cycles_free_vars[0]))
        bit_counter = 0
        var_vals = format(bit_counter, 'b')
        big_cycle_vars = big_cycles_free_vars[1]
        big_cycle = self.big_cycles[big_cycles_free_vars[0]]
        nodes = big_cycle['nodes']
        is_valid = False
        stop = False
        while not stop:
            node_index = len(self.wc_bt_tree.nodes)
            self.wc_bt_tree.add_node(node_index, cycle_id=str(big_cycles_free_vars[0]), is_valid=False, is_leaf=False)
            self.wc_bt_tree.add_edge(parent, node_index)
            old_asserts = self.btt_solver.assertions.copy()
            new_asserts = self.btt_solver.assertions.copy()
            print("  trying assignment")
            for i, val in enumerate(reversed(var_vals)):
                if int(val) == 1:
                    big_cycle_vars[list(big_cycle_vars.keys())[i]] = True
                else:
                    big_cycle_vars[list(big_cycle_vars.keys())[i]] = False
            print("  bit string: " + var_vals)
            print("  big cycle vars: " + str(big_cycle_vars))
            for key in big_cycle_vars:
                if big_cycle_vars[key]:
                    new_asserts.append(key)
                else:
                    new_asserts.append(Not(key))
                self.btt_important_subgraph_vars.add(key)
            self.btt_solver.reset_assertions()
            for assertion in new_asserts:
                self.btt_solver.add_assertion(assertion)
            is_valid = self.btt_solver.solve() and self.is_valid_important_cycle_c_assignment(nodes, self.btt_solver)
            # logging.debug("  old asserts: " + str(old_asserts))
            # logging.debug("  current asserts: " + str(new_asserts))
            # logging.debug("  solvable and valid: " + str(is_valid))
            # Value assignment doesn't satisfy, and we haven't tried out all possible assignments
            if not is_valid and len(var_vals) <= len(list(big_cycle_vars.keys())):
                self.wc_bt_tree.nodes[node_index]['is_leaf'] = True
                self.btt_solver.reset_assertions()
                for assertion in old_asserts:
                    self.btt_solver.add_assertion(assertion)
                self.btt_solver.solve()
                bit_counter += 1
                var_vals = format(bit_counter, 'b')
                stop = len(var_vals) > len(list(big_cycle_vars.keys()))
                continue
            next_big_circle = self.get_big_cycle_with_min_free_vars(self.btt_important_subgraph_vars)
            print("  next circle: " + str(next_big_circle))
            if next_big_circle is None:
                self.wc_bt_tree.nodes[node_index]['is_leaf'] = True
                self.wc_bt_tree.nodes[node_index]['is_valid'] = is_valid
                self.btt_solver.reset_assertions()
                for assertion in old_asserts:
                    self.btt_solver.add_assertion(assertion)
                self.btt_solver.solve()
            else:
                self.backtrack_all(next_big_circle, node_index)
                is_valid = is_valid and self.has_valid_child(self.wc_bt_tree, node_index, self.wc_bt_tree[node_index])
                self.wc_bt_tree.nodes[node_index]['is_valid'] = is_valid
            bit_counter += 1
            var_vals = format(bit_counter, 'b')
            stop = len(var_vals) > len(list(big_cycle_vars.keys()))
        print("we reached the end for " + str(big_cycle_vars))
        return big_cycle_vars if is_valid else None

    def backtrack_big_cycle_c_assignments(self):
        if len(self.big_cycles) < 1:
            self.big_cycle_backtrack_was_success = True
            return
        root = self.get_big_cycle_with_min_free_vars()
        if root is None:
            self.big_cycle_backtrack_was_success = True
            return
        big_cycle_bt_timer.start()
        backtrack_result = self.backtrack(root)
        big_cycle_bt_timer.stop()
        if backtrack_result is not None:
            self.big_cycle_backtrack_was_success = True
        if not self.big_cycle_backtrack_was_success:
            print("number of leaves: " + str(self.big_cycle_backtrack_leaves))
            return
        print("number of leaves: " + str(self.big_cycle_backtrack_leaves))
        print("formula after successful backtrack: " + str(self.formula))
        print("model after successful backtrack:")
        self.get_partial_model(self.solver)

    def get_big_cycle_with_min_free_vars(self, _important_subgraph_vars=None):
        print("    finding cycle with least free vars...")
        big_cycles_free_vars = dict()
        for key in self.big_cycles:
            free_vars = self.get_free_c_vars_for_big_cycle(self.big_cycles[key], _important_subgraph_vars)
            if len(free_vars) > 0:
                big_cycles_free_vars[key] = free_vars
        sorted_big_cycles = sorted(big_cycles_free_vars.items(), key=lambda x: len(x[1]))
        print("      sorted big cycles: " + str(sorted_big_cycles))
        if len(sorted_big_cycles) < 1:
            return None
        return sorted_big_cycles[0]

    def get_free_c_vars_for_big_cycle(self, big_cycle, _important_subgraph_vars=None):
        if _important_subgraph_vars is None:
            _important_subgraph_vars = self.important_subgraph_vars
        c_vars = self.get_c_vars_for_big_cycle(big_cycle)
        big_cycle_vars = dict()
        if len(c_vars) < 1:
            return
        for c_var in c_vars:
            if c_var not in _important_subgraph_vars:
                big_cycle_vars[c_var] = False
        print("      big cycle free vars: " + str(big_cycle_vars))
        return big_cycle_vars

    def get_assigned_c_vars_for_big_cycle(self, big_cycle, _important_subgraph_vars=None):
        if _important_subgraph_vars is None:
            _important_subgraph_vars = self.important_subgraph_vars
        c_vars = self.get_c_vars_for_big_cycle(big_cycle)
        big_cycle_vars = dict()
        if len(c_vars) < 1:
            return
        for c_var in c_vars:
            if c_var in _important_subgraph_vars:
                big_cycle_vars[c_var] = False
        print("      big cycle free vars: " + str(big_cycle_vars))
        return big_cycle_vars

    def get_c_vars_for_big_cycle(self, big_cycle):
        c_vars = set()
        nodes = big_cycle['nodes']
        if len(nodes) < 5:
            print("big cycle with less than 5 nodes. something went wrong.")
            return c_vars
        c_vars.add(self.domain_vars[frozenset({nodes[0], nodes[-2]})])
        c_vars.add(self.domain_vars[frozenset({nodes[1], nodes[-1]})])
        for i in range(2, len(nodes)):
            c_vars.add(self.domain_vars[frozenset({nodes[i - 2], nodes[i]})])
        return c_vars

    def backtrack(self, big_cycles_free_vars):
        print("backtrack")
        print("currently looking for assignment for " + str(big_cycles_free_vars[0]))
        bit_counter = 0
        var_vals = format(bit_counter, 'b')
        big_cycle_vars = big_cycles_free_vars[1]
        big_cycle = self.big_cycles[big_cycles_free_vars[0]]
        nodes = big_cycle['nodes']
        is_valid = False
        stop = False
        while not stop:
            old_asserts = self.solver.assertions.copy()
            new_asserts = self.solver.assertions.copy()
            print("  try finding assignment")
            for i, val in enumerate(reversed(var_vals)):
                if int(val) == 1:
                    big_cycle_vars[list(big_cycle_vars.keys())[i]] = True
                else:
                    big_cycle_vars[list(big_cycle_vars.keys())[i]] = False
            print("  bit string: " + var_vals)
            print("  big cycle vars: " + str(big_cycle_vars))
            for key in big_cycle_vars:
                if big_cycle_vars[key]:
                    new_asserts.append(key)
                else:
                    new_asserts.append(Not(key))
                self.important_subgraph_vars.add(key)
            self.solver.reset_assertions()
            for assertion in new_asserts:
                self.solver.add_assertion(assertion)
            is_valid = self.solver.solve() and self.is_valid_important_cycle_c_assignment(nodes)
            # logging.debug("  old asserts: " + str(old_asserts))
            # logging.debug("  current asserts: " + str(new_asserts))
            # logging.debug("  solvable and valid: " + str(is_valid))
            if not is_valid and len(var_vals) <= len(list(big_cycle_vars.keys())):
                self.solver.reset_assertions()
                for assertion in old_asserts:
                    self.solver.add_assertion(assertion)
                self.solver.solve()
                self.big_cycle_backtrack_leaves += 1  # add a leaf for an unsat assignment
                bit_counter += 1
                var_vals = format(bit_counter, 'b')
                stop = len(var_vals) > len(list(big_cycle_vars.keys()))
                continue
            next_big_circle = self.get_big_cycle_with_min_free_vars()
            print("  next circle: " + str(next_big_circle))
            if next_big_circle is None:
                self.big_cycle_backtrack_leaves += 1  # add a leaf for reaching the last big cycle
            else:
                is_valid = is_valid and self.backtrack(next_big_circle) is not None
            bit_counter += 1
            var_vals = format(bit_counter, 'b')
            stop = len(var_vals) > len(list(big_cycle_vars.keys())) or is_valid
        print("we reached the end. The result for " + str(big_cycle_vars) + " is " + str(is_valid))
        return big_cycle_vars if is_valid else None

    def get_c_domain(self):
        self.c_domain = set()
        self.domain_vars = dict()
        self.important_subgraph_vars = set()
        for i in self.c_graph.nodes:
            node_i = self.c_graph.nodes[i]
            r_nh_i = get_all_neighbors(self.c_graph, node_i)
            for node_n in r_nh_i:
                nh_n = get_all_neighbors(self.c_graph, node_n)
                for node_j in nh_n:
                    if node_j['label'] != node_i['label'] and not are_crossing_chords(node_i, node_j):
                        self.c_domain.add(frozenset({node_i['label'], node_j['label']}))
        for c in self.c_domain:
            c_str = ', '.join(str(i) for i in list(c))
            self.domain_vars[c] = Symbol(c_str)

    def clauses_for_tailtriangle(self):
        clauses = set()
        for tailtriangle in self.tailtriangles:
            left_nh = tailtriangle['left_nh']
            right_nh = tailtriangle['right_nh']
            if not (len(left_nh) == 1 and len(right_nh) == 2):
                print("tailtriangle format is wrong")
                continue
            key_02 = frozenset({left_nh[0], right_nh[0]})
            key_not_02 = frozenset({'not'}).union(key_02)
            key_03 = frozenset({left_nh[0], right_nh[1]})
            key_not_03 = frozenset({'not'}).union(key_03)
            c_02 = self.domain_vars[key_02]  # c*(v_0, v_2)
            c_03 = self.domain_vars[key_03]  # c*(v_0, v_3)
            self.important_subgraph_vars.add(c_02)
            self.important_subgraph_vars.add(c_03)
            clauses.add(Or(c_02, c_03))
            if key_02 not in self.sat_graph_dict:
                self.add_var_to_sat_graph(key_02, c_02)
            if key_03 not in self.sat_graph_dict:
                self.add_var_to_sat_graph(key_03, c_03)
            self.sat_graph.add_edge(self.sat_graph_dict[key_not_02], self.sat_graph_dict[key_03])
            self.sat_graph.add_edge(self.sat_graph_dict[key_not_03], self.sat_graph_dict[key_02])
            clauses.add(Or(Not(c_02), Not(c_03)))
            self.sat_graph.add_edge(self.sat_graph_dict[key_02], self.sat_graph_dict[key_not_03])
            self.sat_graph.add_edge(self.sat_graph_dict[key_03], self.sat_graph_dict[key_not_02])
        # print("tailtriangle clauses: " + str(clauses))
        return clauses

    def add_var_to_sat_graph(self, key, var):
        new_node = len(self.sat_graph.nodes)
        self.sat_graph_dict[key] = new_node
        self.sat_graph.add_node(new_node, c_var=var)
        self.sat_graph_dict[self.var_not.union(key)] = new_node + 1
        self.sat_graph.add_node(new_node + 1, c_var=Not(var))

    def clauses_for_boxslash(self):
        clauses = set()
        for boxslash in self.boxslashes:
            opposites = boxslash['opposites']
            if not len(opposites) == 2:
                print("format for boxslash is wrong")
                continue
            c_02 = self.domain_vars[frozenset({opposites[0], opposites[1]})]  # c*(v_0, v_2)
            clauses.add(c_02)
            self.important_subgraph_vars.add(c_02)
        # print("boxslash clauses: " + str(clauses))
        return clauses

    def clauses_for_4cycle(self):
        clauses = set()
        for four_cycle in self.four_cycles:
            opposites_1 = four_cycle['opposites1']
            opposites_2 = four_cycle['opposites2']
            if not len(opposites_1) == 2 or not len(opposites_2) == 2:
                print("format for 4 cycle is wrong")
                continue
            key_c_02 = frozenset({opposites_1[0], opposites_1[1]})
            key_not_c_02 = frozenset({'not'}).union(key_c_02)
            key_c_13 = frozenset({opposites_2[0], opposites_2[1]})
            key_not_c_13 = frozenset({'not'}).union(key_c_13)
            c_02 = self.domain_vars[key_c_02]  # c*(v_0, v_2)
            c_13 = self.domain_vars[key_c_13]  # c*(v_1, v_3)
            self.important_subgraph_vars.add(c_02)
            self.important_subgraph_vars.add(c_13)
            clauses.add(Or(c_02, c_13))
            if key_c_02 not in self.sat_graph_dict:
                self.add_var_to_sat_graph(key_c_02, c_02)
            if key_c_13 not in self.sat_graph_dict:
                self.add_var_to_sat_graph(key_c_13, c_13)
            self.sat_graph.add_edge(self.sat_graph_dict[key_not_c_02], self.sat_graph_dict[key_c_13])
            self.sat_graph.add_edge(self.sat_graph_dict[key_not_c_13], self.sat_graph_dict[key_c_02])
        # print("squares clauses: " + str(clauses))
        return clauses

    def cnf_clauses_for_5cycle(self):
        clauses = set()
        for key in self.five_cycles:
            five_cycle = self.five_cycles[key]
            nodes = five_cycle['nodes']
            if not len(nodes) == 5:
                print("5 cycles with not 5 nodes, something went wrong")
                continue
            for i in range(0, len(nodes)):
                j = (i + 2) % 5
                k = (i + 3) % 5
                key_c_ij = frozenset({nodes[i], nodes[j]})
                key_not_c_ij = frozenset({'not'}).union(key_c_ij)
                key_c_ik = frozenset({nodes[i], nodes[k]})
                key_not_c_ik = frozenset({'not'}).union(key_c_ik)
                c_ij = self.domain_vars[key_c_ij]  # c*(v_i, v_j)
                c_ik = self.domain_vars[key_c_ik]  # c*(v_i, v_j')
                self.important_subgraph_vars.add(c_ij)
                self.important_subgraph_vars.add(c_ik)
                clauses.add(Or(Not(c_ij), Not(c_ik)))
                if key_c_ij not in self.sat_graph_dict:
                    self.add_var_to_sat_graph(key_c_ij, c_ij)
                if key_c_ik not in self.sat_graph_dict:
                    self.add_var_to_sat_graph(key_c_ik, c_ik)
                self.sat_graph.add_edge(self.sat_graph_dict[key_c_ij], self.sat_graph_dict[key_not_c_ik])
                self.sat_graph.add_edge(self.sat_graph_dict[key_c_ik], self.sat_graph_dict[key_not_c_ij])
        # print("pent CNF clauses: " + str(clauses))
        return clauses

    def dnf_clauses_for_5cycle(self):  # returns one big or-clause (DNF)
        clauses = set()
        for key in self.five_cycles:
            curr_clauses = []
            five_cycle = self.five_cycles[key]
            nodes = five_cycle['nodes']
            if not len(nodes) == 5:
                print("5 cycles with not 5 nodes, something went wrong")
                continue
            relevant_c_vars = [frozenset({nodes[0], nodes[2]}), frozenset({nodes[1], nodes[3]}),
                               frozenset({nodes[2], nodes[4]}), frozenset({nodes[3], nodes[0]}),
                               frozenset({nodes[4], nodes[1]})]
            curr_clauses.append(And(self.domain_vars[relevant_c_vars[0]], self.domain_vars[relevant_c_vars[1]],
                                    Not(self.domain_vars[relevant_c_vars[2]]),
                                    Not(self.domain_vars[relevant_c_vars[3]]),
                                    Not(self.domain_vars[relevant_c_vars[4]])))
            curr_clauses.append(And(self.domain_vars[relevant_c_vars[0]], Not(self.domain_vars[relevant_c_vars[1]]),
                                    self.domain_vars[relevant_c_vars[2]], Not(self.domain_vars[relevant_c_vars[3]]),
                                    Not(self.domain_vars[relevant_c_vars[4]])))
            curr_clauses.append(And(self.domain_vars[relevant_c_vars[0]], Not(self.domain_vars[relevant_c_vars[1]]),
                                    Not(self.domain_vars[relevant_c_vars[2]]), self.domain_vars[relevant_c_vars[3]],
                                    Not(self.domain_vars[relevant_c_vars[4]])))
            curr_clauses.append(And(self.domain_vars[relevant_c_vars[0]], Not(self.domain_vars[relevant_c_vars[1]]),
                                    Not(self.domain_vars[relevant_c_vars[2]]),
                                    Not(self.domain_vars[relevant_c_vars[3]]),
                                    self.domain_vars[relevant_c_vars[4]]))
            curr_clauses.append(And(Not(self.domain_vars[relevant_c_vars[0]]), self.domain_vars[relevant_c_vars[1]],
                                    self.domain_vars[relevant_c_vars[2]], Not(self.domain_vars[relevant_c_vars[3]]),
                                    Not(self.domain_vars[relevant_c_vars[4]])))
            curr_clauses.append(And(Not(self.domain_vars[relevant_c_vars[0]]), self.domain_vars[relevant_c_vars[1]],
                                    Not(self.domain_vars[relevant_c_vars[2]]), self.domain_vars[relevant_c_vars[3]],
                                    Not(self.domain_vars[relevant_c_vars[4]])))
            curr_clauses.append(And(Not(self.domain_vars[relevant_c_vars[0]]), self.domain_vars[relevant_c_vars[1]],
                                    Not(self.domain_vars[relevant_c_vars[2]]),
                                    Not(self.domain_vars[relevant_c_vars[3]]),
                                    self.domain_vars[relevant_c_vars[4]]))
            curr_clauses.append(
                And(Not(self.domain_vars[relevant_c_vars[0]]), Not(self.domain_vars[relevant_c_vars[1]]),
                    self.domain_vars[relevant_c_vars[2]], self.domain_vars[relevant_c_vars[3]],
                    Not(self.domain_vars[relevant_c_vars[4]])))
            curr_clauses.append(
                And(Not(self.domain_vars[relevant_c_vars[0]]), Not(self.domain_vars[relevant_c_vars[1]]),
                    self.domain_vars[relevant_c_vars[2]], Not(self.domain_vars[relevant_c_vars[3]]),
                    self.domain_vars[relevant_c_vars[4]]))
            curr_clauses.append(
                And(Not(self.domain_vars[relevant_c_vars[0]]), Not(self.domain_vars[relevant_c_vars[1]]),
                    Not(self.domain_vars[relevant_c_vars[2]]), self.domain_vars[relevant_c_vars[3]],
                    self.domain_vars[relevant_c_vars[4]]))
            clauses.add(Or(*curr_clauses))
        # print("pent DNF clauses: " + str(clauses))
        return clauses

    def clauses_for_five_and_big_cycles(self):
        clauses = []
        for key in self.five_cycles:
            clauses.append(self.clauses_for_big_cycle(self.five_cycles[key]))
        clauses_s = set([c for clause_list in clauses for c in clause_list])
        clauses_s = clauses_s.union(self.clauses_for_big_cycles())
        return clauses_s

    def clauses_for_big_cycles(self):
        clauses = []
        for key in self.big_cycles:
            clauses.append(self.clauses_for_big_cycle(self.big_cycles[key]))
        return set([c for clause_list in clauses for c in clause_list])

    def clauses_for_big_cycle(self, big_cycle):
        clauses = []
        aux_symbols = {}
        nodes = big_cycle['nodes']
        if len(nodes) < 5:
            print("big cycle with less than 5 nodes, something went wrong")
            return
        for i in range(1, len(nodes)):
            aux_symbols[frozenset({nodes[0], nodes[i]})] = Symbol(f"{big_cycle['id']}({nodes[0]},{nodes[i]})")
            if i == 1:
                continue
            aux_symbols[frozenset({nodes[1], nodes[i]})] = Symbol(f"{big_cycle['id']}({nodes[1]},{nodes[i]})")
        clauses.append(Not(aux_symbols[frozenset({nodes[0], nodes[1]})]))
        clauses.append(Not(aux_symbols[frozenset({nodes[1], nodes[2]})]))
        clauses.append(Not(aux_symbols[frozenset({nodes[0], nodes[len(nodes) - 1]})]))

        key_c_02 = frozenset({nodes[0], nodes[2]})
        c_02 = self.domain_vars[key_c_02]
        self.big_cycle_var_keys.add(key_c_02)
        self.big_cycle_var_keys.add(self.var_not.union(key_c_02))
        if key_c_02 not in self.sat_graph_dict:
            self.add_var_to_sat_graph(key_c_02, c_02)
        clauses.append(EqualsOrIff(aux_symbols[frozenset({nodes[0], nodes[2]})], c_02))

        key_c_13 = frozenset({nodes[1], nodes[3]})
        c_13 = self.domain_vars[key_c_13]
        self.big_cycle_var_keys.add(key_c_13)
        self.big_cycle_var_keys.add(self.var_not.union(key_c_13))
        if key_c_13 not in self.sat_graph_dict:
            self.add_var_to_sat_graph(key_c_13, c_13)
        clauses.append(EqualsOrIff(aux_symbols[frozenset({nodes[1], nodes[3]})], c_13))

        key_c_0x = frozenset({nodes[0], nodes[len(nodes) - 2]})
        c_0x = self.domain_vars[key_c_0x]
        self.big_cycle_var_keys.add(key_c_0x)
        self.big_cycle_var_keys.add(self.var_not.union(key_c_0x))
        if key_c_0x not in self.sat_graph_dict:
            self.add_var_to_sat_graph(key_c_0x, c_0x)
        clauses.append(EqualsOrIff(aux_symbols[frozenset({nodes[0], nodes[len(nodes) - 2]})], c_0x))

        key_c_1y = frozenset({nodes[1], nodes[len(nodes) - 1]})
        c_1y = self.domain_vars[key_c_1y]
        self.big_cycle_var_keys.add(key_c_1y)
        self.big_cycle_var_keys.add(self.var_not.union(key_c_1y))
        if key_c_1y not in self.sat_graph_dict:
            self.add_var_to_sat_graph(key_c_1y, c_1y)
        clauses.append(EqualsOrIff(aux_symbols[frozenset({nodes[1], nodes[len(nodes) - 1]})], c_1y))

        for i in range(3, len(nodes)):
            key_c_i = frozenset({nodes[i - 2], nodes[i]})
            c_i = self.domain_vars[key_c_i]
            self.big_cycle_var_keys.add(key_c_i)
            self.big_cycle_var_keys.add(self.var_not.union(key_c_i))
            if key_c_i not in self.sat_graph_dict:
                self.add_var_to_sat_graph(key_c_i, c_i)
            clauses.append(And(Implies(c_i, EqualsOrIff(aux_symbols[frozenset({nodes[0], nodes[i]})],
                                                        aux_symbols[frozenset({nodes[0], nodes[i - 2]})])),
                               Implies(Not(c_i), EqualsOrIff(aux_symbols[frozenset({nodes[0], nodes[i]})],
                                                             And(Not(
                                                                 aux_symbols[frozenset({nodes[0], nodes[i - 2]})]),
                                                                 Not(aux_symbols[
                                                                         frozenset({nodes[0], nodes[i - 1]})]))))))
            if i == 3:
                continue
            clauses.append(And(Implies(c_i, EqualsOrIff(aux_symbols[frozenset({nodes[1], nodes[i]})],
                                                        aux_symbols[frozenset({nodes[1], nodes[i - 2]})])),
                               Implies(Not(c_i), EqualsOrIff(aux_symbols[frozenset({nodes[1], nodes[i]})],
                                                             And(Not(
                                                                 aux_symbols[frozenset({nodes[1], nodes[i - 2]})]),
                                                                 Not(aux_symbols[
                                                                         frozenset({nodes[1], nodes[i - 1]})]))))))
        return clauses

    def has_valid_child(self, c_graph, node_index, children):
        for c in children:
            if c < node_index:
                continue
            if c_graph.nodes[c]['is_valid']:
                return True
        return False

    def is_valid_important_cycle_c_assignment(self, nodes, _solver=solver):
        if self.check_if_cycle_has_no_free_vars(nodes) is not True:
            return None
        print("    validating important cycle c assignment...")
        h_values = [[False for _ in range(len(nodes))] for _ in range(2)]
        # logging.debug("      node 0: " + str(nodes[0]))
        # logging.debug("      node 1: " + str(nodes[1]))
        h_values[0][2] = self.get_c_value(nodes[0], nodes[2], _solver)
        h_values[1][3] = self.get_c_value(nodes[1], nodes[3], _solver)
        for i in range(2):
            for j in range(i + 3, len(nodes)):
                c_val_j = self.get_c_value(nodes[j], nodes[j - 2], _solver)
                if c_val_j:
                    h_values[i][j] = h_values[i][j - 2]
                else:
                    h_values[i][j] = not h_values[i][j - 2] and not h_values[i][j - 1]
        # logging.debug("      h: " + str(h_values))
        # logging.debug("      c*(0, l-1): " + str(self.get_c_value(nodes[0], nodes[len(nodes) - 2], _solver)))
        # logging.debug("      c*(1, l): " + str(self.get_c_value(nodes[1], nodes[len(nodes) - 1], _solver)))
        result = (not h_values[0][len(nodes) - 1]) and h_values[0][len(nodes) - 2] == self.get_c_value(nodes[0], nodes[
            len(nodes) - 2], _solver) and h_values[1][len(nodes) - 1] == self.get_c_value(
            nodes[1], nodes[len(nodes) - 1], _solver)
        print("      result: " + str(result))
        return result

    def check_if_cycle_has_no_free_vars(self, nodes):
        print("    checking if there's still free variables left for the cycle...")
        if self.domain_vars[frozenset({nodes[0], nodes[2]})] not in self.important_subgraph_vars:
            return False
        if self.domain_vars[frozenset({nodes[1], nodes[3]})] not in self.important_subgraph_vars:
            return False
        for i in range(2):
            for j in range(i + 3, len(nodes)):
                if self.domain_vars[frozenset({nodes[j], nodes[j - 2]})] not in self.important_subgraph_vars:
                    return False
        return True

    def get_c_value(self, a, b, _solver=solver):
        return _solver.get_py_value(self.domain_vars[frozenset({a, b})])

    def solve_sat(self, _solver, timed=True):
        if timed:
            solving_c_timer.start()
            can_solve = _solver.solve()
            solving_c_timer.stop()
        else:
            can_solve = _solver.solve()
        print("solver result: " + str(can_solve))
        if can_solve:
            # self.get_partial_model(_solver)
            # self.get_all_models()
            self.is_three_colorable = True
        else:
            print("no SAT solution found")
            print("unsat core: " + self.get_unsat_core_str())
            self.is_three_colorable = False

    def get_unsat_core_str(self):
        clauses = self.tailtriangle_clauses | self.boxslash_clauses | self.four_cycle_clauses | self.five_cycle_cnf_clauses | self.five_cycle_dnf_clauses | self.big_cycle_clauses
        return str(get_unsat_core(clauses))

    def get_all_models(self, solver):
        while solver.solve():
            partial_model = self.get_partial_model(solver)
            self.solver.add_assertion(Not(And(partial_model)))

    def get_partial_model(self, solver):
        partial_model = [EqualsOrIff(self.domain_vars[c], solver.get_value(self.domain_vars[c])) for c in
                         self.c_domain]
        # print("partial model: " + str(partial_model))
        return partial_model

    def add_partial_model(self, partial_model):
        self.solver.add_assertion(Not(And(partial_model)))

    def get_some_model(self):
        model = get_model(self.formula)
        if model:
            print("some model: " + str(model))
        else:
            print("No solution found")

    def set_values_for_counterexample(self):
        self.solver.add_assertion(Not(self.domain_vars[frozenset({8, 10})]))
        self.solver.add_assertion(self.domain_vars[frozenset({8, 1})])
        self.solver.add_assertion(self.domain_vars[frozenset({8, 5})])
        self.solver.add_assertion(self.domain_vars[frozenset({0, 10})])
        print("set values for counterexample")
        if self.solver.solve():
            self.get_partial_model(self.solver)
            self.is_three_colorable = True
        else:
            print("no solution found")
            self.is_three_colorable = False

    def set_values_for_small_counterexample(self):
        self.solver.add_assertion(Not(self.domain_vars[frozenset({0, 3})]))
        self.solver.add_assertion(self.domain_vars[frozenset({0, 6})])
        self.solver.add_assertion(self.domain_vars[frozenset({4, 5})])
        self.solver.add_assertion(self.domain_vars[frozenset({2, 6})])
        self.solver.add_assertion(self.domain_vars[frozenset({1, 3})])
        self.solver.add_assertion(self.domain_vars[frozenset({2, 4})])
        self.solver.add_assertion(Not(self.domain_vars[frozenset({0, 2})]))
        self.solver.add_assertion(Not(self.domain_vars[frozenset({1, 4})]))
