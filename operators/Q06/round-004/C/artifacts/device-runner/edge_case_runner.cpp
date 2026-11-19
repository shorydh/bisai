#include "sample_support.h"
#include "aclnn_pad_v3_grad.h"

#include <cstdlib>
#include <fstream>
#include <limits.h>
#include <memory>
#include <string>
#include <vector>

namespace {
std::string RealPath(const std::string& path)
{
    char resolved[PATH_MAX];
    return realpath(path.c_str(), resolved) == nullptr ? path : std::string(resolved);
}

std::string FindLoadedLibrary()
{
    std::ifstream maps("/proc/self/maps");
    std::string line;
    while (std::getline(maps, line)) {
        const std::size_t marker = line.find("libcust_opapi.so");
        if (marker == std::string::npos) {
            continue;
        }
        const std::size_t slash = line.find('/', marker);
        if (slash == std::string::npos) {
            continue;
        }
        std::string path = line.substr(slash);
        const std::string deleted = " (deleted)";
        if (path.size() >= deleted.size() &&
            path.compare(path.size() - deleted.size(), deleted.size(), deleted) == 0) {
            path.resize(path.size() - deleted.size());
        }
        return RealPath(path);
    }
    return {};
}

std::string JsonEscape(const std::string& value)
{
    std::string escaped;
    for (const char ch : value) {
        if (ch == '\\' || ch == '"') {
            escaped.push_back('\\');
        }
        escaped.push_back(ch);
    }
    return escaped;
}

void WriteInvocation(const std::string& root, const std::string& caseId, int device,
                     const std::string& dtype, const std::string& layout,
                     const std::string& expectedLibrary, const std::string& loadedLibrary)
{
    std::ofstream out(root + "/invocation.json", std::ios::binary);
    if (!out) {
        throw std::runtime_error("write: invocation.json");
    }
    out << "{\n"
        << "  \"case_id\": \"" << JsonEscape(caseId) << "\",\n"
        << "  \"execution_mode\": \"device\",\n"
        << "  \"device_id\": " << device << ",\n"
        << "  \"paddings_dtype\": \"" << JsonEscape(dtype) << "\",\n"
        << "  \"paddings_layout\": \"" << JsonEscape(layout) << "\",\n"
        << "  \"synchronized\": true,\n"
        << "  \"expected_library\": \"" << JsonEscape(expectedLibrary) << "\",\n"
        << "  \"loaded_library\": \"" << JsonEscape(loadedLibrary) << "\"\n"
        << "}\n";
}
} // namespace

int main(int argc, char** argv)
{
    try {
        if (argc != 6) {
            std::cerr << "usage: edge_case_runner <case_dir> <device_id> <int32|int64> "
                         "<contiguous|split> <case_id>" << std::endl;
            return 1;
        }
        const std::string root = argv[1];
        const int device = std::stoi(argv[2]);
        const std::string dtype = argv[3];
        const std::string layout = argv[4];
        const std::string caseId = argv[5];
        if ((dtype != "int32" && dtype != "int64") ||
            (layout != "contiguous" && layout != "split")) {
            throw std::runtime_error("dtype/layout must be int32|int64 and contiguous|split");
        }
        if (caseId != dtype + "-" + layout) {
            throw std::runtime_error("case_id does not match dtype/layout");
        }
        const bool useInt64 = dtype == "int64";
        const bool contiguous = layout == "contiguous";
        const char* expectedLibraryEnv = std::getenv("PAD_V3_GRAD_EXPECTED_LIBRARY");
        if (expectedLibraryEnv == nullptr || *expectedLibraryEnv == '\0') {
            throw std::runtime_error("PAD_V3_GRAD_EXPECTED_LIBRARY is required");
        }
        const std::string expectedLibrary = RealPath(expectedLibraryEnv);

        check(aclInit(nullptr));
        check(aclrtSetDevice(device));
        aclrtStream stream;
        check(aclrtCreateStream(&stream));
        {
            Tensor input0({1, 1, 1, 5}, ACL_FLOAT, 20, "x.bin", true, false, root);
            const std::vector<int64_t> padShape = contiguous
                ? std::vector<int64_t>{4, 2}
                : std::vector<int64_t>{2, 4};
            const size_t padBytes = useInt64 ? 8 * 8 : 4 * 8;
            std::unique_ptr<Tensor> input1;
            if (useInt64) {
                input1 = std::make_unique<Tensor>(
                    padShape, ACL_INT64, padBytes, "paddings.bin", true, false, root);
            } else {
                input1 = std::make_unique<Tensor>(
                    padShape, ACL_INT32, padBytes, "paddings.bin", true, false, root);
            }
            Tensor output0({1, 1, 1, 3}, ACL_FLOAT, 12, "y.bin", false, false, root);
            char attr0[] = "edge";
            bool attr1 = contiguous;
            uint64_t size = 0;
            aclOpExecutor* executor = nullptr;
            check(aclnnPadV3GradGetWorkspaceSize(
                input0.tensor,
                input1->tensor,
                attr0,
                attr1,
                output0.tensor,
                &size,
                &executor));
            void* workspace = nullptr;
            if (size) {
                check(aclrtMalloc(&workspace, size, ACL_MEM_MALLOC_HUGE_FIRST));
            }
            check(aclnnPadV3Grad(workspace, size, executor, stream));
            check(aclrtSynchronizeStream(stream));
            output0.save(root);
            const std::string loadedLibrary = FindLoadedLibrary();
            if (loadedLibrary.empty()) {
                throw std::runtime_error("libcust_opapi.so is not mapped in the runner");
            }
            if (loadedLibrary != expectedLibrary) {
                throw std::runtime_error(
                    "loaded vendor mismatch: expected " + expectedLibrary + ", got " + loadedLibrary);
            }
            WriteInvocation(root, caseId, device, dtype, layout, expectedLibrary, loadedLibrary);
            std::cout << "LOADED_LIBRARY=" << loadedLibrary << std::endl;
            if (workspace) {
                check(aclrtFree(workspace));
            }
        }
        check(aclrtDestroyStream(stream));
        check(aclrtResetDevice(device));
        check(aclFinalize());
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << std::endl;
        return 2;
    }
}
