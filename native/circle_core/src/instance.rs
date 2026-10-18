use std::collections::HashSet;

use crate::bitset::BitSet;
use crate::colors::{ColorMask, ALL_COLORS};
use crate::dimacs_circle::{DimacsCircle, DimacsCircleGeometry};
use crate::error::SosaError;
use crate::partition::CirclePartition;

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub struct CircleInstance {
    pub n: usize,
    pub endpoint_at: Vec<u32>,
    pub left: Vec<u32>,
    pub right: Vec<u32>,
    pub adj_offsets: Vec<u32>,
    pub adj: Vec<u32>,
    pub allowed: Vec<ColorMask>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ListedEdgeMode {
    Strict,
    Trusted,
}

impl CircleInstance {
    pub fn from_dimacs(dimacs: DimacsCircle) -> Result<Self, SosaError> {
        Self::from_dimacs_with_crossing_validation(dimacs, true)
    }

    pub fn from_dimacs_with_crossing_validation(
        dimacs: DimacsCircle,
        validate_crossings: bool,
    ) -> Result<Self, SosaError> {
        Self::from_dimacs_with_listed_edge_mode(dimacs, validate_crossings, ListedEdgeMode::Strict)
    }

    pub fn from_dimacs_with_listed_edge_mode(
        dimacs: DimacsCircle,
        validate_crossings: bool,
        listed_edge_mode: ListedEdgeMode,
    ) -> Result<Self, SosaError> {
        let (endpoint_at, left, right) =
            build_endpoint_geometry(dimacs.n, &dimacs.chord_endpoint_order)?;
        let edges = match listed_edge_mode {
            ListedEdgeMode::Strict => normalize_edges_strict(dimacs.n, dimacs.edges)?,
            ListedEdgeMode::Trusted => normalize_edges_trusted(dimacs.n, dimacs.edges)?,
        };

        let sort_neighbors = listed_edge_mode == ListedEdgeMode::Strict;
        let instance = Self::from_parts_with_neighbor_sort(
            dimacs.n,
            endpoint_at,
            left,
            right,
            &edges,
            vec![ALL_COLORS; dimacs.n],
            sort_neighbors,
        )?;
        if validate_crossings {
            instance.validate_edge_crossings(&edges)?;
        }
        Ok(instance)
    }

    pub fn from_dimacs_geometry_without_adjacency(
        geometry: DimacsCircleGeometry,
    ) -> Result<Self, SosaError> {
        let (endpoint_at, left, right) =
            build_endpoint_geometry(geometry.n, &geometry.chord_endpoint_order)?;

        Ok(Self {
            n: geometry.n,
            endpoint_at,
            left,
            right,
            adj_offsets: Vec::new(),
            adj: Vec::new(),
            allowed: vec![ALL_COLORS; geometry.n],
        })
    }
}

fn build_endpoint_geometry(
    n: usize,
    chord_endpoint_order: &[u32],
) -> Result<(Vec<u32>, Vec<u32>, Vec<u32>), SosaError> {
    let endpoint_count = 2 * n;
    let mut endpoint_at = Vec::with_capacity(endpoint_count);
    let mut left = vec![u32::MAX; n];
    let mut right = vec![u32::MAX; n];

    for (position, &dimacs_id) in chord_endpoint_order.iter().enumerate() {
        let vertex = dimacs_id - 1;
        endpoint_at.push(vertex);
        let slot = &mut left[vertex as usize];
        if *slot == u32::MAX {
            *slot = position as u32;
        } else {
            right[vertex as usize] = position as u32;
        }
    }

    for vertex in 0..n {
        if left[vertex] == u32::MAX || right[vertex] == u32::MAX {
            return Err(SosaError::Input(format!(
                "vertex {} does not have exactly two endpoints",
                vertex + 1
            )));
        }
    }
    Ok((endpoint_at, left, right))
}

impl CircleInstance {
    pub fn from_parts(
        n: usize,
        endpoint_at: Vec<u32>,
        left: Vec<u32>,
        right: Vec<u32>,
        edges: &[(u32, u32)],
        allowed: Vec<ColorMask>,
    ) -> Result<Self, SosaError> {
        Self::from_parts_with_neighbor_sort(n, endpoint_at, left, right, edges, allowed, true)
    }

    fn from_parts_with_neighbor_sort(
        n: usize,
        endpoint_at: Vec<u32>,
        left: Vec<u32>,
        right: Vec<u32>,
        edges: &[(u32, u32)],
        allowed: Vec<ColorMask>,
        sort_neighbors: bool,
    ) -> Result<Self, SosaError> {
        let (adj_offsets, adj) = build_csr(n, edges, sort_neighbors)?;
        Ok(Self {
            n,
            endpoint_at,
            left,
            right,
            adj_offsets,
            adj,
            allowed,
        })
    }

    pub fn endpoint_count(&self) -> usize {
        self.endpoint_at.len()
    }

    pub fn neighbors(&self, vertex: u32) -> &[u32] {
        assert!(self.has_adjacency(), "adjacency has not been materialized");
        let start = self.adj_offsets[vertex as usize] as usize;
        let end = self.adj_offsets[vertex as usize + 1] as usize;
        &self.adj[start..end]
    }

    pub fn has_adjacency(&self) -> bool {
        self.adj_offsets.len() == self.n + 1
    }

    pub fn materialize_crossing_adjacency(&mut self) -> Result<(), SosaError> {
        if self.has_adjacency() {
            return Ok(());
        }
        let mut edges = Vec::new();
        for u in 0..self.n as u32 {
            for v in (u + 1)..self.n as u32 {
                if self.crosses(u, v) {
                    edges.push((u, v));
                }
            }
        }
        let (adj_offsets, adj) = build_csr(self.n, &edges, true)?;
        self.adj_offsets = adj_offsets;
        self.adj = adj;
        Ok(())
    }

    pub fn degree(&self, vertex: u32) -> usize {
        self.neighbors(vertex).len()
    }

    pub fn crosses(&self, a: u32, b: u32) -> bool {
        let a_left = self.left[a as usize];
        let a_right = self.right[a as usize];
        let b_left = self.left[b as usize];
        let b_right = self.right[b as usize];
        (a_left < b_left && b_left < a_right && a_right < b_right)
            || (b_left < a_left && a_left < b_right && b_right < a_right)
    }

    pub fn rebuild_from_active(
        &self,
        active: &BitSet,
        allowed: Vec<ColorMask>,
    ) -> Result<CircleInstance, SosaError> {
        if active.len() != self.n || allowed.len() != self.n {
            return Err(SosaError::Internal(
                "active mask and allowed colors must match instance size".to_string(),
            ));
        }

        let mut old_to_new = vec![u32::MAX; self.n];
        let mut new_n = 0usize;
        for old_vertex in active.iter_ones() {
            old_to_new[old_vertex] = new_n as u32;
            new_n += 1;
        }

        let mut endpoint_at = Vec::with_capacity(2 * new_n);
        let mut left = vec![u32::MAX; new_n];
        let mut right = vec![u32::MAX; new_n];
        for &old_vertex in &self.endpoint_at {
            let new_vertex = old_to_new[old_vertex as usize];
            if new_vertex == u32::MAX {
                continue;
            }
            let new_position = endpoint_at.len() as u32;
            endpoint_at.push(new_vertex);
            let left_slot = &mut left[new_vertex as usize];
            if *left_slot == u32::MAX {
                *left_slot = new_position;
            } else {
                right[new_vertex as usize] = new_position;
            }
        }

        for vertex in 0..new_n {
            if left[vertex] == u32::MAX || right[vertex] == u32::MAX {
                return Err(SosaError::Internal(format!(
                    "active vertex {vertex} does not have exactly two rebuilt endpoints"
                )));
            }
        }

        let (adj_offsets, adj) = if self.has_adjacency() {
            self.rebuild_csr_from_active(active, &old_to_new, new_n)?
        } else {
            (Vec::new(), Vec::new())
        };
        let mut rebuilt_allowed = Vec::with_capacity(new_n);
        for old_vertex in active.iter_ones() {
            rebuilt_allowed.push(allowed[old_vertex]);
        }

        Ok(Self {
            n: new_n,
            endpoint_at,
            left,
            right,
            adj_offsets,
            adj,
            allowed: rebuilt_allowed,
        })
    }

    pub fn rebuild_from_active_with_partition(
        &self,
        active: &BitSet,
        allowed: Vec<ColorMask>,
        partition: &CirclePartition,
    ) -> Result<(CircleInstance, CirclePartition), SosaError> {
        if partition.n_endpoints != self.endpoint_count() {
            return Err(SosaError::Internal(
                "partition endpoint count must match instance endpoint count".to_string(),
            ));
        }
        if active.len() != self.n || allowed.len() != self.n {
            return Err(SosaError::Internal(
                "active mask and allowed colors must match instance size".to_string(),
            ));
        }

        let mut old_to_new = vec![u32::MAX; self.n];
        let mut new_n = 0usize;
        for old_vertex in active.iter_ones() {
            old_to_new[old_vertex] = new_n as u32;
            new_n += 1;
        }

        let new_endpoint_count = 2 * new_n;
        let old_boundaries = [
            partition.left_boundary,
            partition.top_boundary,
            partition.right_boundary,
            partition.bottom_boundary,
        ];
        let mut new_boundaries = [usize::MAX; 4];

        let mut endpoint_at = Vec::with_capacity(new_endpoint_count);
        let mut left = vec![u32::MAX; new_n];
        let mut right = vec![u32::MAX; new_n];
        for (old_position, &old_vertex) in self.endpoint_at.iter().enumerate() {
            for (boundary_index, &old_boundary) in old_boundaries.iter().enumerate() {
                if old_position == old_boundary {
                    new_boundaries[boundary_index] = if new_endpoint_count == 0 {
                        0
                    } else {
                        endpoint_at.len() % new_endpoint_count
                    };
                }
            }

            let new_vertex = old_to_new[old_vertex as usize];
            if new_vertex == u32::MAX {
                continue;
            }
            let new_position = endpoint_at.len() as u32;
            endpoint_at.push(new_vertex);
            let left_slot = &mut left[new_vertex as usize];
            if *left_slot == u32::MAX {
                *left_slot = new_position;
            } else {
                right[new_vertex as usize] = new_position;
            }
        }
        for boundary in &mut new_boundaries {
            if *boundary == usize::MAX {
                *boundary = 0;
            }
        }

        for vertex in 0..new_n {
            if left[vertex] == u32::MAX || right[vertex] == u32::MAX {
                return Err(SosaError::Internal(format!(
                    "active vertex {vertex} does not have exactly two rebuilt endpoints"
                )));
            }
        }

        let (adj_offsets, adj) = if self.has_adjacency() {
            self.rebuild_csr_from_active(active, &old_to_new, new_n)?
        } else {
            (Vec::new(), Vec::new())
        };
        let mut rebuilt_allowed = Vec::with_capacity(new_n);
        for old_vertex in active.iter_ones() {
            rebuilt_allowed.push(allowed[old_vertex]);
        }

        let rebuilt = Self {
            n: new_n,
            endpoint_at,
            left,
            right,
            adj_offsets,
            adj,
            allowed: rebuilt_allowed,
        };
        let collapsed = new_endpoint_count > 0
            && new_boundaries
                .iter()
                .all(|&boundary| boundary == new_boundaries[0]);
        let rebuilt_partition = if collapsed {
            // All surviving endpoints came from one old arc, which now covers the whole circle.
            let survivor = active
                .iter_ones()
                .next()
                .expect("a non-empty rebuilt instance has an active vertex");
            let full_arc = partition
                .endpoint_arc(self.left[survivor] as usize)
                .ok_or_else(|| {
                    SosaError::Internal(format!(
                        "endpoint {} of vertex {survivor} lies in no partition arc",
                        self.left[survivor]
                    ))
                })?;
            CirclePartition::new_full_arc(new_endpoint_count, new_boundaries[0], full_arc)?
        } else {
            CirclePartition::new(
                new_endpoint_count,
                new_boundaries[0],
                new_boundaries[1],
                new_boundaries[2],
                new_boundaries[3],
            )?
        };
        Ok((rebuilt, rebuilt_partition))
    }

    fn rebuild_csr_from_active(
        &self,
        active: &BitSet,
        old_to_new: &[u32],
        new_n: usize,
    ) -> Result<(Vec<u32>, Vec<u32>), SosaError> {
        let mut degree = vec![0usize; new_n];
        for old_u in active.iter_ones() {
            let new_u = old_to_new[old_u] as usize;
            for &old_v in self.neighbors(old_u as u32) {
                let new_v = old_to_new[old_v as usize];
                if new_v != u32::MAX {
                    degree[new_u] += 1;
                }
            }
        }

        let mut adj_offsets = Vec::with_capacity(new_n + 1);
        adj_offsets.push(0);
        for count in degree {
            let next = *adj_offsets.last().unwrap() as usize + count;
            adj_offsets.push(next as u32);
        }

        let mut cursor = adj_offsets[..new_n].to_vec();
        let mut adj = vec![0u32; *adj_offsets.last().unwrap() as usize];
        for old_u in active.iter_ones() {
            let new_u = old_to_new[old_u] as usize;
            for &old_v in self.neighbors(old_u as u32) {
                let new_v = old_to_new[old_v as usize];
                if new_v == u32::MAX {
                    continue;
                }
                let index = cursor[new_u] as usize;
                adj[index] = new_v;
                cursor[new_u] += 1;
            }
        }

        Ok((adj_offsets, adj))
    }

    fn validate_edge_crossings(&self, edges: &[(u32, u32)]) -> Result<(), SosaError> {
        let edge_set: HashSet<(u32, u32)> = edges.iter().copied().collect();
        for &(u, v) in edges {
            if !self.crosses(u, v) {
                return Err(SosaError::Input(format!(
                    "declared edge {} {} does not match a chord crossing",
                    u + 1,
                    v + 1
                )));
            }
        }
        for u in 0..self.n as u32 {
            for v in (u + 1)..self.n as u32 {
                if self.crosses(u, v) && !edge_set.contains(&(u, v)) {
                    return Err(SosaError::Input(format!(
                        "missing edge for crossing chords {} {}",
                        u + 1,
                        v + 1
                    )));
                }
            }
        }
        Ok(())
    }
}

fn build_csr(
    n: usize,
    edges: &[(u32, u32)],
    sort_neighbors: bool,
) -> Result<(Vec<u32>, Vec<u32>), SosaError> {
    let mut degree = vec![0usize; n];
    for &(u, v) in edges {
        if u as usize >= n || v as usize >= n {
            return Err(SosaError::Input(
                "edge endpoint outside local vertex range".to_string(),
            ));
        }
        degree[u as usize] += 1;
        degree[v as usize] += 1;
    }

    let mut adj_offsets = Vec::with_capacity(n + 1);
    adj_offsets.push(0);
    for count in degree {
        let next = *adj_offsets.last().unwrap() as usize + count;
        adj_offsets.push(next as u32);
    }

    let mut cursor = adj_offsets[..n].to_vec();
    let mut adj = vec![0u32; *adj_offsets.last().unwrap() as usize];
    for &(u, v) in edges {
        let u_index = cursor[u as usize] as usize;
        adj[u_index] = v;
        cursor[u as usize] += 1;
        let v_index = cursor[v as usize] as usize;
        adj[v_index] = u;
        cursor[v as usize] += 1;
    }
    if sort_neighbors {
        for vertex in 0..n {
            let start = adj_offsets[vertex] as usize;
            let end = adj_offsets[vertex + 1] as usize;
            adj[start..end].sort_unstable();
        }
    }
    Ok((adj_offsets, adj))
}

fn normalize_edges_strict(
    n: usize,
    raw_edges: Vec<(u32, u32)>,
) -> Result<Vec<(u32, u32)>, SosaError> {
    let mut edges = Vec::with_capacity(raw_edges.len());
    let mut seen = HashSet::with_capacity(raw_edges.len());
    let n_u32 = n as u32;
    for (u_dimacs, v_dimacs) in raw_edges {
        if u_dimacs == 0 || u_dimacs > n_u32 || v_dimacs == 0 || v_dimacs > n_u32 {
            return Err(SosaError::Input(
                "edge endpoint outside local vertex range".to_string(),
            ));
        }
        let u = u_dimacs - 1;
        let v = v_dimacs - 1;
        if u == v {
            return Err(SosaError::Input(format!("self-loop on vertex {u_dimacs}")));
        }
        let edge = if u < v { (u, v) } else { (v, u) };
        if !seen.insert(edge) {
            return Err(SosaError::Input(format!(
                "duplicate edge {} {}",
                edge.0 + 1,
                edge.1 + 1
            )));
        }
        edges.push(edge);
    }
    edges.sort_unstable();
    Ok(edges)
}

fn normalize_edges_trusted(
    n: usize,
    raw_edges: Vec<(u32, u32)>,
) -> Result<Vec<(u32, u32)>, SosaError> {
    let mut edges = Vec::with_capacity(raw_edges.len());
    let mut previous: Option<(u32, u32)> = None;
    let n_u32 = n as u32;
    for (u_dimacs, v_dimacs) in raw_edges {
        if u_dimacs == 0 || u_dimacs > n_u32 || v_dimacs == 0 || v_dimacs > n_u32 {
            return Err(SosaError::Input(
                "edge endpoint outside local vertex range".to_string(),
            ));
        }
        if u_dimacs >= v_dimacs {
            return Err(SosaError::Input(format!(
                "trusted edge input must use sorted non-loop edges, got {u_dimacs} {v_dimacs}"
            )));
        }
        let edge = (u_dimacs - 1, v_dimacs - 1);
        if previous.is_some_and(|previous| previous >= edge) {
            return Err(SosaError::Input(format!(
                "trusted edge input must be strictly lexicographically sorted at edge {} {}",
                u_dimacs, v_dimacs
            )));
        }
        previous = Some(edge);
        edges.push(edge);
    }
    Ok(edges)
}

#[cfg(test)]
mod tests {
    use crate::dimacs_circle::parse_dimacs_circle;
    use crate::partition::ArcName;

    use super::*;

    #[test]
    fn builds_triangle() {
        let dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 2 3 1 2 3
c hord endpoint order END
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        )
        .unwrap();

        let instance = CircleInstance::from_dimacs(dimacs).unwrap();

        assert_eq!(instance.n, 3);
        assert_eq!(instance.endpoint_at, vec![0, 1, 2, 0, 1, 2]);
        assert_eq!(instance.left, vec![0, 1, 2]);
        assert_eq!(instance.right, vec![3, 4, 5]);
        assert_eq!(instance.neighbors(0), &[1, 2]);
        assert!(instance.crosses(0, 1));
    }

    #[test]
    fn builds_independent_non_crossing_chords() {
        let dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1 2 2
c hord endpoint order END
p edge 2 0
",
        )
        .unwrap();

        let instance = CircleInstance::from_dimacs(dimacs).unwrap();

        assert_eq!(instance.n, 2);
        assert_eq!(instance.neighbors(0), &[]);
        assert!(!instance.crosses(0, 1));
    }

    #[test]
    fn builds_k4() {
        let dimacs = parse_dimacs_circle(
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
        )
        .unwrap();

        let instance = CircleInstance::from_dimacs(dimacs).unwrap();

        assert_eq!(instance.degree(0), 3);
        assert!(instance.crosses(0, 3));
    }

    #[test]
    fn rejects_self_loop() {
        let mut dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1
c hord endpoint order END
p edge 1 0
",
        )
        .unwrap();
        dimacs.edges.push((1, 1));

        assert!(CircleInstance::from_dimacs(dimacs)
            .unwrap_err()
            .to_string()
            .contains("self-loop"));
    }

    #[test]
    fn rejects_duplicate_edge() {
        let mut dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 2 1 2
c hord endpoint order END
p edge 2 1
e 1 2
",
        )
        .unwrap();
        dimacs.edges.push((2, 1));

        assert!(CircleInstance::from_dimacs(dimacs)
            .unwrap_err()
            .to_string()
            .contains("duplicate"));
    }

    #[test]
    fn trusted_listed_edges_reject_non_canonical_order() {
        let dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 2 3 1 2 3
c hord endpoint order END
p edge 3 3
e 1 3
e 1 2
e 2 3
",
        )
        .unwrap();

        assert!(CircleInstance::from_dimacs_with_listed_edge_mode(
            dimacs,
            false,
            ListedEdgeMode::Trusted
        )
        .unwrap_err()
        .to_string()
        .contains("lexicographically sorted"));
    }

    #[test]
    fn trusted_listed_edges_build_sorted_neighbors_from_canonical_order() {
        let dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 2 3 1 2 3
c hord endpoint order END
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        )
        .unwrap();

        let instance = CircleInstance::from_dimacs_with_listed_edge_mode(
            dimacs,
            false,
            ListedEdgeMode::Trusted,
        )
        .unwrap();

        assert_eq!(instance.neighbors(0), &[1, 2]);
        assert_eq!(instance.neighbors(1), &[0, 2]);
        assert_eq!(instance.neighbors(2), &[0, 1]);
    }

    #[test]
    fn rejects_missing_crossing_edge() {
        let dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 2 1 2
c hord endpoint order END
p edge 2 0
",
        )
        .unwrap();

        assert!(CircleInstance::from_dimacs(dimacs)
            .unwrap_err()
            .to_string()
            .contains("missing edge"));
    }

    #[test]
    fn rejects_extra_non_crossing_edge() {
        let dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1 2 2
c hord endpoint order END
p edge 2 1
e 1 2
",
        )
        .unwrap();

        assert!(CircleInstance::from_dimacs(dimacs)
            .unwrap_err()
            .to_string()
            .contains("does not match"));
    }

    #[test]
    fn rebuilds_all_active_instance() {
        let instance = triangle_instance();
        let active = BitSet::full(3);
        let rebuilt = instance
            .rebuild_from_active(&active, instance.allowed.clone())
            .unwrap();

        assert_eq!(rebuilt.endpoint_at, instance.endpoint_at);
        assert_eq!(rebuilt.adj, instance.adj);
    }

    #[test]
    fn rebuilds_subset_with_dense_vertex_ids() {
        let instance = triangle_instance();
        let mut active = BitSet::empty(3);
        active.set(0, true);
        active.set(2, true);
        let mut allowed = instance.allowed.clone();
        allowed[2] = 0b001;

        let rebuilt = instance.rebuild_from_active(&active, allowed).unwrap();

        assert_eq!(rebuilt.n, 2);
        assert_eq!(rebuilt.endpoint_at, vec![0, 1, 0, 1]);
        assert_eq!(rebuilt.left, vec![0, 1]);
        assert_eq!(rebuilt.right, vec![2, 3]);
        assert_eq!(rebuilt.neighbors(0), &[1]);
        assert_eq!(rebuilt.allowed, vec![ALL_COLORS, 0b001]);
    }

    #[test]
    fn rebuilds_empty_instance() {
        let instance = triangle_instance();
        let active = BitSet::empty(3);
        let rebuilt = instance
            .rebuild_from_active(&active, instance.allowed.clone())
            .unwrap();

        assert_eq!(rebuilt.n, 0);
        assert!(rebuilt.endpoint_at.is_empty());
        assert_eq!(rebuilt.adj_offsets, vec![0]);
    }

    #[test]
    fn rebuilds_partition_boundaries_without_full_map() {
        let instance = path_instance();
        let mut active = BitSet::full(3);
        active.clear(0);
        let partition = CirclePartition::new(instance.endpoint_count(), 0, 1, 3, 5).unwrap();

        let (rebuilt, rebuilt_partition) = instance
            .rebuild_from_active_with_partition(&active, instance.allowed.clone(), &partition)
            .unwrap();

        assert_eq!(rebuilt.n, 2);
        assert_eq!(
            rebuilt_partition,
            CirclePartition::new(4, 0, 0, 1, 3).unwrap()
        );
    }

    #[test]
    fn rebuilds_partition_when_all_vertices_deleted() {
        let instance = triangle_instance();
        let active = BitSet::empty(3);
        let partition = CirclePartition::new(instance.endpoint_count(), 0, 2, 4, 5).unwrap();

        let (rebuilt, rebuilt_partition) = instance
            .rebuild_from_active_with_partition(&active, instance.allowed.clone(), &partition)
            .unwrap();

        assert_eq!(rebuilt.n, 0);
        assert_eq!(rebuilt_partition, CirclePartition::empty(0));
    }

    #[test]
    fn rebuilds_partition_whose_surviving_chords_fill_one_arc() {
        let instance = two_separate_chords_instance();
        // L = [0, 2) holds chord 1 and R = [2, 4) holds chord 2; T and B are empty.
        let partition = CirclePartition::new(instance.endpoint_count(), 0, 2, 2, 0).unwrap();

        for (deleted, full_arc) in [(0, ArcName::R), (1, ArcName::L)] {
            let mut active = BitSet::full(2);
            active.clear(deleted);

            let (rebuilt, rebuilt_partition) = instance
                .rebuild_from_active_with_partition(&active, instance.allowed.clone(), &partition)
                .unwrap();

            // All four boundaries collapse onto one position, but the surviving chord must
            // still lie in the arc it came from.
            assert_eq!(rebuilt.n, 1);
            for position in 0..rebuilt.endpoint_count() {
                assert_eq!(rebuilt_partition.endpoint_arc(position), Some(full_arc));
            }
            assert_eq!(
                rebuilt_partition.positions(full_arc).collect::<Vec<_>>(),
                vec![0, 1]
            );
        }
    }

    fn two_separate_chords_instance() -> CircleInstance {
        let dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1 2 2
c hord endpoint order END
p edge 2 0
",
        )
        .unwrap();
        CircleInstance::from_dimacs(dimacs).unwrap()
    }

    fn triangle_instance() -> CircleInstance {
        let dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 2 3 1 2 3
c hord endpoint order END
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        )
        .unwrap();
        CircleInstance::from_dimacs(dimacs).unwrap()
    }

    fn path_instance() -> CircleInstance {
        let dimacs = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 2 1 3 2 3
c hord endpoint order END
p edge 3 2
e 1 2
e 2 3
",
        )
        .unwrap();
        CircleInstance::from_dimacs(dimacs).unwrap()
    }
}
