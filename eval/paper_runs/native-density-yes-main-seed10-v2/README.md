# Main Benchmark Run

This directory contains the public summary files for the benchmark run used in
the main dense-YES evaluation.

Included files:

- `spec.json`: benchmark specification.
- `manifest.json`: sanitized run metadata.
- `summary_by_n.csv`: grouped runtime and memory summaries by family, size, and solver.
- `summary_by_bucket.csv`: grouped summaries by family, size bucket, and solver.
- `summary_overall.csv`: grouped summaries by family and solver.
- `report.html`: static HTML report for browsing the run.

The raw `results.jsonl` file is not included because it is large and contains
environment-specific metadata. The CSV files are the machine-readable data used
for the paper plots.
