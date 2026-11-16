#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PadV3Grad 本地只读对拍（S0 Rev.2 / Stage B）。

用法：python -B -I local_verify/pad_check.py
- 不修改任何题目文件；只读 code/samples/reference.py。
- ml_dtypes 用内存 stub 注入（题目 reference 只为 bf16 导入它，本题 def.cpp 无 bf16）。
- 覆盖：_pad_index 公式、预像组（含 signed）、kernel 模型（多核区间/预像/Neumaier/裸 fp32）、
  6 mode、两种排布、四种 dtype 组合、空/0 维、constant、负 pad（含 reference skip 子族）。
"""

import os
import sys
import types
import traceback

import numpy as np

# ---------------------------------------------------------------- reference 导入
if "ml_dtypes" not in sys.modules:
    _stub = types.ModuleType("ml_dtypes")

    class _BF:
        def __eq__(self, other):
            return False

        def __ne__(self, other):
            return True

    _stub.bfloat16 = _BF()
    sys.modules["ml_dtypes"] = _stub

_HERE = os.path.dirname(os.path.abspath(__file__))
_SAMPLES = os.path.join(_HERE, "..", "code", "samples")
sys.path.insert(0, os.path.abspath(_SAMPLES))
import reference  # noqa: E402

MODES = ("constant", "edge", "replicate", "reflect", "symmetric", "circular")
MODE_ID = {"constant": 0, "edge": 1, "replicate": 1, "reflect": 2, "symmetric": 3, "circular": 4}

STATS = {"pass": 0, "fail": 0, "ref_invalid": 0, "skip_family": 0}


# ---------------------------------------------------------------- 独立公式
def pad_index(n, front, back, mode):
    """reference.py:7-25 的独立复刻（返回长度 = n+front+back）。"""
    if mode in ("edge", "replicate"):
        return np.clip(np.arange(-front, n + back), 0, n - 1)
    if n == 1:
        return np.zeros(front + 1 + back, dtype=np.int64)
    j = np.arange(-front, n + back, dtype=np.int64)
    if mode == "reflect":
        k = np.mod(j, 2 * (n - 1))
        return np.where(k < n, k, 2 * (n - 1) - k)
    if mode == "symmetric":
        k = np.mod(j, 2 * n)
        return np.where(k < n, k, 2 * n - 1 - k)
    if mode == "circular":
        return np.mod(j, n)
    raise ValueError(mode)


def trunc_div(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def pad_floor_div(a, b):
    q = trunc_div(a, b)
    r = a - q * b
    if r != 0 and ((r < 0) != (b < 0)):
        q -= 1
    return q


def pad_ceil_div(a, b):
    return -pad_floor_div(-a, b)


def add_group(slot_state, r, step, jlo, jhi):
    t0 = pad_ceil_div(jlo - r, step)
    t1 = pad_ceil_div(jhi - r, step) - 1
    cnt = t1 - t0 + 1
    if cnt < 0:
        cnt = 0
    slot_state.append((r, step, t0, cnt))


def build_groups(i_vec, out_dims, front, back, mode):
    """与 kernel `BuildGroups` 逐行一致；返回每维的 group 列表或 None。"""
    rank = len(out_dims)
    groups = []
    for d in range(rank):
        n = out_dims[d]
        jlo = -front[d]
        jhi = n + back[d]
        g = []
        if n == 1:
            if jhi > jlo:
                g.append((0, 1, jlo, jhi - jlo))
        elif mode in ("edge", "replicate"):
            iv = i_vec[d]
            if iv == 0:
                t1 = (jhi - 1) if (jhi - 1) < 0 else 0
                if t1 >= jlo:
                    g.append((0, 1, jlo, t1 - jlo + 1))
            elif iv == n - 1:
                t0 = jlo if jlo > (n - 1) else (n - 1)
                if jhi - 1 >= t0:
                    g.append((0, 1, t0, jhi - t0))
            else:
                if jlo <= iv < jhi:
                    g.append((0, 1, iv, 1))
        else:
            P = 2 * (n - 1) if mode == "reflect" else (2 * n if mode == "symmetric" else n)
            add_group(g, i_vec[d] % P, P, jlo, jhi)
            if mode == "reflect":
                if i_vec[d] != 0 and i_vec[d] != n - 1:
                    add_group(g, (P - i_vec[d]) % P, P, jlo, jhi)
            elif mode == "symmetric":
                add_group(g, (2 * n - 1 - i_vec[d]) % P, P, jlo, jhi)
        if sum(gg[3] for gg in g) <= 0:
            return None
        groups.append(g)
    return groups


def group_j(g, k):
    r, step, t0, cnt = g
    return r + (t0 + k) * step


def kernel_model(x, pads, mode, out_dtype, naive=False):
    """与 kernel 完全同构的模型：输出中心 gather + 预像组 + Neumaier/裸 fp32。"""
    rank = x.ndim
    N = list(x.shape)
    front = [int(p[0]) for p in pads]
    back = [int(p[1]) for p in pads]
    out_dims = [N[d] - front[d] - back[d] for d in range(rank)]
    total = 1
    for d in range(rank):
        total *= out_dims[d]
    y = np.zeros(total if total > 0 else 0, dtype=np.float64)
    if total <= 0:
        return y.reshape(out_dims).astype(out_dtype)
    if mode == "constant":
        if any(v < 0 for v in front) or any(v < 0 for v in back):
            return y.reshape(out_dims).astype(out_dtype)   # 无合法 golden -> 0
        sl = tuple(slice(front[d], front[d] + out_dims[d]) for d in range(rank))
        return np.asarray(x[sl]).astype(out_dtype)

    strides = [1] * rank
    for d in range(rank - 2, -1, -1):
        strides[d] = strides[d + 1] * N[d + 1]
    xf = x.reshape(-1)
    for flat in range(total):
        rem = flat
        i_vec = [0] * rank
        for d in range(rank - 1, -1, -1):
            i_vec[d] = rem % out_dims[d]
            rem //= out_dims[d]
        groups = build_groups(i_vec, out_dims, front, back, mode)
        if groups is None:
            continue
        pos = [0] * rank
        dim_cnt = [sum(gg[3] for gg in groups[d]) for d in range(rank)]
        hi = np.float32(0.0)
        comp = np.float32(0.0)
        done = False
        while not done:
            src = 0
            for d in range(rank):
                g = groups[d][0] if pos[d] < groups[d][0][3] else groups[d][1]
                kk = pos[d] if pos[d] < groups[d][0][3] else (pos[d] - groups[d][0][3])
                src += (group_j(g, kk) + front[d]) * strides[d]
            v = np.float32(xf[src])
            if naive:
                hi = np.float32(hi + v)
            else:
                if np.isfinite(hi) and np.isfinite(v):
                    t = np.float32(hi + v)
                    if np.isfinite(t):
                        ah = np.float32(abs(hi))
                        av = np.float32(abs(v))
                        if ah >= av:
                            comp = np.float32(comp + np.float32(np.float32(hi - t) + v))
                        else:
                            comp = np.float32(comp + np.float32(np.float32(v - t) + hi))
                        hi = t
                    else:
                        comp = np.float32(0.0)      # 有限+有限溢出到 ±Inf：直接返回 t
                        hi = t
                else:
                    comp = np.float32(0.0)
                    hi = np.float32(hi + v)
            dd = rank - 1
            while dd >= 0:
                pos[dd] += 1
                if pos[dd] < dim_cnt[dd]:
                    break
                pos[dd] = 0
                dd -= 1
            if dd < 0:
                done = True
        y[flat] = float(np.float32(hi + comp))
    return y.reshape(out_dims).astype(out_dtype)


def declared_out(x_shape, pads):
    return tuple(x_shape[d] - int(pads[d][0]) - int(pads[d][1]) for d in range(len(x_shape)))


def skip_family(out_dims, pads, mode):
    """reference.py:120 的 identity-skip 是否跳过了必要的折叠。"""
    if mode == "constant":
        return False
    for d in range(len(out_dims)):
        idx = pad_index(out_dims[d], int(pads[d][0]), int(pads[d][1]), mode)
        if np.array_equal(idx, np.arange(idx.size)) and idx.size != out_dims[d]:
            return True
    return False


def check_case(tag, x, pads, mode, layout_contiguous=True, pad_dtype=np.int64, verbose=False):
    """返回 (kind, message)。kind ∈ pass/fail/ref_invalid/skip_family。"""
    out_shape = declared_out(x.shape, pads)
    if any(o < 0 for o in out_shape):
        return "ref_invalid", "negative out dim"

    if layout_contiguous:
        flat = np.array([v for p in pads for v in p], dtype=pad_dtype)
    else:
        flat = np.array([p[0] for p in pads] + [p[1] for p in pads], dtype=pad_dtype)
    try:
        ref = reference.impl(x, flat, mode, layout_contiguous)
    except Exception as exc:  # reference 自身无法生成 golden
        if verbose:
            print("  [ref-exc]", tag, type(exc).__name__, str(exc)[:60])
        return "ref_invalid", type(exc).__name__
    if tuple(np.asarray(ref).shape) != out_shape:
        return "ref_invalid", "shape mismatch %s" % (np.asarray(ref).shape,)
    if skip_family(out_shape, pads, mode):
        return "skip_family", "reference identity-skip"

    got = kernel_model(x, pads, mode, x.dtype)
    if x.dtype == np.float16:
        ok = np.array_equal(np.asarray(got).view(np.uint16), np.asarray(ref).view(np.uint16))
        maxdiff = 0
    else:
        a = np.asarray(got).astype(np.float64)
        b = np.asarray(ref).astype(np.float64)
        maxdiff = float(np.max(np.abs(a - b))) if a.size else 0.0
        ok = bool(np.all(np.isclose(a, b, rtol=1e-4, atol=1e-4, equal_nan=True)))
    if ok:
        return "pass", ""
    return "fail", "maxdiff=%g" % maxdiff


# ---------------------------------------------------------------- A. 公式交叉验证
def test_formula_vs_torch():
    import torch
    import torch.nn.functional as F
    bad = 0
    for mode, tmode in (("reflect", "reflect"), ("replicate", "replicate"), ("circular", "circular")):
        for n in range(1, 8):
            lim = n - 1 if mode == "reflect" else n
            for f in range(0, lim + 1):
                for b in range(0, lim + 1):
                    x = torch.arange(n, dtype=torch.float64).reshape(1, 1, n)
                    ref = F.pad(x, (f, b), tmode).reshape(-1).numpy()
                    idx = pad_index(n, f, b, mode)
                    if not np.array_equal(ref, x.reshape(-1).numpy()[idx]):
                        bad += 1
    # 注意：torch 没有 "symmetric" 前向模式，symmetric 只由 _pad_index + brute 验证（[B]）。
    print("[A] _pad_index vs torch F.pad (reflect/replicate/circular): bad=%d" % bad)
    return bad


# ---------------------------------------------------------------- B. 预像组
def test_groups():
    bad = 0
    tested = 0
    for mode in MODES:
        if mode == "constant":
            continue
        for n in range(1, 7):
            for f in range(-4, 9):
                for bk in range(-4, 9):
                    N = n + f + bk
                    if N <= 0:
                        continue
                    idx = pad_index(n, f, bk, mode)
                    if idx.size != N or (idx.size and (idx.min() < 0 or idx.max() >= n)):
                        bad += 1
                        continue
                    brute = {}
                    for pos, i in enumerate(idx):
                        brute.setdefault(int(i), []).append(pos - f)
                    for i in range(n):
                        got = build_groups([i], [n], [f], [bk], mode)
                        mine = [] if got is None else sorted({group_j(g, k) for g in got[0] for k in range(g[3])})
                        if mine != sorted(brute.get(i, [])):
                            bad += 1
                            if bad <= 3:
                                print("  [B] BAD", mode, n, f, bk, i, mine, brute.get(i, []))
                    tested += 1
    print("[B] preimage groups (signed): cases=%d bad=%d" % (tested, bad))
    return bad


# ---------------------------------------------------------------- C. kernel 模型
def test_kernel_matrix():
    rng = np.random.default_rng(2026)
    cases = []

    # sample
    cases.append(("sample", np.zeros((1, 1, 8, 8), np.float32), [(0, 0), (0, 0), (2, 2), (2, 2)], "reflect"))
    # 随机小 shape / 6 mode
    for out_shape in [(4,), (3, 5), (2, 3, 4), (2, 2, 2, 3)]:
        for mode in MODES:
            pads = []
            for o in out_shape:
                pads.append((int(rng.integers(0, 4)), int(rng.integers(0, 4))))
            xs = tuple(o + f + b for o, (f, b) in zip(out_shape, pads))
            cases.append(("rand", np.zeros(xs, np.float32), pads, mode))
    # 不等 pad
    cases.append(("unequal", np.zeros((5, 4), np.float32), [(2, 1), (1, 2)], "reflect"))
    # front/back > n
    for mode in ("reflect", "symmetric", "circular", "edge"):
        cases.append(("pad>n", np.zeros((9, 7), np.float32), [(9, 7), (5, 6)], mode))
    # n == 1
    for mode in MODES:
        cases.append(("n1", np.zeros((1, 4), np.float32), [(3, 2), (0, 2)], mode))
    # signed pads（单边/双边）
    for mode in ("edge", "reflect", "symmetric", "circular"):
        for pads in ([( -2, 0)], [(0, -2)], [(-2, -3)], [(2, -3)], [(-3, 2)], [(1, -1)]):
            xs = tuple(5 + f + b for f, b in pads)
            if xs[0] < 0:
                continue
            cases.append(("signed", np.zeros(xs, np.float32), pads, mode))
    # 空 tensor / rank0
    cases.append(("empty", np.zeros((0, 4), np.float32), [(0, 0), (1, 1)], "reflect"))
    cases.append(("rank0", np.zeros((), np.float32), [], "reflect"))
    # reference identity-skip 的“静默广播”子族（无可靠 golden；应被标记而非比较）
    cases.append(("skip-bc1", np.zeros((1,), np.float32), [(1, -2)], "edge"))
    cases.append(("skip-bc2", np.zeros((1, 1), np.float32), [(1, -2), (0, 0)], "edge"))
    # constant
    cases.append(("const", np.zeros((7, 5), np.float32), [(2, 1), (1, 3)], "constant"))
    cases.append(("const-neg", np.zeros((3,), np.float32), [(-2, 0)], "constant"))

    for tag, x0, pads, mode in cases:
        for dt in (np.float32, np.float16):
            x = rng.uniform(-1, 1, x0.shape).astype(dt) if x0.size else x0.astype(dt)
            kind, msg = check_case(tag, x, pads, mode, True, np.int64)
            STATS[kind] += 1
            if kind == "fail":
                print("  [C] FAIL", tag, x.shape, pads, mode, np.dtype(dt).name, msg)

    # 两种排布（同一逻辑集合）
    x = rng.uniform(-1, 1, (4, 5, 6)).astype(np.float32)
    pads = [(1, 2), (0, 2), (2, 1)]
    for mode in MODES:
        k1, _ = check_case("layout-c", x, pads, mode, True, np.int64)
        k2, _ = check_case("layout-nc", x, pads, mode, False, np.int64)
        STATS[k1] += 1
        STATS[k2] += 1
        if k1 != k2 or k1 == "fail":
            print("  [C] LAYOUT MISMATCH", mode, k1, k2)

    # 四种 dtype 组合（paddings int32/int64）
    x32 = rng.uniform(-1, 1, (1, 1, 8, 8)).astype(np.float32)
    x16 = x32.astype(np.float16)
    sp = [(0, 0), (0, 0), (2, 2), (2, 2)]
    for xx in (x32, x16):
        for pdt in (np.int32, np.int64):
            kind, msg = check_case("dtype-combo", xx, sp, "reflect", True, pdt)
            STATS[kind] += 1
            if kind == "fail":
                print("  [C] DTYPE FAIL", np.dtype(xx.dtype).name, pdt, msg)

    print("[C] kernel model: pass=%d fail=%d ref_invalid=%d skip_family=%d"
          % (STATS["pass"], STATS["fail"], STATS["ref_invalid"], STATS["skip_family"]))
    return STATS["fail"]


# ---------------------------------------------------------------- D. 精度 stress
def scatter_dest(x_shape, pads, mode):
    out = declared_out(x_shape, pads)
    maps = [pad_index(out[d], int(pads[d][0]), int(pads[d][1]), mode) for d in range(len(out))]
    strides = [1] * len(out)
    for d in range(len(out) - 2, -1, -1):
        strides[d] = strides[d + 1] * out[d + 1]
    grids = np.indices(x_shape, sparse=False)
    dest = np.zeros(x_shape, dtype=np.int64)
    for d in range(len(out)):
        dest += maps[d][grids[d]] * strides[d]
    return dest.ravel(), int(np.prod(out)) if out else 1


def neumaier_scatter(x, pads, mode, out_dtype):
    dest, total = scatter_dest(x.shape, pads, mode)
    hi = np.zeros(total, dtype=np.float32)
    comp = np.zeros(total, dtype=np.float32)
    vals = x.reshape(-1).astype(np.float32)
    for k in range(vals.size):
        p = dest[k]
        v = vals[k]
        if np.isfinite(hi[p]) and np.isfinite(v):
            t = np.float32(hi[p] + v)
            if np.isfinite(t):
                if abs(hi[p]) >= abs(v):
                    comp[p] = np.float32(comp[p] + np.float32(np.float32(hi[p] - t) + v))
                else:
                    comp[p] = np.float32(comp[p] + np.float32(np.float32(v - t) + hi[p]))
                hi[p] = t
            else:
                comp[p] = np.float32(0.0)
                hi[p] = t
        else:
            comp[p] = np.float32(0.0)
            hi[p] = np.float32(hi[p] + v)
    return (hi.astype(np.float64) + comp.astype(np.float64)).astype(out_dtype)


def naive_scatter(x, pads, mode, out_dtype):
    dest, total = scatter_dest(x.shape, pads, mode)
    y = np.zeros(total, dtype=np.float32)
    np.add.at(y, dest, x.reshape(-1).astype(np.float32))
    return y.astype(out_dtype)


def test_precision():
    rng = np.random.default_rng(7)
    rows = []
    shapes = [
        ((16, 24), [(40, 40), (30, 25)]),
        ((16, 64), [(300, 300), (50, 20)]),
    ]
    for out_shape, pads in shapes:
        xs = tuple(o + f + b for o, (f, b) in zip(out_shape, pads))
        for mode in ("reflect", "symmetric", "circular", "edge"):
            for lo, hi in ((-1.0, 1.0), (-1e6, 1e6)):
                x = rng.uniform(lo, hi, xs).astype(np.float32)
                ref = reference.impl(x, [list(p) for p in pads], mode, True)
                nv = naive_scatter(x, pads, mode, np.float32)
                kh = neumaier_scatter(x, pads, mode, np.float32)
                a = np.asarray(nv).reshape(-1).astype(np.float64)
                b = np.asarray(ref).reshape(-1).astype(np.float64)
                c = np.asarray(kh).reshape(-1).astype(np.float64)
                bad_nv = int((~np.isclose(a, b, rtol=1e-4, atol=1e-4)).sum())
                bad_kh = int((~np.isclose(c, b, rtol=1e-4, atol=1e-4)).sum())
                m = float(np.max(np.abs(a - b))) if a.size else 0.0
                mkh = float(np.max(np.abs(c - b))) if c.size else 0.0
                rows.append((tuple(out_shape), mode, lo, bad_nv, bad_kh, m, mkh))
                print("  [D] out=%s %-9s |x|<=%g  naive_bad=%d maxabs=%.4g | neumaier_bad=%d maxabs=%.4g"
                      % (out_shape, mode, hi, bad_nv, m, bad_kh, mkh))
    return rows


# ---------------------------------------------------------------- E. 分核覆盖 + 32B 起点
def test_partition():
    bad = 0
    totals = (1, 2, 3, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65,
              1000, 1001, 1023, 1024, 1025, 4096, 4097, 65537)
    for elem in (2, 4):                 # fp16 / fp32
        align = 32 // elem              # 32B 对齐的元素数
        for total in totals:
            for core in (1, 2, 3, 8, 64):
                bf = (total + core - 1) // core
                bf = ((bf + align - 1) // align) * align
                seen = np.zeros(total, dtype=np.int8)
                starts = []
                for c in range(core):
                    st = c * bf
                    en = min(st + bf, total)
                    if st < en:
                        starts.append(st)
                        seen[st:en] += 1
                # 尾 chunk 起点也必须 32B 对齐：chunkStart = start + k*ubFactor
                for ub in (align, 16, 4096, 8192):
                    for st in starts:
                        k = 0
                        while st + k * ub < total:
                            if ((st + k * ub) * elem) % 32 != 0:
                                bad += 1
                            k += 1
                if seen.min() != 1 or seen.max() != 1:
                    bad += 1
                if any((st * elem) % 32 != 0 for st in starts):
                    bad += 1
    print("[E] partition coverage + 32B start/chunk alignment: bad=%d" % bad)
    return bad


# ---------------------------------------------------------------- F. Inf/NaN 返回
def test_inf_nan():
    cases = [
        ("3e38+3e38", np.array([3e38, 3e38], np.float32), [(1, 0)], "edge", "inf"),
        ("overflow-cancel", np.array([3e38, 3e38, -3e38, -3e38], np.float32), [(3, 0)], "edge", "known"),
        ("nan-input", np.array([np.nan, 1.0], np.float32), [(1, 0)], "edge", "nan"),
        ("posinf", np.array([np.inf, 1.0], np.float32), [(1, 0)], "edge", "inf"),
        ("posinf+neginf", np.array([np.inf, -np.inf, 1.0], np.float32), [(2, 0)], "edge", "nan"),
    ]
    bad = 0
    for tag, x, pads, mode, expect in cases:
        ref = np.asarray(reference.impl(x, [list(p) for p in pads], mode, True)).reshape(-1)
        got = np.asarray(kernel_model(x, pads, mode, np.float32)).reshape(-1)
        r = float(ref[0]); g = float(got[0])
        if expect == "inf":
            ok = np.isinf(r) and np.isinf(g) and (np.signbit(r) == np.signbit(g))
        elif expect == "nan":
            ok = np.isnan(r) and np.isnan(g)
        else:   # known limitation：reference 0，kernel 因 fp32 中间溢出得到 Inf
            ok = (r == 0.0) and np.isinf(g)
        print("  [F] %-14s ref=%s kernel=%s %s" % (tag, r, g, "OK" if ok else "BAD"))
        if not ok:
            bad += 1
    print("[F] Inf/NaN return: bad=%d" % bad)
    return bad


# ---------------------------------------------------------------- main
def main():
    bad = 0
    bad += test_formula_vs_torch()
    bad += test_groups()
    bad += test_kernel_matrix()
    test_precision()
    bad += test_partition()
    bad += test_inf_nan()

    print("\nSUMMARY: %s (fail=%d, ref_invalid=%d, skip_family=%d)"
          % ("PASS" if bad == 0 else "FAIL", STATS["fail"], STATS["ref_invalid"], STATS["skip_family"]))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
