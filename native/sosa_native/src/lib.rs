pub mod arc_ops;
pub mod base_case;
pub mod bitset;
pub mod colors;
pub mod dimacs;
pub mod error;
pub mod instance;
pub mod lemma_36;
pub mod lemma_37;
pub mod lemma_38;
pub mod partition;
pub mod reduction;
pub mod solver;
pub mod stats;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SolveConfig {
    pub base_case_n: usize,
    pub validate_graph: bool,
}

impl Default for SolveConfig {
    fn default() -> Self {
        Self {
            base_case_n: 128,
            validate_graph: true,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SolveStatus {
    Colorable,
    NotColorable,
    Unknown,
}

#[derive(Debug)]
pub struct SolveSummary {
    pub status: SolveStatus,
    pub core_time_s: f64,
    pub error: Option<String>,
}

pub use solver::solve_dimacs_circle_file;
