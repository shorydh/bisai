/*!
 * \file pad_v3_grad_tiling.cpp
 * \brief PadV3Grad Tiling 实现（S0 Rev.2）
 *
 * 设计要点：
 *   1. tiling **不读 paddings 的值**（只校验元素数 = 2*rank）；front/back 由 kernel 从
 *      GM 读取并自算 n_d / totalNum。这样 host 侧零数据依赖，避免 host 解引用 device
 *      指针。
 *   2. 分核按**工作量** x.numel = Π N_d 预算（大 pad 时输出小、工作量大）。
 *   3. 输出 shape 只在 `TilingContext::GetOutputShape` 可用时用于优化 blockFactor；
 *      取不到时 blockFactor=0，kernel 自划分。
 *   4. dtype 逐输入独立校验：x ∈ {fp16, fp32}、paddings ∈ {int32, int64} 四种组合都支持。
 *      tilingKey 只由 x dtype 决定，paddings 宽度只写进 tiling 字段。
 *   5. workspace = 0。
 */

#include "register/op_def_registry.h"
#include "op_common/log/log.h"
#include "op_common/op_host/util/math_util.h"
#include "op_common/op_host/util/platform_util.h"
#include "../op_kernel/pad_v3_grad_tiling_data.h"
#include "../op_kernel/pad_v3_grad_tiling_key.h"

#include <cstring>

namespace optiling {

using Ops::Base::CeilDiv;
using Ops::Base::CeilAlign;
using Ops::Base::FloorDiv;
using Ops::Base::FloorAlign;
using Ops::Base::GetUbBlockSize;

constexpr uint32_t WS_SYS_SIZE = 0U;
constexpr int64_t MIN_WORK_PER_CORE = 1024;
constexpr int64_t TILING_SAFE_BYTES = 1024;
constexpr int64_t TILING_PAD_BYTES = 256;

/*
 * TilingContext::GetOutputShape 只用于“可选地”填充 totalNum/blockFactor。
 * 它不影响正确性：kernel 会用自己从 paddings 算出的 total 再划分一次。
 * 为把 P0 编译风险降到最低，默认关闭（=0）；平台确认该接口后改成 1 即可（单变量）。
 */
#ifndef PADV3_TILING_USE_OUT_SHAPE
#define PADV3_TILING_USE_OUT_SHAPE 0
#endif

static inline int64_t CeilDivI(int64_t a, int64_t b)
{
    return (a > 0) ? ((a + b - 1) / b) : 0;
}

static ge::graphStatus GetPlatformInfo(gert::TilingContext* context, uint64_t& ubSize, int64_t& coreNum)
{
    fe::PlatFormInfos* platformInfoPtr = context->GetPlatformInfo();
    OP_CHECK_NULL_WITH_CONTEXT(context, platformInfoPtr);
    auto ascendcPlatform = platform_ascendc::PlatformAscendC(platformInfoPtr);
    coreNum = ascendcPlatform.GetCoreNumAiv();
    OP_CHECK_IF(coreNum == 0, OP_LOGE(context, "coreNum is 0"), return ge::GRAPH_FAILED);
    ascendcPlatform.GetCoreMemSize(platform_ascendc::CoreMemType::UB, ubSize);
    OP_CHECK_IF(ubSize == 0, OP_LOGE(context, "ubSize is 0"), return ge::GRAPH_FAILED);
    return ge::GRAPH_SUCCESS;
}

static ge::graphStatus GetWorkspaceSize(gert::TilingContext* context)
{
    size_t* currentWorkspace = context->GetWorkspaceSizes(1);
    OP_CHECK_NULL_WITH_CONTEXT(context, currentWorkspace);
    currentWorkspace[0] = WS_SYS_SIZE;
    return ge::GRAPH_SUCCESS;
}

static int64_t NumelOfShape(const gert::Shape& shape)
{
    const int64_t dimNum = static_cast<int64_t>(shape.GetDimNum());
    if (dimNum == 0) {
        return 1;
    }
    int64_t numel = 1;
    for (int64_t d = 0; d < dimNum; ++d) {
        const int64_t v = shape.GetDim(static_cast<size_t>(d));
        if (v < 0) {
            return -1;
        }
        numel *= v;
    }
    return numel;
}

static int64_t MapMode(const char* mode)
{
    if (mode == nullptr || mode[0] == '\0') {
        return 2;   // def.cpp 默认 "reflect"
    }
    if (strcmp(mode, "constant") == 0) {
        return 0;
    }
    if (strcmp(mode, "edge") == 0 || strcmp(mode, "replicate") == 0) {
        return 1;
    }
    if (strcmp(mode, "reflect") == 0) {
        return 2;
    }
    if (strcmp(mode, "symmetric") == 0) {
        return 3;
    }
    if (strcmp(mode, "circular") == 0) {
        return 4;
    }
    return -1;
}

static int64_t CalcUbFactor(uint64_t ubSize, int64_t elemSize)
{
    int64_t alignUnit = 32 / elemSize;
    if (alignUnit < 1) {
        alignUnit = 1;
    }
    int64_t avail = static_cast<int64_t>(ubSize) - TILING_SAFE_BYTES - TILING_PAD_BYTES;
    if (avail < 64) {
        avail = 64;
    }
    int64_t ubFactor = (avail / elemSize) / alignUnit * alignUnit;
    if (ubFactor < alignUnit) {
        ubFactor = alignUnit;
    }
    if (ubFactor > PADV3_UB_MAX) {
        ubFactor = PADV3_UB_MAX;
    }
    return ubFactor;
}

static ge::graphStatus PadV3GradTilingFunc(gert::TilingContext* context)
{
    uint64_t ubSize = 0;
    int64_t coreNum = 0;
    OP_CHECK_IF(
        GetPlatformInfo(context, ubSize, coreNum) != ge::GRAPH_SUCCESS,
        OP_LOGE(context, "GetPlatformInfo error"),
        return ge::GRAPH_FAILED);
    OP_CHECK_IF(
        GetWorkspaceSize(context) != ge::GRAPH_SUCCESS,
        OP_LOGE(context, "GetWorkspaceSize error"),
        return ge::GRAPH_FAILED);

    PadV3GradTilingData* tiling = context->GetTilingData<PadV3GradTilingData>();
    OP_CHECK_NULL_WITH_CONTEXT(context, tiling);

    /* ---------- 1. x shape / dtype ---------- */
    const gert::StorageShape* xs = context->GetInputShape(0);
    OP_CHECK_NULL_WITH_CONTEXT(context, xs);
    const gert::Shape& xShape = xs->GetStorageShape();
    const int64_t rank = static_cast<int64_t>(xShape.GetDimNum());
    OP_CHECK_IF(rank > PADV3GRAD_MAX_RANK, OP_LOGE(context, "x rank too large"), return ge::GRAPH_FAILED);

    int64_t xNumel = 1;
    for (int64_t d = 0; d < rank; ++d) {
        const int64_t N = xShape.GetDim(static_cast<size_t>(d));
        OP_CHECK_IF(N < 0, OP_LOGE(context, "x has unknown dim"), return ge::GRAPH_FAILED);
        tiling->xDims[d] = N;
        tiling->outDims[d] = 0;
        if (N > 0) {
            xNumel *= N;
            OP_CHECK_IF(xNumel > PADV3_XNUMEL_MAX, OP_LOGE(context, "x numel too large"),
                        return ge::GRAPH_FAILED);
        }
    }

    const gert::CompileTimeTensorDesc* xDesc = context->GetInputDesc(0);
    OP_CHECK_NULL_WITH_CONTEXT(context, xDesc);
    const ge::DataType dtX = xDesc->GetDataType();
    OP_CHECK_IF(dtX != ge::DT_FLOAT16 && dtX != ge::DT_FLOAT,
                OP_LOGE(context, "x dtype must be fp16/fp32"), return ge::GRAPH_FAILED);

    const int64_t elemSize = (dtX == ge::DT_FLOAT16) ? 2 : 4;
    const int64_t alignElem = (32 / elemSize > 0) ? (32 / elemSize) : 1;   /* 32B / 元素 */

    /* ---------- 2. paddings shape / dtype（只校验元素数，不读值） ---------- */
    const gert::StorageShape* ps = context->GetInputShape(1);
    OP_CHECK_NULL_WITH_CONTEXT(context, ps);
    const gert::Shape& pShape = ps->GetStorageShape();
    int64_t pNum = 0;
    if (pShape.GetDimNum() == 0) {
        /* rank0 的 [] 视为空 paddings；rank>0 时标量 paddings 非法（1 != 2R） */
        pNum = (rank == 0) ? 0 : 1;
    } else {
        pNum = NumelOfShape(pShape);
        OP_CHECK_IF(pNum < 0, OP_LOGE(context, "paddings has unknown dim"), return ge::GRAPH_FAILED);
    }
    OP_CHECK_IF(pNum != 2 * rank, OP_LOGE(context, "paddings numel must be 2*rank"),
                return ge::GRAPH_FAILED);

    const gert::CompileTimeTensorDesc* pDesc = context->GetInputDesc(1);
    OP_CHECK_NULL_WITH_CONTEXT(context, pDesc);
    const ge::DataType dtP = pDesc->GetDataType();
    OP_CHECK_IF(dtP != ge::DT_INT32 && dtP != ge::DT_INT64,
                OP_LOGE(context, "paddings dtype must be int32/int64"), return ge::GRAPH_FAILED);

    /* ---------- 3. attr（null -> def.cpp 默认值） ---------- */
    int64_t mode = 2;
    int64_t contiguous = 1;
    const gert::RuntimeAttrs* attrs = context->GetAttrs();
    if (attrs != nullptr) {
        const char* modeStr = attrs->GetStr(0);
        mode = MapMode(modeStr);
        OP_CHECK_IF(mode < 0, OP_LOGE(context, "unsupported mode"), return ge::GRAPH_FAILED);
        const bool* pc = attrs->GetAttrPointer<bool>(1);
        if (pc != nullptr) {
            contiguous = (*pc) ? 1 : 0;
        }
    }

    /* ---------- 4. 输出 shape（可选；默认关闭，见 PADV3_TILING_USE_OUT_SHAPE） ---------- */
    bool outKnown = false;
    int64_t totalOut = 0;
#if PADV3_TILING_USE_OUT_SHAPE
    const gert::StorageShape* so = context->GetOutputShape(0);
    if (so != nullptr) {
        const gert::Shape& outShape = so->GetStorageShape();
        if (static_cast<int64_t>(outShape.GetDimNum()) == rank) {
            outKnown = true;
            totalOut = 1;
            for (int64_t d = 0; d < rank; ++d) {
                const int64_t v = outShape.GetDim(static_cast<size_t>(d));
                if (v < 0) {
                    outKnown = false;
                    break;
                }
                tiling->outDims[d] = v;
                totalOut *= v;   /* 任一维为 0 -> totalOut=0（空输出） */
            }
            if (outKnown && totalOut > PADV3_XNUMEL_MAX) {
                outKnown = false;
            }
        }
    }
#endif
    if (!outKnown) {
        for (int64_t d = 0; d < rank && d < PADV3GRAD_MAX_RANK; ++d) {
            tiling->outDims[d] = 0;
        }
    }

    /* ---------- 5. 分核：按工作量 x.numel ---------- */
    int64_t usedCore = CeilDivI(xNumel, MIN_WORK_PER_CORE);
    if (usedCore < 1) {
        usedCore = 1;
    }
    if (usedCore > coreNum) {
        usedCore = coreNum;
    }
    int64_t blockFactor = 0;
    if (outKnown && totalOut > 0) {
        /* 每核输出起点必须 32B 字节对齐：blockFactor 向上对齐到 32/sizeof(T) 个元素 */
        blockFactor = CeilDivI(totalOut, usedCore);
        blockFactor = ((blockFactor + alignElem - 1) / alignElem) * alignElem;
        if (blockFactor < alignElem) {
            blockFactor = alignElem;
        }
        const int64_t coresNeeded = CeilDivI(totalOut, blockFactor);
        if (coresNeeded >= 1 && coresNeeded < usedCore) {
            usedCore = coresNeeded;
        }
    }

    /* ---------- 6. ubFactor ---------- */
    const int64_t ubFactor = CalcUbFactor(ubSize, elemSize);

    /* ---------- 7. 写 tiling ---------- */
    tiling->totalNum = (outKnown && totalOut > 0) ? totalOut : 0;
    tiling->blockFactor = blockFactor;
    tiling->ubFactor = ubFactor;
    tiling->rank = rank;
    tiling->mode = mode;
    tiling->paddingsContiguous = contiguous;
    tiling->paddingsInt64 = (dtP == ge::DT_INT64) ? 1 : 0;
    tiling->coreNum = usedCore;
    tiling->dtypeCode = (dtX == ge::DT_FLOAT16) ? 0 : 1;

    context->SetBlockDim(static_cast<uint32_t>(usedCore));

    uint64_t tilingKey;
    if (dtX == ge::DT_FLOAT16) {
        tilingKey = GET_TPL_TILING_KEY(PADV3GRAD_TPL_SCH_MODE_0);
    } else {
        tilingKey = GET_TPL_TILING_KEY(PADV3GRAD_TPL_SCH_MODE_1);
    }
    context->SetTilingKey(tilingKey);
    return ge::GRAPH_SUCCESS;
}

static ge::graphStatus TilingParseForPadV3Grad([[maybe_unused]] gert::TilingParseContext* context)
{
    return ge::GRAPH_SUCCESS;
}

struct PadV3GradCompileInfo {};

IMPL_OP_OPTILING(PadV3Grad).Tiling(PadV3GradTilingFunc).TilingParse<PadV3GradCompileInfo>(TilingParseForPadV3Grad);

} // namespace optiling
