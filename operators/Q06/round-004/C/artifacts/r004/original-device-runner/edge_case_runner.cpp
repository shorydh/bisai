#include "sample_support.h"
#include "aclnn_pad_v3_grad.h"

#include <memory>
#include <string>
#include <vector>

int main(int argc, char** argv)
{
    try {
        if (argc != 5) {
            std::cerr << "usage: edge_case_runner <case_dir> <device_id> <int32|int64> <contiguous|split>" << std::endl;
            return 1;
        }
        const std::string root = argv[1];
        const int device = std::stoi(argv[2]);
        const bool useInt64 = std::string(argv[3]) == "int64";
        const bool contiguous = std::string(argv[4]) == "contiguous";

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
