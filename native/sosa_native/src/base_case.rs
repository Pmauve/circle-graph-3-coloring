use crate::stats::Stats;
use crate::BaseCaseAlgorithm;
use circle_core::colors::{color_bit, color_count, iter_colors};
use circle_core::error::SosaError;
use circle_core::instance::CircleInstance;

pub fn solve_base_case(
    instance: &CircleInstance,
    algorithm: BaseCaseAlgorithm,
    stats: &mut Stats,
) -> Result<bool, SosaError> {
    stats.base_case_calls += 1;
    match algorithm {
        BaseCaseAlgorithm::Backtracking => Ok(solve_base_case_backtracking(instance, stats)),
        BaseCaseAlgorithm::CadicalRustsat => solve_base_case_with_cadical(instance, stats),
        BaseCaseAlgorithm::KissatRustsat => solve_base_case_with_kissat(instance, stats),
    }
}

fn solve_base_case_backtracking(instance: &CircleInstance, stats: &mut Stats) -> bool {
    let mut assigned = vec![0u8; instance.n];
    search(instance, &mut assigned, stats)
}

fn search(instance: &CircleInstance, assigned: &mut [u8], stats: &mut Stats) -> bool {
    stats.base_case_search_nodes += 1;
    let Some(vertex) = choose_vertex(instance, assigned) else {
        return true;
    };
    let mask = available_mask(instance, assigned, vertex);
    for color in iter_colors(mask) {
        assigned[vertex] = color;
        if search(instance, assigned, stats) {
            return true;
        }
        assigned[vertex] = 0;
    }
    false
}

fn choose_vertex(instance: &CircleInstance, assigned: &[u8]) -> Option<usize> {
    let mut best: Option<(u32, usize, usize, usize)> = None;
    for vertex in 0..instance.n {
        if assigned[vertex] != 0 {
            continue;
        }
        let mask = available_mask(instance, assigned, vertex);
        let color_options = color_count(mask);
        let saturation = saturation_degree(instance, assigned, vertex);
        let degree = instance.degree(vertex as u32);
        let key = (
            color_options,
            usize::MAX - saturation,
            usize::MAX - degree,
            vertex,
        );
        if best.is_none_or(|best_key| key < best_key) {
            best = Some(key);
        }
    }
    best.map(|(_, _, _, vertex)| vertex)
}

fn available_mask(instance: &CircleInstance, assigned: &[u8], vertex: usize) -> u8 {
    let mut mask = instance.allowed[vertex];
    for &neighbor in instance.neighbors(vertex as u32) {
        let color = assigned[neighbor as usize];
        if color != 0 {
            mask &= !color_bit(color);
        }
    }
    mask
}

fn saturation_degree(instance: &CircleInstance, assigned: &[u8], vertex: usize) -> usize {
    let mut seen = 0u8;
    for &neighbor in instance.neighbors(vertex as u32) {
        let color = assigned[neighbor as usize];
        if color != 0 {
            seen |= color_bit(color);
        }
    }
    color_count(seen) as usize
}

#[cfg(unix)]
mod sat {
    use crate::stats::Stats;
    use circle_core::colors::color_bit;
    use circle_core::error::SosaError;
    use circle_core::instance::CircleInstance;
    use rustsat::solvers::{Solve, SolverResult};
    use rustsat::types::{Clause, Lit};
    use rustsat_cadical::CaDiCaL;
    use rustsat_kissat::Kissat;
    use std::time::Instant;

    pub fn solve_with_cadical(
        instance: &CircleInstance,
        stats: &mut Stats,
    ) -> Result<bool, SosaError> {
        let mut solver = CaDiCaL::default();
        let build_started = Instant::now();
        add_instance_clauses(instance, |clause| {
            stats.base_case_sat_clauses += 1;
            stats.base_case_sat_literals += clause.len() as u64;
            solver.add_clause(clause).map_err(cadical_error)
        })?;
        stats.base_case_sat_calls += 1;
        stats.base_case_sat_build_ns += build_started.elapsed().as_nanos();
        let solve_started = Instant::now();
        let result = solve_cadical(solver);
        stats.base_case_sat_solve_ns += solve_started.elapsed().as_nanos();
        result
    }

    pub fn solve_with_kissat(
        instance: &CircleInstance,
        stats: &mut Stats,
    ) -> Result<bool, SosaError> {
        let mut solver = Kissat::default();
        let build_started = Instant::now();
        add_instance_clauses(instance, |clause| {
            stats.base_case_sat_clauses += 1;
            stats.base_case_sat_literals += clause.len() as u64;
            solver.add_clause(clause).map_err(kissat_error)
        })?;
        stats.base_case_sat_calls += 1;
        stats.base_case_sat_build_ns += build_started.elapsed().as_nanos();
        let solve_started = Instant::now();
        let result = solve_kissat(solver);
        stats.base_case_sat_solve_ns += solve_started.elapsed().as_nanos();
        result
    }

    fn add_instance_clauses(
        instance: &CircleInstance,
        mut add_clause: impl FnMut(Clause) -> Result<(), SosaError>,
    ) -> Result<(), SosaError> {
        if instance.n == 0 {
            return Ok(());
        }

        for vertex in 0..instance.n {
            let allowed = allowed_colors(instance.allowed[vertex]);
            if allowed.is_empty() {
                return add_clause(std::iter::empty::<Lit>().collect());
            }

            add_clause(
                allowed
                    .iter()
                    .map(|&color| dimacs_lit(var(vertex, color)))
                    .collect::<Result<Clause, SosaError>>()?,
            )?;

            for (left_index, &left_color) in allowed.iter().enumerate() {
                for &right_color in &allowed[left_index + 1..] {
                    add_clause(
                        [
                            dimacs_lit(-var(vertex, left_color))?,
                            dimacs_lit(-var(vertex, right_color))?,
                        ]
                        .into_iter()
                        .collect(),
                    )?;
                }
            }
        }

        for u in 0..instance.n {
            for &v in instance.neighbors(u as u32) {
                if v as usize <= u {
                    continue;
                }
                for color in 1..=3 {
                    if instance.allowed[u] & color_bit(color) == 0 {
                        continue;
                    }
                    if instance.allowed[v as usize] & color_bit(color) == 0 {
                        continue;
                    }
                    add_clause(
                        [
                            dimacs_lit(-var(u, color))?,
                            dimacs_lit(-var(v as usize, color))?,
                        ]
                        .into_iter()
                        .collect(),
                    )?;
                }
            }
        }

        Ok(())
    }

    fn solve_cadical(mut solver: CaDiCaL<'_, '_>) -> Result<bool, SosaError> {
        match solver.solve().map_err(cadical_error)? {
            SolverResult::Sat => Ok(true),
            SolverResult::Unsat => Ok(false),
            SolverResult::Interrupted => Err(SosaError::Internal(
                "RustSAT CaDiCaL interrupted while solving SOSA base case".to_string(),
            )),
        }
    }

    fn solve_kissat(mut solver: Kissat<'_>) -> Result<bool, SosaError> {
        match solver.solve().map_err(kissat_error)? {
            SolverResult::Sat => Ok(true),
            SolverResult::Unsat => Ok(false),
            SolverResult::Interrupted => Err(SosaError::Internal(
                "RustSAT Kissat interrupted while solving SOSA base case".to_string(),
            )),
        }
    }

    fn allowed_colors(mask: u8) -> Vec<u8> {
        (1..=3)
            .filter(|&color| mask & color_bit(color) != 0)
            .collect()
    }

    fn var(vertex: usize, color: u8) -> i32 {
        (vertex as i32) * 3 + color as i32
    }

    fn dimacs_lit(value: i32) -> Result<Lit, SosaError> {
        Lit::from_ipasir(value).map_err(|error| {
            SosaError::Input(format!(
                "failed to convert SOSA base-case literal {value}: {error}"
            ))
        })
    }

    fn cadical_error(error: impl std::fmt::Display) -> SosaError {
        SosaError::Internal(format!("RustSAT CaDiCaL failed in SOSA base case: {error}"))
    }

    fn kissat_error(error: impl std::fmt::Display) -> SosaError {
        SosaError::Internal(format!("RustSAT Kissat failed in SOSA base case: {error}"))
    }
}

#[cfg(unix)]
fn solve_base_case_with_cadical(
    instance: &CircleInstance,
    stats: &mut Stats,
) -> Result<bool, SosaError> {
    sat::solve_with_cadical(instance, stats)
}

#[cfg(not(unix))]
fn solve_base_case_with_cadical(
    _instance: &CircleInstance,
    _stats: &mut Stats,
) -> Result<bool, SosaError> {
    Err(SosaError::NotImplemented(
        "cadical-rustsat base-case algorithm is only available on Unix targets".to_string(),
    ))
}

#[cfg(unix)]
fn solve_base_case_with_kissat(
    instance: &CircleInstance,
    stats: &mut Stats,
) -> Result<bool, SosaError> {
    sat::solve_with_kissat(instance, stats)
}

#[cfg(not(unix))]
fn solve_base_case_with_kissat(
    _instance: &CircleInstance,
    _stats: &mut Stats,
) -> Result<bool, SosaError> {
    Err(SosaError::NotImplemented(
        "kissat-rustsat base-case algorithm is only available on Unix targets".to_string(),
    ))
}

#[cfg(test)]
mod tests {
    use circle_core::colors::{BLUE, GREEN, RED};
    use circle_core::dimacs_circle::parse_dimacs_circle;

    use super::*;

    #[test]
    fn solves_triangle() {
        let instance = instance_from_text(
            "\
c hord endpoint order START
c 1 2 3 1 2 3
c hord endpoint order END
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        );

        assert!(solve_base_case(
            &instance,
            BaseCaseAlgorithm::Backtracking,
            &mut Stats::default()
        )
        .unwrap());
    }

    #[test]
    fn rejects_k4() {
        let instance = instance_from_text(
            "\
c hord endpoint order START
c 1 2 3 4 1 2 3 4
c hord endpoint order END
p edge 4 6
e 1 2
e 1 3
e 1 4
e 2 3
e 2 4
e 3 4
",
        );

        assert!(!solve_base_case(
            &instance,
            BaseCaseAlgorithm::Backtracking,
            &mut Stats::default()
        )
        .unwrap());
    }

    #[test]
    fn solves_path() {
        let instance = instance_from_text(
            "\
c hord endpoint order START
c 1 2 1 3 2 3
c hord endpoint order END
p edge 3 2
e 1 2
e 2 3
",
        );

        assert!(solve_base_case(
            &instance,
            BaseCaseAlgorithm::Backtracking,
            &mut Stats::default()
        )
        .unwrap());
    }

    #[test]
    fn respects_list_color_restrictions() {
        let mut instance = instance_from_text(
            "\
c hord endpoint order START
c 1 2 1 2
c hord endpoint order END
p edge 2 1
e 1 2
",
        );
        instance.allowed[0] = RED;
        instance.allowed[1] = RED;

        assert!(!solve_base_case(
            &instance,
            BaseCaseAlgorithm::Backtracking,
            &mut Stats::default()
        )
        .unwrap());

        instance.allowed[1] = GREEN | BLUE;
        assert!(solve_base_case(
            &instance,
            BaseCaseAlgorithm::Backtracking,
            &mut Stats::default()
        )
        .unwrap());
    }

    #[test]
    fn records_search_stats() {
        let instance = instance_from_text(
            "\
c hord endpoint order START
c 1 1
c hord endpoint order END
p edge 1 0
",
        );
        let mut stats = Stats::default();

        assert!(solve_base_case(&instance, BaseCaseAlgorithm::Backtracking, &mut stats).unwrap());
        assert_eq!(stats.base_case_calls, 1);
        assert!(stats.base_case_search_nodes > 0);
    }

    #[test]
    fn rejects_empty_allowed_mask() {
        let mut instance = instance_from_text(
            "\
c hord endpoint order START
c 1 1
c hord endpoint order END
p edge 1 0
",
        );
        instance.allowed[0] = 0;

        assert!(!solve_base_case(
            &instance,
            BaseCaseAlgorithm::Backtracking,
            &mut Stats::default()
        )
        .unwrap());
    }

    #[cfg(unix)]
    #[test]
    fn sat_backends_match_backtracking_on_restricted_instances() {
        let mut instances = Vec::new();
        instances.push(instance_from_text(
            "\
c hord endpoint order START
c 1 2 3 1 2 3
c hord endpoint order END
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        ));
        let mut restricted = instance_from_text(
            "\
c hord endpoint order START
c 1 2 1 2
c hord endpoint order END
p edge 2 1
e 1 2
",
        );
        restricted.allowed[0] = RED;
        restricted.allowed[1] = RED;
        instances.push(restricted);

        for instance in instances {
            let backtracking = solve_base_case(
                &instance,
                BaseCaseAlgorithm::Backtracking,
                &mut Stats::default(),
            )
            .unwrap();
            let cadical = solve_base_case(
                &instance,
                BaseCaseAlgorithm::CadicalRustsat,
                &mut Stats::default(),
            )
            .unwrap();
            let kissat = solve_base_case(
                &instance,
                BaseCaseAlgorithm::KissatRustsat,
                &mut Stats::default(),
            )
            .unwrap();
            assert_eq!(cadical, backtracking);
            assert_eq!(kissat, backtracking);
        }
    }

    fn instance_from_text(text: &str) -> CircleInstance {
        CircleInstance::from_dimacs(parse_dimacs_circle(text).unwrap()).unwrap()
    }
}
