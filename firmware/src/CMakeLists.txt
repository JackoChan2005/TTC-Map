FILE(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.*)

idf_component_register(
    SRCS ${app_sources}
    INCLUDE_DIRS "../include"
    REQUIRES esp_http_client esp_wifi esp_event esp_netif nvs_flash esp_driver_gpio
)
