use std::fs;
use std::process::Command;

fn binary() -> String {
    env!("CARGO_BIN_EXE_three_col_native").to_string()
}

#[test]
fn inspect_outputs_concise_json() {
    let path = fixture_path("inspect-valid.col");
    write_valid_instance(&path);

    let output = Command::new(binary())
        .args(["instance", "inspect", path.to_str().unwrap()])
        .output()
        .unwrap();

    assert!(output.status.success());
    assert_eq!(
        String::from_utf8(output.stdout).unwrap().trim(),
        r#"{"status":"ok","instance_id":"sample","family":"rc","n":3,"m":3,"num_colors":3}"#
    );
}

#[test]
fn validate_reports_invalid_input_as_json() {
    let path = fixture_path("invalid.col");
    fs::write(
        &path,
        "\
c ircle representation START
c 1 1
c ircle representation END
p edge 1 1
e 1 1
",
    )
    .unwrap();

    let output = Command::new(binary())
        .args(["instance", "validate", path.to_str().unwrap()])
        .output()
        .unwrap();

    assert_eq!(output.status.code(), Some(2));
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains(r#""status":"error""#));
    assert!(stdout.contains("self-loop"));
}

fn fixture_path(name: &str) -> std::path::PathBuf {
    let mut path = std::env::temp_dir();
    path.push(format!("three-col-native-{}-{name}", std::process::id()));
    path
}

fn write_valid_instance(path: &std::path::Path) {
    fs::write(
        path,
        "\
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
",
    )
    .unwrap();
}
