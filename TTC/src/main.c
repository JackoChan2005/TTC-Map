#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#include "driver/gpio.h"
#include "esp_event.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include "board_config.h"
#include "secrets.h"

#ifndef TTC_POLL_INTERVAL_MS
#define TTC_POLL_INTERVAL_MS 5000U
#endif

#ifndef TTC_STALE_AFTER_MS
#define TTC_STALE_AFTER_MS (3U * 60U * 1000U)
#endif

#ifndef TTC_HTTP_TIMEOUT_MS
#define TTC_HTTP_TIMEOUT_MS 8000U
#endif

#ifndef TTC_VERBOSE_LED_LOG
#define TTC_VERBOSE_LED_LOG 0
#endif

#ifndef TTC_ENABLE_SHIFT_OUTPUT
#define TTC_ENABLE_SHIFT_OUTPUT 1
#endif

#ifndef TTC_WIFI_CONNECT_TIMEOUT_MS
#define TTC_WIFI_CONNECT_TIMEOUT_MS 12000U
#endif

#ifndef TTC_WIFI_RETRY_BASE_MS
#define TTC_WIFI_RETRY_BASE_MS 2000U
#endif

#ifndef TTC_WIFI_RETRY_MAX_MS
#define TTC_WIFI_RETRY_MAX_MS 30000U
#endif

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_DISCONNECTED_BIT BIT1

#define TTC_MAX_ETAG_LEN 80U
#define TTC_MAX_HEADER_LEN 96U
#define TTC_MAX_SOURCE_LEN 24U
#define TTC_MAX_FRAME_BYTES ((TTC_BOARD_LED_CAPACITY + 7U) / 8U)

#if defined(TTC_WIFI_FALLBACK_SSID) != defined(TTC_WIFI_FALLBACK_PASSWORD)
#error "Define both TTC_WIFI_FALLBACK_SSID and TTC_WIFI_FALLBACK_PASSWORD"
#endif

typedef struct {
    const char *ssid;
    const char *password;
} wifi_profile_t;

static const wifi_profile_t s_wifi_profiles[] = {
    {TTC_WIFI_SSID, TTC_WIFI_PASSWORD},
#ifdef TTC_WIFI_FALLBACK_SSID
    {TTC_WIFI_FALLBACK_SSID, TTC_WIFI_FALLBACK_PASSWORD},
#endif
};

static const char *TAG = "ttc-esp32";
static EventGroupHandle_t s_wifi_events;

typedef struct {
    uint8_t body[TTC_MAX_FRAME_BYTES];
    size_t body_len;
    bool body_overflow;
    char content_type[TTC_MAX_HEADER_LEN];
    char etag[TTC_MAX_ETAG_LEN];
    char led_count_text[16];
    char generated_at[TTC_MAX_HEADER_LEN];
    char source[TTC_MAX_SOURCE_LEN];
} http_response_t;

typedef struct {
    uint8_t bytes[TTC_MAX_FRAME_BYTES];
    size_t byte_len;
    uint16_t led_count;
    uint32_t crc32;
    TickType_t last_contact;
    char etag[TTC_MAX_ETAG_LEN];
    char generated_at[TTC_MAX_HEADER_LEN];
    char source[TTC_MAX_SOURCE_LEN];
    bool valid;
    bool stale;
} led_frame_t;

static led_frame_t s_frame;

static void copy_header(char *destination, size_t destination_size, const char *value)
{
    if (!destination || destination_size == 0) {
        return;
    }
    if (!value) {
        destination[0] = '\0';
        return;
    }
    snprintf(destination, destination_size, "%s", value);
}

static esp_err_t http_event_handler(esp_http_client_event_t *event)
{
    http_response_t *response = event->user_data;
    if (!response) {
        return ESP_OK;
    }

    switch (event->event_id) {
    case HTTP_EVENT_ON_HEADER:
        if (!event->header_key || !event->header_value) {
            break;
        }
        if (strcasecmp(event->header_key, "Content-Type") == 0) {
            copy_header(response->content_type, sizeof(response->content_type), event->header_value);
        } else if (strcasecmp(event->header_key, "ETag") == 0) {
            copy_header(response->etag, sizeof(response->etag), event->header_value);
        } else if (strcasecmp(event->header_key, "X-Led-Count") == 0) {
            copy_header(response->led_count_text, sizeof(response->led_count_text), event->header_value);
        } else if (strcasecmp(event->header_key, "X-Generated-At") == 0) {
            copy_header(response->generated_at, sizeof(response->generated_at), event->header_value);
        } else if (strcasecmp(event->header_key, "X-Source") == 0) {
            copy_header(response->source, sizeof(response->source), event->header_value);
        }
        break;

    case HTTP_EVENT_ON_DATA:
        if (event->data_len <= 0) {
            break;
        }
        if (response->body_len + (size_t)event->data_len > sizeof(response->body)) {
            response->body_overflow = true;
            break;
        }
        memcpy(response->body + response->body_len, event->data, (size_t)event->data_len);
        response->body_len += (size_t)event->data_len;
        break;

    default:
        break;
    }
    return ESP_OK;
}

static uint32_t crc32_frame(const uint8_t *data, size_t length)
{
    uint32_t crc = UINT32_MAX;
    for (size_t i = 0; i < length; ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit) {
            crc = (crc >> 1) ^ (0xEDB88320U & (-(int32_t)(crc & 1U)));
        }
    }
    return ~crc;
}

static bool parse_led_count(const char *text, uint16_t *count)
{
    if (!text || !*text || !count) {
        return false;
    }
    errno = 0;
    char *end = NULL;
    long parsed = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || parsed <= 0 ||
        parsed > TTC_BOARD_LED_CAPACITY) {
        return false;
    }
    *count = (uint16_t)parsed;
    return true;
}

static bool response_has_required_headers(const http_response_t *response, uint16_t *led_count)
{
    if (!response || response->body_overflow || !response->content_type[0] ||
        !response->etag[0] || !response->generated_at[0] || !response->source[0]) {
        return false;
    }
    if (strncasecmp(response->content_type, "application/octet-stream", 24) != 0) {
        return false;
    }
    return parse_led_count(response->led_count_text, led_count);
}

static bool response_padding_is_zero(const uint8_t *body, size_t body_len, uint16_t led_count)
{
    if (!body || body_len == 0 || (led_count % 8U) == 0) {
        return true;
    }
    unsigned valid_bits = led_count % 8U;
    uint8_t valid_mask = (uint8_t)((1U << valid_bits) - 1U);
    return (body[body_len - 1U] & (uint8_t)~valid_mask) == 0;
}

static bool led_is_on(const uint8_t *body, size_t body_len, uint16_t index)
{
    if (!body || (size_t)(index / 8U) >= body_len) {
        return false;
    }
    return (body[index / 8U] & (uint8_t)(1U << (index % 8U))) != 0;
}

static size_t append_lit_indices(char *output, size_t output_size, const uint8_t *body,
                                 size_t body_len, uint16_t led_count)
{
    if (!output || output_size == 0) {
        return 0;
    }
    size_t used = 0;
    output[0] = '\0';
    for (uint16_t index = 0; index < led_count; ++index) {
        if (!led_is_on(body, body_len, index)) {
            continue;
        }
        int written = snprintf(output + used, output_size - used, "%s%u",
                               used ? "," : "", (unsigned)index);
        if (written < 0 || (size_t)written >= output_size - used) {
            if (output_size >= 4U) {
                snprintf(output + output_size - 4U, 4U, "...");
            }
            break;
        }
        used += (size_t)written;
    }
    if (used == 0) {
        snprintf(output, output_size, "none");
    }
    return used;
}

static void print_frame_diagnostics(const led_frame_t *frame)
{
    char hex[(TTC_MAX_FRAME_BYTES * 2U) + 1U] = {0};
    char lit_indices[(TTC_BOARD_LED_CAPACITY * 4U) + 8U] = {0};
    size_t hex_used = 0;
    for (size_t i = 0; i < frame->byte_len && hex_used + 2U < sizeof(hex); ++i) {
        hex_used += (size_t)snprintf(hex + hex_used, sizeof(hex) - hex_used, "%02x", frame->bytes[i]);
    }
    append_lit_indices(lit_indices, sizeof(lit_indices), frame->bytes, frame->byte_len,
                       frame->led_count);
    ESP_LOGI(TAG, "RX frame: hex=%s bytes=%u leds=%u source=%s crc32=%08" PRIx32,
             hex, (unsigned)frame->byte_len, (unsigned)frame->led_count, frame->source,
             frame->crc32);
    ESP_LOGI(TAG, "Decoded lit indices: %s", lit_indices);

#if TTC_VERBOSE_LED_LOG
    for (uint16_t index = 0; index < frame->led_count; ++index) {
        ESP_LOGI(TAG, "  led[%u]=%s", (unsigned)index,
                 led_is_on(frame->bytes, frame->byte_len, index) ? "ON" : "off");
    }
#endif
}

static void shift_register_write(gpio_num_t data_pin, gpio_num_t clock_pin, gpio_num_t latch_pin,
                                 uint8_t value)
{
    gpio_set_level(latch_pin, 0);
    for (int bit = 7; bit >= 0; --bit) {
        gpio_set_level(clock_pin, 0);
        gpio_set_level(data_pin, (value >> bit) & 1U);
        gpio_set_level(clock_pin, 1);
    }
    gpio_set_level(clock_pin, 0);
    gpio_set_level(latch_pin, 1);
    gpio_set_level(latch_pin, 0);
}

static void shift_output_init(void)
{
#if TTC_ENABLE_SHIFT_OUTPUT
    const gpio_config_t output_config = {
        .pin_bit_mask = (1ULL << TTC_U2_SER) | (1ULL << TTC_U2_SRCLK) | (1ULL << TTC_U2_RCLK) |
                        (1ULL << TTC_U3_SER) | (1ULL << TTC_U3_SRCLK) | (1ULL << TTC_U3_RCLK),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&output_config));
    shift_register_write(TTC_U2_SER, TTC_U2_SRCLK, TTC_U2_RCLK, 0);
    shift_register_write(TTC_U3_SER, TTC_U3_SRCLK, TTC_U3_RCLK, 0);
#else
    ESP_LOGI(TAG, "74HC595 output disabled by TTC_ENABLE_SHIFT_OUTPUT");
#endif
}

static void shift_frame_to_board(const led_frame_t *frame)
{
#if TTC_ENABLE_SHIFT_OUTPUT
    uint8_t u2 = frame->byte_len > 0 ? frame->bytes[0] & 0x0FU : 0;
    uint8_t u3 = frame->byte_len > 0 ? (frame->bytes[0] >> 4) & 0x0FU : 0;
    shift_register_write(TTC_U2_SER, TTC_U2_SRCLK, TTC_U2_RCLK, u2);
    shift_register_write(TTC_U3_SER, TTC_U3_SRCLK, TTC_U3_RCLK, u3);
    ESP_LOGI(TAG, "74HC595 latch complete: U2=0x%02x U3=0x%02x", u2, u3);
#else
    (void)frame;
#endif
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id,
                               void *event_data)
{
    (void)arg;
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        const wifi_event_sta_disconnected_t *disconnected = event_data;
        xEventGroupClearBits(s_wifi_events, WIFI_CONNECTED_BIT);
        xEventGroupSetBits(s_wifi_events, WIFI_DISCONNECTED_BIT);
        ESP_LOGW(TAG, "Wi-Fi disconnected (reason=%d)",
                 disconnected ? (int)disconnected->reason : -1);
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        xEventGroupClearBits(s_wifi_events, WIFI_DISCONNECTED_BIT);
        xEventGroupSetBits(s_wifi_events, WIFI_CONNECTED_BIT);
        ESP_LOGI(TAG, "Wi-Fi connected; local address acquired");
    }
}

static void wifi_init(void)
{
    s_wifi_events = xEventGroupCreate();
    if (!s_wifi_events) {
        ESP_LOGE(TAG, "Unable to allocate Wi-Fi event group");
        abort();
    }
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_netif_create_default_wifi_sta() ? ESP_OK : ESP_FAIL);

    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&config));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());
}

static bool wifi_connect_any(void)
{
    const size_t profile_count = sizeof(s_wifi_profiles) / sizeof(s_wifi_profiles[0]);
    for (size_t profile = 0; profile < profile_count; ++profile) {
        wifi_config_t config = {0};
        snprintf((char *)config.sta.ssid, sizeof(config.sta.ssid), "%s", s_wifi_profiles[profile].ssid);
        snprintf((char *)config.sta.password, sizeof(config.sta.password), "%s",
                 s_wifi_profiles[profile].password);

        ESP_LOGI(TAG, "Trying Wi-Fi profile %u/%u", (unsigned)(profile + 1U),
                 (unsigned)profile_count);
        xEventGroupClearBits(s_wifi_events, WIFI_CONNECTED_BIT | WIFI_DISCONNECTED_BIT);
        ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &config));
        esp_err_t connect_result = esp_wifi_connect();
        if (connect_result != ESP_OK && connect_result != ESP_ERR_WIFI_STATE) {
            ESP_LOGW(TAG, "Wi-Fi connect request failed: %s", esp_err_to_name(connect_result));
            continue;
        }

        EventBits_t bits = xEventGroupWaitBits(
            s_wifi_events, WIFI_CONNECTED_BIT | WIFI_DISCONNECTED_BIT, pdFALSE, pdFALSE,
            pdMS_TO_TICKS(TTC_WIFI_CONNECT_TIMEOUT_MS));
        if (bits & WIFI_CONNECTED_BIT) {
            return true;
        }
        (void)esp_wifi_disconnect();
        ESP_LOGW(TAG, "Wi-Fi profile %u unavailable", (unsigned)(profile + 1U));
    }
    return false;
}

static void frame_mark_stale_if_needed(void)
{
    if (!s_frame.valid || s_frame.stale) {
        return;
    }
    TickType_t age = xTaskGetTickCount() - s_frame.last_contact;
    if (age < pdMS_TO_TICKS(TTC_STALE_AFTER_MS)) {
        return;
    }
    s_frame.stale = true;
    ESP_LOGW(TAG, "Frame is stale after %" PRIu32 " ms; blanking outputs", TTC_STALE_AFTER_MS);
    led_frame_t blank_frame = s_frame;
    memset(blank_frame.bytes, 0, sizeof(blank_frame.bytes));
    shift_frame_to_board(&blank_frame);
}

typedef enum {
    POLL_OK,
    POLL_UNCHANGED,
    POLL_RETRY,
    POLL_CONFIGURATION_ERROR,
} poll_result_t;

static poll_result_t poll_frame(void)
{
    http_response_t response = {0};
    esp_http_client_config_t config = {
        .url = TTC_FRAME_URL,
        .event_handler = http_event_handler,
        .user_data = &response,
        .timeout_ms = TTC_HTTP_TIMEOUT_MS,
        .disable_auto_redirect = true,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        ESP_LOGE(TAG, "HTTP client allocation failed");
        return POLL_RETRY;
    }
    ESP_ERROR_CHECK_WITHOUT_ABORT(esp_http_client_set_header(client, "Accept", "application/octet-stream"));
    if (s_frame.valid && s_frame.etag[0]) {
        ESP_ERROR_CHECK_WITHOUT_ABORT(esp_http_client_set_header(client, "If-None-Match", s_frame.etag));
    }

    esp_err_t request_result = esp_http_client_perform(client);
    if (request_result != ESP_OK) {
        ESP_LOGW(TAG, "HTTP request failed: %s", esp_err_to_name(request_result));
        esp_http_client_cleanup(client);
        return POLL_RETRY;
    }

    int status = esp_http_client_get_status_code(client);
    if (status == 304) {
        if (!s_frame.valid || strcmp(response.etag, s_frame.etag) != 0) {
            ESP_LOGW(TAG, "HTTP 304 received without a matching valid frame");
            esp_http_client_cleanup(client);
            return POLL_RETRY;
        }
        bool was_stale = s_frame.stale;
        s_frame.last_contact = xTaskGetTickCount();
        s_frame.stale = false;
        ESP_LOGI(TAG, "HTTP 304: frame unchanged; state remains valid");
        if (was_stale) {
            shift_frame_to_board(&s_frame);
        }
        esp_http_client_cleanup(client);
        return POLL_UNCHANGED;
    }

    if (status != 200) {
        ESP_LOGW(TAG, "HTTP status=%d; response rejected", status);
        esp_http_client_cleanup(client);
        return status == 404 ? POLL_CONFIGURATION_ERROR : POLL_RETRY;
    }

    uint16_t led_count = 0;
    size_t expected_bytes = 0;
    bool valid = response_has_required_headers(&response, &led_count);
    if (valid) {
        expected_bytes = (led_count + 7U) / 8U;
        valid = response.body_len == expected_bytes && response_padding_is_zero(
                    response.body, response.body_len, led_count);
    }
    if (!valid) {
        ESP_LOGW(TAG, "HTTP 200 response rejected: headers/body do not match contract");
        esp_http_client_cleanup(client);
        return POLL_RETRY;
    }

    memset(s_frame.bytes, 0, sizeof(s_frame.bytes));
    memcpy(s_frame.bytes, response.body, response.body_len);
    s_frame.byte_len = response.body_len;
    s_frame.led_count = led_count;
    s_frame.crc32 = crc32_frame(s_frame.bytes, s_frame.byte_len);
    copy_header(s_frame.etag, sizeof(s_frame.etag), response.etag);
    copy_header(s_frame.generated_at, sizeof(s_frame.generated_at), response.generated_at);
    copy_header(s_frame.source, sizeof(s_frame.source), response.source);
    s_frame.last_contact = xTaskGetTickCount();
    s_frame.valid = true;
    s_frame.stale = false;

    print_frame_diagnostics(&s_frame);
    shift_frame_to_board(&s_frame);
    esp_http_client_cleanup(client);
    return POLL_OK;
}

void app_main(void)
{
    esp_err_t nvs_result = nvs_flash_init();
    if (nvs_result == ESP_ERR_NVS_NO_FREE_PAGES || nvs_result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        nvs_result = nvs_flash_init();
    }
    ESP_ERROR_CHECK(nvs_result);

    shift_output_init();
    wifi_init();

    uint32_t reconnect_delay_ms = TTC_WIFI_RETRY_BASE_MS;
    uint32_t poll_failure_delay_ms = TTC_POLL_INTERVAL_MS;
    while (true) {
        EventBits_t wifi_bits = xEventGroupGetBits(s_wifi_events);
        if ((wifi_bits & WIFI_CONNECTED_BIT) == 0) {
            if (!wifi_connect_any()) {
                ESP_LOGW(TAG, "No configured Wi-Fi profile connected; retrying in %" PRIu32 " ms",
                         reconnect_delay_ms);
                vTaskDelay(pdMS_TO_TICKS(reconnect_delay_ms));
                reconnect_delay_ms = reconnect_delay_ms < TTC_WIFI_RETRY_MAX_MS / 2U
                                         ? reconnect_delay_ms * 2U
                                         : TTC_WIFI_RETRY_MAX_MS;
                frame_mark_stale_if_needed();
                continue;
            }
            reconnect_delay_ms = TTC_WIFI_RETRY_BASE_MS;
        }

        poll_result_t result = poll_frame();
        if (result == POLL_OK || result == POLL_UNCHANGED) {
            poll_failure_delay_ms = TTC_POLL_INTERVAL_MS;
        } else if (result == POLL_CONFIGURATION_ERROR) {
            poll_failure_delay_ms = 60000U;
            ESP_LOGE(TAG, "Server/map configuration error; retrying in 60 seconds");
        } else {
            ESP_LOGW(TAG, "Poll failed; retrying in %" PRIu32 " ms", poll_failure_delay_ms);
            poll_failure_delay_ms = poll_failure_delay_ms < 60000U / 2U
                                        ? poll_failure_delay_ms * 2U
                                        : 60000U;
        }
        frame_mark_stale_if_needed();
        vTaskDelay(pdMS_TO_TICKS(poll_failure_delay_ms));
    }
}
