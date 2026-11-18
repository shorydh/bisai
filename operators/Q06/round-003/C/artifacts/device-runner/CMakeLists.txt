cmake_minimum_required(VERSION 3.16)
project(pad_v3_grad_edge_case CXX)
set(CMAKE_CXX_STANDARD 17)

set(PROJECT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../source/P")
set(OPP_ROOT "${PROJECT_DIR}/build/packages/vendors/pad_v3_grad_custom")
find_path(OP_INCLUDE aclnn_pad_v3_grad.h PATHS "${OPP_ROOT}/op_api/include" NO_DEFAULT_PATH REQUIRED)
find_library(OP_LIBRARY cust_opapi PATHS "${OPP_ROOT}/op_api/lib" NO_DEFAULT_PATH REQUIRED)

add_executable(edge_case_runner edge_case_runner.cpp)
target_include_directories(edge_case_runner PRIVATE
    "${OP_INCLUDE}"
    "${PROJECT_DIR}/examples"
    "$ENV{ASCEND_HOME_PATH}/include")
target_link_libraries(edge_case_runner PRIVATE
    "${OP_LIBRARY}"
    "$ENV{ASCEND_HOME_PATH}/lib64/libascendcl.so"
    "$ENV{ASCEND_HOME_PATH}/lib64/libnnopbase.so")
