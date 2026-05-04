#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_URL="${ZYKOVCOLOR_REPO_URL:-https://github.com/trewes/ZykovColor.git}"
REF="${ZYKOVCOLOR_REF:-412e051417886ef0423565777c7814cda7f967e5}"
SRC_DIR="${ZYKOVCOLOR_SRC_DIR:-${ROOT}/external/ZykovColor}"
FETCH_ONLY=0

usage() {
  cat <<EOF
Usage: scripts/zykovcolor/install.sh [--fetch-only]

Fetch and optionally build ZykovColor at a pinned upstream commit.

Environment:
  ZYKOVCOLOR_REPO_URL  upstream git URL, default ${REPO_URL}
  ZYKOVCOLOR_REF       commit/ref to checkout, default ${REF}
  ZYKOVCOLOR_SRC_DIR   checkout directory, default ${SRC_DIR}
  GUROBI_HOME          required by upstream build.sh unless --fetch-only is used
  BOOST_ROOT           required by upstream build.sh unless --fetch-only is used
  JOBS                 parallel build jobs passed through to upstream build.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fetch-only)
      FETCH_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required tool: $1" >&2
    exit 1
  }
}

need git

mkdir -p "$(dirname "${SRC_DIR}")"
if [[ ! -d "${SRC_DIR}/.git" ]]; then
  git clone "${REPO_URL}" "${SRC_DIR}"
fi

git -C "${SRC_DIR}" fetch --tags origin
git -C "${SRC_DIR}" checkout "${REF}"

if [[ "${FETCH_ONLY}" -eq 1 ]]; then
  echo "ZykovColor source ready at ${SRC_DIR}"
  exit 0
fi

"${SRC_DIR}/build.sh"

BINARY="${SRC_DIR}/cmake-build/ZykovColor"
if [[ ! -x "${BINARY}" ]]; then
  echo "expected ZykovColor binary was not created at ${BINARY}" >&2
  exit 1
fi

echo "ZykovColor binary: ${BINARY}"
echo "Set for benchmark runs with:"
echo "  export ZYKOVCOLOR_BIN='${BINARY}'"
