pub mod cadical_rustsat;
pub mod cnf;
pub mod kissat_rustsat;
pub mod solver;

use circle_core::error::SosaError;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EdgeSource {
    ListedEdges,
    CircleCrossings,
}

impl EdgeSource {
    pub fn parse(value: &str) -> Result<Self, SosaError> {
        match value {
            "listed_edges" => Ok(Self::ListedEdges),
            "circle_crossings" => Ok(Self::CircleCrossings),
            _ => Err(SosaError::Input(format!(
                "unsupported SAT edge source {value:?}, expected \"listed_edges\" or \"circle_crossings\""
            ))),
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::ListedEdges => "listed_edges",
            Self::CircleCrossings => "circle_crossings",
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SatConfig {
    pub backend: String,
    pub timeout_s: Option<u64>,
    pub edge_source: EdgeSource,
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
    pub edge_source: EdgeSource,
    pub load_prepare_time_s: f64,
    pub load_time_s: Option<f64>,
    pub prepare_time_s: Option<f64>,
    pub solve_time_s: Option<f64>,
    pub total_native_time_s: f64,
    pub error: Option<String>,
}

pub use solver::solve_dimacs_edge_file;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_edge_sources() {
        assert_eq!(
            EdgeSource::parse("listed_edges").unwrap(),
            EdgeSource::ListedEdges
        );
        assert_eq!(
            EdgeSource::parse("circle_crossings").unwrap(),
            EdgeSource::CircleCrossings
        );
        assert!(EdgeSource::parse("other").is_err());
    }
}
