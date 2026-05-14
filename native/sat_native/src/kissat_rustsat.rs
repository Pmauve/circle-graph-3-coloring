#[cfg(unix)]
mod imp {
    use std::cell::RefCell;
    use std::fs::File;
    use std::io::BufReader;
    use std::path::Path;
    use std::time::{Duration, Instant};

    use circle_core::crossing_edges::visit_circle_crossing_edges;
    use circle_core::dimacs_circle::read_dimacs_circle_geometry_skip_edges;
    use circle_core::dimacs_edge::stream_dimacs_edges;
    use circle_core::error::SosaError;
    use rustsat::solvers::{ControlSignal, Solve, SolverResult, Terminate};
    use rustsat::types::{Clause, Lit, Var};
    use rustsat_kissat::Kissat;

    use crate::cnf::{edge_clauses, n_vars, vertex_clause};
    use crate::{EdgeSource, SatStatus, SatSummary};

    pub fn solve_dimacs_edge_file_with_kissat(
        path: &Path,
        timeout_s: Option<u64>,
        edge_source: EdgeSource,
    ) -> Result<SatSummary, SosaError> {
        let native_started = Instant::now();
        if edge_source == EdgeSource::CircleCrossings {
            return solve_dimacs_circle_file_with_kissat(
                path,
                timeout_s,
                edge_source,
                native_started,
            );
        }

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
        let prepared_at = Instant::now();
        let load_prepare_time_s = prepared_at.duration_since(native_started).as_secs_f64();

        let mut solver = solver.into_inner();
        attach_deadline(&mut solver, timeout_s);

        let status = match solver.solve().map_err(kissat_error)? {
            SolverResult::Sat => SatStatus::Colorable,
            SolverResult::Unsat => SatStatus::NotColorable,
            SolverResult::Interrupted => SatStatus::Unknown,
        };
        let solved_at = Instant::now();
        let solve_time_s = solved_at.duration_since(prepared_at).as_secs_f64();
        let total_native_time_s = solved_at.duration_since(native_started).as_secs_f64();

        Ok(SatSummary {
            status,
            edge_source,
            load_prepare_time_s,
            load_time_s: None,
            prepare_time_s: None,
            solve_time_s: Some(solve_time_s),
            total_native_time_s,
            error: None,
        })
    }

    fn solve_dimacs_circle_file_with_kissat(
        path: &Path,
        timeout_s: Option<u64>,
        edge_source: EdgeSource,
        native_started: Instant,
    ) -> Result<SatSummary, SosaError> {
        let geometry = read_dimacs_circle_geometry_skip_edges(path)?;
        let loaded_at = Instant::now();
        let load_time_s = loaded_at.duration_since(native_started).as_secs_f64();

        let mut solver = Kissat::default();
        solver
            .reserve(Var::new((n_vars(geometry.n) - 1) as u32))
            .map_err(kissat_error)?;
        for vertex in 1..=geometry.n {
            add_clause(&mut solver, vertex_clause(vertex))?;
        }
        visit_circle_crossing_edges(&geometry, |u, v| {
            for clause in edge_clauses(u, v) {
                add_clause(&mut solver, clause)?;
            }
            Ok(())
        })?;
        let prepared_at = Instant::now();
        let prepare_time_s = prepared_at.duration_since(loaded_at).as_secs_f64();
        let load_prepare_time_s = prepared_at.duration_since(native_started).as_secs_f64();

        attach_deadline(&mut solver, timeout_s);

        let status = match solver.solve().map_err(kissat_error)? {
            SolverResult::Sat => SatStatus::Colorable,
            SolverResult::Unsat => SatStatus::NotColorable,
            SolverResult::Interrupted => SatStatus::Unknown,
        };
        let solved_at = Instant::now();
        let solve_time_s = solved_at.duration_since(prepared_at).as_secs_f64();
        let total_native_time_s = solved_at.duration_since(native_started).as_secs_f64();

        Ok(SatSummary {
            status,
            edge_source,
            load_prepare_time_s,
            load_time_s: Some(load_time_s),
            prepare_time_s: Some(prepare_time_s),
            solve_time_s: Some(solve_time_s),
            total_native_time_s,
            error: None,
        })
    }

    fn attach_deadline(solver: &mut Kissat<'_>, timeout_s: Option<u64>) {
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

    use crate::{EdgeSource, SatSummary};

    pub fn solve_dimacs_edge_file_with_kissat(
        _path: &Path,
        _timeout_s: Option<u64>,
        _edge_source: EdgeSource,
    ) -> Result<SatSummary, SosaError> {
        Err(SosaError::NotImplemented(
            "kissat-rustsat backend is only available on Unix targets".to_string(),
        ))
    }
}

pub use imp::solve_dimacs_edge_file_with_kissat;
