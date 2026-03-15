cmake_minimum_required(VERSION 3.12)
project(physics_engine)

set(CMAKE_CXX_STANDARD 17)

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 REQUIRED)

pybind11_add_module(physics_engine
    fuel.cpp
    propagator.cpp
    conjunction.cpp
    maneuver.cpp
)

target_include_directories(physics_engine PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
