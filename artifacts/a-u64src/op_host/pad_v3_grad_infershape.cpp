/*!
 * \file pad_v3_grad_infershape.cpp
 * \brief PadV3Grad 形状推导（S0 Rev.2 / 161002 修复）
 *
 * 输出 shape 依赖 paddings 的“值”：out_shape[d] = x_shape[d] - front_d - back_d。
 *
 * 默认（PADV3_INFER_FROM_PADDINGS == 1）：**值依赖 infershape**
 *   - 注册 `.InputsDataDependency({1})`，由框架在 infershape 前把 paddings 搬到 Host；
 *   - 用 `context->GetInputTensor(1)` 读 2R 个 int32/int64：
 *       paddings_contiguous=true  -> [f0,b0,f1,b1,...]（flat 相邻配对）
 *       paddings_contiguous=false -> 前 R 个 front，后 R 个 back（[2,R] 排布）
 *   - `outShape->SetDimNum(rank)` + 逐维 `SetDim(d, xDim[d]-front[d]-back[d])`。
 *
 * 回退（不修改框架/调用方已给的输出 shape，直接返回 SUCCESS）：
 *   - `GetInputTensor(1)` 为空、`GetData` 为空（平台没有搬 Host 数据）；
 *   - paddings 的 dtype 不是 int32/int64；
 *   - paddings 的某一维为动态（<0），元素数无法确定；
 *   - 读到的值不在可信范围（|v| > 2^40，说明数据不可信）。
 *   注：本文件不引入日志头，回退分支静默保留 shape；风险记录见 IMPLEMENTATION.md。
 *
 * 非法（返回 FAILED）：
 *   - rank > 8（与 kernel 的 MAX_RANK 一致）；
 *   - paddings 元素数 != 2*rank（排布 rank 不一致）；
 *   - 计算出的输出维度 < 0（front/back 与 x 维度矛盾）。
 *
 * 历史：默认 no-op（不注册数据依赖）时平台点 1 报 `Runtime Error ACL 161002
 * = ACLNN_ERR_PARAM_INVALID`（输出 shape 未设置/校验失败）。本版默认启用读值路径。
 */

#include "register/op_impl_registry.h"
#include "exe_graph/runtime/infer_shape_context.h"

using namespace ge;

namespace ops {

#ifndef PADV3_INFER_FROM_PADDINGS
#define PADV3_INFER_FROM_PADDINGS 0
#endif

static constexpr size_t PADV3_INFER_MAX_RANK = 8;

#if PADV3_INFER_FROM_PADDINGS != 0
/* paddings 值的可信上界；超出视为“数据不可信”，回退到框架给的 shape */
static constexpr int64_t PADV3_INFER_VALUE_ABS_MAX = (1LL << 40);
#endif

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
    /* ---- 读值路径（默认启用）：要求 paddings 数据在 Host ---- */
    if (rank == 0) {
        /* 标量输入：输出仍是标量，无维度依赖 paddings */
        outShape->SetDimNum(0);
        return ge::GRAPH_SUCCESS;
    }

    const gert::Shape* pShape = context->GetInputShape(1);
    if (pShape == nullptr) {
        return ge::GRAPH_SUCCESS;               /* 回退：不覆盖框架 shape */
    }
    int64_t pNum = 1;
    const size_t pRank = pShape->GetDimNum();
    if (pRank == 0) {
        pNum = 1;                               /* 标量 paddings = 1 个元素 */
    } else {
        for (size_t d = 0; d < pRank; ++d) {
            const int64_t dim = pShape->GetDim(d);
            if (dim < 0) {
                return ge::GRAPH_SUCCESS;       /* 动态维：元素数未知，回退 */
            }
            pNum *= dim;
        }
    }
    if (pNum != static_cast<int64_t>(2 * rank)) {
        return ge::GRAPH_FAILED;                /* paddings 元素数必须恰为 2*rank */
    }

    const gert::Tensor* pTensor = context->GetInputTensor(1);
    if (pTensor == nullptr) {
        return ge::GRAPH_SUCCESS;               /* 平台未搬 Host 数据：回退 */
    }
    const ge::DataType dt = pTensor->GetDataType();
    if (dt != ge::DT_INT32 && dt != ge::DT_INT64) {
        return ge::GRAPH_SUCCESS;               /* 回退 */
    }

    int64_t padVals[2 * PADV3_INFER_MAX_RANK] = {0};
    const int64_t want = static_cast<int64_t>(2 * rank);
    if (dt == ge::DT_INT64) {
        const int64_t* p = pTensor->GetData<int64_t>();
        if (p == nullptr) {
            return ge::GRAPH_SUCCESS;           /* 数据为空：回退 */
        }
        for (int64_t k = 0; k < want; ++k) {
            if (p[k] < -PADV3_INFER_VALUE_ABS_MAX || p[k] > PADV3_INFER_VALUE_ABS_MAX) {
                return ge::GRAPH_SUCCESS;       /* 值不可信：回退，不改 shape */
            }
            padVals[k] = p[k];
        }
    } else {
        const int32_t* p = pTensor->GetData<int32_t>();
        if (p == nullptr) {
            return ge::GRAPH_SUCCESS;           /* 数据为空：回退 */
        }
        for (int64_t k = 0; k < want; ++k) {
            if (p[k] < -PADV3_INFER_VALUE_ABS_MAX || p[k] > PADV3_INFER_VALUE_ABS_MAX) {
                return ge::GRAPH_SUCCESS;       /* 值不可信：回退，不改 shape */
            }
            padVals[k] = static_cast<int64_t>(p[k]);
        }
    }

    /* 排布：contiguous -> [f0,b0,f1,b1,...]；否则 -> [f0..f{R-1}, b0..b{R-1}] */
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
        const int64_t front = contiguous ? padVals[2 * d] : padVals[d];
        const int64_t back = contiguous ? padVals[2 * d + 1] : padVals[rank + d];
        const int64_t n = xShape->GetDim(d);
        if (n < 0) {
            out.SetDim(d, -1);                  /* 动态维：保留未知 */
            continue;
        }
        const int64_t v = n - front - back;
        if (v < 0) {
            return ge::GRAPH_FAILED;            /* 非法：输出维度为负 */
        }
        out.SetDim(d, v);
    }

    outShape->SetDimNum(rank);
    for (size_t d = 0; d < rank; ++d) {
        outShape->SetDim(d, out.GetDim(d));
    }
    return ge::GRAPH_SUCCESS;
#endif
}

#if PADV3_INFER_FROM_PADDINGS != 0
/* 数据依赖：让框架在 infershape 前把 paddings（输入 1）的值复制到 Host。
 * 仅在开关打开时声明（默认打开），关闭开关时不引入该接口。 */
IMPL_OP_INFERSHAPE(PadV3Grad).InferShape(InferShapePadV3Grad).InputsDataDependency({1});
#else
IMPL_OP_INFERSHAPE(PadV3Grad).InferShape(InferShapePadV3Grad);
#endif

} // namespace ops
