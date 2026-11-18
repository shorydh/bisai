# Q06 R002 legal edge cancellation device case

This case is generated from the frozen official reference and is not a device
result.

```text
x.shape = [1,1,1,5]
x = [1.7e38, 1, -1.7e38, 0, 0]  # float32
mode = edge
paddings = [[0,0],[0,0],[0,0],[2,0]]
output.shape = [1,1,1,3]
golden = [0,0,0]  # actual official reference output
```

Output 0 receives padded positions `[0,1,2]`, whose values are
`[1.7e38, 1, -1.7e38]`. The exact real sum is 1; sequential FP64 accumulation
is 0. The frozen r6 `AddScalar` source mirror returns 1. The NPU result remains
unknown.

The four subdirectories cover:

* `int32-contiguous`
* `int32-split`
* `int64-contiguous`
* `int64-split`

Each directory contains `case.json`, binary inputs, reference golden data, and
a SHA256 manifest.

The official `build.sh -e` sample only supports the first bundled reflect
sample and its C++ example hard-codes an int32 contiguous tensor. To test these
four variants, use a custom harness that reads this case metadata and keeps the
restored r6 seven-source SHA256 unchanged. Do not replace the golden or widen
the `1e-4` FP32 tolerance.
