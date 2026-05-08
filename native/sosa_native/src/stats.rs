#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct Stats {
    pub rr_steps: u64,
    pub rr_deleted_vertices: u64,
    pub base_case_calls: u64,
    pub base_case_search_nodes: u64,
    pub base_case_sat_calls: u64,
    pub base_case_sat_clauses: u64,
    pub base_case_sat_literals: u64,
    pub base_case_sat_build_ns: u128,
    pub base_case_sat_solve_ns: u128,
    pub solver_calls: u64,
    pub lemma_36_calls: u64,
    pub lemma_37_calls: u64,
    pub lemma_38_calls: u64,
    pub lemma_33_calls: u64,
    pub max_recursion_depth: u64,
}
