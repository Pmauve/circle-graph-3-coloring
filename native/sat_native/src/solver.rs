use std::path::Path;

use circle_core::error::SosaError;

use crate::encode::encode_dimacs_edge_file_to_writer;
use crate::external::solve_with_stdin;
use crate::{SatConfig, SatStatus, SatSummary};

pub fn solve_dimacs_edge_file(path: &Path, config: SatConfig) -> Result<SatSummary, SosaError> {
    if config.backend != "dimacs-pipe" {
        return Err(SosaError::Input(format!(
            "unsupported SAT backend {:?}, expected \"dimacs-pipe\"",
            config.backend
        )));
    }

    let output = solve_with_stdin(&config.solver_bin, config.timeout_s, |stdin| {
        encode_dimacs_edge_file_to_writer(path, stdin)?;
        Ok(())
    })?;
    Ok(SatSummary {
        status: output.status,
        core_time_s: output.core_time_s,
        error: None,
    })
}

pub fn status_to_output(status: SatStatus) -> &'static str {
    match status {
        SatStatus::Colorable => "COLORABLE",
        SatStatus::NotColorable => "NOT_COLORABLE",
        SatStatus::Unknown => "UNKNOWN",
    }
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::*;

    #[test]
    fn maps_status_to_native_output_tokens() {
        assert_eq!(status_to_output(SatStatus::Colorable), "COLORABLE");
        assert_eq!(status_to_output(SatStatus::NotColorable), "NOT_COLORABLE");
        assert_eq!(status_to_output(SatStatus::Unknown), "UNKNOWN");
    }

    #[test]
    fn solves_colorable_instance_with_fake_pipe_solver() {
        let instance = write_temp_file(
            "colorable",
            "\
p edge 2 1
e 1 2
",
        );
        let solver = write_fake_solver(
            "sat",
            "s SATISFIABLE\nc process-time: 0.12 seconds",
            Some(10),
        );
        let summary = solve_dimacs_edge_file(
            &instance,
            SatConfig {
                backend: "dimacs-pipe".to_string(),
                solver_bin: solver.to_string_lossy().to_string(),
                timeout_s: Some(5),
            },
        )
        .unwrap();

        assert_eq!(summary.status, SatStatus::Colorable);
        assert_eq!(summary.core_time_s, Some(0.12));
        let _ = fs::remove_file(instance);
        let _ = fs::remove_file(solver);
    }

    #[test]
    fn solves_uncolorable_instance_with_fake_pipe_solver() {
        let instance = write_temp_file(
            "uncolorable",
            "\
p edge 4 6
e 1 2
e 1 3
e 1 4
e 2 3
e 2 4
e 3 4
",
        );
        let solver = write_fake_solver(
            "unsat",
            "s UNSATISFIABLE\nc process-time: 0.12 seconds",
            Some(20),
        );
        let summary = solve_dimacs_edge_file(
            &instance,
            SatConfig {
                backend: "dimacs-pipe".to_string(),
                solver_bin: solver.to_string_lossy().to_string(),
                timeout_s: Some(5),
            },
        )
        .unwrap();

        assert_eq!(summary.status, SatStatus::NotColorable);
        assert_eq!(summary.core_time_s, Some(0.12));
        let _ = fs::remove_file(instance);
        let _ = fs::remove_file(solver);
    }

    #[test]
    fn rejects_unknown_status_with_nonzero_solver_exit() {
        let instance = write_temp_file("unknown", "p edge 1 0\n");
        let solver = write_fake_solver("unknown", "s UNKNOWN", Some(1));
        let error = solve_dimacs_edge_file(
            &instance,
            SatConfig {
                backend: "dimacs-pipe".to_string(),
                solver_bin: solver.to_string_lossy().to_string(),
                timeout_s: Some(5),
            },
        )
        .unwrap_err();

        assert!(error.to_string().contains("exited with"));
        let _ = fs::remove_file(instance);
        let _ = fs::remove_file(solver);
    }

    #[test]
    fn rejects_unknown_backend() {
        let instance = write_temp_file("unknown-backend", "p edge 1 0\n");
        let error = solve_dimacs_edge_file(
            &instance,
            SatConfig {
                backend: "other".to_string(),
                solver_bin: "unused".to_string(),
                timeout_s: None,
            },
        )
        .unwrap_err();

        assert!(error.to_string().contains("unsupported SAT backend"));
        let _ = fs::remove_file(instance);
    }

    fn write_temp_file(label: &str, content: &str) -> PathBuf {
        let mut path = std::env::temp_dir();
        path.push(format!("sat-native-{label}-{}.col", unique_suffix()));
        fs::write(&path, content).unwrap();
        path
    }

    fn write_fake_solver(label: &str, output_line: &str, exit_code: Option<i32>) -> PathBuf {
        let mut path = std::env::temp_dir();
        #[cfg(windows)]
        {
            path.push(format!("sat-native-fake-{label}-{}.cmd", unique_suffix()));
            let exit_line = exit_code
                .map(|code| format!("exit /b {code}\r\n"))
                .unwrap_or_default();
            let output_lines = output_line
                .lines()
                .map(|line| format!("echo {line}\r\n"))
                .collect::<String>();
            fs::write(
                &path,
                format!("@echo off\r\nmore > nul\r\n{output_lines}{exit_line}"),
            )
            .unwrap();
        }
        #[cfg(not(windows))]
        {
            use std::os::unix::fs::PermissionsExt;

            path.push(format!("sat-native-fake-{label}-{}", unique_suffix()));
            let exit_line = exit_code
                .map(|code| format!("exit {code}\n"))
                .unwrap_or_default();
            fs::write(
                &path,
                format!("#!/bin/sh\ncat >/dev/null\nprintf '%s\\n' '{output_line}'\n{exit_line}"),
            )
            .unwrap();
            let mut permissions = fs::metadata(&path).unwrap().permissions();
            permissions.set_mode(0o755);
            fs::set_permissions(&path, permissions).unwrap();
        }
        path
    }

    fn unique_suffix() -> u128 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    }
}
