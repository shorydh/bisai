# R004 PadV3Grad legal-edge runner

This directory is a corrected copy of the R003 runner. The frozen P/F
projects, inputs, and goldens are byte-preserved under `artifacts/source/` and
`artifacts/device-case/`.

## Contract

- Cases are sourced only from `device-case/edge-legal-cancellation/manifest.json`.
  The four required IDs are int32/int64 x contiguous/split. Extra files and
  directories, including a nested `manifest.json`, are not cases.
- Every fixture is checked against its dtype, shape, byte size, SHA256, mode,
  padding layout, golden values `[0,0,0]`, and `rtol=atol=1e-4`.
- Every device output must be exactly 12 bytes and decode to exactly three
  FP32 values. Missing, short, oversized, stale, NaN, and out-of-tolerance
  outputs fail.
- Synthetic PASS fixtures are always reported with `device_execution=false`.
  They cannot be promoted to NPU evidence.
- Device PASS additionally requires four zero runner exit codes, synchronized
  streams, matching CMake/vendor configuration, and an actual
  `libcust_opapi.so` mapping equal to the selected project's library.

## Device command

Check `npu-smi info` and shared load first, then run:

```bash
source /path/to/cann-9.1.0/set_env.sh
DEVICE_ID=<actual-device> bash artifacts/device-runner/run_four_variants.sh \
  /absolute/path/to/artifacts/source/P
```

The explicit project path is passed unchanged through the shell to the
`PAD_V3_GRAD_PROJECT_DIR` CMake cache entry. CMake validates and records the
vendor header, library, and version. At runtime, the runner requires
`PAD_V3_GRAD_EXPECTED_LIBRARY` and checks `/proc/self/maps` after execution.

The default output root is a fresh
`artifacts/r004/device/<UTC-run-id>/`. It contains:

- `run-record.json`: selected project/vendor, CMake cache/config, environment,
  `npu-smi` output reference, fixture hashes before and after, and build exits.
- `<case_id>/output/y.bin`: synchronized device output copied to a fresh run
  directory.
- `<case_id>/{stdout.log,stderr.log,invocation.json,case-run.json}`.
- `acceptance.json`: strict per-case verdict, raw values, and element errors.
- build, loader, cache-binding, and command logs.

If a package is absent, the script runs the frozen project's `build.sh -j4`.
If CANN is unavailable, build/configure exits are recorded and the four cases
remain missing; no numerical verdict is claimed.

## Synthetic regression tests

```bash
python3 artifacts/tests/test_r004_runner.py
python3 artifacts/tests/test_vendor_switch.py
```

The second test can be run on a target host with CMake. It configures two
different fake projects into one build cache and verifies both cache and vendor
config switching without compiling either project.
