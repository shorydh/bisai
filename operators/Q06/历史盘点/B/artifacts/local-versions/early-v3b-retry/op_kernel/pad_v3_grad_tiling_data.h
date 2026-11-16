#ifndef PAD_V3_GRAD_TILING_DATA_H
#define PAD_V3_GRAD_TILING_DATA_H
#include <cstddef>
#include <cstdint>
constexpr int64_t PAD_V3_GRAD_MAX_RANK = 32;
constexpr int64_t PAD_V3_GRAD_SMALL_RANK = 8;
// Fixed-width wire POD shared by the host and kernel. No default initialization:
// the host value-initializes it, while the kernel loads only the active axes.
struct PadV3GradTilingData {
    int64_t totalInput;
    int64_t totalOutput;
    int64_t blockFactor;
    int64_t ubFactor;
    int64_t rank;
    int64_t mode;
    int64_t inputShape[PAD_V3_GRAD_MAX_RANK];
    int64_t outputShape[PAD_V3_GRAD_MAX_RANK];
    int64_t inputStride[PAD_V3_GRAD_MAX_RANK];
    int64_t padFront[PAD_V3_GRAD_MAX_RANK];
    // Generated tensor-ABI ACLNN callers may keep padding values on the device.
    int64_t paddingsDtype;       // 0=int32, 1=int64
    int64_t paddingsContiguous;
    int64_t readPaddings;        // 1: kernel loads front values from GM
};
// Compact wire format for the common low-rank case. The algorithm retains the
// same field names; larger ranks continue to use the full format above.
struct PadV3GradSmallTilingData {
    int64_t totalInput;
    int64_t totalOutput;
    int64_t blockFactor;
    int64_t ubFactor;
    int64_t rank;
    int64_t mode;
    int64_t inputShape[PAD_V3_GRAD_SMALL_RANK];
    int64_t outputShape[PAD_V3_GRAD_SMALL_RANK];
    int64_t inputStride[PAD_V3_GRAD_SMALL_RANK];
    int64_t padFront[PAD_V3_GRAD_SMALL_RANK];
    int64_t paddingsDtype;
    int64_t paddingsContiguous;
    int64_t readPaddings;
};
static_assert(sizeof(PadV3GradSmallTilingData) == 328, "compact wire size changed");
static_assert(offsetof(PadV3GradSmallTilingData, totalInput) == 0, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, totalOutput) == 8, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, blockFactor) == 16, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, ubFactor) == 24, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, rank) == 32, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, mode) == 40, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, inputShape) == 48, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, outputShape) == 112, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, inputStride) == 176, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, padFront) == 240, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, paddingsDtype) == 304, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, paddingsContiguous) == 312, "compact wire offset");
static_assert(offsetof(PadV3GradSmallTilingData, readPaddings) == 320, "compact wire offset");
// Keep the established host/device ABI exact, including all unused array slots.
static_assert(sizeof(PadV3GradTilingData) == 1096, "PadV3Grad wire size changed");
static_assert(offsetof(PadV3GradTilingData, totalInput) == 0, "wire offset");
static_assert(offsetof(PadV3GradTilingData, totalOutput) == 8, "wire offset");
static_assert(offsetof(PadV3GradTilingData, blockFactor) == 16, "wire offset");
static_assert(offsetof(PadV3GradTilingData, ubFactor) == 24, "wire offset");
static_assert(offsetof(PadV3GradTilingData, rank) == 32, "wire offset");
static_assert(offsetof(PadV3GradTilingData, mode) == 40, "wire offset");
static_assert(offsetof(PadV3GradTilingData, inputShape) == 48, "wire offset");
static_assert(offsetof(PadV3GradTilingData, outputShape) == 304, "wire offset");
static_assert(offsetof(PadV3GradTilingData, inputStride) == 560, "wire offset");
static_assert(offsetof(PadV3GradTilingData, padFront) == 816, "wire offset");
static_assert(offsetof(PadV3GradTilingData, paddingsDtype) == 1072, "wire offset");
static_assert(offsetof(PadV3GradTilingData, paddingsContiguous) == 1080, "wire offset");
static_assert(offsetof(PadV3GradTilingData, readPaddings) == 1088, "wire offset");
#endif
