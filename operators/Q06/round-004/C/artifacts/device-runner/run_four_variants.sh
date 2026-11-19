#!/bin/bash
set -uo pipefail

RUNNER_DIR="$(cd "$(dirname "$0")" && pwd)"
ROUND_DIR="$(cd "$RUNNER_DIR/.." && pwd)"
PROJECT_DIR_INPUT="${1:-}"
CASES_DIR="${2:-$ROUND_DIR/device-case/edge-legal-cancellation}"
DEVICE_ID="${DEVICE_ID:?set DEVICE_ID after checking npu-smi}"
PYTHON="${PYTHON:-python3}"

if [ -z "$PROJECT_DIR_INPUT" ]; then
  echo "usage: DEVICE_ID=<id> bash run_four_variants.sh <explicit-P-or-F-project> [cases-dir]" >&2
  exit 64
fi
if [ ! -d "$PROJECT_DIR_INPUT" ]; then
  echo "project directory does not exist: $PROJECT_DIR_INPUT" >&2
  exit 66
fi
PROJECT_DIR="$(realpath "$PROJECT_DIR_INPUT")"
VENDOR_ROOT="$PROJECT_DIR/build/packages/vendors/pad_v3_grad_custom"
OP_API_HEADER="$VENDOR_ROOT/op_api/include/aclnn_pad_v3_grad.h"
EXPECTED_LIBRARY="$VENDOR_ROOT/op_api/lib/libcust_opapi.so"
VERSION_INFO="$VENDOR_ROOT/version.info"
BUILD_DIR="${RUNNER_BUILD_DIR:-$PROJECT_DIR/build/edge-case-runner-r004}"
CMAKE_CACHE="$BUILD_DIR/CMakeCache.txt"
CMAKE_CONFIG="$BUILD_DIR/vendor-config.json"
RUNNER_BINARY="$BUILD_DIR/edge_case_runner"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${STAMP}-$$"
RUN_ROOT="${RUN_ROOT:-$ROUND_DIR/r004/device/$RUN_ID}"

if [ -e "$RUN_ROOT" ] && [ -n "$(find "$RUN_ROOT" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
  echo "refusing to reuse non-empty RUN_ROOT: $RUN_ROOT" >&2
  exit 73
fi
mkdir -p "$RUN_ROOT"

NPU_LOG="$RUN_ROOT/npu-smi.log"
if command -v npu-smi >/dev/null 2>&1; then
  npu-smi info >"$NPU_LOG" 2>&1
  NPU_SMI_EXIT=$?
else
  printf '%s\n' "npu-smi not found on PATH" >"$NPU_LOG"
  NPU_SMI_EXIT=127
fi
printf '%s\n' "$0 $*" >"$RUN_ROOT/top-level-command.txt"

"$PYTHON" "$RUNNER_DIR/stage_cases.py" --cases "$CASES_DIR" --run-root "$RUN_ROOT" \
  >"$RUN_ROOT/stage.log" 2>&1
STAGE_EXIT=$?
if [ "$STAGE_EXIT" -ne 0 ]; then
  cat "$RUN_ROOT/stage.log" >&2
  exit "$STAGE_EXIT"
fi
mapfile -t CASE_IDS <"$RUN_ROOT/case-ids.txt"
if [ "${#CASE_IDS[@]}" -ne 4 ]; then
  echo "expected exactly four cases, got ${#CASE_IDS[@]}" >&2
  exit 65
fi

"$PYTHON" "$RUNNER_DIR/runner_metadata.py" begin \
  --run-root "$RUN_ROOT" \
  --run-id "$RUN_ID" \
  --project-dir "$PROJECT_DIR" \
  --vendor-root "$VENDOR_ROOT" \
  --expected-library "$EXPECTED_LIBRARY" \
  --cmake-cache "$CMAKE_CACHE" \
  --vendor-config "$CMAKE_CONFIG" \
  --runner-binary "$RUNNER_BINARY" \
  --cases "$CASES_DIR" \
  --device-id "$DEVICE_ID" \
  --npu-smi-log "$NPU_LOG" \
  --npu-smi-exit-code "$NPU_SMI_EXIT"
BEGIN_EXIT=$?
if [ "$BEGIN_EXIT" -ne 0 ]; then
  exit "$BEGIN_EXIT"
fi

PACKAGE_BUILD_EXIT=0
CONFIGURE_EXIT=0
COMPILE_EXIT=0
DEVICE_STARTED=0
NPU_BEFORE_CASES="$RUN_ROOT/npu-smi-before-cases.log"
NPU_AFTER_CASES="$RUN_ROOT/npu-smi-after-cases.log"
NPU_BEFORE_CASES_EXIT=127
NPU_AFTER_CASES_EXIT=127
if [ -z "${ASCEND_HOME_PATH:-}" ]; then
  printf '%s\n' "ASCEND_HOME_PATH is unset; source CANN set_env.sh first" \
    >"$RUN_ROOT/build-error.log"
  PACKAGE_BUILD_EXIT=69
  CONFIGURE_EXIT=69
  COMPILE_EXIT=69
elif [ "$NPU_SMI_EXIT" -ne 0 ]; then
  printf '%s\n' "npu-smi did not complete successfully; refusing a device verdict" \
    >"$RUN_ROOT/build-error.log"
  PACKAGE_BUILD_EXIT=70
  CONFIGURE_EXIT=70
  COMPILE_EXIT=70
elif ! command -v cmake >/dev/null 2>&1; then
  printf '%s\n' "cmake is missing from PATH" >"$RUN_ROOT/build-error.log"
  PACKAGE_BUILD_EXIT=69
  CONFIGURE_EXIT=69
  COMPILE_EXIT=69
else
  (
    cd "$PROJECT_DIR" &&
    bash build.sh -j4
  ) >"$RUN_ROOT/package-build.log" 2>&1
  PACKAGE_BUILD_EXIT=$?
  if [ "$PACKAGE_BUILD_EXIT" -eq 0 ] &&
     { [ ! -f "$OP_API_HEADER" ] || [ ! -f "$EXPECTED_LIBRARY" ] || [ ! -f "$VERSION_INFO" ]; }; then
    printf '%s\n' "selected project build did not produce the required vendor artifacts" \
      >"$RUN_ROOT/build-error.log"
    PACKAGE_BUILD_EXIT=71
  fi
fi

if [ "$PACKAGE_BUILD_EXIT" -eq 0 ] && [ -n "${ASCEND_HOME_PATH:-}" ]; then
  cmake --version >"$RUN_ROOT/cmake-version.log" 2>&1
  cmake -S "$RUNNER_DIR" -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DPAD_V3_GRAD_PROJECT_DIR="$PROJECT_DIR" \
    >"$RUN_ROOT/cmake-configure.log" 2>&1
  CONFIGURE_EXIT=$?
fi
if [ "$CONFIGURE_EXIT" -eq 0 ]; then
  cmake --build "$BUILD_DIR" --parallel "${CANNJUDGE_COMPILE_JOBS:-4}" \
    >"$RUN_ROOT/cmake-build.log" 2>&1
  COMPILE_EXIT=$?
fi

if [ "$COMPILE_EXIT" -eq 0 ]; then
  grep -E '^PAD_V3_GRAD_(PROJECT_DIR|RESOLVED_VENDOR_ROOT)' "$CMAKE_CACHE" \
    >"$RUN_ROOT/cmake-cache-binding.log" 2>&1 || true
  ldd "$RUNNER_BINARY" >"$RUN_ROOT/loader-ldd.log" 2>&1 || true
  export ASCEND_CUSTOM_OPP_PATH="$VENDOR_ROOT${ASCEND_CUSTOM_OPP_PATH:+:$ASCEND_CUSTOM_OPP_PATH}"
  export LD_LIBRARY_PATH="$VENDOR_ROOT/op_api/lib:${ASCEND_HOME_PATH}/lib64:${LD_LIBRARY_PATH:-}"
  export PAD_V3_GRAD_EXPECTED_LIBRARY="$EXPECTED_LIBRARY"
  DEVICE_STARTED=1
  npu-smi info >"$NPU_BEFORE_CASES" 2>&1
  NPU_BEFORE_CASES_EXIT=$?

  for case_id in "${CASE_IDS[@]}"; do
    dtype="${case_id%%-*}"
    layout="${case_id#*-}"
    case_root="$RUN_ROOT/$case_id"
    rm -rf "$case_root/output"
    mkdir -p "$case_root/output"
    stdout_log="$case_root/stdout.log"
    stderr_log="$case_root/stderr.log"
    started_ns="$("$PYTHON" -c 'import time; print(time.time_ns())')"
    "$RUNNER_BINARY" "$case_root" "$DEVICE_ID" "$dtype" "$layout" "$case_id" \
      >"$stdout_log" 2>"$stderr_log"
    runner_exit=$?
    ended_ns="$("$PYTHON" -c 'import time; print(time.time_ns())')"
    "$PYTHON" "$RUNNER_DIR/runner_metadata.py" case \
      --case-root "$case_root" \
      --case-id "$case_id" \
      --started-at-ns "$started_ns" \
      --ended-at-ns "$ended_ns" \
      --exit-code "$runner_exit" \
      --command "$RUNNER_BINARY $case_root $DEVICE_ID $dtype $layout $case_id" \
      --stdout "$stdout_log" \
      --stderr "$stderr_log"
  done
  npu-smi info >"$NPU_AFTER_CASES" 2>&1
  NPU_AFTER_CASES_EXIT=$?
fi

VERIFY_EXIT=1
"$PYTHON" "$RUNNER_DIR/verify_outputs.py" \
  --cases "$CASES_DIR" \
  --run-root "$RUN_ROOT" \
  --execution-mode device \
  --run-record "$RUN_ROOT/run-record.json" \
  --output "$RUN_ROOT/acceptance.json" \
  >"$RUN_ROOT/acceptance.log" 2>&1
VERIFY_EXIT=$?

FINALIZE_ARGS=(
  "$RUNNER_DIR/runner_metadata.py" finalize
  --run-root "$RUN_ROOT" \
  --package-build-exit-code "$PACKAGE_BUILD_EXIT" \
  --configure-exit-code "$CONFIGURE_EXIT" \
  --compile-exit-code "$COMPILE_EXIT" \
  --verify-exit-code "$VERIFY_EXIT" \
  --npu-smi-before-cases "$NPU_BEFORE_CASES" \
  --npu-smi-before-cases-exit-code "$NPU_BEFORE_CASES_EXIT" \
  --npu-smi-after-cases "$NPU_AFTER_CASES" \
  --npu-smi-after-cases-exit-code "$NPU_AFTER_CASES_EXIT"
)
if [ "$DEVICE_STARTED" -eq 1 ]; then
  FINALIZE_ARGS+=(--device-execution-started)
fi
"$PYTHON" "${FINALIZE_ARGS[@]}"

cat "$RUN_ROOT/acceptance.log"
printf 'RUN_ROOT=%s\n' "$RUN_ROOT"
exit "$VERIFY_EXIT"
