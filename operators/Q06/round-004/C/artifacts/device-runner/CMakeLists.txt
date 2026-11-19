cmake_minimum_required(VERSION 3.16)
project(pad_v3_grad_edge_case CXX)
set(CMAKE_CXX_STANDARD 17)

set(PAD_V3_GRAD_PROJECT_DIR "" CACHE PATH
    "Explicit PadV3Grad P/F project used by this runner")
include("${CMAKE_CURRENT_SOURCE_DIR}/vendor_paths.cmake")

add_executable(edge_case_runner edge_case_runner.cpp)
target_include_directories(edge_case_runner PRIVATE
    "${pad_v3_grad_vendor_root}/op_api/include"
    "${pad_v3_grad_project_real}/examples"
    "$ENV{ASCEND_HOME_PATH}/include")
target_link_libraries(edge_case_runner PRIVATE
    "${pad_v3_grad_library}"
    "$ENV{ASCEND_HOME_PATH}/lib64/libascendcl.so"
    "$ENV{ASCEND_HOME_PATH}/lib64/libnnopbase.so"
    dl)
