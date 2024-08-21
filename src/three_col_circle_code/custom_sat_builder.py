import itertools
import time

from three_col_circle_code.util import *
from three_col_circle_code.timer import Timer


class CustomSatBuilder:
    c_graph = nx.Graph()
    implication_graph = nx.DiGraph()
    impl_graph_dict = dict()
    tailtriangles = []
    boxslashes = []
    four_cycles = []
    five_cycles = []
    big_cycles = []
    big_cycle_vars = set()
    assignment = dict()
    small_clauses = set()
    large_clauses = set()
    var_not = frozenset({"not"})
    aux_symbol = frozenset({"aux"})
    bt_tree = nx.DiGraph()
    current_node = 0
    leaves = 0
    to_assign = []
    finished_in_time = True
    timer = time.time()
    contradiction_timer = Timer(name="contradiction", text="Finding a contradiction took {:0.6f} seconds")

    def __init__(self, c_graph, important_subgraphs):
        self.c_graph = c_graph
        self.implication_graph = nx.DiGraph()
        self.impl_graph_dict = dict()
        self.assignment = dict()
        self.tailtriangles = important_subgraphs[TAILTRIANGLE_STR]
        self.boxslashes = important_subgraphs.get(BOXSLASH_STR)
        self.four_cycles = important_subgraphs.get(FOUR_CYCLE_STR)
        self.five_cycles = important_subgraphs.get(FIVE_CYCLE_STR)
        self.big_cycles = important_subgraphs.get(BIG_CYCLE_STR)
        self.big_cycle_vars = set()
        self.small_clauses = set()
        self.large_clauses = set()
        self.build_clauses()
        self.bt_tree = nx.DiGraph()
        self.current_node = 0
        self.leaves = 0
        self.to_assign = []
        self.finished_in_time = True
        self.timer = time.time()
        self.contradiction_timer = Timer(name="contradiction", text="Finding a contradiction took {:0.6f} seconds")

    def build_clauses(self):
        print("initial big cycle vars:", self.big_cycle_vars.copy())
        for tailtriangle in self.tailtriangles:
            self.clauses_for_tailtriangle(tailtriangle)
        for boxslash in self.boxslashes:
            self.clauses_for_boxslash(boxslash)
        for four_cycle in self.four_cycles:
            self.clauses_for_4cycle(four_cycle)
        for key in self.five_cycles:
            five_cycle = self.five_cycles[key]
            self.small_clauses_for_5cycle(five_cycle)
            self.large_clauses_for_cycle(self.five_cycles[key])
        for key in self.big_cycles:
            self.large_clauses_for_cycle(self.big_cycles[key])
        self.add_implications_to_clauses()

    def clauses_for_tailtriangle(self, tailtriangle):
        left_nh = tailtriangle['left_nh']
        right_nh = tailtriangle['right_nh']
        if not (len(left_nh) == 1 and len(right_nh) == 2):
            print("tailtriangle format is wrong")
            return
        c_02 = frozenset({left_nh[0], right_nh[0]})
        c_not_02 = self.var_not.union(c_02)
        c_03 = frozenset({left_nh[0], right_nh[1]})
        c_not_03 = self.var_not.union(c_03)
        if c_02 not in self.impl_graph_dict:
            self.init_var(c_02)
        if c_03 not in self.impl_graph_dict:
            self.init_var(c_03)
        self.small_clauses.add(frozenset({c_02, c_03}))
        self.implication_graph.add_edge(self.impl_graph_dict[c_not_02], self.impl_graph_dict[c_03])
        self.implication_graph.add_edge(self.impl_graph_dict[c_not_03], self.impl_graph_dict[c_02])
        self.small_clauses.add(frozenset({c_not_02, c_not_03}))
        self.implication_graph.add_edge(self.impl_graph_dict[c_02], self.impl_graph_dict[c_not_03])
        self.implication_graph.add_edge(self.impl_graph_dict[c_03], self.impl_graph_dict[c_not_02])

    def clauses_for_boxslash(self, boxslash):
        opposites = boxslash['opposites']
        if not len(opposites) == 2:
            print("format for boxslash is wrong")
            return
        c_02 = frozenset({opposites[0], opposites[1]})
        c_not_02 = self.var_not.union(c_02)
        self.small_clauses.add(frozenset({c_02}))
        if c_02 not in self.impl_graph_dict:
            self.init_var(c_02)
        self.implication_graph.add_edge(self.impl_graph_dict[c_not_02], self.impl_graph_dict[c_02])

    def clauses_for_4cycle(self, four_cycle):
        opposites_1 = four_cycle['opposites1']
        opposites_2 = four_cycle['opposites2']
        if not len(opposites_1) == 2 or not len(opposites_2) == 2:
            print("format for 4 cycle is wrong")
            return
        c_02 = frozenset({opposites_1[0], opposites_1[1]})
        c_not_02 = self.var_not.union(c_02)
        c_13 = frozenset({opposites_2[0], opposites_2[1]})
        c_not_13 = self.var_not.union(c_13)
        self.small_clauses.add(frozenset({c_02, c_13}))
        if c_02 not in self.impl_graph_dict:
            self.init_var(c_02)
        if c_13 not in self.impl_graph_dict:
            self.init_var(c_13)
        self.implication_graph.add_edge(self.impl_graph_dict[c_not_02], self.impl_graph_dict[c_13])
        self.implication_graph.add_edge(self.impl_graph_dict[c_not_13], self.impl_graph_dict[c_02])

    def small_clauses_for_5cycle(self, five_cycle):
        nodes = five_cycle['nodes']
        if not len(nodes) == 5:
            print("5 cycles with not 5 nodes, something went wrong")
            return
        for i in range(0, len(nodes)):
            j = (i + 2) % 5
            k = (i + 3) % 5
            c_ij = frozenset({nodes[i], nodes[j]})
            c_not_ij = self.var_not.union(c_ij)
            c_ik = frozenset({nodes[i], nodes[k]})
            c_not_ik = self.var_not.union(c_ik)
            self.small_clauses.add(frozenset({c_not_ij, c_not_ik}))
            if c_ij not in self.impl_graph_dict:
                self.init_var(c_ij)
            if c_ik not in self.impl_graph_dict:
                self.init_var(c_ik)
            self.implication_graph.add_edge(self.impl_graph_dict[c_ij], self.impl_graph_dict[c_not_ik])
            self.implication_graph.add_edge(self.impl_graph_dict[c_ik], self.impl_graph_dict[c_not_ij])

    def large_clauses_for_cycle(self, big_cycle):
        nodes = big_cycle['nodes']
        if len(nodes) < 5:
            print("big cycle with less than 5 nodes, something went wrong")
            return
        not_aux_01 = self.var_not.union(self.aux_symbol.union(frozenset({nodes[0], nodes[1]})))
        self.assignment[not_aux_01.difference(self.var_not)] = None
        self.small_clauses.add(frozenset({not_aux_01}))
        not_aux_12 = self.var_not.union(self.aux_symbol.union(frozenset({nodes[1], nodes[2]})))
        self.assignment[not_aux_12.difference(self.var_not)] = None
        self.small_clauses.add(frozenset({not_aux_12}))
        not_aux_0l = self.var_not.union(self.aux_symbol.union(frozenset({nodes[0], nodes[len(nodes) - 1]})))
        self.assignment[not_aux_0l.difference(self.var_not)] = None
        self.small_clauses.add(frozenset({not_aux_0l}))

        c_02 = frozenset({nodes[0], nodes[2]})
        self.big_cycle_vars.add(c_02)
        self.init_var(c_02)
        not_c_02 = self.var_not.union(c_02)
        aux_02 = self.aux_symbol.union(c_02)
        self.assignment[aux_02] = None
        not_aux_02 = self.var_not.union(aux_02)
        self.small_clauses.add(frozenset({not_aux_02, c_02}))
        self.small_clauses.add(frozenset({aux_02, not_c_02}))

        c_13 = frozenset({nodes[1], nodes[3]})
        self.big_cycle_vars.add(c_13)
        self.init_var(c_13)
        not_c_13 = self.var_not.union(c_13)
        aux_13 = self.aux_symbol.union(c_13)
        self.assignment[aux_13] = None
        not_aux_13 = self.var_not.union(aux_13)
        self.small_clauses.add(frozenset({not_aux_13, c_13}))
        self.small_clauses.add(frozenset({aux_13, not_c_13}))

        c_0x = frozenset({nodes[0], nodes[len(nodes) - 2]})
        self.big_cycle_vars.add(c_0x)
        self.init_var(c_0x)
        not_c_0x = self.var_not.union(c_0x)
        aux_0x = self.aux_symbol.union(c_0x)
        self.assignment[aux_0x] = None
        not_aux_0x = self.var_not.union(aux_0x)
        self.small_clauses.add(frozenset({not_aux_0x, c_0x}))
        self.small_clauses.add(frozenset({aux_0x, not_c_0x}))

        c_1y = frozenset({nodes[1], nodes[len(nodes) - 1]})
        self.big_cycle_vars.add(c_1y)
        self.init_var(c_1y)
        not_c_1y = self.var_not.union(c_1y)
        aux_1y = self.aux_symbol.union(c_1y)
        self.assignment[aux_1y] = None
        not_aux_1y = self.var_not.union(aux_1y)
        self.small_clauses.add(frozenset({not_aux_1y, c_1y}))
        self.small_clauses.add(frozenset({aux_1y, not_c_1y}))

        for i in range(3, len(nodes)):
            c_i = frozenset({nodes[i - 2], nodes[i]})
            self.big_cycle_vars.add(c_i)
            self.init_var(c_i)
            not_c_i = self.var_not.union(c_i)
            aux_0i = self.aux_symbol.union(frozenset({nodes[0], nodes[i]}))
            self.assignment[aux_0i] = None
            not_aux_0i = self.var_not.union(aux_0i)
            aux_0i1 = self.aux_symbol.union(frozenset({nodes[0], nodes[i - 1]}))
            self.assignment[aux_0i1] = None
            not_aux_0i1 = self.var_not.union(aux_0i1)
            aux_0i2 = self.aux_symbol.union(frozenset({nodes[0], nodes[i - 2]}))
            self.assignment[aux_0i2] = None
            not_aux_0i2 = self.var_not.union(aux_0i2)
            self.large_clauses.add(frozenset({not_c_i, not_aux_0i, aux_0i2}))  # (1)
            self.large_clauses.add(frozenset({not_c_i, aux_0i, not_aux_0i2}))  # (1)
            self.large_clauses.add(frozenset({c_i, not_aux_0i, not_aux_0i2}))  # (2)
            self.large_clauses.add(frozenset({c_i, not_aux_0i, not_aux_0i1}))  # (2)
            self.large_clauses.add(frozenset({c_i, aux_0i, aux_0i2, aux_0i1}))  # (2)

            if i == 3:
                continue

            aux_1i = self.aux_symbol.union(frozenset({nodes[1], nodes[i]}))
            self.assignment[aux_1i] = None
            not_aux_1i = self.var_not.union(aux_1i)
            aux_1i1 = self.aux_symbol.union(frozenset({nodes[1], nodes[i - 1]}))
            self.assignment[aux_1i1] = None
            not_aux_1i1 = self.var_not.union(aux_1i1)
            aux_1i2 = self.aux_symbol.union(frozenset({nodes[1], nodes[i - 2]}))
            self.assignment[aux_1i2] = None
            not_aux_1i2 = self.var_not.union(aux_1i2)
            self.large_clauses.add(frozenset({not_c_i, not_aux_1i, aux_1i2}))  # (1)
            self.large_clauses.add(frozenset({not_c_i, aux_1i, not_aux_1i2}))  # (1)
            self.large_clauses.add(frozenset({c_i, not_aux_1i, not_aux_1i2}))  # (2)
            self.large_clauses.add(frozenset({c_i, not_aux_1i, not_aux_1i1}))  # (2)
            self.large_clauses.add(frozenset({c_i, aux_1i, aux_1i2, aux_1i1}))  # (2)

    def init_var(self, key):
        if key in self.impl_graph_dict:
            return
        self.assignment[key] = None
        new_node = len(self.implication_graph.nodes)
        self.impl_graph_dict[key] = new_node
        self.implication_graph.add_node(new_node)
        self.impl_graph_dict[self.var_not.union(key)] = new_node + 1
        self.implication_graph.add_node(new_node + 1)

    def add_implications_to_clauses(self):
        # for each variable of big cycle find all reachable variables in implication graph
        implications = dict()
        for key in self.big_cycle_vars:
            implications_for_bc_vars = [i for i in nx.descendants(self.implication_graph, self.impl_graph_dict[key]) if
                                        self.get_var_from_impl_graph(i) in self.big_cycle_vars]
            if len(implications_for_bc_vars) > 0:
                implications[key] = implications_for_bc_vars
            not_key = self.var_not.union(key)
            implications_for_bc_vars = [i for i in nx.descendants(self.implication_graph, self.impl_graph_dict[not_key])
                                        if self.get_var_from_impl_graph(i) in self.big_cycle_vars]
            if len(implications_for_bc_vars) > 0:
                implications[not_key] = implications_for_bc_vars
        for key in implications:
            for implied in implications[key]:
                if len(key.intersection(self.var_not)) > 0:
                    implies = key.difference(self.var_not)
                else:
                    implies = key.union(self.var_not)
                self.small_clauses.add(frozenset({implies, self.get_var_from_impl_graph(implied)}))

    def get_var_from_impl_graph(self, n):
        return list(self.impl_graph_dict.keys())[list(self.impl_graph_dict.values()).index(n)]

    def solve_small_clauses(self):
        scc = list(nx.strongly_connected_components(self.implication_graph))
        for component in scc:
            for vertex in component:
                var = self.get_var_from_impl_graph(vertex)
                if self.impl_graph_dict[var.difference(self.var_not)] in component and self.impl_graph_dict[
                    var.union(self.var_not)] in component:
                    print("conflicting component:", component)
                    return False
        condensed = nx.condensation(self.implication_graph, scc=scc)
        for component in reversed(list(nx.topological_sort(condensed))):
            for vertex in condensed.nodes[component]['members']:
                var = self.get_var_from_impl_graph(vertex)
                if self.assignment[var.difference(self.var_not)] is not None:
                    continue
                if len(self.var_not.intersection(var)) > 0:
                    self.assignment[var.difference(self.var_not)] = False
                else:
                    self.assignment[var.difference(self.var_not)] = True
        return True

    def print_small_clauses(self):
        literal_strings = []
        for clause in self.small_clauses:
            literal_string = ""
            literals = list(clause)
            if len(literals) > 1:
                literal_string += "("
            literal_a = literals[0]
            if len(literal_a.intersection(self.var_not)) > 0:
                literal_a = literal_a.difference(self.var_not)
                if len(literal_a.intersection(self.aux_symbol)) > 0:
                    literal_a = list(literal_a.difference(self.aux_symbol))
                    literal_string += "!aux(" + str(literal_a[0]) + "," + str(literal_a[1]) + ")"
                else:
                    literal_a = list(literal_a)
                    literal_string += "!(" + str(literal_a[0]) + "," + str(literal_a[1]) + ")"
            elif len(literal_a.intersection(self.aux_symbol)) > 0:
                literal_a = list(literal_a.difference(self.aux_symbol))
                literal_string += "aux(" + str(literal_a[0]) + "," + str(literal_a[1]) + ")"
            else:
                literal_a = list(literal_a)
                literal_string += "(" + str(literal_a[0]) + "," + str(literal_a[1]) + ")"
            if len(literals) > 1:
                literal_b = literals[1]
                if len(literal_b.intersection(self.var_not)) > 0:
                    literal_b = literals[1].difference(self.var_not)
                    if len(literal_b.intersection(self.aux_symbol)) > 0:
                        literal_b = list(literal_b.difference(self.aux_symbol))
                        literal_string += "| !aux(" + str(literal_b[0]) + "," + str(literal_b[1]) + ")"
                    else:
                        literal_b = list(literal_b)
                        literal_string += "| !(" + str(literal_b[0]) + "," + str(literal_b[1]) + ")"
                elif len(literal_b.intersection(self.aux_symbol)) > 0:
                    literal_b = list(literal_b.difference(self.aux_symbol))
                    literal_string += "| aux(" + str(literal_b[0]) + "," + str(literal_b[1]) + ")"
                else:
                    literal_b = list(literal_b)
                    literal_string += "| (" + str(literal_b[0]) + "," + str(literal_b[1]) + ")"
            if len(literals) > 1:
                literal_string += ")"
            literal_strings.append(literal_string)
        print(" &\n".join(literal_strings))

    def print_large_clauses(self):
        literal_strings = []
        for clause in self.large_clauses:
            clause_strings = []
            for literal in clause:
                clause_string = ""
                if len(self.aux_symbol.intersection(literal)) > 0:
                    if len(self.var_not.intersection(literal)) > 0:
                        temp = list(literal.difference(self.aux_symbol).difference(self.var_not))
                        clause_string += "!aux(" + str(temp[0]) + ", " + str(temp[1]) + ")"
                    else:
                        temp = list(literal.difference(self.aux_symbol))
                        clause_string += "aux(" + str(temp[0]) + ", " + str(temp[1]) + ")"
                else:
                    if len(self.var_not.intersection(literal)) > 0:
                        temp = list(literal.difference(self.var_not))
                        clause_string += "!(" + str(temp[0]) + ", " + str(temp[1]) + ")"
                    else:
                        temp = list(literal)
                        clause_string += "(" + str(temp[0]) + ", " + str(temp[1]) + ")"
                clause_strings.append(clause_string)
            literal_strings.append("(" + " | ".join(clause_strings) + ")")
        print(" &\n".join(literal_strings))

    def print_var_assignment(self):
        for key in self.assignment:
            l_key = list(key.difference(self.var_not))
            if len(l_key) < 3:
                print("(" + str(l_key[0]) + ", " + str(l_key[1]) + ") -> " + str(self.assignment[key]))
            else:
                l_key = list(key.difference(self.aux_symbol))
                print("aux(" + str(l_key[0]) + ", " + str(l_key[1]) + ") -> " + str(self.assignment[key]))

    def init_backtracking(self):
        # Resetting assignments for backtracking (we don't want to use the solution from solving small clauses)
        for key in self.assignment:
            self.assignment[key] = None
        # Go through all clauses
        # If it contains a free variable, assign sensible value that hasn't been used yet in current subtree
        # Node in the backtracking tree corresponds to a variable being assigned a value
        self.to_assign = [k for k in self.assignment.keys()]
        root = len(self.bt_tree.nodes)
        print("to assign:", self.to_assign)
        if len(self.to_assign) < 1:
            self.bt_tree.add_node(root, var="root", val=None)
            print("no variables to assign")
            return
        print("starting variable backtracking...")
        self.bt_tree.add_node(root, var="root", val=None)
        return root

    def solve_with_backtracking(self):
        root = self.init_backtracking()
        if root is None:
            return
        return self.backtrack_values(root)

    # for each clause assign variables
    # after each assigned variable check if any other clause that is affected by assignment yields contradiction
    # when all variables are assigned check if the clause is satisfied (as well as all affected yield no contr.)
    # variables are assigned True and then False if contr. occurs
    def backtrack_values(self, parent):
        if self.time_limit_reached():
            print("reached the time limit, stopping ...")
            self.finished_in_time = False
            return self.verify_assignment()
        var = self.to_assign.pop()
        while len(self.to_assign) > 0 and self.assignment[var] is not None:
            var = self.to_assign.pop()
        current_node = len(self.bt_tree.nodes)
        self.bt_tree.add_node(current_node, var=var, val=True)
        self.bt_tree.add_edge(parent, current_node)
        old_assignment = self.assignment.copy()
        print("setting", var, "to True")
        self.assignment[var] = True
        # check clauses for contradiction
        contradicting_clause = self.find_contradicting_clause_containing(var)
        if contradicting_clause is not None:
            current_node = len(self.bt_tree.nodes)
            self.bt_tree.add_node(current_node, var=var, val=False)
            self.bt_tree.add_edge(parent, current_node)
            print("setting", var, "to False")
            self.assignment[var] = False
            if not self.is_clause_satisfied(contradicting_clause):
                print("didn't fix contradiction in", contradicting_clause)
                # flipping assignment didn't fix contradiction, find variable that might fix
                for other_var in contradicting_clause.difference(var):
                    if self.assignment[other_var.difference(self.var_not)] is True:
                        self.to_assign.append(var)
                        # go back in BT tree to this variable
                        return other_var
                # all variables have been assigned both values, no solution
                return False
            # check if another clause might not be satisfied anymore
            contradicting_clause = self.find_contradicting_clause_containing(var)
            if contradicting_clause is not None:
                print("caused another contradiction", contradicting_clause)
                for other_var in contradicting_clause.difference(var):
                    if self.assignment[other_var.difference(self.var_not)] is True:
                        self.to_assign.append(var)
                        # go back in BT tree to this variable
                        return other_var
                    # all variables have been assigned both values, no solution
                print("all variables in", contradicting_clause, "have been assigned both values:")
                print([(v, self.assignment[v.difference(self.var_not)]) for v in contradicting_clause])
                return False
        if len(self.to_assign) < 1:
            return True
        fix_var = self.backtrack_values(current_node)
        if self.time_limit_reached():
            print("reached the time limit, stopping ...")
            self.finished_in_time = False
            return fix_var
        if fix_var in {True, False}:
            return fix_var
        # node further down the tree resulted in a contradiction
        print("we have to go back to", fix_var, "and we are at", var)
        if var == fix_var.difference(self.var_not):
            current_node = len(self.bt_tree.nodes)
            self.bt_tree.add_node(current_node, var=var, val=False)
            self.bt_tree.add_edge(parent, current_node)
            self.assignment = old_assignment
            print("setting", var, "to False")
            self.assignment[var] = False
            # check if we caused any other contradiction by assigning the variable
            contradicting_clause = self.find_contradicting_clause_containing(var)
            if contradicting_clause is not None:
                for other_var in contradicting_clause.difference(var):
                    if self.assignment[other_var.difference(self.var_not)] is True:
                        self.to_assign.append(var)
                        return other_var
                # all variables have been assigned both values, no solution
                return False
        else:
            # go further up the backtracking tree
            self.to_assign.append(var)
            return fix_var
        if len(self.to_assign) < 1:
            return True
        fix_var = self.backtrack_values(current_node)
        if self.time_limit_reached():
            print("reached the time limit, stopping ...")
            self.finished_in_time = False
            return fix_var
        if fix_var in {True, False}:
            return fix_var
        if fix_var is not None:
            if var == fix_var.difference(self.var_not):
                self.assignment = old_assignment
                # we already tried both values, return False
                return False
            print("going further up, returning", fix_var)
            self.to_assign.append(var)
            return fix_var
        print("done")
        return True

    def is_clause_empty(self, clause):
        for var in clause:
            if self.assignment[var.difference(self.var_not)] is None:
                return True
        return False

    def is_clause_satisfied(self, clause):
        for var in clause:
            if self.assignment[var.difference(self.var_not)] is True and len(var.intersection(self.var_not)) < 1:
                return True
            if self.assignment[var.difference(self.var_not)] is False and len(var.intersection(self.var_not)) > 0:
                return True
        return False

    def find_contradicting_clause_containing(self, var):
        self.contradiction_timer.start()
        for clause in itertools.chain(self.small_clauses, self.large_clauses):
            if (var in clause or var.union(self.var_not) in clause) and not (
                    self.is_clause_empty(clause) or self.is_clause_satisfied(clause)):
                print("contradicting clause:", clause)
                self.contradiction_timer.stop()
                return clause
        self.contradiction_timer.stop()

    def verify_assignment(self):
        for clause in self.small_clauses | self.large_clauses:
            is_satisfied = False
            for var in clause:
                if self.assignment[var.difference(self.var_not)] is True and len(var.intersection(self.var_not)) < 1:
                    print(clause, var, self.assignment[var.difference(self.var_not)])
                    is_satisfied = True
                    break
                if self.assignment[var.difference(self.var_not)] is False and len(var.intersection(self.var_not)) > 0:
                    print(clause, var, self.assignment[var.difference(self.var_not)])
                    is_satisfied = True
                    break
            if not is_satisfied:
                print(clause, ": clause is not satisfied",
                      [(a, self.assignment[a.difference(self.var_not)]) for a in clause])
                return False
        return True

    def solve_with_regular_backtracking(self):
        root = self.init_backtracking()
        if root is None:
            return
        self.timer = time.time()
        return self.regular_backtrack()

    def regular_backtrack(self):
        if self.time_limit_reached():
            print("reached the time limit, stopping ...")
            self.finished_in_time = False
            return
        var = self.to_assign.pop()
        print(var, 1, time.perf_counter(), self.timer)
        self.current_node = self.current_node + 1
        old_assignment = self.assignment.copy()
        print("setting", var, "to True")
        self.assignment[var] = True
        # check clauses for contradiction
        contradicting_clause = self.find_contradicting_clause_containing(var)
        print(var, 2, time.perf_counter(), self.timer)
        if contradicting_clause is not None:
            self.current_node = self.current_node + 1
            self.leaves = self.leaves + 1
            print("setting", var, "to False")
            self.assignment[var] = False
            if not self.is_clause_satisfied(contradicting_clause):
                self.leaves = self.leaves + 1
                self.to_assign.append(var)
                return False
            # check if another clause might not be satisfied anymore
            contradicting_clause = self.find_contradicting_clause_containing(var)
            print(var, 3, time.perf_counter(), self.timer)
            if contradicting_clause is not None:
                self.leaves = self.leaves + 1
                self.to_assign.append(var)
                # go step up back in BT tree
                return False
        if len(self.to_assign) < 1:
            self.leaves = self.leaves + 1
            return True
        fix_var = self.regular_backtrack()
        print(var, 4, time.perf_counter(), self.timer)
        if self.time_limit_reached():
            print("reached the time limit, stopping ...")
            self.finished_in_time = False
            return fix_var
        if fix_var is True:
            return fix_var
        # node further down the tree resulted in a contradiction
        if self.assignment[var] is False:
            # we already tried both values, we're done
            print("tried both values for ", var, ", step up")
            self.to_assign.append(var)
            return False
        print("found contradiction, try different value")
        self.current_node = self.current_node + 1
        self.assignment = old_assignment
        print("setting", var, "to False")
        self.assignment[var] = False
        # check if we caused any other contradiction by assigning the variable
        contradicting_clause = self.find_contradicting_clause_containing(var)
        print(var, 5, time.perf_counter(), self.timer)
        if contradicting_clause is not None:
            self.to_assign.append(var)
            self.leaves = self.leaves + 1
            return False
        if len(self.to_assign) < 1:
            self.leaves = self.leaves + 1
            return True
        result = self.regular_backtrack()
        print(var, 6, time.perf_counter(), self.timer)
        if self.time_limit_reached():
            print("reached the time limit, stopping ...")
            self.finished_in_time = False
            return result
        if result is True:
            return result
        self.to_assign.append(var)
        return result

    def get_btt_leaves(self):
        leaves = 0
        if len(self.bt_tree.nodes) == 1:
            return 1
        for i in self.bt_tree.nodes:
            if i == 0:
                continue
            if self.bt_tree.degree(i) == 1:
                leaves = leaves + 1
        return leaves

    def time_limit_reached(self):
        return time.time() - 3600 > self.timer
