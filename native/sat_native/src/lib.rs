pub mod cadical_rustsat;
pub mod cnf;
pub mod kissat_rustsat;
pub mod solver;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SatConfig {
    pub backend: String,
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
    pub parse_time_s: Option<f64>,
    pub build_time_s: Option<f64>,
    pub solve_time_s: Option<f64>,
    pub error: Option<String>,
}

pub use solver::solve_dimacs_edge_file;
