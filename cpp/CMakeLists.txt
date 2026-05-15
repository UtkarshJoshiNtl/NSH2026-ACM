cmake_minimum_required(VERSION 3.18)
project(physics_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)

# ── Optional CUDA support ─────────────────────────────────────────────────────
option(USE_CUDA "Enable CUDA GPU acceleration (requires nvcc + CUDA Toolkit)" ON)

if(USE_CUDA)
    include(CheckLanguage)
    check_language(CUDA)
    if(CMAKE_CUDA_COMPILER)
        enable_language(CUDA)
        set(CMAKE_CUDA_STANDARD 17)
        # RTX 2050 = Turing = sm_75
        # Also include sm_70 (Volta) and sm_86 (Ampere) for broader compatibility
        set(CMAKE_CUDA_ARCHITECTURES 75)
        message(STATUS "CUDA found: ${CMAKE_CUDA_COMPILER} — building GPU kernels (sm_75)")
        set(HAS_CUDA TRUE)
    else()
        message(WARNING "USE_CUDA=ON but nvcc not found — building CPU-only")
        set(HAS_CUDA FALSE)
    endif()
else()
    set(HAS_CUDA FALSE)
    message(STATUS "USE_CUDA=OFF — building CPU-only engine")
endif()

# ── Optional OpenMP (CPU parallelism for batch propagation) ───────────────────
find_package(OpenMP)

# ── Python + pybind11 ─────────────────────────────────────────────────────────
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 REQUIRED)

# ── Source files ──────────────────────────────────────────────────────────────
set(CPP_SOURCES
    propagator.cpp
    conjunction.cpp
)

if(HAS_CUDA)
    list(APPEND CPP_SOURCES
        cuda_propagator.cu
        cuda_conjunction.cu
    )
    pybind11_add_module(physics_engine ${CPP_SOURCES})
    target_compile_definitions(physics_engine PRIVATE USE_CUDA)
    set_target_properties(physics_engine PROPERTIES
        CUDA_SEPARABLE_COMPILATION OFF
    )
else()
    pybind11_add_module(physics_engine ${CPP_SOURCES})
endif()

target_include_directories(physics_engine PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

# ── OpenMP linkage ────────────────────────────────────────────────────────────
if(OpenMP_CXX_FOUND)
    target_link_libraries(physics_engine PRIVATE OpenMP::OpenMP_CXX)
    target_compile_definitions(physics_engine PRIVATE _OPENMP)
    message(STATUS "OpenMP enabled for CPU batch parallelism")
endif()

# ── Optimization flags ────────────────────────────────────────────────────────
if(MSVC)
    target_compile_options(physics_engine PRIVATE /O2 /fp:fast)
else()
    target_compile_options(physics_engine PRIVATE
        -O3 -march=native -ffast-math
        -fno-omit-frame-pointer          # needed by perf/gprof profilers
        -fopt-info-vec                   # report auto-vectorised loops to stdout at build time
    )
    if(HAS_CUDA)
        target_compile_options(physics_engine PRIVATE
            $<$<COMPILE_LANGUAGE:CUDA>:-O3 --use_fast_math -lineinfo>
        )
    endif()
endif()

message(STATUS "Build summary:")
message(STATUS "  CUDA acceleration : ${HAS_CUDA}")
message(STATUS "  OpenMP            : ${OpenMP_CXX_FOUND}")
message(STATUS "  Install prefix    : ${CMAKE_INSTALL_PREFIX}")
