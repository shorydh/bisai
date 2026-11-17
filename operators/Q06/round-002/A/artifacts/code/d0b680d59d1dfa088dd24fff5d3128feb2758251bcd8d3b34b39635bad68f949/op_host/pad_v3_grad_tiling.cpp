/*!
 * \file pad_v3_grad_tiling.cpp
 * \brief Validate padding values and partition disjoint output ranges among AIV cores.
 */
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <limits>
#include "register/op_def_registry.h"
#include "op_common/log/log.h"
#include "op_common/op_host/util/platform_util.h"
#include "../op_kernel/pad_v3_grad_tiling_data.h"
#include "../op_kernel/pad_v3_grad_tiling_key.h"

namespace optiling {
namespace {
constexpr int64_t kMaxRank = PAD_V3_GRAD_MAX_RANK;
constexpr int64_t kTileElements = 1024;
constexpr int64_t kSmallInputElements = 8192;
constexpr int64_t kSmallOutputElements = 256;
constexpr int64_t kSmallWorkPerCore = 32;
constexpr int64_t kGeneralWorkPerCore = 256;
constexpr uint64_t kMinUbBytes = 128 * 1024;
constexpr int64_t kDmaBytes = 32;

bool AddChecked(int64_t left, int64_t right, int64_t& result)
{
    if ((right > 0 && left > std::numeric_limits<int64_t>::max() - right) ||
        (right < 0 && left < std::numeric_limits<int64_t>::min() - right)) {
        return false;
    }
    result = left + right;
    return true;
}

bool SubtractChecked(int64_t left, int64_t right, int64_t& result)
{
    if ((right > 0 && left < std::numeric_limits<int64_t>::min() + right) ||
        (right < 0 && left > std::numeric_limits<int64_t>::max() + right)) {
        return false;
    }
    result = left - right;
    return true;
}

bool MultiplyChecked(int64_t left, int64_t right, int64_t& result)
{
    if (left < 0 || right < 0 || (right != 0 && left > std::numeric_limits<int64_t>::max() / right)) {
        return false;
    }
    result = left * right;
    return true;
}

int64_t CeilDivide(int64_t numerator, int64_t denominator)
{
    return numerator / denominator + (numerator % denominator != 0);
}

int64_t GetMode(const char* name)
{
    if (name == nullptr || std::strcmp(name, "reflect") == 0) {
        return 2;
    }
    if (std::strcmp(name, "constant") == 0) {
        return 0;
    }
    if (std::strcmp(name, "edge") == 0 || std::strcmp(name, "replicate") == 0) {
        return 1;
    }
    if (std::strcmp(name, "symmetric") == 0) {
        return 3;
    }
    if (std::strcmp(name, "circular") == 0) {
        return 4;
    }
    return -1;
}

void CopyCompactTiling(const PadV3GradTilingData& source, PadV3GradSmallTilingData& destination)
{
    destination = PadV3GradSmallTilingData{};
    destination.totalInput = source.totalInput;
    destination.totalOutput = source.totalOutput;
    destination.blockFactor = source.blockFactor;
    destination.ubFactor = source.ubFactor;
    destination.rank = source.rank;
    destination.mode = source.mode;
    destination.paddingsDtype = source.paddingsDtype;
    destination.paddingsContiguous = source.paddingsContiguous;
    destination.readPaddings = source.readPaddings;
    for (int64_t axis = 0; axis < source.rank; ++axis) {
        destination.inputShape[axis] = source.inputShape[axis];
        destination.outputShape[axis] = source.outputShape[axis];
        destination.inputStride[axis] = source.inputStride[axis];
        destination.padFront[axis] = source.padFront[axis];
    }
}

template <typename P>
bool PopulateShapes(const gert::Shape& input, const gert::Shape& output, const P* paddings,
    bool contiguous, PadV3GradTilingData& tiling)
{
    const int64_t rank = static_cast<int64_t>(input.GetDimNum());
    if (rank > kMaxRank || output.GetDimNum() != input.GetDimNum()) {
        return false;
    }
    tiling.rank = rank;
    for (int64_t axis = 0; axis < rank; ++axis) {
        const int64_t inputDim = input.GetDim(axis);
        const int64_t front = paddings == nullptr ? 0 : paddings[contiguous ? 2 * axis : axis];
        const int64_t back = paddings == nullptr ? 0 : paddings[contiguous ? 2 * axis + 1 : rank + axis];
        int64_t outputDim = output.GetDim(axis);
        if (inputDim < 0 || outputDim < 0) {
            return false;
        }
        if (paddings != nullptr && (!SubtractChecked(inputDim, front, outputDim) ||
            !SubtractChecked(outputDim, back, outputDim) || outputDim < 0 ||
            output.GetDim(axis) != outputDim)) {
            return false;
        }
        // Nonconstant mapping into a zero-length dimension is undefined unless
        // the corresponding input dimension is empty as well.
        if (tiling.mode != 0 && outputDim == 0 && inputDim != 0) {
            return false;
        }
        // The mirror period and signed coordinate arithmetic must stay in int64.
        int64_t ignored;
        if (outputDim > std::numeric_limits<int64_t>::max() / 2 ||
            front == std::numeric_limits<int64_t>::min() ||
            (inputDim > 0 && !SubtractChecked(inputDim - 1, front, ignored)) ||
            (outputDim > 0 && !AddChecked(outputDim - 1, front, ignored))) {
            return false;
        }
        tiling.inputShape[axis] = inputDim;
        tiling.outputShape[axis] = outputDim;
        tiling.padFront[axis] = front;
    }
    tiling.totalInput = 1;
    tiling.totalOutput = 1;
    for (int64_t axis = rank; axis-- > 0;) {
        tiling.inputStride[axis] = tiling.totalInput;
        if (!MultiplyChecked(tiling.totalInput, tiling.inputShape[axis], tiling.totalInput) ||
            !MultiplyChecked(tiling.totalOutput, tiling.outputShape[axis], tiling.totalOutput)) {
            return false;
        }
    }
    return true;
}
} // namespace

static ge::graphStatus PadV3GradTilingFunc(gert::TilingContext* context)
{
    const auto* input = context->GetInputShape(0);
    const auto* output = context->GetOutputShape(0);
    const auto* xDesc = context->GetInputDesc(0);
    const auto* yDesc = context->GetOutputDesc(0);
    const gert::Tensor* paddings = context->GetInputTensor(1);
    OP_CHECK_NULL_WITH_CONTEXT(context, input);
    OP_CHECK_NULL_WITH_CONTEXT(context, output);
    OP_CHECK_NULL_WITH_CONTEXT(context, xDesc);
    OP_CHECK_NULL_WITH_CONTEXT(context, yDesc);
    OP_CHECK_NULL_WITH_CONTEXT(context, paddings);
    const auto dtype = xDesc->GetDataType();
    OP_CHECK_IF((dtype != ge::DT_FLOAT16 && dtype != ge::DT_FLOAT) || yDesc->GetDataType() != dtype,
        OP_LOGE(context, "x and y must have matching float16 or float32 dtypes"), return ge::GRAPH_FAILED);

    const auto& xShape = input->GetStorageShape();
    const auto& yShape = output->GetStorageShape();
    OP_CHECK_IF(xShape.GetDimNum() > kMaxRank ||
        paddings->GetShapeSize() != 2 * static_cast<int64_t>(xShape.GetDimNum()),
        OP_LOGE(context, "paddings must contain exactly two values per input dimension (rank <= 32)"),
        return ge::GRAPH_FAILED);
    const auto* attrs = context->GetAttrs();
    const char* modeName = attrs == nullptr ? nullptr : attrs->GetStr(0);
    const bool* contiguousAttr = attrs == nullptr ? nullptr : attrs->GetAttrPointer<bool>(1);
    const bool contiguous = contiguousAttr == nullptr ? true : *contiguousAttr;

    // Validate and schedule in a local full-rank object. A compact variant may
    // have only 328 bytes of raw tiling storage, so never write a large POD there.
    PadV3GradTilingData working{};
    PadV3GradTilingData* tiling = &working;
    tiling->mode = GetMode(modeName);
    OP_CHECK_IF(tiling->mode < 0, OP_LOGE(context, "Unsupported padding mode"), return ge::GRAPH_FAILED);
    bool valid = false;
    // GetData may carry a DEVICE address in the direct ACLNN tensor-input path.
    // Never dereference it on the host merely because it is non-null.
    const auto placement = paddings->GetPlacement();
    const bool paddingOnHost = placement == gert::TensorPlacement::kOnHost ||
        placement == gert::TensorPlacement::kFollowing;
    tiling->paddingsContiguous = contiguous ? 1 : 0;
    if (paddings->GetDataType() == ge::DT_INT32) {
        const int32_t* values = paddingOnHost ? paddings->GetData<int32_t>() : nullptr;
        tiling->paddingsDtype = 0;
        tiling->readPaddings = xShape.GetDimNum() != 0 ? 1 : 0;
        valid = PopulateShapes(xShape, yShape, values, contiguous, *tiling);
    } else if (paddings->GetDataType() == ge::DT_INT64) {
        const int64_t* values = paddingOnHost ? paddings->GetData<int64_t>() : nullptr;
        tiling->paddingsDtype = 1;
        tiling->readPaddings = xShape.GetDimNum() != 0 ? 1 : 0;
        valid = PopulateShapes(xShape, yShape, values, contiguous, *tiling);
    }
    // Ordinary tensor values are not part of the ACLNN tiling-cache key. Even
    // host-readable padding can change between otherwise identical invocations,
    // so each core always refreshes front values from the current kernel input.
    // When values are unavailable here, the caller's concrete y shape is used.
    const int64_t typeBytes = dtype == ge::DT_FLOAT16 ? 2 : 4;
    OP_CHECK_IF(!valid || tiling->totalInput > std::numeric_limits<int64_t>::max() / typeBytes ||
        tiling->totalOutput > std::numeric_limits<int64_t>::max() / typeBytes,
        OP_LOGE(context, "Invalid padding dtype, values, output shape, or overflowing dimensions"),
        return ge::GRAPH_FAILED);

    auto* platformInfo = context->GetPlatformInfo();
    OP_CHECK_NULL_WITH_CONTEXT(context, platformInfo);
    auto platform = platform_ascendc::PlatformAscendC(platformInfo);
    const int64_t coreNum = platform.GetCoreNumAiv();
    uint64_t ubBytes = 0;
    platform.GetCoreMemSize(platform_ascendc::CoreMemType::UB, ubBytes);
    OP_CHECK_IF(coreNum <= 0 || ubBytes < kMinUbBytes,
        OP_LOGE(context, "No AIV cores or insufficient UB memory"), return ge::GRAPH_FAILED);

    tiling->ubFactor = kTileElements;
    uint32_t blockDim = 1;
    tiling->blockFactor = 0;
    if (tiling->totalOutput != 0) {
        const int64_t alignment = kDmaBytes / typeBytes;
        // Shape-only scheduling stays valid across cached invocations with
        // different padding values. Keep every output interval DMA-aligned.
        const bool smallOutput = tiling->totalInput <= kSmallInputElements &&
            tiling->totalOutput <= kSmallOutputElements;
        const int64_t workPerCore = smallOutput ? kSmallWorkPerCore : kGeneralWorkPerCore;
        const int64_t usefulCores = std::max<int64_t>(1,
            CeilDivide(std::max(tiling->totalInput, tiling->totalOutput), workPerCore));
        const int64_t requestedCores = std::min(coreNum,
            std::min(usefulCores, CeilDivide(tiling->totalOutput, alignment)));
        const int64_t alignedBlocks = CeilDivide(CeilDivide(tiling->totalOutput, requestedCores), alignment);
        tiling->blockFactor = alignedBlocks * alignment;
        blockDim = static_cast<uint32_t>(CeilDivide(tiling->totalOutput, tiling->blockFactor));
    }
    context->SetBlockDim(blockDim);
    if (tiling->rank <= PAD_V3_GRAD_SMALL_RANK) {
        auto* compact = context->GetTilingData<PadV3GradSmallTilingData>();
        OP_CHECK_NULL_WITH_CONTEXT(context, compact);
        CopyCompactTiling(*tiling, *compact);
        context->SetTilingKey(dtype == ge::DT_FLOAT16 ? GET_TPL_TILING_KEY(PADV3GRAD_TPL_SCH_MODE_2) :
            GET_TPL_TILING_KEY(PADV3GRAD_TPL_SCH_MODE_3));
        context->GetRawTilingData()->SetDataSize(sizeof(PadV3GradSmallTilingData));
    } else {
        auto* full = context->GetTilingData<PadV3GradTilingData>();
        OP_CHECK_NULL_WITH_CONTEXT(context, full);
        *full = *tiling;
        context->SetTilingKey(dtype == ge::DT_FLOAT16 ? GET_TPL_TILING_KEY(PADV3GRAD_TPL_SCH_MODE_0) :
            GET_TPL_TILING_KEY(PADV3GRAD_TPL_SCH_MODE_1));
        context->GetRawTilingData()->SetDataSize(sizeof(PadV3GradTilingData));
    }
    size_t* workspace = context->GetWorkspaceSizes(1);
    OP_CHECK_NULL_WITH_CONTEXT(context, workspace);
    workspace[0] = 0;
    return ge::GRAPH_SUCCESS;
}

static ge::graphStatus TilingParseForPadV3Grad(gert::TilingParseContext*)
{
    return ge::GRAPH_SUCCESS;
}

struct PadV3GradCompileInfo {};

IMPL_OP_OPTILING(PadV3Grad)
    .Tiling(PadV3GradTilingFunc)
    .TilingParse<PadV3GradCompileInfo>(TilingParseForPadV3Grad)
    .TilingInputsDataDependency({1});
} // namespace optiling
