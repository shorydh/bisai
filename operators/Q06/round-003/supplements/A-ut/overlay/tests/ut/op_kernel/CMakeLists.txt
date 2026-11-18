set(OP_NAME pad_v3_grad)
set(UT_EXE ${OP_NAME}_op_kernel_ut)

message(STATUS "Building op_kernel UT for: ${OP_NAME}")

if(DEFINED ENV{ASCEND_HOME_PATH} AND EXISTS "$ENV{ASCEND_HOME_PATH}")
    set(CANN_HOME "$ENV{ASCEND_HOME_PATH}")
else()
    message(FATAL_ERROR "Cannot find CANN installation")
endif()

message(STATUS "Using CANN_HOME: ${CANN_HOME}")

set(SOC_VERSION "Ascend910B3" CACHE STRING "tikicpulib device model for CPU UT")

find_package(tikicpulib CONFIG REQUIRED HINTS
    "${CANN_HOME}/tools/tikicpulib/lib64/cmake" "${CANN_HOME}/tools/tikicpulib/lib/cmake")
if(NOT TARGET tikicpulib::${SOC_VERSION})
    message(FATAL_ERROR "No tikicpulib target for ${SOC_VERSION}")
endif()

set(OP_KERNEL_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../op_kernel)

set(UT_TEST_SRCS
    test_${OP_NAME}.cpp
)

set(UT_INCLUDE_DIRS
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${OP_KERNEL_DIR}
    ${UT_COMMON_INCLUDE_DIRS}
    ${CANN_HOME}/tools/tikicpulib/lib64/include
    ${CANN_HOME}/tools/tikicpulib/lib/include
    ${CANN_HOME}/compiler/ascendc/include/highlevel_api
    ${CANN_HOME}/compiler/ascendc/include/basic_api/impl
    ${CANN_HOME}/compiler/ascendc/include/basic_api
    ${CANN_HOME}/compiler/ascendc/include
    ${CANN_HOME}/compiler/ascendc/include/ascendc/host_api/tiling
    ${CANN_HOME}/compiler/ascendc/include/ascendc/host_api
    ${CANN_HOME}/compiler/ascendc/include/ascendc
    ${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/include
    ${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/asc/include/basic_api
    ${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/asc/include
    ${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/asc/include/interface
    ${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/asc/impl/basic_api
    ${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/asc
    ${CANN_HOME}/compiler/tikcpp/tikcfw
    ${CANN_HOME}/compiler/tikcpp/tikcfw/impl
    ${CANN_HOME}/compiler/tikcpp/tikcfw/interface
    ${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/include/graph
    ${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/ascendc/include/highlevel_api
    ${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/asc/impl/basic_api/utils
)

add_executable(${UT_EXE}
    ${UT_TEST_SRCS}
)

target_include_directories(${UT_EXE} PRIVATE
    ${UT_INCLUDE_DIRS}
)

target_compile_definitions(${UT_EXE} PRIVATE
    _GLIBCXX_USE_CXX11_ABI=0
    __aicore__=
    __NPU_TILING__=1
)

target_compile_options(${UT_EXE} PRIVATE
    -Wall
    -Wno-deprecated-declarations
    -Wno-unused-variable
    -Wno-unknown-pragmas
    -fno-access-control
    -std=c++17
)

target_link_directories(${UT_EXE} PRIVATE
    ${UT_COMMON_LIB_DIRS}
    ${CANN_HOME}/lib64
)

target_link_libraries(${UT_EXE} PRIVATE
    gtest_main
    gtest
    ${CANN_HOME}/lib64/libmmpa.so
    tikicpulib::${SOC_VERSION}
    dl
    pthread
)

set_target_properties(${UT_EXE} PROPERTIES
    INSTALL_RPATH "$ORIGIN;${CANN_HOME}/lib64;${CANN_HOME}/tools/tikicpulib/lib64;${CANN_HOME}/tools/tikicpulib/lib64/${SOC_VERSION};${CANN_HOME}/${CMAKE_SYSTEM_PROCESSOR}-linux/simulator/${SOC_VERSION}/lib"
    BUILD_WITH_INSTALL_RPATH TRUE
)

message(STATUS "  Kernel UT executable: ${UT_EXE}")
message(STATUS "  CANN Home: ${CANN_HOME}")
message(STATUS "  SOC Version: ${SOC_VERSION}")
