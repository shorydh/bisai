/*!
 * \file pad_v3_grad_tiling.h
 * \brief PadV3Grad tiling 数据定义
 */

#ifndef _I_PADV3GRAD_TILING_H_
#define _I_PADV3GRAD_TILING_H_

#include <cstdint>
#include <cstring>
#include "../../../op_kernel/pad_v3_grad_tiling_data.h"
#include "tikicpulib.h"
#include "kernel_operator.h"
#include "kernel_tiling/kernel_tiling.h"
#include "graph/c_types.h"
#include "ascendc/host_api/tiling/template_argument.h"

#ifndef __aicore__
#define __aicore__
#endif

#ifndef __gm__
#define __gm__
#endif

#ifndef __ubuf__
#define __ubuf__
#endif

template <typename Wire>
inline void InitTilingData(const uint8_t *tiling, Wire *constData)
{
    // CPU emulation uses the exact wire size selected by the real kernel.
    memcpy(constData, tiling, sizeof(Wire));
}

#ifdef GET_TILING_DATA_WITH_STRUCT
#undef GET_TILING_DATA_WITH_STRUCT
#endif
#define GET_TILING_DATA_WITH_STRUCT(tilingStruct, tilingData, tilingArg) \
    tilingStruct tilingData;                                             \
    InitTilingData(tilingArg, &tilingData)

#ifdef GET_TILING_DATA
#undef GET_TILING_DATA
#endif
#define GET_TILING_DATA(tilingData, tilingArg) \
    PadV3GradTilingData tilingData;          \
    InitTilingData(tilingArg, &tilingData)

#endif
