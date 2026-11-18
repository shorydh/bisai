#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "pad_v3_grad_tiling.h"
#include "../../../op_kernel/pad_v3_grad.cpp"

namespace {
std::string RequiredDirectory(const char* name)
{
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') throw std::runtime_error(std::string("Missing ") + name);
    return value;
}

template<class T>
std::vector<T> ReadExact(const std::string& path, size_t count)
{
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    const auto bytes = static_cast<std::streamsize>(count * sizeof(T));
    if (!file || file.tellg() != bytes) throw std::runtime_error("Wrong size or missing: " + path);
    std::vector<T> values(count);
    file.seekg(0);
    if (!file.read(reinterpret_cast<char*>(values.data()), bytes)) throw std::runtime_error("Read failed: " + path);
    return values;
}

struct GmDeleter {
    void operator()(uint8_t* ptr) const { AscendC::GmFree(ptr); }
};

using GmBuffer = std::unique_ptr<uint8_t, GmDeleter>;

GmBuffer MakeGm(const void* initial, size_t bytes)
{
    const size_t aligned = (bytes + 31) / 32 * 32;
    GmBuffer buffer(reinterpret_cast<uint8_t*>(AscendC::GmAlloc(aligned)));
    if (!buffer) throw std::runtime_error("GmAlloc failed");
    std::memset(buffer.get(), 0, aligned);
    if (initial) std::memcpy(buffer.get(), initial, bytes);
    return buffer;
}

std::vector<float> RunCompactFp32(const std::string& fixture, const std::vector<float>& input,
                                  const std::vector<int32_t>& pads, size_t outputCount)
{
    const std::string prefix = RequiredDirectory("PADV3GRAD_UT_FIXTURE_DIR") + "/" + fixture;
    std::ifstream dispatch(prefix + ".dispatch");
    uint64_t key = 0;
    uint32_t blocks = 0;
    if (!(dispatch >> key >> blocks) || key != 3 || blocks == 0 || blocks > outputCount) {
        throw std::runtime_error("Invalid compact FP32 dispatch: " + prefix);
    }
    const auto wire = ReadExact<PadV3GradSmallTilingData>(prefix + ".tiling", 1);
    const auto& data = wire[0];
    if (data.totalInput != static_cast<int64_t>(input.size()) ||
        data.totalOutput != static_cast<int64_t>(outputCount) ||
        data.rank < 1 || data.rank > PAD_V3_GRAD_SMALL_RANK ||
        static_cast<size_t>(data.rank) * 2 != pads.size() || data.paddingsDtype != 0 ||
        data.blockFactor <= 0 || (data.totalOutput - 1) / data.blockFactor + 1 != blocks) {
        throw std::runtime_error("Host tiling dimensions do not fit the test buffers: " + prefix);
    }
    std::vector<float> output(outputCount, std::numeric_limits<float>::quiet_NaN());
    auto x = MakeGm(input.data(), input.size() * sizeof(float));
    auto p = MakeGm(pads.data(), pads.size() * sizeof(int32_t));
    auto y = MakeGm(output.data(), output.size() * sizeof(float));
    auto tiling = MakeGm(&data, sizeof(data));
    auto workspace = MakeGm(nullptr, 32);
    AscendC::SetKernelMode(KernelMode::AIV_MODE);
    ICPU_SET_TILING_KEY(key);
    ICPU_RUN_KF((pad_v3_grad<3>), blocks, x.get(), p.get(), y.get(), workspace.get(), tiling.get());
    std::memcpy(output.data(), y.get(), output.size() * sizeof(float));
    return output;
}

TEST(PadV3GradKernelTest, PublicReflectSample)
{
    const std::string sample = RequiredDirectory("SAMPLE_DIR");
    const auto x = ReadExact<float>(sample + "/input/x.bin", 64);
    const auto paddings = ReadExact<int32_t>(sample + "/input/paddings.bin", 8);
    const auto golden = ReadExact<float>(sample + "/golden/y.bin", 16);
    const auto actual = RunCompactFp32("reflect", x, paddings, golden.size());
    std::ofstream file(sample + "/output/y.bin", std::ios::binary | std::ios::trunc);
    ASSERT_TRUE(file.write(reinterpret_cast<const char*>(actual.data()), actual.size() * sizeof(float)));
    file.close();
    ASSERT_TRUE(file);
    for (size_t i = 0; i < golden.size(); ++i) {
        EXPECT_NEAR(static_cast<double>(actual[i]), static_cast<double>(golden[i]),
                    1e-4 + 1e-4 * std::abs(static_cast<double>(golden[i]))) << "output index " << i;
    }
}

TEST(PadV3GradKernelTest, EdgeAccumulatesRepeatedContributions)
{
    // With left pad 2 and right pad 1, the first three samples map to
    // output 0 and the last two map to output 2. All sums are exact in FP32.
    const auto actual = RunCompactFp32("edge", {1, 2, 3, 4, 5, 6}, {2, 1}, 3);
    EXPECT_EQ(actual, (std::vector<float>{6, 4, 11}));
}
}  // namespace
