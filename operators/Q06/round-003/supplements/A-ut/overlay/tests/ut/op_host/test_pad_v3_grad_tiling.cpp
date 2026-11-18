#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <string>
#include <vector>

#include <gtest/gtest.h>
#include "base/registry/op_impl_space_registry_v2.h"
#include "platform/platform_infos_def.h"
#include "tiling_context_faker.h"
#include "pad_v3_grad_tiling_data.h"
#include "pad_v3_grad_tiling_key.h"

namespace {
// These resources describe the test platform passed to the real host operator.
// Model A2 core counts separately: 20 Cube cores and 40 Vector cores.
void SetTestPlatform(fe::PlatFormInfos& platform)
{
    platform.Init();
    std::map<std::string, std::string> soc{{"ai_core_cnt", "20"}, {"cube_core_cnt", "20"},
                                          {"vector_core_cnt", "40"}, {"core_type_list", "AICore"}};
    std::map<std::string, std::string> memory{{"ub_size", "196608"}};
    std::map<std::string, std::string> version{{"NpuArch", "2201"}, {"Short_SoC_version", "Ascend910B"}};
    platform.SetPlatformRes("SoCInfo", soc);
    platform.SetPlatformRes("AICoreSpec", memory);
    platform.SetPlatformRes("version", version);
    platform.SetCoreNumByCoreType("AICore");
}

struct TestCase {
    const char* mode;
    gert::StorageShape x;
    gert::StorageShape padsShape;
    gert::StorageShape y;
    std::vector<int32_t> pads;
    int64_t expectedMode;
    int64_t expectedInput;
    int64_t expectedOutput;
    int64_t expectedBlockFactor;
    uint32_t expectedBlocks;
    std::vector<int64_t> expectedStride;
};

void CheckAndExport(TestCase c)
{
    gert::StorageFormat format(ge::FORMAT_ND, ge::FORMAT_ND, gert::ExpandDimsType());
    gert::Tensor x(c.x, format, gert::TensorPlacement::kOnHost, ge::DT_FLOAT, nullptr);
    gert::Tensor pads(c.padsShape, format, gert::TensorPlacement::kOnHost, ge::DT_INT32, c.pads.data());
    gert::Tensor y(c.y, format, gert::TensorPlacement::kOnHost, ge::DT_FLOAT, nullptr);
    std::vector<gert::Tensor*> inputs{&x, &pads};
    std::vector<gert::Tensor*> outputs{&y};
    fe::PlatFormInfos platform;
    SetTestPlatform(platform);
    auto wire = gert::TilingData::CreateCap(sizeof(PadV3GradSmallTilingData));
    auto workspace = gert::ContinuousVector::Create<size_t>(1);
    struct CompileInfo {} compileInfo;
    gert::TilingContextFaker builder;
    builder.NodeIoNum(2, 1).SetOpType("PadV3Grad").InputTensors(inputs).OutputTensors(outputs)
        .Attr("mode", ge::AscendString(c.mode)).Attr("paddings_contiguous", true)
        .CompileInfo(&compileInfo).PlatformInfo(&platform).TilingData(wire.get())
        .Workspace(reinterpret_cast<gert::ContinuousVector*>(workspace.get()));
    auto holder = builder.Build();
    auto* context = holder.GetContext();
    ASSERT_NE(context, nullptr);
    auto registry = gert::DefaultOpImplSpaceRegistryV2::GetInstance().GetSpaceRegistry();
    ASSERT_NE(registry, nullptr);
    auto impl = registry->GetOpImpl("PadV3Grad");
    ASSERT_NE(impl, nullptr);
    ASSERT_NE(impl->tiling, nullptr);
    ASSERT_EQ(impl->tiling(context), ge::GRAPH_SUCCESS);

    ASSERT_EQ(context->GetTilingKey(), GET_TPL_TILING_KEY(PADV3GRAD_TPL_SCH_MODE_3));
    ASSERT_EQ(context->GetBlockDim(), c.expectedBlocks);
    ASSERT_EQ(context->GetWorkspaceNum(), 1U);
    ASSERT_EQ(context->GetWorkspaceSizes(1)[0], 0U);
    const auto* raw = context->GetRawTilingData();
    ASSERT_EQ(raw->GetDataSize(), sizeof(PadV3GradSmallTilingData));
    PadV3GradSmallTilingData data{};
    std::memcpy(&data, raw->GetData(), sizeof(data));
    ASSERT_EQ(data.totalInput, c.expectedInput);
    ASSERT_EQ(data.totalOutput, c.expectedOutput);
    ASSERT_EQ(data.blockFactor, c.expectedBlockFactor);
    ASSERT_EQ(data.ubFactor, 1024);
    ASSERT_EQ(data.rank, static_cast<int64_t>(c.expectedStride.size()));
    ASSERT_EQ(data.mode, c.expectedMode);
    ASSERT_EQ(data.paddingsDtype, 0);
    ASSERT_EQ(data.paddingsContiguous, 1);
    ASSERT_EQ(data.readPaddings, 1);
    for (int64_t axis = 0; axis < data.rank; ++axis) {
        ASSERT_EQ(data.inputShape[axis], c.x.GetStorageShape().GetDim(axis));
        ASSERT_EQ(data.outputShape[axis], c.y.GetStorageShape().GetDim(axis));
        ASSERT_EQ(data.inputStride[axis], c.expectedStride[axis]);
        ASSERT_EQ(data.padFront[axis], c.pads[2 * axis]);
    }

    // Standalone host UT needs no filesystem output. The integrated runner
    // passes a fresh per-build directory for the kernel simulator to consume.
    if (const char* directory = std::getenv("PADV3GRAD_UT_FIXTURE_DIR")) {
        const auto stem = std::filesystem::path(directory) / c.mode;
        std::ofstream blob(stem.string() + ".tiling", std::ios::binary);
        blob.write(reinterpret_cast<const char*>(raw->GetData()), raw->GetDataSize());
        blob.close();
        ASSERT_TRUE(blob.good());
        std::ofstream dispatch(stem.string() + ".dispatch");
        dispatch << context->GetTilingKey() << ' ' << context->GetBlockDim() << '\n';
        dispatch.close();
        ASSERT_TRUE(dispatch.good());
    }
}

TEST(PadV3GradHost, ReflectTwoBlockCompactFp32)
{
    CheckAndExport({"reflect", {{1, 1, 8, 8}, {1, 1, 8, 8}}, {{4, 2}, {4, 2}},
                    {{1, 1, 4, 4}, {1, 1, 4, 4}}, {0, 0, 0, 0, 2, 2, 2, 2},
                    2, 64, 16, 8, 2, {64, 64, 8, 1}});
}

TEST(PadV3GradHost, EdgeAsymmetricCompactFp32)
{
    CheckAndExport({"edge", {{6}, {6}}, {{1, 2}, {1, 2}}, {{3}, {3}}, {2, 1},
                    1, 6, 3, 8, 1, {1}});
}
} // namespace
