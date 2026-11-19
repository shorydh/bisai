#!/bin/bash
set -euo pipefail

RUNNER_DIR="$(cd "$(dirname "$0")" && pwd)"
ROUND_DIR="$(cd "$RUNNER_DIR/.." && pwd)"
PROJECT_DIR="${1:-$ROUND_DIR/source/P}"
CASES_DIR="$ROUND_DIR/device-case/edge-legal-cancellation"
DEVICE_ID="${DEVICE_ID:-0}"

: "${ASCEND_HOME_PATH:?source the CANN set_env.sh first}"

if [ ! -f "$PROJECT_DIR/build/packages/vendors/pad_v3_grad_custom/op_api/include/aclnn_pad_v3_grad.h" ]; then
  bash "$PROJECT_DIR/build.sh" -j4
fi

export ASCEND_CUSTOM_OPP_PATH="$PROJECT_DIR/build/packages/vendors/pad_v3_grad_custom${ASCEND_CUSTOM_OPP_PATH:+:$ASCEND_CUSTOM_OPP_PATH}"
export LD_LIBRARY_PATH="$PROJECT_DIR/build/packages/vendors/pad_v3_grad_custom/op_api/lib:$ASCEND_HOME_PATH/lib64:${LD_LIBRARY_PATH:-}"

cmake -S "$RUNNER_DIR" -B "$PROJECT_DIR/build/edge-case-runner"
cmake --build "$PROJECT_DIR/build/edge-case-runner" --parallel "${CANNJUDGE_COMPILE_JOBS:-4}"

for dtype in int32 int64; do
  for layout in contiguous split; do
    case_dir="$CASES_DIR/$dtype-$layout"
    mkdir -p "$case_dir/output"
    "$PROJECT_DIR/build/edge-case-runner/edge_case_runner" \
      "$case_dir" "$DEVICE_ID" "$dtype" "$layout" \
      2>&1 | tee "$case_dir/device-run.log"
  done
done

python3 "$RUNNER_DIR/verify_outputs.py" \
  --cases "$CASES_DIR" \
  --output "$ROUND_DIR/results/R003-device-four-variants.json"
