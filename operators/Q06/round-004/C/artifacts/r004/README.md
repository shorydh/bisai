# R004 evidence map

- `original-device-runner/`: byte-preserved R003 runner used for defect
  reproduction.
- `synth/legacy-repro-v1/`: legacy fifth-case and short-output false PASS,
  followed by corrected verifier results on the same synthetic fixtures.
- `synth/vendor-switch-v4/`: two-path CMake cache evidence. A and B were
  configured successively in one temporary build directory; both configure
  logs exited 0 and their cache/config records name different projects.
- `synth/suite-summary.json`: final no-device test suite result.
- `synth/final-*.log`: final test output.
- `synth/shellcheck.log` and `../results/R004-shellcheck.json`: shell static
  check.
- `../logs/R004-device-entry-probe.json`: current device-entry blocker.
- `../results/R004-baseline-audit.json`: frozen P/F/case/reference identity and
  UT fixture observations.

All paths under `synth/` are synthetic evidence. They do not represent NPU
execution and must not be labeled as device output.
