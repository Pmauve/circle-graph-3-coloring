use std::collections::HashSet;

use crate::arc_ops::{advance_boundary_inside_arc, chords_between_arcs, count_endpoints_in_arc};
use crate::lemma_36::{visit_lemma_36_family_with_partition, EliminatedSet};
use crate::lemma_37::{visit_lemma_37_family, SemiSeparatedInstance};
use crate::stats::Stats;
use circle_core::bitset::BitSet;
use circle_core::error::SosaError;
use circle_core::instance::CircleInstance;
use circle_core::partition::{ArcName, CirclePartition};

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub struct FullySeparatedInstance {
    pub instance: CircleInstance,
    pub partition: CirclePartition,
}

pub fn visit_lemma_33_family<F>(
    instance: &CircleInstance,
    stats: &mut Stats,
    mut visit: F,
) -> Result<bool, SosaError>
where
    F: FnMut(FullySeparatedInstance, &mut Stats) -> Result<bool, SosaError>,
{
    stats.lemma_33_calls += 1;
    let mut seen = HashSet::new();
    visit_lemma_37_family(instance, stats, |semi, stats| {
        visit_lemma_38_family(&semi, stats, |full, stats| {
            if seen.insert(full.clone()) {
                return visit(full, stats);
            }
            Ok(false)
        })
    })
}

pub fn visit_lemma_38_family<F>(
    semi: &SemiSeparatedInstance,
    stats: &mut Stats,
    mut visit: F,
) -> Result<bool, SosaError>
where
    F: FnMut(FullySeparatedInstance, &mut Stats) -> Result<bool, SosaError>,
{
    stats.lemma_38_calls += 1;
    let mut seen = HashSet::new();
    visit_lemma_38_recursive(semi, stats, &mut seen, &mut visit)
}

pub fn is_fully_separated_instance(full: &FullySeparatedInstance) -> bool {
    full.partition.top_boundary == full.partition.right_boundary
        && full.partition.bottom_boundary == full.partition.left_boundary
        && chords_between_arcs(
            &full.instance,
            &full.partition,
            ArcName::L,
            &full.partition,
            ArcName::R,
        )
        .count_ones()
            == 0
}

fn visit_lemma_38_recursive<F>(
    semi: &SemiSeparatedInstance,
    stats: &mut Stats,
    seen: &mut HashSet<FullySeparatedInstance>,
    visit: &mut F,
) -> Result<bool, SosaError>
where
    F: FnMut(FullySeparatedInstance, &mut Stats) -> Result<bool, SosaError>,
{
    let (chosen_arc, x) = choose_x_arc(&semi.instance, &semi.partition);

    if x == 0 {
        let full = FullySeparatedInstance {
            instance: semi.instance.clone(),
            partition: collapse_empty_top_and_bottom(&semi.partition)?,
        };
        if seen.insert(full.clone()) {
            return visit(full, stats);
        }
        return Ok(false);
    }

    if x == 1 {
        let next_partition =
            partition_for_single_endpoint_case(&semi.instance, &semi.partition, chosen_arc)?;
        return visit_lemma_38_recursive(
            &SemiSeparatedInstance {
                instance: semi.instance.clone(),
                partition: next_partition,
            },
            stats,
            seen,
            visit,
        );
    }

    let (x_left, x_right) = split_x_arc(&semi.instance, &semi.partition, chosen_arc, x)?;
    let (h_left, h_right) = split_chord_sets(&semi.instance, &semi.partition, &x_left, &x_right);

    let x_parent_partition = partition_after_split_branch(
        &semi.partition,
        chosen_arc,
        &x_left,
        &x_right,
        &EliminatedSet::X,
    )?;
    let y_parent_partition = partition_after_split_branch(
        &semi.partition,
        chosen_arc,
        &x_left,
        &x_right,
        &EliminatedSet::Y,
    )?;

    visit_lemma_36_family_with_partition(
        &semi.instance,
        &x_parent_partition,
        &y_parent_partition,
        &h_left,
        &h_right,
        stats,
        |branch, stats| {
            visit_lemma_38_recursive(
                &SemiSeparatedInstance {
                    instance: branch.instance,
                    partition: branch.partition,
                },
                stats,
                seen,
                visit,
            )
        },
    )
}

fn choose_x_arc(instance: &CircleInstance, partition: &CirclePartition) -> (ArcName, usize) {
    let top_count = count_endpoints_in_arc(instance, partition, ArcName::T);
    let bottom_count = count_endpoints_in_arc(instance, partition, ArcName::B);
    if top_count >= bottom_count {
        (ArcName::T, top_count)
    } else {
        (ArcName::B, bottom_count)
    }
}

fn collapse_empty_top_and_bottom(
    partition: &CirclePartition,
) -> Result<CirclePartition, SosaError> {
    CirclePartition::new(
        partition.n_endpoints,
        partition.left_boundary,
        partition.right_boundary,
        partition.right_boundary,
        partition.left_boundary,
    )
}

fn partition_for_single_endpoint_case(
    instance: &CircleInstance,
    partition: &CirclePartition,
    chosen_arc: ArcName,
) -> Result<CirclePartition, SosaError> {
    let h_lx = chords_between_arcs(instance, partition, ArcName::L, partition, chosen_arc);
    let h_xr = chords_between_arcs(instance, partition, chosen_arc, partition, ArcName::R);
    match chosen_arc {
        ArcName::T if h_lx.count_ones() == 0 => CirclePartition::new(
            partition.n_endpoints,
            partition.left_boundary,
            partition.top_boundary,
            partition.top_boundary,
            partition.bottom_boundary,
        ),
        ArcName::T if h_xr.count_ones() == 0 => CirclePartition::new(
            partition.n_endpoints,
            partition.left_boundary,
            partition.right_boundary,
            partition.right_boundary,
            partition.bottom_boundary,
        ),
        ArcName::B if h_lx.count_ones() == 0 => CirclePartition::new(
            partition.n_endpoints,
            partition.left_boundary,
            partition.top_boundary,
            partition.right_boundary,
            partition.left_boundary,
        ),
        ArcName::B if h_xr.count_ones() == 0 => CirclePartition::new(
            partition.n_endpoints,
            partition.bottom_boundary,
            partition.top_boundary,
            partition.right_boundary,
            partition.bottom_boundary,
        ),
        _ => Err(SosaError::Internal(
            "Lemma 3.8 single-endpoint case could not choose an empty side".to_string(),
        )),
    }
}

fn split_x_arc(
    instance: &CircleInstance,
    partition: &CirclePartition,
    chosen_arc: ArcName,
    x: usize,
) -> Result<(CirclePartition, CirclePartition), SosaError> {
    match chosen_arc {
        ArcName::T => {
            let x_left_size = x.div_ceil(2);
            let split_boundary =
                advance_boundary_inside_arc(instance, partition, ArcName::T, x_left_size)?;
            Ok((
                CirclePartition::new(
                    partition.n_endpoints,
                    partition.top_boundary,
                    split_boundary,
                    split_boundary,
                    partition.top_boundary,
                )?,
                CirclePartition::new(
                    partition.n_endpoints,
                    split_boundary,
                    partition.right_boundary,
                    partition.right_boundary,
                    split_boundary,
                )?,
            ))
        }
        ArcName::B => {
            let x_right_size = x / 2;
            let split_boundary =
                advance_boundary_inside_arc(instance, partition, ArcName::B, x_right_size)?;
            Ok((
                CirclePartition::new(
                    partition.n_endpoints,
                    split_boundary,
                    partition.left_boundary,
                    partition.left_boundary,
                    split_boundary,
                )?,
                CirclePartition::new(
                    partition.n_endpoints,
                    partition.bottom_boundary,
                    split_boundary,
                    split_boundary,
                    partition.bottom_boundary,
                )?,
            ))
        }
        _ => Err(SosaError::Internal(
            "Lemma 3.8 only splits T or B".to_string(),
        )),
    }
}

fn split_chord_sets(
    instance: &CircleInstance,
    partition: &CirclePartition,
    x_left: &CirclePartition,
    x_right: &CirclePartition,
) -> (BitSet, BitSet) {
    (
        chords_between_arcs(instance, partition, ArcName::L, x_right, ArcName::L),
        chords_between_arcs(instance, x_left, ArcName::L, partition, ArcName::R),
    )
}

fn partition_after_split_branch(
    partition: &CirclePartition,
    chosen_arc: ArcName,
    x_left: &CirclePartition,
    x_right: &CirclePartition,
    eliminated: &EliminatedSet,
) -> Result<CirclePartition, SosaError> {
    match (chosen_arc, eliminated) {
        (ArcName::T, EliminatedSet::X) => CirclePartition::new(
            partition.n_endpoints,
            partition.left_boundary,
            partition.top_boundary,
            x_right.left_boundary,
            partition.bottom_boundary,
        ),
        (ArcName::T, EliminatedSet::Y) => CirclePartition::new(
            partition.n_endpoints,
            partition.left_boundary,
            x_left.top_boundary,
            partition.right_boundary,
            partition.bottom_boundary,
        ),
        (ArcName::B, EliminatedSet::X) => CirclePartition::new(
            partition.n_endpoints,
            partition.left_boundary,
            partition.top_boundary,
            partition.right_boundary,
            x_left.left_boundary,
        ),
        (ArcName::B, EliminatedSet::Y) => CirclePartition::new(
            partition.n_endpoints,
            x_left.left_boundary,
            partition.top_boundary,
            partition.right_boundary,
            partition.bottom_boundary,
        ),
        _ => Err(SosaError::Internal(
            "Lemma 3.8 split branch must eliminate H_L or H_R".to_string(),
        )),
    }
}

#[cfg(test)]
mod tests {
    use circle_core::dimacs_circle::parse_dimacs_circle;

    use super::*;

    #[test]
    fn lemma_33_visits_fully_separated_instances() {
        let instance = instance_from_text(
            "\
c ircle representation START
c 1 2 3 1 2 3
c ircle representation END
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        );
        let mut branches = Vec::new();

        visit_lemma_33_family(&instance, &mut Stats::default(), |full, _| {
            branches.push(full);
            Ok(false)
        })
        .unwrap();

        assert!(!branches.is_empty());
        assert!(branches.iter().all(is_fully_separated_instance));
    }

    fn instance_from_text(text: &str) -> CircleInstance {
        CircleInstance::from_dimacs(parse_dimacs_circle(text).unwrap()).unwrap()
    }
}
