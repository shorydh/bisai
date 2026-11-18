#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="$ROOT/tests/ut/build"
SOC_VERSION="${SOC_VERSION:-Ascend910B3}"

# Each invocation receives fresh directories so a failed host fixture cannot
# accidentally supply old tiling bytes to the CPU kernel simulation.
evidence_root="${PADV3GRAD_UT_ARTIFACT_DIR:-$BUILD/evidence}"
mkdir -p "$evidence_root"
evidence="$(mktemp -d "$evidence_root/run-XXXXXXXX")"
export PADV3GRAD_UT_FIXTURE_DIR="$evidence/fixtures"
export SAMPLE_DIR="$evidence/sample"
mkdir -p "$PADV3GRAD_UT_FIXTURE_DIR"
printf 'UT evidence: %s\n' "$evidence"

cmake -S "$ROOT/tests/ut" -B "$BUILD" \
    -DCMAKE_BUILD_TYPE=Debug -DGTEST_SOURCE_DIR="${GTEST_SOURCE_DIR:-/usr/src/googletest}" -DSOC_VERSION="$SOC_VERSION"
cmake --build "$BUILD" --parallel "${CANNJUDGE_COMPILE_JOBS:-4}"
"$BUILD/op_host/pad_v3_grad_op_host_ut" --gtest_output="xml:$evidence/host.xml"
python3 "$ROOT/samples/sample.py" generate --directory "$SAMPLE_DIR"
"$BUILD/op_kernel/pad_v3_grad_op_kernel_ut" --gtest_output="xml:$evidence/kernel.xml"
python3 "$ROOT/samples/sample.py" verify --directory "$SAMPLE_DIR"
python3 - "$evidence/host.xml" "$evidence/kernel.xml" <<'PY'
import sys
from xml.etree import ElementTree

required_cases = (
    {'PadV3GradHost.ReflectTwoBlockCompactFp32', 'PadV3GradHost.EdgeAsymmetricCompactFp32'},
    {'PadV3GradKernelTest.PublicReflectSample', 'PadV3GradKernelTest.EdgeAccumulatesRepeatedContributions'},
)
for xml, required in zip(sys.argv[1:], required_cases):
    cases = ElementTree.parse(xml).findall('.//testcase')
    ran = {f"{case.get('classname')}.{case.get('name')}" for case in cases}
    missing = sorted(required - ran)
    if missing:
        raise SystemExit(f"{xml}: missing required tests: {', '.join(missing)}")
    if any(case.get('status') != 'run' or case.find('skipped') is not None
           or case.find('failure') is not None or case.find('error') is not None for case in cases):
        raise SystemExit('Expected every listed test to run and pass: ' + xml)
    print(f'{xml}: {len(cases)} tests ran')
PY
if [ -x "$BUILD/op_api/pad_v3_grad_op_api_ut" ]; then
    export ASCEND_CUSTOM_OPP_PATH="$ROOT/build/packages/vendors/pad_v3_grad_custom${ASCEND_CUSTOM_OPP_PATH:+:$ASCEND_CUSTOM_OPP_PATH}"
    "$BUILD/op_api/pad_v3_grad_op_api_ut" --gtest_output="xml:$evidence/op_api.xml"
fi
