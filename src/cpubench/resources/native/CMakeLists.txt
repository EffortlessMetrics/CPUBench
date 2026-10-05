cmake_minimum_required(VERSION 3.20)
project(cpubench_native C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_executable(cpubench-native cpubench_native.c)

if(MSVC)
  target_compile_options(cpubench-native PRIVATE /W4 /O2)
else()
  target_compile_options(cpubench-native PRIVATE -Wall -Wextra -Wpedantic -O3)
  if(APPLE)
    target_compile_definitions(cpubench-native PRIVATE _DARWIN_C_SOURCE)
  else()
    target_compile_definitions(cpubench-native PRIVATE _POSIX_C_SOURCE=200809L)
  endif()
endif()
