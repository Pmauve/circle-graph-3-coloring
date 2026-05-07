use std::collections::HashSet;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use crate::error::SosaError;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InstanceSummary {
    pub instance_id: Option<String>,
    pub family: Option<String>,
    pub n: usize,
    pub m: usize,
    pub num_colors: Option<usize>,
}

pub fn inspect_dimacs_circle_file(path: &Path) -> Result<InstanceSummary, SosaError> {
    let file = File::open(path)?;
    inspect_dimacs_circle(BufReader::new(file))
}

pub fn validate_dimacs_circle_file(path: &Path) -> Result<InstanceSummary, SosaError> {
    let file = File::open(path)?;
    validate_dimacs_circle(BufReader::new(file))
}

pub fn inspect_dimacs_circle<R: BufRead>(reader: R) -> Result<InstanceSummary, SosaError> {
    let mut parser = ParserState::default();
    for (line_index, raw_line) in reader.lines().enumerate() {
        let line_number = line_index + 1;
        let raw_line = raw_line?;
        let line = raw_line.trim().trim_start_matches('\u{feff}');
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        match parts[0] {
            "c" => parser.capture_comment(&parts[1..], line_number)?,
            "p" => {
                parser.parse_problem(&parts, line_number, line)?;
                return parser.summary();
            }
            "e" => {
                return input_error(format!(
                    "edge line before problem line at line {line_number}"
                ));
            }
            _ => {
                return input_error(format!(
                    "unsupported DIMACS line at line {line_number}: {line}"
                ));
            }
        }
    }
    input_error("DIMACS file is missing a problem line".to_string())
}

pub fn validate_dimacs_circle<R: BufRead>(reader: R) -> Result<InstanceSummary, SosaError> {
    let mut parser = ParserState::default();
    let mut edge_count = 0usize;
    let mut circle_order = Vec::new();
    let mut edges = HashSet::new();

    for (line_index, raw_line) in reader.lines().enumerate() {
        let line_number = line_index + 1;
        let raw_line = raw_line?;
        let line = raw_line.trim().trim_start_matches('\u{feff}');
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        match parts[0] {
            "c" => match parser.circle_comment_action(&parts[1..], line_number)? {
                CircleAction::Start | CircleAction::End | CircleAction::Metadata => {}
                CircleAction::EndpointLine => {
                    for token in &parts[1..] {
                        circle_order.push(parse_positive_usize(token, line_number)?);
                    }
                }
            },
            "p" => parser.parse_problem(&parts, line_number, line)?,
            "e" => {
                let problem = parser.problem.ok_or_else(|| {
                    SosaError::Input(format!(
                        "edge line before problem line at line {line_number}"
                    ))
                })?;
                if parts.len() != 3 {
                    return input_error(format!(
                        "malformed edge line at line {line_number}: {line}"
                    ));
                }
                let u = parse_positive_usize(parts[1], line_number)?;
                let v = parse_positive_usize(parts[2], line_number)?;
                if u > problem.n {
                    return input_error(format!(
                        "edge vertex id {u} out of range 1..{}",
                        problem.n
                    ));
                }
                if v > problem.n {
                    return input_error(format!(
                        "edge vertex id {v} out of range 1..{}",
                        problem.n
                    ));
                }
                if u == v {
                    return input_error(format!("self-loop on vertex {u} at line {line_number}"));
                }
                let key = edge_key(u, v);
                if !edges.insert(key) {
                    return input_error(format!("duplicate edge ({u}, {v}) at line {line_number}"));
                }
                edge_count += 1;
            }
            _ => {
                return input_error(format!(
                    "unsupported DIMACS line at line {line_number}: {line}"
                ));
            }
        }
    }

    if parser.in_circle_block {
        return input_error("circle representation block is missing END".to_string());
    }
    if !parser.saw_circle_block {
        return input_error("DIMACS file is missing a circle representation block".to_string());
    }
    let problem = parser
        .problem
        .ok_or_else(|| SosaError::Input("DIMACS file is missing a problem line".to_string()))?;
    if edge_count != problem.m {
        return input_error(format!(
            "problem line declares {} edge(s), but {edge_count} were read",
            problem.m
        ));
    }
    validate_metadata_consistency(&parser, problem)?;
    validate_circle_order(problem.n, &circle_order)?;
    parser.summary()
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Problem {
    n: usize,
    m: usize,
}

#[derive(Default)]
struct ParserState {
    instance_id: Option<String>,
    family: Option<String>,
    metadata_n: Option<usize>,
    metadata_m: Option<usize>,
    num_colors: Option<usize>,
    problem: Option<Problem>,
    in_circle_block: bool,
    saw_circle_block: bool,
}

impl ParserState {
    fn capture_comment(&mut self, parts: &[&str], line_number: usize) -> Result<(), SosaError> {
        match circle_action(parts) {
            Some("START") => {
                if self.in_circle_block {
                    return input_error(format!(
                        "nested circle representation block at line {line_number}"
                    ));
                }
                if self.saw_circle_block {
                    return input_error(format!(
                        "duplicate circle representation block at line {line_number}"
                    ));
                }
                self.in_circle_block = true;
                self.saw_circle_block = true;
            }
            Some("END") => {
                if !self.in_circle_block {
                    return input_error(format!(
                        "circle representation END without START at line {line_number}"
                    ));
                }
                self.in_circle_block = false;
            }
            Some(action) if self.in_circle_block => {
                return input_error(format!(
                    "unsupported circle representation directive {action:?} at line {line_number}"
                ));
            }
            _ if self.in_circle_block => {}
            _ => self.capture_metadata(parts, line_number)?,
        }
        Ok(())
    }

    fn circle_comment_action(
        &mut self,
        parts: &[&str],
        line_number: usize,
    ) -> Result<CircleAction, SosaError> {
        match circle_action(parts) {
            Some("START") => {
                if self.in_circle_block {
                    return input_error(format!(
                        "nested circle representation block at line {line_number}"
                    ));
                }
                if self.saw_circle_block {
                    return input_error(format!(
                        "duplicate circle representation block at line {line_number}"
                    ));
                }
                self.in_circle_block = true;
                self.saw_circle_block = true;
                Ok(CircleAction::Start)
            }
            Some("END") => {
                if !self.in_circle_block {
                    return input_error(format!(
                        "circle representation END without START at line {line_number}"
                    ));
                }
                self.in_circle_block = false;
                Ok(CircleAction::End)
            }
            Some(action) if self.in_circle_block => input_error(format!(
                "unsupported circle representation directive {action:?} at line {line_number}"
            )),
            _ if self.in_circle_block => Ok(CircleAction::EndpointLine),
            _ => {
                self.capture_metadata(parts, line_number)?;
                Ok(CircleAction::Metadata)
            }
        }
    }

    fn capture_metadata(&mut self, parts: &[&str], line_number: usize) -> Result<(), SosaError> {
        if starts_with(parts, &["instance", "id"]) && parts.len() > 2 {
            self.instance_id = Some(parts[2..].join(" "));
        } else if starts_with(parts, &["family"]) && parts.len() > 1 {
            self.family = Some(parts[1..].join(" "));
        } else if starts_with(parts, &["n"]) && parts.len() > 1 {
            self.metadata_n = Some(parse_usize(parts[1], line_number, "metadata n")?);
        } else if starts_with(parts, &["m"]) && parts.len() > 1 {
            self.metadata_m = Some(parse_usize(parts[1], line_number, "metadata m")?);
        } else if starts_with(parts, &["num", "colors"]) && parts.len() > 2 {
            self.num_colors = Some(parse_usize(parts[2], line_number, "metadata num_colors")?);
        }
        Ok(())
    }

    fn parse_problem(
        &mut self,
        parts: &[&str],
        line_number: usize,
        line: &str,
    ) -> Result<(), SosaError> {
        if parts.len() != 4 || (parts[1] != "edge" && parts[1] != "col") {
            return input_error(format!(
                "unsupported DIMACS problem line at line {line_number}: {line}"
            ));
        }
        if self.problem.is_some() {
            return input_error(format!(
                "duplicate DIMACS problem line at line {line_number}"
            ));
        }
        self.problem = Some(Problem {
            n: parse_usize(parts[2], line_number, "vertex count")?,
            m: parse_usize(parts[3], line_number, "edge count")?,
        });
        Ok(())
    }

    fn summary(&self) -> Result<InstanceSummary, SosaError> {
        let problem = self
            .problem
            .ok_or_else(|| SosaError::Input("DIMACS file is missing a problem line".to_string()))?;
        Ok(InstanceSummary {
            instance_id: self.instance_id.clone(),
            family: self.family.clone(),
            n: problem.n,
            m: problem.m,
            num_colors: self.num_colors,
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum CircleAction {
    Start,
    End,
    EndpointLine,
    Metadata,
}

fn validate_metadata_consistency(parser: &ParserState, problem: Problem) -> Result<(), SosaError> {
    if let Some(metadata_n) = parser.metadata_n {
        if metadata_n != problem.n {
            return input_error(format!(
                "metadata n={metadata_n} does not match problem line n={}",
                problem.n
            ));
        }
    }
    if let Some(metadata_m) = parser.metadata_m {
        if metadata_m != problem.m {
            return input_error(format!(
                "metadata m={metadata_m} does not match problem line m={}",
                problem.m
            ));
        }
    }
    Ok(())
}

fn validate_circle_order(n: usize, circle_order: &[usize]) -> Result<(), SosaError> {
    let expected_len = n
        .checked_mul(2)
        .ok_or_else(|| SosaError::Input(format!("vertex count {n} is too large")))?;
    if circle_order.len() != expected_len {
        return input_error(format!(
            "circle order has {} endpoint(s), expected {expected_len}",
            circle_order.len()
        ));
    }
    let mut counts = vec![0u8; n];
    for &vertex in circle_order {
        if vertex > n {
            return input_error(format!("circle vertex id {vertex} out of range 1..{n}"));
        }
        let count = &mut counts[vertex - 1];
        *count = count.saturating_add(1);
    }
    for (index, count) in counts.iter().copied().enumerate() {
        if count != 2 {
            return input_error(format!(
                "vertex {} appears {count} time(s) in circle order, expected 2",
                index + 1
            ));
        }
    }
    Ok(())
}

fn circle_action(parts: &[&str]) -> Option<&'static str> {
    if parts.len() == 3 && parts[0] == "ircle" && parts[1] == "representation" {
        match parts[2] {
            "START" => Some("START"),
            "END" => Some("END"),
            _ => Some("UNKNOWN"),
        }
    } else {
        None
    }
}

fn starts_with(parts: &[&str], prefix: &[&str]) -> bool {
    parts.len() >= prefix.len() && parts[..prefix.len()] == *prefix
}

fn parse_usize(token: &str, line_number: usize, name: &str) -> Result<usize, SosaError> {
    token
        .parse::<usize>()
        .map_err(|_| SosaError::Input(format!("invalid {name} {token:?} at line {line_number}")))
}

fn parse_positive_usize(token: &str, line_number: usize) -> Result<usize, SosaError> {
    let value = parse_usize(token, line_number, "positive integer")?;
    if value == 0 {
        return input_error(format!("vertex id 0 out of range at line {line_number}"));
    }
    Ok(value)
}

fn edge_key(u: usize, v: usize) -> u64 {
    let (a, b) = if u < v { (u, v) } else { (v, u) };
    ((a as u64) << 32) | b as u64
}

fn input_error<T>(message: String) -> Result<T, SosaError> {
    Err(SosaError::Input(message))
}

#[cfg(test)]
mod tests {
    use std::io::Cursor;

    use super::*;

    const SAMPLE: &str = "\
c format version 1
c instance id sample
c family rc
c n 3
c m 3
c num colors 3
c ircle representation START
c 1 2 3 1 2 3
c ircle representation END
p edge 3 3
e 1 2
e 1 3
e 2 3
";

    #[test]
    fn inspects_concise_summary() {
        let summary = inspect_dimacs_circle(Cursor::new(SAMPLE)).unwrap();

        assert_eq!(summary.instance_id.as_deref(), Some("sample"));
        assert_eq!(summary.family.as_deref(), Some("rc"));
        assert_eq!(summary.n, 3);
        assert_eq!(summary.m, 3);
        assert_eq!(summary.num_colors, Some(3));
    }

    #[test]
    fn validates_structural_file() {
        let summary = validate_dimacs_circle(Cursor::new(SAMPLE)).unwrap();

        assert_eq!(summary.n, 3);
        assert_eq!(summary.m, 3);
    }

    #[test]
    fn rejects_duplicate_edge() {
        let error = validate_dimacs_circle(Cursor::new(
            "\
c ircle representation START
c 1 2 1 2
c ircle representation END
p edge 2 2
e 1 2
e 2 1
",
        ))
        .unwrap_err();

        assert!(error.to_string().contains("duplicate edge"));
    }

    #[test]
    fn rejects_metadata_mismatch() {
        let error = validate_dimacs_circle(Cursor::new(
            "\
c n 4
c ircle representation START
c 1 2 1 2
c ircle representation END
p edge 2 1
e 1 2
",
        ))
        .unwrap_err();

        assert!(error.to_string().contains("metadata n=4"));
    }
}
