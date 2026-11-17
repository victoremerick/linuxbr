cmake_minimum_required(VERSION 3.22)
project(LinuxBRInstallation LANGUAGES CXX)

find_package(Qt6 REQUIRED COMPONENTS Widgets)
find_library(CALAMARES_CORE NAMES calamares PATHS "${CALAMARES_LIBDIR}" NO_DEFAULT_PATH REQUIRED)
find_library(CALAMARES_UI NAMES calamaresui PATHS "${CALAMARES_LIBDIR}" NO_DEFAULT_PATH REQUIRED)

add_library(calamares_viewmodule_linuxbr_installation MODULE Installation.cpp Preflight.cpp)
set_target_properties(calamares_viewmodule_linuxbr_installation PROPERTIES
    AUTOMOC ON
    BUILD_WITH_INSTALL_RPATH ON
    INSTALL_RPATH ""
)
target_compile_features(calamares_viewmodule_linuxbr_installation PRIVATE cxx_std_17)
target_include_directories(calamares_viewmodule_linuxbr_installation PRIVATE "${CALAMARES_HEADERS}")
target_link_libraries(calamares_viewmodule_linuxbr_installation PRIVATE Qt6::Widgets "${CALAMARES_UI}" "${CALAMARES_CORE}")
