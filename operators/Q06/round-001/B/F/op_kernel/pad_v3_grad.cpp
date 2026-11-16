/*!
 * \file pad_v3_grad.cpp
 * \brief PadV3Grad 算子 kernel 入口
 */

#include "pad_v3_grad.h"

enum class PadV3GradTilingKey : uint32_t
{
    TILING_KEY_PADV3GRAD_MODE_0 = 0,
    TILING_KEY_PADV3GRAD_MODE_1 = 1,
    TILING_KEY_PADV3GRAD_MODE_2 = 2,
    TILING_KEY_PADV3GRAD_MODE_3 = 3,
};

// Dynamic ACLNN tiling lives in GM. The generated GET_TILING_DATA macro copies
// the whole rank-32 struct via UB into the stack and synchronizes both engines.
// Load just the active fields; unused array entries are never consumed.
__aicore__ inline bool LoadPadV3GradTiling(GM_ADDR tiling, PadV3GradTilingData &data)
{
    AscendC::GlobalTensor<int64_t> words;
    words.SetGlobalBuffer(reinterpret_cast<__gm__ int64_t *>(tiling),
                          sizeof(PadV3GradTilingData) / sizeof(int64_t));
    data.totalInput = words.GetValue(0);
    data.totalOutput = words.GetValue(1);
    data.blockFactor = words.GetValue(2);
    data.ubFactor = words.GetValue(3);
    data.rank = words.GetValue(4);
    data.mode = words.GetValue(5);
    if (data.rank < 0 || data.rank > PAD_V3_GRAD_MAX_RANK) {
        return false;
    }
    data.paddingsDtype = words.GetValue(134);
    data.paddingsContiguous = words.GetValue(135);
    data.readPaddings = words.GetValue(136);
    for (int64_t d = 0; d < data.rank; ++d) {
        data.inputShape[d] = words.GetValue(6 + d);
        data.outputShape[d] = words.GetValue(38 + d);
        data.inputStride[d] = words.GetValue(70 + d);
        if (data.readPaddings == 0) {
            data.padFront[d] = words.GetValue(102 + d);
        }
    }
    return true;
}

template <uint32_t schMode>
__global__ __aicore__ void pad_v3_grad(GM_ADDR x, GM_ADDR paddings, GM_ADDR y, GM_ADDR workspace, GM_ADDR tiling)
{
    REGISTER_TILING_DEFAULT(PadV3GradTilingData);
    REGISTER_TILING_FOR_TILINGKEY("schMode == 2", PadV3GradSmallTilingData);
    REGISTER_TILING_FOR_TILINGKEY("schMode == 3", PadV3GradSmallTilingData);
    if constexpr (schMode == 2 || schMode == 3) {
        // Small metadata is contiguous and inexpensive to DMA in one operation.
        GET_TILING_DATA_WITH_STRUCT(PadV3GradSmallTilingData, tilingData, tiling);
        if (tilingData.rank < 0 || tilingData.rank > PAD_V3_GRAD_SMALL_RANK) {
            return;
        }
        if constexpr (schMode == 2) {
            NsPadV3Grad::PadV3Grad<half, PadV3GradSmallTilingData> op;
            op.Init(x, paddings, y, &tilingData);
            op.Process();
        } else {
            NsPadV3Grad::PadV3Grad<float, PadV3GradSmallTilingData> op;
            op.Init(x, paddings, y, &tilingData);
            op.Process();
        }
    } else {
        // Retain the generated binary's tiling-size metadata without a bulk copy.
    #ifdef REGISTER_TILINGDATA_SIZE
        REGISTER_TILINGDATA_SIZE(PadV3GradTilingData, __COUNTER__);
    #endif
        PadV3GradTilingData tilingData;
        if (!LoadPadV3GradTiling(tiling, tilingData)) {
            return;
        }
        if constexpr (schMode == static_cast<uint32_t>(PadV3GradTilingKey::TILING_KEY_PADV3GRAD_MODE_0)) {
            NsPadV3Grad::PadV3Grad<half> op;
            op.Init(x, paddings, y, &tilingData);
            op.Process();
        }
        if constexpr (schMode == static_cast<uint32_t>(PadV3GradTilingKey::TILING_KEY_PADV3GRAD_MODE_1)) {
            NsPadV3Grad::PadV3Grad<float> op;
            op.Init(x, paddings, y, &tilingData);
            op.Process();
        }
    }
}
