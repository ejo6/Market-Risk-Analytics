cmake_minimum_required(VERSION 3.20)
project(mra VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)  # lets clangd find Eigen and mra headers

option(MRA_BUILD_PYTHON "Build the pybind11 module (mra._core)" ON)
option(MRA_BUILD_TESTS "Build the C++ tests (Catch2)" OFF)

include(cmake/dependencies.cmake)

# Core C++ library: the analytics engine shared by the CLI, API, and Python.
# Pure numerics: no I/O, no symbols, no DuckDB. Inputs are Eigen matrices.
add_library(mra_core
    cpp/src/version.cpp
    cpp/src/models/registry.cpp
    cpp/src/models/covariance.cpp
    cpp/src/models/tail_risk.cpp
    cpp/src/portfolio.cpp
    cpp/src/drawdown.cpp
    cpp/src/normal.cpp
)
target_include_directories(mra_core PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/cpp/include>
)
target_link_libraries(mra_core PUBLIC Eigen3::Eigen)
target_compile_options(mra_core PRIVATE -Wall -Wextra -Wpedantic)

if(MRA_BUILD_PYTHON)
    find_package(Python 3.10 REQUIRED COMPONENTS Interpreter Development.Module)
    find_package(pybind11 CONFIG REQUIRED)

    pybind11_add_module(_core bindings/module.cpp)
    target_link_libraries(_core PRIVATE mra_core)

    # scikit-build-core installs into the wheel root; put _core next to mra/__init__.py
    install(TARGETS _core LIBRARY DESTINATION mra)
endif()

if(MRA_BUILD_TESTS)
    enable_testing()
    add_executable(mra_tests
        tests/cpp/test_registry.cpp
        tests/cpp/test_covariance.cpp
        tests/cpp/test_tail_risk.cpp
        tests/cpp/test_portfolio.cpp
        tests/cpp/test_normal.cpp
    )
    target_link_libraries(mra_tests PRIVATE mra_core Catch2::Catch2WithMain)
    include(Catch)
    catch_discover_tests(mra_tests)
endif()
