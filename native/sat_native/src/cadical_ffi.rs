use std::cell::RefCell;
use std::fs::File;
use std::io::BufReader;
use std::path::Path;
use std::time::Instant;

use cadical::{Solver, Timeout};
use circle_core::dimacs_edge::stream_dimacs_edges;
use circle_core::error::SosaError;

use crate::cnf::{edge_clauses, n_vars, vertex_clause};
use crate::{SatStatus, SatSummary};

pub fn solve_dimacs_edge_file_with_cadical(
    path: &Path,
    timeout_s: Option<u64>,
) -> Result<SatSummary, SosaError> {
    let file = File::open(path)?;
    let reader = BufReader::new(file);
    let solver = RefCell::new(Solver::new());

    stream_dimacs_edges(
        reader,
        |problem| {
            let mut solver = solver.borrow_mut();
            solver.reserve(n_vars(problem.n) as i32);
            for vertex in 1..=problem.n {
                solver.add_clause(vertex_clause(vertex));
            }
            Ok(())
        },
        |u, v| {
            let mut solver = solver.borrow_mut();
            for clause in edge_clauses(u, v) {
                solver.add_clause(clause);
            }
            Ok(())
        },
    )?;

    let mut solver = solver.into_inner();
    if let Some(timeout_s) = timeout_s {
        solver.set_callbacks(Some(Timeout::new(timeout_s as f32)));
    }

    let started_at = Instant::now();
    let status = match solver.solve() {
        Some(true) => SatStatus::Colorable,
        Some(false) => SatStatus::NotColorable,
        None => SatStatus::Unknown,
    };

    Ok(SatSummary {
        status,
        core_time_s: Some(started_at.elapsed().as_secs_f64()),
        error: None,
    })
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::*;

    #[test]
    fn solves_colorable_instance() {
        let instance = write_temp_file(
            "colorable",
            "\
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        );

        let summary = solve_dimacs_edge_file_with_cadical(&instance, Some(5)).unwrap();

        assert_eq!(summary.status, SatStatus::Colorable);
        assert!(summary.core_time_s.is_some());
        let _ = fs::remove_file(instance);
    }

    #[test]
    fn solves_uncolorable_instance() {
        let instance = write_temp_file(
            "uncolorable",
            "\
p edge 4 6
e 1 2
e 1 3
e 1 4
e 2 3
e 2 4
e 3 4
",
        );

        let summary = solve_dimacs_edge_file_with_cadical(&instance, Some(5)).unwrap();

        assert_eq!(summary.status, SatStatus::NotColorable);
        assert!(summary.core_time_s.is_some());
        let _ = fs::remove_file(instance);
    }

    fn write_temp_file(label: &str, content: &str) -> PathBuf {
        let mut path = std::env::temp_dir();
        path.push(format!("cadical-direct-{label}-{}.col", unique_suffix()));
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
