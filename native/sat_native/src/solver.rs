use std::path::Path;

use circle_core::error::SosaError;

use crate::cadical_rustsat::solve_dimacs_edge_file_with_rustsat_cadical;
use crate::kissat_rustsat::solve_dimacs_edge_file_with_kissat;
use crate::{SatConfig, SatStatus, SatSummary};

pub fn solve_dimacs_edge_file(path: &Path, config: SatConfig) -> Result<SatSummary, SosaError> {
    match config.backend.as_str() {
        "cadical-rustsat" => solve_dimacs_edge_file_with_rustsat_cadical(
            path,
            config.timeout_s,
            config.edge_source,
        ),
        "kissat-rustsat" => {
            solve_dimacs_edge_file_with_kissat(path, config.timeout_s, config.edge_source)
        }
        backend => Err(SosaError::Input(format!(
            "unsupported SAT backend {backend:?}, expected \"cadical-rustsat\" or \"kissat-rustsat\""
        ))),
    }
}

pub fn status_to_output(status: SatStatus) -> &'static str {
    match status {
        SatStatus::Colorable => "COLORABLE",
        SatStatus::NotColorable => "NOT_COLORABLE",
        SatStatus::Unknown => "UNKNOWN",
    }
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::*;
    use crate::EdgeSource;

    #[test]
    fn maps_status_to_native_output_tokens() {
        assert_eq!(status_to_output(SatStatus::Colorable), "COLORABLE");
        assert_eq!(status_to_output(SatStatus::NotColorable), "NOT_COLORABLE");
        assert_eq!(status_to_output(SatStatus::Unknown), "UNKNOWN");
    }

    #[test]
    fn rejects_unknown_backend() {
        let instance = write_temp_file("unknown-backend", "p edge 1 0\n");
        let error = solve_dimacs_edge_file(
            &instance,
            SatConfig {
                backend: "other".to_string(),
                timeout_s: None,
                edge_source: EdgeSource::ListedEdges,
            },
        )
        .unwrap_err();

        assert!(error.to_string().contains("unsupported SAT backend"));
        let _ = fs::remove_file(instance);
    }

    #[cfg(unix)]
    #[test]
    fn solves_with_cadical_rustsat_backend() {
        let instance = write_temp_file(
            "cadical-rustsat",
            "\
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        );

        let summary = solve_dimacs_edge_file(
            &instance,
            SatConfig {
                backend: "cadical-rustsat".to_string(),
                timeout_s: Some(5),
                edge_source: EdgeSource::ListedEdges,
            },
        )
        .unwrap();

        assert_eq!(summary.status, SatStatus::Colorable);
        assert!(summary.total_native_time_s > 0.0);
        let _ = fs::remove_file(instance);
    }

    #[cfg(unix)]
    #[test]
    fn solves_with_kissat_rustsat_backend() {
        let instance = write_temp_file(
            "kissat-rustsat",
            "\
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        );

        let summary = solve_dimacs_edge_file(
            &instance,
            SatConfig {
                backend: "kissat-rustsat".to_string(),
                timeout_s: Some(5),
                edge_source: EdgeSource::ListedEdges,
            },
        )
        .unwrap();

        assert_eq!(summary.status, SatStatus::Colorable);
        assert!(summary.total_native_time_s > 0.0);
        let _ = fs::remove_file(instance);
    }

    fn write_temp_file(label: &str, content: &str) -> PathBuf {
        let mut path = std::env::temp_dir();
        path.push(format!("sat-native-{label}-{}.col", unique_suffix()));
        fs::write(&path, content).unwrap();
        path
    }

    fn unique_suffix() -> u128 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    }
}
