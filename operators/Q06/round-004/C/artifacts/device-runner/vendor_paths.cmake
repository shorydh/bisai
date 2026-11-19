if(NOT DEFINED PAD_V3_GRAD_PROJECT_DIR OR PAD_V3_GRAD_PROJECT_DIR STREQUAL "")
    message(FATAL_ERROR "PAD_V3_GRAD_PROJECT_DIR must name the explicit P/F project")
endif()
if(NOT IS_ABSOLUTE "${PAD_V3_GRAD_PROJECT_DIR}")
    message(FATAL_ERROR "PAD_V3_GRAD_PROJECT_DIR must be absolute: ${PAD_V3_GRAD_PROJECT_DIR}")
endif()

get_filename_component(pad_v3_grad_project_real "${PAD_V3_GRAD_PROJECT_DIR}" REALPATH)
set(PAD_V3_GRAD_PROJECT_DIR "${pad_v3_grad_project_real}" CACHE PATH
    "Explicit PadV3Grad project used for compilation and runtime loading" FORCE)

set(pad_v3_grad_vendor_root
    "${pad_v3_grad_project_real}/build/packages/vendors/pad_v3_grad_custom")
set(PAD_V3_GRAD_RESOLVED_VENDOR_ROOT "${pad_v3_grad_vendor_root}" CACHE INTERNAL
    "Vendor root resolved from PAD_V3_GRAD_PROJECT_DIR")
set(pad_v3_grad_header "${pad_v3_grad_vendor_root}/op_api/include/aclnn_pad_v3_grad.h")
set(pad_v3_grad_library "${pad_v3_grad_vendor_root}/op_api/lib/libcust_opapi.so")
set(pad_v3_grad_version "${pad_v3_grad_vendor_root}/version.info")

foreach(path IN ITEMS
        "${pad_v3_grad_header}"
        "${pad_v3_grad_library}"
        "${pad_v3_grad_version}")
    if(NOT EXISTS "${path}")
        message(FATAL_ERROR "Selected vendor is incomplete; missing ${path}")
    endif()
endforeach()

file(SHA256 "${pad_v3_grad_header}" pad_v3_grad_header_sha256)
file(SHA256 "${pad_v3_grad_library}" pad_v3_grad_library_sha256)
file(SHA256 "${pad_v3_grad_version}" pad_v3_grad_version_sha256)

function(pad_v3_grad_json_escape input output)
    string(REPLACE "\\" "\\\\" escaped "${input}")
    string(REPLACE "\"" "\\\"" escaped "${escaped}")
    string(REPLACE "\n" "\\n" escaped "${escaped}")
    set(${output} "${escaped}" PARENT_SCOPE)
endfunction()

pad_v3_grad_json_escape("${pad_v3_grad_project_real}" project_json)
pad_v3_grad_json_escape("${pad_v3_grad_vendor_root}" vendor_json)
pad_v3_grad_json_escape("${pad_v3_grad_header}" header_json)
pad_v3_grad_json_escape("${pad_v3_grad_library}" library_json)
pad_v3_grad_json_escape("${pad_v3_grad_version}" version_json)

if(NOT DEFINED PAD_V3_GRAD_CONFIG_OUT)
    set(PAD_V3_GRAD_CONFIG_OUT "${CMAKE_BINARY_DIR}/vendor-config.json")
endif()
file(WRITE "${PAD_V3_GRAD_CONFIG_OUT}"
"{
  \"schema_version\": 1,
  \"requested_project_dir\": \"${project_json}\",
  \"resolved_project_dir\": \"${project_json}\",
  \"vendor_root\": \"${vendor_json}\",
  \"op_api_header\": \"${header_json}\",
  \"op_api_library\": \"${library_json}\",
  \"header_sha256\": \"${pad_v3_grad_header_sha256}\",
  \"library_sha256\": \"${pad_v3_grad_library_sha256}\",
  \"version_info\": \"${version_json}\",
  \"version_info_sha256\": \"${pad_v3_grad_version_sha256}\"
}
")
