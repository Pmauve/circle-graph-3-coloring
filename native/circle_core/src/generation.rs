use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::error::SosaError;

const GENERATOR_VERSION: &str = "native_incremental_v1";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum GenerationFamily {
    Rc,
    RcFast,
    Rcy,
    RcyFast,
    Rccy,
    RccyTuned,
    RccyFullSweepWeightedActive,
    RccyFullSweepMaxActive,
}

impl GenerationFamily {
    pub fn parse(value: &str) -> Result<Self, SosaError> {
        match value {
            "rc" => Ok(Self::Rc),
            "rc_fast" => Ok(Self::RcFast),
            "rcy" => Ok(Self::Rcy),
            "rcy_fast" => Ok(Self::RcyFast),
            "rccy" => Ok(Self::Rccy),
            "rccy_tuned" => Ok(Self::RccyTuned),
            "rccy_full_sweep_weighted_active" => Ok(Self::RccyFullSweepWeightedActive),
            "rccy_full_sweep_max_active" => Ok(Self::RccyFullSweepMaxActive),
            _ => Err(SosaError::Input(format!(
                "unsupported generation family {value:?}"
            ))),
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Rc => "rc",
            Self::RcFast => "rc_fast",
            Self::Rcy => "rcy",
            Self::RcyFast => "rcy_fast",
            Self::Rccy => "rccy",
            Self::RccyTuned => "rccy_tuned",
            Self::RccyFullSweepWeightedActive => "rccy_full_sweep_weighted_active",
            Self::RccyFullSweepMaxActive => "rccy_full_sweep_max_active",
        }
    }

    fn uses_colors(self) -> bool {
        !matches!(self, Self::Rc | Self::RcFast)
    }

    fn constructive_config(self) -> Option<ConstructiveConfig> {
        match self {
            Self::Rccy | Self::RccyTuned => Some(ConstructiveConfig {
                start_lookahead: 16,
                end_selection: EndSelection::MaxActive,
                full_sweep: false,
            }),
            Self::RccyFullSweepWeightedActive => Some(ConstructiveConfig {
                start_lookahead: 16,
                end_selection: EndSelection::WeightedActive,
                full_sweep: true,
            }),
            Self::RccyFullSweepMaxActive => Some(ConstructiveConfig {
                start_lookahead: 16,
                end_selection: EndSelection::MaxActive,
                full_sweep: true,
            }),
            _ => None,
        }
    }

    fn generator_name(self) -> &'static str {
        match self {
            Self::Rc => "native_seeded_random_circle_graph",
            Self::RcFast => "native_seeded_random_circle_graph_fast",
            Self::Rcy => "native_seeded_random_circle_graph_yes",
            Self::RcyFast => "native_seeded_random_circle_graph_yes_fast",
            Self::Rccy => "native_seeded_random_circle_graph_yes_constructive_tuned",
            Self::RccyTuned => "native_seeded_random_circle_graph_yes_constructive_tuned",
            Self::RccyFullSweepWeightedActive => {
                "native_seeded_random_circle_graph_yes_constructive_full_sweep_weighted_active"
            }
            Self::RccyFullSweepMaxActive => {
                "native_seeded_random_circle_graph_yes_constructive_full_sweep_max_active"
            }
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ConstructiveConfig {
    start_lookahead: usize,
    end_selection: EndSelection,
    full_sweep: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum EndSelection {
    MaxActive,
    WeightedActive,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct ConstructiveCandidate {
    second_gap: usize,
    available_colors: Vec<u8>,
    active_count: usize,
    step: usize,
}

#[derive(Clone, Debug)]
pub struct GenerationConfig {
    pub family: GenerationFamily,
    pub seed: u64,
    pub num_colors: u8,
    pub max_attempts_per_node: usize,
}

impl GenerationConfig {
    pub fn validate(&self) -> Result<(), SosaError> {
        if self.num_colors == 0 {
            return Err(SosaError::Input(
                "num_colors must be at least 1".to_string(),
            ));
        }
        if !self.family.uses_colors() && self.num_colors != 3 {
            return Err(SosaError::Input(format!(
                "family {:?} does not support num_colors={}",
                self.family, self.num_colors
            )));
        }
        if self.max_attempts_per_node == 0 {
            return Err(SosaError::Input(
                "max_attempts_per_node must be at least 1".to_string(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct GeneratedSummary {
    pub instance_id: String,
    pub family: String,
    pub n: usize,
    pub m: usize,
    pub num_colors: u8,
    pub path: PathBuf,
}

pub struct CircleGraphBuilder {
    config: GenerationConfig,
    rng: GeneratorRng,
    endpoint_order: Vec<u32>,
    adjacency: Vec<Vec<u32>>,
    colors: Option<Vec<u8>>,
    marks: Vec<bool>,
}

impl CircleGraphBuilder {
    pub fn new(config: GenerationConfig) -> Result<Self, SosaError> {
        config.validate()?;
        let colors = if config.family.uses_colors() {
            Some(Vec::new())
        } else {
            None
        };
        let seed = config.seed;
        Ok(Self {
            config,
            rng: GeneratorRng::new(seed),
            endpoint_order: Vec::new(),
            adjacency: Vec::new(),
            colors,
            marks: Vec::new(),
        })
    }

    pub fn len(&self) -> usize {
        self.adjacency.len()
    }

    pub fn edge_count(&self) -> usize {
        self.adjacency.iter().map(Vec::len).sum::<usize>() / 2
    }

    pub fn extend_to(&mut self, n: usize) -> Result<(), SosaError> {
        while self.len() < n {
            self.insert_next_vertex()?;
        }
        Ok(())
    }

    pub fn write_col(&self, path: &Path) -> Result<GeneratedSummary, SosaError> {
        let summary = self.summary_for_path(path);
        write_dimacs_circle(self, &summary)?;
        Ok(summary)
    }

    pub fn summary_for_path(&self, path: &Path) -> GeneratedSummary {
        GeneratedSummary {
            instance_id: instance_id(
                self.config.family,
                self.len(),
                self.config.seed,
                self.config.num_colors,
            ),
            family: self.config.family.as_str().to_string(),
            n: self.len(),
            m: self.edge_count(),
            num_colors: self.config.num_colors,
            path: path.to_path_buf(),
        }
    }

    fn insert_next_vertex(&mut self) -> Result<(), SosaError> {
        if let Some(config) = self.config.family.constructive_config() {
            return self.insert_next_constructive_vertex(config);
        }
        let node_id = self.len() as u32;
        for _attempt in 0..self.config.max_attempts_per_node {
            let first_position = self.rng.next_usize(self.endpoint_order.len() + 1);
            let second_position = self.rng.next_usize(self.endpoint_order.len() + 2);
            let (left, right) = candidate_neighbor_slice(first_position, second_position);
            let neighbors = self.candidate_neighbors_between(left, right);
            if !candidate_is_connected(node_id, &neighbors) {
                continue;
            }
            if self.contains_triangle(&neighbors) {
                continue;
            }

            let color = if let Some(colors) = &self.colors {
                match choose_compatible_color(&neighbors, colors, self.config.num_colors) {
                    Some(color) => Some(color),
                    None => continue,
                }
            } else {
                None
            };

            self.commit_candidate(node_id, first_position, second_position, &neighbors, color);
            return Ok(());
        }
        Err(SosaError::Input(format!(
            "failed to generate {} vertex {} after {} attempts",
            self.config.family.as_str(),
            node_id + 1,
            self.config.max_attempts_per_node
        )))
    }

    fn insert_next_constructive_vertex(
        &mut self,
        constructive: ConstructiveConfig,
    ) -> Result<(), SosaError> {
        let node_id = self.len() as u32;
        if node_id == 0 {
            self.endpoint_order.push(node_id);
            self.endpoint_order.push(node_id);
            self.adjacency.push(Vec::new());
            let color = self.rng.next_u8_inclusive(1, self.config.num_colors);
            self.colors
                .as_mut()
                .expect("constructive families must use colors")
                .push(color);
            return Ok(());
        }

        for _attempt in 0..self.config.max_attempts_per_node {
            let (start_gap, direction) = self.choose_constructive_start(constructive);
            let candidates =
                self.collect_constructive_candidates(start_gap, direction, constructive.full_sweep);
            if candidates.is_empty() {
                continue;
            }
            let chosen =
                self.choose_constructive_candidate(&candidates, constructive.end_selection);
            let color_index = self.rng.next_usize(chosen.available_colors.len());
            let color = chosen.available_colors[color_index];
            self.commit_constructive_candidate(node_id, start_gap, chosen.second_gap, color);
            return Ok(());
        }
        Err(SosaError::Input(format!(
            "failed to generate {} vertex {} after {} attempts",
            self.config.family.as_str(),
            node_id + 1,
            self.config.max_attempts_per_node
        )))
    }

    fn choose_constructive_start(&mut self, config: ConstructiveConfig) -> (usize, i8) {
        if self.endpoint_order.is_empty() {
            return (0, 1);
        }
        if config.start_lookahead <= 1 {
            return (
                self.rng.next_usize(self.endpoint_order.len() + 1),
                self.random_direction(),
            );
        }

        let mut best_score: Option<(usize, usize)> = None;
        let mut best_pairs = Vec::new();
        for _ in 0..config.start_lookahead {
            let pair = (
                self.rng.next_usize(self.endpoint_order.len() + 1),
                self.random_direction(),
            );
            let score = self.constructive_frontier_stats(pair.0, pair.1);
            if best_score.map_or(true, |best| score > best) {
                best_score = Some(score);
                best_pairs.clear();
                best_pairs.push(pair);
            } else if best_score == Some(score) {
                best_pairs.push(pair);
            }
        }
        best_pairs[self.rng.next_usize(best_pairs.len())]
    }

    fn random_direction(&mut self) -> i8 {
        if self.rng.next_usize(2) == 0 {
            -1
        } else {
            1
        }
    }

    fn constructive_frontier_stats(&self, start_gap: usize, direction: i8) -> (usize, usize) {
        let mut frontier_length = 0;
        let mut max_active = 0;
        for candidate in self.iter_constructive_candidates(start_gap, direction, false) {
            frontier_length += 1;
            max_active = max_active.max(candidate.active_count);
        }
        (frontier_length, max_active)
    }

    fn collect_constructive_candidates(
        &self,
        start_gap: usize,
        direction: i8,
        full_sweep: bool,
    ) -> Vec<ConstructiveCandidate> {
        self.iter_constructive_candidates(start_gap, direction, full_sweep)
    }

    fn iter_constructive_candidates(
        &self,
        start_gap: usize,
        direction: i8,
        full_sweep: bool,
    ) -> Vec<ConstructiveCandidate> {
        let mut active = vec![false; self.len()];
        let mut active_count = 0usize;
        let colors = self
            .colors
            .as_ref()
            .expect("constructive families need colors");
        let mut color_counts = vec![0usize; self.config.num_colors as usize + 1];
        let mut current_low = start_gap;
        let mut current_high = start_gap;
        let mut started = false;
        let mut candidates = Vec::new();
        for (step, gap) in ordered_second_gaps(self.endpoint_order.len(), start_gap, direction)
            .into_iter()
            .enumerate()
        {
            let step = step + 1;
            let (low_gap, high_gap) = sorted_pair(start_gap, gap);
            move_active_interval(
                &self.endpoint_order,
                &mut active,
                &mut active_count,
                &mut color_counts,
                colors,
                current_low,
                current_high,
                low_gap,
                high_gap,
            );
            current_low = low_gap;
            current_high = high_gap;

            let available_colors = if active_count == 0 {
                Vec::new()
            } else {
                available_colors_from_counts(&color_counts, self.config.num_colors)
            };
            if available_colors.is_empty() {
                if started && !full_sweep {
                    break;
                }
                continue;
            }
            started = true;
            candidates.push(ConstructiveCandidate {
                second_gap: gap,
                available_colors,
                active_count,
                step,
            });
        }
        candidates
    }

    fn choose_constructive_candidate<'a>(
        &mut self,
        candidates: &'a [ConstructiveCandidate],
        end_selection: EndSelection,
    ) -> &'a ConstructiveCandidate {
        match end_selection {
            EndSelection::MaxActive => {
                let best = candidates
                    .iter()
                    .map(|candidate| candidate.active_count)
                    .max()
                    .unwrap_or(0);
                let best_count = candidates
                    .iter()
                    .filter(|candidate| candidate.active_count == best)
                    .count();
                let mut selected = self.rng.next_usize(best_count);
                for candidate in candidates {
                    if candidate.active_count == best {
                        if selected == 0 {
                            return candidate;
                        }
                        selected -= 1;
                    }
                }
                &candidates[0]
            }
            EndSelection::WeightedActive => {
                let total_weight: usize = candidates
                    .iter()
                    .map(|candidate| candidate.active_count)
                    .sum();
                let mut selected = self.rng.next_usize(total_weight.max(1));
                for candidate in candidates {
                    if selected < candidate.active_count {
                        return candidate;
                    }
                    selected -= candidate.active_count;
                }
                &candidates[0]
            }
        }
    }

    fn commit_constructive_candidate(
        &mut self,
        node_id: u32,
        start_gap: usize,
        second_gap: usize,
        color: u8,
    ) {
        let (low_gap, high_gap) = sorted_pair(start_gap, second_gap);
        let neighbors = self.neighbors_between_gaps(low_gap, high_gap);
        self.endpoint_order.insert(low_gap, node_id);
        self.endpoint_order.insert(high_gap + 1, node_id);

        self.adjacency.push(Vec::new());
        for &neighbor in &neighbors {
            self.adjacency[node_id as usize].push(neighbor);
            self.adjacency[neighbor as usize].push(node_id);
        }
        self.adjacency[node_id as usize].sort_unstable();
        self.colors
            .as_mut()
            .expect("constructive families must use colors")
            .push(color);
    }

    fn neighbors_between_gaps(&self, low_gap: usize, high_gap: usize) -> Vec<u32> {
        let mut active = vec![false; self.len()];
        for &vertex in &self.endpoint_order[low_gap..high_gap] {
            let slot = &mut active[vertex as usize];
            *slot = !*slot;
        }
        active_neighbors(&active)
    }

    fn contains_triangle(&self, neighbors: &[u32]) -> bool {
        if neighbors.len() < 3 {
            return false;
        }
        let mut marked = vec![false; self.len()];
        for &neighbor in neighbors {
            marked[neighbor as usize] = true;
        }
        for (index, &left) in neighbors.iter().enumerate() {
            let left_neighbors = &self.adjacency[left as usize];
            for &right in &neighbors[index + 1..] {
                if left_neighbors.binary_search(&right).is_err() {
                    continue;
                }
                let right_neighbors = &self.adjacency[right as usize];
                if right_neighbors.iter().any(|candidate| {
                    marked[*candidate as usize]
                        && *candidate != left
                        && left_neighbors.binary_search(candidate).is_ok()
                }) {
                    return true;
                }
            }
        }
        false
    }

    fn candidate_neighbors_between(&mut self, left: usize, right: usize) -> Vec<u32> {
        if self.marks.len() < self.len() {
            self.marks.resize(self.len(), false);
        }
        let mut touched = Vec::new();
        for &vertex in &self.endpoint_order[left..right] {
            let mark = &mut self.marks[vertex as usize];
            *mark = !*mark;
            if *mark {
                touched.push(vertex);
            }
        }
        let mut neighbors = Vec::new();
        for vertex in touched {
            if self.marks[vertex as usize] {
                neighbors.push(vertex);
                self.marks[vertex as usize] = false;
            }
        }
        neighbors.sort_unstable();
        neighbors
    }

    fn commit_candidate(
        &mut self,
        node_id: u32,
        first_position: usize,
        second_position: usize,
        neighbors: &[u32],
        color: Option<u8>,
    ) {
        self.endpoint_order.insert(first_position, node_id);
        self.endpoint_order.insert(second_position, node_id);

        self.adjacency.push(Vec::new());
        for &neighbor in neighbors {
            self.adjacency[node_id as usize].push(neighbor);
            self.adjacency[neighbor as usize].push(node_id);
        }
        self.adjacency[node_id as usize].sort_unstable();
        if let Some(colors) = &mut self.colors {
            colors.push(color.expect("colored families must pass a chosen color"));
        }
    }
}

pub fn instance_id(family: GenerationFamily, n: usize, seed: u64, num_colors: u8) -> String {
    format!(
        "{}-k{:02}-n{:04}-seed{}",
        family.as_str(),
        num_colors,
        n,
        seed
    )
}

pub fn bucket_for_n(n: usize) -> &'static str {
    if n <= 250 {
        "s"
    } else if n <= 750 {
        "m"
    } else if n <= 1500 {
        "l"
    } else {
        "xl"
    }
}

pub fn sequence_output_path(
    output_dir: &Path,
    family: GenerationFamily,
    n: usize,
    seed: u64,
    num_colors: u8,
) -> PathBuf {
    output_dir
        .join(family.as_str())
        .join(bucket_for_n(n))
        .join(format!("{}.col", instance_id(family, n, seed, num_colors)))
}

fn write_dimacs_circle(
    builder: &CircleGraphBuilder,
    summary: &GeneratedSummary,
) -> Result<(), SosaError> {
    if let Some(parent) = summary.path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let file = File::create(&summary.path)?;
    let mut writer = BufWriter::new(file);
    let average_degree = if summary.n == 0 {
        0.0
    } else {
        2.0 * summary.m as f64 / summary.n as f64
    };
    writeln!(writer, "c format version 1")?;
    writeln!(writer, "c instance id {}", summary.instance_id)?;
    writeln!(writer, "c family {}", summary.family)?;
    writeln!(writer, "c seed {}", builder.config.seed)?;
    writeln!(writer, "c n {}", summary.n)?;
    writeln!(writer, "c m {}", summary.m)?;
    writeln!(writer, "c average degree {:.12}", average_degree)?;
    writeln!(writer, "c num colors {}", summary.num_colors)?;
    writeln!(writer, "c source generated")?;
    writeln!(
        writer,
        "c generator {}:{}",
        builder.config.family.generator_name(),
        GENERATOR_VERSION
    )?;
    writeln!(writer, "c created at {}", created_at_text())?;
    writeln!(writer, "c generation time seconds none")?;
    writeln!(
        writer,
        "c max attempts per node {}",
        builder.config.max_attempts_per_node
    )?;
    writeln!(writer, "c ircle representation START")?;
    for chunk in builder.endpoint_order.chunks(32) {
        write!(writer, "c")?;
        for vertex in chunk {
            write!(writer, " {}", vertex + 1)?;
        }
        writeln!(writer)?;
    }
    writeln!(writer, "c ircle representation END")?;
    writeln!(writer, "p edge {} {}", summary.n, summary.m)?;
    for (u, neighbors) in builder.adjacency.iter().enumerate() {
        for &v in neighbors {
            if u < v as usize {
                writeln!(writer, "e {} {}", u + 1, v + 1)?;
            }
        }
    }
    Ok(())
}

fn candidate_neighbor_slice(first_position: usize, second_position: usize) -> (usize, usize) {
    if second_position <= first_position {
        (second_position, first_position)
    } else {
        (first_position, second_position - 1)
    }
}

fn candidate_is_connected(node_id: u32, neighbors: &[u32]) -> bool {
    node_id == 0 || !neighbors.is_empty()
}

fn choose_compatible_color(neighbors: &[u32], colors: &[u8], num_colors: u8) -> Option<u8> {
    let mut used = vec![false; num_colors as usize + 1];
    for &neighbor in neighbors {
        let color = colors[neighbor as usize] as usize;
        if color < used.len() {
            used[color] = true;
        }
    }
    (1..=num_colors).find(|&color| !used[color as usize])
}

fn created_at_text() -> String {
    match SystemTime::now().duration_since(UNIX_EPOCH) {
        Ok(duration) => format!("unix:{}", duration.as_secs()),
        Err(_) => "unix:0".to_string(),
    }
}

#[derive(Clone, Debug)]
struct GeneratorRng {
    state: u64,
}

impl GeneratorRng {
    fn new(seed: u64) -> Self {
        Self {
            state: seed ^ 0x9e37_79b9_7f4a_7c15,
        }
    }

    fn next_u64(&mut self) -> u64 {
        self.state = self.state.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut value = self.state;
        value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        value ^ (value >> 31)
    }

    fn next_usize(&mut self, upper_exclusive: usize) -> usize {
        debug_assert!(upper_exclusive > 0);
        (self.next_u64() % upper_exclusive as u64) as usize
    }

    fn next_u8_inclusive(&mut self, low: u8, high: u8) -> u8 {
        low + self.next_usize((high - low + 1) as usize) as u8
    }
}

fn ordered_second_gaps(endpoint_order_len: usize, start_gap: usize, direction: i8) -> Vec<usize> {
    let n_gaps = endpoint_order_len + 1;
    let mut current = start_gap;
    let mut gaps = Vec::with_capacity(n_gaps.saturating_sub(1));
    for _ in 0..n_gaps.saturating_sub(1) {
        current = if direction > 0 {
            (current + 1) % n_gaps
        } else {
            (current + n_gaps - 1) % n_gaps
        };
        gaps.push(current);
    }
    gaps
}

fn sorted_pair(left: usize, right: usize) -> (usize, usize) {
    if left <= right {
        (left, right)
    } else {
        (right, left)
    }
}

fn move_active_interval(
    endpoint_order: &[u32],
    active: &mut [bool],
    active_count: &mut usize,
    color_counts: &mut [usize],
    colors: &[u8],
    old_low: usize,
    old_high: usize,
    new_low: usize,
    new_high: usize,
) {
    if new_low > old_low {
        toggle_endpoint_range(
            endpoint_order,
            active,
            active_count,
            color_counts,
            colors,
            old_low,
            new_low,
        );
    } else if new_low < old_low {
        toggle_endpoint_range(
            endpoint_order,
            active,
            active_count,
            color_counts,
            colors,
            new_low,
            old_low,
        );
    }
    if new_high > old_high {
        toggle_endpoint_range(
            endpoint_order,
            active,
            active_count,
            color_counts,
            colors,
            old_high,
            new_high,
        );
    } else if new_high < old_high {
        toggle_endpoint_range(
            endpoint_order,
            active,
            active_count,
            color_counts,
            colors,
            new_high,
            old_high,
        );
    }
}

fn toggle_endpoint_range(
    endpoint_order: &[u32],
    active: &mut [bool],
    active_count: &mut usize,
    color_counts: &mut [usize],
    colors: &[u8],
    start: usize,
    stop: usize,
) {
    for &vertex in &endpoint_order[start..stop] {
        let slot = &mut active[vertex as usize];
        *slot = !*slot;
        let color = colors[vertex as usize] as usize;
        if *slot {
            *active_count += 1;
            color_counts[color] += 1;
        } else {
            *active_count -= 1;
            color_counts[color] -= 1;
        }
    }
}

fn active_neighbors(active: &[bool]) -> Vec<u32> {
    active
        .iter()
        .enumerate()
        .filter_map(|(vertex, is_active)| is_active.then_some(vertex as u32))
        .collect()
}

fn available_colors_from_counts(color_counts: &[usize], num_colors: u8) -> Vec<u8> {
    (1..=num_colors)
        .filter(|&color| color_counts[color as usize] == 0)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extends_incrementally_with_stable_prefix() {
        let config = GenerationConfig {
            family: GenerationFamily::RcFast,
            seed: 17,
            num_colors: 3,
            max_attempts_per_node: 10_000,
        };
        let mut small = CircleGraphBuilder::new(config.clone()).unwrap();
        small.extend_to(8).unwrap();
        let small_order = small.endpoint_order.clone();

        let mut large = CircleGraphBuilder::new(config).unwrap();
        large.extend_to(9).unwrap();
        let mut truncated = large.endpoint_order.clone();
        truncated.retain(|vertex| *vertex < 8);

        assert_eq!(small_order, truncated);
    }

    #[test]
    fn generates_colored_family() {
        for family in [
            GenerationFamily::RcyFast,
            GenerationFamily::RccyTuned,
            GenerationFamily::RccyFullSweepWeightedActive,
            GenerationFamily::RccyFullSweepMaxActive,
        ] {
            let config = GenerationConfig {
                family,
                seed: 29,
                num_colors: 4,
                max_attempts_per_node: 10_000,
            };
            let mut builder = CircleGraphBuilder::new(config).unwrap();

            builder.extend_to(12).unwrap();

            assert_eq!(builder.len(), 12);
            assert_eq!(builder.colors.as_ref().unwrap().len(), 12);
        }
    }

    #[test]
    fn rejects_custom_color_count_for_non_yes_family() {
        let config = GenerationConfig {
            family: GenerationFamily::RcFast,
            seed: 1,
            num_colors: 4,
            max_attempts_per_node: 10_000,
        };

        assert!(CircleGraphBuilder::new(config).is_err());
    }

    #[test]
    fn formats_legacy_instance_ids() {
        assert_eq!(
            instance_id(GenerationFamily::RcFast, 8, 17, 3),
            "rc_fast-k03-n0008-seed17"
        );
    }
}
