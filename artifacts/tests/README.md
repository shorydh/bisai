# Q06 round-001 C test entry points

All commands are run from `operators/Q06/round-001/C/`.

```powershell
python -B artifacts/tests/r6_boundary.py --output artifacts/results/E001-E003-model.json
python -B artifacts/tests/dispatch_matrix.py --output artifacts/results/E005-dispatch.json
```

The official Python reference check requires NumPy and a CPU build of PyTorch.
The FP32 case only needs an `ml_dtypes.bfloat16` stub, which the script installs
in memory.

```powershell
python -B artifacts/tests/reference_minimal_case.py `
  --reference-root <path-to-1367774>/code/samples `
  --output artifacts/results/E004-reference-minimal.json
```

The source verifier takes the original B ZIP and identity JSON and requires no
local CANN installation:

```powershell
./artifacts/tests/verify_sources.ps1 `
  -ZipPath operators/Q06/历史盘点/B/artifacts/official/1367774.zip `
  -IdentityPath operators/Q06/历史盘点/B/artifacts/official/1367774-identity.json `
  -OutputPath artifacts/results/source-verification-1367774.json
```

`r6_boundary.py` intentionally exits non-zero for E002 because the source model
found a pending FP32 reference difference. `reference_minimal_case.py` also
exits non-zero when that candidate remains outside tolerance. Neither script is
an Ascend build or NPU test.
