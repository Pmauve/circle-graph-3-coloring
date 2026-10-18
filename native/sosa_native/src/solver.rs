use std::path::Path;
use std::time::Instant;

use crate::arc_ops::{chords_contained_in_left_right_arcs, restrict_instance_to_vertices};
use crate::base_case::solve_base_case;
use crate::lemma_38::{visit_lemma_33_family, FullySeparatedInstance};
use crate::reduction::{reduce_exhaustively, ReductionOutcome};
use crate::stats::Stats;
use crate::{SolveConfig, SolveStatus, SolveSummary};
use circle_core::dimacs_circle::{read_dimacs_circle, read_dimacs_circle_geometry_skip_edges};
use circle_core::error::SosaError;
use circle_core::instance::{CircleInstance, ListedEdgeMode};

pub fn solve_dimacs_circle_file(
    path: &Path,
    config: SolveConfig,
) -> Result<SolveSummary, SosaError> {
    let parse_started = Instant::now();
    let geometry = if config.input_mode == crate::SosaInputMode::LazyCircleNeighbors {
        if config.validate_graph {
            return Err(SosaError::Input(
                "lazy-circle-neighbors requires --skip-graph-validation".to_string(),
            ));
        }
        Some(read_dimacs_circle_geometry_skip_edges(path)?)
    } else {
        None
    };
    let dimacs = if geometry.is_none() {
        Some(read_dimacs_circle(path)?)
    } else {
        None
    };
    let parse_time_s = parse_started.elapsed().as_secs_f64();

    let build_started = Instant::now();
    let instance = if let Some(geometry) = geometry {
        debug_assert_eq!(config.input_mode, crate::SosaInputMode::LazyCircleNeighbors);
        CircleInstance::from_dimacs_geometry_without_adjacency(geometry)?
    } else {
        CircleInstance::from_dimacs_with_listed_edge_mode(
            dimacs.expect("DIMACS instance must be parsed when lazy geometry is disabled"),
            config.validate_graph,
            listed_edge_mode(config),
        )?
    };
    let build_time_s = build_started.elapsed().as_secs_f64();

    let started = Instant::now();
    let mut stats = Stats::with_profile_timers(config.profile);
    stats.set_disable_branch_dedup(config.disable_branch_dedup);
    stats.set_lazy_circle_neighbors(config.input_mode == crate::SosaInputMode::LazyCircleNeighbors);
    let status = if solve_instance_recursively(instance, config, &mut stats, 0)? {
        SolveStatus::Colorable
    } else {
        SolveStatus::NotColorable
    };
    let solve_time_s = started.elapsed().as_secs_f64();
    let core_time_s = solve_time_s;

    Ok(SolveSummary {
        status,
        core_time_s,
        parse_time_s,
        build_time_s,
        solve_time_s,
        stats,
        error: None,
    })
}

fn listed_edge_mode(config: SolveConfig) -> ListedEdgeMode {
    match config.input_mode {
        crate::SosaInputMode::StrictListedEdges => ListedEdgeMode::Strict,
        crate::SosaInputMode::TrustedListedEdges => ListedEdgeMode::Trusted,
        crate::SosaInputMode::LazyCircleNeighbors => {
            unreachable!("lazy circle-neighbor mode does not build listed-edge adjacency")
        }
    }
}

fn solve_instance_recursively(
    instance: CircleInstance,
    config: SolveConfig,
    stats: &mut Stats,
    depth: u64,
) -> Result<bool, SosaError> {
    stats.solver_calls += 1;
    stats.max_recursion_depth = stats.max_recursion_depth.max(depth);

    let mut reduced = match reduce_exhaustively(instance, stats)? {
        ReductionOutcome::Conflict => return Ok(false),
        ReductionOutcome::Consistent(reduced) => reduced,
    };
    if reduced.n <= config.base_case_n {
        if !reduced.has_adjacency() {
            let started_at = stats.start_timer();
            reduced.materialize_crossing_adjacency()?;
            stats.adjacency_materialize_time_ns += Stats::elapsed_ns(started_at);
        }
        let started_at = stats.start_timer();
        let is_colorable = solve_base_case(&reduced, config.base_case_algorithm, stats)?;
        stats.base_case_time_ns += Stats::elapsed_ns(started_at);
        return Ok(is_colorable);
    }

    let mut found_colorable_branch = false;
    visit_lemma_33_family(&reduced, stats, |full, stats| {
        if solve_full_branch(full, config, stats, depth + 1)? {
            found_colorable_branch = true;
            return Ok(true);
        }
        Ok(false)
    })?;
    Ok(found_colorable_branch)
}

fn solve_full_branch(
    full: FullySeparatedInstance,
    config: SolveConfig,
    stats: &mut Stats,
    depth: u64,
) -> Result<bool, SosaError> {
    let (left_vertices, right_vertices) =
        chords_contained_in_left_right_arcs(&full.instance, &full.partition);
    let left_n = left_vertices.count_ones();
    let right_n = right_vertices.count_ones();
    // The two sets are disjoint, so this checks that every chord lies in exactly one of them.
    if left_n + right_n != full.instance.n {
        return Err(SosaError::Internal(format!(
            "fully separated branch puts only {} of {} chords into I_L or I_R (partition {:?})",
            left_n + right_n,
            full.instance.n,
            full.partition
        )));
    }
    let (first_vertices, second_vertices) = if left_n <= right_n {
        (&left_vertices, &right_vertices)
    } else {
        (&right_vertices, &left_vertices)
    };

    stats.arc_restrictions += 1;
    stats.child_instances_built += 1;
    let started_at = stats.start_timer();
    let first = restrict_instance_to_vertices(&full.instance, first_vertices)?;
    stats.arc_restriction_time_ns += Stats::elapsed_ns(started_at);
    if !solve_instance_recursively(first, config, stats, depth)? {
        stats.second_child_instances_skipped += 1;
        return Ok(false);
    }

    stats.arc_restrictions += 1;
    stats.child_instances_built += 1;
    let started_at = stats.start_timer();
    let second = restrict_instance_to_vertices(&full.instance, second_vertices)?;
    stats.arc_restriction_time_ns += Stats::elapsed_ns(started_at);
    solve_instance_recursively(second, config, stats, depth)
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    use circle_core::colors::{ColorMask, ALL_COLORS, BLUE, GREEN, RED};
    use circle_core::dimacs_circle::DimacsCircleGeometry;
    use circle_core::partition::CirclePartition;

    use super::*;

    #[test]
    fn solves_small_colorable_file() {
        let path = write_temp_col(
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

        let summary = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 3,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                input_mode: crate::SosaInputMode::StrictListedEdges,
                validate_graph: true,
                profile: false,
                disable_branch_dedup: false,
            },
        )
        .unwrap();

        assert_eq!(summary.status, SolveStatus::Colorable);
        assert!(summary.error.is_none());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn solves_small_uncolorable_file() {
        let path = write_temp_col(
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

        let summary = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 4,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                input_mode: crate::SosaInputMode::StrictListedEdges,
                validate_graph: true,
                profile: false,
                disable_branch_dedup: false,
            },
        )
        .unwrap();

        assert_eq!(summary.status, SolveStatus::NotColorable);
        assert!(summary.error.is_none());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn solves_above_base_case_threshold() {
        let path = write_temp_col(
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

        let summary = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 2,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                input_mode: crate::SosaInputMode::StrictListedEdges,
                validate_graph: true,
                profile: false,
                disable_branch_dedup: false,
            },
        )
        .unwrap();

        assert_eq!(summary.status, SolveStatus::Colorable);
        assert!(summary.error.is_none());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn can_skip_crossing_validation() {
        let path = write_temp_col(
            "\
c hord endpoint order START
c 1 1 2 2
c hord endpoint order END
p edge 2 1
e 1 2
",
        );

        let strict = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 2,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                input_mode: crate::SosaInputMode::StrictListedEdges,
                validate_graph: true,
                profile: false,
                disable_branch_dedup: false,
            },
        );
        assert!(strict.unwrap_err().to_string().contains("does not match"));

        let skipped = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 2,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                input_mode: crate::SosaInputMode::StrictListedEdges,
                validate_graph: false,
                profile: false,
                disable_branch_dedup: false,
            },
        )
        .unwrap();
        assert_eq!(skipped.status, SolveStatus::Colorable);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn rejects_k4_reproducer_at_every_low_threshold() {
        // Six chords containing the clique {0, 2, 3, 4}. Before the full-arc fix, every
        // threshold below 6 accepted a branch whose chords had silently been dropped.
        let word = [3, 4, 5, 0, 1, 2, 1, 5, 3, 4, 0, 2];
        for allowed in [vec![5, 6, 7, 3, 5, 6], vec![ALL_COLORS; 6]] {
            for input in both_representations(restricted_instance(&word, &allowed)) {
                for base_case_n in 1..=6 {
                    assert!(
                        !solve_with_threshold(input.clone(), base_case_n),
                        "allowed={allowed:?}, base_case_n={base_case_n}, lazy={}",
                        !input.has_adjacency()
                    );
                }
            }
        }
    }

    #[test]
    fn rejects_uncolorable_generated_instance_below_base_case_size() {
        // `three_col_native instance generate --family rc_fast --n 20 --seed 8`; not
        // 3-colorable (checked independently with CaDiCaL).
        let path = write_temp_col(
            "\
c hord endpoint order START
c 6 13 8 15 14 5 4 8 7 12 3 5 17 14 1 10 12 20 16 7 2 20 9 17 16 3 11 10 9 1 11 18
c 19 6 4 19 18 13 2 15
c hord endpoint order END
p circle 20 53
",
        );

        for base_case_n in [1, 2, 4, 8, 16, 19, 20, 128] {
            let summary = solve_dimacs_circle_file(
                &path,
                SolveConfig {
                    base_case_n,
                    input_mode: crate::SosaInputMode::LazyCircleNeighbors,
                    validate_graph: false,
                    ..SolveConfig::default()
                },
            )
            .unwrap();
            assert_eq!(
                summary.status,
                SolveStatus::NotColorable,
                "base_case_n={base_case_n}"
            );
        }
        let _ = fs::remove_file(path);
    }

    #[test]
    fn matches_exhaustive_search_on_random_restricted_circle_graphs() {
        // Random restricted circle graphs (n = 3..9), compared against plain exhaustive search
        // instead of the solver's own base case.
        let mut next = lcg(92_673);
        let mut checks = 0;
        let mut uncolorable = 0;
        for trial in 0..500 {
            let n = 3 + (next() % 7) as usize;
            let word = random_endpoint_word(n, &mut next);
            let allowed = (0..n)
                .map(|_| {
                    if trial % 4 == 0 {
                        ALL_COLORS
                    } else {
                        [3, 5, 6, 7][(next() % 4) as usize]
                    }
                })
                .collect::<Vec<_>>();
            let instance = restricted_instance(&word, &allowed);
            let exact = exhaustively_colorable(&instance);
            uncolorable += usize::from(!exact);
            for input in both_representations(instance) {
                for base_case_n in [1, 2, 3, 4, 5, 6, 8, 128] {
                    assert_eq!(
                        solve_with_threshold(input.clone(), base_case_n),
                        exact,
                        "trial={trial}, word={word:?}, allowed={allowed:?}, \
                         base_case_n={base_case_n}, lazy={}",
                        !input.has_adjacency()
                    );
                    checks += 1;
                }
            }
        }
        assert_eq!(checks, 8_000);
        assert!(uncolorable > 0);
    }

    #[test]
    fn matches_exhaustive_search_on_larger_unrestricted_circle_graphs() {
        let mut next = lcg(20_261_018);
        let mut uncolorable = 0;
        for trial in 0..300 {
            let n = 8 + (next() % 7) as usize;
            let word = random_endpoint_word(n, &mut next);
            let instance = restricted_instance(&word, &vec![ALL_COLORS; n]);
            let exact = exhaustively_colorable(&instance);
            uncolorable += usize::from(!exact);
            for input in both_representations(instance) {
                for base_case_n in [1, 2, 3, 5, 8] {
                    assert_eq!(
                        solve_with_threshold(input.clone(), base_case_n),
                        exact,
                        "trial={trial}, word={word:?}, base_case_n={base_case_n}, lazy={}",
                        !input.has_adjacency()
                    );
                }
            }
        }
        assert!(uncolorable > 0);
    }

    #[test]
    fn full_branch_rejects_partition_that_leaves_a_chord_out() {
        // The first chord runs from L = [0, 1) into T = [1, 2), so it belongs to neither side.
        let instance = restricted_instance(&[0, 0, 1, 1], &[ALL_COLORS; 2]);
        let full = FullySeparatedInstance {
            partition: CirclePartition::new(instance.endpoint_count(), 0, 1, 2, 0).unwrap(),
            instance,
        };

        let error =
            solve_full_branch(full, SolveConfig::default(), &mut Stats::default(), 0).unwrap_err();

        assert!(error.to_string().contains("only 1 of 2 chords"), "{error}");
    }

    fn solve_with_threshold(instance: CircleInstance, base_case_n: usize) -> bool {
        let config = SolveConfig {
            base_case_n,
            ..SolveConfig::default()
        };
        solve_instance_recursively(instance, config, &mut Stats::default(), 0).unwrap()
    }

    /// Builds a lazy-neighbor instance from a zero-based endpoint word and color masks.
    fn restricted_instance(word: &[u32], allowed: &[ColorMask]) -> CircleInstance {
        let mut instance =
            CircleInstance::from_dimacs_geometry_without_adjacency(DimacsCircleGeometry {
                n: allowed.len(),
                m_declared: 0,
                chord_endpoint_order: word.iter().map(|vertex| vertex + 1).collect(),
            })
            .unwrap();
        instance.allowed = allowed.to_vec();
        instance
    }

    fn both_representations(lazy: CircleInstance) -> [CircleInstance; 2] {
        let mut listed = lazy.clone();
        listed.materialize_crossing_adjacency().unwrap();
        [lazy, listed]
    }

    fn lcg(seed: u64) -> impl FnMut() -> u64 {
        let mut state = seed;
        move || {
            state = state
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1);
            state
        }
    }

    fn random_endpoint_word(n: usize, next: &mut impl FnMut() -> u64) -> Vec<u32> {
        let mut word = (0..n as u32).chain(0..n as u32).collect::<Vec<_>>();
        for i in (1..word.len()).rev() {
            let j = (next() % (i + 1) as u64) as usize;
            word.swap(i, j);
        }
        word
    }

    /// Plain depth-first enumeration of list colorings; independent of `base_case`.
    fn exhaustively_colorable(instance: &CircleInstance) -> bool {
        fn extend(instance: &CircleInstance, colors: &mut Vec<ColorMask>) -> bool {
            let vertex = colors.len();
            if vertex == instance.n {
                return true;
            }
            for color in [RED, GREEN, BLUE] {
                let conflicts = (0..vertex).any(|other| {
                    colors[other] == color && instance.crosses(other as u32, vertex as u32)
                });
                if instance.allowed[vertex] & color == 0 || conflicts {
                    continue;
                }
                colors.push(color);
                if extend(instance, colors) {
                    return true;
                }
                colors.pop();
            }
            false
        }
        extend(instance, &mut Vec::with_capacity(instance.n))
    }

    fn write_temp_col(content: &str) -> PathBuf {
        let mut path = std::env::temp_dir();
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        path.push(format!("sosa-native-{nanos}.col"));
        fs::write(&path, content).unwrap();
        path
    }
}
