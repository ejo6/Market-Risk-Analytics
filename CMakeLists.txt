cmake_minimum_required(VERSION 3.20)
project(mra VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(MRA_BUILD_PYTHON "Build the pybind11 module (mra._core)" ON)

# Core C++ library: the analytics engine shared by the CLI, API, and Python
add_library(mra_core
    cpp/src/version.cpp
)
target_include_directories(mra_core PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/cpp/include>
)

if(MRA_BUILD_PYTHON)
    find_package(Python 3.10 REQUIRED COMPONENTS Interpreter Development.Module)
    find_package(pybind11 CONFIG REQUIRED)

    pybind11_add_module(_core bindings/module.cpp)
    target_link_libraries(_core PRIVATE mra_core)

    # scikit-build-core installs into the wheel root; put _core next to mra/__init__.py
    install(TARGETS _core LIBRARY DESTINATION mra)
endif()
