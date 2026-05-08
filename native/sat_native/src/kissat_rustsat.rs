#[cfg(unix)]
mod imp {
    use std::cell::RefCell;
    use std::fs::File;
    use std::io::BufReader;
    use std::path::Path;
    use std::time::{Duration, Instant};

    use circle_core::dimacs_edge::stream_dimacs_edges;
    use circle_core::error::SosaError;
    use rustsat::solvers::{ControlSignal, Solve, SolverResult, Terminate};
    use rustsat::types::{Clause, Lit, Var};
    use rustsat_kissat::Kissat;

    use crate::cnf::{edge_clauses, n_vars, vertex_clause};
    use crate::{SatStatus, SatSummary};

    pub fn solve_dimacs_edge_file_with_kissat(
        path: &Path,
        timeout_s: Option<u64>,
    ) -> Result<SatSummary, SosaError> {
        let file = File::open(path)?;
        let reader = BufReader::new(file);
        let solver = RefCell::new(Kissat::default());

        stream_dimacs_edges(
            reader,
            |problem| {
                let mut solver = solver.borrow_mut();
                solver
                    .reserve(Var::new((n_vars(problem.n) - 1) as u32))
                    .map_err(kissat_error)?;
                for vertex in 1..=problem.n {
                    add_clause(&mut solver, vertex_clause(vertex))?;
                }
                Ok(())
            },
            |u, v| {
                let mut solver = solver.borrow_mut();
                for clause in edge_clauses(u, v) {
                    add_clause(&mut solver, clause)?;
                }
                Ok(())
            },
        )?;

        let mut solver = solver.into_inner();
        let deadline = timeout_s.map(|seconds| Instant::now() + Duration::from_secs(seconds));
        if let Some(deadline) = deadline {
            solver.attach_terminator(move || {
                if Instant::now() >= deadline {
                    ControlSignal::Terminate
                } else {
                    ControlSignal::Continue
                }
            });
        }

        let started_at = Instant::now();
        let status = match solver.solve().map_err(kissat_error)? {
            SolverResult::Sat => SatStatus::Colorable,
            SolverResult::Unsat => SatStatus::NotColorable,
            SolverResult::Interrupted => SatStatus::Unknown,
        };

        Ok(SatSummary {
            status,
            core_time_s: Some(started_at.elapsed().as_secs_f64()),
            error: None,
        })
    }

    fn add_clause<const N: usize>(
        solver: &mut Kissat<'_>,
        clause: [i32; N],
    ) -> Result<(), SosaError> {
        let clause = clause
            .into_iter()
            .map(dimacs_lit)
            .collect::<Result<Clause, SosaError>>()?;
        solver.add_clause(clause).map_err(kissat_error)
    }

    fn dimacs_lit(value: i32) -> Result<Lit, SosaError> {
        Lit::from_ipasir(value).map_err(|error| {
            SosaError::Input(format!(
                "failed to convert literal {value} for Kissat: {error}"
            ))
        })
    }

    fn kissat_error(error: impl std::fmt::Display) -> SosaError {
        SosaError::Internal(format!("RustSAT Kissat failed: {error}"))
    }
}

#[cfg(not(unix))]
mod imp {
    use std::path::Path;

    use circle_core::error::SosaError;

    use crate::SatSummary;

    pub fn solve_dimacs_edge_file_with_kissat(
        _path: &Path,
        _timeout_s: Option<u64>,
    ) -> Result<SatSummary, SosaError> {
        Err(SosaError::NotImplemented(
            "kissat-rustsat backend is only available on Unix targets".to_string(),
        ))
    }
}

pub use imp::solve_dimacs_edge_file_with_kissat;
