/*!
 * \file pad_v3_grad_tiling_data.h
 * \brief PadV3Grad tiling data（S0 Rev.2）
 *
 * 前 3 个字段保持模板桩的名称/顺序；其余字段只在末尾追加并给默认值。
 * 结构体大小：4*8 + 2*8*8 + 5*8 = 200 B（远小于 4096 B 的 tiling data 上限）。
 *
 * 说明：
 *   - totalNum/blockFactor 只是 tiling 的“参考值”：kernel 用自己从 paddings 算出的
 *     total 为准；两者不一致时 kernel 自划分（不 clamp、不部分写）。
 *   - outDims[d] == 0 表示 tiling 未拿到输出 shape（kernel 自算）。
 */
#ifndef _PADV3GRAD_TILING_DATA_H_
#define _PADV3GRAD_TILING_DATA_H_

#include <cstdint>

#ifndef PADV3GRAD_MAX_RANK
#define PADV3GRAD_MAX_RANK 8
#endif

/* kernel guard 用到的上界；host 与 kernel 共用 */
#ifndef PADV3_UB_MAX
#define PADV3_UB_MAX 8192
#endif
#ifndef PADV3_XNUMEL_MAX
#define PADV3_XNUMEL_MAX (1LL << 40)
#endif

struct PadV3GradTilingData {
    int64_t totalNum = 0;     // prod(outDims)（若已知）；0 = kernel 自算
    int64_t blockFactor = 1;  // 每核输出元素数（若已知）；0 = kernel 自算
    int64_t ubFactor = 0;     // 每次 UB 处理的输出元素数（>0）
    int64_t rank = 0;         // R = x 维数
    int64_t xDims[PADV3GRAD_MAX_RANK] = {0};    // N_d（padded 长度）
    int64_t outDims[PADV3GRAD_MAX_RANK] = {0};  // n_d；0 = 未知
    int64_t mode = 2;         // 0=constant 1=edge(含 replicate) 2=reflect 3=symmetric 4=circular
    int64_t paddingsContiguous = 1;
    int64_t paddingsInt64 = 0;
    int64_t coreNum = 1;      // 实际启动块数（= SetBlockDim）
    int64_t dtypeCode = 0;    // 0=fp16 1=fp32
};
#endif
