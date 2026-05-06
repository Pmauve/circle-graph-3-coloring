use std::collections::HashSet;

use crate::reduction::{
    reduce_exhaustively, reduce_exhaustively_with_partition, PartitionedReductionOutcome,
    ReductionOutcome,
};
use crate::stats::Stats;
use circle_core::bitset::BitSet;
use circle_core::colors::{ColorMask, BLUE, GREEN, RED};
use circle_core::error::SosaError;
use circle_core::instance::CircleInstance;
use circle_core::partition::CirclePartition;

const COLOR_BRANCH_ORDER: [ColorMask; 3] = [RED, GREEN, BLUE];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EliminatedSet {
    X,
    Y,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Lemma36Branch {
    pub instance: CircleInstance,
    pub eliminated: EliminatedSet,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Lemma36PartitionedBranch {
    pub instance: CircleInstance,
    pub partition: CirclePartition,
    pub eliminated: EliminatedSet,
}

pub fn visit_lemma_36_family<F>(
    instance: &CircleInstance,
    x_vertices: &BitSet,
    y_vertices: &BitSet,
    stats: &mut Stats,
    mut visit: F,
) -> Result<bool, SosaError>
where
    F: FnMut(Lemma36Branch, &mut Stats) -> Result<bool, SosaError>,
{
    stats.lemma_36_calls += 1;
    let mut seen = HashSet::new();

    if !contains_internal_edge(instance, x_vertices) {
        let should_stop = visit_monochromatic_branches(
            instance,
            x_vertices,
            EliminatedSet::X,
            &mut seen,
            stats,
            &mut visit,
        )?;
        if should_stop {
            return Ok(true);
        }
    }

    if !contains_internal_edge(instance, y_vertices) {
        let should_stop = visit_monochromatic_branches(
            instance,
            y_vertices,
            EliminatedSet::Y,
            &mut seen,
            stats,
            &mut visit,
        )?;
        if should_stop {
            return Ok(true);
        }
    }

    Ok(false)
}

pub fn visit_lemma_36_family_with_partition<F>(
    instance: &CircleInstance,
    x_partition: &CirclePartition,
    y_partition: &CirclePartition,
    x_vertices: &BitSet,
    y_vertices: &BitSet,
    stats: &mut Stats,
    mut visit: F,
) -> Result<bool, SosaError>
where
    F: FnMut(Lemma36PartitionedBranch, &mut Stats) -> Result<bool, SosaError>,
{
    stats.lemma_36_calls += 1;
    let mut seen = HashSet::new();

    if !contains_internal_edge(instance, x_vertices) {
        let should_stop = visit_partitioned_monochromatic_branches(
            instance,
            x_partition,
            x_vertices,
            EliminatedSet::X,
            &mut seen,
            stats,
            &mut visit,
        )?;
        if should_stop {
            return Ok(true);
        }
    }

    if !contains_internal_edge(instance, y_vertices) {
        let should_stop = visit_partitioned_monochromatic_branches(
            instance,
            y_partition,
            y_vertices,
            EliminatedSet::Y,
            &mut seen,
            stats,
            &mut visit,
        )?;
        if should_stop {
            return Ok(true);
        }
    }

    Ok(false)
}

fn visit_monochromatic_branches<F>(
    instance: &CircleInstance,
    vertices: &BitSet,
    eliminated: EliminatedSet,
    seen: &mut HashSet<CircleInstance>,
    stats: &mut Stats,
    visit: &mut F,
) -> Result<bool, SosaError>
where
    F: FnMut(Lemma36Branch, &mut Stats) -> Result<bool, SosaError>,
{
    let target_vertices = vertices.iter_ones().collect::<Vec<_>>();
    for color_mask in COLOR_BRANCH_ORDER {
        if target_vertices
            .iter()
            .any(|&vertex| instance.allowed[vertex] & color_mask == 0)
        {
            continue;
        }

        let mut branch = instance.clone();
        for &vertex in &target_vertices {
            branch.allowed[vertex] = color_mask;
        }

        let reduced = match reduce_exhaustively(branch, stats)? {
            ReductionOutcome::Conflict => continue,
            ReductionOutcome::Consistent(instance) => instance,
        };
        if seen.insert(reduced.clone())
            && visit(
                Lemma36Branch {
                    instance: reduced,
                    eliminated,
                },
                stats,
            )?
        {
            return Ok(true);
        }
    }
    Ok(false)
}

fn visit_partitioned_monochromatic_branches<F>(
    instance: &CircleInstance,
    partition: &CirclePartition,
    vertices: &BitSet,
    eliminated: EliminatedSet,
    seen: &mut HashSet<(CircleInstance, CirclePartition)>,
    stats: &mut Stats,
    visit: &mut F,
) -> Result<bool, SosaError>
where
    F: FnMut(Lemma36PartitionedBranch, &mut Stats) -> Result<bool, SosaError>,
{
    let target_vertices = vertices.iter_ones().collect::<Vec<_>>();
    for color_mask in COLOR_BRANCH_ORDER {
        if target_vertices
            .iter()
            .any(|&vertex| instance.allowed[vertex] & color_mask == 0)
        {
            continue;
        }

        let mut branch = instance.clone();
        for &vertex in &target_vertices {
            branch.allowed[vertex] = color_mask;
        }

        let (reduced, reduced_partition) =
            match reduce_exhaustively_with_partition(branch, partition, stats)? {
                PartitionedReductionOutcome::Conflict => continue,
                PartitionedReductionOutcome::Consistent {
                    instance,
                    partition,
                } => (instance, partition),
            };
        if seen.insert((reduced.clone(), reduced_partition.clone()))
            && visit(
                Lemma36PartitionedBranch {
                    instance: reduced,
                    partition: reduced_partition,
                    eliminated,
                },
                stats,
            )?
        {
            return Ok(true);
        }
    }
    Ok(false)
}

fn contains_internal_edge(instance: &CircleInstance, vertices: &BitSet) -> bool {
    for vertex in vertices.iter_ones() {
        for &neighbor in instance.neighbors(vertex as u32) {
            if vertices.get(neighbor as usize) {
                return true;
            }
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use circle_core::dimacs_circle::parse_dimacs_circle;

    use super::*;

    #[test]
    fn branches_on_independent_set_and_reduces_it_away() {
        let instance = instance_from_text(
            "\
c ircle representation START
c 1 2 1 2
c ircle representation END
p edge 2 1
e 1 2
",
        );
        let mut x = BitSet::empty(instance.n);
        x.set(0, true);
        let y = BitSet::full(instance.n);
        let mut branches = Vec::new();

        visit_lemma_36_family(&instance, &x, &y, &mut Stats::default(), |branch, _| {
            branches.push(branch);
            Ok(false)
        })
        .unwrap();

        assert_eq!(branches.len(), 3);
        assert!(branches.iter().all(|branch| branch.instance.n == 1));
        assert!(branches
            .iter()
            .all(|branch| branch.eliminated == EliminatedSet::X));
    }

    #[test]
    fn skips_non_independent_target_set() {
        let instance = instance_from_text(
            "\
c ircle representation START
c 1 2 1 2
c ircle representation END
p edge 2 1
e 1 2
",
        );
        let x = BitSet::full(instance.n);
        let y = BitSet::empty(instance.n);
        let mut count = 0;

        visit_lemma_36_family(&instance, &x, &y, &mut Stats::default(), |_, _| {
            count += 1;
            Ok(false)
        })
        .unwrap();

        assert_eq!(count, 1);
    }

    fn instance_from_text(text: &str) -> CircleInstance {
        CircleInstance::from_dimacs(parse_dimacs_circle(text).unwrap()).unwrap()
    }
}
