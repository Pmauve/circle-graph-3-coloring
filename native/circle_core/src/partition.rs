use crate::error::SosaError;

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum ArcName {
    L,
    T,
    R,
    B,
}

/// Four clockwise half-open arcs `L = [left, top)`, `T = [top, right)`, `R = [right, bottom)`
/// and `B = [bottom, left)` over the endpoint positions.
///
/// An arc with `start == end` is normally empty. When all four boundaries coincide on a
/// non-empty circle, one arc covers the whole circle instead; the boundaries alone cannot say
/// which, so that arc is stored in `full_arc`.
#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub struct CirclePartition {
    pub n_endpoints: usize,
    pub left_boundary: usize,
    pub top_boundary: usize,
    pub right_boundary: usize,
    pub bottom_boundary: usize,
    full_arc: Option<ArcName>,
}

impl CirclePartition {
    /// Builds a partition whose boundaries do not all coincide; use [`Self::new_full_arc`] or
    /// [`Self::new_or_full_arc`] when one arc may cover the whole circle.
    pub fn new(
        n_endpoints: usize,
        left_boundary: usize,
        top_boundary: usize,
        right_boundary: usize,
        bottom_boundary: usize,
    ) -> Result<Self, SosaError> {
        if boundaries_coincide(
            n_endpoints,
            left_boundary,
            top_boundary,
            right_boundary,
            bottom_boundary,
        ) {
            return Err(SosaError::Internal(format!(
                "partition boundaries all coincide at {left_boundary}; the arc covering the whole circle must be named"
            )));
        }
        Self::with_full_arc(
            n_endpoints,
            left_boundary,
            top_boundary,
            right_boundary,
            bottom_boundary,
            None,
        )
    }

    /// Builds the partition in which `full_arc` covers all `n_endpoints > 0` positions and the
    /// other three arcs are empty.
    pub fn new_full_arc(
        n_endpoints: usize,
        boundary: usize,
        full_arc: ArcName,
    ) -> Result<Self, SosaError> {
        if n_endpoints == 0 {
            return Err(SosaError::Internal(
                "a zero-endpoint partition has no arc covering the circle".to_string(),
            ));
        }
        Self::with_full_arc(
            n_endpoints,
            boundary,
            boundary,
            boundary,
            boundary,
            Some(full_arc),
        )
    }

    /// Like [`Self::new`], but if the boundaries all coincide on a non-empty circle, the result
    /// is the partition in which `full_arc` covers the whole circle.
    pub fn new_or_full_arc(
        n_endpoints: usize,
        left_boundary: usize,
        top_boundary: usize,
        right_boundary: usize,
        bottom_boundary: usize,
        full_arc: ArcName,
    ) -> Result<Self, SosaError> {
        let full_arc = boundaries_coincide(
            n_endpoints,
            left_boundary,
            top_boundary,
            right_boundary,
            bottom_boundary,
        )
        .then_some(full_arc);
        Self::with_full_arc(
            n_endpoints,
            left_boundary,
            top_boundary,
            right_boundary,
            bottom_boundary,
            full_arc,
        )
    }

    fn with_full_arc(
        n_endpoints: usize,
        left_boundary: usize,
        top_boundary: usize,
        right_boundary: usize,
        bottom_boundary: usize,
        full_arc: Option<ArcName>,
    ) -> Result<Self, SosaError> {
        if n_endpoints == 0 {
            if left_boundary != 0
                || top_boundary != 0
                || right_boundary != 0
                || bottom_boundary != 0
            {
                return Err(SosaError::Internal(
                    "zero-endpoint partition must use boundary 0".to_string(),
                ));
            }
        } else {
            for boundary in [left_boundary, top_boundary, right_boundary, bottom_boundary] {
                if boundary >= n_endpoints {
                    return Err(SosaError::Internal(format!(
                        "partition boundary {boundary} is out of range for {n_endpoints} endpoints"
                    )));
                }
            }
        }
        Ok(Self {
            n_endpoints,
            left_boundary,
            top_boundary,
            right_boundary,
            bottom_boundary,
            full_arc,
        })
    }

    /// The partition of a circle without endpoints.
    pub fn empty(n_endpoints: usize) -> Self {
        debug_assert_eq!(
            n_endpoints, 0,
            "a non-empty circle needs an arc covering it"
        );
        Self {
            n_endpoints,
            left_boundary: 0,
            top_boundary: 0,
            right_boundary: 0,
            bottom_boundary: 0,
            full_arc: None,
        }
    }

    /// The arc covering the whole circle, if all four boundaries coincide.
    pub fn full_arc(&self) -> Option<ArcName> {
        self.full_arc
    }

    pub fn rotate_counterclockwise(&self) -> Self {
        Self {
            n_endpoints: self.n_endpoints,
            left_boundary: self.top_boundary,
            top_boundary: self.right_boundary,
            right_boundary: self.bottom_boundary,
            bottom_boundary: self.left_boundary,
            full_arc: self.full_arc.map(|arc_name| match arc_name {
                ArcName::T => ArcName::L,
                ArcName::R => ArcName::T,
                ArcName::B => ArcName::R,
                ArcName::L => ArcName::B,
            }),
        }
    }

    pub fn contains_position(&self, arc_name: ArcName, position: usize) -> bool {
        assert!(position < self.n_endpoints);
        let (start, end) = self.arc_bounds(arc_name);
        if start == end {
            return self.full_arc == Some(arc_name);
        }
        if start < end {
            start <= position && position < end
        } else {
            position >= start || position < end
        }
    }

    pub fn endpoint_arc(&self, position: usize) -> Option<ArcName> {
        [ArcName::L, ArcName::T, ArcName::R, ArcName::B]
            .into_iter()
            .find(|&arc_name| self.contains_position(arc_name, position))
    }

    pub fn positions(&self, arc_name: ArcName) -> ArcPositionIter {
        let (start, end) = self.arc_bounds(arc_name);
        ArcPositionIter {
            n_endpoints: self.n_endpoints,
            current: start,
            end,
            done: self.n_endpoints == 0 || (start == end && self.full_arc != Some(arc_name)),
        }
    }

    fn arc_bounds(&self, arc_name: ArcName) -> (usize, usize) {
        match arc_name {
            ArcName::L => (self.left_boundary, self.top_boundary),
            ArcName::T => (self.top_boundary, self.right_boundary),
            ArcName::R => (self.right_boundary, self.bottom_boundary),
            ArcName::B => (self.bottom_boundary, self.left_boundary),
        }
    }
}

fn boundaries_coincide(
    n_endpoints: usize,
    left_boundary: usize,
    top_boundary: usize,
    right_boundary: usize,
    bottom_boundary: usize,
) -> bool {
    n_endpoints > 0
        && left_boundary == top_boundary
        && top_boundary == right_boundary
        && right_boundary == bottom_boundary
}

pub struct ArcPositionIter {
    n_endpoints: usize,
    current: usize,
    end: usize,
    done: bool,
}

impl Iterator for ArcPositionIter {
    type Item = usize;

    fn next(&mut self) -> Option<Self::Item> {
        if self.done {
            return None;
        }
        let position = self.current;
        self.current = (self.current + 1) % self.n_endpoints;
        if self.current == self.end {
            self.done = true;
        }
        Some(position)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn iterates_wrapping_arc() {
        let partition = CirclePartition::new(6, 0, 2, 4, 5).unwrap();

        assert_eq!(partition.positions(ArcName::B).collect::<Vec<_>>(), vec![5]);
        assert!(partition.contains_position(ArcName::L, 1));
        assert!(!partition.contains_position(ArcName::L, 2));
    }

    #[test]
    fn rotates_partition() {
        let partition = CirclePartition::new(8, 0, 2, 4, 6).unwrap();

        assert_eq!(
            partition.rotate_counterclockwise(),
            CirclePartition::new(8, 2, 4, 6, 0).unwrap()
        );
    }

    #[test]
    fn full_arc_covers_every_position() {
        for full_arc in [ArcName::L, ArcName::T, ArcName::R, ArcName::B] {
            let partition = CirclePartition::new_full_arc(4, 3, full_arc).unwrap();

            for position in 0..4 {
                assert_eq!(partition.endpoint_arc(position), Some(full_arc));
            }
            assert_eq!(
                partition.positions(full_arc).collect::<Vec<_>>(),
                vec![3, 0, 1, 2]
            );
            for other_arc in [ArcName::L, ArcName::T, ArcName::R, ArcName::B] {
                if other_arc != full_arc {
                    assert_eq!(partition.positions(other_arc).count(), 0);
                }
            }
        }
    }

    #[test]
    fn rejects_coinciding_boundaries_without_full_arc() {
        assert!(CirclePartition::new(4, 1, 1, 1, 1).is_err());
        assert!(CirclePartition::new_full_arc(0, 0, ArcName::L).is_err());
        assert_eq!(
            CirclePartition::new(0, 0, 0, 0, 0).unwrap(),
            CirclePartition::empty(0)
        );
    }

    #[test]
    fn names_full_arc_only_when_boundaries_coincide() {
        assert_eq!(
            CirclePartition::new_or_full_arc(4, 2, 2, 2, 2, ArcName::R)
                .unwrap()
                .full_arc(),
            Some(ArcName::R)
        );
        assert_eq!(
            CirclePartition::new_or_full_arc(4, 0, 2, 2, 0, ArcName::R).unwrap(),
            CirclePartition::new(4, 0, 2, 2, 0).unwrap()
        );
    }

    #[test]
    fn rotation_moves_full_arc_with_its_boundaries() {
        let partition = CirclePartition::new_full_arc(4, 0, ArcName::T).unwrap();

        let rotated = partition.rotate_counterclockwise();

        assert_eq!(rotated.full_arc(), Some(ArcName::L));
        assert_eq!(
            rotated.rotate_counterclockwise().full_arc(),
            Some(ArcName::B)
        );
    }
}
