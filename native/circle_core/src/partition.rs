use crate::error::SosaError;

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum ArcName {
    L,
    T,
    R,
    B,
}

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub struct CirclePartition {
    pub n_endpoints: usize,
    pub left_boundary: usize,
    pub top_boundary: usize,
    pub right_boundary: usize,
    pub bottom_boundary: usize,
}

impl CirclePartition {
    pub fn new(
        n_endpoints: usize,
        left_boundary: usize,
        top_boundary: usize,
        right_boundary: usize,
        bottom_boundary: usize,
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
        })
    }

    pub fn empty(n_endpoints: usize) -> Self {
        Self {
            n_endpoints,
            left_boundary: 0,
            top_boundary: 0,
            right_boundary: 0,
            bottom_boundary: 0,
        }
    }

    pub fn rotate_counterclockwise(&self) -> Self {
        Self {
            n_endpoints: self.n_endpoints,
            left_boundary: self.top_boundary,
            top_boundary: self.right_boundary,
            right_boundary: self.bottom_boundary,
            bottom_boundary: self.left_boundary,
        }
    }

    pub fn contains_position(&self, arc_name: ArcName, position: usize) -> bool {
        assert!(position < self.n_endpoints);
        let (start, end) = self.arc_bounds(arc_name);
        if start == end {
            return false;
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
            done: self.n_endpoints == 0 || start == end,
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
}
