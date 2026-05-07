use std::io::Write;
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use circle_core::error::SosaError;

use crate::SatStatus;

#[derive(Debug)]
pub struct ExternalSolveOutput {
    pub status: SatStatus,
    pub core_time_s: Option<f64>,
}

pub fn solve_with_stdin(
    solver_bin: &str,
    timeout_s: Option<u64>,
    write_input: impl FnOnce(&mut dyn Write) -> Result<(), SosaError>,
) -> Result<ExternalSolveOutput, SosaError> {
    let started_at = Instant::now();
    let mut child = Command::new(solver_bin)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| {
            SosaError::Input(format!(
                "failed to start SAT solver {solver_bin:?}: {error}"
            ))
        })?;

    let write_result = {
        let stdin = child.stdin.as_mut().ok_or_else(|| {
            SosaError::Internal("SAT solver stdin pipe was not available".to_string())
        })?;
        write_input(stdin)
    };
    if let Err(error) = write_result {
        drop(child.stdin.take());
        let _ = child.kill();
        let _ = child.wait();
        return Err(error);
    }
    drop(child.stdin.take());

    let timeout = timeout_s.map(Duration::from_secs);
    loop {
        if child.try_wait()?.is_some() {
            break;
        }
        if let Some(timeout) = timeout {
            if started_at.elapsed() > timeout {
                let _ = child.kill();
                let output = child.wait_with_output()?;
                return Err(SosaError::Input(format!(
                    "SAT solver timed out after {}s; stdout_tail={}; stderr_tail={}",
                    timeout.as_secs(),
                    tail(&String::from_utf8_lossy(&output.stdout)),
                    tail(&String::from_utf8_lossy(&output.stderr))
                )));
            }
        }
        thread::sleep(Duration::from_millis(10));
    }

    let output = child.wait_with_output()?;
    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
    let status = parse_solver_status(&stdout).ok_or_else(|| {
        SosaError::Input(format!(
            "SAT solver output is missing SAT/UNSAT status; stdout_tail={}; stderr_tail={}",
            tail(&stdout),
            tail(&stderr)
        ))
    })?;
    if !solver_exit_matches_status(output.status.code(), status) {
        return Err(SosaError::Input(format!(
            "SAT solver exited with {}; stdout_tail={}; stderr_tail={}",
            output.status,
            tail(&stdout),
            tail(&stderr)
        )));
    }
    let core_time_s = parse_solver_time_s(&stdout);
    Ok(ExternalSolveOutput {
        status,
        core_time_s,
    })
}

pub fn parse_solver_status(stdout: &str) -> Option<SatStatus> {
    for raw_line in stdout.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('c') {
            continue;
        }
        let mut parts = line.split_whitespace();
        let first = parts.next()?;
        let status_token = if first == "s" {
            parts.next()
        } else {
            Some(first)
        };
        match status_token {
            Some("SATISFIABLE") | Some("SAT") => return Some(SatStatus::Colorable),
            Some("UNSATISFIABLE") | Some("UNSAT") => return Some(SatStatus::NotColorable),
            Some("UNKNOWN") => return Some(SatStatus::Unknown),
            _ => {}
        }
    }
    None
}

fn solver_exit_matches_status(exit_code: Option<i32>, status: SatStatus) -> bool {
    match (exit_code, status) {
        (Some(0), _) => true,
        (Some(10), SatStatus::Colorable) => true,
        (Some(20), SatStatus::NotColorable) => true,
        _ => false,
    }
}

pub fn parse_solver_time_s(stdout: &str) -> Option<f64> {
    for raw_line in stdout.lines().rev() {
        let line = raw_line
            .trim()
            .strip_prefix('c')
            .unwrap_or(raw_line.trim())
            .trim();
        let lower = line.to_ascii_lowercase();
        if lower.contains("total process time since initialization")
            || lower.starts_with("process-time:")
            || lower.starts_with("process time:")
        {
            if let Some(value) = first_float_after_separator(line) {
                return Some(value);
            }
        }
    }
    None
}

fn first_float_after_separator(line: &str) -> Option<f64> {
    let tail = line.split_once(':').map(|(_, tail)| tail).unwrap_or(line);
    tail.split_whitespace()
        .find_map(|token| token.parse::<f64>().ok())
}

fn tail(text: &str) -> String {
    const LIMIT: usize = 4000;
    if text.len() <= LIMIT {
        return text.to_string();
    }
    text[text.len() - LIMIT..].to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_common_solver_status_lines() {
        assert_eq!(
            parse_solver_status("c comment\ns SATISFIABLE\n"),
            Some(SatStatus::Colorable)
        );
        assert_eq!(
            parse_solver_status("s UNSATISFIABLE\n"),
            Some(SatStatus::NotColorable)
        );
        assert_eq!(parse_solver_status("SAT\n"), Some(SatStatus::Colorable));
        assert_eq!(
            parse_solver_status("UNSAT\n"),
            Some(SatStatus::NotColorable)
        );
        assert_eq!(parse_solver_status("s UNKNOWN\n"), Some(SatStatus::Unknown));
        assert_eq!(parse_solver_status("no status\n"), None);
    }

    #[test]
    fn parses_common_solver_time_lines() {
        assert_eq!(
            parse_solver_time_s(
                "c total process time since initialization:         1.23    seconds\n"
            ),
            Some(1.23)
        );
        assert_eq!(
            parse_solver_time_s("c process-time: 0.45 seconds\n"),
            Some(0.45)
        );
        assert_eq!(parse_solver_time_s("c real-time: 0.50 seconds\n"), None);
    }
}
