# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.16)
project(VolumeIdentityTests LANGUAGES C)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
find_package(Threads REQUIRED)
enable_testing()

add_custom_command(
    OUTPUT kernel_identity_under_test.inc kernel_identity_init.inc
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/generate_identity_fixture.py" "${CMAKE_CURRENT_BINARY_DIR}"
    DEPENDS generate_identity_fixture.py ../kernel.c ../custom.c
    VERBATIM
)
add_executable(kernel_identity_test kernel_identity_test.c kernel_identity_under_test.inc kernel_identity_init.inc)
set_target_properties(kernel_identity_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
target_include_directories(kernel_identity_test PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
target_link_libraries(kernel_identity_test PRIVATE Threads::Threads)
if(NOT WIN32)
    target_compile_definitions(kernel_identity_test PRIVATE _GNU_SOURCE)
endif()
if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang" AND NOT MSVC)
    target_compile_options(kernel_identity_test PRIVATE -fgnu89-inline)
endif()
foreach(test collisions failure names hash media concurrent tls allocation)
    add_test(NAME volume_identity_${test} COMMAND kernel_identity_test ${test})
endforeach()

if(WIN32)
    add_executable(volume_identity_probe volume_identity_probe.c)
    set_target_properties(volume_identity_probe PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
    target_compile_definitions(volume_identity_probe PRIVATE _WIN32_WINNT=0x0601)
    if(MINGW)
        target_link_options(volume_identity_probe PRIVATE -municode)
    endif()
endif()
