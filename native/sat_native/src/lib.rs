pub mod cadical_ffi;
pub mod cnf;
pub mod encode;
pub mod external;
pub mod kissat_ffi;
pub mod solver;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SatConfig {
    pub backend: String,
    pub solver_bin: String,
    pub timeout_s: Option<u64>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SatStatus {
    Colorable,
    NotColorable,
    Unknown,
}

#[derive(Debug)]
pub struct SatSummary {
    pub status: SatStatus,
    pub core_time_s: Option<f64>,
    pub error: Option<String>,
}

pub use solver::solve_dimacs_edge_file;
