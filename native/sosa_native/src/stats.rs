use std::time::Instant;

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct Stats {
    pub profile_timers: bool,
    pub rr_steps: u64,
    pub rr_deleted_vertices: u64,
    pub rr_rebuilds: u64,
    pub partitioned_rr_rebuilds: u64,
    pub base_case_calls: u64,
    pub base_case_search_nodes: u64,
    pub base_case_sat_calls: u64,
    pub base_case_sat_clauses: u64,
    pub base_case_sat_literals: u64,
    pub base_case_sat_build_ns: u128,
    pub base_case_sat_solve_ns: u128,
    pub solver_calls: u64,
    pub arc_restrictions: u64,
    pub child_instances_built: u64,
    pub second_child_instances_skipped: u64,
    pub lemma_36_calls: u64,
    pub lemma_37_calls: u64,
    pub lemma_38_calls: u64,
    pub lemma_33_calls: u64,
    pub max_recursion_depth: u64,
    pub base_case_time_ns: u128,
    pub arc_restriction_time_ns: u128,
    pub rr_queue_time_ns: u128,
    pub rr_rebuild_time_ns: u128,
    pub partitioned_rr_rebuild_time_ns: u128,
    pub lemma_36_time_ns: u128,
    pub lemma_36_branch_setup_time_ns: u128,
    pub lemma_36_reduction_time_ns: u128,
    pub lemma_36_dedup_time_ns: u128,
    pub lemma_38_time_ns: u128,
}

impl Stats {
    pub fn with_profile_timers(profile_timers: bool) -> Self {
        Self {
            profile_timers,
            ..Self::default()
        }
    }

    pub fn start_timer(&self) -> Option<Instant> {
        self.profile_timers.then(Instant::now)
    }

    pub fn elapsed_ns(started_at: Option<Instant>) -> u128 {
        started_at.map_or(0, |started_at| started_at.elapsed().as_nanos())
    }
}
