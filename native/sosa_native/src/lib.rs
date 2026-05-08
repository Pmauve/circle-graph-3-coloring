pub mod arc_ops;
pub mod base_case;
pub mod lemma_36;
pub mod lemma_37;
pub mod lemma_38;
pub mod reduction;
pub mod solver;
pub mod stats;

pub use stats::Stats;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BaseCaseAlgorithm {
    Backtracking,
    CadicalRustsat,
    KissatRustsat,
}

impl BaseCaseAlgorithm {
    pub fn parse(value: &str) -> Result<Self, circle_core::error::SosaError> {
        match value {
            "backtracking" => Ok(Self::Backtracking),
            "cadical-rustsat" => Ok(Self::CadicalRustsat),
            "kissat-rustsat" => Ok(Self::KissatRustsat),
            other => Err(circle_core::error::SosaError::Input(format!(
                "unsupported base-case algorithm {other:?}, expected \"backtracking\", \"cadical-rustsat\", or \"kissat-rustsat\""
            ))),
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Backtracking => "backtracking",
            Self::CadicalRustsat => "cadical-rustsat",
            Self::KissatRustsat => "kissat-rustsat",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SolveConfig {
    pub base_case_n: usize,
    pub base_case_algorithm: BaseCaseAlgorithm,
    pub validate_graph: bool,
    pub profile: bool,
    pub disable_branch_dedup: bool,
    pub lazy_circle_neighbors: bool,
}

impl Default for SolveConfig {
    fn default() -> Self {
        Self {
            base_case_n: 128,
            base_case_algorithm: BaseCaseAlgorithm::Backtracking,
            validate_graph: true,
            profile: false,
            disable_branch_dedup: false,
            lazy_circle_neighbors: false,
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
    pub parse_time_s: f64,
    pub build_time_s: f64,
    pub solve_time_s: f64,
    pub stats: stats::Stats,
    pub error: Option<String>,
}

pub use solver::solve_dimacs_circle_file;
