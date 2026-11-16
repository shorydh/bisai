/*!
 * \file pad_v3_grad_infershape.cpp
 * \brief Infer the unpadded shape from the input gradient and padding values.
 */
#include <cstdint>
#include <cstring>
#include <limits>
#include "register/op_impl_registry.h"
#include "exe_graph/runtime/infer_shape_context.h"
#include "exe_graph/runtime/infer_datatype_context.h"
#include "../op_kernel/pad_v3_grad_tiling_data.h"

namespace ops {
namespace {
constexpr size_t kMaxRank = PAD_V3_GRAD_MAX_RANK;

bool SubtractChecked(int64_t left, int64_t right, int64_t& result)
{
    if ((right > 0 && left < std::numeric_limits<int64_t>::min() + right) ||
        (right < 0 && left > std::numeric_limits<int64_t>::max() + right)) {
        return false;
    }
    result = left - right;
    return true;
}

bool ValidMode(const char* mode)
{
    return mode == nullptr || std::strcmp(mode, "constant") == 0 || std::strcmp(mode, "edge") == 0 ||
        std::strcmp(mode, "replicate") == 0 || std::strcmp(mode, "reflect") == 0 ||
        std::strcmp(mode, "symmetric") == 0 || std::strcmp(mode, "circular") == 0;
}

template <typename P>
ge::graphStatus InferWithPaddings(const gert::Shape& input, const P* paddings,
    bool contiguous, gert::Shape& output)
{
    const size_t rank = input.GetDimNum();
    output.SetDimNum(rank);
    for (size_t axis = 0; axis < rank; ++axis) {
        const int64_t inputDim = input.GetDim(axis);
        if (inputDim < -1) {
            return ge::GRAPH_FAILED;
        }
        if (paddings == nullptr || inputDim == -1) {
            output.SetDim(axis, -1);
            continue;
        }
        const int64_t front = paddings[contiguous ? 2 * axis : axis];
        const int64_t back = paddings[contiguous ? 2 * axis + 1 : rank + axis];
        int64_t dim;
        if (!SubtractChecked(inputDim, front, dim) || !SubtractChecked(dim, back, dim) || dim < 0) {
            return ge::GRAPH_FAILED;
        }
        output.SetDim(axis, dim);
    }
    return ge::GRAPH_SUCCESS;
}
} // namespace

static ge::graphStatus InferShapePadV3Grad(gert::InferShapeContext* context)
{
    const gert::Shape* input = context->GetInputShape(0);
    gert::Shape* output = context->GetOutputShape(0);
    if (input == nullptr || output == nullptr) {
        return ge::GRAPH_FAILED;
    }
    // CANN represents an unknown rank by the one-element shape [-2].
    if (input->GetDimNum() == 1 && input->GetDim(0) == -2) {
        *output = *input;
        return ge::GRAPH_SUCCESS;
    }
    if (input->GetDimNum() > kMaxRank) {
        return ge::GRAPH_FAILED;
    }
    const gert::Tensor* paddings = context->GetInputTensor(1);
    if (paddings == nullptr) {
        return ge::GRAPH_FAILED;
    }
    const auto* attrs = context->GetAttrs();
    const char* mode = attrs == nullptr ? nullptr : attrs->GetStr(0);
    const bool* contiguousAttr = attrs == nullptr ? nullptr : attrs->GetAttrPointer<bool>(1);
    const bool contiguous = contiguousAttr == nullptr ? true : *contiguousAttr;
    if (!ValidMode(mode)) {
        return ge::GRAPH_FAILED;
    }
    const int64_t paddingCount = paddings->GetShapeSize();
    if (paddingCount >= 0 && paddingCount != 2 * static_cast<int64_t>(input->GetDimNum())) {
        return ge::GRAPH_FAILED;
    }
    // Graph construction may see absent values or a device-resident tensor.
    // Infer only from host-readable data; otherwise preserve unknown dimensions.
    // Direct ACLNN tiling can instead use its caller-provided output descriptor.
    const auto placement = paddings->GetPlacement();
    const bool paddingOnHost = placement == gert::TensorPlacement::kOnHost ||
        placement == gert::TensorPlacement::kFollowing;
    if (paddings->GetDataType() == ge::DT_INT32) {
        return InferWithPaddings(*input, paddingOnHost ? paddings->GetData<int32_t>() : nullptr,
            contiguous, *output);
    }
    if (paddings->GetDataType() == ge::DT_INT64) {
        return InferWithPaddings(*input, paddingOnHost ? paddings->GetData<int64_t>() : nullptr,
            contiguous, *output);
    }
    return ge::GRAPH_FAILED;
}

static ge::graphStatus InferDataTypePadV3Grad(gert::InferDataTypeContext* context)
{
    const auto dtype = context->GetInputDataType(0);
    if (dtype != ge::DT_FLOAT16 && dtype != ge::DT_FLOAT) {
        return ge::GRAPH_FAILED;
    }
    return context->SetOutputDataType(0, dtype);
}

IMPL_OP_INFERSHAPE(PadV3Grad)
    .InferShape(InferShapePadV3Grad)
    .InferDataType(InferDataTypePadV3Grad)
    .InputsDataDependency({1});
} // namespace ops
