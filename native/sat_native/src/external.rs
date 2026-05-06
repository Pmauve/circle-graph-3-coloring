use std::io::Write;
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use circle_core::error::SosaError;

use crate::SatStatus;

#[derive(Debug)]
pub struct ExternalSolveOutput {
    pub status: SatStatus,
    pub solve_time_s: f64,
}

pub fn solve_with_stdin(
    solver_bin: &str,
    dimacs_cnf: &str,
    timeout_s: Option<u64>,
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

    {
        let stdin = child.stdin.as_mut().ok_or_else(|| {
            SosaError::Internal("SAT solver stdin pipe was not available".to_string())
        })?;
        stdin.write_all(dimacs_cnf.as_bytes())?;
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
    let solve_time_s = started_at.elapsed().as_secs_f64();
    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
    if !output.status.success() {
        return Err(SosaError::Input(format!(
            "SAT solver exited with {}; stdout_tail={}; stderr_tail={}",
            output.status,
            tail(&stdout),
            tail(&stderr)
        )));
    }
    let status = parse_solver_status(&stdout).ok_or_else(|| {
        SosaError::Input(format!(
            "SAT solver output is missing SAT/UNSAT status; stdout_tail={}; stderr_tail={}",
            tail(&stdout),
            tail(&stderr)
        ))
    })?;
    Ok(ExternalSolveOutput {
        status,
        solve_time_s,
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
}
