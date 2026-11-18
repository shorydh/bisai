include_guard(GLOBAL)
# The host test compiles the tiling context faker directly. Its inputs do
# not use the JSON parser from the legacy tiling_case_executor.cpp.
set(GTEST_SOURCE_DIR "$ENV{GTEST_SOURCE_DIR}" CACHE PATH "GoogleTest source directory")
if(NOT EXISTS "${GTEST_SOURCE_DIR}/CMakeLists.txt")
    message(FATAL_ERROR "Set GTEST_SOURCE_DIR to local GoogleTest sources")
endif()
add_compile_definitions(_GLIBCXX_USE_CXX11_ABI=0)
add_subdirectory(${GTEST_SOURCE_DIR} ${CMAKE_BINARY_DIR}/gtest EXCLUDE_FROM_ALL)
add_library(intf_llt_pub_asan_cxx17 INTERFACE)
target_link_libraries(intf_llt_pub_asan_cxx17 INTERFACE gtest)
