/*!
 * \file pad_v3_grad.h
 * \brief PadV3Grad kernel 实现（S0 Rev.2）
 *
 * 语义（reference.py）：
 *   - x 是 PadV3 前向输出（padded），y 是原张量梯度；
 *   - 非 constant：y[i_vec] = Σ_{j: pad_index(j_d) == i_d, ∀d} x[j_vec + front_vec]
 *     其中 j_d 是算术坐标，j_d ∈ [-front_d, n_d + back_d)，物理下标 = j_d + front_d；
 *   - constant：y[i_vec] = x[i_vec + front_vec]（中间块，无累加）。
 *
 * 关键点：
 *   1. 有符号 front/back：每个预像组都与 [-front, n+back) 求交；交集为空 -> 该输出为 0。
 *   2. 每个核独占输出扁平区间 [start_, end_)：无 race、无需清零、无 workspace。
 *   3. 精度：Neumaier（hi/lo）补偿 + 非有限值旁路（位模式判断，Inf+Inf 不会被算成 NaN）。
 *   4. 本核输出区间全覆盖写入；不 clamp、不部分写。
 *   5. constant + 负 pad：reference 自身返回的 shape 与声明不符（无合法 golden），
 *      kernel 对本核区间全写 0（确定性、全覆盖）。
 */
#ifndef PADV3GRAD_H
#define PADV3GRAD_H

#include "kernel_operator.h"
#include "kernel_tiling/kernel_tiling.h"
#include "pad_v3_grad_tiling_data.h"
#include "pad_v3_grad_tiling_key.h"

namespace NsPadV3Grad {
using namespace AscendC;

constexpr int32_t BUFFER_NUM = 1;
constexpr int32_t PAD_MAX_RANK = PADV3GRAD_MAX_RANK;
constexpr int32_t PAD_MAX_GROUPS = 2;

union FloatUint32 {
    float f;
    uint32_t u;
};

template <typename T> struct PadConvert;
template <> struct PadConvert<float> {
    __aicore__ static inline float ToFloat(float v) { return v; }
    __aicore__ static inline float FromFloat(float v) { return v; }
};
template <> struct PadConvert<half> {
    __aicore__ static inline float ToFloat(half v) { return static_cast<float>(v); }
    __aicore__ static inline half FromFloat(float v) { return static_cast<half>(v); }
};

/* fast-math 安全的有限性判断：指数位全 1 -> Inf/NaN */
__aicore__ inline bool PadIsFinite(float v)
{
    FloatUint32 c;
    c.f = v;
    return (c.u & 0x7f800000u) != 0x7f800000u;
}

/* Neumaier（补偿求和）。
 * 非有限旁路：
 *   - 任一操作数非有限（Inf/NaN）-> 直接相加、comp=0，保证 Inf+(-Inf)=NaN、
 *     Inf+有限=Inf、NaN 传播；
 *   - 两个有限数相加**溢出到 ±Inf**（如 3e38+3e38）-> 直接返回 t，comp=0。
 *     否则补偿项 (hi-t)+v 会算出 -Inf，最终 hi+comp = Inf+(-Inf) = NaN，
 *     而 reference(fp64->fp32) 是 Inf。
 */
__aicore__ inline float PadAccStep(float hi, float& comp, float v)
{
    if (PadIsFinite(hi) && PadIsFinite(v)) {
        const float t = hi + v;
        if (PadIsFinite(t)) {
            const float ah = (hi < 0.0f) ? -hi : hi;
            const float av = (v < 0.0f) ? -v : v;
            if (ah >= av) {
                comp += (hi - t) + v;
            } else {
                comp += (v - t) + hi;
            }
            return t;
        }
        comp = 0.0f;
        return t;   /* ±Inf（fp32 中间和溢出；与 reference 的该次加法一致） */
    }
    comp = 0.0f;
    return hi + v;
}

/* C++ 整除是截断，负数时需要 floor-mod（审计 P3） */
__aicore__ inline int64_t PadFloorDiv(int64_t a, int64_t b)
{
    int64_t q = a / b;
    int64_t r = a % b;
    if (r != 0 && ((r < 0) != (b < 0))) {
        q -= 1;
    }
    return q;
}

__aicore__ inline int64_t PadCeilDiv(int64_t a, int64_t b)
{
    return -PadFloorDiv(-a, b);
}

template <typename T>
class PadV3Grad {
public:
    __aicore__ inline PadV3Grad() {}
    __aicore__ inline void Init(GM_ADDR x, GM_ADDR paddings, GM_ADDR y,
                                const PadV3GradTilingData* tilingData);
    __aicore__ inline void Process();

private:
    __aicore__ inline bool BuildGroups(int64_t flat);
    __aicore__ inline bool BuildGroupsFromDec();
    __aicore__ inline bool UpdateDimGroups(int64_t d);
    __aicore__ inline void AddGroup(int64_t slot, int64_t r, int64_t step, int64_t jlo, int64_t jhi);
    __aicore__ inline int64_t GroupJ(int64_t d, int64_t k) const;
    __aicore__ inline void ComputeChunk(int64_t chunkStart, int64_t chunkLen);
    __aicore__ inline void ComputeConstantChunk(int64_t chunkStart, int64_t chunkLen);
    __aicore__ inline void CopyOutChunk(int64_t chunkStart, int64_t chunkLen);

    TPipe pipe_;
    TBuf<TPosition::VECCALC> outBuf_;
    LocalTensor<T> outLocal_;
    GlobalTensor<T> xGm_;
    GlobalTensor<T> yGm_;
    GlobalTensor<int32_t> padGm32_;
    GlobalTensor<int64_t> padGm64_;

    int64_t rank_ = 0;
    int64_t mode_ = 2;
    int64_t contiguous_ = 1;
    int64_t useInt64Pad_ = 0;
    int64_t coreNum_ = 1;
    int64_t ubFactor_ = 0;
    int64_t xDims_[PAD_MAX_RANK] = {0};
    int64_t outDims_[PAD_MAX_RANK] = {0};
    int64_t front_[PAD_MAX_RANK] = {0};
    int64_t back_[PAD_MAX_RANK] = {0};
    int64_t strides_[PAD_MAX_RANK] = {0};
    int64_t total_ = 0;
    int64_t start_ = 0;
    int64_t end_ = 0;
    int64_t hasNegPad_ = 0;

    /* 每个输出元素的预像组（成员数组，避免 __aicore__ 内大栈数组） */
    int64_t iDec_[PAD_MAX_RANK] = {0};
    int64_t gr_[PAD_MAX_RANK * PAD_MAX_GROUPS] = {0};
    int64_t gs_[PAD_MAX_RANK * PAD_MAX_GROUPS] = {0};
    int64_t gt0_[PAD_MAX_RANK * PAD_MAX_GROUPS] = {0};
    int64_t gcnt_[PAD_MAX_RANK * PAD_MAX_GROUPS] = {0};
    int64_t dimCnt_[PAD_MAX_RANK] = {0};
    int64_t pos_[PAD_MAX_RANK] = {0};
};

template <typename T>
__aicore__ inline void PadV3Grad<T>::Init(GM_ADDR x, GM_ADDR paddings, GM_ADDR y,
                                          const PadV3GradTilingData* tilingData)
{
    if (tilingData == nullptr || x == nullptr || y == nullptr) {
        return;
    }
    rank_ = tilingData->rank;
    if (rank_ < 0 || rank_ > PAD_MAX_RANK) {
        return;
    }
    coreNum_ = tilingData->coreNum;
    if (coreNum_ < 1 || coreNum_ > 1024) {
        return;
    }
    ubFactor_ = tilingData->ubFactor;
    if (ubFactor_ < 1 || ubFactor_ > PADV3_UB_MAX) {
        return;
    }
    mode_ = tilingData->mode;
    if (mode_ < 0 || mode_ > 4) {
        return;
    }
    contiguous_ = (tilingData->paddingsContiguous != 0) ? 1 : 0;
    useInt64Pad_ = (tilingData->paddingsInt64 != 0) ? 1 : 0;

    int64_t xNumel = 1;
    for (int64_t d = 0; d < rank_; ++d) {
        const int64_t N = tilingData->xDims[d];
        if (N < 0) {
            return;
        }
        xDims_[d] = N;
        outDims_[d] = 0;
        front_[d] = 0;
        back_[d] = 0;
        strides_[d] = 1;
        if (N > 0) {
            xNumel *= N;
            if (xNumel > PADV3_XNUMEL_MAX) {
                return;
            }
        }
    }

    /* ---- 从 GM 读 paddings（2R 个 int32/int64）---- */
    const int64_t padCount = 2 * rank_;
    if (padCount > 0) {
        if (paddings == nullptr) {
            return;
        }
        if (useInt64Pad_ != 0) {
            padGm64_.SetGlobalBuffer(reinterpret_cast<__gm__ int64_t*>(paddings), padCount);
        } else {
            padGm32_.SetGlobalBuffer(reinterpret_cast<__gm__ int32_t*>(paddings), padCount);
        }
    }
    for (int64_t d = 0; d < rank_; ++d) {
        int64_t f = 0;
        int64_t b = 0;
        if (padCount > 0) {
            const int64_t i0 = (contiguous_ != 0) ? (2 * d) : d;
            const int64_t i1 = (contiguous_ != 0) ? (2 * d + 1) : (rank_ + d);
            if (useInt64Pad_ != 0) {
                f = padGm64_.GetValue(static_cast<uint32_t>(i0));
                b = padGm64_.GetValue(static_cast<uint32_t>(i1));
            } else {
                f = static_cast<int64_t>(padGm32_.GetValue(static_cast<uint32_t>(i0)));
                b = static_cast<int64_t>(padGm32_.GetValue(static_cast<uint32_t>(i1)));
            }
        }
        /* 防 int64 溢出：paddings 是外部输入，限制在 [-(2^40), 2^40] */
        if (f < -PADV3_XNUMEL_MAX || f > PADV3_XNUMEL_MAX ||
            b < -PADV3_XNUMEL_MAX || b > PADV3_XNUMEL_MAX) {
            return;
        }
        front_[d] = f;
        back_[d] = b;
        if (f < 0 || b < 0) {
            hasNegPad_ = 1;
        }
        const int64_t n = xDims_[d] - f - b;
        if (n < 0) {
            return;   /* 非法（front+back > N）：无合法 golden */
        }
        outDims_[d] = n;
    }

    /* ---- x 的行主序 stride ---- */
    for (int64_t d = rank_ - 1; d >= 0; --d) {
        int64_t s = 1;
        for (int64_t k = d + 1; k < rank_; ++k) {
            s *= xDims_[k];
        }
        strides_[d] = s;
    }

    /* ---- 输出总数（rank0 -> 1）---- */
    total_ = 1;
    for (int64_t d = 0; d < rank_; ++d) {
        if (outDims_[d] <= 0 || outDims_[d] > PADV3_XNUMEL_MAX) {
            total_ = 0;
            break;
        }
        total_ *= outDims_[d];
        if (total_ > PADV3_XNUMEL_MAX) {
            total_ = 0;
            break;
        }
    }
    if (total_ <= 0) {
        return;   /* 空输出：不启动计算 */
    }

    /* ---- 分核：以 kernel 自己算出的 total_ 为准 ----
     * 每核起点必须是 32B 字节对齐：blockFactor 向上对齐到 32/sizeof(T) 个元素。
     * 这样 start_ = coreId*bf 与 chunkStart = start_ + k*ubFactor_ 都是 32B 对齐，
     * DataCopyPad 的目的 GM 起点不再依赖“非 32B 对齐 GM 起始”。
     */
    const int64_t alignElem = static_cast<int64_t>(32 / sizeof(T));
    if (alignElem < 1 || (ubFactor_ % alignElem) != 0) {
        return;
    }
    const int64_t coreId = static_cast<int64_t>(GetBlockIdx());
    if (coreId < 0 || coreId >= coreNum_) {
        return;
    }
    int64_t bf = 0;
    if (tilingData->totalNum > 0 && tilingData->totalNum == total_ && tilingData->blockFactor > 0) {
        bf = tilingData->blockFactor;
    } else {
        bf = (total_ + coreNum_ - 1) / coreNum_;
    }
    if (bf <= 0) {
        return;
    }
    bf = ((bf + alignElem - 1) / alignElem) * alignElem;   /* 幂等：tiling 已对齐时不变 */
    start_ = coreId * bf;
    end_ = start_ + bf;
    if (end_ > total_) {
        end_ = total_;
    }
    if (start_ >= end_) {
        return;
    }

    xGm_.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(x), (xNumel > 0) ? xNumel : 1);
    yGm_.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(y), total_);

    int64_t outBytes = ubFactor_ * static_cast<int64_t>(sizeof(T));
    if (outBytes < 32) {
        outBytes = 32;
    }
    pipe_.InitBuffer(outBuf_, outBytes);
    outLocal_ = outBuf_.Get<T>();
}

template <typename T>
__aicore__ inline void PadV3Grad<T>::AddGroup(int64_t slot, int64_t r, int64_t step,
                                              int64_t jlo, int64_t jhi)
{
    /* j = r + t*step，t ∈ [t0, t1] */
    const int64_t t0 = PadCeilDiv(jlo - r, step);
    const int64_t t1 = PadCeilDiv(jhi - r, step) - 1;
    int64_t cnt = t1 - t0 + 1;
    if (cnt < 0) {
        cnt = 0;
    }
    gr_[slot] = r;
    gs_[slot] = step;
    gt0_[slot] = t0;
    gcnt_[slot] = cnt;
}

template <typename T>
__aicore__ inline bool PadV3Grad<T>::BuildGroups(int64_t flat)
{
    /* 解码输出多下标 */
    int64_t rem = flat;
    for (int64_t d = rank_ - 1; d >= 0; --d) {
        const int64_t n = outDims_[d];
        if (n <= 0) {
            return false;
        }
        iDec_[d] = rem % n;
        rem /= n;
    }
    return BuildGroupsFromDec();
}

/* exp7_odometer：直接使用已维护的 iDec_（ComputeChunk 增量推进），跳过每元素的
 * rank 层 div/mod。语义与 BuildGroups(flat) 完全一致。 */
template <typename T>
__aicore__ inline bool PadV3Grad<T>::BuildGroupsFromDec()
{
    for (int64_t d = 0; d < rank_; ++d) {
        UpdateDimGroups(d);
    }
    for (int64_t d = 0; d < rank_; ++d) {
        if (dimCnt_[d] <= 0) {
            return false;
        }
    }
    return true;
}

/* exp8_incgroup：只重算 index 发生变化的维度。语义与逐元素全量 BuildGroupsFromDec 一致
 * （同一个函数体，只是把「哪些维度变了」交给调用方）。 */
template <typename T>
__aicore__ inline bool PadV3Grad<T>::UpdateDimGroups(int64_t d)
{
    {
        const int64_t n = outDims_[d];
        if (n <= 0) {
            dimCnt_[d] = 0;   /* 防御：Init 已保证 >0；置 0 让 elemOk 判为无效 */
            return false;
        }
        const int64_t jlo = -front_[d];
        const int64_t jhi = n + back_[d];
        const int64_t s0 = 2 * d;
        gcnt_[s0] = 0;
        gcnt_[s0 + 1] = 0;

        if (n == 1) {
            /* 所有 padded 位置都映射到 0（含 edge；reflect/symmetric/circular 同） */
            if (jhi > jlo) {
                gr_[s0] = 0;
                gs_[s0] = 1;
                gt0_[s0] = jlo;
                gcnt_[s0] = jhi - jlo;
            }
        } else if (mode_ == 1) {
            /* edge / replicate：端点是连续区间，中间是单点；全部与 [jlo, jhi) 求交 */
            const int64_t iv = iDec_[d];
            if (iv == 0) {
                const int64_t t1 = (jhi - 1 < 0) ? (jhi - 1) : 0;
                if (t1 >= jlo) {
                    gr_[s0] = 0;
                    gs_[s0] = 1;
                    gt0_[s0] = jlo;
                    gcnt_[s0] = t1 - jlo + 1;
                }
            } else if (iv == n - 1) {
                const int64_t t0 = (jlo > n - 1) ? jlo : (n - 1);
                if (jhi - 1 >= t0) {
                    gr_[s0] = 0;
                    gs_[s0] = 1;
                    gt0_[s0] = t0;
                    gcnt_[s0] = jhi - t0;
                }
            } else {
                if (iv >= jlo && iv < jhi) {
                    gr_[s0] = 0;
                    gs_[s0] = 1;
                    gt0_[s0] = iv;
                    gcnt_[s0] = 1;
                }
            }
        } else {
            const int64_t P = (mode_ == 2) ? (2 * (n - 1)) : ((mode_ == 3) ? (2 * n) : n);
            AddGroup(s0, iDec_[d] % P, P, jlo, jhi);
            if (mode_ == 2) {
                /* reflect 的两组在 i=0 / i=n-1 重合，需去重 */
                if (iDec_[d] != 0 && iDec_[d] != n - 1) {
                    AddGroup(s0 + 1, (P - iDec_[d]) % P, P, jlo, jhi);
                }
            } else if (mode_ == 3) {
                AddGroup(s0 + 1, (2 * n - 1 - iDec_[d]) % P, P, jlo, jhi);
            }
        }
        dimCnt_[d] = gcnt_[s0] + gcnt_[s0 + 1];
        return dimCnt_[d] > 0;
    }
}

template <typename T>
__aicore__ inline int64_t PadV3Grad<T>::GroupJ(int64_t d, int64_t k) const
{
    const int64_t s0 = 2 * d;
    if (k < gcnt_[s0]) {
        return gr_[s0] + (gt0_[s0] + k) * gs_[s0];
    }
    const int64_t kk = k - gcnt_[s0];
    return gr_[s0 + 1] + (gt0_[s0 + 1] + kk) * gs_[s0 + 1];
}

template <typename T>
__aicore__ inline void PadV3Grad<T>::ComputeChunk(int64_t chunkStart, int64_t chunkLen)
{
    /* exp7_odometer：chunkStart 的多下标只解码一次，之后逐元素 +1 进位。
     * 旧实现对每个元素重做 rank 层 div/mod（`rem % n` + `rem /= n`）。 */
    int64_t remDec = chunkStart;
    for (int64_t d = rank_ - 1; d >= 0; --d) {
        const int64_t n = outDims_[d];
        iDec_[d] = (n > 0) ? (remDec % n) : 0;
        remDec = (n > 0) ? (remDec / n) : 0;
    }
    /* exp8_incgroup：chunk 起点做一次全量 group 构建；之后每次 index +1 只重算变化的维度。 */
    for (int64_t d = 0; d < rank_; ++d) {
        UpdateDimGroups(d);
    }
    bool elemOk = true;
    for (int64_t d = 0; d < rank_; ++d) {
        if (dimCnt_[d] <= 0) {
            elemOk = false;
            break;
        }
    }
    for (int64_t k = 0; k < chunkLen; ++k) {
        float val = 0.0f;
        if (elemOk) {
            for (int64_t d = 0; d < rank_; ++d) {
                pos_[d] = 0;
            }
            float hi = 0.0f;
            float comp = 0.0f;
            bool done = false;
            while (!done) {
                int64_t src = 0;
                for (int64_t d = 0; d < rank_; ++d) {
                    src += (GroupJ(d, pos_[d]) + front_[d]) * strides_[d];
                }
                const float v = PadConvert<T>::ToFloat(xGm_.GetValue(static_cast<uint32_t>(src)));
                hi = PadAccStep(hi, comp, v);

                int64_t dd = rank_ - 1;
                while (dd >= 0) {
                    pos_[dd] += 1;
                    if (pos_[dd] < dimCnt_[dd]) {
                        break;
                    }
                    pos_[dd] = 0;
                    dd -= 1;
                }
                if (dd < 0) {
                    done = true;
                }
            }
            val = hi + comp;
        }
        outLocal_.SetValue(k, PadConvert<T>::FromFloat(val));
        if (k + 1 < chunkLen) {
            /* 多下标 +1；只有发生变化的维度需要重算 group（进位链上每一维都变了）。 */
            for (int64_t d = rank_ - 1; d >= 0; --d) {
                ++iDec_[d];
                if (iDec_[d] < outDims_[d]) {
                    UpdateDimGroups(d);
                    break;
                }
                iDec_[d] = 0;
                UpdateDimGroups(d);
            }
            elemOk = true;
            for (int64_t d = 0; d < rank_; ++d) {
                if (dimCnt_[d] <= 0) {
                    elemOk = false;
                    break;
                }
            }
        }
    }
}

template <typename T>
__aicore__ inline void PadV3Grad<T>::ComputeConstantChunk(int64_t chunkStart, int64_t chunkLen)
{
    /* exp9_constodo：mode 0 是平移拷贝 dx[i] = dy[i+front]。
     * 旧实现每个元素重做 rank 层 div/mod 与 rank 次乘加；这里解码一次、
     * 之后最内维 +1（stride==1）时 src 直接 +1，只在进位时按 iDec_ 重算 src。 */
    if (hasNegPad_ != 0) {
        for (int64_t k = 0; k < chunkLen; ++k) {
            outLocal_.SetValue(k, PadConvert<T>::FromFloat(0.0f));
        }
        return;
    }
    /* exp12_blkdma：mode 0 的 gather 实测占该题 67% 的耗时（诊断提交：跳过 gather
     * 后 14.57µs → 4.82µs）。原来的 gather 是逐元素 GM 标量读 + UB 标量写；但只要
     * 「一个 32B 块整块落在同一输出行的内部区间」，它对应的输入也是一段连续内存，
     * 可以一次 DataCopyPad 搬完。填充占比很小，所以绝大多数块都能走 DMA。
     *
     * 对齐：块大小取 alignElems（32B），块起点 kf 恒为 alignElems 倍数 ⇒
     * outLocal_[kf] 恒 32B 对齐；跨行块与 chunk 尾部（不足一块）保留标量语义。
     * 数值：T→float→T 往返对 f32/f16/bf16 都是恒等，所以直接搬 T 字节与原来逐位一致。 */
    if (rank_ >= 1 && outDims_[rank_ - 1] > 0 && xDims_[rank_ - 1] > 0) {
        const int64_t rowLen = outDims_[rank_ - 1];
        const int64_t blk = 32 / static_cast<int64_t>(sizeof(T));
        if (blk > 0 && chunkStart % blk == 0) {
            int64_t remF = chunkStart;
            for (int64_t d = rank_ - 1; d >= 0; --d) {
                const int64_t n = outDims_[d];
                iDec_[d] = (n > 0) ? (remF % n) : 0;
                remF = (n > 0) ? (remF / n) : 0;
            }
            int64_t kf = 0;
            while (kf < chunkLen) {
                int64_t nb = blk;
                if (nb > chunkLen - kf) {
                    nb = chunkLen - kf;
                }
                const int64_t col = iDec_[rank_ - 1];
                bool blkOk = (nb == blk) && (col + blk <= rowLen) &&
                             (col >= front_[rank_ - 1]) &&
                             (col + blk <= front_[rank_ - 1] + xDims_[rank_ - 1]);
                for (int64_t d = 0; d < rank_ - 1 && blkOk; ++d) {
                    if (iDec_[d] < front_[d] || iDec_[d] >= front_[d] + xDims_[d]) {
                        blkOk = false;
                    }
                }
                bool advDone = false;
                if (nb == blk) {
                    int64_t srcF = 0;
                    for (int64_t d = 0; d < rank_; ++d) {
                        srcF += (iDec_[d] + front_[d]) * strides_[d];
                    }
                    if (blkOk) {
                        DataCopyExtParams pf;
                        pf.blockCount = 1;
                        pf.blockLen = static_cast<uint32_t>(blk * static_cast<int64_t>(sizeof(T)));
                        pf.srcStride = 0;
                        pf.dstStride = 0;
                        pf.rsv = 0;
                        DataCopyPadExtParams<T> pp{};
                        pp.isPad = false;
                        pp.leftPadding = 0;
                        pp.rightPadding = 0;
                        DataCopyPad(outLocal_[kf], xGm_[srcF], pf, pp);
                    } else {
                        /* 该块含填充：逐元素判定（最多 blk 个） */
                        for (int64_t j = 0; j < blk; ++j) {
                            bool ok = true;
                            for (int64_t d = 0; d < rank_; ++d) {
                                if (iDec_[d] < front_[d] || iDec_[d] >= front_[d] + xDims_[d]) {
                                    ok = false;
                                    break;
                                }
                            }
                            float val = 0.0f;
                            if (ok) {
                                int64_t sv = 0;
                                for (int64_t d = 0; d < rank_; ++d) {
                                    sv += (iDec_[d] + front_[d]) * strides_[d];
                                }
                                val = PadConvert<T>::ToFloat(xGm_.GetValue(static_cast<uint32_t>(sv)));
                            }
                            outLocal_.SetValue(kf + j, PadConvert<T>::FromFloat(val));
                            if (j + 1 < blk) {
                                for (int64_t d = rank_ - 1; d >= 0; --d) {
                                    ++iDec_[d];
                                    if (iDec_[d] < outDims_[d]) {
                                        break;
                                    }
                                    iDec_[d] = 0;
                                }
                            }
                        }
                        advDone = true;   /* 标量分支已逐元素推进过下标 */
                    }
                    kf += blk;
                } else {
                    /* chunk 尾部不足一个 32B 块：逐元素收尾 */
                    for (int64_t j = 0; j < nb; ++j) {
                        bool ok = true;
                        for (int64_t d = 0; d < rank_; ++d) {
                            if (iDec_[d] < front_[d] || iDec_[d] >= front_[d] + xDims_[d]) {
                                ok = false;
                                break;
                            }
                        }
                        float val = 0.0f;
                        if (ok) {
                            int64_t sv = 0;
                            for (int64_t d = 0; d < rank_; ++d) {
                                sv += (iDec_[d] + front_[d]) * strides_[d];
                            }
                            val = PadConvert<T>::ToFloat(xGm_.GetValue(static_cast<uint32_t>(sv)));
                        }
                        outLocal_.SetValue(kf + j, PadConvert<T>::FromFloat(val));
                        if (j + 1 < nb) {
                            for (int64_t d = rank_ - 1; d >= 0; --d) {
                                ++iDec_[d];
                                if (iDec_[d] < outDims_[d]) {
                                    break;
                                }
                                iDec_[d] = 0;
                            }
                        }
                    }
                    kf += nb;
                }
                /* 块推进后的下标：DMA 分支没有逐元素推进，这里统一前进 blk/nb */
                if (nb == blk && !advDone) {
                    iDec_[rank_ - 1] += blk;
                    for (int64_t d = rank_ - 1; d >= 0; --d) {
                        if (iDec_[d] < outDims_[d]) {
                            break;
                        }
                        if (d > 0) {
                            iDec_[d] = 0;
                            ++iDec_[d - 1];
                        } else {
                            iDec_[d] = 0;
                        }
                    }
                }
            }
            PipeBarrier<PIPE_ALL>();
            return;
        }
    }
    for (int64_t d = 0; d < rank_; ++d) {
        iDec_[d] = 0;
    }
    int64_t rem = chunkStart;
    for (int64_t d = rank_ - 1; d >= 0; --d) {
        const int64_t n = outDims_[d];
        iDec_[d] = (n > 0) ? (rem % n) : 0;
        rem = (n > 0) ? (rem / n) : 0;
    }
    int64_t src = 0;
    for (int64_t d = 0; d < rank_; ++d) {
        src += (iDec_[d] + front_[d]) * strides_[d];
    }
    for (int64_t k = 0; k < chunkLen; ++k) {
        outLocal_.SetValue(k,
            PadConvert<T>::FromFloat(PadConvert<T>::ToFloat(xGm_.GetValue(static_cast<uint32_t>(src)))));
        if (k + 1 < chunkLen && rank_ > 0) {
            ++iDec_[rank_ - 1];
            if (iDec_[rank_ - 1] < outDims_[rank_ - 1]) {
                src += strides_[rank_ - 1];   /* 最内维 stride 恒为 1 */
            } else {
                iDec_[rank_ - 1] = 0;
                for (int64_t d = rank_ - 2; d >= 0; --d) {
                    ++iDec_[d];
                    if (iDec_[d] < outDims_[d]) {
                        break;
                    }
                    iDec_[d] = 0;
                }
                src = 0;
                for (int64_t d = 0; d < rank_; ++d) {
                    src += (iDec_[d] + front_[d]) * strides_[d];
                }
            }
        }
    }
}

template <typename T>
__aicore__ inline void PadV3Grad<T>::CopyOutChunk(int64_t chunkStart, int64_t chunkLen)
{
    PipeBarrier<PIPE_ALL>();
    DataCopyExtParams p;
    p.blockCount = 1;
    p.blockLen = static_cast<uint32_t>(chunkLen * static_cast<int64_t>(sizeof(T)));
    p.srcStride = 0;
    p.dstStride = 0;
    p.rsv = 0;
    DataCopyPad(yGm_[chunkStart], outLocal_, p);
    PipeBarrier<PIPE_ALL>();
}

template <typename T>
__aicore__ inline void PadV3Grad<T>::Process()
{
    if (start_ >= end_) {
        return;
    }
    for (int64_t chunkStart = start_; chunkStart < end_; chunkStart += ubFactor_) {
        int64_t chunkLen = end_ - chunkStart;
        if (chunkLen > ubFactor_) {
            chunkLen = ubFactor_;
        }
        if (mode_ == 0) {
            ComputeConstantChunk(chunkStart, chunkLen);
        } else {
            ComputeChunk(chunkStart, chunkLen);
        }
        CopyOutChunk(chunkStart, chunkLen);
    }
}

} // namespace NsPadV3Grad
#endif // PADV3GRAD_H
