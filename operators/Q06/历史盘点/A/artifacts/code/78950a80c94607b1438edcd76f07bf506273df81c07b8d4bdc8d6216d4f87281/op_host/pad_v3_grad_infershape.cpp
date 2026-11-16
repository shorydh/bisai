/*!
 * \file pad_v3_grad_infershape.cpp
 * \brief PadV3Grad 形状推导（S0 Rev.2）
 *
 * 输出 shape 依赖 paddings 的“值”：out_shape[d] = x_shape[d] - front_d - back_d。
 *
 * 默认（PADV3_INFER_FROM_PADDINGS == 0）：**纯 no-op**
 *   - 不读 paddings（平台 example 的 paddings 是 device aclTensor，host 解引用 device
 *     指针会崩溃）；
 *   - 不覆盖框架/调用方已给出的输出 shape；
 *   - 不复制 input0 的 shape（模板桩的旧逻辑是错的）。
 *   平台 `-e` 路径的输出张量由调用方按 golden shape 创建（examples/sample.py/case.json）。
 *
 * 打开编译期开关（= 1）后才读取 paddings 值；启用前必须先在平台确认
 * `GetInputTensor(1)` 返回的是 Host 地址（S2 专项验证）。
 */

#include "register/op_impl_registry.h"
#include "exe_graph/runtime/infer_shape_context.h"

using namespace ge;

namespace ops {

#ifndef PADV3_INFER_FROM_PADDINGS
#define PADV3_INFER_FROM_PADDINGS 0
#endif

static constexpr size_t PADV3_INFER_MAX_RANK = 8;

static ge::graphStatus InferShapePadV3Grad(gert::InferShapeContext* context)
{
    if (context == nullptr) {
        return ge::GRAPH_FAILED;
    }
    const gert::Shape* xShape = context->GetInputShape(0);
    if (xShape == nullptr) {
        return ge::GRAPH_FAILED;
    }
    const size_t rank = xShape->GetDimNum();
    if (rank > PADV3_INFER_MAX_RANK) {
        return ge::GRAPH_FAILED;
    }
    gert::Shape* outShape = context->GetOutputShape(0);
    if (outShape == nullptr) {
        return ge::GRAPH_FAILED;
    }

#if PADV3_INFER_FROM_PADDINGS == 0
    /* no-op：不读数据、不改输出 shape（shape 由调用方/框架提供） */
    (void)outShape;
    return ge::GRAPH_SUCCESS;
#else
    /* ---- 读值路径：仅开关打开时编译；要求 paddings 数据在 Host ---- */
    const gert::Shape* pShape = context->GetInputShape(1);
    if (pShape == nullptr) {
        return ge::GRAPH_SUCCESS;
    }
    int64_t pNum = 1;
    if (pShape->GetDimNum() == 0) {
        pNum = (rank == 0) ? 0 : 1;
    } else {
        for (size_t d = 0; d < pShape->GetDimNum(); ++d) {
            const int64_t dim = pShape->GetDim(d);
            if (dim < 0) {
                return ge::GRAPH_SUCCESS;   /* 未知维：不冒险读 */
            }
            pNum *= dim;
        }
    }
    if (pNum != static_cast<int64_t>(2 * rank)) {
        return ge::GRAPH_SUCCESS;           /* 元素数不符：不读 */
    }

    const gert::Tensor* pTensor = context->GetInputTensor(1);
    if (pTensor == nullptr) {
        return ge::GRAPH_SUCCESS;
    }
    const ge::DataType dt = pTensor->GetDataType();
    if (dt != ge::DT_INT32 && dt != ge::DT_INT64) {
        return ge::GRAPH_SUCCESS;
    }

    bool contiguous = true;
    const gert::RuntimeAttrs* attrs = context->GetAttrs();
    if (attrs != nullptr) {
        const bool* pc = attrs->GetAttrPointer<bool>(1);
        if (pc != nullptr) {
            contiguous = *pc;
        }
    }

    gert::Shape out;
    out.SetDimNum(rank);
    for (size_t d = 0; d < rank; ++d) {
        int64_t front = 0;
        int64_t back = 0;
        const size_t i0 = contiguous ? (2 * d) : d;
        const size_t i1 = contiguous ? (2 * d + 1) : (rank + d);
        if (dt == ge::DT_INT64) {
            const int64_t* p = pTensor->GetData<int64_t>();
            if (p == nullptr) {
                return ge::GRAPH_SUCCESS;
            }
            front = p[i0];
            back = p[i1];
        } else {
            const int32_t* p = pTensor->GetData<int32_t>();
            if (p == nullptr) {
                return ge::GRAPH_SUCCESS;
            }
            front = static_cast<int64_t>(p[i0]);
            back = static_cast<int64_t>(p[i1]);
        }
        const int64_t n = xShape->GetDim(d);
        if (n < 0) {
            out.SetDim(d, -1);
        } else {
            int64_t v = n - front - back;
            if (v < 0) {
                v = 0;
            }
            out.SetDim(d, v);
        }
    }
    *outShape = out;
    return ge::GRAPH_SUCCESS;
#endif
}

#if PADV3_INFER_FROM_PADDINGS != 0
/* 仅开关打开时才声明数据依赖，默认构建不引入该接口 */
IMPL_OP_INFERSHAPE(PadV3Grad).InferShape(InferShapePadV3Grad).InputsDataDependency({1});
#else
IMPL_OP_INFERSHAPE(PadV3Grad).InferShape(InferShapePadV3Grad);
#endif

} // namespace ops
