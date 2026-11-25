# Third-party C++ dependencies.
#
# Each one is pinned to a release tarball and its SHA-256, so every build (laptop,
# CI, Docker) compiles against the same bytes. A system install is used first if
# present, which keeps rebuilds offline once you `brew install eigen`.

include(FetchContent)

# ---- Eigen (header-only linear algebra) -------------------------------------
find_package(Eigen3 3.4 QUIET NO_MODULE)
if(NOT TARGET Eigen3::Eigen)
    # SOURCE_SUBDIR points at a folder that does not exist, so FetchContent only
    # downloads and unpacks Eigen instead of running its (large) CMake project.
    # Eigen is headers only, so an include path is all we need.
    FetchContent_Declare(eigen
        URL https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.tar.gz
        URL_HASH SHA256=8586084f71f9bde545ee7fa6d00288b264a2b7ac3607b974e54d13e7162c1c72
        SOURCE_SUBDIR do-not-configure
    )
    FetchContent_MakeAvailable(eigen)
    add_library(Eigen3::Eigen INTERFACE IMPORTED GLOBAL)
    # SYSTEM: warnings inside Eigen's headers are not ours to fix.
    target_include_directories(Eigen3::Eigen SYSTEM INTERFACE ${eigen_SOURCE_DIR})
endif()

# ---- Catch2 (C++ tests only) ------------------------------------------------
if(MRA_BUILD_TESTS)
    find_package(Catch2 3 QUIET)
    if(NOT TARGET Catch2::Catch2WithMain)
        FetchContent_Declare(catch2
            URL https://github.com/catchorg/Catch2/archive/refs/tags/v3.7.1.tar.gz
            URL_HASH SHA256=c991b247a1a0d7bb9c39aa35faf0fe9e19764213f28ffba3109388e62ee0269c
        )
        FetchContent_MakeAvailable(catch2)
    endif()
endif()
