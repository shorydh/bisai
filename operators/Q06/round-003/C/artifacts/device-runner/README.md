# R003 legal edge runner

This auxiliary runner is prepared but was not compiled or executed because no
CANN/NPU connection was available on the execution host.

Run it on a host with the authorized CANN 9.1 environment and the restored P
project:

```bash
source /path/to/cann/set_env.sh
DEVICE_ID=<actual-device> bash artifacts/device-runner/run_four_variants.sh \
  /absolute/path/to/artifacts/source/P
```

The script builds the unmodified P source if its operator package is missing,
then runs int32/int64 × contiguous/split against the four immutable R002 case
directories. `verify_outputs.py` compares actual device bytes with the existing
golden using `rtol=atol=1e-4` and writes
`artifacts/results/R003-device-four-variants.json`.

This runner changes no frozen P source and performs no instrumentation.
