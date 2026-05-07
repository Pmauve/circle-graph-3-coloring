use std::collections::HashSet;

use crate::reduction::{
    reduce_allowed, reduce_allowed_with_partition, PartitionedReductionOutcome, ReductionOutcome,
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

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub(crate) struct InstanceDedupKey {
    endpoint_at: Vec<u32>,
    allowed: Vec<ColorMask>,
}

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub(crate) struct PartitionedInstanceDedupKey {
    instance: InstanceDedupKey,
    partition: PartitionDedupKey,
}

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub(crate) struct PartitionDedupKey {
    n_endpoints: usize,
    left_boundary: usize,
    top_boundary: usize,
    right_boundary: usize,
    bottom_boundary: usize,
}

impl InstanceDedupKey {
    pub(crate) fn from_instance(instance: &CircleInstance) -> Self {
        Self {
            endpoint_at: instance.endpoint_at.clone(),
            allowed: instance.allowed.clone(),
        }
    }
}

impl PartitionDedupKey {
    pub(crate) fn from_partition(partition: &CirclePartition) -> Self {
        Self {
            n_endpoints: partition.n_endpoints,
            left_boundary: partition.left_boundary,
            top_boundary: partition.top_boundary,
            right_boundary: partition.right_boundary,
            bottom_boundary: partition.bottom_boundary,
        }
    }
}

impl PartitionedInstanceDedupKey {
    pub(crate) fn from_parts(instance: &CircleInstance, partition: &CirclePartition) -> Self {
        Self {
            instance: InstanceDedupKey::from_instance(instance),
            partition: PartitionDedupKey::from_partition(partition),
        }
    }
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
    seen: &mut HashSet<InstanceDedupKey>,
    stats: &mut Stats,
    visit: &mut F,
) -> Result<bool, SosaError>
where
    F: FnMut(Lemma36Branch, &mut Stats) -> Result<bool, SosaError>,
{
    let started_at = stats.start_timer();
    let target_vertices = vertices.iter_ones().collect::<Vec<_>>();
    record_lemma_36_setup_time(stats, started_at);
    for color_mask in COLOR_BRANCH_ORDER {
        let started_at = stats.start_timer();
        if target_vertices
            .iter()
            .any(|&vertex| instance.allowed[vertex] & color_mask == 0)
        {
            record_lemma_36_setup_time(stats, started_at);
            continue;
        }

        let mut allowed = instance.allowed.clone();
        for &vertex in &target_vertices {
            allowed[vertex] = color_mask;
        }
        record_lemma_36_setup_time(stats, started_at);

        let started_at = stats.start_timer();
        let reduced = match reduce_allowed(instance, allowed, stats)? {
            ReductionOutcome::Conflict => {
                record_lemma_36_reduction_time(stats, started_at);
                continue;
            }
            ReductionOutcome::Consistent(instance) => instance,
        };
        record_lemma_36_reduction_time(stats, started_at);

        let started_at = stats.start_timer();
        let branch = if seen.insert(InstanceDedupKey::from_instance(&reduced)) {
            Some(Lemma36Branch {
                instance: reduced,
                eliminated,
            })
        } else {
            None
        };
        record_lemma_36_dedup_time(stats, started_at);
        if let Some(branch) = branch {
            if visit(branch, stats)? {
                return Ok(true);
            }
        }
    }
    Ok(false)
}

fn visit_partitioned_monochromatic_branches<F>(
    instance: &CircleInstance,
    partition: &CirclePartition,
    vertices: &BitSet,
    eliminated: EliminatedSet,
    seen: &mut HashSet<PartitionedInstanceDedupKey>,
    stats: &mut Stats,
    visit: &mut F,
) -> Result<bool, SosaError>
where
    F: FnMut(Lemma36PartitionedBranch, &mut Stats) -> Result<bool, SosaError>,
{
    let started_at = stats.start_timer();
    let target_vertices = vertices.iter_ones().collect::<Vec<_>>();
    record_lemma_36_setup_time(stats, started_at);
    for color_mask in COLOR_BRANCH_ORDER {
        let started_at = stats.start_timer();
        if target_vertices
            .iter()
            .any(|&vertex| instance.allowed[vertex] & color_mask == 0)
        {
            record_lemma_36_setup_time(stats, started_at);
            continue;
        }

        let mut allowed = instance.allowed.clone();
        for &vertex in &target_vertices {
            allowed[vertex] = color_mask;
        }
        record_lemma_36_setup_time(stats, started_at);

        let started_at = stats.start_timer();
        let (reduced, reduced_partition) =
            match reduce_allowed_with_partition(instance, allowed, partition, stats)? {
                PartitionedReductionOutcome::Conflict => {
                    record_lemma_36_reduction_time(stats, started_at);
                    continue;
                }
                PartitionedReductionOutcome::Consistent {
                    instance,
                    partition,
                } => (instance, partition),
            };
        record_lemma_36_reduction_time(stats, started_at);

        let started_at = stats.start_timer();
        let branch = if seen.insert(PartitionedInstanceDedupKey::from_parts(
            &reduced,
            &reduced_partition,
        )) {
            Some(Lemma36PartitionedBranch {
                instance: reduced,
                partition: reduced_partition,
                eliminated,
            })
        } else {
            None
        };
        record_lemma_36_dedup_time(stats, started_at);
        if let Some(branch) = branch {
            if visit(branch, stats)? {
                return Ok(true);
            }
        }
    }
    Ok(false)
}

fn record_lemma_36_setup_time(stats: &mut Stats, started_at: Option<std::time::Instant>) {
    let elapsed = Stats::elapsed_ns(started_at);
    stats.lemma_36_branch_setup_time_ns += elapsed;
    stats.lemma_36_time_ns += elapsed;
}

fn record_lemma_36_reduction_time(stats: &mut Stats, started_at: Option<std::time::Instant>) {
    let elapsed = Stats::elapsed_ns(started_at);
    stats.lemma_36_reduction_time_ns += elapsed;
    stats.lemma_36_time_ns += elapsed;
}

fn record_lemma_36_dedup_time(stats: &mut Stats, started_at: Option<std::time::Instant>) {
    let elapsed = Stats::elapsed_ns(started_at);
    stats.lemma_36_dedup_time_ns += elapsed;
    stats.lemma_36_time_ns += elapsed;
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
